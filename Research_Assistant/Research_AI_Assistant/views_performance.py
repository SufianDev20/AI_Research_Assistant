"""
Performance monitoring views for OpenRouter model statistics.
Provides API endpoints for model performance data and insights.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAdminUser
from rest_framework import status

from .error_handling import handle_internal_errors
from .models import ModelPerformance, ResponseLog, ModelReliability
from .services.performance_tracker import PerformanceTracker
from .throttles import PerformanceRateThrottle
from .views import clerk_context


@api_view(["GET"])
@permission_classes([IsAdminUser])
@throttle_classes([PerformanceRateThrottle])
@handle_internal_errors("Failed to retrieve performance stats")
def model_performance_stats(request):
    """
    Get comprehensive model performance statistics.

    GET /api/performance/stats/

    Returns JSON:
    {
        "total_models": int,
        "active_models": int,
        "models_by_tier": {...},
        "top_performers": [...],
        "recent_failures": [...],
        "performance_summary": {...}
    }
    """
    stats = PerformanceTracker.get_model_stats()

    # Add additional performance summary
    performance_summary = {
        "avg_success_rate": 0.0,
        "avg_response_time": 0.0,
        "total_requests_today": 0,
    }

    # Calculate averages
    active_models = ModelPerformance.objects.filter(is_active=True)
    if active_models.exists():
        total_success_rate = sum(model.success_rate for model in active_models)
        performance_summary["avg_success_rate"] = (
            total_success_rate / active_models.count()
        )

        total_response_time = sum(
            model.avg_response_time for model in active_models
        )
        performance_summary["avg_response_time"] = (
            total_response_time / active_models.count()
        )

    # Today's requests
    from django.utils import timezone

    today = timezone.now().date()
    performance_summary["total_requests_today"] = ResponseLog.objects.filter(
        created_at__date=today
    ).count()

    stats["performance_summary"] = performance_summary

    return JsonResponse(stats)


@api_view(["GET"])
@permission_classes([IsAdminUser])
@throttle_classes([PerformanceRateThrottle])
@handle_internal_errors("Failed to retrieve model details")
def model_details(request):
    """
    Get detailed information for a specific model.

    GET /api/performance/model/?model_name=<str>

    Returns JSON:
    {
        "model_name": str,
        "performance": {...},
        "reliability": {...},
        "recent_logs": [...],
        "error_analysis": {...}
    }
    """
    model_name = request.GET.get("model_name", "").strip()

    if not model_name:
        return JsonResponse(
            {"error": "model_name parameter is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get model performance data
    performance = ModelPerformance.objects.filter(model_name=model_name).first()
    if not performance:
        return JsonResponse({"error": f"Model '{model_name}' not found"}, status=404)

    # Get reliability configuration
    reliability = ModelReliability.objects.filter(model_name=model_name).first()

    # Get recent logs
    recent_logs = ResponseLog.objects.filter(model_name=model_name).order_by(
        "-created_at"
    )[:20]

    # Get error analysis
    error_logs = ResponseLog.objects.filter(
        model_name=model_name, success=False
    ).order_by("-created_at")[:10]

    # Build response
    response_data = {
        "model_name": model_name,
        "performance": {
            "total_requests": performance.total_requests,
            "successful_requests": performance.successful_requests,
            "failed_requests": performance.failed_requests,
            "success_rate": performance.success_rate,
            "avg_response_time": performance.avg_response_time,
            "reliability_score": performance.reliability_score,
            "consecutive_failures": performance.consecutive_failures,
            "is_active": performance.is_active,
            "last_success": (
                performance.last_success.isoformat()
                if performance.last_success
                else None
            ),
            "last_failure": (
                performance.last_failure.isoformat()
                if performance.last_failure
                else None
            ),
        },
        "reliability": (
            {
                "tier": reliability.tier,
                "priority": reliability.priority,
                "custom_temperature": reliability.custom_temperature,
                "max_retries": reliability.max_retries,
                "circuit_breaker_threshold": reliability.circuit_breaker_threshold,
            }
            if reliability
            else None
        ),
        "recent_logs": [
            {
                "request_type": log.request_type,
                "success": log.success,
                "response_time": log.response_time,
                "response_length": log.response_length,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent_logs
        ],
        "error_analysis": {
            "recent_errors": [
                {
                    "error_message": log.error_message,
                    "response_time": log.response_time,
                    "created_at": log.created_at.isoformat(),
                }
                for log in error_logs
            ],
            "common_errors": _get_common_errors(model_name),
        },
    }

    return JsonResponse(response_data)


@api_view(["GET"])
@permission_classes([IsAdminUser])
@throttle_classes([PerformanceRateThrottle])
@handle_internal_errors("Failed to compare models")
def model_comparison(request):
    """
    Compare performance between multiple models.

    GET /api/performance/compare/?models=<model1,model2,model3>

    Returns JSON:
    {
        "models": [...],
        "comparison_metrics": {...}
    }
    """
    models_param = request.GET.get("models", "").strip()

    if not models_param:
        return JsonResponse(
            {"error": "models parameter is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    model_names = [name.strip() for name in models_param.split(",") if name.strip()]

    if len(model_names) < 2:
        return JsonResponse(
            {"error": "At least 2 models required for comparison"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    models_data = []

    for model_name in model_names:
        performance = ModelPerformance.objects.filter(model_name=model_name).first()
        if performance:
            reliability = ModelReliability.objects.filter(
                model_name=model_name
            ).first()

            models_data.append(
                {
                    "model_name": model_name,
                    "success_rate": performance.success_rate,
                    "reliability_score": performance.reliability_score,
                    "avg_response_time": performance.avg_response_time,
                    "total_requests": performance.total_requests,
                    "tier": reliability.tier if reliability else "unknown",
                }
            )

    # Calculate comparison metrics
    if models_data:
        comparison_metrics = {
            "fastest_model": min(models_data, key=lambda x: x["avg_response_time"])[
                "model_name"
            ],
            "most_reliable": max(models_data, key=lambda x: x["reliability_score"])[
                "model_name"
            ],
            "highest_success_rate": max(
                models_data, key=lambda x: x["success_rate"]
            )["model_name"],
            "most_used": max(models_data, key=lambda x: x["total_requests"])[
                "model_name"
            ],
        }
    else:
        comparison_metrics = {
            "fastest_model": None,
            "most_reliable": None,
            "highest_success_rate": None,
            "most_used": None,
        }

    return JsonResponse(
        {"models": models_data, "comparison_metrics": comparison_metrics}
    )


@staff_member_required
def performance_dashboard(request):
    """
    Render performance monitoring dashboard. Restricted to Django staff
    users (logged in via /admin/login/); unauthenticated or non-staff
    visitors are redirected to the admin login page.

    GET /performance/
    """
    # Get top performers
    top_models = ModelPerformance.objects.filter(
        is_active=True, total_requests__gte=5
    ).order_by("-reliability_score")[:10]

    # Get recent activity
    recent_logs = ResponseLog.objects.select_related().order_by("-created_at")[:20]

    # Get tier distribution
    tier_stats = {}
    for tier_choice, tier_label in ModelReliability.TIER_CHOICES:
        count = ModelReliability.objects.filter(tier=tier_choice).count()
        tier_stats[tier_label] = count

    # Share of each tier among all configured models, for display only
    tier_total = sum(tier_stats.values())
    tier_rows = [
        {
            "label": label,
            "count": count,
            "percent": round(count / tier_total * 100, 1) if tier_total else 0.0,
        }
        for label, count in tier_stats.items()
    ]

    context = {
        "top_models": top_models,
        "recent_logs": recent_logs,
        "tier_stats": tier_stats,
        "tier_rows": tier_rows,
        "tier_total": tier_total,
        "total_models": ModelPerformance.objects.count(),
        "active_models": ModelPerformance.objects.filter(is_active=True).count(),
        **clerk_context(),
    }

    return render(request, "admin/performance_dashboard.html", context)


def _get_common_errors(model_name: str, limit: int = 5) -> list:
    """
    Get common error messages for a model.

    Args:
        model_name: Name of the model
        limit: Maximum number of errors to return

    Returns:
        List of common error messages with counts
    """
    from django.db.models import Count

    errors = (
        ResponseLog.objects.filter(
            model_name=model_name, success=False, error_message__isnull=False
        )
        .values("error_message")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )

    return [
        {
            "error": error["error_message"][:100],  # Truncate long errors
            "count": error["count"],
        }
        for error in errors
    ]
