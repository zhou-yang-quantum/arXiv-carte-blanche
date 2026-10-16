import base64
import json
import unittest
import urllib.error
from unittest.mock import patch
from tools.publish_digest import publish, check_date
from tools.speech_text import make_script
from tools.import_digest import parse_digest
from tools.project import WEBSITE
from test_archive import example_digest


class PublisherTests(unittest.TestCase):
    @patch('tools.publish_digest.git_request')
    @patch('tools.publish_digest.api_request', return_value=None)
    def test_text_and_speech_are_published_in_one_protected_commit(self, api, git):
        text = example_digest(include_priority=False)
        script = make_script(parse_digest(text), [], phrase_groups=[['A useful concept']])
        git.side_effect = [{'object': {'sha': 'base'}}, {'tree': {'sha': 'base-tree'}},
                           {'sha': 'new-tree'}, {'sha': 'new-commit'}, {'object': {'sha': 'new-commit'}}]
        result = publish(text, 'test-credential', speech_script=script)
        self.assertEqual(result['commit'], 'new-commit')
        self.assertEqual(result['website'], WEBSITE + '#date=2026-10-06')
        tree = git.call_args_list[2].args[3]
        self.assertEqual({entry['path'] for entry in tree['tree']}, {'incoming/2026-10-06.md', 'audio/scripts/2026-10-06.json'})
        self.assertEqual(tree['base_tree'], 'base-tree')
        speech = next(entry for entry in tree['tree'] if entry['path'].startswith('audio/scripts/'))
        self.assertEqual(json.loads(speech['content'])['phrase_groups'], [['A useful concept']])
        self.assertEqual(git.call_args_list[3].args[3]['parents'], ['base'])
        self.assertEqual(git.call_args_list[4].args[3], {'sha': 'new-commit', 'force': False})
        self.assertEqual([call.args[0] for call in api.call_args_list], ['GET', 'GET'])

    @patch('tools.publish_digest.api_request')
    def test_stale_speech_never_reaches_github(self, api):
        text = example_digest(include_priority=False)
        script = make_script(parse_digest(text), [])
        script['source_hash'] = 'stale'
        with self.assertRaises(ValueError):
            publish(text, 'test-credential', speech_script=script)
        api.assert_not_called()

    @patch('tools.publish_digest.git_request')
    @patch('tools.publish_digest.api_request', return_value=None)
    def test_branch_race_rebuilds_against_new_parent_without_force(self, api, git):
        text = example_digest(include_priority=False)
        script = make_script(parse_digest(text), [])
        git.side_effect = [
            {'object': {'sha': 'first'}}, {'tree': {'sha': 'tree-first'}}, {'sha': 'tree-one'}, {'sha': 'commit-one'},
            urllib.error.HTTPError('https://api.github.com', 422, 'branch moved', {}, None),
            {'object': {'sha': 'second'}}, {'tree': {'sha': 'tree-second'}}, {'sha': 'tree-two'}, {'sha': 'commit-two'}, {}]
        result = publish(text, 'test-credential', speech_script=script)
        self.assertEqual(result['commit'], 'commit-two')
        self.assertEqual(git.call_args_list[8].args[3]['parents'], ['second'])
        self.assertEqual(git.call_args_list[9].args[3]['force'], False)

    @patch('tools.publish_digest.api_request')
    def test_uploads_only_the_dated_markdown_to_main(self, api):
        api.side_effect = [None, {'commit': {'sha': 'a' * 40}}]
        text = example_digest()
        result = publish(text, 'test-credential')
        self.assertEqual(result['status'], 'publication-queued')
        self.assertEqual(result['website'], WEBSITE + '#date=2026-10-06')
        method, date, _, payload = api.call_args.args
        self.assertEqual((method, date, payload['branch']), ('PUT', '2026-10-06', 'main'))
        self.assertEqual(base64.b64decode(payload['content']).decode('utf-8'), text)
        self.assertNotIn('sha', payload)

    @patch('tools.publish_digest.api_request')
    def test_identical_redelivery_does_not_write(self, api):
        text = example_digest()
        api.return_value = {'encoding': 'base64', 'content': base64.b64encode(text.encode()).decode()}
        self.assertEqual(publish(text, 'test-credential')['status'], 'already-delivered')
        self.assertEqual(api.call_count, 1)

    @patch('tools.publish_digest.api_request')
    def test_refuses_to_overwrite_a_date(self, api):
        api.return_value = {'encoding': 'base64', 'content': base64.b64encode(b'Old content').decode()}
        with self.assertRaises(ValueError):
            publish(example_digest(), 'test-credential')
        self.assertEqual(api.call_count, 1)

    @patch('tools.publish_digest.api_request')
    def test_invalid_digest_never_reaches_github(self, api):
        with self.assertRaises(ValueError):
            publish('# arXiv-2026-10-06\nIncomplete', 'test-credential')
        api.assert_not_called()

    @patch('tools.publish_digest.api_request')
    def test_reports_actual_paper_count_on_delivery_and_redelivery(self, api):
        text = example_digest(20, include_priority=False)
        api.side_effect = [None, {'commit': {'sha': 'a' * 40}}]
        self.assertEqual(publish(text, 'test-credential')['papers'], 20)
        api.side_effect = None
        api.return_value = {'encoding': 'base64', 'content': base64.b64encode(text.encode()).decode()}
        self.assertEqual(publish(text, 'test-credential')['papers'], 20)
        self.assertEqual(api.call_count, 3)

    @patch('tools.publish_digest.api_request')
    def test_out_of_range_counts_never_reach_github(self, api):
        for count in (9, 21):
            with self.subTest(count=count), self.assertRaises(ValueError):
                publish(example_digest(count, include_priority=False), 'test-credential')
        api.assert_not_called()

    @patch('tools.publish_digest.api_request')
    def test_date_check_does_not_return_digest_content(self, api):
        api.return_value = {'content': 'a large archived selection'}
        self.assertEqual(check_date('2026-10-06', 'test-credential'), {'date': '2026-10-06', 'status': 'exists'})


if __name__ == '__main__':
    unittest.main()
