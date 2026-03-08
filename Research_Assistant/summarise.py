#!/usr/bin/env python3
"""
AI Research Assistant - Generate individual paper summaries.
"""

import requests
import sys
import os
from pathlib import Path

# Load API key from .env file
API_KEY = None
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")
env_path = Path(__file__).resolve().parent / '.env'

if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            if line.startswith('OPENROUTER_API_KEY='):
                API_KEY = line.split('=', 1)[1].strip()
                break

def get_metadata(query, per_page=3):
    """Fetch paper metadata from OpenAlex."""
    url = f"{BASE_URL}/api/search/"
    params = {"q": query, "per_page": per_page}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["papers"]

def summarise_papers(query, papers):
    """Generate individual summaries for each paper."""
    url = f"{BASE_URL}/api/summarise/"
    payload = {"query": query, "papers": papers}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["summary"]
    except requests.exceptions.HTTPError as e:
        print(f"Error generating summaries: {e}")
        return None

def main():
    """Get user query and generate individual paper summaries."""
    if len(sys.argv) < 2:
        print("Usage: python summarise.py \"your research query\"")
        return
    
    query = sys.argv[1]
    
    try:
        # Get papers from OpenAlex
        papers = get_metadata(query, per_page=5)
        
        if not papers:
            print("No papers found for this query.")
            return
        
        # Generate summaries
        summary = summarise_papers(query, papers)
        
        if summary:
            print(summary)
        else:
            print("Error: Could not generate summaries.")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
