"""
Views for Research AI Assistant API.
Handles OpenAlex paper search with three ranking modes.
"""

import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import QueryLog
from .services.openalex_service import OpenAlexAPIError, OpenAlexService
from .services.extract_service import ExtractionService

logger = logging.getLogger(__name__)

openalex_service = OpenAlexService()


@require_GET
def api_root(request):
    """
    Root endpoint providing API information.

    GET /api/
    """
    return JsonResponse(
        {
            "message": "AI Research Assistant API",
            "version": "1.0",
            "endpoints": {
                "search": "/api/search/?q=<query>&mode=<mode>&per_page=<int>",
                "modes": ["relevance", "open_access", "best_match"],
            },
            "documentation": "https://docs.openalex.org/",
        }
    )


@require_GET
def search(request):
    """
    Search academic papers via OpenAlex with ranking modes.

    GET /api/search/?q=<query>&mode=<mode>&per_page=<int>&oa_status=<status>

    Query params:
        q (required): keyword search string
        mode (optional): relevance | open_access | best_match (default: relevance)
        per_page (optional): results per page, 1-50 (default: 25)
        oa_status (optional): gold | green | hybrid | bronze

    Returns JSON:
    {
        "papers": [...],
        "count": int,
        "mode": str,
        "query": str
    }

    References:
        Django views: https://docs.djangoproject.com/en/6.0/topics/http/views/
        OpenAlex API: https://docs.openalex.org/api-entities/works
    """
    query = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "relevance").strip()
    per_page_raw = request.GET.get("per_page", "25")
    oa_status = request.GET.get("oa_status", None)

    # Validate query
    if not query:
        return JsonResponse({"error": "Query parameter 'q' is required."}, status=400)

    # Validate mode
    valid_modes = {"relevance", "open_access", "best_match"}
    if mode not in valid_modes:
        return JsonResponse(
            {
                "error": f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}"
            },
            status=400,
        )

    # Validate per_page
    try:
        per_page = int(per_page_raw)
        if per_page < 1 or per_page > 50:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    # Map mode to OpenAlexService parameters
    open_access_only = mode == "open_access"

    logger.info(
        "Search request: query='%s' mode='%s' per_page=%d", query, mode, per_page
    )

    try:
        # Fetch raw works from OpenAlex
        raw_results = openalex_service.search_papers(
            query=query,
            per_page=per_page,
            open_access_only=open_access_only,
            oa_status=oa_status,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except OpenAlexAPIError as exc:
        logger.error("OpenAlex error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)

    # Extract structured metadata from raw works
    papers = [ExtractionService.extract_metadata(work) for work in raw_results]

    # Log query — non-blocking
    try:
        QueryLog.objects.create(
            query_text=query,
            ranking_mode=mode,
            result_count=len(papers),
        )
    except Exception:
        logger.warning("Failed to write QueryLog entry.", exc_info=True)

    return JsonResponse(
        {
            "papers": papers,
            "count": len(papers),
            "mode": mode,
            "query": query,
        }
    )
