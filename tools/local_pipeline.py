"""Subscription-backed local generation, durable catch-up, and protected publishing."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

if __package__:
    from . import collect_arxiv, publish_digest
    from .import_digest import parse_digest
    from .speech_text import make_script
else:
    import collect_arxiv
    import publish_digest
    from import_digest import parse_digest
    from speech_text import make_script

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.cache' / 'local-pipeline'
CONFIG = ROOT / 'local-pipeline.json'
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'status': {'type': 'string', 'enum': ['ready', 'insufficient']},
                   'reason': {'type': 'string'}, 'markdown': {'type': 'string'},
                   'math_pronunciations': {'type': 'array', 'items': {
                       'type': 'object', 'additionalProperties': False,
                       'properties': {'latex': {'type': 'string'}, 'spoken': {'type': 'string'}},
                       'required': ['latex', 'spoken']}}},
    'required': ['status', 'reason', 'markdown', 'math_pronunciations'],
}
COMPLETE = {'published', 'no-batch'}


class SnapshotPending(RuntimeError):
    """Only the cloud collector crawls arXiv; local runs wait for its archive."""


def load_config():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    # The app schedule controls the same model used by startup catch-up runs.
    runtime_file = RUNTIME / 'runtime.json'
    if runtime_file.exists():
        runtime = json.loads(runtime_file.read_text(encoding='utf-8'))
        automation_id = runtime.get('automation_id')
        if automation_id and all(character.isalnum() or character in '-_' for character in automation_id):
            state_root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
            automation_file = state_root / 'automations' / automation_id / 'automation.toml'
            if automation_file.exists():
                saved = tomllib.loads(automation_file.read_text(encoding='utf-8'))
                config['enabled'] = saved.get('status') == 'ACTIVE'
                if saved.get('model'):
                    config['model'] = saved['model']
                effort = saved.get('reasoning_effort') or saved.get('model_reasoning_effort')
                if effort:
                    config['reasoning_effort'] = effort
    date.fromisoformat(config['start_date'])
    ZoneInfo(config['timezone'])
    if config.get('allow_paid_api') is not False or config.get('require_chatgpt_login') is not True:
        raise ValueError('This workflow requires subscription login and forbids paid model APIs')
    if config['reasoning_effort'] not in ('low', 'medium', 'high', 'xhigh', 'max'):
        raise ValueError('Invalid reasoning effort')
    if not isinstance(config['model'], str) or not config['model'].startswith('gpt-'):
        raise ValueError('Choose an available GPT model explicitly; no automatic fallback is allowed')
    time(config['hour'], config['minute'])
    return config


def expected_dates(config, now):
    """All due weekdays, including older days and gaps between published dates."""
    local = now.astimezone(ZoneInfo(config['timezone']))
    end = local.date()
    if local.time() < time(config['hour'], config['minute']):
        end -= timedelta(days=1)
    day = date.fromisoformat(config['start_date'])
    result = []
    while day <= end:
        if day.weekday() < 5:
            result.append(day.isoformat())
        day += timedelta(days=1)
    return result


def read_state():
    path = RUNTIME / 'state.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'days': {}}


def save_state(state):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    target = RUNTIME / 'state.json'
    temporary = RUNTIME / 'state.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)


def plan(config, state, now):
    published_local = {path.stem for folder, pattern in ((ROOT / 'content/digests', '*.json'), (ROOT / 'incoming', '*.md'))
                       for path in folder.glob(pattern) if path.stem != 'README'}
    due, waiting, review = [], [], []
    pause_until = state.get('pause_until')
    paused = bool(pause_until and datetime.fromisoformat(pause_until) > now)
    for day in expected_dates(config, now):
        item = state.get('days', {}).get(day, {})
        if day in published_local or item.get('status') in COMPLETE:
            continue
        if item.get('status') == 'needs-review':
            review.append(day)
            continue
        retry_at = item.get('retry_at')
        if paused or (retry_at and datetime.fromisoformat(retry_at) > now):
            waiting.append(day)
        else:
            due.append(day)
    return {'due': due, 'waiting': waiting, 'needs_review': review,
            'model': config['model'], 'effort': config['reasoning_effort'],
            'enabled': config.get('enabled', True),
            'timezone': config['timezone'], 'time': f"{config['hour']:02}:{config['minute']:02}"}


@contextmanager
def pipeline_lock():
    """OS lock releases after crashes; a startup and daily trigger cannot overlap."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    handle = (RUNTIME / 'run.lock').open('a+b')
    if os.fstat(handle.fileno()).st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
        yield acquired
    finally:
        if acquired:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def child_environment():
    environment = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN',
                'ARXIV_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN'):
        environment.pop(key, None)
    environment['PYTHONUTF8'] = '1'
    return environment


def find_codex():
    available = shutil.which('codex')
    if available:
        return available
    runtime_file = RUNTIME / 'runtime.json'
    if runtime_file.exists():
        saved = json.loads(runtime_file.read_text(encoding='utf-8')).get('codex')
        if saved and Path(saved).is_file():
            return saved
    # The desktop app includes its CLI. Account for updates replacing its bin.
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
    binaries = sorted(base.glob('*/codex.exe'), key=lambda path: path.stat().st_mtime, reverse=True)
    if binaries:
        return str(binaries[0])
    raise RuntimeError('Codex CLI is unavailable; open/update the desktop app or install the CLI')


def app_is_running():
    if os.name != 'nt':
        return False
    command = "$p = @(Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ($_.Path -like '*\\WindowsApps\\OpenAI.Codex_*\\app\\ChatGPT.exe' -or $_.Path -like '*\\app\\Codex.exe') }); if ($p.Count -gt 0) { 'yes' } else { 'no' }"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, timeout=20)
    return result.returncode == 0 and result.stdout.strip() == 'yes'


def github_token():
    # The token remains in this Python process; it never enters the model prompt,
    # child environment, logs, source files, or the scheduled-task definition.
    executable = shutil.which('gh')
    if not executable:
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'GitHub CLI/gh.exe'
        executable = str(candidate) if candidate.exists() else None
    if not executable:
        raise RuntimeError('GitHub CLI is missing')
    result = subprocess.run([executable, 'auth', 'token'], capture_output=True, text=True, timeout=30)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('GitHub CLI login is unavailable; run gh auth login outside the task')
    return result.stdout.strip()


def read_remote_snapshot(day, token):
    date.fromisoformat(day)
    request = urllib.request.Request(
        f'https://api.github.com/repos/{publish_digest.REPOSITORY}/contents/sources/{day}.json?ref=main',
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github.raw+json',
                 'User-Agent': 'daily-arxiv-local/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(f'GitHub snapshot read returned HTTP {error.code}') from None
    return data


def validate_snapshot(snapshot, day):
    expected_metadata = 'feed' if snapshot.get('version', 1) >= 3 else 'v1'
    if snapshot.get('date') != day or snapshot.get('metadata_version') != expected_metadata:
        raise ValueError('Snapshot date/version mismatch')
    papers = snapshot.get('papers', [])
    if len({paper['id'] for paper in papers}) != len(papers):
        raise ValueError('Snapshot contains duplicate IDs')
    if not snapshot.get('listing_sources'):
        raise ValueError('Snapshot lacks dated listing evidence')
    for paper in papers:
        if paper.get('announcement_date') != day or not paper.get('abstract'):
            raise ValueError('Paper date or saved abstract is missing')
        if not collect_arxiv.ARXIV_ID.fullmatch(paper['id']) or 'v' in paper['id']:
            raise ValueError('Snapshot contains an invalid paper ID')
        if snapshot.get('version', 1) >= 2 and (paper.get('first_announcement_date') != day or not paper.get('primary_listing_sources')):
            raise ValueError('Paper lacks first-announcement evidence for this date')
        if snapshot.get('version', 1) >= 3:
            origin = paper.get('metadata_origin')
            if snapshot.get('source_format') != 'arxiv-atom' or paper.get('announcement_type') != 'new' or origin != 'arxiv-atom':
                raise ValueError('Feed snapshot lacks an original new announcement')
            if not re.fullmatch(re.escape(paper['id']) + r'v[1-9]\d*', paper.get('feed_id', '')):
                raise ValueError('Feed metadata has an invalid version')
            published = datetime.fromisoformat(paper.get('feed_published', ''))
            if published.tzinfo is None or published.date().isoformat() != day or paper.get('versioned_url') != f'https://arxiv.org/abs/{paper["feed_id"]}':
                raise ValueError('Feed snapshot has incorrect dated version evidence')
    return snapshot


def get_snapshot(day, config, token):
    cache = RUNTIME / 'inputs'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f'{day}.json'
    if target.exists():
        return validate_snapshot(json.loads(target.read_text(encoding='utf-8')), day)
    local = ROOT / 'sources' / f'{day}.json'
    snapshot = json.loads(local.read_text(encoding='utf-8')) if local.exists() else read_remote_snapshot(day, token)
    if snapshot is None:
        raise SnapshotPending(f'No verified announcement snapshot for {day}; waiting for the GitHub collector')
    validate_snapshot(snapshot, day)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return snapshot


def catalog(snapshot):
    return {'date': snapshot['date'], 'paper_count': len(snapshot['papers']),
            'listing_sources': snapshot['listing_sources'],
            'papers': [{key: paper[key] for key in ('id', 'title', 'categories')} for paper in snapshot['papers']]}


def generation_command(executable, config, output, schema):
    return [executable, '--search', 'exec', '--ignore-user-config',
            '-c', 'forced_login_method="chatgpt"', '-c', 'model_provider="openai"',
            '-c', 'service_tier="standard"', '-c', f'model_reasoning_effort="{config["reasoning_effort"]}"',
            '-m', config['model'], '--approve-for-me',
            '-C', str(ROOT), '--output-schema', str(schema), '--output-last-message', str(output), '--json', '-']


def generate(day, snapshot, config):
    folder = RUNTIME / 'runs' / day
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / 'result.json'
    if output.exists():
        return json.loads(output.read_text(encoding='utf-8'))
    executable = find_codex()
    auth = subprocess.run([executable, '-c', 'forced_login_method="chatgpt"', 'login', 'status'],
                          capture_output=True, text=True, env=child_environment(), timeout=30)
    if auth.returncode or 'ChatGPT' not in auth.stdout + auth.stderr:
        raise RuntimeError('ChatGPT subscription login is required; no API-key fallback is permitted')
    catalog_file = folder / 'catalog.json'
    catalog_file.write_text(json.dumps(catalog(snapshot), ensure_ascii=False) + '\n', encoding='utf-8')
    schema_file = folder / 'result-schema.json'
    schema_file.write_text(json.dumps(SCHEMA), encoding='utf-8')
    prompt = (ROOT / 'prompts/local-research.md').read_text(encoding='utf-8')
    prompt += f'\n\nExact target date: {day}.\nCatalog: {catalog_file}.\n'
    prompt += f'Metadata lookup: python tools/local_pipeline.py paper {day} ID1 ID2 ...\n'
    prompt += 'The metadata lookup only reads saved announcement data. Use the exact source version recorded in source_v1 (legacy snapshots) or versioned_url (feed snapshots). You may read files and use live web search. Use automatic approval review for required read commands. Return the digest in your final JSON, not through file writes.\n'
    with (folder / 'events.jsonl').open('w', encoding='utf-8') as events, (folder / 'stderr.log').open('w', encoding='utf-8') as errors:
        result = subprocess.run(generation_command(executable, config, output, schema_file), input=prompt,
                                text=True, encoding='utf-8', stdout=events, stderr=errors,
                                cwd=ROOT, env=child_environment(), timeout=config['generation_timeout_minutes'] * 60)
    if result.returncode or not output.exists():
        raise RuntimeError(f'Codex generation failed for {day}; queued for retry, see its local run log')
    return json.loads(output.read_text(encoding='utf-8'))


def validate_result(result, snapshot, day):
    if result.get('status') != 'ready':
        raise ValueError('No complete digest was generated')
    text = result['markdown']
    digest = parse_digest(text)
    if digest['date'] != day:
        raise ValueError('Generated digest has the wrong date')
    candidates = {paper['id']: paper for paper in snapshot['papers']}
    for paper in digest['papers']:
        if paper['id'] not in candidates:
            raise ValueError('Generated paper is outside the verified announcement batch')
        normalize = lambda value: collect_arxiv.clean(html.unescape(value))
        if normalize(paper['title']) != normalize(candidates[paper['id']]['title']):
            raise ValueError(f"Title does not match verified announcement metadata for {paper['id']}")
        if 'priority' in paper:
            raise ValueError('New digests must omit priority verdicts')
    make_script(digest, result.get('math_pronunciations', []))
    return text, digest


def run_pipeline(limit=None, automatic=False):
    with pipeline_lock() as acquired:
        if not acquired:
            return {'status': 'already-running'}
        config = load_config()
        state = read_state()
        now = datetime.now(timezone.utc)
        pending = plan(config, state, now)
        if automatic and not config.get('enabled', True):
            return {'status': 'paused', **pending}
        if not pending['due']:
            return {'status': 'up-to-date', **pending}
        if not app_is_running():
            return {'status': 'waiting-for-app', **pending}
        token = github_token()
        results = []
        for day in pending['due'][:limit] if limit else pending['due']:
            if not app_is_running():
                return {'status': 'waiting-for-app', 'results': results, 'remaining': plan(config, state, datetime.now(timezone.utc))}
            attempted = datetime.now(timezone.utc)
            try:
                if publish_digest.check_date(day, token)['status'] == 'exists':
                    state['days'][day] = {'status': 'published', 'verified_at': attempted.isoformat()}
                    save_state(state)
                    results.append({'date': day, 'status': 'already-delivered'})
                    continue
                snapshot = get_snapshot(day, config, token)
                if not snapshot['papers']:
                    state['days'][day] = {'status': 'no-batch', 'verified_at': attempted.isoformat()}
                    save_state(state)
                    results.append({'date': day, 'status': 'no-batch'})
                    continue
                state['days'][day] = {'status': 'generating', 'attempted_at': attempted.isoformat()}
                save_state(state)
                result = generate(day, snapshot, config)
                if result.get('status') == 'insufficient':
                    state['days'][day] = {'status': 'needs-review', 'reason': result.get('reason', 'Insufficient appropriate papers')}
                    save_state(state)
                    results.append({'date': day, 'status': 'needs-review'})
                    continue
                markdown, digest = validate_result(result, snapshot, day)
                draft = RUNTIME / 'runs' / day / f'{day}.md'
                draft.write_text(markdown, encoding='utf-8')
                script = make_script(digest, result.get('math_pronunciations', []))
                (draft.parent / 'speech.json').write_text(json.dumps(script, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                publication = publish_digest.publish(markdown, token, speech_script=script)
                if publish_digest.check_date(day, token)['status'] != 'exists':
                    raise RuntimeError('GitHub did not confirm the published file')
                state['days'][day] = {'status': 'published', 'papers': len(digest['papers']),
                                      'model': config['model'], 'effort': config['reasoning_effort'],
                                      'commit': publication.get('commit'), 'verified_at': datetime.now(timezone.utc).isoformat()}
                save_state(state)
                results.append(publication)
            except SnapshotPending as error:
                # This checks GitHub, not arXiv, and never starts a model call.
                retry_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                state['days'][day] = {'status': 'retry', 'waiting_for': 'archive',
                                      'reason': str(error), 'retry_at': retry_at}
                save_state(state)
                results.append({'date': day, 'status': 'retry', 'waiting_for': 'archive', 'reason': str(error)})
                continue
            except ValueError as error:
                state['days'][day] = {'status': 'needs-review', 'reason': str(error)}
                save_state(state)
                results.append({'date': day, 'status': 'needs-review', 'reason': str(error)})
                continue
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                retry_at = (datetime.now(timezone.utc) + timedelta(minutes=config['retry_minutes'])).isoformat()
                state['days'][day] = {'status': 'retry', 'reason': str(error),
                                      'retry_at': retry_at}
                state['pause_until'] = retry_at
                save_state(state)
                results.append({'date': day, 'status': 'retry', 'reason': str(error)})
                # Stop this session on failure; later triggers resume the queue
                # without repeating completed days or buying additional credits.
                break
        return {'status': 'processed', 'results': results,
                'remaining': plan(config, state, datetime.now(timezone.utc))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'run', 'paper', 'status', 'retry'), nargs='?', default='plan')
    parser.add_argument('date', nargs='?')
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--automatic', action='store_true', help='Honor the saved task pause setting')
    args = parser.parse_args()
    if args.command == 'retry':
        date.fromisoformat(args.date)
        with pipeline_lock() as acquired:
            if not acquired:
                raise SystemExit('A worker is active; retry after it finishes')
            state = read_state()
            if state.get('days', {}).get(args.date, {}).get('status') in COMPLETE:
                raise SystemExit('Completed dates are protected')
            result = RUNTIME / 'runs' / args.date / 'result.json'
            if result.exists():
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
                result.replace(result.with_name(f'result.previous-{stamp}.json'))
            state.setdefault('days', {}).pop(args.date, None)
            state.pop('pause_until', None)
            save_state(state)
        print(json.dumps({'status': 'retry-enabled', 'date': args.date}))
    elif args.command == 'paper':
        date.fromisoformat(args.date)
        if not 1 <= len(args.ids) <= 20:
            parser.error('Request 1–20 paper IDs at a time')
        snapshot = json.loads((RUNTIME / 'inputs' / f'{args.date}.json').read_text(encoding='utf-8'))
        selected = {paper['id']: paper for paper in snapshot['papers']}
        if any(paper_id not in selected for paper_id in args.ids):
            raise SystemExit('ID is outside this dated batch')
        print(json.dumps([selected[paper_id] for paper_id in args.ids], ensure_ascii=False))
    elif args.command == 'run':
        print(json.dumps(run_pipeline(args.limit, automatic=args.automatic), ensure_ascii=False))
    else:
        result = plan(load_config(), read_state(), datetime.now(timezone.utc))
        if args.command == 'status':
            result['days'] = read_state().get('days', {})
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
