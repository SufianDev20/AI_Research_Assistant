"""
Persistent cache for Multi-Paper Q&A chunks.

Without this, every follow-up question re-downloads each paper's PDF and
re-runs PyMuPDF4LLM (and OCR, which dominates the cost) to produce chunks
that are byte-for-byte identical to the previous question's. Chunking is
deterministic given the PDF bytes, so the result is safe to reuse across
questions and across users.

Kept out of qa_pipeline.py deliberately: that module stays free of database
access so Test/test_qa_services.py can exercise it offline.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Union

from django.utils import timezone

from ..models import PaperPDF
from .qa_pipeline import QAChunkError, QAChunkService

logger = logging.getLogger(__name__)

# Bump when the chunking logic changes shape (page tagging, token sizing,
# split boundaries) so stale cached chunks are discarded rather than served.
CHUNK_SCHEMA_VERSION = 1

# A paper the publisher blocks fails the same way for every user, and each
# attempt costs a full fetch timeout. Remember the failure briefly so repeat
# questions fail instantly with the same reason.
CHUNK_FAILURE_COOLDOWN_MIN = 15


class QAChunkCache:
    """Read-through cache over QAChunkService.fetch_and_chunk."""

    @staticmethod
    def get_or_chunk(pdf_url: Union[str, List[str]], openalex_id: str) -> Dict:
        """
        Return page-tagged chunks for a paper, fetching only if needed.

        Args:
            pdf_url: A direct PDF URL or an ordered list of candidates, as
                accepted by QAChunkService.fetch_and_chunk.
            openalex_id: OpenAlex work ID; the sole cache key. Not keyed on
                the URL, because the caller sends a candidate list and which
                candidate succeeds varies between requests.

        Returns:
            The same dict shape as QAChunkService.fetch_and_chunk:
            {"chunks": [...], "page_count": int, "error": None}.

        Raises:
            QAChunkError: If the PDF cannot be fetched or chunked, or if a
                recent attempt failed and is still within the cooldown.
                Callers must catch this per-paper so one bad paper does not
                stop Q&A for the rest of the selected set.
        """
        record = PaperPDF.objects.filter(openalex_id=openalex_id).first()

        if record:
            if record.qa_chunk_version == CHUNK_SCHEMA_VERSION and record.qa_chunks:
                logger.info(
                    "Q&A chunk cache hit for %s (%d chunks, no fetch).",
                    openalex_id,
                    len(record.qa_chunks),
                )
                return {
                    "chunks": record.qa_chunks,
                    "page_count": record.page_count or 0,
                    "error": None,
                }

            if QAChunkCache._in_failure_cooldown(record):
                logger.info(
                    "Q&A chunk cache: recent failure for %s, not retrying yet.",
                    openalex_id,
                )
                raise QAChunkError(record.qa_error)

        try:
            result = QAChunkService.fetch_and_chunk(pdf_url, openalex_id)
        except QAChunkError as exc:
            QAChunkCache._record_failure(openalex_id, pdf_url, str(exc))
            raise

        QAChunkCache._record_success(openalex_id, pdf_url, result)
        return result

    @staticmethod
    def _in_failure_cooldown(record: PaperPDF) -> bool:
        if not record.qa_error or not record.qa_last_attempt_at:
            return False
        cutoff = timezone.now() - timedelta(minutes=CHUNK_FAILURE_COOLDOWN_MIN)
        return record.qa_last_attempt_at > cutoff

    @staticmethod
    def _first_url(pdf_url: Union[str, List[str]]) -> str:
        """The URL to store when the winning candidate isn't reported back."""
        if isinstance(pdf_url, str):
            return pdf_url[:500]
        return (pdf_url[0] if pdf_url else "")[:500]

    @staticmethod
    def _record_success(
        openalex_id: str, pdf_url: Union[str, List[str]], result: Dict
    ) -> None:
        # markdown_content and pdf_url are non-null on PaperPDF, so a row
        # created from the Q&A path (which produces chunks, not markdown)
        # has to supply defaults for them.
        url = QAChunkCache._first_url(pdf_url)
        try:
            PaperPDF.objects.update_or_create(
                openalex_id=openalex_id,
                defaults={
                    "qa_chunks": result["chunks"],
                    "qa_chunk_version": CHUNK_SCHEMA_VERSION,
                    "qa_source_pdf_url": url,
                    "qa_error": "",
                    "qa_last_attempt_at": timezone.now(),
                    "page_count": result.get("page_count") or 0,
                },
                create_defaults={
                    "pdf_url": url,
                    "markdown_content": "",
                    "extraction_success": "pending",
                    "qa_chunks": result["chunks"],
                    "qa_chunk_version": CHUNK_SCHEMA_VERSION,
                    "qa_source_pdf_url": url,
                    "qa_last_attempt_at": timezone.now(),
                    "page_count": result.get("page_count") or 0,
                },
            )
        except Exception:
            # A cache write must never turn a successful answer into an error.
            logger.exception("Could not cache Q&A chunks for %s", openalex_id)

    @staticmethod
    def _record_failure(
        openalex_id: str, pdf_url: Union[str, List[str]], reason: str
    ) -> None:
        url = QAChunkCache._first_url(pdf_url)
        try:
            PaperPDF.objects.update_or_create(
                openalex_id=openalex_id,
                defaults={
                    "qa_error": reason,
                    "qa_last_attempt_at": timezone.now(),
                },
                create_defaults={
                    "pdf_url": url,
                    "markdown_content": "",
                    "extraction_success": "failed",
                    "qa_error": reason,
                    "qa_last_attempt_at": timezone.now(),
                },
            )
        except Exception:
            logger.exception("Could not cache Q&A failure for %s", openalex_id)
