"""
Q&A data pipeline for Multi-Paper Q&A.

This module contains everything that touches paper data before and after
the LLM call:

    - PDF fetching and page-aware chunking
    - Context assembly and context-window validation
    - Citation validation

The LLM-specific code remains in qa_llm.py.
"""

import logging, re, os, tempfile
from difflib import SequenceMatcher
from typing import Dict, List

from .pdf_service import PDFExtractionError, fetch_pdf_bytes

# Configurations / Constants
MIN_CHUNK_TOKENS = 300
MAX_CHUNK_TOKENS = 500
CHARS_PER_TOKEN = 4
DEFAULT_CONTEXT_WINDOW_TOKENS = 8000
RESERVED_TOKENS = 2000
FUZZY_MATCH_THRESHOLD = 0.6

# Logging
logger = logging.getLogger(__name__)


class QAChunkError(Exception):
    """
    Raised when a paper's PDF cannot be fetched or chunked for Q&A
    """

    pass


class QAChunkService:
    """
    Fetch a PDF and produce page-tagged chunks for the Q&A context builder.
    """

    @staticmethod
    def fetch_and_chunk(pdf_url: str, openalex_id: str) -> Dict:
        """
          Fetch a PDF and split it into page tagged

        Args:
            pdf_url (str): Direct PDF URL
            openalex_id (str): OpenAlex Work ID used only for logging and error messages.

        Returns:
            Dict: "chunks": List[Dict] - each item has
                    "paper_id": str (openalex_id),
                    "page": int (1-based page number),
                    "text": str (chunk text),
                    "token_estimate": int,
                "page_count": int,
                "error": Optional[str]
        Raises:
            QAChunkError: If the PDF cannot be fetched or has no extractable
            text. Callers must catch this per-paper so one bad paper does
            not stop Q&A for the rest of the selected set.
        """
        if not pdf_url:
            raise QAChunkError(
                f"No direct pdf_url available for {openalex_id} cannot chunk a page for citation without a fetchable PDF."
            )
        try:
            pdf_bytes = fetch_pdf_bytes(pdf_url, openalex_id)
        except PDFExtractionError as exc:
            raise QAChunkError(str(exc)) from exc
        try:
            import pymupdf4llm as pm4
        except ModuleNotFoundError as exc:
            raise QAChunkError(
                f"No PDF Backend available. Install `pymupdf4llm`"
            ) from exc
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            page_dicts = pm4.to_markdown(
                tmp_path, page_chunks=True, force_text=True, write_images=False
            )
            if not isinstance(page_dicts, list) or not page_dicts:
                raise QAChunkError(f"No pages extracted from PDF for {openalex_id}.")
            chunks: List[Dict] = []
            for page_dict in page_dicts:
                page_number = (
                    page_dict.get("metadata", {}).get("page_number")
                    if isinstance(page_dict, dict)
                    else None
                )

                page_text = (
                    page_dict.get("text", "") if isinstance(page_dict, dict) else ""
                )

                if not page_number or not page_text or not page_text.strip():
                    continue

                for sub_chunk in QAChunkService._split_page_text(page_text):
                    chunks.append(
                        {
                            "paper_id": openalex_id,
                            "page": page_number,
                            "text": sub_chunk,
                            "token_estimate": QAChunkService._estimate_tokens(
                                sub_chunk
                            ),
                        }
                    )

            if not chunks:
                raise QAChunkError(
                    f"PDF for {openalex_id} produced no usable text chunks."
                )

            return {
                "chunks": chunks,
                "page_count": len(page_dicts),
                "error": None,
            }

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Approximate token count using the ~4 chars/token heuristic."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    @staticmethod
    def _split_page_text(page_text: str) -> List[str]:
        """
        Split one page's markdown text into 300-500 token sub-chunks.

        Splits on paragraph boundaries first (double newline) to avoid
        cutting sentences mid-way, then greedily packs paragraphs into a
        chunk until the max token target is reached. A page shorter than
        MIN_CHUNK_TOKENS is still returned as a single chunk; citation
        granularity is by page, so a short chunk is not an error.
        """
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]

        if not paragraphs:
            return []

        max_chars = MAX_CHUNK_TOKENS * CHARS_PER_TOKEN

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for paragraph in paragraphs:
            paragraph_len = len(paragraph)

            if current and current_len + paragraph_len > max_chars:
                chunks.append("\n\n".join(current))
                current = [paragraph]
                current_len = paragraph_len
            else:
                current.append(paragraph)
                current_len += paragraph_len

        if current:
            chunks.append("\n\n".join(current))

        minimum_chars = MIN_CHUNK_TOKENS * CHARS_PER_TOKEN
        merged_chunks: List[str] = []
        for chunk in chunks:
            if merged_chunks and len(chunk) < minimum_chars:
                merged_chunks[-1] = f"{merged_chunks[-1]}\n\n{chunk}"
            else:
                merged_chunks.append(chunk)

        return merged_chunks


# Context Building
class QAContextError(Exception):
    """Raised when the assembled context cannot be safely sent to the LLM."""

    pass


class QAContextService:
    """Assemble page-tagged chunks into an ordered context, with a length guard."""

    @staticmethod
    def build_context(
        papers_chunks: Dict[str, List[Dict]],
        max_context_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS,
    ) -> List[Dict]:
        """
        Concatenate chunks from multiple papers in a stable order and verify
        the total fits inside the model's context window.

        Args:
            papers_chunks: Mapping of paper_id -> list of chunk dicts, where
                each chunk dict has keys "paper_id", "page", "text",
                "token_estimate" (the shape produced by
                QAChunkService.fetch_and_chunk()["chunks"]).
            max_context_tokens: The selected model's context window in
                tokens. Defaults to DEFAULT_CONTEXT_WINDOW_TOKENS when the
                caller does not know the model's real limit.

        Returns:
            A flat list of chunk dicts, ordered by paper_id then page number,
            ready to pass to qa_prompt_builder.build_qa_user_message().

        Raises:
            QAContextError: If no chunks are provided, or if the total
                estimated tokens exceed the available budget
                (max_context_tokens - RESERVED_TOKENS). The caller should
                surface this as a 413-style error to the client rather than
                silently truncating, since silent truncation could drop the
                page containing the answer.
        """
        if not papers_chunks:
            raise QAContextError("No paper chunks were provided to build context from.")

        ordered_chunks: List[Dict] = []

        for paper_id in sorted(papers_chunks.keys()):
            paper_chunk_list = papers_chunks[paper_id] or []

            ordered_chunks.extend(
                sorted(paper_chunk_list, key=lambda c: c.get("page", 0))
            )

        if not ordered_chunks:
            raise QAContextError(
                "All selected papers produced zero usable chunks; nothing to "
                "answer from."
            )

        total_tokens = sum(
            chunk.get("token_estimate")
            or QAContextService._estimate_tokens(chunk.get("text", ""))
            for chunk in ordered_chunks
        )

        budget = max_context_tokens - RESERVED_TOKENS

        if budget <= 0:
            raise QAContextError(
                f"max_context_tokens ({max_context_tokens}) is too small to "
                f"leave room for the system prompt and output "
                f"(reserve {RESERVED_TOKENS})."
            )

        if total_tokens > budget:
            raise QAContextError(
                f"Selected papers require ~{total_tokens} tokens of context, "
                f"which exceeds the available budget of {budget} tokens "
                f"(model window {max_context_tokens}, reserved "
                f"{RESERVED_TOKENS}). Select fewer papers or a model with "
                f"a larger context window."
            )

        logger.info(
            "Q&A context assembled: %d chunks, ~%d tokens (budget %d)",
            len(ordered_chunks),
            total_tokens,
            budget,
        )

        return ordered_chunks

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Fallback token estimate if a chunk is missing token_estimate."""
        return max(1, len(text) // CHARS_PER_TOKEN)


# Citation Validation
class QACitationValidator:
    """Validate LLM-returned citations against the actual source chunks."""

    @staticmethod
    def validate_citations(
        citations: List[Dict],
        context_chunks: List[Dict],
    ) -> List[Dict]:
        """
        Check each citation's page existence and snippet overlap.

        Args:
            citations: List of dicts as returned by the LLM, each expected
                to have "paper_id", "page", "quoted_snippet".
            context_chunks: The exact chunk list that was sent to the LLM
                (output of qa_context_service.build_context()), used as the
                ground truth for what pages/text actually exist.

        Returns:
            The same citations, each with two added keys:
                "page_exists": bool
                "text_verified": bool
            A citation is only safe to display as "verified" when both are
            True; the caller/frontend should treat anything else as
            unverified per the plan.

        Note:
            This function never raises for a single bad citation; a
            malformed or unverifiable citation is flagged, not fatal to the
            rest of the response.
        """
        if not citations:
            return []

        # Build a lookup of (paper_id, page) -> concatenated page text so multiple chunks belonging to the same page are checked together.
        page_text_lookup: Dict[tuple, str] = {}

        for chunk in context_chunks:
            key = (
                chunk.get("paper_id"),
                chunk.get("page"),
            )

            existing = page_text_lookup.get(key, "")

            page_text_lookup[key] = (f"{existing} {chunk.get('text', '')}").strip()

        validated: List[Dict] = []

        for citation in citations:
            paper_id = citation.get("paper_id")
            page = citation.get("page")
            snippet = (citation.get("quoted_snippet") or "").strip()

            key = (paper_id, page)

            page_exists = key in page_text_lookup

            text_verified = False

            if page_exists and snippet:
                text_verified = QACitationValidator._snippet_overlaps(
                    snippet,
                    page_text_lookup[key],
                )

            if not page_exists:
                logger.info(
                    "Citation flagged: page %s not found for paper %s",
                    page,
                    paper_id,
                )
            elif not text_verified:
                logger.info(
                    "Citation flagged: snippet did not match page %s of %s",
                    page,
                    paper_id,
                )

            validated.append(
                {
                    **citation,
                    "page_exists": page_exists,
                    "text_verified": text_verified,
                }
            )

        return validated

    @staticmethod
    def _snippet_overlaps(
        snippet: str,
        page_text: str,
    ) -> bool:
        """
        Return True if the snippet is reasonably found within the page text.

        First tries a direct case-insensitive substring match (handles the
        common case where the model copied the text correctly). Falls back
        to a fuzzy ratio check using the best-matching window of the page
        text, to tolerate minor whitespace/punctuation differences from
        markdown conversion.
        """
        normalized_snippet = QACitationValidator._normalize(snippet)

        normalized_page = QACitationValidator._normalize(page_text)

        if not normalized_snippet or not normalized_page:
            return False

        if normalized_snippet in normalized_page:
            return True

        # Fuzzy fallback: compare the snippet against a sliding window of the page text roughly the same length as the snippet.
        window_size = max(
            len(normalized_snippet),
            20,
        )

        best_ratio = 0.0

        step = max(
            1,
            window_size // 2,
        )

        for start in range(
            0,
            max(
                1,
                len(normalized_page) - window_size + 1,
            ),
            step,
        ):
            window = normalized_page[start : start + window_size]

            ratio = SequenceMatcher(
                None,
                normalized_snippet,
                window,
            ).ratio()

            best_ratio = max(
                best_ratio,
                ratio,
            )

            if best_ratio >= FUZZY_MATCH_THRESHOLD:
                return True

        return best_ratio >= FUZZY_MATCH_THRESHOLD

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase and collapse whitespace for comparison purposes."""
        return re.sub(
            r"\s+",
            " ",
            text.lower(),
        ).strip()
