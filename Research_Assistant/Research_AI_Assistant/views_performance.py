"""
Performance monitoring views for OpenRouter model statistics.
Provides API endpoints for model performance data and insights.
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from .models import ModelPerformance, ResponseLog, ModelReliability
from .services.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)


@require_GET
@ratelimit(key="ip", rate="60/m")
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
    try:
        stats = PerformanceTracker.get_model_stats()
        
        # Add additional performance summary
        performance_summary = {
            "avg_success_rate": 0.0,
            "avg_response_time": 0.0,
            "total_requests_today": 0,
            "success_rate_trend": "stable"  # Could be calculated from historical data
        }
        
        # Calculate averages
        active_models = ModelPerformance.objects.filter(is_active=True)
        if active_models.exists():
            total_success_rate = sum(model.success_rate for model in active_models)
            performance_summary["avg_success_rate"] = total_success_rate / active_models.count()
            
            total_response_time = sum(model.avg_response_time for model in active_models)
            performance_summary["avg_response_time"] = total_response_time / active_models.count()
        
        # Today's requests
        from django.utils import timezone
        today = timezone.now().date()
        performance_summary["total_requests_today"] = ResponseLog.objects.filter(
            created_at__date=today
        ).count()
        
        stats["performance_summary"] = performance_summary
        
        return JsonResponse(stats)
        
    except Exception as exc:
        logger.error(f"Error in model_performance_stats: {exc}")
        return JsonResponse({"error": "Failed to retrieve performance stats"}, status=500)


@require_GET
@ratelimit(key="ip", rate="60/m")
def model_details(request):
    """
    Get detailed information for a specific model.
    
    GET /api/performance/model/<str:model_name>/
    
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
        return JsonResponse({"error": "model_name parameter is required"}, status=400)
    
    try:
        # Get model performance data
        performance = ModelPerformance.objects.filter(model_name=model_name).first()
        if not performance:
            return JsonResponse({"error": f"Model '{model_name}' not found"}, status=404)
        
        # Get reliability configuration
        reliability = ModelReliability.objects.filter(model_name=model_name).first()
        
        # Get recent logs
        recent_logs = ResponseLog.objects.filter(
            model_name=model_name
        ).order_by("-created_at")[:20]
        
        # Get error analysis
        error_logs = ResponseLog.objects.filter(
            model_name=model_name,
            success=False
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
                "last_success": performance.last_success.isoformat() if performance.last_success else None,
                "last_failure": performance.last_failure.isoformat() if performance.last_failure else None,
            },
            "reliability": {
                "tier": reliability.tier if reliability else "unknown",
                "priority": reliability.priority if reliability else 999,
                "custom_temperature": reliability.custom_temperature if reliability else None,
                "max_retries": reliability.max_retries if reliability else 3,
                "circuit_breaker_threshold": reliability.circuit_breaker_threshold if reliability else 5,
            } if reliability else None,
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
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as exc:
        logger.error(f"Error in model_details for {model_name}: {exc}")
        return JsonResponse({"error": "Failed to retrieve model details"}, status=500)


@require_GET
@ratelimit(key="ip", rate="60/m")
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
        return JsonResponse({"error": "models parameter is required"}, status=400)
    
    model_names = [name.strip() for name in models_param.split(",") if name.strip()]
    
    if len(model_names) < 2:
        return JsonResponse({"error": "At least 2 models required for comparison"}, status=400)
    
    try:
        models_data = []
        
        for model_name in model_names:
            performance = ModelPerformance.objects.filter(model_name=model_name).first()
            if performance:
                reliability = ModelReliability.objects.filter(model_name=model_name).first()
                
                models_data.append({
                    "model_name": model_name,
                    "success_rate": performance.success_rate,
                    "reliability_score": performance.reliability_score,
                    "avg_response_time": performance.avg_response_time,
                    "total_requests": performance.total_requests,
                    "tier": reliability.tier if reliability else "unknown",
                })
        
        # Calculate comparison metrics
        if models_data:
            comparison_metrics = {
                "fastest_model": min(models_data, key=lambda x: x["avg_response_time"])["model_name"],
                "most_reliable": max(models_data, key=lambda x: x["reliability_score"])["model_name"],
                "highest_success_rate": max(models_data, key=lambda x: x["success_rate"])["model_name"],
                "most_used": max(models_data, key=lambda x: x["total_requests"])["model_name"],
            }
        else:
            comparison_metrics = {
                "fastest_model": None,
                "most_reliable": None,
                "highest_success_rate": None,
                "most_used": None,
            }
        
        return JsonResponse({
            "models": models_data,
            "comparison_metrics": comparison_metrics
        })
        
    except Exception as exc:
        logger.error(f"Error in model_comparison: {exc}")
        return JsonResponse({"error": "Failed to compare models"}, status=500)


@require_GET
@ratelimit(key="ip", rate="60/m")
def performance_dashboard(request):
    """
    Render performance monitoring dashboard.
    
    GET /admin/performance/
    """
    try:
        # Get top performers
        top_models = ModelPerformance.objects.filter(
            is_active=True,
            total_requests__gte=5
        ).order_by("-reliability_score")[:10]
        
        # Get recent activity
        recent_logs = ResponseLog.objects.select_related().order_by("-created_at")[:20]
        
        # Get tier distribution
        tier_stats = {}
        for tier_choice, tier_label in ModelReliability.TIER_CHOICES:
            count = ModelReliability.objects.filter(tier=tier_choice).count()
            tier_stats[tier_label] = count
        
        context = {
            "top_models": top_models,
            "recent_logs": recent_logs,
            "tier_stats": tier_stats,
            "total_models": ModelPerformance.objects.count(),
            "active_models": ModelPerformance.objects.filter(is_active=True).count(),
        }
        
        return render(request, "admin/performance_dashboard.html", context)
        
    except Exception as exc:
        logger.error(f"Error in performance_dashboard: {exc}")
        return JsonResponse({"error": "Failed to load dashboard"}, status=500)


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
    
    errors = ResponseLog.objects.filter(
        model_name=model_name,
        success=False,
        error_message__isnull=False
    ).values("error_message").annotate(
        count=Count("id")
    ).order_by("-count")[:limit]
    
    return [
        {
            "error": error["error_message"][:100],  # Truncate long errors
            "count": error["count"]
        }
        for error in errors
    ]
