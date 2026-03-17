"""
Quick test to check instruction consistency across models.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Research_AI_Assistant.settings')
django.setup()

from Research_AI_Assistant.services.openrouter_service import OpenRouterService
from Research_AI_Assistant.services.prompt_builder import build_user_message, system_prompt

def test_single_model():
    """Test one model for instruction consistency."""
    
    # Simple test data
    test_papers = [
        {
            "title": "Machine Learning Basics",
            "authors": [{"name": "John Doe"}],
            "abstract": "This paper explains machine learning fundamentals.",
            "publication_year": 2020,
            "doi": "https://doi.org/10.1000/test",
            "source": "Test Journal",
            "cited_by_count": 100
        }
    ]
    
    user_message = build_user_message(test_papers, "Summarize this paper")
    
    try:
        service = OpenRouterService()
        response = service.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            request_type="summary"
        )
        
        print("RESPONSE RECEIVED:")
        print("=" * 50)
        print(response)
        print("=" * 50)
        
        # Quick consistency checks
        print("\nCONSISTENCY CHECKS:")
        
        # Check for required elements
        if "Paper 1:" in response:
            print("+ Has numbered paper format")
        else:
            print("- Missing numbered paper format")
        
        if "Authors:" in response:
            print("+ Has authors section")
        else:
            print("- Missing authors section")
        
        if "Year:" in response:
            print("+ Has year section")
        else:
            print("- Missing year section")
        
        if "References:" in response:
            print("+ Has references section")
        else:
            print("- Missing references section")
        
        # Check for no markdown
        if not any(char in response for char in ['*', '#', '`']):
            print("+ No markdown formatting")
        else:
            print("- Contains markdown formatting")
        
        # Check word count
        word_count = len(response.split())
        if 50 <= word_count <= 200:
            print(f"+ Appropriate length ({word_count} words)")
        else:
            print(f"- Inappropriate length ({word_count} words)")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("Quick Instruction Consistency Test")
    print("Testing if models follow prompt instructions correctly.")
    print()
    
    # Check API key
    from django.conf import settings
    if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY not configured")
        return
    
    # Test with default model (will use intelligent fallback)
    print("Testing with intelligent model selection...")
    success = test_single_model()
    
    if success:
        print("\nTest completed successfully!")
        print("You can now:")
        print("1. Check if response follows the required format")
        print("2. Look for proper Harvard citations in References")
        print("3. Verify no markdown formatting is used")
        print("4. Check word count is reasonable")
    else:
        print("\nTest failed - check error messages above")

if __name__ == "__main__":
    main()
