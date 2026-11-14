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


class _StreamReset:
    """Type of STREAM_RESET; a class so the marker has a readable repr."""

    def __repr__(self):
        return "STREAM_RESET"


# Yielded by a stream_complete() generator in place of a token when it moves
# on to another model or backend after already yielding tokens. Everything
# yielded before it belongs to an answer that failed and must be discarded.
STREAM_RESET = _StreamReset()


def _make_openrouter():
    # Imported lazily so the module can be deleted once OpenRouter is removed.
    from .openrouter_service import OpenRouterService

    return OpenRouterService()


def _make_ollama():
    from .ollama_service import OllamaService

    return OllamaService()


class FallbackLLM:
    """Try the primary backend; on LLMError try the secondary one."""

    def __init__(
        self,
        primary,
        secondary_factory: Callable,
        primary_label: str = "primary",
        secondary_label: str = "secondary",
    ):
        self._primary = primary
        self._secondary_factory = secondary_factory
        self._primary_label = primary_label
        self._secondary_label = secondary_label

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
            logger.info(
                "LLM answered by %s (request_type=%s).",
                self._primary_label,
                request_type,
            )
            return result
        except LLMError as primary_error:
            logger.warning(
                "SWITCHING TO %s for request_type=%s: %s failed (%s).",
                self._secondary_label.upper(),
                request_type,
                self._primary_label,
                primary_error,
            )
            try:
                secondary = self._secondary_factory()
                result = secondary.complete(**kwargs)
                logger.warning(
                    "LLM answered by %s fallback (request_type=%s).",
                    self._secondary_label,
                    request_type,
                )
                return result
            except LLMError as secondary_error:
                raise LLMError(
                    f"All LLM backends failed. {self._primary_label}: {primary_error}. "
                    f"{self._secondary_label} fallback: {secondary_error}"
                ) from secondary_error

    def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        request_type: str = "summary",
        response_validator: Optional[Callable[[str], None]] = None,
    ):
        kwargs = dict(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            request_type=request_type,
            response_validator=response_validator,
        )
        primary_sent_tokens = False
        try:
            for token in self._primary.stream_complete(**kwargs):
                primary_sent_tokens = True
                yield token
            logger.info(
                "LLM stream answered by %s (request_type=%s).",
                self._primary_label,
                request_type,
            )
        except LLMError as primary_error:
            logger.warning(
                "SWITCHING TO %s stream for request_type=%s: %s failed (%s).",
                self._secondary_label.upper(),
                request_type,
                self._primary_label,
                primary_error,
            )
            # The caller already holds the primary's partial answer.
            if primary_sent_tokens:
                yield STREAM_RESET
            try:
                secondary = self._secondary_factory()
                yield from secondary.stream_complete(**kwargs)
            except LLMError as secondary_error:
                raise LLMError(
                    f"All LLM backends failed. {self._primary_label}: {primary_error}. "
                    f"{self._secondary_label} fallback: {secondary_error}"
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
    return FallbackLLM(
        primary, _make_openrouter, primary_label="Ollama", secondary_label="OpenRouter"
    )
