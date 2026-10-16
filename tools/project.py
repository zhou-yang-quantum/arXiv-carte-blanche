"""Canonical project locations, including compatibility with pre-rename audio."""
from copy import deepcopy

REPOSITORY = 'zhou-yang-quantum/arXiv-carte-blanche'
LEGACY_REPOSITORY = 'zhou-yang-quantum/daily-arXiv'
WEBSITE = 'https://zhou-yang-quantum.github.io/arXiv-carte-blanche/'
AUDIO_BASE = f'https://github.com/{REPOSITORY}/releases/download/'
LEGACY_AUDIO_BASE = f'https://github.com/{LEGACY_REPOSITORY}/releases/download/'


def canonical_audio_url(url):
    if isinstance(url, str) and url.startswith(LEGACY_AUDIO_BASE + 'audio-'):
        return AUDIO_BASE + url[len(LEGACY_AUDIO_BASE):]
    return url


def canonical_audio_manifest(manifest):
    """Migrate links without editing release identities, narration, or the input."""
    result = deepcopy(manifest)
    for track in [result.get('day', {}), *result.get('items', [])]:
        if 'url' in track:
            track['url'] = canonical_audio_url(track['url'])
    for field in ('speech_url', 'playlist_url'):
        if field in result:
            result[field] = canonical_audio_url(result[field])
    return result
