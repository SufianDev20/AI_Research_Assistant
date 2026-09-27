"""
Extract Metadata and Related information from OpenAlex
Converts raw API responses into structured data for storage and LLM processing.

OpenAlex Work object reference: https://developers.openalex.org
"""

from typing import Dict, List, Optional, Tuple

RELIABLE_DOMAINS = {
    "arxiv.org",
    "www.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "europepmc.org",
    "www.biorxiv.org",
    "www.medrxiv.org",
    "doaj.org",
    "core.ac.uk",
    "zenodo.org",
    "osf.io",
}

BLOCKED_DOMAINS = {
    "dl.acm.org",
    "ieeexplore.ieee.org",
    "www.sciencedirect.com",
    "link.springer.com",
    "onlinelibrary.wiley.com",
    "www.tandfonline.com",
    "www.jstor.org",
}


MAX_PDF_CANDIDATES = 3


def fetch_reliability(pdf_url: str) -> str:
    """Return 'reliable', 'blocked', or 'unknown' based on the URL's domain."""
    from urllib.parse import urlparse

    host = urlparse(pdf_url).hostname or ""
    if host in RELIABLE_DOMAINS:
        return "reliable"
    if host in BLOCKED_DOMAINS:
        return "blocked"
    return "unknown"


class ExtractionService:
    """Parse OpenAlex work objects into structured metadata."""

    @staticmethod
    def extract_metadata(work: Dict) -> Dict:
        """
        Extract metadata from OpenAlex work object.

        Args:
            work: Raw work dict from OpenAlex API.

        Returns:
            Structured metadata dict.

        Reference:
            https://developers.openalex.org
        """
        pdf_candidates = ExtractionService._collect_pdf_candidates(work)
        pdf_url, oa_url = ExtractionService._extract_pdf_and_oa_urls(work)

        return {
            "openalex_id": work.get("id", ""),
            "title": work.get("title", ""),
            "authors": ExtractionService._extract_authors(work),
            "abstract": ExtractionService._reconstruct_abstract(work),
            "publication_year": work.get("publication_year"),
            "doi": work.get("doi", ""),
            "cited_by_count": work.get("cited_by_count", 0),
            "concepts": ExtractionService._extract_concepts(work),
            "source": (
                work.get("primary_location", {}).get("source", {}).get("display_name")
                if work.get("primary_location")
                and work.get("primary_location", {}).get("source")
                else None
            ),
            # is_open_access reflects OpenAlex's own OA determination (open_access.is_oa),
            # NOT whether a PDF link exists. A green-OA paper can be OA with only a
            # landing_page_url and no direct pdf_url. Do not conflate the two.
            "is_open_access": bool(work.get("open_access", {}).get("is_oa", False)),
            "oa_status": work.get("open_access", {}).get("oa_status"),
            # has_pdf_link means a direct PDF URL was found in metadata.
            # This does NOT mean the URL is fetchable (publishers can still 403 it).
            # Use this field, not is_open_access, to decide whether to attempt extraction.
            "has_pdf_link": bool(pdf_url),
            "full_text_url": pdf_url or oa_url,
            "pdf_url": pdf_url,
            "pdf_candidates": pdf_candidates,
            "oa_url": oa_url,
            "referenced_works": ExtractionService._extract_referenced_works(work),
            "referenced_works_count": len(work.get("referenced_works", [])),
        }

    @staticmethod
    def _extract_authors(work: Dict) -> List[Dict]:
        """
        Extract author names and institutions.
        Reference: https://developers.openalex.org
        """
        authors = []
        for authorship in work.get("authorships", []):
            author = authorship.get("author", {})
            institutions = [
                inst.get("display_name") for inst in authorship.get("institutions", [])
            ]
            authors.append(
                {
                    "name": author.get("display_name", ""),
                    "orcid": author.get("orcid") or "",
                    "institutions": institutions,
                }
            )
        return authors

    @staticmethod
    def _reconstruct_abstract(work: Dict) -> str:
        """
        Reconstruct abstract from inverted index.
        Reference: https://developers.openalex.org
        """
        inverted = work.get("abstract_inverted_index")
        if not inverted or not isinstance(inverted, dict):
            return ""

        words = {}
        for word, positions in inverted.items():
            if isinstance(positions, list):
                for pos in positions:
                    words[pos] = word

        return " ".join(words[i] for i in sorted(words.keys()))

    @staticmethod
    def _extract_full_text_url(work: Dict) -> Optional[str]:
        """
        Extract open-access full text URL if available.
        Reference: https://developers.openalex.org
        """
        best_oa = work.get("best_oa_location")
        if best_oa:
            # Prefer direct PDF if available
            pdf_url = best_oa.get("pdf_url")
            if pdf_url:
                return pdf_url

            # Fall back to landing page (publisher's open-access page)
            landing_page = best_oa.get("landing_page_url")
            if landing_page:
                return landing_page

        # Fallback to content_urls if best_oa_location not available
        content_urls = work.get("content_urls")
        if content_urls:
            pdf_url = content_urls.get("pdf")
            if pdf_url:
                return pdf_url

        return None

    @staticmethod
    def _collect_pdf_candidates(work: Dict) -> List[str]:
        """
        Direct PDF URLs OpenAlex lists for this work, best first (max 3).

        Sources, in the order they were always consulted: best_oa_location,
        primary_location, every locations[] entry, content_urls["pdf"]. The
        first of these is the URL the app has always used; it is kept in the
        result even when the cap applies. The rest are ordered so hosts that
        don't block server downloads come before known-blocked publishers.
        """
        best_oa = work.get("best_oa_location") or {}
        primary = work.get("primary_location") or {}
        locations = work.get("locations")
        content_urls = work.get("content_urls")

        raw = [best_oa.get("pdf_url"), primary.get("pdf_url")]
        if isinstance(locations, list):
            raw += [loc.get("pdf_url") for loc in locations if isinstance(loc, dict)]
        if isinstance(content_urls, dict):
            raw.append(content_urls.get("pdf"))

        unique = list(dict.fromkeys(u for u in raw if isinstance(u, str) and u))
        if not unique:
            return []

        original = unique[0]
        rank = {"reliable": 0, "unknown": 1, "blocked": 2}
        candidates = sorted(unique, key=lambda u: rank[fetch_reliability(u)])[
            :MAX_PDF_CANDIDATES
        ]
        if original not in candidates:
            candidates[-1] = original
        return candidates

    @staticmethod
    def _extract_pdf_and_oa_urls(work: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Return (best direct pdf_url, landing page). The pdf_url is the first of
        _collect_pdf_candidates; the landing page falls back from best_oa_location
        to primary_location to open_access.oa_url.
        """
        candidates = ExtractionService._collect_pdf_candidates(work)
        pdf_url = candidates[0] if candidates else None

        best_oa = work.get("best_oa_location") or {}
        primary = work.get("primary_location") or {}
        landing_page = (
            best_oa.get("landing_page_url")
            or primary.get("landing_page_url")
            or (work.get("open_access") or {}).get("oa_url")
        )

        return pdf_url, landing_page

    @staticmethod
    def _extract_referenced_works(work: Dict) -> List[str]:
        """
        Extract referenced works (papers that this paper cites).
        Reference: https://developers.openalex.org

        Returns: List of OpenAlex ID strings
        """
        referenced_works = work.get("referenced_works", [])

        # Handle missing or invalid referenced_works field
        if not referenced_works or not isinstance(referenced_works, list):
            return []

        # referenced_works contains OpenAlex ID strings, not objects with metadata
        return referenced_works[:10]  # Limit to first 10 references

    @staticmethod
    def _extract_concepts(work: Dict) -> List[Dict]:
        """
        Extract research concepts/topics.
        Reference: https://developers.openalex.org
        """
        return [
            {"name": concept.get("display_name"), "score": concept.get("score")}
            for concept in work.get("concepts", [])[:5]
        ]
