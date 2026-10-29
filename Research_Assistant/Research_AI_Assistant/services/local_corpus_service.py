"""
Client for the university research server (POST /retrieve).

Returns papers in the same shape as ExtractionService.extract_metadata(),
so the summary code can consume them unchanged. Q&A cannot: pdf_url and
oa_url are always None (the server has no full-text URL to give), so
these papers are excluded from multi-paper Q&A (see analysis.js's
`eligible` filter) rather than sent to it.

Settings (all optional; an empty URL or key disables the local corpus):
    RESEARCH_API_URL, RESEARCH_API_KEY, RESEARCH_TIMEOUT = (connect, read)
"""
import logging
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SERVER_MAX_PAPERS = 10  # server.py clamps max_papers to 10


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
        {"name": p.strip(), "orcid": "", "institutions": []}
        for p in parts
        if p.strip()
    ]


def _to_year(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_paper(source: Dict, index: int) -> Dict:
    """Map one server source to the OpenAlex-style paper dict."""
    filename = source.get("filename") or ""
    return {
        "openalex_id": f"local:{filename or index}",
        "title": source.get("title") or "Untitled paper",
        "authors": _split_authors(source.get("authors")),
        "abstract": " ".join(source.get("snippets") or []),
        "publication_year": _to_year(source.get("year")),
        "doi": "",
        "cited_by_count": 0,
        "concepts": [],
        "source": source.get("source") or "",
        "is_open_access": False,
        "oa_status": None,
        "has_pdf_link": False,
        "full_text_url": None,
        "pdf_url": None,
        "pdf_candidates": [],
        "oa_url": None,
        "referenced_works": [],
        "referenced_works_count": 0,
        "origin": "local",
        "relevant_pages": source.get("relevant_pages") or [],
    }


class LocalCorpusService:
    def __init__(self) -> None:
        self.base_url: str = (getattr(settings, "RESEARCH_API_URL", "") or "").rstrip("/")
        self.api_key: str = getattr(settings, "RESEARCH_API_KEY", "") or ""
        self.timeout = getattr(settings, "RESEARCH_TIMEOUT", (6, 30))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    def search(self, query: str, max_papers: int = 10) -> Dict:
        """
        Returns {"papers": [...], "confidence": {...}}.
        Raises LocalCorpusError on any network, auth or payload problem.
        """
        if not self.enabled:
            raise LocalCorpusError("Local corpus is not configured.")

        try:
            response = requests.post(
                f"{self.base_url}/retrieve",
                json={
                    "question": query,
                    "max_papers": max(1, min(int(max_papers), SERVER_MAX_PAPERS)),
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
            papers = [to_paper(s, i) for i, s in enumerate(sources, 1)]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LocalCorpusError("Local corpus returned an invalid payload.") from exc

        return {"papers": papers, "confidence": confidence}

    @staticmethod
    def is_sufficient(result: Dict) -> bool:
        """False means: switch to OpenAlex."""
        if not result["papers"]:
            return False
        return result["confidence"].get("label") != "Low"
