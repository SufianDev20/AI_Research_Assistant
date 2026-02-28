"""
Extract Metadata and Related information from OpenAlex
Converts raw API responses into structured data for storage and LLM processing.

OpenAlex Work object reference: https://docs.openalex.org/api-entities/works/work-object
"""

from typing import Dict, List, Optional


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
            https://docs.openalex.org/api-entities/works/work-object
        """
        return {
            "openalex_id": work.get("id", ""),
            "title": work.get("title", ""),
            "authors": ExtractionService._extract_authors(work),
            "abstract": ExtractionService._reconstruct_abstract(work),
            "publication_year": work.get("publication_year"),
            "doi": work.get("doi", ""),
            "cited_by_count": work.get("cited_by_count", 0),
            "concepts": ExtractionService._extract_concepts(work),
            "source": work.get("primary_location", {})
            .get("source", {})
            .get("display_name") if work.get("primary_location") and work.get("primary_location", {}).get("source") else None,
            "is_open_access": work.get("open_access", {}).get("is_oa", False),
            "oa_status": work.get("open_access", {}).get("oa_status"),
            "full_text_url": ExtractionService._extract_full_text_url(work),
        }

    @staticmethod
    def _extract_authors(work: Dict) -> List[Dict]:
        """
        Extract author names and institutions.
        Reference: https://docs.openalex.org/api-entities/works/work-object#authorships
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
        Reference: https://docs.openalex.org/api-entities/works/work-object#abstract_inverted_index
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
        Reference: https://docs.openalex.org/api-entities/works/work-object#best_oa_location
        """
        best_oa = work.get("best_oa_location")
        if not best_oa:
            return None

        # Prefer direct PDF if available
        pdf_url = best_oa.get("pdf_url")
        if pdf_url:
            return pdf_url

        # Fall back to landing page (publisher's open-access page)
        landing_page = best_oa.get("landing_page_url")
        if landing_page:
            return landing_page

        return None

    @staticmethod
    def _extract_concepts(work: Dict) -> List[Dict]:
        """
        Extract research concepts/topics.
        Reference: https://docs.openalex.org/api-entities/works/work-object#concepts
        """
        return [
            {"name": concept.get("display_name"), "score": concept.get("score")}
            for concept in work.get("concepts", [])[:5]
        ]
