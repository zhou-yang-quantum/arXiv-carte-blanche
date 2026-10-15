import json
import tempfile
import unittest
from pathlib import Path
from tools.import_digest import parse_digest
from tools.build import load_archive, ROOT


def example_digest(count=10, include_priority=True):
    priority = '\n**Priority: high**' if include_priority else ''
    return '# arXiv-2026-10-06\n\nOverview\n\n' + '\n\n'.join(
        f'## arXiv-2026-10-06 — Item {n}\n\n### Paper {n}\n**Author — arXiv:2610.{n:05d}**{priority}\n\nSummary of paper {n}.\n\n**Background.** A useful concept.\n\n**Why it matters for you:** A useful connection.\n'
        for n in range(1, count + 1)
    )


class DigestTests(unittest.TestCase):
    def test_import_preserves_sections_and_date(self):
        day = parse_digest(example_digest())
        self.assertEqual(day['date'], '2026-10-06')
        self.assertEqual(len(day['papers']), 10)
        self.assertEqual(day['papers'][0]['authors'], 'Author')
        self.assertEqual(day['papers'][0]['summary'], 'Summary of paper 1.')
        self.assertEqual(day['papers'][0]['background'], 'A useful concept.')
        self.assertEqual(day['papers'][0]['why'], 'A useful connection.')

    def test_new_format_accepts_variable_counts_without_verdicts(self):
        for count in (10, 11, 20):
            with self.subTest(count=count):
                day = parse_digest(example_digest(count, include_priority=False))
                self.assertEqual(len(day['papers']), count)
                self.assertEqual(day['overview'], 'Overview')
                self.assertEqual(day['reading_order'], list(range(1, count + 1)))
                for paper in day['papers']:
                    self.assertNotIn('priority', paper)
                    self.assertEqual(paper['authors'], 'Author')
                    self.assertEqual(paper['summary'], f"Summary of paper {paper['rank']}.")
                    self.assertEqual(paper['background'], 'A useful concept.')
                    self.assertEqual(paper['why'], 'A useful connection.')

    def test_rejects_counts_outside_limits(self):
        for count in (9, 21):
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse_digest(example_digest(count, include_priority=False))

    def test_why_heading_preserves_sections_for_new_and_legacy_digests(self):
        for heading in ('**Why it matters?**', '**Why it matters:**',
                        '**Why it matters for you:**'):
            with self.subTest(heading=heading):
                text = example_digest(include_priority=False).replace(
                    '**Why it matters for you:**', heading)
                day = parse_digest(text)
                for paper in day['papers']:
                    self.assertEqual(paper['background'], 'A useful concept.')
                    self.assertEqual(paper['why'], 'A useful connection.')

    def test_twenty_paper_reading_order_and_notes(self):
        order = list(range(20, 0, -1))
        advice = 'My reading order would be **' + ' → '.join(map(str, order)) + '**.\n\nDaily synthesis.'
        day = parse_digest(example_digest(20, include_priority=False) + '\n' + advice)
        self.assertEqual(day['reading_order'], order)
        self.assertIn('Daily synthesis.', day['notes'])
        self.assertEqual(day['papers'][-1]['why'], 'A useful connection.')

    def test_new_format_rejects_empty_sections(self):
        for section in ('Summary of paper 1.', 'A useful concept.', 'A useful connection.'):
            with self.subTest(section=section), self.assertRaises(ValueError):
                parse_digest(example_digest(include_priority=False).replace(section, '', 1))

    def test_json_archive_enforces_count_ranks_and_reading_order(self):
        day = parse_digest(example_digest(20, include_priority=False))
        invalid_count = {**day, 'papers': day['papers'][:9], 'reading_order': list(range(1, 10))}
        invalid_order = {**day, 'reading_order': list(range(1, 20))}
        invalid_rank = json.loads(json.dumps(day))
        invalid_rank['papers'][-1]['rank'] = 21
        too_many = json.loads(json.dumps(day))
        too_many['papers'].append({**day['papers'][-1], 'rank': 21, 'id': '2610.00021', 'url': 'https://arxiv.org/abs/2610.00021'})
        too_many['reading_order'].append(21)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, '2026-10-06.json')
            target.write_text(json.dumps(day), encoding='utf-8')
            self.assertEqual(len(load_archive(Path(folder))[0]['papers']), 20)
            for invalid in (invalid_count, invalid_order, invalid_rank, too_many):
                target.write_text(json.dumps(invalid), encoding='utf-8')
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    load_archive(Path(folder))

    def test_rejects_wrong_date_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            parse_digest(example_digest().replace('2026-10-06 — Item 2', '2026-10-05 — Item 2'))
        with self.assertRaises(ValueError):
            parse_digest(example_digest().replace('2610.00002', '2610.00001'))

    def test_rejects_missing_background_and_missing_rank(self):
        with self.assertRaises(ValueError):
            parse_digest(example_digest().replace('**Background.**', '**Details.**', 1))
        with self.assertRaises(ValueError):
            parse_digest(example_digest().replace('— Item 10', '— Item 11'))

    def test_build_rejects_unsafe_paper_link(self):
        day = parse_digest(example_digest())
        day['papers'][0]['url'] = 'javascript:alert(1)'
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, '2026-10-06.json').write_text(json.dumps(day), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_archive(Path(folder))

    def test_real_archive_has_complete_sections(self):
        days = load_archive(ROOT / 'content/digests', ROOT / 'incoming')
        for day in days:
            self.assertGreaterEqual(len(day['papers']), 10)
            self.assertLessEqual(len(day['papers']), 20)
            self.assertEqual(sorted(day['reading_order']), list(range(1, len(day['papers']) + 1)))
            for paper in day['papers']:
                for key in ('summary', 'background', 'why'):
                    self.assertNotIn('\ue200', paper[key])

    def test_incoming_markdown_is_published_without_json_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp, 'digests')
            incoming = Path(temp, 'incoming')
            folder.mkdir()
            incoming.mkdir()
            Path(incoming, 'README.md').write_text('Delivery instructions', encoding='utf-8')
            Path(incoming, '2026-10-06.md').write_text(example_digest(20, include_priority=False), encoding='utf-8')
            days = load_archive(folder, incoming)
            self.assertEqual(days[0]['date'], '2026-10-06')
            self.assertEqual(len(days[0]['papers']), 20)
            self.assertEqual(list(folder.iterdir()), [])

    def test_incoming_filename_must_match_digest_date(self):
        with tempfile.TemporaryDirectory() as temp:
            incoming = Path(temp, 'incoming')
            incoming.mkdir()
            Path(incoming, '2026-10-05.md').write_text(example_digest(), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_archive(Path(temp, 'empty'), incoming)

    def test_identical_redelivery_keeps_reviewed_tags(self):
        day = parse_digest(example_digest())
        day['papers'][0]['topics'] = ['Quantum field theory']
        with tempfile.TemporaryDirectory() as temp:
            folder, incoming = Path(temp, 'digests'), Path(temp, 'incoming')
            folder.mkdir()
            incoming.mkdir()
            Path(folder, '2026-10-06.json').write_text(json.dumps(day), encoding='utf-8')
            Path(incoming, '2026-10-06.md').write_text(example_digest(), encoding='utf-8')
            days = load_archive(folder, incoming)
            self.assertEqual(len(days), 1)
            self.assertEqual(days[0]['papers'][0]['topics'], ['Quantum field theory'])

    def test_conflicting_redelivery_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, incoming = Path(temp, 'digests'), Path(temp, 'incoming')
            folder.mkdir()
            incoming.mkdir()
            Path(folder, '2026-10-06.json').write_text(json.dumps(parse_digest(example_digest())), encoding='utf-8')
            Path(incoming, '2026-10-06.md').write_text(example_digest().replace('Summary of paper 1.', 'A changed claim.'), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_archive(folder, incoming)


if __name__ == '__main__':
    unittest.main()
