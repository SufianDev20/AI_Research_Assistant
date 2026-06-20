"""
Views for Research AI Assistant API.
Handles OpenAlex paper search with three ranking modes.
"""

import logging
import json
import re

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status

from .models import QueryLog, PaperPDF
from .services.openalex_service import OpenAlexAPIError, OpenAlexService
from .services.extract_service import ExtractionService
from .services.openrouter_service import OpenRouterAPIError, OpenRouterService
from .services.prompt_builder import system_prompt, build_user_message
from .services.pdf_service import PDFService, PDFExtractionError

logger = logging.getLogger(__name__)

openalex_service = OpenAlexService()


class SearchRateThrottle(AnonRateThrottle):
    """Rate throttle for search requests for Annonymous users"""

    rate = "100/s"


class GenerateTitle(AnonRateThrottle):
    """Rate throttle for title generation requests for Annonymous users"""

    rate = "20/m"


@api_view(["GET"])
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


@api_view(["GET"])
@throttle_classes([SearchRateThrottle])
def search(request):
    """
    Search academic papers via OpenAlex with ranking modes and pagination.

    GET /api/search/?q=<query>&mode=<mode>&per_page=<int>&page=<int>&cursor=<str>&oa_status=<status>&min_year=<int>&max_year=<int>&random_seed=<int>

    Query params:
        q (required): keyword search string
        mode (optional): relevance | open_access | best_match (default: relevance)
        per_page (optional): results per page, 1-50 (default: 25)
        page (optional): page number for basic pagination (default: 1)
        cursor (optional): cursor for advanced pagination (overrides page)
        oa_status (optional): gold | green | hybrid | bronze
        min_year (optional): minimum publication year (default: None)
        max_year (optional): maximum publication year (default: None)

    Returns JSON:
    {
        "papers": [...],
        "count": int,
        "total_count": int,
        "per_page": int,
        "page": int,
        "next_cursor": str|null,
        "has_more": bool,
        "mode": str,
        "query": str
    }

    References:
        Django views: https://docs.djangoproject.com/en/6.0/topics/http/views/
        OpenAlex API: https://docs.openalex.org/api-entities/works
    """
    query = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "open_access").strip()
    per_page_raw = request.GET.get("per_page", "25")
    cursor = request.GET.get("cursor", None)
    oa_status = request.GET.get("oa_status", None)
    min_year_raw = request.GET.get("min_year", None)
    max_year_raw = request.GET.get("max_year", None)
    random_seed_raw = request.GET.get("random_seed", None)

    # Validate query
    if not query:
        return JsonResponse(
            {"error": "Query parameter 'q' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate mode
    valid_modes = {"relevance", "open_access", "best_match"}
    if mode not in valid_modes:
        return JsonResponse(
            {
                "error": f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate per_page
    try:
        per_page = int(per_page_raw)
        if per_page < 1 or per_page > 50:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    # Parse load_more parameter
    load_more_raw = request.GET.get("load_more", "false").lower()
    load_more = load_more_raw in ("true", "1", "yes", "on")

    # Validate load_more: if true, cursor is required
    if load_more and not cursor:
        return JsonResponse(
            {"error": "cursor parameter is required when load_more=true"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate and parse year parameters
    min_year = None
    max_year = None

    if min_year_raw is not None:
        try:
            min_year = int(min_year_raw)
            if min_year < 1900 or min_year > 2026:
                return JsonResponse(
                    {"error": "min_year must be between 1900 and 2026"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "min_year must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if max_year_raw is not None:
        try:
            max_year = int(max_year_raw)
            if max_year < 1900 or max_year > 2026:
                return JsonResponse(
                    {"error": "max_year must be between 1900 and 2026"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "max_year must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if min_year is not None and max_year is not None and min_year > max_year:
        return JsonResponse(
            {"error": "min_year cannot be greater than max_year"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Parse random_seed parameter
    random_seed = None
    if random_seed_raw is not None:
        try:
            random_seed = int(random_seed_raw)
        except (ValueError, TypeError):
            random_seed = None

    # Map mode to OpenAlexService parameters
    open_access_only = mode == "open_access"

    logger.info(
        "Search request: query='%s' mode='%s' per_page=%d load_more=%s",
        query,
        mode,
        per_page,
        load_more,
    )

    try:
        # Fetch raw works from OpenAlex with pagination
        api_response = openalex_service.search_papers(
            query=query,
            per_page=per_page,
            cursor=cursor,
            open_access_only=open_access_only,
            oa_status=oa_status,
            min_year=min_year,
            max_year=max_year,
            random_seed=random_seed,
        )

        raw_results = api_response.get("results", [])
        meta = api_response.get("meta", {})
        total_count = meta.get("count", len(raw_results))
        next_cursor = meta.get("next_cursor")

    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except OpenAlexAPIError as exc:
        logger.error("OpenAlex error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

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

    message = None
    if next_cursor is None:
        message = "No more papers available"

    return JsonResponse(
        {
            "papers": papers,
            "count": len(papers),
            "total_count": total_count,
            "per_page": per_page,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
            "mode": mode,
            "query": query,
            "message": message,
        }
    )


@require_POST
@throttle_classes([GenerateTitle])
def generate_title(request):
    """
    Generate a title for a research conversation using OpenRouter LLM.

    POST /api/generate_title/
    Content-Type: application/json

    Body:
    {
        "messages": [...]  # List of message objects with role and content
    }

    Returns:
    {
        "title": "Generated title"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    messages = data.get("messages")

    if not messages or not isinstance(messages, list) or len(messages) == 0:
        return JsonResponse(
            {"error": "Missing or invalid 'messages' field"}, status=400
        )

    try:
        # Initialize OpenRouter service
        openrouter_service = OpenRouterService()

        # Convert conversation history to a single user message for title generation
        conversation_text = "\n".join(
            [
                f"{msg.get('role', '').title()}: {msg.get('content', '')}"
                for msg in messages[-5:]  # Use last 5 messages to avoid token limits
            ]
        )

        # Get title from LLM
        title = openrouter_service.complete(
            system_prompt="You are a helpful assistant that generates concise, professional titles for research conversations.",
            user_message=f"Based on this conversation, suggest a short, catchy, professional title (maximum 40 characters). Respond with ONLY the title text - no quotes, explanations, or extra words.\n\nConversation:\n{conversation_text}",
            request_type="title",
        )

        # Clean the title
        title = re.sub(r'^["\']|["\']$|^\s*Title:\s*', "", title).strip()

        if len(title) < 5 or len(title) > 60:
            title = "Research Conversation"

        return JsonResponse({"title": title})

    except OpenRouterAPIError as exc:
        logger.error("OpenRouter title generation error: %s", exc)
        return JsonResponse(
            {"error": "Service temporarily unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.error("Unexpected error in generate_title: %s", exc, exc_info=True)
        return JsonResponse(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def frontend(request):
    """
    Render the frontend HTML template for BRAIN AI Research Assistant.
    """
    return render(request, "index.html")


@require_POST
@throttle_classes([GenerateTitle])
def summarise(request):
    """
    Generate a summary of research papers using OpenRouter LLM.

    POST /api/summarise/
    Content-Type: application/json

    Body:
    {
        "query": "research question",
        "papers": [...]  # List of paper objects from search endpoint
    }

    Returns:
    {
        "summary": "Generated summary"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    query = data.get("query")
    papers = data.get("papers")

    if not query or not isinstance(query, str):
        return JsonResponse({"error": "Missing or invalid 'query' field"}, status=400)

    if not papers or not isinstance(papers, list):
        return JsonResponse({"error": "Missing or invalid 'papers' field"}, status=400)

    try:
        # Initialize OpenRouter service
        openrouter_service = OpenRouterService()

        # Build user message with papers context
        user_message = build_user_message(papers, query)

        # Get summary from LLM
        summary = openrouter_service.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            request_type="summary",
        )

        return JsonResponse({"summary": summary})

    except OpenRouterAPIError as exc:
        logger.error("OpenRouter summarise error: %s", exc)
        return JsonResponse(
            {
                "error": "Service temporarily unavailable",
                "error_code": "OPENROUTER_API_ERROR",
                "message": "Summary service temporarily unavailable - please try again later",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.error("Unexpected error in summarise: %s", exc, exc_info=True)
        return JsonResponse(
            {
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@require_GET
@throttle_classes([SearchRateThrottle])
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
        return JsonResponse({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class PDFThrottle(AnonRateThrottle):
    rate = "10/m"  # PDF fetches are expensive


class SummariseThrottle(AnonRateThrottle):
    rate = "10/m"  # Summarisation is expensive


@api_view(["POST"])
@throttle_classes([PDFThrottle])
def extract_pdf(request):
    """
    POST /api/extract-pdf/
    Body: { "openalex_id": "https://openalex.org/W123", "pdf_url": "https://..." }
    """
    openalex_id = request.data.get("openalex_id", "").strip()
    pdf_url = request.data.get("pdf_url", "").strip()
    open_access = request.data.get("is_open_access", False)
    if not openalex_id or not pdf_url:
        return Response(
            {"error": "Both 'openalex_id' and 'pdf_url' are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not open_access:
        return Response(
            {"error": "cannot extract this paper is not open access"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Return cached result — filter on the actual DB column name
    cached = PaperPDF.objects.filter(
        openalex_id=openalex_id, extraction_success="success"
    ).first()
    if cached:
        return Response(
            {
                "openalex_id": openalex_id,
                "markdown": cached.markdown_content,
                "page_count": cached.page_count,
                "image_paths": cached.image_paths,
                "cached": True,
            }
        )

    # Prevent duplicate concurrent fetches
    record, created = PaperPDF.objects.get_or_create(
        openalex_id=openalex_id,
        defaults={"pdf_url": pdf_url, "extraction_success": "pending"},
    )

    if not created and record.extraction_success == "pending":
        from django.utils import timezone
        from datetime import timedelta

        if timezone.now() - record.created_at > timedelta(minutes=2):
            record.extraction_success = "pending"
            record.save(update_fields=["extraction_success"])
        else:
            return Response(
                {"error": "Extraction already in progress."},
                status=status.HTTP_409_CONFLICT,
            )

    # If a previous attempt failed, allow retry by resetting to pending
    if not created and record.extraction_success == "failed":
        record.extraction_success = "pending"
        record.pdf_url = pdf_url
        record.save(update_fields=["extraction_success", "pdf_url"])

    try:
        result = PDFService.fetch_and_extract(pdf_url, openalex_id)

        record.markdown_content = result["markdown"]
        record.page_count = result["page_count"]
        record.image_paths = result["image_paths"]
        record.extraction_success = "success"
        record.pdf_url = pdf_url
        record.error_message = None
        record.save()

        return Response(
            {
                "openalex_id": openalex_id,
                "markdown": result["markdown"],
                "page_count": result["page_count"],
                "image_paths": result["image_paths"],
                "cached": False,
            }
        )

    except PDFExtractionError as exc:
        record.extraction_success = "failed"
        record.error_message = str(exc)
        record.save(update_fields=["extraction_success", "error_message"])
        logger.error("PDF extraction failed for %s: %s", openalex_id, exc)
        return Response(
            {"error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["POST"])
@throttle_classes([SummariseThrottle])
def ask_paper(request):
    """
    POST /api/ask-paper/
    Body: { "openalex_id": "https://openalex.org/W123", "question": "What method did they use?" }
    """
    openalex_id = request.data.get("openalex_id", "").strip()
    question = request.data.get("question", "").strip()

    if not openalex_id or not question:
        return Response(
            {"error": "Both 'openalex_id' and 'question' are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    record = PaperPDF.objects.filter(
        openalex_id=openalex_id, extraction_success="success"
    ).first()
    if not record:
        return Response(
            {"error": "Paper not extracted yet. Call /api/extract-pdf/ first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 6000 chars covers roughly 3-4 pages within free model token limits
    context = record.markdown_content[:6000]

    try:
        openrouter_service = OpenRouterService()
        answer = openrouter_service.complete(
            system_prompt=(
                "You are a research assistant. Answer questions about the provided "
                "academic paper content accurately and concisely. "
                "Cite specific sections when relevant. "
                "If the answer is not in the paper, say so explicitly."
            ),
            user_message=f"Paper content:\n\n{context}\n\n---\n\nQuestion: {question}",
            request_type="paper_qa",
        )
        return Response({"answer": answer, "openalex_id": openalex_id})

    except OpenRouterAPIError as exc:
        logger.error("OpenRouter ask_paper error: %s", exc)
        return Response(
            {"error": "LLM service temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.error("Unexpected error in ask_paper: %s", exc, exc_info=True)
        return Response(
            {"error": "Internal server error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
