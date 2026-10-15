"""Capture dated, original announcements from arXiv's official Atom feeds."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

if __package__:
    from . import collect_arxiv as legacy
else:
    import collect_arxiv as legacy

ATOM = '{http://www.w3.org/2005/Atom}'
ARXIV = '{http://arxiv.org/schemas/atom}'
DC = '{http://purl.org/dc/elements/1.1/}'
BASE = 'https://rss.arxiv.org/atom/'
CACHE = legacy.ROOT / '.cache/arxiv-collector/feeds'


def canonical(categories):
    result = sorted({'math-ph' if c == 'math.MP' else c for c in categories})
    if not result or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9.-]*', c) for c in result):
        raise ValueError('Invalid feed categories')
    return result


def feed_url(categories):
    return BASE + '+'.join(canonical(categories))


def parse_feed(text, categories):
    root = ET.fromstring(text)
    if root.tag != ATOM + 'feed':
        raise ValueError('Not an Atom feed')
    identity = root.findtext(ATOM + 'id', '')
    if not identity.startswith(('https://rss.arxiv.org/atom/', 'http://rss.arxiv.org/atom/')) or canonical(identity.rsplit('/', 1)[-1].split('+')) != canonical(categories):
        raise ValueError('Feed category identity mismatch')
    entries = root.findall(ATOM + 'entry')
    if len(entries) >= 2000:
        raise OverflowError('Feed may be truncated at 2000 entries')
    if not entries:
        raise ValueError('An empty Atom feed cannot prove an announcement date')
    records, dates = [], set()
    for entry in entries:
        raw_id = entry.findtext(ATOM + 'id', '').removeprefix('oai:arXiv.org:')
        kind = entry.findtext(ARXIV + 'announce_type', '')
        if not re.fullmatch(legacy.ARXIV_ID.pattern, raw_id) or not re.search(r'v[1-9]\d*$', raw_id):
            raise ValueError('Invalid versioned feed paper ID')
        if kind not in ('new', 'cross', 'replace', 'replace-cross'):
            raise ValueError('Unrecognized announcement type')
        published = entry.findtext(ATOM + 'published', '')
        timestamp = datetime.fromisoformat(published)
        if timestamp.tzinfo is None:
            raise ValueError('Feed announcement timestamp lacks timezone')
        announced = timestamp.date().isoformat()
        dates.add(announced)
        title = legacy.clean(entry.findtext(ATOM + 'title', ''))
        summary = entry.findtext(ATOM + 'summary', '')
        # arXiv's feed prefixes the abstract with ID and announcement type.
        match = re.match(r'arXiv:' + re.escape(raw_id) + r'\s+Announce Type:\s*' + re.escape(kind) + r'\s+Abstract:\s*([\s\S]+)', summary)
        authors = legacy.clean(entry.findtext(DC + 'creator', ''))
        subjects = sorted({node.attrib['term'] for node in entry.findall(ATOM + 'category') if node.attrib.get('term')})
        if not title or not match or not authors or not subjects:
            raise ValueError('Incomplete feed metadata')
        paper_id = re.sub(r'v\d+$', '', raw_id)
        records.append({'id': paper_id, 'feed_id': raw_id, 'announcement_type': kind,
                        'feed_source': feed_url(categories),
                        'feed_published': published, 'announcement_date': announced,
                        'title': title, 'abstract': legacy.clean(match.group(1)),
                        # Preserve the complete author string, including names
                        # containing commas, instead of guessing its separators.
                        'authors': [authors], 'categories': subjects,
                        'url': 'https://arxiv.org/abs/' + paper_id,
                        'versioned_url': 'https://arxiv.org/abs/' + raw_id,
                        'metadata_origin': 'arxiv-atom'})
    if len(dates) != 1:
        raise ValueError('Feed mixes announcement dates; retry after update finishes')
    return records, dates.pop()


def save_feed(text, categories, cache=CACHE):
    records, announced = parse_feed(text, categories)
    url = feed_url(categories)
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    folder = Path(cache) / announced
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (key + '.xml')
    receipt = target.with_suffix('.json')
    if not receipt.exists():
        temporary = target.with_suffix('.tmp')
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(target)
        evidence = {'url': url, 'categories': canonical(categories), 'date': announced,
                    'captured_at': datetime.now(timezone.utc).isoformat(),
                    'sha256': hashlib.sha256(text.encode()).hexdigest()}
        receipt.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return records, announced


def cached_group(categories, day, cache=CACHE):
    key = hashlib.sha256(feed_url(categories).encode()).hexdigest()[:20]
    target = Path(cache) / day / (key + '.xml')
    if not target.with_suffix('.json').exists():
        if len(categories) > 1:
            middle = len(categories) // 2
            left = cached_group(categories[:middle], day, cache)
            right = cached_group(categories[middle:], day, cache)
            if left is not None and right is not None:
                return left + right
        return None
    evidence = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
    text = target.read_text(encoding='utf-8')
    if evidence['sha256'] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError('Cached feed checksum mismatch')
    records, announced = parse_feed(text, categories)
    if announced != day:
        raise ValueError('Cached feed date mismatch')
    return records


def fetch_group(categories, day=None, cache=CACHE):
    categories = canonical(categories)
    if day:
        saved = cached_group(categories, day, cache)
        if saved is not None:
            return saved, day
    text = legacy.fetch_text(feed_url(categories))
    try:
        records, announced = save_feed(text, categories, cache)
    except OverflowError:
        if len(categories) == 1:
            raise ValueError('Single-category feed reaches its completeness limit') from None
        middle = len(categories) // 2
        left, left_day = fetch_group(categories[:middle], day, cache)
        right, right_day = fetch_group(categories[middle:], day, cache)
        if left_day != right_day:
            raise ValueError('Split feeds are not the same dated batch')
        return left + right, left_day
    if day and announced != day:
        raise RuntimeError(f'Feed for {day} is not cached and the live feed is {announced}; historical recovery is required')
    return records, announced


def collect(categories, since, folder, through=None, cache=CACHE):
    categories = canonical(categories)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    through = through or datetime.now(timezone.utc).date().isoformat()
    # Capture today's feed immediately, then recover earlier successful inputs
    # from durable cache without revisiting the HTML website.
    _, latest = fetch_group(categories, cache=cache)
    days = sorted({latest} | {p.name for p in Path(cache).iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)})
    outputs = []
    for day in reversed(days):
        target = folder / (day + '.json')
        if not since <= day <= through or target.exists():
            continue
        base, _ = fetch_group(categories, day, cache)
        candidates = {}
        for entry in base:
            if entry['announcement_type'] not in ('new', 'cross'):
                continue
            previous = candidates.get(entry['id'])
            if previous is None or entry['announcement_type'] == 'new':
                candidates[entry['id']] = entry
        sources = {entry['feed_source'] for entry in base}
        proofs = {entry['id']: (entry, entry['feed_source']) for entry in base if entry['announcement_type'] == 'new'}
        # A cross-list can be old even when its unchanged version is v1. Verify
        # its original category through official feeds, never submission dates.
        unresolved = [entry for key, entry in candidates.items() if key not in proofs]
        subjects = {c for entry in unresolved for c in entry['categories']}
        related = sorted(set(canonical(subjects)) - set(categories)) if subjects else []
        for start in range(0, len(related), 5):
            group = related[start:start + 5]
            rows, _ = fetch_group(group, day, cache)
            sources.update(entry['feed_source'] for entry in rows)
            for entry in rows:
                if entry['id'] in candidates and entry['announcement_type'] == 'new':
                    proofs[entry['id']] = (entry, entry['feed_source'])
        papers, excluded = [], []
        for paper_id, listed in sorted(candidates.items()):
            if paper_id not in proofs:
                excluded.append({'id': paper_id, 'reason': 'No original new announcement in this dated feed batch'})
                continue
            original, url = proofs[paper_id]
            papers.append({**original, 'first_announcement_date': day,
                           'primary_listing_sources': [url],
                           'listed_categories': sorted(set(canonical(listed['categories'])) & set(categories))})
        snapshot = {'date': day, 'version': 3, 'metadata_version': 'feed',
                    'source_format': 'arxiv-atom', 'captured_at': datetime.now(timezone.utc).isoformat(),
                    'feed_counts': {kind: sum(entry['announcement_type'] == kind for entry in base)
                                    for kind in ('new', 'cross', 'replace', 'replace-cross')},
                    'listing_sources': sorted(sources), 'papers': papers, 'excluded_papers': excluded}
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
        print(f'Archived {day}: {len(papers)} new papers; excluded {len(excluded)} old cross-lists', flush=True)
        outputs.append({'date': day, 'papers': len(papers)})
    return outputs
