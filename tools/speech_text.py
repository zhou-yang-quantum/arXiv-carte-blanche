"""Validate math readings and source-exact phrase groups without rewriting prose."""
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


def validate_phrase_groups(day, phrase_groups):
    if not isinstance(phrase_groups, list):
        raise ValueError('Audio phrase groups must be a list')
    found = {}
    for parts in phrase_groups:
        if (not isinstance(parts, list) or not 1 <= len(parts) <= 8
                or any(not isinstance(part, str) or not part.strip() or part != part.strip()
                       or '\n' in part or '\r' in part for part in parts)):
            raise ValueError('Each phrase group needs nonempty exact source parts')
        phrase = ' '.join(parts)
        if len(phrase) > 400 or not any(character.isalnum() for character in phrase) or phrase in found:
            raise ValueError('Invalid, excessive, or duplicate audio phrase group')
        found[phrase] = parts
    matched = set()
    for paper in day['papers']:
        for field in ('title', 'summary', 'background', 'why'):
            source = paper[field]
            math = [(match.start(), match.end()) for match in MATH.finditer(source)]
            spans = []
            for phrase, parts in found.items():
                offset = 0
                while (start := source.find(phrase, offset)) != -1:
                    end = start + len(phrase)
                    boundaries = [start, end]
                    position = start
                    for part in parts[:-1]:
                        position += len(part)
                        boundaries.extend((position, position + 1))
                        position += 1
                    if any(left < boundary < right for left, right in math for boundary in boundaries):
                        raise ValueError('Audio phrase groups cannot split math expressions')
                    spans.append((start, end))
                    matched.add(phrase)
                    offset = end
            spans.sort()
            if any(right[0] < left[1] for left, right in zip(spans, spans[1:])):
                raise ValueError('Audio phrase groups cannot overlap')
    if matched != set(found):
        raise ValueError('Audio phrase groups must copy phrases from the digest exactly')
    return [found[phrase] for phrase in sorted(found)]


def make_script(day, pronunciations, version=6, phrase_groups=None):
    if version not in (2, 3, 4, 5, 6):
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
        plain = spoken
        if version >= 5:
            # Rhythm controls belong only to math readings, never digest prose.
            if re.search(r'\([^()]*\[p\][^()]*\)', plain):
                raise ValueError('Math rhythm groups cannot contain pauses')
            plain = plain.replace('[p]', ' ')
            groups = re.findall(r'\(([^()]*)\)', plain)
            plain = re.sub(r'\(([^()]*)\)', r'\1', plain)
            if any(not group.strip() for group in groups) or any(character in plain for character in '()'):
                raise ValueError('Math rhythm groups must be nonempty and cannot nest')
        if len(spoken) > 2000 or not plain.strip() or any(character in plain for character in '$\\<>_=+*/^{}[]|~') or re.search(r'[\u0370-\u03ff]', plain):
            raise ValueError('Equation pronunciations must be plain English, not TeX or markup')
        found[latex] = spoken.strip()
    expected = set(expressions(day))
    if set(found) != expected:
        raise ValueError('Equation pronunciations must cover every distinct item equation exactly once')
    script = {'version': version, 'date': day['date'], 'source_hash': audio_source_hash(day),
              'pronunciations': [{'latex': expression, 'spoken': found[expression]} for expression in sorted(found)]}
    if version >= 6:
        script['phrase_groups'] = validate_phrase_groups(day, [] if phrase_groups is None else phrase_groups)
    elif phrase_groups:
        raise ValueError('Audio phrase grouping requires narration version 6')
    return script
