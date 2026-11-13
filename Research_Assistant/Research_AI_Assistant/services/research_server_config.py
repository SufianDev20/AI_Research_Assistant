"""
Shared config reader for the two clients of the university research server
(local_corpus_service.py's paper search, ollama_service.py's LLM calls) —
both gated by the same two settings.
"""

from typing import Tuple

from django.conf import settings


def research_server_config() -> Tuple[str, str]:
    """Returns (base_url, api_key); either is "" if unset."""
    base_url = (getattr(settings, "RESEARCH_API_URL", "") or "").rstrip("/")
    api_key = getattr(settings, "RESEARCH_API_KEY", "") or ""
    return base_url, api_key
