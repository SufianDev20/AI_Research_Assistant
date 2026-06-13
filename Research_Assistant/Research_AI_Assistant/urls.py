"""
URL routing for Research AI Assistant.

Django URL routing: https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.urls import path
from . import views, views_performance
from .views import extract_pdf, ask_paper  # add to existing imports

# Add inside urlpatterns:
app_name = "research_ai_assistant"

urlpatterns = [
    path("", views.frontend, name="frontend"),
    path("api/", views.api_root, name="api_root"),
    path("api/search/", views.search, name="search"),
    path("api/summarise/", views.summarise, name="summarise"),
    path("api/generate_title/", views.generate_title, name="generate_title"),
    path("api/openalex/authors/", views.search_authors, name="openalex_authors_search"),
    path("api/extract-pdf/", extract_pdf, name="extract_pdf"),
    path("api/ask-paper/", ask_paper, name="ask_paper"),
    # Performance monitoring endpoints
    path(
        "api/performance/stats/",
        views_performance.model_performance_stats,
        name="performance_stats",
    ),
    path(
        "api/performance/model/", views_performance.model_details, name="model_details"
    ),
    path(
        "api/performance/compare/",
        views_performance.model_comparison,
        name="model_comparison",
    ),
    path(
        "performance/",
        views_performance.performance_dashboard,
        name="performance_dashboard",
    ),
]
