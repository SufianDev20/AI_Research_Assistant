"""
OpenAlex API client for fetching academic paper metadata.
Handles all interactions with OpenAlex API using pyalex library.
"""

from pyalex import Works, Authors
from django.conf import settings
from typing import List, Optional, Dict
import logging, pyalex, time
import requests

logger = logging.getLogger(__name__)

# Configure PyAlex API key if available
try:
    if (hasattr(settings, "OPENALEX_API_KEY") and settings.OPENALEX_API_KEY) or (
        hasattr(settings, "OPENALEX_EMAIL") and settings.OPENALEX_EMAIL
    ):
        pyalex.config.email = settings.OPENALEX_EMAIL
        pyalex.config.api_key = settings.OPENALEX_API_KEY
        if settings.OPENALEX_API_KEY:
            logger.info("PyAlex API key configured")
        else:
            logger.warning(
                "OPENALEX_API_KEY is empty: Load More (cursor paging) will fail with 401."
            )
except Exception as e:
    logger.warning(f"Failed to configure PyAlex API key: {e}")


class OpenAlexAPIError(Exception):
    """Custom exception for OpenAlex API failures."""

    pass


# OpenAlex sometimes answers with 429/5xx under load; those clear on their
# own, so retry a few times before giving up. 401 is not retried: a wrong or
# expired key returns it on every attempt, so retrying it only wastes time.
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.0


def _response_detail(exc) -> str:
    """OpenAlex's own explanation (e.g. "API key required for cursor paging")."""
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        body = response.json()
        message = body.get("message") or body.get("error") or ""
    except ValueError:
        message = (response.text or "")[:200]
    return f" — OpenAlex says: {message}" if message else ""


def _get_with_retry(works_query, **kwargs):
    """Run works_query.get(**kwargs), retrying transient OpenAlex errors."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return works_query.get(**kwargs)
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code not in RETRYABLE_STATUSES or attempt == MAX_ATTEMPTS:
                raise
            logger.warning(
                "OpenAlex returned %s (attempt %d/%d); retrying.",
                status_code,
                attempt,
                MAX_ATTEMPTS,
            )
            time.sleep(RETRY_DELAY_SECONDS * attempt)


class OpenAlexService:
    """Fetch and process data from OpenAlex API."""

    def search_papers(
        self,
        query: str,
        per_page: int = 25,
        cursor: Optional[str] = None,
        exclude_retracted: bool = True,
        open_access_only: bool = False,
        oa_status: Optional[str] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        random_seed: Optional[int] = None,
    ) -> Dict:
        """
        Search for academic papers with optional filters.

        Args:
           query: Search query string
           per_page: Results per page (max 200)
           cursor: Cursor for cursor-based pagination
           exclude_retracted: Filter out retracted papers (default: True)
           open_access_only: Return only open access papers (default: False)
           oa_status: Open access type filter - 'gold', 'green', 'hybrid', 'bronze' (default: None)
           min_year: Minimum publication year filter (default: None)
           max_year: Maximum publication year filter (default: None)
           random_seed: Random seed for result randomization (default: None)

        Returns:
           Dict with keys: 'results', 'meta' containing pagination info

        Raises:
           OpenAlexAPIError: If API request fails
           ValueError: If input parameters are invalid
        """
        # Input validation to prevent API abuse and errors
        if not query or not isinstance(query, str) or len(query.strip()) == 0:
            raise ValueError("Query must be a non-empty string")

        if not isinstance(per_page, int) or per_page < 1 or per_page > 200:
            raise ValueError("per_page must be an integer between 1 and 200")

        valid_oa_statuses = ["gold", "green", "hybrid", "bronze"]
        if oa_status is not None and oa_status not in valid_oa_statuses:
            raise ValueError(f"oa_status must be one of {valid_oa_statuses} or None")

        # Validate year parameters
        if min_year is not None and (
            not isinstance(min_year, int) or min_year < 1900 or min_year > 2026
        ):
            raise ValueError("min_year must be an integer between 1900 and 2026")

        if max_year is not None and (
            not isinstance(max_year, int) or max_year < 1900 or max_year > 2026
        ):
            raise ValueError("max_year must be an integer between 1900 and 2026")

        if min_year is not None and max_year is not None and min_year > max_year:
            raise ValueError("min_year cannot be greater than max_year")

        try:
            works_query = Works().search(query)

            if exclude_retracted:
                works_query = works_query.filter(is_retracted=False)

            if open_access_only:
                works_query = works_query.filter(is_oa=True)

            if oa_status:
                works_query = works_query.filter(oa_status=oa_status)

            # Add year filters
            if min_year is not None:
                works_query = works_query.filter(
                    from_publication_date=f"{min_year}-01-01"
                )

            if max_year is not None:
                works_query = works_query.filter(
                    to_publication_date=f"{max_year}-12-31"
                )

            # Cursor paging (OpenAlex documented) OR sampling mode (OpenAlex documented)
            #
            # We support a "sampling pagination" token so the UI can load additional random batches:
            #   cursor = "sample:<seed>:<page>"
            #
            # When in sampling mode, we do NOT rely on OpenAlex cursor paging, because sampling doesn't
            # provide a stable cursor. Instead, we deterministically vary the seed per page.
            sample_seed = None
            sample_page = 0
            if cursor and isinstance(cursor, str) and cursor.startswith("sample:"):
                try:
                    _, seed_str, page_str = cursor.split(":", 2)
                    sample_seed = int(seed_str)
                    sample_page = int(page_str)
                except Exception:
                    sample_seed = None
                    sample_page = 0

            if random_seed is not None or sample_seed is not None:
                base_seed = sample_seed if sample_seed is not None else int(random_seed)
                effective_seed = base_seed + int(sample_page)

                # Use documented sampling API
                results_list = works_query.sample(per_page, seed=effective_seed).get()
                meta = {
                    "count": 0,
                    "next_cursor": None,
                }

                # Allow a few "load more" batches (Google Scholar-style incremental reveal)
                # The frontend will hide the button when next_cursor is null.
                if sample_page < 4:
                    meta["next_cursor"] = f"sample:{base_seed}:{sample_page + 1}"
            else:
                results_list, meta = _get_with_retry(
                    works_query,
                    return_meta=True,
                    per_page=per_page,
                    cursor=cursor or "*",
                )

            return {
                "results": list(results_list),
                "meta": {
                    "count": meta.get("count", 0),
                    "next_cursor": meta.get("next_cursor"),
                },
            }

        except Exception as e:
            logger.error(
                f"OpenAlex API search failed for query: {query}", exc_info=True
            )
            raise OpenAlexAPIError(
                f"Failed to retrieve papers from OpenAlex: {str(e)}"
                f"{_response_detail(e)}"
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
