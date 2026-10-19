"""Lossless, bounded delivery of saved research evidence to the generator."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from tools import local_pipeline as pipeline


DAY = '2026-10-19'


def snapshot(count=20):
    return {'date': DAY, 'listing_sources': ['https://example.org/feed'], 'papers': [
        {'id': f'2610.{index:05d}', 'title': f'Exact title {index}: $N \\to \\infty$',
         'authors': ['A. Author', 'B. Author'],
         'abstract': ('A complete abstract with a qualification and $x^2$ math. ' * 30) + f'Final claim {index}.',
         'categories': ['quant-ph', 'math-ph'],
         'versioned_url': f'https://arxiv.org/abs/2610.{index:05d}v2',
         'feed_id': f'2610.{index:05d}v2', 'feed_source': 'https://example.org/feed',
         'announcement_date': DAY, 'primary_listing_sources': ['https://example.org/feed'],
         'metadata_origin': 'arxiv-atom'} for index in range(1, count + 1)]}


class MetadataLookupTests(unittest.TestCase):
    def assert_bounded(self, page):
        encoded = pipeline.lookup_json(page).encode('utf-8') + b'\n'
        self.assertLessEqual(len(encoded), pipeline.LOOKUP_PAGE_BYTES)
        self.assertEqual(json.loads(encoded), page)
        self.assertEqual(list(page)[-1], 'complete')

    def collect_pages(self, data, ids=None, details=False):
        start = offset = 0
        records = []
        fragments = []
        pages = []
        for _ in range(1000):
            page = (pipeline.catalog_page(data, DAY, start, offset) if ids is None else
                    pipeline.paper_page(data, DAY, ids, start, offset, details))
            self.assert_bounded(page)
            pages.append(page)
            records.extend(page['papers'])
            if 'fragment' in page:
                fragment = page['fragment']
                self.assertEqual(fragment['offset'], sum(len(part) for part in fragments))
                self.assertEqual(fragment['end'] - fragment['offset'], len(fragment['text']))
                fragments.append(fragment['text'])
                if fragment['record_complete']:
                    self.assertEqual(fragment['end'], fragment['total_characters'])
                    records.append(json.loads(''.join(fragments)))
                    fragments = []
            if page['complete']:
                self.assertIsNone(page['next_command'])
                self.assertFalse(fragments)
                return records, pages
            args = shlex.split(page['next_command'])
            self.assertEqual(args[:4], ['python', 'tools/local_pipeline.py', 'catalog' if ids is None else 'paper', DAY])
            if details:
                self.assertIn('--details', args)
            new_start = int(args[args.index('--start') + 1])
            new_offset = int(args[args.index('--offset') + 1]) if '--offset' in args else 0
            self.assertGreater((new_start, new_offset), (start, offset))
            start, offset = new_start, new_offset
        self.fail('Continuation did not finish')

    def test_compact_records_preserve_complete_scientific_evidence(self):
        data = snapshot(1)
        original = copy.deepcopy(data)
        paper = data['papers'][0]
        compact = pipeline.compact_paper(paper)
        self.assertEqual(set(compact), {'id', 'title', 'authors', 'abstract', 'categories', 'versioned_url'})
        for field in compact:
            self.assertEqual(compact[field], paper[field])
        self.assertEqual(data, original)
        paper['source_v1'] = paper.pop('versioned_url').replace('v2', 'v1')
        compact = pipeline.compact_paper(paper)
        self.assertEqual(compact['source_v1'], paper['source_v1'])
        self.assertNotIn('versioned_url', compact)
        del paper['source_v1']
        with self.assertRaisesRegex(ValueError, 'Missing recorded source version'):
            pipeline.compact_paper(paper)

    def test_twenty_requested_records_arrive_losslessly_across_pages(self):
        data = snapshot()
        ids = [paper['id'] for paper in data['papers']]
        records, pages = self.collect_pages(data, ids)
        self.assertGreater(len(pages), 1)
        self.assertEqual(records, [pipeline.compact_paper(paper) for paper in data['papers']])
        self.assertTrue(all(not page['complete'] for page in pages[:-1]))

    def test_full_audit_evidence_is_separately_available_and_bounded(self):
        data = snapshot(6)
        ids = [paper['id'] for paper in data['papers']]
        records, _ = self.collect_pages(data, ids, details=True)
        self.assertEqual(records, data['papers'])

    def test_oversized_unicode_record_is_fragmented_without_losing_any_text(self):
        data = snapshot(2)
        # Includes multibyte text, escaped quotes, literal backslashes, and newlines.
        data['papers'][0]['abstract'] = ('临界点 α → β "quoted" \\frac{a}{b}\n' * 1500) + 'FINAL QUALIFICATION.'
        data['papers'][0]['authors'] = ['An author with a very long name'] * 500
        ids = [paper['id'] for paper in data['papers']]
        records, pages = self.collect_pages(data, ids)
        self.assertEqual(records, [pipeline.compact_paper(paper) for paper in data['papers']])
        self.assertIn('fragment', pages[0])
        self.assertFalse(pages[0]['fragment']['record_complete'])
        self.assertFalse(pages[0]['complete'])

    def test_whole_catalog_remains_available_without_keyword_filtering(self):
        data = snapshot(150)
        records, pages = self.collect_pages(data)
        self.assertGreater(len(pages), 1)
        self.assertEqual(records, [{key: paper[key] for key in ('id', 'title', 'categories')}
                                   for paper in data['papers']])
        self.assertEqual(len(records), 150)

    def test_duplicate_requested_ids_do_not_duplicate_records(self):
        data = snapshot(2)
        ids = [data['papers'][1]['id'], data['papers'][0]['id'], data['papers'][1]['id']]
        records, _ = self.collect_pages(data, ids)
        self.assertEqual([record['id'] for record in records], ids[:2])

    def test_bad_ids_dates_and_continuations_fail_before_partial_delivery(self):
        data = snapshot(2)
        ids = [paper['id'] for paper in data['papers']]
        for kwargs in [{'ids': []}, {'ids': ids + ['2610.99999']}, {'ids': ids * 11},
                       {'ids': ids, 'start': -1}, {'ids': ids, 'start': 2},
                       {'ids': ids, 'offset': -1}, {'ids': ids, 'offset': 1000000}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                pipeline.paper_page(data, DAY, **kwargs)
        with self.assertRaisesRegex(ValueError, 'Snapshot date mismatch'):
            pipeline.catalog_page(data, '2026-10-16')
        empty, _ = self.collect_pages(snapshot(0))
        self.assertEqual(empty, [])

    def test_cli_continuation_commands_are_executable_and_return_bounded_json(self):
        data = snapshot(8)
        with tempfile.TemporaryDirectory() as directory, patch.object(pipeline, 'RUNTIME', Path(directory)):
            inputs = Path(directory) / 'inputs'
            inputs.mkdir()
            (inputs / f'{DAY}.json').write_text(json.dumps(data), encoding='utf-8')
            command = ['tools/local_pipeline.py', 'paper', DAY] + [paper['id'] for paper in data['papers']]
            seen = []
            for _ in range(20):
                stream = io.StringIO()
                with patch('sys.argv', command), redirect_stdout(stream):
                    pipeline.main()
                page = json.loads(stream.getvalue())
                self.assert_bounded(page)
                seen.extend(page['papers'])
                if page['complete']:
                    break
                command = shlex.split(page['next_command'])[1:]
            else:
                self.fail('CLI continuation did not finish')
            self.assertEqual(seen, [pipeline.compact_paper(paper) for paper in data['papers']])
            with patch('sys.argv', ['tools/local_pipeline.py', 'paper', DAY, '2610.99999']), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                pipeline.main()
            self.assertEqual(output.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
