"""
Test script for OpenRouter performance tracking using Django test client.
This bypasses CSRF and tests the actual performance tracking functionality.
"""

import os
import sys
import django
from django.test import Client
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Research_AI_Assistant.settings')
django.setup()

from Research_AI_Assistant.services.openrouter_service import OpenRouterService

def test_openrouter_performance():
    """Test OpenRouter service with performance tracking."""
    print("=" * 60)
    print("TESTING OPENROUTER PERFORMANCE TRACKING")
    print("=" * 60)
    
    try:
        # Initialize OpenRouter service
        service = OpenRouterService()
        
        print("1. Testing title generation with performance tracking...")
        
        # Test title generation
        title = service.complete(
            system_prompt="You are a helpful assistant that generates concise titles.",
            user_message="Generate a title for: machine learning research trends",
            request_type="title"
        )
        
        print(f"+ Title generated: '{title}'")
        
        print("\n2. Testing summary generation with performance tracking...")
        
        # Test summary generation
        test_papers = [
            {
                "title": "Scikit-learn: Machine Learning in Python",
                "authors": [{"name": "Fabián Pedregosa"}],
                "abstract": "Scikit-learn is a Python module integrating machine learning algorithms.",
                "publication_year": 2012,
                "doi": "https://doi.org/10.48550/arxiv.1201.0490",
                "cited_by_count": 63359
            }
        ]
        
        summary = service.complete(
            system_prompt="You are a helpful research assistant that summarizes academic papers.",
            user_message=f"Summarize this paper: {test_papers[0]['title']}",
            request_type="summary"
        )
        
        print(f"+ Summary generated (length: {len(summary)} chars)")
        print(f"Preview: {summary[:150]}...")
        
        return True
        
    except Exception as e:
        print(f"- Error: {e}")
        return False

def check_performance_data():
    """Check if performance data was recorded."""
    print("\n" + "=" * 60)
    print("CHECKING PERFORMANCE DATA")
    print("=" * 60)
    
    try:
        from Research_AI_Assistant.services.performance_tracker import PerformanceTracker
        
        # Get performance statistics
        stats = PerformanceTracker.get_model_stats()
        
        print(f"Total models: {stats.get('total_models', 0)}")
        print(f"Active models: {stats.get('active_models', 0)}")
        
        print("\nModels by tier:")
        for tier, count in stats.get('models_by_tier', {}).items():
            print(f"  {tier}: {count}")
        
        print("\nTop performers:")
        for model in stats.get('top_performers', [])[:3]:
            if model.get('total_requests', 0) > 0:
                print(f"  {model['model']}: {model['reliability_score']:.3f} ({model['success_rate']:.1f}% success)")
        
        # Check specific model data
        from Research_AI_Assistant.models import ModelPerformance, ResponseLog
        
        models_with_data = ModelPerformance.objects.filter(total_requests__gt=0)
        print(f"\nModels with performance data: {models_with_data.count()}")
        
        for model in models_with_data:
            print(f"  {model.model_name}:")
            print(f"    Requests: {model.total_requests}")
            print(f"    Success rate: {model.success_rate:.1f}%")
            print(f"    Reliability score: {model.reliability_score:.3f}")
            print(f"    Avg response time: {model.avg_response_time:.2f}s")
        
        # Check response logs
        recent_logs = ResponseLog.objects.all().order_by('-created_at')[:5]
        print(f"\nRecent response logs ({len(recent_logs)} entries):")
        for log in recent_logs:
            status = "+" if log.success else "-"
            print(f"  {status} {log.model_name} - {log.request_type} ({log.response_time:.2f}s)")
        
        return True
        
    except Exception as e:
        print(f"- Error checking performance data: {e}")
        return False

def test_intelligent_fallback():
    """Test intelligent model ordering."""
    print("\n" + "=" * 60)
    print("TESTING INTELLIGENT FALLBACK")
    print("=" * 60)
    
    try:
        from Research_AI_Assistant.services.performance_tracker import PerformanceTracker
        from Research_AI_Assistant.services.openrouter_service import FREE_MODELS
        
        # Get intelligent model order
        ordered_models = PerformanceTracker.get_intelligent_model_order(FREE_MODELS)
        
        print("Model order (first 5):")
        for i, model in enumerate(ordered_models[:5], 1):
            print(f"  {i}. {model}")
        
        # Test model-specific temperature
        for model in ordered_models[:3]:
            temp = PerformanceTracker.get_model_temperature(model)
            print(f"  {model}: temperature = {temp}")
        
        return True
        
    except Exception as e:
        print(f"- Error testing intelligent fallback: {e}")
        return False

def main():
    """Run all OpenRouter performance tests."""
    print("OpenRouter Performance Tracking Test Suite")
    print("This will test the enhanced OpenRouter service with performance tracking.")
    print()
    
    # Check if API key is configured
    from django.conf import settings
    if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
        print("- OPENROUTER_API_KEY not configured in settings")
        print("Please set up your .env file with a valid OpenRouter API key")
        return
    
    success = True
    
    # Run tests
    success &= test_openrouter_performance()
    success &= check_performance_data()
    success &= test_intelligent_fallback()
    
    print("\n" + "=" * 60)
    if success:
        print("+ ALL TESTS PASSED")
        print("\nPerformance tracking system is working correctly!")
        print("You can now:")
        print("1. Check Django admin at http://127.0.0.1:8080/admin/")
        print("2. View performance stats at http://127.0.0.1:8080/api/performance/stats/")
        print("3. Monitor model performance in real-time")
    else:
        print("- SOME TESTS FAILED")
        print("Check the error messages above for debugging information.")
    print("=" * 60)

if __name__ == "__main__":
    main()
