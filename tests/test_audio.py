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
        prefix = 'https://github.com/zhou-yang-quantum/daily-arXiv/releases/download/audio-test/'
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

    def test_incomplete_playlist_is_not_published_as_a_download(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            with self.assertRaises(FileNotFoundError):
                build_playlist_archive(self.audio, folder)
            self.assertFalse((folder / 'arxiv-2026-10-06-playlist.zip').exists())

    def test_reused_release_gets_playlist_without_speech_generation(self):
        manifest = {**self.audio, 'items': self.audio['items'][:2]}
        tag = 'audio-2026-10-06-fixture'
        prefix = 'https://github.com/zhou-yang-quantum/daily-arXiv/releases/download/' + tag + '/'
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

    @unittest.skipUnless(shutil.which('node'), 'Speech text exporter requires Node.js')
    def test_title_pause_and_letter_a_are_versioned_without_rewriting_prose(self):
        self.day['papers'][0]['summary'] = 'A useful quantity is $S(AB)$. A result follows.'
        pronunciations = [{'latex': '$S(AB)$', 'spoken': 'the entropy of A B'}]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'days.json'
            source.write_text(json.dumps([self.day]), encoding='utf-8')
            for version in (2, 3, 4):
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
                if version == 4:
                    expected.insert(0, 'item')
                    self.assertEqual(item['sections'][0]['text'], 'Item 1.')
                    self.assertEqual(heading['text'], 'Paper 1')
                    self.assertEqual(prepared['item_title_pause_seconds'], 0.6)
                    self.assertNotIn('October', item['text'])
                self.assertEqual([section['name'] for section in item['sections']], expected)
                self.assertEqual(prepared['text'], '\n\n'.join(item['text'] for item in prepared['items']))

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


if __name__ == '__main__':
    unittest.main()
