"""
Test script for the AI Research Assistant API.

Run Django server first: python manage.py runserver
Then run this script: python test_api.py
"""

import urllib.request
import json

if __name__ == "__main__":
    # Test 1: Search with relevance mode (default)
    print("=" * 60)
    print("TEST 1: Search with relevance mode")
    print("=" * 60)

    url = "http://127.0.0.1:8080/api/search/?q=deep+learning&mode=relevance&per_page=3"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print(f"Query: {data.get('query')}")
            print(f"Mode: {data.get('mode')}")
            print(f"Count: {data.get('count')}")
            print("\nFirst paper:")
            if data.get("papers"):
                paper = data["papers"][0]
                print(f"  Title: {paper.get('title')}")
                print(f"  Year: {paper.get('publication_year')}")
                print(f"  Citations: {paper.get('cited_by_count')}")
                print(f"  DOI: {paper.get('doi')}")
                print(f"  Abstract: {paper.get('abstract', '')[:100]}...")
            print("\n")
    except Exception as e:
        print(f"Error: {e}\n")

    # Test 2: Search with open_access mode
    print("=" * 60)
    print("TEST 2: Search with open_access mode")
    print("=" * 60)

    url = "http://127.0.0.1:8080/api/search/?q=machine+learning&mode=open_access&per_page=3"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print(f"Query: {data.get('query')}")
            print(f"Mode: {data.get('mode')}")
            print(f"Count: {data.get('count')}")
            print("\nAll papers are open access:")
            for i, paper in enumerate(data.get("papers", [])[:3], 1):
                print(
                    f"  {i}. {paper.get('title')} - OA: {paper.get('is_open_access')}"
                )
            print("\n")
    except Exception as e:
        print(f"Error: {e}\n")

    # Test 3: Search with best_match mode
    print("=" * 60)
    print("TEST 3: Search with best_match mode (most cited)")
    print("=" * 60)

    url = (
        "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=best_match&per_page=3"
    )

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Status: {response.status}")
            print(f"Query: {data.get('query')}")
            print(f"Mode: {data.get('mode')}")
            print(f"Count: {data.get('count')}")
            print("\nTop 3 most cited papers:")
            for i, paper in enumerate(data.get("papers", [])[:3], 1):
                print(f"  {i}. {paper.get('title')}")
                print(f"     Citations: {paper.get('cited_by_count')}")
            print("\n")
    except Exception as e:
        print(f"Error: {e}\n")

    # Test 4: Error handling - missing query
    print("=" * 60)
    print("TEST 4: Error handling - missing query parameter")
    print("=" * 60)

    url = "http://127.0.0.1:8080/api/search/"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            print(f"Should not reach here")
    except urllib.error.HTTPError as e:
        print(f"Status: {e.code} (expected 400)")
        error_data = json.loads(e.read().decode())
        print(f"Error message: {error_data.get('error')}")
        print("\n")

    print("=" * 60)
    print("All tests completed")
    print("=" * 60)
