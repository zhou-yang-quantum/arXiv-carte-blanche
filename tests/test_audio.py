import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave
import zipfile
from unittest.mock import patch

from tools.build import ROOT, audio_source_hash, audio_script_hash, load_audio_index
from tools.generate_audio import fingerprint, concatenate, append_silence, text_chunks, build_playlist_archive, ensure_playlist, render
from tools.speech_text import make_script
from tools.import_digest import parse_digest
from tools.project import AUDIO_BASE, LEGACY_AUDIO_BASE, canonical_audio_manifest
from test_archive import example_digest


class AudioTests(unittest.TestCase):
    def setUp(self):
        # Synthetic October 6 fixtures must not pick up that real day's companion.
        sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(sandbox.cleanup)
        root = patch('tools.build.ROOT', Path(sandbox.name))
        root.start()
        self.addCleanup(root.stop)
        self.day = parse_digest(example_digest(include_priority=False))
        prefix = 'https://github.com/zhou-yang-quantum/arXiv-carte-blanche/releases/download/audio-test/'
        self.audio = {'date': self.day['date'], 'source_hash': audio_source_hash(self.day),
                      'day': {'url': prefix + 'day.mp3', 'duration': 300},
                      'items': [{'rank': p['rank'], 'id': p['id'], 'url': prefix + f'item-{p["rank"]:02}.mp3',
                                 'duration': 30} for p in self.day['papers']]}

    def read(self, audio):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'index.json')
            path.write_text(json.dumps({'days': {self.day['date']: audio}}), encoding='utf-8')
            return load_audio_index([self.day], path)

    def test_edited_prose_cannot_use_an_old_recording(self):
        self.assertIn(self.day['date'], self.read(self.audio)['days'])
        self.day['papers'][0]['summary'] += ' Corrected statement.'
        self.assertEqual(self.read(self.audio)['days'], {})

    def test_pre_rename_audio_links_migrate_without_changing_recordings(self):
        legacy = json.loads(json.dumps(self.audio).replace(AUDIO_BASE, LEGACY_AUDIO_BASE))
        legacy['speech_url'] = LEGACY_AUDIO_BASE + 'audio-test/speech.txt'
        legacy['playlist_url'] = LEGACY_AUDIO_BASE + 'audio-test/arxiv-2026-10-06-playlist.zip'
        original = json.loads(json.dumps(legacy))
        migrated = self.read(legacy)['days'][self.day['date']]
        for track in [migrated['day'], *migrated['items']]:
            self.assertTrue(track['url'].startswith(AUDIO_BASE))
        self.assertEqual(migrated['playlist_url'], AUDIO_BASE + 'audio-test/arxiv-2026-10-06-playlist.zip')
        self.assertEqual(migrated['speech_url'], AUDIO_BASE + 'audio-test/speech.txt')
        self.assertEqual(migrated['source_hash'], original['source_hash'])
        self.assertEqual(legacy, original)
        self.assertEqual(canonical_audio_manifest(migrated), migrated)

    def test_lookalike_audio_repositories_remain_rejected_after_rename(self):
        for repository in ('arXiv-carte-blanche-other', 'daily-arXiv-other'):
            changed = json.loads(json.dumps(self.audio))
            changed['day']['url'] = f'https://github.com/zhou-yang-quantum/{repository}/releases/download/audio-test/day.mp3'
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                self.read(changed)

    def test_legacy_playlist_reuse_needs_no_upload_or_synthesis(self):
        legacy = json.loads(json.dumps(self.audio))
        tag = 'audio-2026-10-06-fixture'
        legacy['day']['url'] = LEGACY_AUDIO_BASE + tag + '/day.mp3'
        legacy['playlist_url'] = LEGACY_AUDIO_BASE + tag + '/arxiv-2026-10-06-playlist.zip'
        with patch('tools.generate_audio.command') as command:
            migrated = ensure_playlist(legacy, tag)
            self.assertEqual(migrated['playlist_url'], AUDIO_BASE + tag + '/arxiv-2026-10-06-playlist.zip')
            command.assert_not_called()

    def test_reuse_only_skips_missing_recordings_without_loading_speech_runtime(self):
        from tools import generate_audio
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / 'text').mkdir()
            prepared = {'version': 6, 'date': self.day['date'], 'items': []}
            (folder / 'text' / (self.day['date'] + '.json')).write_text(json.dumps(prepared), encoding='utf-8')
            scripts = folder / 'audio/scripts'
            scripts.mkdir(parents=True)
            script = make_script(self.day, [])
            (scripts / (self.day['date'] + '.json')).write_text(json.dumps(script), encoding='utf-8')
            (folder / 'audio/index.json').write_text('{"days": {"seed": {"date": "seed"}}}', encoding='utf-8')
            with patch.object(generate_audio, 'ROOT', folder), patch.object(generate_audio, 'CACHE', folder), \
                 patch.object(generate_audio, 'load_archive', return_value=[self.day]), \
                 patch.object(generate_audio, 'command'), patch.object(generate_audio, 'cached_release', return_value=None), \
                 patch.object(generate_audio, 'download_voice') as voice, patch.object(generate_audio, 'render') as render, \
                 patch('sys.argv', ['generate_audio.py', '--reuse-only']):
                generate_audio.main()
                voice.assert_not_called()
                render.assert_not_called()
            self.assertEqual(json.loads((folder / 'audio/index.json').read_text(encoding='utf-8'))['days'], {})

    def test_wrong_item_ids_ranks_and_external_hosts_are_rejected(self):
        for key, value in [('id', '2610.99999'), ('rank', 20), ('url', 'https://example.com/track.mp3')]:
            changed = json.loads(json.dumps(self.audio))
            changed['items'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read(changed)

    def test_hash_covers_all_reading_sections_but_not_topic_tags(self):
        original = audio_source_hash(self.day)
        self.day['papers'][0]['topics'] = ['Quantum simulation']
        self.assertEqual(original, audio_source_hash(self.day))
        for field in ('title', 'authors', 'summary', 'background', 'why'):
            changed = json.loads(json.dumps(self.day))
            changed['papers'][0][field] += ' Changed.'
            self.assertNotEqual(original, audio_source_hash(changed))

    def test_playlist_boundaries_and_download_must_match_the_recording(self):
        normalized = self.read(self.audio)['days'][self.day['date']]
        self.assertEqual([item['start'] for item in normalized['items']], list(range(0, 300, 30)))
        for changes in ({'start': -1}, {'start': 1}, {'duration': float('inf')}):
            changed = json.loads(json.dumps(self.audio))
            changed['items'][1].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.read(changed)
        for url in ('https://example.com/playlist.zip', self.audio['day']['url'].replace('day.mp3', 'arxiv-2026-10-07-playlist.zip')):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.read({**self.audio, 'playlist_url': url})

    def test_playlist_zip_has_all_twelve_dated_item_files_with_original_bytes(self):
        manifest = {'date': '2026-10-15', 'items': [{'rank': rank} for rank in range(1, 13)]}
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for rank in range(1, 13):
                (folder / f'item-{rank:02}.mp3').write_bytes(b'ID3' + bytes([rank]) * 64)
            target = build_playlist_archive(manifest, folder)
            self.assertEqual(target.name, 'arxiv-2026-10-15-playlist.zip')
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.namelist(), [f'arxiv-2026-10-15-item-{rank:02}.mp3' for rank in range(1, 13)])
                self.assertIsNone(archive.testzip())
                for rank in range(1, 13):
                    self.assertEqual(archive.read(f'arxiv-2026-10-15-item-{rank:02}.mp3'), b'ID3' + bytes([rank]) * 64)

    def test_playlist_checksum_is_identical_on_windows_and_linux(self):
        manifest = {'date': '2026-10-15', 'items': [{'rank': 1}]}
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / 'item-01.mp3').write_bytes(b'ID3 original recording')
            with patch('zipfile.sys.platform', 'linux'):
                linux = build_playlist_archive(manifest, folder).read_bytes()
            with patch('zipfile.sys.platform', 'win32'):
                windows = build_playlist_archive(manifest, folder).read_bytes()
            self.assertEqual(linux, windows)

    def test_incomplete_playlist_is_not_published_as_a_download(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            with self.assertRaises(FileNotFoundError):
                build_playlist_archive(self.audio, folder)
            self.assertFalse((folder / 'arxiv-2026-10-06-playlist.zip').exists())

    def test_reused_release_gets_playlist_without_speech_generation(self):
        manifest = {**self.audio, 'items': self.audio['items'][:2]}
        tag = 'audio-2026-10-06-fixture'
        prefix = 'https://github.com/zhou-yang-quantum/arXiv-carte-blanche/releases/download/' + tag + '/'
        manifest['day'] = {**manifest['day'], 'url': prefix + 'day.mp3'}
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if 'view' in args:
                return '{"assets": []}'
            if 'download' in args:
                (Path(args[-1]) / args[args.index('--pattern') + 1]).write_bytes(b'original MP3')
            return ''
        with tempfile.TemporaryDirectory() as folder, patch('tools.generate_audio.CACHE', Path(folder)), patch('tools.generate_audio.command', side_effect=run):
            updated = ensure_playlist(manifest, tag)
            self.assertEqual(updated['playlist_url'], prefix + 'arxiv-2026-10-06-playlist.zip')
            self.assertEqual(sum('download' in call for call in calls), 2)
            self.assertTrue(calls[-2][-1].endswith('playlist.zip'))
            self.assertTrue(calls[-1][-1].endswith('manifest.json'))
            self.assertNotIn('playlist_url', manifest)
            calls.clear()
            self.assertEqual(ensure_playlist(updated, tag), updated)
            self.assertEqual(calls, [])

    def test_immutable_release_identity_changes_with_speech_or_voice_source(self):
        first = {'date': '2026-10-08', 'items': [{'text': 'An exact sentence.'}]}
        self.assertEqual(fingerprint(first), fingerprint(json.loads(json.dumps(first))))
        self.assertNotEqual(fingerprint(first), fingerprint({**first, 'items': [{'text': 'A different sentence.'}]}))

    def test_math_requires_complete_plain_english_without_changing_prose(self):
        self.day['papers'][0]['summary'] = 'The result is $x^2$.'
        original = json.loads(json.dumps(self.day))
        with self.assertRaises(ValueError):
            make_script(self.day, [])
        with self.assertRaises(ValueError):
            make_script(self.day, [{'latex': '$x^2$', 'spoken': 'x^2'}])
        script = make_script(self.day, [{'latex': '$x^2$', 'spoken': 'x squared'}])
        self.assertEqual(self.day, original)
        self.assertEqual(script['source_hash'], audio_source_hash(self.day))
        with self.assertRaises(ValueError):
            make_script(self.day, script['pronunciations'] * 2)

    def test_edited_pronunciation_cannot_use_old_audio(self):
        script = make_script(self.day, [])
        with tempfile.TemporaryDirectory() as folder, patch('tools.build.ROOT', Path(folder)):
            scripts = Path(folder, 'audio/scripts')
            scripts.mkdir(parents=True)
            (scripts / (self.day['date'] + '.json')).write_text(json.dumps(script), encoding='utf-8')
            self.assertEqual(self.read(self.audio)['days'], {})
            self.audio['speech_script_hash'] = audio_script_hash(script)
            self.assertIn(self.day['date'], self.read(self.audio)['days'])

    def test_math_rhythm_rejects_invalid_or_legacy_controls(self):
        self.day['papers'][0]['summary'] = 'The result is $x$.'
        invalid = ['[pause] x', '[p]', '()', '(J (plus one))', '(J plus one',
                   'J plus one)', '(J [p] plus one)', '<break/> x', 'x^2']
        for spoken in invalid:
            with self.subTest(spoken=spoken), self.assertRaises(ValueError):
                make_script(self.day, [{'latex': '$x$', 'spoken': spoken}])
        with self.assertRaises(ValueError):
            make_script(self.day, [{'latex': '$x$', 'spoken': 'x [p] equals one'}], version=4)

    def test_phrase_groups_are_source_exact_nonoverlapping_and_cannot_split_math(self):
        self.day['papers'][0]['title'] = 'Large $N$ Vector and SYK-like Models'
        self.day['papers'][0]['summary'] = 'The Sachdev–Ye–Kitaev model is useful.'
        readings = [{'latex': '$N$', 'spoken': 'N'}]
        groups = [['Large $N$', 'Vector and SYK-like Models'], ['Sachdev–Ye–Kitaev']]
        original = json.loads(json.dumps(self.day))
        script = make_script(self.day, readings, phrase_groups=groups)
        self.assertEqual(script['phrase_groups'], groups)
        self.assertEqual(self.day, original)
        self.assertEqual(script, make_script(self.day, readings, version=script['version'], phrase_groups=script['phrase_groups']))
        self.assertNotEqual(audio_script_hash(script), audio_script_hash(make_script(self.day, readings)))
        invalid = ['phrase', ['phrase'], [[]], [['']], [[' Large $N$']], [['made-up jargon']],
                   [['Sachdev–Ye–Kitaev'], ['Sachdev–Ye–Kitaev']],
                   [['Sachdev–Ye–Kitaev'], ['Sachdev–Ye–Kitaev model']],
                   [['Large $N', '$ Vector and SYK-like Models']], [['N']]]
        for value in invalid:
            with self.subTest(groups=value), self.assertRaises(ValueError):
                make_script(self.day, readings, phrase_groups=value)
        with self.assertRaises(ValueError):
            make_script(self.day, readings, version=5, phrase_groups=groups)

    @unittest.skipUnless(shutil.which('node'), 'Speech text exporter requires Node.js')
    def test_title_pause_and_letter_a_are_versioned_without_rewriting_prose(self):
        self.day['papers'][0]['summary'] = 'A useful quantity is $S(AB)$. A result follows.'
        pronunciations = [{'latex': '$S(AB)$', 'spoken': 'the entropy of A B'}]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'days.json'
            source.write_text(json.dumps([self.day]), encoding='utf-8')
            for version in (2, 3, 4, 5, 6):
                script = make_script(self.day, pronunciations, version=version)
                (folder / (self.day['date'] + '.json')).write_text(json.dumps(script), encoding='utf-8')
                subprocess.run(['node', str(ROOT / 'tools/export_audio.mjs'), str(source), str(folder / 'text'), str(folder)],
                               check=True, capture_output=True, timeout=60)
                prepared = json.loads((folder / 'text' / (self.day['date'] + '.json')).read_text(encoding='utf-8'))
                item = prepared['items'][0]
                expected = ['heading', 'summary', 'background', 'why']
                heading = next(section for section in item['sections'] if section['name'] == 'heading')
                if version >= 3:
                    expected.insert(1, 'authors')
                    self.assertEqual(prepared['title_author_pause_seconds'], 0.75)
                    self.assertNotIn('Authors:', heading['text'])
                    self.assertIn('Authors:', next(section for section in item['sections'] if section['name'] == 'authors')['text'])
                    self.assertIn('A useful quantity is the entropy of eh B. A result follows.', item['text'])
                else:
                    self.assertNotIn('title_author_pause_seconds', prepared)
                    self.assertIn('Authors:', item['sections'][0]['text'])
                    self.assertIn('the entropy of A B', item['text'])
                if version >= 4:
                    expected.insert(0, 'item')
                    self.assertEqual(item['sections'][0]['text'], 'Item 1.')
                    self.assertEqual(heading['text'], 'Paper 1')
                    self.assertEqual(prepared['item_title_pause_seconds'], 0.6)
                    self.assertNotIn('October', item['text'])
                self.assertEqual([section['name'] for section in item['sections']], expected)
                self.assertEqual(prepared['text'], '\n\n'.join(item['text'] for item in prepared['items']))

    @unittest.skipUnless(shutil.which('node') and importlib.util.find_spec('numpy'), 'Math rhythm requires Node.js and NumPy')
    def test_math_preferences_export_and_render_with_real_pauses_and_group_speed(self):
        import numpy as np
        from types import SimpleNamespace
        formula = r'$F_j = c^\dagger_j + c^\dagger_{j+1}$'
        self.day['papers'][0]['summary'] = 'A useful quantity (in QEC) is ' + formula + '. The $[[4,2,2]]$ code follows.'
        original = json.loads(json.dumps(self.day))
        script = make_script(self.day, [
            {'latex': formula, 'spoken': 'F sub J [p] equals [p] C sub J dagger [p] plus [p] C sub (J plus one) dagger'},
            {'latex': '$[[4,2,2]]$', 'spoken': 'four two two'},
        ])
        self.assertEqual(script['version'], 6)
        self.assertEqual(self.day, original)
        calls = []
        def synthesize(text, **kwargs):
            calls.append((text, kwargs['speed']))
            return np.full(240, 0.25), 24000
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'days.json'
            source.write_text(json.dumps([self.day]), encoding='utf-8')
            (folder / (self.day['date'] + '.json')).write_text(json.dumps(script), encoding='utf-8')
            subprocess.run(['node', str(ROOT / 'tools/export_audio.mjs'), str(source), str(folder / 'text'), str(folder)],
                           check=True, capture_output=True, timeout=60)
            prepared = json.loads((folder / 'text' / (self.day['date'] + '.json')).read_text(encoding='utf-8'))
            summary = next(section for section in prepared['items'][0]['sections'] if section['name'] == 'summary')
            self.assertEqual(summary['text'], 'Summary.\n\nA useful quantity (in Q E C) is F sub J equals C sub J dagger plus C sub J plus one dagger. The four two two code follows.')
            self.assertEqual([segment for segment in summary['segments'] if 'pause_seconds' in segment],
                             [{'pause_seconds': 0.18}] * 4)
            self.assertEqual([segment['text'] for segment in summary['segments'] if segment.get('speed') == 1.1], ['J plus one'])
            self.assertNotIn('[p]', prepared['text'])
            self.assertNotIn('(J plus one)', prepared['text'])
            prepared['items'] = prepared['items'][:1]
            prepared['text'] = prepared['items'][0]['text']
            prepared['speech_script_hash'] = audio_script_hash(script)
            with patch('tools.generate_audio.CACHE', folder), patch('tools.generate_audio.command'):
                _, output = render(prepared, 'rhythm', SimpleNamespace(create=synthesize))
            self.assertIn(('J plus one', 1.1), calls)
            self.assertEqual([text for text, speed in calls if speed == 1.1], ['J plus one'])
            self.assertTrue(all('[p]' not in text and '(J plus one)' not in text for text, _ in calls))
            tone = (np.full(240, 0.25) * 32767).astype('<i2').tobytes()
            expected_pcm = b''.join(b'\0' * 8640 if 'pause_seconds' in segment else tone
                                    for segment in summary['segments'])
            with wave.open(str(output / 'item-01-summary.wav'), 'rb') as recording:
                self.assertEqual(recording.readframes(recording.getnframes()), expected_pcm)
            self.assertEqual((output / 'speech.txt').read_text(encoding='utf-8'), prepared['text'] + '\n')

    @unittest.skipUnless(shutil.which('node') and importlib.util.find_spec('numpy'), 'Phrase grouping requires Node.js and NumPy')
    def test_technical_phrases_keep_names_together_and_preserve_shared_modifier_pause(self):
        import numpy as np
        from types import SimpleNamespace
        phrase = 'Large $N$ Vector and SYK-like Models'
        self.day['papers'][0]['title'] = '𝒩: Kinetic Equations and Turbulence in ' + phrase
        # Put the name beyond the ordinary chunk boundary to catch accidental splitting.
        self.day['papers'][0]['summary'] = 'An introductory word. ' * 31 + 'Sachdev–Ye–Kitaev.'
        source_before = json.loads(json.dumps(self.day))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'days.json'
            source.write_text(json.dumps([self.day]), encoding='utf-8')
            for parts in ([phrase], ['Large $N$', 'Vector and SYK-like Models']):
                with self.subTest(parts=parts):
                    script = make_script(self.day, [{'latex': '$N$', 'spoken': '(N)'}],
                                         phrase_groups=[parts, ['Sachdev–Ye–Kitaev']])
                    (folder / (self.day['date'] + '.json')).write_text(json.dumps(script), encoding='utf-8')
                    subprocess.run(['node', str(ROOT / 'tools/export_audio.mjs'), str(source), str(folder / 'text'), str(folder)],
                                   check=True, capture_output=True, timeout=60)
                    prepared = json.loads((folder / 'text' / (self.day['date'] + '.json')).read_text(encoding='utf-8'))
                    heading = next(section for section in prepared['items'][0]['sections'] if section['name'] == 'heading')
                    joined = [segment for segment in heading['segments'] if segment.get('protected_spans')]
                    expected = ['Large N Vector and S Y K like Models'] if len(parts) == 1 else ['Large N', 'Vector and S Y K like Models']
                    self.assertEqual([segment['text'][start:end] for segment in joined for start, end in segment['protected_spans']], expected)
                    self.assertTrue(all(segment['speed'] == 1.0 for segment in joined))
                    pauses = [segment for segment in heading['segments'] if 'pause_seconds' in segment]
                    self.assertEqual(pauses, [{'pause_seconds': 0.18}] * (len(parts) - 1))
                    self.assertEqual(prepared['items'][0]['title'], source_before['papers'][0]['title'])
                    self.assertNotIn('DIGESTPHRASE', prepared['text'])
                    prepared['items'] = prepared['items'][:1]
                    prepared['text'] = prepared['items'][0]['text']
                    prepared['speech_script_hash'] = audio_script_hash(script)
                    calls = []
                    def synthesize(text, **kwargs):
                        calls.append((text, kwargs['speed']))
                        return np.full(240, 0.25), 24000
                    tag = 'phrase-' + str(len(parts))
                    with patch('tools.generate_audio.CACHE', folder), patch('tools.generate_audio.command'):
                        render(prepared, tag, SimpleNamespace(create=synthesize))
                    self.assertTrue(any('Sachdev Ye Kitaev.' in text for text, _ in calls))
                    for text in expected:
                        self.assertTrue(any(text in spoken for spoken, _ in calls))
                    self.assertIn(('𝒩: Kinetic Equations and Turbulence in ' + expected[0], 1.0), calls)
                    self.assertTrue(all(speed == 1.0 for _, speed in calls))
                    self.assertNotIn(('.', 1.0), calls)
                    self.assertEqual(self.day, source_before)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'Renderer requires NumPy')
    def test_item_number_and_title_are_separated_by_real_pcm_silence(self):
        import numpy as np
        from types import SimpleNamespace
        calls = []
        def synthesize(text, **kwargs):
            calls.append(text)
            return np.full(240, 0.25), 24000
        prepared = {'version': 4, 'date': self.day['date'], 'title': self.day['title'],
                    'source_hash': 'fixture', 'speech_script_hash': 'fixture',
                    'item_title_pause_seconds': 0.6, 'title_author_pause_seconds': 0.75,
                    'heading_pause_seconds': 0.5, 'section_pause_seconds': 1.5, 'item_pause_seconds': 1.5,
                    'items': [{'rank': 1, 'id': '2610.00001', 'title': 'Paper 1', 'sections': [
                        {'name': name, 'text': text} for name, text in zip(
                            ['item', 'heading', 'authors', 'summary', 'background', 'why'],
                            ['Item 1.', 'Paper 1', 'Authors: Author', 'Summary.', 'Background.', 'Why it matters?'])]}]}
        prepared['text'] = '\n\n'.join(section['text'] for section in prepared['items'][0]['sections'])
        with tempfile.TemporaryDirectory() as folder, patch('tools.generate_audio.CACHE', Path(folder)), patch('tools.generate_audio.command'):
            manifest, output = render(prepared, 'fixture', SimpleNamespace(create=synthesize))
            self.assertEqual(calls[:2], ['Item 1.', 'Paper 1'])
            self.assertEqual(manifest['items'][0]['sections'][1]['start'], 0.61)
            with wave.open(str(output / 'item-01.wav'), 'rb') as recording:
                opening = recording.readframes(240 + 14400 + 240)
                self.assertNotEqual(opening[:480], b'\0' * 480)
                self.assertEqual(opening[480:-480], b'\0' * 28800)
                self.assertNotEqual(opening[-480:], b'\0' * 480)

    def test_day_pcm_is_exactly_item_pcm_and_pauses_are_real_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            files, content = [], []
            for index in range(2):
                path = Path(folder, f'item-{index}.wav')
                with wave.open(str(path), 'wb') as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(1000)
                    output.writeframes(bytes([index + 1, 0]) * 100)
                    append_silence(output, 1.5)
                with wave.open(str(path), 'rb') as source:
                    data = source.readframes(source.getnframes())
                    self.assertEqual(data[-3000:], b'\0' * 3000)
                    content.append(data)
                files.append(path)
            target = Path(folder, 'day.wav')
            concatenate(files, target)
            with wave.open(str(target), 'rb') as source:
                self.assertEqual(source.readframes(source.getnframes()), b''.join(content))

    def test_chunking_preserves_every_word_including_long_sentences(self):
        text = ' '.join('word' + str(i) for i in range(500))
        self.assertEqual(' '.join(text_chunks(text)).split(), text.split())

    def test_chunking_moves_a_complete_technical_term_to_the_next_chunk(self):
        phrase = 'Sachdev Ye Kitaev'
        text = 'Some text before the ' + phrase + ' model.'
        start = text.index(phrase)
        chunks = list(text_chunks(text, limit=30, protected_spans=[(start, start + len(phrase))]))
        self.assertEqual(chunks, ['Some text before the', 'Sachdev Ye Kitaev model.'])
        self.assertEqual(' '.join(chunks), text)


if __name__ == '__main__':
    unittest.main()
