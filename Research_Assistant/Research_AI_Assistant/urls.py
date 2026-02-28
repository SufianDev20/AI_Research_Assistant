"""
URL routing for Research AI Assistant.

Django URL routing: https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.urls import path
from . import views

app_name = "research_ai_assistant"

urlpatterns = [
    path("api/", views.api_root, name="api_root"),
    path("api/search/", views.search, name="search"),
]
