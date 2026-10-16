"""Publish one validated Markdown digest; credentials stay in the environment."""
import argparse
import base64
import datetime
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

if __package__:
    from .import_digest import parse_digest
    from .speech_text import make_script
else:
    from import_digest import parse_digest
    from speech_text import make_script

REPOSITORY = "zhou-yang-quantum/daily-arXiv"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}/contents/incoming/"


def api_request(method, date, token, payload=None):
    datetime.date.fromisoformat(date)
    url = API_ROOT + date + ".md"
    if method == "GET":
        url += "?ref=main"
    request = urllib.request.Request(
        url, method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "daily-arxiv-publisher/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if method == "GET" and error.code == 404:
            return None
        # Do not print requests, headers, environment values, or response bodies.
        raise RuntimeError(f"GitHub returned HTTP {error.code}; check the cloud credential's repository access") from None


def check_date(date, token):
    datetime.date.fromisoformat(date)
    existing = api_request("GET", date, token)
    return {"date": date, "status": "exists" if existing is not None else "missing"}


def git_request(method, path, token, payload=None):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{REPOSITORY}/git/' + path, method=method,
        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'daily-arxiv-publisher/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def publish_bundle(text, script, token):
    """One Git commit delivers text and its matching speech metadata together."""
    date = script['date']
    for attempt in range(3):
        # Never overwrite another run's dated entry, even if the branch moved.
        existing = api_request('GET', date, token)
        if existing is not None:
            previous = base64.b64decode(existing['content']).decode('utf-8')
            if previous.rstrip() != text.rstrip():
                raise ValueError(f'{date} already exists with different content; refusing to overwrite it')
            return None
        base = git_request('GET', 'ref/heads/main', token)['object']['sha']
        tree = git_request('GET', 'commits/' + base, token)['tree']['sha']
        entries = [('incoming/' + date + '.md', text),
                   ('audio/scripts/' + date + '.json', json.dumps(script, ensure_ascii=False, indent=2) + '\n')]
        updated = git_request('POST', 'trees', token, {'base_tree': tree, 'tree': [
            {'path': path, 'mode': '100644', 'type': 'blob', 'content': content} for path, content in entries]})
        commit = git_request('POST', 'commits', token, {
            'message': f'Add arXiv-{date} selection and speech pronunciations',
            'tree': updated['sha'], 'parents': [base]})
        try:
            git_request('PATCH', 'refs/heads/main', token, {'sha': commit['sha'], 'force': False})
            return commit['sha']
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422) or attempt == 2:
                raise RuntimeError(f'GitHub returned HTTP {error.code}; publication was not confirmed') from None
    raise RuntimeError('Publication was not confirmed')


def publish(text, token, speech_script=None):
    digest = parse_digest(text)
    date = digest["date"]
    count = len(digest["papers"])
    if speech_script is not None:
        if speech_script != make_script(digest, speech_script.get('pronunciations', []), version=speech_script.get('version'),
                                        phrase_groups=speech_script.get('phrase_groups', [])):
            raise ValueError('Speech metadata does not match the digest')
    existing = api_request("GET", date, token)
    if existing is not None:
        if existing.get("encoding") != "base64":
            raise ValueError("Cannot verify the existing digest; refusing to overwrite it")
        previous = base64.b64decode(existing["content"]).decode("utf-8")
        if previous.rstrip() != text.rstrip():
            raise ValueError(f"{date} already exists with different content; refusing to overwrite it")
        return {"date": date, "papers": count, "status": "already-delivered"}
    if speech_script is not None:
        sha = publish_bundle(text, speech_script, token)
        return {'date': date, 'papers': count, 'status': 'publication-queued' if sha else 'already-delivered',
                'commit': sha, 'website': f'https://zhou-yang-quantum.github.io/daily-arXiv/#date={date}'}
    result = api_request("PUT", date, token, {
        "message": f"Add arXiv-{date} selection",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": "main",
    })
    if not result.get("commit", {}).get("sha"):
        raise RuntimeError("GitHub did not confirm a commit; publication is unverified")
    return {
        "date": date, "papers": count, "status": "publication-queued",
        "commit": result["commit"]["sha"],
        "website": f"https://zhou-yang-quantum.github.io/daily-arXiv/#date={date}",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path, nargs="?")
    parser.add_argument("--check-date", help="Return only whether this date is already delivered")
    args = parser.parse_args()
    if bool(args.markdown) == bool(args.check_date):
        parser.error("Supply either a Markdown file or --check-date YYYY-MM-DD")
    token = os.environ.get("ARXIV_GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("ARXIV_GITHUB_TOKEN is missing; configure it in the cloud environment, not in a source file")
    try:
        result = check_date(args.check_date, token) if args.check_date else publish(
            args.markdown.read_text(encoding="utf-8-sig"), token)
    except (ValueError, RuntimeError, OSError, urllib.error.URLError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
