"""Offline unit tests for the Q&A LLM and paper-context services."""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django
from django.test import override_settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Research_Assistant.settings")
django.setup()

from Research_AI_Assistant.serializers import QARequestSerializer
from Research_AI_Assistant.services.extract_service import ExtractionService
from Research_AI_Assistant.services.pdf_service import (
    MAX_PDF_BYTES,
    PDFExtractionError,
    PDFService,
    fetch_pdf_bytes,
)
from Research_AI_Assistant.services.qa_llm import (
    QACompletionError,
    QACompletionService,
    build_paper_legend,
    build_qa_user_message,
    paper_label,
)
from Research_AI_Assistant.services.qa_pipeline import (
    QAChunkError,
    QAChunkService,
    QAContextError,
    QAContextService,
    QACitationValidator,
)


class TestQALlm(unittest.TestCase):
    def test_build_user_message_includes_non_empty_chunks_and_question(self):
        chunks = [
            {"paper_id": "W1", "page": 2, "text": "  First finding.  "},
            {"paper_id": "W2", "page": 4, "text": ""},
        ]

        message = build_qa_user_message(chunks, "  What did the papers find? ")

        self.assertIn("[W1, Page 2]: First finding.", message)
        self.assertNotIn("[W2, Page 4]", message)
        self.assertIn('Question: "What did the papers find?"', message)

    def test_build_user_message_rejects_missing_source_or_question(self):
        with self.assertRaises(ValueError):
            build_qa_user_message([], "A question")

        with self.assertRaises(ValueError):
            build_qa_user_message([{"text": "source"}], "   ")

    def test_ask_sends_qa_request_and_parses_json(self):
        openrouter = MagicMock()
        openrouter.complete.return_value = (
            '{"answer":"Supported answer",'
            '"citations":[{"paper_id":"W1","page":2,'
            '"quoted_snippet":"Supported"}]}'
        )

        result = QACompletionService.ask(
            openrouter,
            [{"paper_id": "W1", "page": 2, "text": "Supported evidence."}],
            "What is supported?",
        )

        self.assertEqual(result["answer"], "Supported answer")
        self.assertEqual(result["citations"][0]["paper_id"], "W1")
        call = openrouter.complete.call_args.kwargs
        self.assertEqual(call["request_type"], "qa")
        self.assertEqual(call["temperature"], 0.1)
        self.assertEqual(call["max_tokens"], 800)

    def test_paper_label_formats_one_two_and_many_authors(self):
        self.assertEqual(paper_label({"authors": ["Ann Smith"]}, "Paper 1"), "Smith")
        self.assertEqual(
            paper_label({"authors": ["Ann Smith", "Bo Jones"]}, "Paper 1"),
            "Smith and Jones",
        )
        self.assertEqual(
            paper_label({"authors": ["Ann Smith", "Bo Jones", "Cy Lee"]}, "Paper 1"),
            "Smith, Jones et al.",
        )
        self.assertEqual(paper_label({"title": "A Title"}, "Paper 1"), "A Title")
        self.assertEqual(paper_label({}, "Paper 1"), "Paper 1")

    def test_ask_with_legend_uses_aliases_and_maps_back_to_real_ids(self):
        url_a, url_b = "https://openalex.org/W1", "https://openalex.org/W2"
        _, legend = build_paper_legend(
            {
                url_a: {"title": "Alpha", "authors": ["Ann Smith"], "year": 2020},
                url_b: {"title": "Beta", "authors": ["Bo Jones", "Cy Lee", "Di Wu"]},
            },
            [url_b, url_a],
        )
        chunks = [
            {"paper_id": url_a, "page": 3, "text": "Alpha text."},
            {"paper_id": url_b, "page": 1, "text": "Beta text."},
        ]

        message = build_qa_user_message(chunks, "Q?", legend)
        self.assertIn("[P1, Page 3]: Alpha text.", message)
        self.assertIn("[P2, Page 1]: Beta text.", message)
        self.assertIn("label: Smith", message)
        self.assertIn("label: Jones, Lee et al.", message)
        self.assertNotIn("openalex.org", message)

        openrouter = MagicMock()
        openrouter.complete.return_value = (
            '{"answer":"The paper Smith says x.",'
            '"citations":[{"paper_id":"P1","page":"3","quoted_snippet":"Alpha"}]}'
        )
        result = QACompletionService.ask(openrouter, chunks, "Q?", legend)
        self.assertEqual(result["citations"][0]["paper_id"], url_a)

        validated = QACitationValidator.validate_citations(result["citations"], chunks)
        self.assertTrue(validated[0]["page_exists"])
        self.assertTrue(validated[0]["text_verified"])
        self.assertEqual(validated[0]["page"], 3)

    def test_validate_citations_resolves_bare_openalex_token(self):
        chunks = [{"paper_id": "https://openalex.org/W9", "page": 2, "text": "Some text here."}]
        validated = QACitationValidator.validate_citations(
            [{"paper_id": "W9", "page": 2, "quoted_snippet": "Some text"}], chunks
        )
        self.assertTrue(validated[0]["page_exists"])
        self.assertEqual(validated[0]["paper_id"], "https://openalex.org/W9")

    def test_ask_wraps_completion_failures(self):
        openrouter = MagicMock()
        openrouter.complete.side_effect = RuntimeError("network down")

        with self.assertRaisesRegex(QACompletionError, "LLM completion failed"):
            QACompletionService.ask(
                openrouter,
                [{"paper_id": "W1", "page": 1, "text": "Evidence."}],
                "Question",
            )

    def test_parse_response_accepts_json_code_fence_and_drops_bad_citations(self):
        response = QACompletionService._parse_response(
            '```json\n{"answer": 42, "citations": [{"paper_id": "W1", '
            '"page": 1}, "not a citation"]}\n```'
        )

        self.assertEqual(
            response,
            {
                "answer": "42",
                "citations": [{"paper_id": "W1", "page": 1, "quoted_snippet": ""}],
            },
        )

    def test_parse_response_rejects_invalid_shape(self):
        with self.assertRaises(QACompletionError):
            QACompletionService._parse_response("not json")

        with self.assertRaisesRegex(QACompletionError, "citations.*not a list"):
            QACompletionService._parse_response('{"answer":"ok", "citations": {}}')


class TestQAPipeline(unittest.TestCase):
    def test_split_page_text_packs_paragraphs_and_keeps_short_page(self):
        short_page = QAChunkService._split_page_text("Short page text.")
        self.assertEqual(short_page, ["Short page text."])

        paragraphs = ["A" * 1200, "B" * 1200]
        chunks = QAChunkService._split_page_text("\n\n".join(paragraphs))
        self.assertEqual(chunks, paragraphs)

    def test_split_page_text_merges_short_chunk_into_previous_chunk(self):
        long_paragraph = "A" * 1200
        short_paragraph = "B" * 100

        chunks = QAChunkService._split_page_text(
            f"{long_paragraph}\n\n{short_paragraph}"
        )

        self.assertEqual(chunks, [f"{long_paragraph}\n\n{short_paragraph}"])

    def test_estimate_tokens_uses_four_chars_per_token_with_floor_of_one(self):
        self.assertEqual(QAChunkService._estimate_tokens("a" * 8), 2)
        self.assertEqual(QAChunkService._estimate_tokens("a" * 3), 1)

    def test_fetch_and_chunk_returns_page_tagged_chunks(self):
        pdf_backend = SimpleNamespace(
            to_markdown=MagicMock(
                return_value=[
                    {"metadata": {"page_number": 1}, "text": "Extracted page text."},
                    {"metadata": {"page_number": 2}, "text": "   "},
                ]
            )
        )

        with patch(
            "Research_AI_Assistant.services.qa_pipeline.fetch_pdf_bytes",
            return_value=b"pdf bytes",
        ), patch.dict(
            sys.modules,
            {"pymupdf4llm": pdf_backend, "pymupdf": SimpleNamespace(open=lambda **kw: MagicMock())},
        ):
            result = QAChunkService.fetch_and_chunk("https://example.test/a.pdf", "W1")

        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["error"], None)
        self.assertEqual(result["chunks"][0]["paper_id"], "W1")
        self.assertEqual(result["chunks"][0]["page"], 1)

    def test_fetch_and_chunk_rejects_missing_pdf_url(self):
        with self.assertRaises(QAChunkError):
            QAChunkService.fetch_and_chunk("", "W1")

    def test_fetch_and_chunk_rejects_missing_pdf_backend(self):
        with patch(
            "Research_AI_Assistant.services.qa_pipeline.fetch_pdf_bytes",
            return_value=b"pdf bytes",
        ), patch.dict(sys.modules, {"pymupdf4llm": None}):
            with self.assertRaisesRegex(QAChunkError, "No PDF Backend"):
                QAChunkService.fetch_and_chunk("https://example.test/a.pdf", "W1")

    def test_fetch_and_chunk_rejects_pages_without_usable_text(self):
        pdf_backend = SimpleNamespace(
            to_markdown=MagicMock(
                return_value=[
                    {"metadata": {"page_number": 1}, "text": ""},
                    {"metadata": {"page_number": 2}, "text": "   "},
                ]
            )
        )

        with patch(
            "Research_AI_Assistant.services.qa_pipeline.fetch_pdf_bytes",
            return_value=b"pdf bytes",
        ), patch.dict(
            sys.modules,
            {"pymupdf4llm": pdf_backend, "pymupdf": SimpleNamespace(open=lambda **kw: MagicMock())},
        ):
            with self.assertRaisesRegex(QAChunkError, "no usable text chunks"):
                QAChunkService.fetch_and_chunk("https://example.test/a.pdf", "W1")

    def test_build_context_orders_chunks_and_uses_fallback_token_estimate(self):
        chunks, _ = QAContextService.build_context(
            {
                "W2": [{"paper_id": "W2", "page": 3, "text": "third"}],
                "W1": [
                    {
                        "paper_id": "W1",
                        "page": 2,
                        "text": "second",
                        "token_estimate": 2,
                    },
                    {"paper_id": "W1", "page": 1, "text": "first", "token_estimate": 1},
                ],
            },
            max_context_tokens=2100,
        )

        self.assertEqual(
            [(chunk["paper_id"], chunk["page"]) for chunk in chunks],
            [("W1", 1), ("W1", 2), ("W2", 3)],
        )

    def test_build_context_rejects_empty_and_over_budget_context(self):
        with self.assertRaises(QAContextError):
            QAContextService.build_context({})

        with self.assertRaises(QAContextError):
            QAContextService.build_context(
                {"W1": [{"text": "evidence", "token_estimate": 101}]},
                max_context_tokens=2100,
            )

        with self.assertRaisesRegex(QAContextError, "too small"):
            QAContextService.build_context(
                {"W1": [{"text": "evidence", "token_estimate": 1}]},
                max_context_tokens=1999,
            )

    def test_build_context_trims_to_relevant_chunks_when_question_given(self):
        def chunk(paper, page, text):
            return {"paper_id": paper, "page": page, "text": text, "token_estimate": 1500}

        papers = {
            "W1": [
                chunk("W1", 1, "unrelated methods section"),
                chunk("W1", 2, "amyloid plaque symptoms of alzheimer disease"),
            ],
            "W2": [
                chunk("W2", 1, "budget tables"),
                chunk("W2", 2, "memory loss symptoms in alzheimer patients"),
            ],
        }
        chunks, stats = QAContextService.build_context(
            papers,
            max_context_tokens=5100,  # budget 3100 -> two 1500-token chunks
            question="What are the symptoms of alzheimer disease?",
        )

        self.assertTrue(stats["trimmed"])
        self.assertEqual([(c["paper_id"], c["page"]) for c in chunks], [("W1", 2), ("W2", 2)])
        self.assertEqual(stats["papers"]["W1"], {"total": 2, "used": 1})

        with self.assertRaises(QAContextError):
            QAContextService.build_context(papers, max_context_tokens=5100)

    def test_validate_citations_flags_page_and_snippet_independently(self):
        citations = QACitationValidator.validate_citations(
            [
                {"paper_id": "W1", "page": 1, "quoted_snippet": "Important finding"},
                {"paper_id": "W1", "page": 1, "quoted_snippet": "Wrong text"},
                {"paper_id": "W9", "page": 4, "quoted_snippet": "Important finding"},
            ],
            [
                {
                    "paper_id": "W1",
                    "page": 1,
                    "text": "An important finding appears here.",
                }
            ],
        )

        self.assertEqual(
            [(item["page_exists"], item["text_verified"]) for item in citations],
            [(True, True), (True, False), (False, False)],
        )

    def test_validate_citations_handles_empty_and_fuzzy_snippet(self):
        self.assertEqual(QACitationValidator.validate_citations([], []), [])
        self.assertTrue(
            QACitationValidator._snippet_overlaps(
                "methods improve results", "The method improves results significantly."
            )
        )

    def test_validate_citations_combines_text_from_chunks_on_same_page(self):
        validated = QACitationValidator.validate_citations(
            [{"paper_id": "W1", "page": 1, "quoted_snippet": "second chunk"}],
            [
                {"paper_id": "W1", "page": 1, "text": "first chunk"},
                {"paper_id": "W1", "page": 1, "text": "second chunk"},
            ],
        )

        self.assertTrue(validated[0]["page_exists"])
        self.assertTrue(validated[0]["text_verified"])


class TestPDFService(unittest.TestCase):
    def test_fetch_pdf_bytes_rejects_content_length_over_limit(self):
        response = MagicMock()
        response.headers = {"Content-Length": str(MAX_PDF_BYTES + 1)}
        response.content = b"small"

        with patch(
            "Research_AI_Assistant.services.pdf_service.requests.get",
            return_value=response,
        ):
            with self.assertRaisesRegex(PDFExtractionError, "too large"):
                fetch_pdf_bytes("https://example.test/a.pdf", "W1")

    def test_fetch_pdf_bytes_rejects_download_over_limit(self):
        response = MagicMock()
        response.headers = {"Content-Length": "0"}
        response.content = b"x" * (MAX_PDF_BYTES + 1)

        with patch(
            "Research_AI_Assistant.services.pdf_service.requests.get",
            return_value=response,
        ):
            with self.assertRaisesRegex(PDFExtractionError, "exceeds 50MB"):
                fetch_pdf_bytes("https://example.test/a.pdf", "W1")

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_fetch_and_extract_returns_markdown_and_page_metadata(self):
        pdf_backend = SimpleNamespace(
            to_markdown=MagicMock(return_value="Extracted markdown")
        )
        fitz_backend = SimpleNamespace(
            open=MagicMock(
                return_value=SimpleNamespace(page_count=3, close=MagicMock())
            )
        )

        with patch(
            "Research_AI_Assistant.services.pdf_service.fetch_pdf_bytes",
            return_value=b"pdf bytes",
        ), patch.dict(
            sys.modules,
            {"pymupdf4llm": pdf_backend, "fitz": fitz_backend},
        ):
            result = PDFService.fetch_and_extract(
                "https://example.test/a.pdf", "https://openalex.org/W1"
            )

        self.assertEqual(result["markdown"], "Extracted markdown")
        self.assertEqual(result["page_count"], 3)
        self.assertEqual(result["image_paths"], [])
        self.assertIsNone(result["error"])


SPRINGER = "https://link.springer.com/content/pdf/x.pdf"
REPO = "https://repo.example.edu/files/x.pdf"


def _loc(pdf_url=None, is_oa=True):
    return {"pdf_url": pdf_url, "landing_page_url": "https://l.example/x", "is_oa": is_oa}


class TestPDFCandidates(unittest.TestCase):
    def test_single_pdf_url_is_unchanged(self):
        work = {"best_oa_location": _loc(SPRINGER), "locations": [_loc(SPRINGER)]}
        self.assertEqual(ExtractionService._collect_pdf_candidates(work), [SPRINGER])
        meta = ExtractionService.extract_metadata(work)
        self.assertEqual(meta["pdf_url"], SPRINGER)
        self.assertEqual(meta["pdf_candidates"], [SPRINGER])
        self.assertTrue(meta["has_pdf_link"])

    def test_non_blocked_copy_is_ordered_before_blocked_publisher(self):
        work = {
            "best_oa_location": _loc(SPRINGER),
            "locations": [_loc(SPRINGER), _loc(REPO)],
        }
        self.assertEqual(
            ExtractionService._collect_pdf_candidates(work), [REPO, SPRINGER]
        )
        self.assertEqual(ExtractionService.extract_metadata(work)["pdf_url"], REPO)

    def test_original_pick_is_kept_when_cap_applies(self):
        others = [f"https://r{i}.example.edu/x.pdf" for i in range(5)]
        work = {
            "best_oa_location": _loc(SPRINGER),
            "locations": [_loc(SPRINGER)] + [_loc(u) for u in others],
        }
        candidates = ExtractionService._collect_pdf_candidates(work)
        self.assertLessEqual(len(candidates), 3)
        self.assertIn(SPRINGER, candidates)

    def test_no_pdf_url_gives_empty_list(self):
        work = {"best_oa_location": _loc(None), "locations": [_loc(None)]}
        self.assertEqual(ExtractionService._collect_pdf_candidates(work), [])
        meta = ExtractionService.extract_metadata(work)
        self.assertIsNone(meta["pdf_url"])
        self.assertFalse(meta["has_pdf_link"])


class TestChunkCandidateFallback(unittest.TestCase):
    def _backend(self):
        return SimpleNamespace(
            to_markdown=MagicMock(
                return_value=[{"metadata": {"page_number": 1}, "text": "Page text."}]
            )
        )

    def test_blocked_first_candidate_falls_through_to_second(self):
        fetch = MagicMock(
            side_effect=[PDFExtractionError("403 Forbidden: blocked"), b"%PDF ok"]
        )
        with patch(
            "Research_AI_Assistant.services.qa_pipeline.fetch_pdf_bytes", fetch
        ), patch.dict(
            sys.modules,
            {"pymupdf4llm": self._backend(), "pymupdf": SimpleNamespace(open=lambda **kw: MagicMock())},
        ):
            result = QAChunkService.fetch_and_chunk([SPRINGER, REPO], "W1")
        self.assertEqual(result["chunks"][0]["page"], 1)
        self.assertEqual([c.args[0] for c in fetch.call_args_list], [SPRINGER, REPO])

    def test_all_candidates_failing_reports_reasons(self):
        fetch = MagicMock(side_effect=PDFExtractionError("403 Forbidden: blocked"))
        with patch("Research_AI_Assistant.services.qa_pipeline.fetch_pdf_bytes", fetch):
            with self.assertRaisesRegex(QAChunkError, "403 Forbidden"):
                QAChunkService.fetch_and_chunk([SPRINGER, REPO], "W1")

    def test_empty_candidate_list_is_rejected(self):
        with self.assertRaises(QAChunkError):
            QAChunkService.fetch_and_chunk([], "W1")


class TestQARequestSerializerCandidates(unittest.TestCase):
    def _validate(self, pdf_urls):
        s = QARequestSerializer(
            data={"paper_ids": ["W1"], "question": "q?", "pdf_urls": pdf_urls}
        )
        return s, s.is_valid()

    def test_string_value_is_normalised_to_list(self):
        s, ok = self._validate({"W1": SPRINGER})
        self.assertTrue(ok, s.errors)
        self.assertEqual(s.validated_data["pdf_urls"]["W1"], [SPRINGER])

    def test_list_value_is_accepted(self):
        s, ok = self._validate({"W1": [SPRINGER, REPO]})
        self.assertTrue(ok, s.errors)
        self.assertEqual(s.validated_data["pdf_urls"]["W1"], [SPRINGER, REPO])

    def test_more_than_three_candidates_rejected(self):
        _, ok = self._validate({"W1": [REPO] * 4})
        self.assertFalse(ok)

    def test_overlong_url_rejected(self):
        _, ok = self._validate({"W1": ["https://e.example/" + "a" * 500]})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
