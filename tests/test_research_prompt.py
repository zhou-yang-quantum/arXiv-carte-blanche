from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import local_pipeline as pipeline


class ResearchPromptTests(unittest.TestCase):
    def test_all_instructions_are_supplied_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = root / 'prompts'
            prompts.mkdir()
            texts = {'local-research.md': 'SCREENING_CONTENT',
                     'local-research-writing.md': 'WRITING_CONTENT',
                     'local-research-audio.md': 'AUDIO_CONTENT'}
            for name, text in texts.items():
                (prompts / name).write_text(text, encoding='utf-8')
            with patch.object(pipeline, 'ROOT', root):
                prompt = pipeline.research_prompt('2026-10-19', root / 'style-example.md')
            for text in texts.values():
                self.assertIn(text, prompt)
            self.assertIn('catalog 2026-10-19', prompt)
            self.assertIn('paper 2026-10-19 ID1 ID2', prompt)
            self.assertIn(str(root / 'style-example.md'), prompt)
            self.assertIn('after source verification', prompt)

    def test_missing_instruction_file_fails_before_generation(self):
        for missing in ('local-research.md', 'local-research-writing.md', 'local-research-audio.md'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'prompts').mkdir()
                for name in ('local-research.md', 'local-research-writing.md', 'local-research-audio.md'):
                    if name != missing:
                        (root / 'prompts' / name).write_text('Instructions', encoding='utf-8')
                with patch.object(pipeline, 'ROOT', root):
                    with self.assertRaisesRegex(ValueError, 'Missing instruction file'):
                        pipeline.research_prompt('2026-10-19')


if __name__ == '__main__':
    unittest.main()
