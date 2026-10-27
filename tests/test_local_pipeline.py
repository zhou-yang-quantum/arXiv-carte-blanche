import json
import io
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import collect_arxiv as collector
from tools import local_pipeline as pipeline
from test_archive import example_digest


def snapshot(count=10, day='2026-10-07'):
    return {'date': day, 'metadata_version': 'v1', 'listing_sources': ['https://arxiv.org/list/quant-ph/pastweek?show=2000'],
            'papers': [{'id': f'2610.{n:05d}', 'title': f'Paper {n}', 'abstract': f'Abstract {n}',
                        'authors': ['Author'], 'categories': ['quant-ph'], 'announcement_date': day}
                       for n in range(1, count + 1)]}


class CollectorTests(unittest.TestCase):
    def test_dates_metadata_math_and_replacements(self):
        listing = '''<div>Total of 2 entries</div><dl>
        <h3>Wed, 7 Oct 2026 (showing 1 of 1 entries)</h3>
        <dt><a href="/abs/2610.00001" title="Abstract">arXiv:2610.00001</a></dt>
        <dd><div class="list-title mathjax"><span>Title:</span> A $Q$ &amp; theory</div>
        <div class="list-authors"><a>A. Author</a>, <a>B. Author</a></div></dd>
        <h3>Tue, 6 Oct 2026 (showing 1 of 1 entries)</h3>
        <dt><a href="/abs/2610.00002" title="Abstract">arXiv:2610.00002</a></dt>
        <dd><div class="list-title">Title: Earlier paper</div></dd>
        <h3>Replacements</h3><dt><a href="/abs/2610.00003v2" title="Abstract">replacement</a></dt>
        </dl>'''
        papers, dates, total = collector.parse_listing(listing)
        self.assertEqual(total, 2)
        self.assertEqual(dates, {'2026-10-07', '2026-10-06'})
        self.assertEqual([paper['date'] for paper in papers], ['2026-10-07', '2026-10-06'])
        self.assertEqual(papers[0]['title'], 'A $Q$ & theory')
        self.assertEqual(papers[0]['authors'], 'A. Author, B. Author')

    def test_refuses_undated_monthly_list(self):
        with self.assertRaises(ValueError):
            collector.parse_listing('Total of 1 entries<dt><a href="/abs/2610.00001" title="Abstract">x</a></dt>')

    def test_empty_category_is_valid(self):
        self.assertEqual(collector.parse_listing('Total of 0 entries'), ([], set(), 0))

    def test_atom_v1_metadata_and_error_entries(self):
        atom = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>
        <id>http://arxiv.org/abs/2610.00001v1</id><title>A paper</title>
        <summary>First version abstract.</summary><published>2026-10-01T12:00:00Z</published>
        <author><name>A. Author</name></author><category term="quant-ph"/>
        <arxiv:primary_category term="quant-ph"/>
        </entry></feed>'''
        paper = collector.parse_atom(atom)['2610.00001']
        self.assertEqual(paper['source_v1'], 'https://arxiv.org/abs/2610.00001v1')
        self.assertEqual(paper['authors'], ['A. Author'])
        self.assertEqual(paper['primary_category'], 'quant-ph')
        with self.assertRaises(ValueError):
            collector.parse_atom(atom.replace('http://arxiv.org/abs/2610.00001v1', 'http://arxiv.org/api/errors#incorrect_id_format'))
        with self.assertRaises(ValueError):
            collector.parse_atom(atom.replace('2610.00001v1', '2610.00001v2'))

    def test_cross_list_marker_and_old_cross_list_exclusion(self):
        listing = '''Total of 1 entries<h3>Thu, 8 Oct 2026</h3>
        <dt><a href="/abs/2504.04899" title="Abstract">arXiv:2504.04899</a> (cross-list from physics.optics)</dt>'''
        self.assertTrue(collector.parse_listing(listing)[0][0]['is_cross_list'])
        metadata = {'2610.00001': {'primary_category': 'quant-ph'},
                    '2610.00002': {'primary_category': 'hep-th'},
                    '2504.04899': {'primary_category': 'physics.optics'}}
        listings = {'quant-ph': ([{'id': '2610.00001', 'date': '2026-10-08', 'is_cross_list': False},
                                  {'id': '2504.04899', 'date': '2026-10-08', 'is_cross_list': True}], set(), {'quant-ph-list'})}
        def additional(category):
            return ([{'id': '2610.00002', 'date': '2026-10-08', 'is_cross_list': False}] if category == 'hep-th' else [], set(), {category + '-list'})
        with patch.object(collector, 'fetch_listing', side_effect=additional), patch.object(collector.time, 'sleep'):
            first = collector.first_announcements(metadata, listings)
        self.assertEqual(first['2610.00001']['date'], '2026-10-08')
        self.assertEqual(first['2610.00002']['date'], '2026-10-08')
        self.assertNotIn('2504.04899', first)

    def test_verified_snapshot_rejects_wrong_first_announcement(self):
        current = snapshot()
        current['version'] = 2
        for paper in current['papers']:
            paper['first_announcement_date'] = current['date']
            paper['primary_listing_sources'] = ['quant-ph-list']
        pipeline.validate_snapshot(current, current['date'])
        current['papers'][0]['first_announcement_date'] = '2026-10-06'
        with self.assertRaises(ValueError):
            pipeline.validate_snapshot(current, current['date'])


class QueueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root_patch = patch.object(pipeline, 'ROOT', Path(temporary.name))
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.config = {'start_date': '2026-10-07', 'timezone': 'America/Chicago', 'hour': 10, 'minute': 0,
                       'model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'retry_minutes': 60,
                       'generation_timeout_minutes': 45, 'categories': ['quant-ph']}

    def test_before_ten_only_older_dates_and_weekends(self):
        morning = datetime(2026, 10, 8, 14, 59, tzinfo=timezone.utc)
        self.assertEqual(pipeline.expected_dates(self.config, morning), ['2026-10-07'])
        self.assertEqual(pipeline.expected_dates(self.config, datetime(2026, 10, 8, 15, tzinfo=timezone.utc)), ['2026-10-07', '2026-10-08'])
        dates = pipeline.expected_dates(self.config, datetime(2026, 10, 12, 16, tzinfo=timezone.utc))
        self.assertEqual(dates, ['2026-10-07', '2026-10-08', '2026-10-09', '2026-10-12'])

    def test_timezone_follows_daylight_saving(self):
        config = {**self.config, 'start_date': '2026-11-02'}
        self.assertEqual(pipeline.expected_dates(config, datetime(2026, 11, 2, 15, 59, tzinfo=timezone.utc)), [])
        self.assertEqual(pipeline.expected_dates(config, datetime(2026, 11, 2, 16, tzinfo=timezone.utc)), ['2026-11-02'])

    def test_missing_gap_not_just_latest_date(self):
        now = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)
        state = {'days': {'2026-10-08': {'status': 'published'}}}
        self.assertEqual(pipeline.plan(self.config, state, now)['due'], ['2026-10-07', '2026-10-09'])

    def test_retry_and_review_are_not_false_completions(self):
        now = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)
        state = {'days': {'2026-10-07': {'status': 'retry', 'retry_at': '2026-10-09T19:00:00+00:00'},
                          '2026-10-08': {'status': 'needs-review'}}}
        result = pipeline.plan(self.config, state, now)
        self.assertEqual(result['due'], ['2026-10-09'])
        self.assertEqual(result['waiting'], ['2026-10-07'])
        self.assertEqual(result['needs_review'], ['2026-10-08'])

    def test_quota_or_network_cooldown_applies_to_entire_queue(self):
        now = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)
        state = {'days': {}, 'pause_until': '2026-10-09T19:00:00+00:00'}
        result = pipeline.plan(self.config, state, now)
        self.assertEqual(result['due'], [])
        self.assertEqual(result['waiting'], ['2026-10-07', '2026-10-08', '2026-10-09'])
        self.assertEqual(len(pipeline.plan(self.config, state, datetime(2026, 10, 9, 19, tzinfo=timezone.utc))['due']), 3)

    def test_local_settings_are_independent_of_retired_app_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / 'config.json'
            config_path.write_text(json.dumps({**self.config, 'enabled': True, 'require_chatgpt_login': True, 'allow_paid_api': False}), encoding='utf-8')
            (root / 'runtime.json').write_text(json.dumps({'automation_id': 'fixture'}), encoding='utf-8')
            task_folder = root / 'automations/fixture'
            task_folder.mkdir(parents=True)
            (task_folder / 'automation.toml').write_text('status = "PAUSED"\nmodel = "gpt-6-sol"\nreasoning_effort = "medium"\n', encoding='utf-8')
            with patch.object(pipeline, 'RUNTIME', root), patch.object(pipeline, 'CONFIG', config_path), patch.dict(os.environ, {'CODEX_HOME': str(root)}):
                loaded = pipeline.load_config()
            self.assertEqual((loaded['model'], loaded['reasoning_effort']), ('gpt-6.1-sol', 'high'))
            self.assertTrue(loaded['enabled'])

    def test_pause_and_resume_preserve_local_generation_settings(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'CONFIG', Path(folder) / 'config.json'):
            original = {**self.config, 'enabled': True}
            pipeline.CONFIG.write_text(json.dumps(original), encoding='utf-8')
            self.assertFalse(pipeline.set_enabled(False)['enabled'])
            self.assertEqual(json.loads(pipeline.CONFIG.read_text()), {**original, 'enabled': False})
            self.assertTrue(pipeline.set_enabled(True)['enabled'])
            self.assertEqual(json.loads(pipeline.CONFIG.read_text()), original)

    def test_kernel_lock_prevents_duplicate_workers_and_releases(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)):
            with pipeline.pipeline_lock() as first:
                self.assertTrue(first)
                with pipeline.pipeline_lock() as second:
                    self.assertFalse(second)
            with pipeline.pipeline_lock() as third:
                self.assertTrue(third)

    def test_model_and_effort_override_current_chat_and_strip_keys(self):
        command = pipeline.generation_command('codex', self.config, Path('result.json'), Path('schema.json'))
        self.assertIn('gpt-6.1-sol', command)
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertIn('forced_login_method="chatgpt"', command)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret', 'ARXIV_GITHUB_TOKEN': 'secret', 'GH_TOKEN': 'secret'}):
            environment = pipeline.child_environment()
            self.assertNotIn('OPENAI_API_KEY', environment)
            self.assertNotIn('ARXIV_GITHUB_TOKEN', environment)
            self.assertNotIn('GH_TOKEN', environment)
            self.assertEqual(environment['PYTHONUTF8'], '1')

    def test_automatic_worker_honors_local_pause(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'load_config', return_value={**self.config, 'enabled': False}), \
             patch.object(pipeline, 'github_token') as credential:
            self.assertEqual(pipeline.run_pipeline(automatic=True)['status'], 'paused')
            credential.assert_not_called()

    def test_repeated_idle_checks_never_reach_model_or_credentials(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'load_config', return_value=self.config), \
             patch.object(pipeline, 'expected_dates', return_value=['2026-10-07', '2026-10-08']), \
             patch.object(pipeline, 'app_is_running') as app, \
             patch.object(pipeline, 'github_token') as credential, \
             patch.object(pipeline, 'generate') as generate:
            pipeline.save_state({'days': {'2026-10-07': {'status': 'published'},
                                          '2026-10-08': {'status': 'no-batch'}}})
            for _ in range(3):
                self.assertEqual(pipeline.run_pipeline(automatic=True)['status'], 'up-to-date')
            app.assert_not_called()
            credential.assert_not_called()
            generate.assert_not_called()

    def test_login_failure_receives_cooldown_without_starting_research(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'load_config', return_value=self.config), \
             patch.object(pipeline, 'expected_dates', return_value=['2026-10-07']), \
             patch.object(pipeline, 'app_is_running', return_value=True), \
             patch.object(pipeline, 'github_token', side_effect=RuntimeError('Login unavailable')) as credential, \
             patch.object(pipeline, 'generate') as generate:
            first = pipeline.run_pipeline(automatic=True)
            self.assertEqual(first['status'], 'retry')
            self.assertEqual(first['remaining']['waiting'], ['2026-10-07'])
            self.assertEqual(pipeline.run_pipeline(automatic=True)['status'], 'up-to-date')
            credential.assert_called_once()
            generate.assert_not_called()

    def test_optional_delivery_errors_fall_back_but_required_equations_still_block(self):
        text = example_digest(include_priority=False).replace('2026-10-06', '2026-10-07')
        for groups in ([['A useful concept'], ['useful concept']], [['A useful concept'], ['A useful concept']],
                       [[]], 'not a list'):
            with self.subTest(groups=groups), redirect_stdout(io.StringIO()) as output:
                prepared = pipeline.prepare_generated_result({'status': 'ready', 'markdown': text,
                                                               'phrase_groups': groups})
                self.assertEqual(prepared['phrase_groups'], [])
                self.assertIn('audio-grouping-fallback', output.getvalue())
                pipeline.validate_result(prepared, snapshot(), '2026-10-07')
        text = text.replace('Summary of paper 1.', 'A quantity is $N$.')
        with redirect_stdout(io.StringIO()):
            prepared = pipeline.prepare_generated_result({'status': 'ready', 'markdown': text,
                                                           'phrase_groups': 'bad'})
        with self.assertRaisesRegex(ValueError, 'cover every distinct'):
            pipeline.validate_result(prepared, snapshot(), '2026-10-07')

    def test_rejects_wrong_date_wrong_batch_and_changed_title(self):
        result = {'status': 'ready', 'markdown': example_digest(include_priority=False).replace('2026-10-06', '2026-10-07')}
        pipeline.validate_result(result, snapshot(), '2026-10-07')
        for changed in (result['markdown'].replace('2026-10-07', '2026-10-08'),
                        result['markdown'].replace('2610.00001', '2610.99999'),
                        result['markdown'].replace('### Paper 1\n', '### Invented title\n')):
            with self.subTest(changed=changed[:80]), self.assertRaises(ValueError):
                pipeline.validate_result({**result, 'markdown': changed}, snapshot(), '2026-10-07')

    def test_existing_dates_never_generate_and_success_survives_restart(self):
        now = datetime(2026, 10, 8, 18, tzinfo=timezone.utc)
        text = example_digest(include_priority=False).replace('2026-10-06', '2026-10-08')
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'load_config', return_value=self.config), \
             patch.object(pipeline, 'app_is_running', return_value=True), \
             patch.object(pipeline, 'github_token', return_value='test-token'), \
             patch.object(pipeline, 'plan', side_effect=lambda config, state, _: pipeline_plan(config, state, now)), \
             patch.object(pipeline.publish_digest, 'check_date', side_effect=[{'status': 'exists'}, {'status': 'missing'}, {'status': 'exists'}]), \
             patch.object(pipeline, 'get_snapshot', return_value=snapshot(day='2026-10-08')), \
             patch.object(pipeline, 'generate', return_value={'status': 'ready', 'markdown': text}) as generate, \
             patch.object(pipeline.publish_digest, 'publish', return_value={'date': '2026-10-08', 'status': 'publication-queued', 'commit': 'a' * 40}):
            (Path(folder) / 'runs/2026-10-08').mkdir(parents=True)
            result = pipeline.run_pipeline()
            self.assertEqual(len(result['results']), 2)
            generate.assert_called_once()
            self.assertEqual(pipeline.read_state()['days']['2026-10-08']['status'], 'published')
            self.assertEqual(pipeline_plan(self.config, pipeline.read_state(), now)['due'], [])
            self.assertEqual(pipeline.run_pipeline(automatic=True)['status'], 'up-to-date')
            generate.assert_called_once()

    def test_missing_archive_never_starts_a_second_arxiv_collector(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'read_remote_snapshot', return_value=None), \
             patch.object(collector, 'collect') as collect:
            with self.assertRaises(pipeline.SnapshotPending):
                pipeline.get_snapshot('2026-10-14', self.config, 'test-token')
            collect.assert_not_called()

    def test_waiting_for_archive_checks_again_in_five_minutes_without_gpt(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, 'RUNTIME', Path(folder)), \
             patch.object(pipeline, 'load_config', return_value=self.config), \
             patch.object(pipeline, 'app_is_running', return_value=True), \
             patch.object(pipeline, 'github_token', return_value='test-token'), \
             patch.object(pipeline, 'plan', return_value={'due': ['2026-10-14']}), \
             patch.object(pipeline.publish_digest, 'check_date', return_value={'status': 'missing'}), \
             patch.object(pipeline, 'get_snapshot', side_effect=pipeline.SnapshotPending('Archive pending')), \
             patch.object(pipeline, 'generate') as generate:
            pipeline.run_pipeline()
            state = pipeline.read_state()
            waiting = state['days']['2026-10-14']
            self.assertEqual(waiting['waiting_for'], 'archive')
            delay = (datetime.fromisoformat(waiting['retry_at']) - datetime.now(timezone.utc)).total_seconds()
            self.assertGreater(delay, 290)
            self.assertLessEqual(delay, 300)
            self.assertNotIn('pause_until', state)
            generate.assert_not_called()


class StyleExampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in [('ROOT', self.root), ('RUNTIME', self.root / 'runtime')]:
            patched = patch.object(pipeline, name, value)
            patched.start()
            self.addCleanup(patched.stop)
        self.folder = pipeline.RUNTIME / 'runs/2026-10-19'

    def write_digest(self, day, directory='incoming'):
        path = self.root / directory / f'{day}.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        text = example_digest(include_priority=False).replace('2026-10-06', day)
        path.write_text(text + '\nMy reading order would be **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10**.', encoding='utf-8')
        return path

    def test_one_random_item_from_latest_earlier_digest_without_day_notes(self):
        for day in ['2026-10-15', '2026-10-16', '2026-10-19', '2026-10-20']:
            self.write_digest(day)
        with patch.object(pipeline.random, 'choice', side_effect=lambda papers: papers[-1]) as choose:
            path = pipeline.prepare_style_example('2026-10-19', self.folder)
        text = path.read_text(encoding='utf-8')
        choose.assert_called_once()
        self.assertEqual(len(choose.call_args.args[0]), 10)
        self.assertIn('## arXiv-2026-10-16 — Item 10', text)
        self.assertEqual(text.count('\n## arXiv-'), 1)
        self.assertIn('Summary of paper 10.', text)
        self.assertNotIn('Summary of paper 9.', text)
        self.assertNotIn('Overview', text)
        self.assertNotIn('My reading order', text)
        self.assertNotIn('Priority', text)
        self.assertIn('not evidence, a selection criterion', text)

    def test_retries_reuse_the_same_item(self):
        self.write_digest('2026-10-16')
        path = pipeline.prepare_style_example('2026-10-19', self.folder)
        original = path.read_bytes()
        self.write_digest('2026-10-18')
        with patch.object(pipeline.random, 'choice') as choose:
            self.assertEqual(pipeline.prepare_style_example('2026-10-19', self.folder).read_bytes(), original)
            choose.assert_not_called()

    def test_published_cached_result_is_available_before_checkout_sync(self):
        self.write_digest('2026-10-15')
        source = self.write_digest('2026-10-16', 'scratch')
        folder = pipeline.RUNTIME / 'runs/2026-10-16'
        folder.mkdir(parents=True)
        (folder / 'result.json').write_text(json.dumps({'status': 'ready', 'markdown': source.read_text(encoding='utf-8')}), encoding='utf-8')
        pipeline.save_state({'days': {'2026-10-16': {'status': 'published'}}})
        text = pipeline.prepare_style_example('2026-10-19', self.folder).read_text(encoding='utf-8')
        self.assertIn('## arXiv-2026-10-16', text)

    def test_unpublished_draft_cannot_be_a_style_reference(self):
        source = self.write_digest('2026-10-16', 'scratch')
        folder = pipeline.RUNTIME / 'runs/2026-10-16'
        folder.mkdir(parents=True)
        (folder / 'result.json').write_text(json.dumps({'status': 'ready', 'markdown': source.read_text(encoding='utf-8')}), encoding='utf-8')
        pipeline.save_state({'days': {'2026-10-16': {'status': 'needs-review'}}})
        self.assertIsNone(pipeline.prepare_style_example('2026-10-19', self.folder))

    def test_json_archive_and_malformed_newer_digest(self):
        source = self.write_digest('2026-10-15', 'scratch')
        folder = self.root / 'content/digests'
        folder.mkdir(parents=True)
        (folder / '2026-10-15.json').write_text(json.dumps(pipeline.parse_digest(source.read_text(encoding='utf-8'))), encoding='utf-8')
        invalid = self.root / 'incoming/2026-10-16.md'
        invalid.parent.mkdir()
        invalid.write_text('Incomplete digest', encoding='utf-8')
        self.assertIn('## arXiv-2026-10-15', pipeline.prepare_style_example('2026-10-19', self.folder).read_text(encoding='utf-8'))

    def test_bootstrap_uses_one_frozen_item_only_for_a_later_day(self):
        self.write_digest('2026-10-06', 'prompts/examples')
        self.assertIsNone(pipeline.prepare_style_example('2026-10-06', self.folder))
        text = pipeline.prepare_style_example('2026-10-07', self.folder).read_text(encoding='utf-8')
        self.assertEqual(text.count('\n## arXiv-'), 1)
        self.assertIn('## arXiv-2026-10-06', text)

    def test_generate_supplies_only_single_item_path_and_reuses_final_result(self):
        self.write_digest('2026-10-16')
        prompts = self.root / 'prompts'
        prompts.mkdir()
        (prompts / 'local-research.md').write_text('Study current sources independently.', encoding='utf-8')
        (prompts / 'local-research-writing.md').write_text('Write source-grounded prose.', encoding='utf-8')
        (prompts / 'local-research-audio.md').write_text('Annotate the equations faithfully.', encoding='utf-8')
        config = {'model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'generation_timeout_minutes': 45}
        def run(command, **kwargs):
            if command[-2:] == ['login', 'status']:
                return type('Result', (), {'returncode': 0, 'stdout': 'ChatGPT', 'stderr': ''})()
            prompt = kwargs['input']
            self.assertIn(str(self.folder / 'style-example.md'), prompt)
            self.assertIn('do not load the full previous digest', prompt)
            self.assertIn('Catalog lookup: python tools/local_pipeline.py catalog 2026-10-19', prompt)
            self.assertIn('Follow next_command until complete is true', prompt)
            self.assertNotIn('Catalog: ', prompt)
            self.assertNotIn('prompts/examples/2026-10-06.md', prompt)
            text = example_digest(include_priority=False).replace('2026-10-06', '2026-10-19')
            output = Path(command[command.index('--output-last-message') + 1])
            output.write_text(json.dumps({'status': 'ready', 'markdown': text}), encoding='utf-8')
            return type('Result', (), {'returncode': 0})()
        with patch.object(pipeline, 'find_codex', return_value='codex'), patch.object(pipeline.subprocess, 'run', side_effect=run) as process:
            pipeline.generate('2026-10-19', snapshot(day='2026-10-19'), config)
            self.assertEqual(process.call_count, 2)
            pipeline.generate('2026-10-19', snapshot(day='2026-10-19'), config)
            self.assertEqual(process.call_count, 2)

    def test_failed_or_interrupted_generation_never_becomes_a_cached_result(self):
        self.write_digest('2026-10-16')
        (self.root / 'prompts').mkdir()
        (self.root / 'prompts/local-research.md').write_text('Research', encoding='utf-8')
        (self.root / 'prompts/local-research-writing.md').write_text('Write', encoding='utf-8')
        (self.root / 'prompts/local-research-audio.md').write_text('Annotate', encoding='utf-8')
        config = {'model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'generation_timeout_minutes': 45}
        failure = [1, 'timeout', 'json', 0]
        def run(command, **kwargs):
            if command[-2:] == ['login', 'status']:
                return subprocess.CompletedProcess(command, 0, 'ChatGPT', '')
            output = Path(command[command.index('--output-last-message') + 1])
            current = failure.pop(0)
            text = example_digest(include_priority=False).replace('2026-10-06', '2026-10-19')
            output.write_text('{"status":' if current == 'json' else json.dumps(
                {'status': 'ready', 'markdown': text}), encoding='utf-8')
            if current == 'timeout':
                raise subprocess.TimeoutExpired(command, 1)
            return subprocess.CompletedProcess(command, current if isinstance(current, int) else 0)
        with patch.object(pipeline, 'find_codex', return_value='codex'), \
             patch.object(pipeline.subprocess, 'run', side_effect=run):
            for _ in range(3):
                with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                    pipeline.generate('2026-10-19', snapshot(day='2026-10-19'), config)
                self.assertFalse((self.folder / 'result.json').exists())
            result = pipeline.generate('2026-10-19', snapshot(day='2026-10-19'), config)
        pipeline.validate_result(result, snapshot(day='2026-10-19'), '2026-10-19')
        self.assertTrue((self.folder / 'result.json').exists())
        self.assertEqual(len(list(self.folder.glob('result.incomplete-*.json'))), 3)

    def test_cached_generation_repairs_capitalization_without_another_model_call(self):
        self.folder.mkdir(parents=True)
        text = example_digest(include_priority=False).replace('2026-10-06', '2026-10-19')
        text = text.replace('Summary of paper 1.', 'Counterdiabatic driving is useful.')
        result = {'status': 'ready', 'markdown': text,
                  'phrase_groups': [['counterdiabatic driving'], ['conditional relative entropy']]}
        output = self.folder / 'result.json'
        output.write_text(json.dumps(result), encoding='utf-8')
        with patch.object(pipeline, 'find_codex') as cli, patch.object(pipeline.subprocess, 'run') as process:
            log, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(log), redirect_stderr(errors):
                prepared = pipeline.generate('2026-10-19', snapshot(day='2026-10-19'), {})
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(json.loads(log.getvalue()), {'status': 'audio-annotation-skipped',
                                                     'phrase': 'conditional relative entropy'})
        self.assertEqual(prepared['phrase_groups'], [['Counterdiabatic driving']])
        pipeline.validate_result(prepared, snapshot(day='2026-10-19'), '2026-10-19')
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), result)
        cli.assert_not_called()
        process.assert_not_called()

    @unittest.skipUnless(shutil.which('powershell.exe'), 'Windows watcher requires PowerShell')
    def test_optional_annotation_logging_survives_windows_watcher_redirection(self):
        # Windows PowerShell treats native stderr as terminating with this setting.
        # Exercise the same invocation/redirection used by the startup watcher.
        self.folder.mkdir(parents=True)
        text = example_digest(include_priority=False)
        result = self.folder / 'input.json'
        result.write_text(json.dumps({'status': 'ready', 'markdown': text,
                                      'phrase_groups': [['conditional relative entropy']]}), encoding='utf-8')
        script = self.folder / 'prepare.py'
        script.write_text('import sys,json\n'
                          f'sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})\n'
                          'from tools.local_pipeline import prepare_generated_result\n'
                          f'with open({str(result)!r}, encoding="utf-8") as f: result=json.load(f)\n'
                          'prepare_generated_result(result)\nprint("completed")\n', encoding='utf-8')
        log = self.folder / 'watcher.log'
        runner = self.folder / 'watch.ps1'
        runner.write_text("param($pythonPath,$scriptPath,$logPath)\n$ErrorActionPreference='Stop'\n"
                          '& $pythonPath $scriptPath >> $logPath 2>&1\nexit $LASTEXITCODE\n', encoding='utf-8')
        completed = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(runner),
                                    sys.executable, str(script), str(log)], capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # Windows PowerShell redirects native output as UTF-16.
        output = log.read_text(encoding='utf-16')
        self.assertIn('audio-annotation-skipped', output)
        self.assertIn('completed', output)


pipeline_plan = pipeline.plan


if __name__ == '__main__':
    unittest.main()
