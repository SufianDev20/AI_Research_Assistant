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

from Research_AI_Assistant.services.pdf_service import (
    MAX_PDF_BYTES,
    PDFExtractionError,
    PDFService,
    fetch_pdf_bytes,
)
from Research_AI_Assistant.services.qa_llm import (
    QACompletionError,
    QACompletionService,
    build_qa_user_message,
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
        ), patch.dict(sys.modules, {"pymupdf4llm": pdf_backend}):
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
        ), patch.dict(sys.modules, {"pymupdf4llm": pdf_backend}):
            with self.assertRaisesRegex(QAChunkError, "no usable text chunks"):
                QAChunkService.fetch_and_chunk("https://example.test/a.pdf", "W1")

    def test_build_context_orders_chunks_and_uses_fallback_token_estimate(self):
        chunks = QAContextService.build_context(
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


if __name__ == "__main__":
    unittest.main()
