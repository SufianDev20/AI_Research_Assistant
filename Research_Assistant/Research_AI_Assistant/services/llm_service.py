"""
Single entry point for every LLM call in the app.

    llm = get_llm()
    text = llm.complete(system_prompt=..., user_message=..., ...)

LLM_BACKEND (settings / .env) selects the provider:
    openrouter             OpenRouter only (previous behaviour; the default)
    ollama                 Ollama on the university server only
    ollama_then_openrouter Ollama first; OpenRouter only if Ollama fails

To drop OpenRouter entirely, set LLM_BACKEND=ollama and delete
openrouter_service.py (see the migration notes in the README).
"""

import logging
from typing import Callable, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

VALID_BACKENDS = ("openrouter", "ollama", "ollama_then_openrouter")


class LLMError(Exception):
    """Base class for every LLM failure. Views catch this one type."""


def _make_openrouter():
    # Imported lazily so the module can be deleted once OpenRouter is removed.
    from .openrouter_service import OpenRouterService

    return OpenRouterService()


def _make_ollama():
    from .ollama_service import OllamaService

    return OllamaService()


class FallbackLLM:
    """Try the primary backend; on LLMError try the secondary one."""

    def __init__(self, primary, secondary_factory: Callable):
        self._primary = primary
        self._secondary_factory = secondary_factory

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        request_type: str = "summary",
        response_validator: Optional[Callable[[str], None]] = None,
    ) -> str:
        kwargs = dict(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            request_type=request_type,
            response_validator=response_validator,
        )
        try:
            result = self._primary.complete(**kwargs)
            logger.info("LLM answered by Ollama (request_type=%s).", request_type)
            return result
        except LLMError as primary_error:
            logger.warning(
                "SWITCHING TO OPENROUTER for request_type=%s: Ollama failed (%s).",
                request_type,
                primary_error,
            )
            try:
                secondary = self._secondary_factory()
                result = secondary.complete(**kwargs)
                logger.warning(
                    "LLM answered by OpenRouter fallback (request_type=%s).",
                    request_type,
                )
                return result
            except LLMError as secondary_error:
                raise LLMError(
                    f"All LLM backends failed. Primary: {primary_error}. "
                    f"Fallback: {secondary_error}"
                ) from secondary_error


def get_llm():
    backend = (getattr(settings, "LLM_BACKEND", "openrouter") or "openrouter").strip()
    if backend not in VALID_BACKENDS:
        raise LLMError(
            f"Invalid LLM_BACKEND '{backend}'. Use one of: {', '.join(VALID_BACKENDS)}."
        )
    if backend == "openrouter":
        return _make_openrouter()
    if backend == "ollama":
        return _make_ollama()
    try:
        primary = _make_ollama()
    except LLMError as exc:
        # No research server configured: degrade to OpenRouter instead of
        # failing every request.
        logger.warning(
            "SWITCHING TO OPENROUTER: Ollama not configured (%s); using OpenRouter only.",
            exc,
        )
        return _make_openrouter()
    return FallbackLLM(primary, _make_openrouter)
