import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

from tools import collect_feeds as feeds
from tools import local_pipeline as pipeline

DAY = '2026-10-14'


def entry(paper_id='2610.00001', kind='new', subjects=('quant-ph',), day=DAY, version=1):
    raw_id = paper_id + 'v' + str(version)
    categories = ''.join('<category term="' + c + '"/>' for c in subjects)
    return f'''<entry><id>oai:arXiv.org:{raw_id}</id><title>Paper $x^2$</title>
      <summary>{escape(f'arXiv:{raw_id} Announce Type: {kind} Abstract: An exact $x^2$ result.')}</summary>
      <published>{day}T00:00:00-04:00</published><arxiv:announce_type>{kind}</arxiv:announce_type>
      <dc:creator>Doe, Alice, Bob Smith</dc:creator>{categories}</entry>'''


def feed(entries, categories=('quant-ph',)):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:dc="http://purl.org/dc/elements/1.1/"><id>{feeds.feed_url(categories)}</id>{''.join(entries)}</feed>'''


class FeedCollectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / 'cache/feeds'
        self.output = self.root / 'sources'

    def test_correct_date_math_and_full_authors_are_preserved(self):
        rows, day = feeds.parse_feed(feed([entry()]), ['quant-ph'])
        self.assertEqual(day, DAY)
        self.assertEqual(rows[0]['title'], 'Paper $x^2$')
        self.assertEqual(rows[0]['abstract'], 'An exact $x^2$ result.')
        self.assertEqual(rows[0]['authors'], ['Doe, Alice, Bob Smith'])

    def test_replacements_and_old_cross_lists_are_excluded_with_dated_primary_proof(self):
        base = feed([entry(), entry('2610.00002', 'cross', ('math.QA', 'quant-ph')),
                     entry('2504.04899', 'cross', ('math.QA', 'quant-ph')),
                     entry('2610.00004', 'replace', version=2)])
        primary = feed([entry('2610.00002', subjects=('math.QA',)), entry('2610.00005', subjects=('math.QA',))], ['math.QA'])
        with patch.object(feeds.legacy, 'fetch_text', side_effect=lambda url: {feeds.feed_url(['quant-ph']): base, feeds.feed_url(['math.QA']): primary}[url]), patch.object(feeds.legacy, 'fetch_metadata') as api:
            feeds.collect(['quant-ph'], DAY, self.output, through=DAY, cache=self.cache)
        snapshot = json.loads((self.output / (DAY + '.json')).read_text(encoding='utf-8'))
        self.assertEqual([p['id'] for p in snapshot['papers']], ['2610.00001', '2610.00002'])
        self.assertEqual([p['id'] for p in snapshot['excluded_papers']], ['2504.04899'])
        pipeline.validate_snapshot(snapshot, DAY)
        api.assert_not_called()

    def test_updated_new_announcement_keeps_its_declared_version_without_api_calls(self):
        raw = feed([entry(version=2)])
        with patch.object(feeds.legacy, 'fetch_text', return_value=raw), patch.object(feeds.legacy, 'fetch_metadata') as api:
            feeds.collect(['quant-ph'], DAY, self.output, through=DAY, cache=self.cache)
        snapshot = json.loads((self.output / (DAY + '.json')).read_text(encoding='utf-8'))
        self.assertEqual(snapshot['papers'][0]['versioned_url'], 'https://arxiv.org/abs/2610.00001v2')
        self.assertEqual(snapshot['papers'][0]['metadata_origin'], 'arxiv-atom')
        pipeline.validate_snapshot(snapshot, DAY)
        api.assert_not_called()

    def test_failed_related_feed_keeps_checkpoint_without_publishing_partial_batch(self):
        base = feed([entry(), entry('2610.00002', 'cross', ('math.QA', 'quant-ph'))])
        with patch.object(feeds.legacy, 'fetch_text', side_effect=[base, RuntimeError('429')]):
            with self.assertRaises(RuntimeError):
                feeds.collect(['quant-ph'], DAY, self.output, through=DAY, cache=self.cache)
        self.assertIsNotNone(feeds.cached_group(['quant-ph'], DAY, self.cache))
        self.assertFalse((self.output / (DAY + '.json')).exists())

    def test_existing_snapshots_are_immutable(self):
        self.output.mkdir()
        target = self.output / (DAY + '.json')
        target.write_text('original', encoding='utf-8')
        with patch.object(feeds.legacy, 'fetch_text', return_value=feed([entry()])):
            self.assertEqual(feeds.collect(['quant-ph'], DAY, self.output, through=DAY, cache=self.cache), [])
        self.assertEqual(target.read_text(encoding='utf-8'), 'original')

    def test_truncated_combined_feed_is_split_and_cached_for_recovery(self):
        categories = ['hep-th', 'quant-ph']
        full = feed(['<entry/>' for _ in range(2000)], categories)
        data = {feeds.feed_url(categories): full,
                feeds.feed_url(['hep-th']): feed([entry(subjects=('hep-th',))], ['hep-th']),
                feeds.feed_url(['quant-ph']): feed([entry('2610.00002')])}
        with patch.object(feeds.legacy, 'fetch_text', side_effect=lambda url: data[url]):
            rows, day = feeds.fetch_group(categories, cache=self.cache)
        self.assertEqual((len(rows), day), (2, DAY))
        self.assertEqual(len(feeds.cached_group(categories, DAY, self.cache)), 2)

    def test_stale_feed_and_corrupted_cache_are_rejected(self):
        with patch.object(feeds.legacy, 'fetch_text', return_value=feed([entry(day='2026-10-15')])):
            with self.assertRaises(RuntimeError):
                feeds.fetch_group(['quant-ph'], DAY, self.cache)
        feeds.save_feed(feed([entry()]), ['quant-ph'], self.cache)
        next((self.cache / DAY).glob('*.xml')).write_text('corrupt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            feeds.cached_group(['quant-ph'], DAY, self.cache)

    def test_unknown_types_and_undated_feeds_are_not_empty_batches(self):
        for data in [feed([]), feed([entry(kind='unknown')]), feed([entry()]).replace('<published>', '<missing>').replace('</published>', '</missing>')]:
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                feeds.parse_feed(data, ['quant-ph'])

    def test_large_snapshot_is_read_directly_without_contents_api_size_limit(self):
        data = {'date': DAY, 'papers': [], 'padding': 'x' * 1100000}
        with patch.object(pipeline.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as request:
            self.assertEqual(pipeline.read_remote_snapshot(DAY, 'test-token'), data)
        self.assertEqual(request.call_args.args[0].get_header('Accept'), 'application/vnd.github.raw+json')


if __name__ == '__main__':
    unittest.main()
