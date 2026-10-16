"""Render immutable MP3 releases with offline CPU speech; no model APIs."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import wave
import zipfile

if __package__:
    from .build import ROOT, load_archive, audio_source_hash, audio_script_hash
    from .speech_text import make_script
    from .project import REPOSITORY, WEBSITE, canonical_audio_manifest
else:
    from build import ROOT, load_archive, audio_source_hash, audio_script_hash
    from speech_text import make_script
    from project import REPOSITORY, WEBSITE, canonical_audio_manifest

VOICE = 'af_heart'
MODEL_SHA = 'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a'
CONFIG_SHA = 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'
CACHE = ROOT / '.cache/audio'


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    if result.returncode:
        # Only a diagnostic tail; never include credentials or request headers.
        raise RuntimeError(f'{Path(args[0]).name} failed: {result.stderr[-1200:]}')
    return result.stdout


def fingerprint(prepared):
    settings = {'voice': VOICE, 'voice_sha': MODEL_SHA, 'config_sha': CONFIG_SHA, 'engine': 'kokoro-onnx-0.6.1', 'speed': 1.0, 'encoder': 'mp3-64k-id3-v1', 'content': prepared}
    return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def playlist_name(manifest):
    stamp = manifest['date']
    if date.fromisoformat(stamp).isoformat() != stamp:
        raise ValueError('Invalid playlist date')
    return f'arxiv-{stamp}-playlist.zip'


def build_playlist_archive(manifest, folder):
    """Keep the original item MP3 bytes, with portable dated, ordered names."""
    ranks = [item['rank'] for item in manifest['items']]
    if ranks != list(range(1, len(ranks) + 1)) or not ranks:
        raise ValueError('Playlist items must be consecutively ranked')
    target = folder / playlist_name(manifest)
    partial = target.with_suffix('.partial.zip')
    with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_STORED) as archive:
        for rank in ranks:
            source = folder / f'item-{rank:02}.mp3'
            info = zipfile.ZipInfo(f'arxiv-{manifest["date"]}-item-{rank:02}.mp3')
            # Keep the ZIP checksum stable when rendering on Linux and publishing on Windows.
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    partial.replace(target)
    return target


def ensure_playlist(manifest, tag):
    """Add a download to an existing release without re-synthesizing speech."""
    manifest = canonical_audio_manifest(manifest)
    base = f'https://github.com/{REPOSITORY}/releases/download/{tag}/'
    if manifest['day']['url'] != base + 'day.mp3' or not tag.startswith('audio-' + manifest['date'] + '-'):
        raise ValueError('Playlist release does not match the recording')
    name = playlist_name(manifest)
    url = base + name
    if manifest.get('playlist_url') == url:
        return manifest
    release = json.loads(command(['gh', 'release', 'view', tag, '--repo', REPOSITORY, '--json', 'assets']))
    folder = CACHE / 'renders' / tag
    folder.mkdir(parents=True, exist_ok=True)
    if name not in {asset['name'] for asset in release.get('assets', [])}:
        for item in manifest['items']:
            filename = f'item-{item["rank"]:02}.mp3'
            if not (folder / filename).exists():
                command(['gh', 'release', 'download', tag, '--repo', REPOSITORY, '--pattern', filename, '--dir', str(folder)], timeout=180)
        archive = build_playlist_archive(manifest, folder)
        command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber', str(archive)], timeout=300)
    updated = {**manifest, 'playlist_url': url}
    path = folder / 'manifest.json'
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber', str(path)])
    return updated


def cached_release(tag):
    result = subprocess.run(['gh', 'api', f'repos/{REPOSITORY}/releases/tags/{tag}'], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        if '404' in result.stderr:
            return None
        raise RuntimeError('Could not check the audio release; refusing duplicate generation')
    data = json.loads(result.stdout)
    names = {asset['name'] for asset in data.get('assets', [])}
    if 'manifest.json' not in names:
        return None
    asset = next(asset for asset in data['assets'] if asset['name'] == 'manifest.json')
    manifest = json.loads(command(['gh', 'api', f'repos/{REPOSITORY}/releases/assets/{asset["id"]}', '-H', 'Accept: application/octet-stream']))
    manifest = canonical_audio_manifest(manifest)
    required = {'day.mp3'} | {f'item-{item["rank"]:02}.mp3' for item in manifest['items']}
    if manifest.get('version') in (2, 3, 4, 5, 6):
        required.add('speech.txt')
    if not required <= names:
        return None
    name = playlist_name(manifest)
    if name in names:
        manifest['playlist_url'] = f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}'
    else:
        manifest.pop('playlist_url', None)
    return manifest


def download_voice():
    folder = CACHE / 'voice'
    folder.mkdir(parents=True, exist_ok=True)
    base = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
    for name, expected in (('kokoro-v1.0.onnx', MODEL_SHA), ('voices-v1.0.bin', CONFIG_SHA)):
        target = folder / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        print('Downloading pinned speech asset ' + target.name, flush=True)
        partial = target.with_suffix(target.suffix + '.partial')
        with urllib.request.urlopen(base + target.name, timeout=120) as response, partial.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if hashlib.sha256(partial.read_bytes()).hexdigest() != expected:
            raise ValueError('Speech model checksum mismatch')
        partial.replace(target)
    return folder / 'kokoro-v1.0.onnx', folder / 'voices-v1.0.bin'


def duration(path):
    with wave.open(str(path), 'rb') as wav:
        return wav.getnframes() / wav.getframerate()


def save_index(path, index):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def append_silence(output, seconds):
    output.writeframes(b'\0' * round(seconds * output.getframerate()) * output.getnchannels() * output.getsampwidth())


def concatenate(paths, target):
    with wave.open(str(target), 'wb') as output:
        for index, path in enumerate(paths):
            with wave.open(str(path), 'rb') as source:
                if index == 0:
                    output.setparams(source.getparams())
                elif (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (output.getframerate(), output.getnchannels(), output.getsampwidth()):
                    raise ValueError('Incompatible speech segments')
                output.writeframes(source.readframes(source.getnframes()))


def text_chunks(text, limit=650, protected_spans=()):
    words, chunk, size = [], [], 0
    for word in re.finditer(r'\S+', text):
        # Pack all words of a protected phrase as one unit, keeping its sentence context.
        if words and any(start < word.start() < end for start, end in protected_spans):
            words[-1] += ' ' + word.group()
        else:
            words.append(word.group())
    for word in words:
        if chunk and size + len(word) + 1 > limit:
            yield ' '.join(chunk)
            chunk, size = [], 0
        chunk.append(word)
        size += len(word) + 1
    if chunk:
        yield ' '.join(chunk)


def render(prepared, tag, voice):
    import numpy as np
    folder = CACHE / 'renders' / tag
    folder.mkdir(parents=True, exist_ok=True)
    paths, items, elapsed = [], [], 0.0
    for item in prepared['items']:
        name = f'item-{item["rank"]:02}'
        sections = item['sections']
        expected = ['heading', 'authors', 'summary', 'background', 'why'] if prepared['version'] >= 3 else ['heading', 'summary', 'background', 'why']
        if prepared['version'] >= 4:
            expected.insert(0, 'item')
        if [section['name'] for section in sections] != expected:
            raise ValueError('Speech sections are missing or out of order')
        section_paths = []
        for section in sections:
            target = folder / (name + '-' + section['name'] + '.wav')
            if not target.exists():
                partial = target.with_suffix('.partial.wav')
                with wave.open(str(partial), 'wb') as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(24000)
                    segments = section.get('segments', [{'text': section['text'], 'speed': 1.0}]) if prepared['version'] >= 5 else [{'text': section['text'], 'speed': 1.0}]
                    for segment in segments:
                        if 'pause_seconds' in segment:
                            append_silence(output, segment['pause_seconds'])
                            continue
                        chunks = text_chunks(segment['text'], protected_spans=segment.get('protected_spans', []))
                        for index, chunk in enumerate(chunks):
                            samples, rate = voice.create(chunk, voice=VOICE, speed=segment['speed'], lang='en-us')
                            if rate != 24000 or not len(samples):
                                raise ValueError('Speech synthesis returned invalid audio')
                            if index:
                                append_silence(output, 0.2)
                            output.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
                partial.replace(target)
            section_paths.append(target)
        target = folder / (name + '.wav')
        silence, boundaries, position = [], [], 0.0
        with wave.open(str(target), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            for index, section_path in enumerate(section_paths):
                if index:
                    if sections[index]['name'] == 'heading':
                        pause = prepared['item_title_pause_seconds']
                    elif sections[index]['name'] == 'authors':
                        pause = prepared['title_author_pause_seconds']
                    elif sections[index]['name'] == 'summary':
                        pause = prepared['heading_pause_seconds']
                    else:
                        pause = prepared['section_pause_seconds']
                    silence.append({'start': round(position, 3), 'duration': pause})
                    append_silence(output, pause)
                    position += pause
                length = duration(section_path)
                boundaries.append({'name': sections[index]['name'], 'start': round(position, 3), 'duration': round(length, 3)})
                with wave.open(str(section_path), 'rb') as source:
                    output.writeframes(source.readframes(source.getnframes()))
                position += length
            append_silence(output, prepared['item_pause_seconds'])
        length = duration(target)
        command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(target), '-c:a', 'libmp3lame', '-b:a', '64k', '-write_xing', '1',
                 '-metadata', 'title=' + prepared['title'] + ' — Item ' + str(item['rank']) + ' — ' + item['title'],
                 '-metadata', 'artist=daily-arXiv', '-metadata', 'album=' + prepared['title'], str(folder / (name + '.mp3'))])
        items.append({key: item[key] for key in ('rank', 'id', 'title')} | {'start': round(elapsed, 3), 'duration': round(length, 3),
                     'sections': boundaries, 'silence': silence})
        elapsed += length
        paths.append(target)
        print('Rendered item ' + str(item['rank']), flush=True)
    # The complete day is exactly the item PCM recordings joined in rank order.
    combined = folder / 'day.wav'
    concatenate(paths, combined)
    command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(combined), '-c:a', 'libmp3lame', '-b:a', '64k', '-write_xing', '1',
             '-metadata', 'title=' + prepared['title'] + ' — Full digest', '-metadata', 'artist=daily-arXiv',
             '-metadata', 'album=' + prepared['title'], str(folder / 'day.mp3')], timeout=300)
    (folder / 'speech.txt').write_text(prepared['text'] + '\n', encoding='utf-8')
    base = f'https://github.com/{REPOSITORY}/releases/download/{tag}/'
    for item in items:
        item['url'] = base + f'item-{item["rank"]:02}.mp3'
    return {'version': prepared['version'], 'date': prepared['date'], 'source_hash': prepared['source_hash'],
            'speech_script_hash': prepared['speech_script_hash'], 'content_hash': fingerprint(prepared),
            'voice': 'kokoro-' + VOICE, 'language': 'en-US', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'speech_url': base + 'speech.txt', 'day': {'url': base + 'day.mp3', 'duration': round(duration(combined), 3)}, 'items': items}, folder



def publish(manifest, folder, tag):
    archive = build_playlist_archive(manifest, folder)
    manifest['playlist_url'] = f'https://github.com/{REPOSITORY}/releases/download/{tag}/{archive.name}'
    path = folder / 'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Existing partial releases are repaired; only these exact deterministic
    # asset names are touched. The manifest is uploaded last as the ready marker.
    view = subprocess.run(['gh', 'release', 'view', tag, '--repo', REPOSITORY, '--json', 'tagName'], capture_output=True, timeout=60)
    if view.returncode:
        notes = folder / 'release-notes.md'
        notes.write_text('Offline synthetic reading of ' + manifest['date'] + '.\n\n'
            'Voice: Kokoro af_heart, American English; free local CPU synthesis.\n'
            'Model and training-data credits: https://huggingface.co/hexgrad/Kokoro-82M\n'
            'Math: Codex-authored exact English substitutions; surrounding prose preserved.\n'
            'Sections have 1.5-second pauses; the full day contains only item recordings.\n'
            'Source digest: https://github.com/' + REPOSITORY + '/blob/main/incoming/' + manifest['date'] + '.md\n'
            'Generated without model API calls.\n', encoding='utf-8')
        command(['gh', 'release', 'create', tag, '--repo', REPOSITORY, '--target', os.environ.get('GITHUB_SHA', 'main'),
                 '--title', 'arXiv-' + manifest['date'] + ' audio', '--notes-file', str(notes), '--latest=false'])
    command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber', *[str(p) for p in sorted(folder.glob('*.mp3'))], str(folder / 'speech.txt')], timeout=600)
    command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber', str(archive)], timeout=300)
    command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber', str(path)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date')
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--reuse-only', action='store_true', help='Publish available recordings without starting speech synthesis')
    args = parser.parse_args()
    if args.local_only and args.reuse_only:
        parser.error('--local-only and --reuse-only cannot be combined')
    CACHE.mkdir(parents=True, exist_ok=True)
    all_days = load_archive(ROOT / 'content/digests', ROOT / 'incoming')
    days = all_days
    if args.date:
        days = [day for day in days if day['date'] == args.date]
        if not days:
            raise ValueError('Requested digest does not exist')
    scripts = {}
    for day in days:
        script_path = ROOT / 'audio/scripts' / (day['date'] + '.json')
        if script_path.exists():
            script = json.loads(script_path.read_text(encoding='utf-8'))
            if script != make_script(day, script.get('pronunciations', []), version=script.get('version'),
                                     phrase_groups=script.get('phrase_groups', [])):
                raise ValueError('Speech script is stale or does not match ' + day['date'])
            scripts[day['date']] = script
    source = CACHE / 'days.json'
    source.write_text(json.dumps(days, ensure_ascii=False), encoding='utf-8')
    text_folder = CACHE / 'text'
    command(['node', str(ROOT / 'tools/export_audio.mjs'), str(source), str(text_folder)], timeout=300)
    index_file = ROOT / 'audio/index.json'
    index_file.parent.mkdir(parents=True, exist_ok=True)
    seed = json.loads(index_file.read_text(encoding='utf-8')) if index_file.exists() else {'days': {}}
    if not seed.get('days'):
        try:
            with urllib.request.urlopen(WEBSITE + 'data/audio/index.json', timeout=20) as response:
                seed = json.load(response)
        except (OSError, ValueError):
            pass
    seed['days'] = {stamp: canonical_audio_manifest(manifest) for stamp, manifest in seed.get('days', {}).items()}
    # Preserve previously verified, still-current recordings if a new day's
    # synthesis or upload fails before this run can finish.
    index = {'version': 1, 'days': {day['date']: seed['days'][day['date']] for day in all_days
             if seed.get('days', {}).get(day['date'], {}).get('source_hash') == audio_source_hash(day)}}
    if not args.local_only:
        save_index(index_file, index)
    voice = None
    for day in days:
        if day['date'] not in scripts:
            if day['date'] in index['days']:
                manifest = index['days'][day['date']]
                tag = manifest['day']['url'].rsplit('/', 2)[-2]
                if not args.local_only:
                    index['days'][day['date']] = ensure_playlist(manifest, tag)
                    save_index(index_file, index)
                print('Kept existing recording for ' + day['date'] + ' (no new speech script)', flush=True)
            else:
                print('Audio needs an English math companion for ' + day['date'], flush=True)
            continue
        prepared = json.loads((text_folder / (day['date'] + '.json')).read_text(encoding='utf-8'))
        prepared['source_hash'] = audio_source_hash(day)
        prepared['speech_script_hash'] = audio_script_hash(scripts[day['date']])
        tag = 'audio-' + day['date'] + '-' + fingerprint(prepared)[:16]
        existing = None if args.local_only else seed.get('days', {}).get(day['date'])
        if existing and existing.get('content_hash') != fingerprint(prepared):
            existing = None
        if existing is None and not args.local_only:
            existing = cached_release(tag)
        if existing:
            if existing['content_hash'] != fingerprint(prepared) or existing['date'] != day['date']:
                raise ValueError('Audio release content mismatch')
            manifest = ensure_playlist(existing, tag)
            print('Reused audio for ' + day['date'], flush=True)
        else:
            if args.reuse_only:
                print('No completed recording for ' + day['date'] + '; synthesis was not requested.', flush=True)
                continue
            if voice is None:
                from kokoro_onnx import Kokoro
                import onnxruntime as runtime
                model, voices = download_voice()
                options = runtime.SessionOptions()
                options.intra_op_num_threads = min(4, os.cpu_count() or 2)
                options.inter_op_num_threads = 1
                session = runtime.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
                voice = Kokoro.from_session(session, str(voices))
            manifest, folder = render(prepared, tag, voice)
            if args.local_only:
                build_playlist_archive(manifest, folder)
            (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            if not args.local_only:
                publish(manifest, folder, tag)
                verified = cached_release(tag)
                if verified is None or verified['content_hash'] != manifest['content_hash']:
                    raise RuntimeError('Audio publication could not be verified')
            print('Rendered audio for ' + day['date'] + ': ' + str(round(manifest['day']['duration'] / 60, 1)) + ' minutes', flush=True)
        if not args.local_only:
            index['days'][day['date']] = manifest
            save_index(index_file, index)


if __name__ == '__main__':
    main()
