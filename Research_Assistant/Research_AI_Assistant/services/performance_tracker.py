"""
Performance tracking service for OpenRouter models.
Handles model performance metrics, reliability scoring, and intelligent fallback.
"""

import logging
import hashlib
import time
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.db.models import Count

from ..models import ModelPerformance, ResponseLog, ModelReliability

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks and analyzes OpenRouter model performance for intelligent fallback decisions.
    """
    
    @staticmethod
    def log_request_start(model_name: str, request_type: str = "summary", user_query: str = None) -> str:
        """
        Log the start of a model request and return a request ID.
        
        Args:
            model_name: Name of the OpenRouter model
            request_type: Type of request (summary, title, other)
            user_query: User query for consistency analysis
            
        Returns:
            Request ID for tracking
        """
        request_id = f"{model_name}_{int(time.time() * 1000)}"
        
        # Generate hash for consistency analysis if query provided
        query_hash = None
        if user_query:
            query_hash = hashlib.sha256(user_query.encode()).hexdigest()[:64]
        
        return request_id, query_hash
    
    @staticmethod
    def log_request_success(
        model_name: str,
        request_id: str,
        request_type: str,
        response_time: float,
        response_content: str,
        query_hash: str = None
    ):
        """
        Log a successful model request and update performance metrics.
        
        Args:
            model_name: Name of the OpenRouter model
            request_id: Unique request identifier
            request_type: Type of request (summary, title, other)
            response_time: Time taken for response in seconds
            response_content: The response content
            query_hash: Hash of user query for consistency analysis
        """
        try:
            with transaction.atomic():
                # Update model performance
                perf, created = ModelPerformance.objects.get_or_create(
                    model_name=model_name,
                    defaults={
                        'total_requests': 1,
                        'successful_requests': 1,
                        'avg_response_time': response_time,
                        'total_response_time': response_time,
                        'last_success': timezone.now(),
                        'consecutive_failures': 0,
                        'is_active': True
                    }
                )
                
                # Validate format compliance for new records too
                required_fields = ["Authors:", "Year:", "Source:", "DOI:", "Summary:", "References:"]
                passed_format_check = all(field in response_content for field in required_fields)
                
                if created:
                    # Update format compliance for new record
                    perf.update_format_compliance(passed_format_check)
                    perf.update_reliability_score()
                    perf.save()
                
                if not created:
                    # Update existing performance record
                    perf.total_requests += 1
                    perf.successful_requests += 1
                    perf.total_response_time += response_time
                    perf.avg_response_time = perf.total_response_time / perf.total_requests
                    perf.last_success = timezone.now()
                    perf.consecutive_failures = 0
                    
                    # Update format compliance metrics
                    perf.update_format_compliance(passed_format_check)
                    
                    # Update reliability score
                    perf.update_reliability_score()
                    perf.save()
                
                # Log detailed response
                ResponseLog.objects.create(
                    model_name=model_name,
                    request_type=request_type,
                    success=True,
                    response_time=response_time,
                    response_length=len(response_content) if response_content else 0,
                    user_query_hash=query_hash
                )
                
                logger.info(f"Logged success for {model_name}: {response_time:.2f}s, reliability: {perf.reliability_score:.2f}")
                
        except Exception as e:
            logger.error(f"Failed to log success for {model_name}: {e}")
    
    @staticmethod
    def log_request_failure(
        model_name: str,
        request_id: str,
        request_type: str,
        response_time: float,
        error_message: str,
        query_hash: str = None
    ):
        """
        Log a failed model request and update performance metrics.
        
        Args:
            model_name: Name of the OpenRouter model
            request_id: Unique request identifier
            request_type: Type of request (summary, title, other)
            response_time: Time taken before failure in seconds
            error_message: Error message from the failure
            query_hash: Hash of user query for consistency analysis
        """
        try:
            with transaction.atomic():
                # Update model performance
                perf, created = ModelPerformance.objects.get_or_create(
                    model_name=model_name,
                    defaults={
                        'total_requests': 1,
                        'failed_requests': 1,
                        'avg_response_time': response_time,
                        'total_response_time': response_time,
                        'last_failure': timezone.now(),
                        'consecutive_failures': 1,
                        'is_active': True
                    }
                )
                
                if not created:
                    # Update existing performance record
                    perf.total_requests += 1
                    perf.failed_requests += 1
                    perf.total_response_time += response_time
                    perf.avg_response_time = perf.total_response_time / perf.total_requests
                    perf.last_failure = timezone.now()
                    perf.consecutive_failures += 1
                    
                    # Check if circuit breaker should be triggered
                    reliability = ModelReliability.objects.filter(model_name=model_name).first()
                    if reliability and perf.consecutive_failures >= reliability.circuit_breaker_threshold:
                        perf.is_active = False
                        logger.warning(f"Circuit breaker triggered for {model_name} after {perf.consecutive_failures} consecutive failures")
                    
                    # Update reliability score
                    perf.update_reliability_score()
                    perf.save()
                
                # Log detailed response
                ResponseLog.objects.create(
                    model_name=model_name,
                    request_type=request_type,
                    success=False,
                    response_time=response_time,
                    error_message=error_message[:500],  # Truncate long error messages
                    user_query_hash=query_hash
                )
                
                logger.info(f"Logged failure for {model_name}: {response_time:.2f}s, consecutive failures: {perf.consecutive_failures}")
                
        except Exception as e:
            logger.error(f"Failed to log failure for {model_name}: {e}")
    
    @staticmethod
    def get_intelligent_model_order(free_models: List[str]) -> List[str]:
        """
        Get models ordered by reliability and performance.
        
        Args:
            free_models: List of available free model names
            
        Returns:
            List of model names ordered by reliability
        """
        try:
            # Get model reliability configuration
            reliability_models = ModelReliability.objects.filter(
                model_name__in=free_models,
                tier__in=['primary', 'secondary', 'emergency']
            ).order_by('tier', 'priority', 'model_name')
            
            # Get performance data
            performance_models = ModelPerformance.objects.filter(
                model_name__in=free_models,
                is_active=True
            ).order_by('-reliability_score', '-successful_requests')
            
            # Create a scoring system
            model_scores = {}
            
            # Base scores from reliability configuration
            tier_scores = {'primary': 1000, 'secondary': 500, 'emergency': 100}
            for rel_model in reliability_models:
                base_score = tier_scores.get(rel_model.tier, 100) - rel_model.priority
                model_scores[rel_model.model_name] = base_score
            
            # Boost scores based on actual performance
            for perf_model in performance_models:
                if perf_model.model_name in model_scores:
                    # Add performance bonus
                    performance_bonus = perf_model.reliability_score * 500
                    model_scores[perf_model.model_name] += performance_bonus
                else:
                    # New model not in reliability config
                    model_scores[perf_model.model_name] = perf_model.reliability_score * 300
            
            # Sort models by score (highest first)
            sorted_models = sorted(
                model_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Return just the model names
            ordered_models = [model for model, score in sorted_models]
            
            # Add any remaining models that weren't scored
            for model in free_models:
                if model not in ordered_models:
                    ordered_models.append(model)
            
            logger.info(f"Intelligent model order: {ordered_models[:5]}...")  # Log first 5
            return ordered_models
            
        except Exception as e:
            logger.error(f"Failed to get intelligent model order, using fallback: {e}")
            return free_models
    
    @staticmethod
    def get_model_temperature(model_name: str, default_temperature: float = 0.3) -> float:
        """
        Get the optimal temperature for a specific model.
        
        Args:
            model_name: Name of the OpenRouter model
            default_temperature: Default temperature if no custom setting
            
        Returns:
            Temperature value for the model
        """
        try:
            reliability = ModelReliability.objects.filter(model_name=model_name).first()
            if reliability and reliability.custom_temperature is not None:
                return reliability.custom_temperature
            return default_temperature
        except Exception as e:
            logger.error(f"Failed to get custom temperature for {model_name}: {e}")
            return default_temperature
    
    @staticmethod
    def get_model_stats() -> Dict:
        """
        Get comprehensive model performance statistics.
        
        Returns:
            Dictionary with model performance statistics
        """
        try:
            stats = {
                'total_models': ModelPerformance.objects.count(),
                'active_models': ModelPerformance.objects.filter(is_active=True).count(),
                'models_by_tier': {},
                'top_performers': [],
                'recent_failures': []
            }
            
            # Models by tier
            for tier_choice, tier_label in ModelReliability.TIER_CHOICES:
                count = ModelReliability.objects.filter(tier=tier_choice).count()
                stats['models_by_tier'][tier_label] = count
            
            # Top performers
            top_models = ModelPerformance.objects.filter(
                is_active=True,
                total_requests__gte=5  # At least 5 requests
            ).order_by('-reliability_score')[:5]
            
            stats['top_performers'] = [
                {
                    'model': model.model_name,
                    'reliability_score': round(model.reliability_score, 3),
                    'success_rate': round(model.success_rate, 1),
                    'avg_response_time': round(model.avg_response_time, 2),
                    'total_requests': model.total_requests
                }
                for model in top_models
            ]
            
            # Recent failures
            recent_failures = ResponseLog.objects.filter(
                success=False,
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).values('model_name').annotate(
                failure_count=Count('id')
            ).order_by('-failure_count')[:5]
            
            stats['recent_failures'] = list(recent_failures)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get model stats: {e}")
            return {'error': str(e)}
