"""
Shared exception -> HTTP status mapping for API views, so each view does not
repeat its own copy of "OpenAlexAPIError -> 502 / LLMError -> 503 / anything
else -> 500". A view with its own error body shape (e.g. multi_paper_qa,
which merges a per-paper "paper_errors" dict into every error response)
keeps its own try/except instead of using this.
"""

import logging
from functools import wraps

from django.http import JsonResponse
from rest_framework import status

from .services.openalex_service import OpenAlexAPIError
from .services.llm_service import LLMError

logger = logging.getLogger(__name__)


def handle_service_errors(include_error_code: bool = False):
    """
    Decorator for a DRF @api_view function. Catches the exception types every
    search/LLM view already maps to the same statuses, logs them once, and
    returns a JSON error body.

    include_error_code=True matches summarise()'s existing response shape
    (adds "error_code"/"message" alongside "error"); views that don't need
    that extra detail leave it off.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except OpenAlexAPIError as exc:
                logger.error("%s: OpenAlex error: %s", view_func.__name__, exc)
                return JsonResponse(
                    {"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY
                )
            except LLMError as exc:
                logger.error("%s: LLM error: %s", view_func.__name__, exc)
                body = {"error": "Service temporarily unavailable"}
                if include_error_code:
                    body["error_code"] = "LLM_API_ERROR"
                    body["message"] = (
                        "Summary service temporarily unavailable - please try again later"
                    )
                return JsonResponse(body, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception as exc:
                logger.error(
                    "Unexpected error in %s: %s", view_func.__name__, exc, exc_info=True
                )
                body = {"error": "Internal server error"}
                if include_error_code:
                    body["error_code"] = "INTERNAL_ERROR"
                    body["message"] = "An unexpected error occurred"
                return JsonResponse(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return wrapper

    return decorator


def handle_internal_errors(error_message: str):
    """
    Decorator for a @api_view function that has no service-specific
    exceptions to map (performance views: plain DB reads), just the same
    "log and return a 500" every one of them repeats by hand.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as exc:
                logger.error("Error in %s: %s", view_func.__name__, exc)
                return JsonResponse(
                    {"error": error_message},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return wrapper

    return decorator
