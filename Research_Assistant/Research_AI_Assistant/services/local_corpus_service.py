"""
Client for the university research server (POST /retrieve).

Returns papers in the same shape as ExtractionService.extract_metadata(),
so the summary and Q&A code can consume them unchanged when the corpus
provides a fetchable pdf_url.

Settings (all optional; an empty URL or key disables the local corpus):
    RESEARCH_API_URL, RESEARCH_API_KEY, RESEARCH_TIMEOUT = (connect, read)
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from django.conf import settings

from .research_server_config import research_server_config

logger = logging.getLogger(__name__)

class LocalCorpusError(Exception):
    """Raised for any failure that should trigger the OpenAlex fallback."""


def _split_authors(raw: str) -> List[Dict]:
    # Author format in the server database is not confirmed. Prefer ";" as
    # the separator; otherwise split on ",". Check with SELECT authors
    # FROM papers LIMIT 10 and adjust if names are stored as "Last, First".
    raw = (raw or "").strip()
    if not raw:
        return []
    parts = raw.split(";") if ";" in raw else raw.split(",")
    return [
        {"name": p.strip(), "orcid": "", "institutions": []} for p in parts if p.strip()
    ]


def _to_year(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _absolute_pdf_url(base_url: str, pdf_url: Optional[str]) -> Optional[str]:
    """The server returns pdf_url as a path relative to its own host (e.g.
    "/papers/foo.pdf"), not an absolute URL. Fetching it server-side (Q&A's
    PDF chunking) requires a real http(s) URL with a host, so resolve it
    against the research server's own base_url before it leaves this
    module. An already-absolute URL is returned unchanged."""
    if not pdf_url:
        return None
    return urljoin(base_url + "/", pdf_url)


def to_paper(source: Dict, index: int, base_url: str = "") -> Dict:
    """Map one server source to the OpenAlex-style paper dict.

    Source keys use the server's `papers` table column names.
    """
    filename = source.get("filename") or ""
    abstract = source.get("abstract") or " ".join(source.get("snippets") or [])
    pdf_url = _absolute_pdf_url(base_url, source.get("pdf_url"))
    return {
        "openalex_id": source.get("openalex_id") or f"local:{filename or index}",
        "title": source.get("title") or "Untitled paper",
        "authors": _split_authors(source.get("authors")),
        "abstract": abstract,
        "publication_year": _to_year(source.get("year")),
        "doi": source.get("doi") or "",
        "cited_by_count": source.get("citation_count") or 0,
        "concepts": [],
        "source": source.get("source") or "",
        "is_open_access": bool(pdf_url),
        "oa_status": None,
        "has_pdf_link": bool(pdf_url),
        "full_text_url": pdf_url,
        "pdf_url": pdf_url,
        "pdf_candidates": [pdf_url] if pdf_url else [],
        "oa_url": None,
        "referenced_works": [],
        "referenced_works_count": 0,
        "origin": "local",
        "relevant_pages": source.get("relevant_pages") or [],
    }


class LocalCorpusService:
    def __init__(self) -> None:
        self.base_url, self.api_key = research_server_config()
        self.timeout = getattr(settings, "RESEARCH_TIMEOUT", (6, 30))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    def search(self, query: str, max_papers: int = 25) -> Dict:
        """
        Returns {"papers": [...], "confidence": {...}}.
        Raises LocalCorpusError on any network, auth or payload problem.
        """
        if not self.enabled:
            raise LocalCorpusError("Local corpus is not configured.")

        try:
            requested_papers = int(max_papers)
        except (TypeError, ValueError) as exc:
            raise LocalCorpusError("Local corpus paper count must be an integer.") from exc
        if requested_papers < 1:
            raise LocalCorpusError("Local corpus paper count must be positive.")

        try:
            response = requests.post(
                f"{self.base_url}/retrieve",
                json={
                    "question": query,
                    "max_papers": requested_papers,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Local corpus request failed: %s", exc)
            raise LocalCorpusError("Local corpus unreachable.") from exc

        if response.status_code == 401:
            logger.error("Local corpus rejected the key (401). Key expired or wrong.")
            raise LocalCorpusError("Local corpus authentication failed.")
        if response.status_code != 200:
            logger.warning("Local corpus returned HTTP %s", response.status_code)
            raise LocalCorpusError(f"Local corpus HTTP {response.status_code}.")

        try:
            data = response.json()
            sources = data["sources"]
            confidence = data.get("confidence") or {}
            if not isinstance(confidence, dict):
                confidence = {}
            papers = [
                to_paper(s, i, base_url=self.base_url) for i, s in enumerate(sources, 1)
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LocalCorpusError("Local corpus returned an invalid payload.") from exc

        return {"papers": papers, "confidence": confidence}

    @staticmethod
    def is_sufficient(result: Dict) -> bool:
        """False means: switch to OpenAlex."""
        if not result["papers"]:
            return False
        return result["confidence"].get("label") != "Low"
