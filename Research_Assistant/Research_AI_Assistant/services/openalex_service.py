"""
OpenAlex API client for fetching academic paper metadata.
Handles all interactions with OpenAlex API using pyalex library.
"""

from pyalex import Works, Authors
from django.conf import settings
from typing import List, Optional, Dict
import logging

# Configure PyAlex API key if available
try:
    if hasattr(settings, 'OPENALEX_API_KEY') and settings.OPENALEX_API_KEY:
        import pyalex
        pyalex.config.api_key = settings.OPENALEX_API_KEY
        logger = logging.getLogger(__name__)
        logger.info("PyAlex API key configured")
except Exception as e:
    logging.getLogger(__name__).warning(f"Failed to configure PyAlex API key: {e}")

logger = logging.getLogger(__name__)


class OpenAlexAPIError(Exception):
    """Custom exception for OpenAlex API failures."""

    pass


class OpenAlexService:
    """Fetch and process data from OpenAlex API."""

    def search_papers(
        self,
        query: str,
        per_page: int = 25,
        page: int = 1,
        exclude_retracted: bool = True,
        open_access_only: bool = False,
        oa_status: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for academic papers with optional filters.

        Args:
           query: Search query string
           per_page: Results per page (max 200)
           exclude_retracted: Filter out retracted papers (default: True)
           open_access_only: Return only open access papers (default: False)
           oa_status: Open access type filter - 'gold', 'green', 'hybrid', 'bronze' (default: None)

        Returns:
           List of work objects from OpenAlex

        Raises:
           OpenAlexAPIError: If API request fails
           ValueError: If input parameters are invalid
        """
        # Input validation to prevent API abuse and errors
        if not query or not isinstance(query, str) or len(query.strip()) == 0:
            raise ValueError("Query must be a non-empty string")

        if not isinstance(per_page, int) or per_page < 1 or per_page > 200:
            raise ValueError("per_page must be an integer between 1 and 200")
        if not isinstance(page, int) or page < 1:
            raise ValueError("page must be a positive integer")

        valid_oa_statuses = ["gold", "green", "hybrid", "bronze"]
        if oa_status is not None and oa_status not in valid_oa_statuses:
            raise ValueError(f"oa_status must be one of {valid_oa_statuses} or None")

        try:
            works_query = Works().search(query)

            if exclude_retracted:
                works_query = works_query.filter(is_retracted=False)

            if open_access_only:
                works_query = works_query.filter(is_oa=True)

            if oa_status:
                works_query = works_query.filter(oa_status=oa_status)

            results = works_query.get(per_page=per_page, page=page)
            return list(results)

        except Exception as e:
            logger.error(
                f"OpenAlex API search failed for query: {query}", exc_info=True
            )
            raise OpenAlexAPIError(
                f"Failed to retrieve papers from OpenAlex: {str(e)}"
            ) from e

    def search_authors(
        self,
        query: str,
        per_page: int = 25,
        page: int = 1,
    ) -> List[Dict]:
        """Search OpenAlex for authors matching a query string.

        Args:
            query: Search query string
            per_page: number of results per page (1-200)
            page: page number, positive integer

        Returns:
            A list of author objects (dictionaries) returned from OpenAlex.

        Raises:
            OpenAlexAPIError if the upstream API fails or a ValueError for bad input.
        """
        if not query or not isinstance(query, str) or len(query.strip()) == 0:
            raise ValueError("Query must be a non-empty string")
        if not isinstance(per_page, int) or per_page < 1 or per_page > 200:
            raise ValueError("per_page must be an integer between 1 and 200")
        if not isinstance(page, int) or page < 1:
            raise ValueError("page must be a positive integer")

        try:
            authors_query = Authors().search(query)
            results = authors_query.get(per_page=per_page, page=page)
            return list(results)
        except Exception as e:
            logger.error(
                f"OpenAlex API author search failed for query: {query}",
                exc_info=True,
            )
            raise OpenAlexAPIError(
                f"Failed to retrieve authors from OpenAlex: {str(e)}"
            ) from e
