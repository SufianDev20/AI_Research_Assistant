from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from Research_AI_Assistant.services.local_corpus_service import (
    LocalCorpusError,
    LocalCorpusService,
)

CFG = dict(RESEARCH_API_URL="https://x.example/", RESEARCH_API_KEY="k")
POST = "Research_AI_Assistant.services.local_corpus_service.requests.post"


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


SRC = {"title": "T", "authors": "A One; B Two", "year": 2023,
       "filename": "t.pdf", "source": "J", "snippets": ["s1", "s2"],
       "relevant_pages": ["3"]}


@override_settings(**CFG)
class LocalCorpusTests(SimpleTestCase):
    @patch(POST)
    def test_maps_paper_shape_and_sends_bearer(self, post):
        post.return_value = _resp(body={"sources": [SRC], "confidence": {"label": "High"}})
        out = LocalCorpusService().search("q", 25)
        paper = out["papers"][0]
        self.assertEqual(paper["authors"][1]["name"], "B Two")
        self.assertEqual(paper["abstract"], "s1 s2")
        self.assertEqual(paper["publication_year"], 2023)
        self.assertEqual(paper["openalex_id"], "local:t.pdf")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://x.example/retrieve")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k")
        self.assertEqual(kwargs["json"]["max_papers"], 10)
        self.assertEqual(kwargs["timeout"], (6, 30))

    @patch(POST)
    def test_empty_year_becomes_none(self, post):
        post.return_value = _resp(body={"sources": [dict(SRC, year="")], "confidence": {}})
        self.assertIsNone(LocalCorpusService().search("q")["papers"][0]["publication_year"])

    @patch(POST)
    def test_fallback_on_zero_papers(self, post):
        post.return_value = _resp(body={"sources": [], "confidence": {"label": "Low"}})
        self.assertFalse(LocalCorpusService.is_sufficient(LocalCorpusService().search("q")))

    @patch(POST)
    def test_fallback_on_low_confidence(self, post):
        post.return_value = _resp(body={"sources": [SRC], "confidence": {"label": "Low"}})
        self.assertFalse(LocalCorpusService.is_sufficient(LocalCorpusService().search("q")))

    @patch(POST)
    def test_moderate_is_accepted(self, post):
        post.return_value = _resp(body={"sources": [SRC], "confidence": {"label": "Moderate"}})
        self.assertTrue(LocalCorpusService.is_sufficient(LocalCorpusService().search("q")))

    @patch(POST)
    def test_401_raises(self, post):
        post.return_value = _resp(401)
        with self.assertRaises(LocalCorpusError):
            LocalCorpusService().search("q")

    @patch(POST, side_effect=requests.ConnectTimeout())
    def test_timeout_raises(self, post):
        with self.assertRaises(LocalCorpusError):
            LocalCorpusService().search("q")

    @patch(POST)
    def test_bad_payload_raises(self, post):
        post.return_value = _resp(body={"nope": 1})
        with self.assertRaises(LocalCorpusError):
            LocalCorpusService().search("q")

    @override_settings(RESEARCH_API_URL="", RESEARCH_API_KEY="")
    def test_disabled_when_unset(self):
        svc = LocalCorpusService()
        self.assertFalse(svc.enabled)
        with self.assertRaises(LocalCorpusError):
            svc.search("q")

    @patch(POST)
    def test_null_sources_raises_local_corpus_error(self, post):
        post.return_value = _resp(body={"sources": None, "confidence": {"label": "High"}})
        with self.assertRaises(LocalCorpusError):
            LocalCorpusService().search("q")

    @patch(POST)
    def test_non_dict_source_item_raises_local_corpus_error(self, post):
        post.return_value = _resp(body={"sources": ["not-a-dict"], "confidence": {"label": "High"}})
        with self.assertRaises(LocalCorpusError):
            LocalCorpusService().search("q")

    @patch(POST)
    def test_non_dict_confidence_does_not_crash_is_sufficient(self, post):
        post.return_value = _resp(body={"sources": [SRC], "confidence": "High"})
        result = LocalCorpusService().search("q")
        self.assertTrue(LocalCorpusService.is_sufficient(result))
