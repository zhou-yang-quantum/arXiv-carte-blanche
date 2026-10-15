"""Validate exact equation-to-English substitutions without rewriting digest prose."""
import re

if __package__:
    from .build import audio_source_hash
else:
    from build import audio_source_hash

MATH = re.compile(r'\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\$)(?:\\.|[^$\n])+?\$')


def expressions(day):
    return sorted({match.group() for paper in day['papers']
                   for field in ('title', 'summary', 'background', 'why')
                   for match in MATH.finditer(paper[field])})


def make_script(day, pronunciations, version=4):
    if version not in (2, 3, 4):
        raise ValueError('Unsupported narration version')
    if not isinstance(pronunciations, list):
        raise ValueError('Audio needs an equation pronunciation list')
    found = {}
    for entry in pronunciations:
        if not isinstance(entry, dict) or set(entry) != {'latex', 'spoken'}:
            raise ValueError('Each equation needs exactly latex and spoken fields')
        latex, spoken = entry['latex'], entry['spoken']
        if not isinstance(latex, str) or not isinstance(spoken, str) or not spoken.strip():
            raise ValueError('Empty or invalid equation pronunciation')
        if latex in found:
            raise ValueError('Duplicate equation pronunciation')
        if len(spoken) > 2000 or any(character in spoken for character in '$\\<>_=+*/^{}[]|~') or re.search(r'[\u0370-\u03ff]', spoken):
            raise ValueError('Equation pronunciations must be plain English, not TeX or markup')
        found[latex] = spoken.strip()
    expected = set(expressions(day))
    if set(found) != expected:
        raise ValueError('Equation pronunciations must cover every distinct item equation exactly once')
    return {'version': version, 'date': day['date'], 'source_hash': audio_source_hash(day),
            'pronunciations': [{'latex': expression, 'spoken': found[expression]} for expression in sorted(found)]}
