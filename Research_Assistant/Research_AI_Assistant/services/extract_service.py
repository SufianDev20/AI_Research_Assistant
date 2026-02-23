"""
Extract Metadata and Related information from Openalex
Converts raw API responses into structured data for storage and LLM processing.
"""

from typing import Dict, List, Optional


class ExtractionService:
    """Parse OpenAlex work objects into structured metadata. Use static method decorator for avoid making 'self' instance as first input"""

    @staticmethod
    def extract_metadata(work: Dict) -> Dict:
        """Extract metadata from Openalex

        Args:
            work (Dict): Raw work objects from Openalex

        Returns:
            Dict: Return a normal dictionary from all the extracted metadata
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
            .get("display_name"),
            "full_text_url": ExtractionService._extract_full_text_url(work),
        }

    @staticmethod
    def _extract_authors(work: Dict) -> List[Dict]:
        """Extract author names and institutions."""
        authors = []
        for authorship in work.get("authorships", []):
            author = authorship.get("author", {})
            institutions = [
                inst.get("display_name")
                for inst in authorship.get("institutions", [])  # list comprehension
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
        """Reconstruct abstract from inverted index."""
        inverted = work.get("abstract_inverted_index")
        if not inverted or not isinstance(inverted, dict):
            return ""
        # Reconstruct text from inverted index
        words = {}
        for word, positions in inverted.items():
            if isinstance(positions, list):
                for pos in positions:
                    words[pos] = word
        return " ".join(words[i] for i in sorted(words.keys()))

    @staticmethod
    def _extract_full_text_url(work: Dict) -> Optional[str]:
        """Extract full text PDF URL if available."""
        # Try best OA location first
        best_oa = work.get("best_oa_location")
        if best_oa and best_oa.get("pdf_url"):
            return best_oa["pdf_url"]

        # Fallback to content_urls
        content_urls = work.get("content_urls")
        if content_urls and content_urls.get("pdf"):
            return content_urls["pdf"]

        # No full text available
        return None

    @staticmethod
    def _extract_concepts(work: Dict) -> List[Dict]:
        """Extract research concepts/topics."""
        return [
            {"name": concept.get("display_name"), "score": concept.get("score")}
            for concept in work.get("concepts", [])[:5]  # Top 5
        ]
