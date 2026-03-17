"""
Test script for OpenRouter performance tracking system.
Tests model reliability, performance tracking, and intelligent fallback.
"""

import json
import time
import urllib.request
import urllib.parse
from typing import Dict, List

def test_api_endpoint(url: str, data: Dict = None, method: str = "GET") -> Dict:
    """
    Test an API endpoint and return the response.
    
    Args:
        url: API endpoint URL
        data: Request data (for POST requests)
        method: HTTP method (GET or POST)
        
    Returns:
        Response data as dictionary
    """
    try:
        if method == "GET":
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())
        elif method == "POST":
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

def test_performance_stats():
    """Test the performance statistics endpoint."""
    print("=" * 60)
    print("TEST 1: Performance Statistics")
    print("=" * 60)
    
    url = "http://127.0.0.1:8080/api/performance/stats/"
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print(f"Total models: {data.get('total_models', 'N/A')}")
            print(f"Active models: {data.get('active_models', 'N/A')}")
            
            print("\nModels by tier:")
            for tier, count in data.get('models_by_tier', {}).items():
                print(f"  {tier}: {count}")
            
            print("\nTop performers:")
            for model in data.get('top_performers', [])[:3]:
                print(f"  {model['model']}: {model['reliability_score']:.3f} ({model['success_rate']:.1f}% success)")
            
            print("\nPerformance summary:")
            summary = data.get('performance_summary', {})
            print(f"  Avg success rate: {summary.get('avg_success_rate', 0):.1f}%")
            print(f"  Avg response time: {summary.get('avg_response_time', 0):.2f}s")
            print(f"  Today's requests: {summary.get('total_requests_today', 0)}")
            
    except Exception as e:
        print(f"Error: {e}")

def test_model_details():
    """Test the model details endpoint."""
    print("\n" + "=" * 60)
    print("TEST 2: Model Details")
    print("=" * 60)
    
    model_name = "arcee-ai/trinity-large-preview:free"
    url = f"http://127.0.0.1:8080/api/performance/model/?model_name={urllib.parse.quote(model_name)}"
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print(f"Model: {data.get('model_name', 'N/A')}")
            
            perf = data.get('performance', {})
            print(f"Success rate: {perf.get('success_rate', 0):.1f}%")
            print(f"Reliability score: {perf.get('reliability_score', 0):.3f}")
            print(f"Total requests: {perf.get('total_requests', 0)}")
            print(f"Avg response time: {perf.get('avg_response_time', 0):.2f}s")
            
            reliability = data.get('reliability', {})
            if reliability:
                print(f"Tier: {reliability.get('tier', 'N/A')}")
                print(f"Priority: {reliability.get('priority', 'N/A')}")
                print(f"Custom temperature: {reliability.get('custom_temperature', 'N/A')}")
            
            recent_logs = data.get('recent_logs', [])
            print(f"Recent logs: {len(recent_logs)} entries")
            
    except Exception as e:
        print(f"Error: {e}")

def test_model_comparison():
    """Test the model comparison endpoint."""
    print("\n" + "=" * 60)
    print("TEST 3: Model Comparison")
    print("=" * 60)
    
    models = ["arcee-ai/trinity-large-preview:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-4b-it:free"]
    models_param = ",".join(models)
    url = f"http://127.0.0.1:8080/api/performance/compare/?models={urllib.parse.quote(models_param)}"
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            
            print("\nModel comparison:")
            for model in data.get('models', []):
                print(f"  {model['model_name']}:")
                print(f"    Success rate: {model['success_rate']:.1f}%")
                print(f"    Reliability: {model['reliability_score']:.3f}")
                print(f"    Response time: {model['avg_response_time']:.2f}s")
                print(f"    Tier: {model['tier']}")
            
            print("\nComparison metrics:")
            metrics = data.get('comparison_metrics', {})
            print(f"  Fastest model: {metrics.get('fastest_model', 'N/A')}")
            print(f"  Most reliable: {metrics.get('most_reliable', 'N/A')}")
            print(f"  Highest success rate: {metrics.get('highest_success_rate', 'N/A')}")
            print(f"  Most used: {metrics.get('most_used', 'N/A')}")
            
    except Exception as e:
        print(f"Error: {e}")

def test_intelligent_fallback():
    """Test the intelligent fallback by making a summary request."""
    print("\n" + "=" * 60)
    print("TEST 4: Intelligent Fallback Test")
    print("=" * 60)
    
    # First, search for some papers
    search_url = "http://127.0.0.1:8080/api/search/?q=machine+learning&per_page=2"
    
    try:
        print("Step 1: Searching for papers...")
        with urllib.request.urlopen(search_url) as response:
            search_data = json.loads(response.read().decode())
            papers = search_data.get('papers', [])
            
            if not papers:
                print("No papers found for testing")
                return
            
            print(f"Found {len(papers)} papers for testing")
            
            # Step 2: Generate a summary (this will trigger performance tracking)
            summary_url = "http://127.0.0.1:8080/api/summarise/"
            summary_data = {
                "query": "What are the main trends in machine learning?",
                "papers": papers[:2]  # Use first 2 papers
            }
            
            print("\nStep 2: Generating summary (with performance tracking)...")
            start_time = time.time()
            
            req = urllib.request.Request(
                summary_url,
                data=json.dumps(summary_data).encode(),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req) as response:
                summary_result = json.loads(response.read().decode())
                end_time = time.time()
                
                print(f"Status: {response.status}")
                print(f"Response time: {end_time - start_time:.2f}s")
                print(f"Summary length: {len(summary_result.get('summary', ''))} characters")
                
                if 'summary' in summary_result:
                    print("✓ Summary generated successfully")
                    print(f"Preview: {summary_result['summary'][:200]}...")
                else:
                    print("✗ Summary generation failed")
                    print(f"Error: {summary_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error: {e}")

def test_performance_after_requests():
    """Check performance stats after making requests."""
    print("\n" + "=" * 60)
    print("TEST 5: Performance After Requests")
    print("=" * 60)
    
    # Wait a moment for any async processing
    time.sleep(2)
    
    url = "http://127.0.0.1:8080/api/performance/stats/"
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            
            print("Updated performance statistics:")
            summary = data.get('performance_summary', {})
            print(f"  Total requests today: {summary.get('total_requests_today', 0)}")
            print(f"  Avg success rate: {summary.get('avg_success_rate', 0):.1f}%")
            print(f"  Avg response time: {summary.get('avg_response_time', 0):.2f}s")
            
            print("\nTop performers after test:")
            for model in data.get('top_performers', [])[:3]:
                if model['total_requests'] > 0:  # Only show models with actual requests
                    print(f"  {model['model']}: {model['reliability_score']:.3f} ({model['success_rate']:.1f}% success, {model['total_requests']} requests)")
            
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Run all performance tracking tests."""
    print("OpenRouter Performance Tracking System Test")
    print("Make sure your Django server is running on http://127.0.0.1:8080")
    print()
    
    # Run tests
    test_performance_stats()
    test_model_details()
    test_model_comparison()
    test_intelligent_fallback()
    test_performance_after_requests()
    
    print("\n" + "=" * 60)
    print("All performance tests completed")
    print("=" * 60)
    print("\nTo view detailed performance data:")
    print("1. Visit Django admin: http://127.0.0.1:8080/admin/")
    print("2. Check Model Performance and Response Log sections")
    print("3. Use the performance dashboard: http://127.0.0.1:8080/admin/performance/")

if __name__ == "__main__":
    main()
