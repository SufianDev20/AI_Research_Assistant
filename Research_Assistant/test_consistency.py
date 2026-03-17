"""
Test script to check instruction consistency across different OpenRouter models.
Tests if models follow the prompt formatting rules consistently.
"""

import os
import sys
import django
from django.test import Client

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Research_AI_Assistant.settings')
django.setup()

from Research_AI_Assistant.services.openrouter_service import OpenRouterService
from Research_AI_Assistant.services.prompt_builder import build_user_message, system_prompt

def test_instruction_consistency():
    """Test if different models follow instructions consistently."""
    print("=" * 80)
    print("TESTING INSTRUCTION CONSISTENCY ACROSS MODELS")
    print("=" * 80)
    
    # Test data - same papers, same query for all models
    test_papers = [
        {
            "title": "Scikit-learn: Machine Learning in Python",
            "authors": [
                {"name": "Fabián Pedregosa", "orcid": "https://orcid.org/0000-0003-4025-3953"},
                {"name": "Gaël Varoquaux", "orcid": "https://orcid.org/0000-0003-1076-5122"},
                {"name": "Alexandre Gramfort", "orcid": "https://orcid.org/0000-0001-9791-4404"}
            ],
            "abstract": "Scikit-learn is a Python module integrating a wide range of state-of-the-art machine learning algorithms for medium-scale supervised and unsupervised problems. This package focuses on bringing machine learning to non-specialists using a general-purpose high-level language. Emphasis is put on ease of use, performance, documentation, and API consistency. It has minimal dependencies and is distributed under the simplified BSD license, encouraging its use in both academic and commercial settings.",
            "publication_year": 2012,
            "doi": "https://doi.org/10.48550/arxiv.1201.0490",
            "source": "arXiv (Cornell University)",
            "cited_by_count": 63359,
            "concepts": [
                {"name": "Python (programming language)", "score": 0.8748029470443726},
                {"name": "Machine learning", "score": 0.511991560459137}
            ]
        }
    ]
    
    test_query = "Summarize this machine learning paper"
    user_message = build_user_message(test_papers, test_query)
    
    # Test models that should work
    test_models = [
        "arcee-ai/trinity-large-preview:free",
        "stepfun/step-3.5-flash:free", 
        "google/gemma-3-4b-it:free"
    ]
    
    results = {}
    
    for model_name in test_models:
        print(f"\n{'='*60}")
        print(f"TESTING MODEL: {model_name}")
        print(f"{'='*60}")
        
        try:
            # Create service instance and force specific model
            service = OpenRouterService()
            service.model = model_name
            
            # Make request
            response = service.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                request_type="summary"
            )
            
            # Analyze response for instruction consistency
            analysis = analyze_response_consistency(response, model_name)
            results[model_name] = analysis
            
            print(f"+ Response received ({len(response)} chars)")
            print(f"Format compliance: {analysis['format_compliance']}")
            print(f"Citation format: {analysis['citation_format']}")
            print(f"Content rules: {analysis['content_rules']}")
            print(f"Word count: {analysis['word_count']}")
            
            # Show response preview
            print(f"\nResponse preview:")
            print("-" * 40)
            print(response[:500] + "..." if len(response) > 500 else response)
            print("-" * 40)
            
        except Exception as e:
            print(f"- Error: {e}")
            results[model_name] = {
                'error': str(e),
                'format_compliance': 'Failed',
                'citation_format': 'N/A',
                'content_rules': 'N/A',
                'word_count': 'N/A'
            }
    
    # Compare consistency across models
    print(f"\n{'='*80}")
    print("CONSISTENCY ANALYSIS")
    print(f"{'='*80}")
    
    compare_model_consistency(results)
    
    return results

def analyze_response_consistency(response: str, model_name: str) -> dict:
    """Analyze if response follows the instruction format."""
    
    analysis = {
        'format_compliance': 'Unknown',
        'citation_format': 'Unknown',
        'content_rules': 'Unknown',
        'word_count': len(response.split()),
        'issues': []
    }
    
    # Check for required format elements
    lines = response.split('\n')
    
    # 1. Check if papers are numbered
    has_numbered_papers = any(line.strip().startswith("Paper 1:") or "Paper 2:" in line for line in lines)
    if has_numbered_papers:
        analysis['format_compliance'] = 'Good'
    else:
        analysis['format_compliance'] = 'Poor'
        analysis['issues'].append('Missing numbered paper format')
    
    # 2. Check for Harvard citation format in References section
    references_section = False
    harvard_citations = []
    
    for i, line in enumerate(lines):
        if "References:" in line:
            references_section = True
            # Look for Harvard format in following lines
            for j in range(i+1, min(i+10, len(lines))):
                ref_line = lines[j].strip()
                if ref_line and '(' in ref_line and ')' in ref_line:
                    # Check for Harvard pattern: Author (Year) 'Title'. Source. doi: DOI
                    if 'doi:' in ref_line.lower() or ref_line.count('(') >= 2:
                        harvard_citations.append(ref_line)
    
    if references_section and harvard_citations:
        analysis['citation_format'] = 'Good'
    elif references_section:
        analysis['citation_format'] = 'Partial'
        analysis['issues'].append('References section found but incorrect format')
    else:
        analysis['citation_format'] = 'Poor'
        analysis['issues'].append('Missing References section')
    
    # 3. Check content rules
    has_paper_sections = any("Paper 1:" in line or "Paper 2:" in line for line in lines)
    has_authors_year = any("Authors:" in line for line in lines)
    has_no_markdown = not any('*' in line or '#' in line for line in lines)
    
    rule_compliance = []
    if has_paper_sections:
        rule_compliance.append('Paper sections present')
    if has_authors_year:
        rule_compliance.append('Author/Year format present')
    if has_no_markdown:
        rule_compliance.append('No markdown formatting')
    
    if len(rule_compliance) >= 2:
        analysis['content_rules'] = 'Good'
    elif len(rule_compliance) >= 1:
        analysis['content_rules'] = 'Partial'
    else:
        analysis['content_rules'] = 'Poor'
        analysis['issues'].append('Missing required content structure')
    
    # 4. Word count check (should be reasonable for summary)
    word_count = analysis['word_count']
    if 50 <= word_count <= 300:
        analysis['word_count'] = 'Appropriate'
    elif word_count < 50:
        analysis['word_count'] = 'Too Short'
        analysis['issues'].append('Summary too short')
    else:
        analysis['word_count'] = 'Too Long'
        analysis['issues'].append('Summary too long')
    
    return analysis

def compare_model_consistency(results: dict):
    """Compare consistency across different models."""
    
    print("Format Compliance Comparison:")
    for model, analysis in results.items():
        if 'error' not in analysis:
            compliance = analysis['format_compliance']
            print(f"  {model}: {compliance}")
    
    print("\nCitation Format Comparison:")
    for model, analysis in results.items():
        if 'error' not in analysis:
            citations = analysis['citation_format']
            print(f"  {model}: {citations}")
    
    print("\nContent Rules Comparison:")
    for model, analysis in results.items():
        if 'error' not in analysis:
            rules = analysis['content_rules']
            print(f"  {model}: {rules}")
    
    print("\nWord Count Comparison:")
    for model, analysis in results.items():
        if 'error' not in analysis:
            count = analysis['word_count']
            print(f"  {model}: {count}")
    
    # Identify most consistent model
    scores = {}
    for model, analysis in results.items():
        if 'error' not in analysis:
            score = 0
            if analysis['format_compliance'] == 'Good':
                score += 3
            elif analysis['format_compliance'] == 'Partial':
                score += 1
            
            if analysis['citation_format'] == 'Good':
                score += 3
            elif analysis['citation_format'] == 'Partial':
                score += 1
            
            if analysis['content_rules'] == 'Good':
                score += 2
            elif analysis['content_rules'] == 'Partial':
                score += 1
            
            if analysis['word_count'] == 'Appropriate':
                score += 2
            
            scores[model] = score
    
    if scores:
        best_model = max(scores, key=scores.get)
        print(f"\nMost Consistent Model: {best_model} (Score: {scores[best_model]}/10)")
        
        # Show consistency ranking
        print("\nConsistency Ranking:")
        ranked_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for i, (model, score) in enumerate(ranked_models, 1):
            print(f"  {i}. {model}: {score}/10")

def main():
    """Run consistency tests."""
    print("OpenRouter Model Instruction Consistency Test")
    print("Tests if different models follow prompt instructions consistently.")
    print()
    
    # Check if API key is configured
    from django.conf import settings
    if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
        print("- OPENROUTER_API_KEY not configured in settings")
        print("Please set up your .env file with a valid OpenRouter API key")
        return
    
    results = test_instruction_consistency()
    
    print(f"\n{'='*80}")
    print("CONSISTENCY TEST COMPLETE")
    print(f"{'='*80}")
    print("\nKey Findings:")
    
    successful_models = [m for m, r in results.items() if 'error' not in r]
    failed_models = [m for m, r in results.items() if 'error' in r]
    
    print(f"Models tested: {len(results)}")
    print(f"Successful responses: {len(successful_models)}")
    print(f"Failed responses: {len(failed_models)}")
    
    if successful_models:
        good_format = [m for m, r in results.items() 
                      if 'error' not in r and r['format_compliance'] == 'Good']
        print(f"Models with good format compliance: {len(good_format)}")
        
        good_citations = [m for m, r in results.items() 
                        if 'error' not in r and r['citation_format'] == 'Good']
        print(f"Models with proper citations: {len(good_citations)}")
    
    print("\nRecommendations:")
    if len(good_format) < len(successful_models):
        print("- Some models are not following format instructions consistently")
        print("- Consider prioritizing models with better compliance in reliability settings")
    
    if len(good_citations) < len(successful_models):
        print("- Citation formatting varies between models")
        print("- May need additional prompt engineering for consistency")
    
    print("- Use performance tracking to monitor consistency over time")
    print("- Consider model-specific prompts for consistently poor performers")

if __name__ == "__main__":
    main()
