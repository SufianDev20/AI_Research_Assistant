from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from Research_AI_Assistant.services.openalex_service import (
    MAX_ATTEMPTS,
    _get_with_retry,
)
import requests


def _http_error(status):
    response = MagicMock()
    response.status_code = status
    return requests.exceptions.HTTPError(response=response)


SLEEP = "Research_AI_Assistant.services.openalex_service.time.sleep"


class GetWithRetryTests(SimpleTestCase):
    @patch(SLEEP)
    def test_401_raises_immediately_without_sleeping(self, sleep):
        works_query = MagicMock()
        works_query.get.side_effect = _http_error(401)
        with self.assertRaises(requests.exceptions.HTTPError):
            _get_with_retry(works_query)
        self.assertEqual(works_query.get.call_count, 1)
        sleep.assert_not_called()

    @patch(SLEEP)
    def test_429_retries_and_succeeds(self, sleep):
        works_query = MagicMock()
        works_query.get.side_effect = [_http_error(429), ("results", {"meta": 1})]
        result = _get_with_retry(works_query)
        self.assertEqual(result, ("results", {"meta": 1}))
        self.assertEqual(works_query.get.call_count, 2)

    @patch(SLEEP)
    def test_429_exhausts_max_attempts(self, sleep):
        works_query = MagicMock()
        works_query.get.side_effect = _http_error(429)
        with self.assertRaises(requests.exceptions.HTTPError):
            _get_with_retry(works_query)
        self.assertEqual(works_query.get.call_count, MAX_ATTEMPTS)
