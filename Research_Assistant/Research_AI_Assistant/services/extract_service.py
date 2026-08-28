"""
Extract Metadata and Related information from OpenAlex
Converts raw API responses into structured data for storage and LLM processing.

OpenAlex Work object reference: https://developers.openalex.org
"""

from typing import Dict, List, Optional, Tuple


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
    def _extract_pdf_and_oa_urls(work: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Iterates across best_oa_location, primary_location, content_urls, and all locations
        to find direct PDF links and fallback landing pages.
        """
        pdf_url = None
        landing_page = None

        # 1. Best OA Location
        best_oa = work.get("best_oa_location") or {}
        if best_oa.get("pdf_url"):
            pdf_url = best_oa.get("pdf_url")
        landing_page = best_oa.get("landing_page_url")

        # 2. Primary Location Fallback
        primary = work.get("primary_location") or {}
        if not pdf_url and primary.get("pdf_url"):
            pdf_url = primary.get("pdf_url")
        if not landing_page:
            landing_page = primary.get("landing_page_url")

        # 3. Deep search: Check all locations array for a direct pdf_url
        if not pdf_url:
            locations = work.get("locations", [])
            if isinstance(locations, list):
                for loc in locations:
                    if isinstance(loc, dict) and loc.get("pdf_url"):
                        pdf_url = loc.get("pdf_url")
                        break

        # 4. Fallback content_urls
        if not pdf_url:
            content_urls = work.get("content_urls") or {}
            if isinstance(content_urls, dict):
                pdf_url = content_urls.get("pdf")

        # 5. Open Access Landing Page Fallback
        if not landing_page:
            landing_page = (work.get("open_access") or {}).get("oa_url")

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
