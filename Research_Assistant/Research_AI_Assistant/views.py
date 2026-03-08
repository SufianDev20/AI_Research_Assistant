"""
Views for Research AI Assistant API.
Handles OpenAlex paper search with three ranking modes.
"""

import logging
import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from .models import QueryLog
from .services.openalex_service import OpenAlexAPIError, OpenAlexService
from .services.extract_service import ExtractionService
from .services.openrouter_service import OpenRouterAPIError, OpenRouterService
from .services.prompt_builder import system_prompt, build_user_message

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
@ratelimit(key="ip", rate="100/s")  # OpenAlex: Max 100 requests per second
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


@csrf_exempt
@require_POST
@ratelimit(key="ip", rate="20/m")
def summarise(request):
    """
    Generate a synthesis summary of research papers using OpenRouter LLM.

    POST /api/summarise/
    Content-Type: application/json

    Body:
    {
        "query": "search query string",
        "papers": [...]  # List of paper metadata objects
    }

    Returns:
    {
        "summary": "LLM-generated synthesis with citations",
        "paper_count": int,
        "query": "original query"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    # Validate required fields
    query = data.get("query")
    papers = data.get("papers")

    if not query:
        return JsonResponse({"error": "Missing 'query' field"}, status=400)

    if not papers:
        return JsonResponse({"error": "Missing 'papers' field"}, status=400)

    if not isinstance(papers, list) or len(papers) == 0:
        return JsonResponse({"error": "'papers' must be a non-empty list"}, status=400)

    # Cap papers at 20 to avoid token limits
    papers = papers[:20]

    try:
        # Initialize OpenRouter service
        openrouter_service = OpenRouterService()

        # Build user message from papers
        user_message = build_user_message(papers, query)

        # Get summary from LLM
        summary = openrouter_service.complete(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        return JsonResponse(
            {
                "summary": summary,
                "paper_count": len(papers),
                "query": query,
            }
        )

    except OpenRouterAPIError as exc:
        logger.error("OpenRouter service error: %s", exc)
        return JsonResponse(
            {"error": "Service temporarily unavailable"}, status=503
        )
    except Exception as exc:
        logger.error("Unexpected error in summarise: %s", exc, exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_GET
@ratelimit(key="ip", rate="100/s")  # OpenAlex: Max 100 requests per second
def search_authors(request):
    """
    Search authors via OpenAlex API.

    GET /api/openalex/authors/?q=<query>&per_page=<int>&page=<int>

    Query params:
        q (required): author search string
        per_page (optional): results per page, 1-50 (default: 10)
        page (optional): page number (default: 1)

    Returns JSON:
    {
        "results": [...],
        "page": int,
        "per_page": int,
        "query": str
    }
    """
    query = request.GET.get("q", "").strip()
    per_page_raw = request.GET.get("per_page", "10")
    page_raw = request.GET.get("page", "1")

    # Validate query
    if not query:
        return JsonResponse(
            {
                "error": {
                    "code": "missing_query",
                    "message": "Query parameter 'q' is required.",
                }
            },
            status=400,
        )

    # Validate per_page
    try:
        per_page = int(per_page_raw)
        if per_page < 1 or per_page > 50:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    # Validate page
    try:
        page = int(page_raw)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    logger.info(
        "Author search request: query='%s' per_page=%d page=%d", query, per_page, page
    )

    try:
        # Fetch authors from OpenAlex
        results = openalex_service.search_authors(
            query=query,
            per_page=per_page,
            page=page,
        )
        return JsonResponse(
            {
                "results": results,
                "page": page,
                "per_page": per_page,
                "query": query,
            }
        )
    except OpenAlexAPIError as exc:
        logger.error("OpenAlex author search error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)


@require_GET
@ratelimit(key="ip", rate="100/s")  # OpenAlex: Max 100 requests per second
def openalex_works_search(request):
    """
    Search papers via OpenAlex API with different response format.

    GET /api/openalex/works/?q=<query>&per_page=<int>&page=<int>

    Query params:
        q (required): keyword search string
        per_page (optional): results per page, 1-50 (default: 25)
        page (optional): page number (default: 1)

    Returns JSON:
    {
        "results": [...],
        "page": int,
        "per_page": int,
        "query": str
    }
    """
    query = request.GET.get("q", "").strip()
    per_page_raw = request.GET.get("per_page", "25")
    page_raw = request.GET.get("page", "1")

    # Validate query
    if not query:
        return JsonResponse(
            {
                "error": {
                    "code": "missing_query",
                    "message": "Query parameter 'q' is required.",
                }
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

    # Validate page
    try:
        page = int(page_raw)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    logger.info(
        "OpenAlex works search request: query='%s' per_page=%d page=%d",
        query,
        per_page,
        page,
    )

    try:
        # Fetch raw works from OpenAlex
        raw_results = openalex_service.search_papers(
            query=query,
            per_page=per_page,
            page=page,
        )
        return JsonResponse(
            {
                "results": raw_results,
                "page": page,
                "per_page": per_page,
                "query": query,
            }
        )
    except OpenAlexAPIError as exc:
        logger.error("OpenAlex works search error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)
