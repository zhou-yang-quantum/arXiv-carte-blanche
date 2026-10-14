import io
import itertools
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import call, patch

from tools import collect_arxiv as collector

URL = 'https://arxiv.org/list/quant-ph/pastweek?show=2000&skip=0'


class CollectorHTTPTests(unittest.TestCase):
    def setUp(self):
        for replacement in (patch.object(collector, '_next_request_at', 0),
                            patch.object(collector.time, 'monotonic', side_effect=itertools.count(100, 10)),
                            patch.object(collector.sys, 'stderr', io.StringIO())):
            replacement.start()
            self.addCleanup(replacement.stop)

    def error(self, code, headers=None):
        return urllib.error.HTTPError(URL, code, 'Service error', headers or {}, None)

    def test_429_honors_retry_after_then_recovers(self):
        with patch.object(collector.urllib.request, 'urlopen', side_effect=[self.error(429, {'Retry-After': '90'}), io.BytesIO(b'verified listing')]) as request, patch.object(collector.time, 'sleep') as sleep:
            self.assertEqual(collector.fetch_text(URL), 'verified listing')
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(90)

    def test_429_without_header_has_long_backoff_and_bounded_attempts(self):
        with patch.object(collector.urllib.request, 'urlopen', side_effect=self.error(429)) as request, patch.object(collector.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'arxiv.org/list/quant-ph/pastweek: HTTP 429'):
                collector.fetch_text(URL)
        self.assertEqual(request.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(60), call(120), call(240)])

    def test_http_date_retry_after_is_respected(self):
        with patch.object(collector, 'datetime') as clock, patch.object(collector.urllib.request, 'urlopen', side_effect=[self.error(503, {'Retry-After': 'Wed, 14 Oct 2026 12:02:00 GMT'}), io.BytesIO(b'ok')]), patch.object(collector.time, 'sleep') as sleep:
            clock.now.return_value = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
            self.assertEqual(collector.fetch_text(URL), 'ok')
        sleep.assert_called_once_with(120)

    def test_long_server_cooldown_stops_instead_of_retrying_too_soon(self):
        with patch.object(collector.urllib.request, 'urlopen', side_effect=self.error(429, {'Retry-After': '600'})) as request, patch.object(collector.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'server requested a 600-second wait'):
                collector.fetch_text(URL)
        request.assert_called_once()
        sleep.assert_not_called()

    def test_permanent_http_error_is_not_retried_or_treated_as_empty(self):
        with patch.object(collector.urllib.request, 'urlopen', side_effect=self.error(404)) as request, patch.object(collector.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 404; archive remains incomplete'):
                collector.fetch_text(URL)
        request.assert_called_once()
        sleep.assert_not_called()

    def test_invalid_header_falls_back_to_transient_error_backoff(self):
        with patch.object(collector.urllib.request, 'urlopen', side_effect=[self.error(500, {'Retry-After': 'invalid'}), io.BytesIO(b'ok')]), patch.object(collector.time, 'sleep') as sleep:
            self.assertEqual(collector.fetch_text(URL), 'ok')
        sleep.assert_called_once_with(10)

    def test_successful_requests_are_paced_across_endpoint_transitions(self):
        with patch.object(collector.time, 'monotonic', side_effect=[0, 0, 1, 3]), patch.object(collector.urllib.request, 'urlopen', side_effect=[io.BytesIO(b'listing'), io.BytesIO(b'metadata')]), patch.object(collector.time, 'sleep') as sleep:
            collector.fetch_text(URL)
            collector.fetch_text('https://export.arxiv.org/api/query?id_list=2610.00001v1')
        sleep.assert_called_once_with(2)


if __name__ == '__main__':
    unittest.main()
