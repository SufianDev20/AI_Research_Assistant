"""
End-to-end checks through the Django test client: local corpus first with an
OpenAlex fallback on /api/search/, and the Ollama -> OpenRouter chain on
/api/summarise/. All network calls are mocked.
"""
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

from Research_AI_Assistant.services.local_corpus_service import LocalCorpusError
from Research_AI_Assistant.services.openrouter_service import OpenRouterAPIError
from Research_AI_Assistant.tests import ClerkAuthTestMixin

CFG = dict(RESEARCH_API_URL="https://x.example", RESEARCH_API_KEY="k",
           LLM_TIMEOUT=(6, 240), LLM_NUM_CTX=8192, RESEARCH_TIMEOUT=(6, 30))
V = "Research_AI_Assistant.views"
SUMMARY = "Paper 1: T\nSummary text.\n\nReferences:\nA (2023) T."
LOCAL_SRC = {"title": "T", "authors": "A One; B Two", "year": 2023,
             "filename": "t.pdf", "source": "J", "snippets": ["s"],
             "relevant_pages": ["3"]}
OA_RESPONSE = {"results": [{"id": "https://openalex.org/W1", "title": "OA paper"}],
               "meta": {"count": 1, "next_cursor": None}}


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


@override_settings(**CFG)
class SearchFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def _get(self, **extra):
        params = {"q": "attention", "mode": "relevance", **extra}
        return self.client.get("/api/search/", params)

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post")
    def test_local_hit_skips_openalex(self, post, oa):
        post.return_value = _resp(body={"sources": [LOCAL_SRC],
                                        "confidence": {"label": "High"}})
        body = self._get().json()
        self.assertEqual(body["source"], "local")
        self.assertEqual(body["papers"][0]["title"], "T")
        self.assertEqual(body["papers"][0]["openalex_id"], "local:t.pdf")
        oa.assert_not_called()

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post")
    def test_zero_papers_falls_back(self, post, oa):
        post.return_value = _resp(body={"sources": [], "confidence": {"label": "Low"}})
        body = self._get().json()
        self.assertEqual(body["source"], "openalex")
        oa.assert_called_once()

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post")
    def test_low_confidence_falls_back(self, post, oa):
        post.return_value = _resp(body={"sources": [LOCAL_SRC],
                                        "confidence": {"label": "Low"}})
        self.assertEqual(self._get().json()["source"], "openalex")

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post",
           side_effect=requests.ConnectionError("tunnel down"))
    def test_tunnel_down_falls_back(self, post, oa):
        self.assertEqual(self._get().json()["source"], "openalex")

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post")
    def test_expired_token_falls_back(self, post, oa):
        post.return_value = _resp(401)
        self.assertEqual(self._get().json()["source"], "openalex")

    @override_settings(RESEARCH_API_URL="", RESEARCH_API_KEY="")
    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    def test_unconfigured_goes_straight_to_openalex(self, oa):
        self.assertEqual(self._get().json()["source"], "openalex")

    @patch(f"{V}.openalex_service.search_papers", return_value=OA_RESPONSE)
    @patch("Research_AI_Assistant.services.local_corpus_service.requests.post")
    def test_open_access_mode_skips_local(self, post, oa):
        # Default mode in the view is "open_access"; the local server cannot
        # honour that filter, so OpenAlex answers.
        self.assertEqual(self._get(mode="open_access").json()["source"], "openalex")
        post.assert_not_called()


@override_settings(**CFG)
class SummariseChainTests(ClerkAuthTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def _post(self):
        return self.client.post(
            "/api/summarise/",
            data={"query": "attention", "papers": [{"title": "T", "abstract": "a"}]},
            content_type="application/json",
        )

    @override_settings(LLM_BACKEND="ollama")
    @patch("Research_AI_Assistant.services.ollama_service.time.sleep")
    @patch("Research_AI_Assistant.services.ollama_service.requests.get")
    @patch("Research_AI_Assistant.services.ollama_service.requests.post")
    def test_ollama_only_success(self, post, get, _sleep):
        post.return_value = _resp(202, {"job_id": "j1"})
        get.return_value = _resp(body={"status": "completed", "result": {"content": SUMMARY}})
        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["summary"].startswith("Paper 1:"))

    @override_settings(LLM_BACKEND="ollama")
    @patch("Research_AI_Assistant.services.ollama_service.requests.post",
           side_effect=requests.ConnectionError("down"))
    def test_ollama_only_failure_returns_503(self, post):
        r = self._post()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error_code"], "LLM_API_ERROR")

    @override_settings(LLM_BACKEND="ollama_then_openrouter")
    @patch("Research_AI_Assistant.services.llm_service._make_openrouter")
    @patch("Research_AI_Assistant.services.ollama_service.requests.post",
           side_effect=requests.ConnectionError("down"))
    def test_ollama_down_uses_openrouter(self, post, make_or):
        make_or.return_value.complete.return_value = SUMMARY
        r = self._post()
        self.assertEqual(r.status_code, 200)
        make_or.return_value.complete.assert_called_once()

    @override_settings(LLM_BACKEND="ollama_then_openrouter")
    @patch("Research_AI_Assistant.services.llm_service._make_openrouter",
           side_effect=OpenRouterAPIError("OPENROUTER_API_KEY is not set"))
    @patch("Research_AI_Assistant.services.ollama_service.requests.post",
           side_effect=requests.ConnectionError("down"))
    def test_both_down_returns_503_not_500(self, post, make_or):
        self.assertEqual(self._post().status_code, 503)

    @override_settings(LLM_BACKEND="ollama_then_openrouter")
    @patch("Research_AI_Assistant.services.llm_service._make_openrouter")
    @patch("Research_AI_Assistant.services.ollama_service.time.sleep")
    @patch("Research_AI_Assistant.services.ollama_service.requests.get")
    @patch("Research_AI_Assistant.services.ollama_service.requests.post")
    def test_ollama_ok_never_touches_openrouter(self, post, get, _sleep, make_or):
        post.return_value = _resp(202, {"job_id": "j1"})
        get.return_value = _resp(body={"status": "completed", "result": {"content": SUMMARY}})
        self.assertEqual(self._post().status_code, 200)
        make_or.assert_not_called()
