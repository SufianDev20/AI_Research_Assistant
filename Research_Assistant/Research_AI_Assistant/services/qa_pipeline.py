"""
Q&A data pipeline for Multi-Paper Q&A.

This module contains everything that touches paper data before and after
the LLM call:

    - PDF fetching and page-aware chunking
    - Context assembly and context-window validation
    - Citation validation

The LLM-specific code remains in qa_llm.py.
"""

import logging, math, re
from collections import Counter
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Union

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
    def fetch_and_chunk(pdf_url: Union[str, List[str]], openalex_id: str) -> Dict:
        """
        Fetch a PDF and split it into page-tagged chunks, trying each
        candidate URL in order until one yields usable text.

        Args:
            pdf_url: A direct PDF URL, or an ordered list of them (best first).
            openalex_id (str): OpenAlex Work ID used only for logging and error messages.

        Raises:
            QAChunkError: If no candidate works. With one candidate the error
            is that candidate's own; with several, all reasons are joined.
        """
        candidates = [pdf_url] if isinstance(pdf_url, str) else list(pdf_url or [])
        if not candidates:
            candidates = [""]

        reasons: List[str] = []
        for candidate in candidates:
            try:
                return QAChunkService._fetch_and_chunk_one(candidate, openalex_id)
            except Exception as exc:
                logger.warning(
                    "PDF candidate failed for %s (%s): %s", openalex_id, candidate, exc
                )
                reasons.append(str(exc))

        if len(reasons) == 1:
            raise QAChunkError(reasons[0])
        raise QAChunkError("; ".join(reasons))

    @staticmethod
    def _fetch_and_chunk_one(pdf_url: str, openalex_id: str) -> Dict:
        """
        Fetch a single PDF and split it into page tagged

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
            import pymupdf
            import pymupdf4llm as pm4
        except ModuleNotFoundError as exc:
            raise QAChunkError(
                f"No PDF Backend available. Install `pymupdf4llm`"
            ) from exc
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            page_dicts = pm4.to_markdown(
                doc, page_chunks=True, force_text=True, write_images=False
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
            doc.close()

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
        question: Optional[str] = None,
    ) -> Tuple[List[Dict], Dict]:
        """
        Assemble chunks from all papers ordered by (paper_id, page) and fit
        them inside the context window.

        If everything fits, all chunks are returned. If not and a ``question``
        is given, only the chunks most relevant to it are kept, with a fair
        per-paper share of the budget. Without a question an overflow raises.

        Returns:
            (chunks, stats) where stats is {"trimmed": bool, "papers":
            {paper_id: {"total": n, "used": n}}} (chunk counts).

        Raises:
            QAContextError: no chunks, no usable budget, or (no question)
                an overflow.
        """
        if not papers_chunks:
            raise QAContextError("No paper chunks were provided to build context from.")

        budget = max_context_tokens - RESERVED_TOKENS
        if budget <= 0:
            raise QAContextError(
                f"max_context_tokens ({max_context_tokens}) is too small to "
                f"leave room for the system prompt and output "
                f"(reserve {RESERVED_TOKENS})."
            )

        def tokens(chunk: Dict) -> int:
            return chunk.get("token_estimate") or QAContextService._estimate_tokens(
                chunk.get("text", "")
            )

        ordered_chunks: List[Dict] = []
        for paper_id in sorted(papers_chunks.keys()):
            ordered_chunks.extend(
                sorted(papers_chunks[paper_id] or [], key=lambda c: c.get("page", 0))
            )

        if not ordered_chunks:
            raise QAContextError(
                "All selected papers produced zero usable chunks; nothing to "
                "answer from."
            )

        total_tokens = sum(tokens(c) for c in ordered_chunks)
        trimmed = total_tokens > budget
        chosen = ordered_chunks

        if trimmed:
            if not (question or "").strip():
                raise QAContextError(
                    f"Selected papers require ~{total_tokens} tokens of context, "
                    f"which exceeds the available budget of {budget} tokens "
                    f"(model window {max_context_tokens}, reserved "
                    f"{RESERVED_TOKENS}). Select fewer papers or a model with "
                    f"a larger context window."
                )
            chosen = QAContextService._select_relevant(
                ordered_chunks, question, budget, tokens
            )

        papers: Dict[str, Dict] = {}
        for c in ordered_chunks:
            papers.setdefault(c.get("paper_id"), {"total": 0, "used": 0})["total"] += 1
        for c in chosen:
            papers[c.get("paper_id")]["used"] += 1

        logger.info(
            "Q&A context assembled: %d/%d chunks (budget %d tokens, trimmed=%s)",
            len(chosen),
            len(ordered_chunks),
            budget,
            trimmed,
        )

        return chosen, {"trimmed": trimmed, "papers": papers}

    @staticmethod
    def _select_relevant(
        ordered_chunks: List[Dict], question: str, budget: int, tokens
    ) -> List[Dict]:
        """
        Keep the chunks most relevant to the question within the budget.

        Relevance is a small TF-IDF keyword score. Each paper first gets an
        equal share of the budget so one long paper cannot crowd out the
        others; any unused budget is then filled with the best remaining
        chunks overall. The result keeps the (paper_id, page) ordering.
        """
        terms = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2}
        counts = [
            Counter(re.findall(r"[a-z0-9]+", c.get("text", "").lower()))
            for c in ordered_chunks
        ]
        n = len(ordered_chunks)
        idf = {
            t: math.log(1 + n / (1 + sum(1 for cnt in counts if t in cnt)))
            for t in terms
        }
        scores = [
            sum(idf[t] * (1 + math.log(cnt[t])) for t in terms if cnt.get(t))
            for cnt in counts
        ]

        by_paper: Dict[str, List[int]] = {}
        for i, c in enumerate(ordered_chunks):
            by_paper.setdefault(c.get("paper_id"), []).append(i)

        share = budget // len(by_paper)
        picked = set()
        used = 0

        # Pass 1: best chunks per paper within that paper's share.
        for indices in by_paper.values():
            spent = 0
            for i in sorted(indices, key=lambda i: (-scores[i], i)):
                cost = tokens(ordered_chunks[i])
                if spent + cost <= share and used + cost <= budget:
                    picked.add(i)
                    spent += cost
                    used += cost

        # Pass 2: spend whatever is left on the best remaining chunks.
        rest = sorted((i for i in range(n) if i not in picked), key=lambda i: (-scores[i], i))
        for i in rest:
            cost = tokens(ordered_chunks[i])
            if used + cost <= budget:
                picked.add(i)
                used += cost

        return [ordered_chunks[i] for i in sorted(picked)]

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
