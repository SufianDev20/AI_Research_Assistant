"""
This is the OpenRouter API logic for LLM inference
Sends structured paper metadata to a free OpenRouter model and returns a Harvard-style cited summary.

References:
1)OpenRouter QuickStart: https://openrouter.ai/docs/quickstart
2)OpenRouter API overview:https://openrouter.ai/docs/api/reference/overview
"""

import json
import logging
import time
from typing import Callable, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache

from .llm_service import LLMError, STREAM_RESET
from .performance_tracker import PerformanceTracker
from ..request_types import JSON_REQUEST_TYPES

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default free model.
# Browse free models at https://openrouter.ai/models?max_price=0
DEFAULT_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_MAX_MODELS_PER_REQUEST = 10

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
FREE_MODELS_CACHE_KEY = "openrouter:free_models"
REASONING_MODELS_CACHE_KEY = "openrouter:free_reasoning_models"

# Q&A limits. Each free-model attempt counts against OpenRouter's daily
# free-request quota (50/day under 10 credits), and a 10-model walk on one
# question also kept the browser waiting for minutes.
DEFAULT_QA_MAX_MODELS = 4
DEFAULT_QA_DEADLINE_SECONDS = 90
# Not worth starting another model with less time than this left.
MIN_ATTEMPT_SECONDS = 5
DEFAULT_MODELS_CACHE_SECONDS = 6 * 60 * 60
MODELS_FETCH_TIMEOUT = 10

# "openrouter/free" routes to a random free model, so it is only ever a last
# resort and is pushed to the end of the discovered list.
LAST_RESORT_MODEL = "openrouter/free"

# Confirmed exceptions: models the supported_parameters/output_modalities
# check cannot catch because they genuinely expose a full chat-completion
# parameter set (max_tokens, temperature, ...) while actually being
# special-purpose moderation/guardrail models, not chat models. This is a
# short list of specific, verified ids, not a pattern — each entry here was
# confirmed against a live OpenRouter response (not guessed), and a model
# only belongs here if letting it into the fallback chain would actually
# misbehave (e.g. a moderation verdict returned where a research answer was
# expected), not merely "sounds unrelated to research".
KNOWN_NON_CHAT_MODEL_IDS = {
    # Verified 2026-10-23: supported_parameters includes max_tokens/temperature
    # (so the generic filter below keeps it), but it is NVIDIA's guardrail
    # model for moderating LLM/VLM input and output, not a chat model.
    "nvidia/nemotron-3.5-content-safety:free",
}


def _as_bool(value, default: bool = False) -> bool:
    """Read a setting that may arrive from .env as a string."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _is_reasoning_model(entry: dict) -> bool:
    """
    True when the models API says the model reasons. A `reasoning` object
    is present only for models with reasoning configuration, and
    supported_parameters lists "reasoning"/"include_reasoning" for them.
    complete() sends reasoning.effort="low" to every model, which switches
    reasoning on for optional-reasoning models too, so both count.

    Reference: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
    """
    if isinstance(entry.get("reasoning"), dict):
        return True
    params = entry.get("supported_parameters") or []
    return "reasoning" in params or "include_reasoning" in params


def reasoning_model_ids() -> set:
    """Free model ids recorded as reasoning models by the last discovery.

    Empty when nothing is cached (e.g. OPENROUTER_MODELS overrides
    discovery), which leaves the model order unchanged.
    """
    return set(cache.get(REASONING_MODELS_CACHE_KEY) or ())


def fetch_free_models() -> List[str]:
    """
    Discover the currently available free models from the OpenRouter API.

    There is no hand-maintained model list to go stale here: every free
    model id and every exclusion comes straight from the live API response,
    so a model OpenRouter adds or withdraws is reflected on the next cache
    refresh with no code change.

    Keeps only ids ending in ":free". Excludes a model only on positive
    evidence it cannot hold a chat completion: `output_modalities` present
    and missing "text", or `supported_parameters` present and missing every
    generation parameter a chat completion needs (`max_tokens`/
    `temperature`) — this is what filters out classifiers, guard/moderation
    models and embedders, using OpenRouter's own reported capabilities
    instead of a hand-maintained keyword list. A model missing either field
    entirely is kept (benefit of doubt, since OpenRouter doesn't document
    these as always present). Orders the survivors by context window
    descending so the largest window is tried first, and pushes
    LAST_RESORT_MODEL to the end. The result is cached, so discovery costs
    one HTTP request every OPENROUTER_MODELS_CACHE_SECONDS rather than one
    per completion.

    Returns:
        Ordered list of free model ids.

    Raises:
        OpenRouterAPIError: if the API cannot be reached or returns nothing
        usable. There is no built-in fallback list to degrade to, so a
        discovery outage surfaces the same way any other OpenRouter failure
        does — propagating out of OpenRouterService.complete() to the view,
        which already maps OpenRouterAPIError to a 502/503.

    Reference: https://openrouter.ai/docs/api/reference/list-available-models
    """
    cached = cache.get(FREE_MODELS_CACHE_KEY)
    if cached:
        return cached

    try:
        api_key = getattr(settings, "OPENROUTER_API_KEY", "")
        response = requests.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=MODELS_FETCH_TIMEOUT,
        )
        payload = response.json()
        entries = payload.get("data") or []

        # Every attribute below except "id" is optional in the response, so a
        # missing key means "keep": a model is only excluded on positive
        # evidence that it is unusable.
        usable = []
        reasoning = []
        for entry in entries:
            model_id = (entry or {}).get("id") or ""
            if not model_id.endswith(":free"):
                continue
            if model_id in KNOWN_NON_CHAT_MODEL_IDS:
                continue
            outputs = (entry.get("architecture") or {}).get("output_modalities")
            if outputs and "text" not in outputs:
                continue
            supported_params = entry.get("supported_parameters")
            if supported_params is not None and not any(
                p in supported_params for p in ("max_tokens", "temperature")
            ):
                continue
            usable.append((model_id, entry.get("context_length") or 0))
            if _is_reasoning_model(entry):
                reasoning.append(model_id)

        if not usable:
            raise OpenRouterAPIError("OpenRouter returned no usable free models.")

        usable.sort(key=lambda item: item[1], reverse=True)
        models = [model_id for model_id, _ in usable]

        if LAST_RESORT_MODEL in models:
            models.remove(LAST_RESORT_MODEL)
            models.append(LAST_RESORT_MODEL)

        cache_seconds = getattr(
            settings,
            "OPENROUTER_MODELS_CACHE_SECONDS",
            DEFAULT_MODELS_CACHE_SECONDS,
        )
        # Written first so it is never older than the model list it describes.
        cache.set(REASONING_MODELS_CACHE_KEY, reasoning, cache_seconds)
        cache.set(FREE_MODELS_CACHE_KEY, models, cache_seconds)
        logger.info("Discovered %d free OpenRouter models.", len(models))

        # A newly discovered model has no tracking rows, so it would sort to
        # the unscored tail of get_intelligent_model_order forever.
        PerformanceTracker.ensure_model_rows(models)

        return models

    except OpenRouterAPIError:
        raise
    except Exception as exc:
        logger.error("Could not fetch free models from OpenRouter: %s", exc)
        raise OpenRouterAPIError(
            f"Could not fetch the free model list from OpenRouter: {exc}"
        ) from exc


class OpenRouterAPIError(LLMError):
    """Raised when the OpenRouter API returns an error or an unexpected response."""

    pass


class OpenRouterService:
    """
    Thin HTTP client for the OpenRouter chat completions endpoint.

    Requires OPENROUTER_API_KEY in Django settings.
    Optionally reads OPENROUTER_MODEL to override the default model.

    Reference:
        POST https://openrouter.ai/api/v1/chat/completions
        https://openrouter.ai/docs/api/reference/overview#completions-request-format
    """

    def __init__(self) -> None:
        self.api_key: str = getattr(settings, "OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise OpenRouterAPIError(
                "OPENROUTER_API_KEY is not set in Django settings."
            )
        self.model: str = getattr(settings, "OPENROUTER_MODEL", DEFAULT_MODEL)
        self.timeout: int = getattr(settings, "OPENROUTER_TIMEOUT_SECONDS", 60)
        self.max_models_per_request: int = max(
            1,
            int(
                getattr(
                    settings,
                    "OPENROUTER_MAX_MODELS_PER_REQUEST",
                    DEFAULT_MAX_MODELS_PER_REQUEST,
                )
            ),
        )
        self.use_json_mode: bool = _as_bool(
            getattr(settings, "OPENROUTER_USE_JSON_MODE", False)
        )
        self.pin_default_model: bool = _as_bool(
            getattr(settings, "OPENROUTER_PIN_DEFAULT_MODEL", False)
        )
        self.qa_max_models: int = max(
            1,
            int(getattr(settings, "OPENROUTER_QA_MAX_MODELS", DEFAULT_QA_MAX_MODELS)),
        )
        self.qa_deadline_seconds: float = float(
            getattr(
                settings, "OPENROUTER_QA_DEADLINE_SECONDS", DEFAULT_QA_DEADLINE_SECONDS
            )
        )

    def _models_for_request(self, request_type: str) -> List[str]:
        """
        Models to try, in order, for one request.

        Ranked by PerformanceTracker, then capped. For Q&A, models that are
        not reasoning models go first: a reasoning model spends part of
        max_tokens on hidden reasoning and is the usual cause of an empty or
        cut-off JSON answer. The partition is stable, so the reliability
        ranking still decides order within each group. Q&A is also capped at
        qa_max_models attempts so one question cannot use up the daily
        free-model quota.
        """
        configured_models = getattr(settings, "OPENROUTER_MODELS", None)
        if isinstance(configured_models, str):
            configured_models = [
                model.strip() for model in configured_models.split(",") if model.strip()
            ]
        if not configured_models:
            configured_models = fetch_free_models()

        # Retry models the circuit breaker disabled, before ranking: nothing
        # else clears is_active, so a model that recovered from a transient
        # outage would otherwise stay at the back of the chain forever.
        try:
            PerformanceTracker.reset_circuit_breaker()
        except Exception as exc:
            logger.warning("Circuit breaker reset failed: %s", exc)

        # Get intelligent model order based on performance, then cap the
        # request. Trying every stale or rate-limited free model creates a
        # long chain of avoidable failures for one user request.
        models_to_try = PerformanceTracker.get_intelligent_model_order(
            list(dict.fromkeys(configured_models))
        )

        limit = self.max_models_per_request
        if request_type == "qa":
            reasoning = reasoning_model_ids()
            if reasoning:
                models_to_try = [m for m in models_to_try if m not in reasoning] + [
                    m for m in models_to_try if m in reasoning
                ]
            limit = min(limit, self.qa_max_models)

        # Pinning the default model to the front overrides the reliability
        # ranking, which also means it overrides the circuit breaker: a model
        # with dozens of consecutive failures would still be tried first on
        # every request. Off by default; opt in only to force one model.
        if self.pin_default_model and self.model in models_to_try:
            models_to_try.remove(self.model)
            models_to_try.insert(0, self.model)
        return models_to_try[:limit]

    def _deadline_for(self, request_type: str) -> Optional[float]:
        """time.monotonic() value after which a Q&A request stops; None otherwise."""
        if request_type == "qa" and self.qa_deadline_seconds > 0:
            return time.monotonic() + self.qa_deadline_seconds
        return None

    def _attempt_timeout(self, deadline: Optional[float]) -> Optional[float]:
        """
        Per-attempt HTTP timeout, shortened to the time left before the
        deadline. Returns None when too little time is left to start another
        model.
        """
        if deadline is None:
            return self.timeout
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_SECONDS:
            return None
        return min(self.timeout, remaining)

    def _deadline_error(self, attempts: int, last_error) -> "OpenRouterAPIError":
        error_msg = (
            f"Q&A time limit of {self.qa_deadline_seconds:g}s reached after "
            f"{attempts} model attempt(s). Last error: {last_error}"
        )
        logger.warning(error_msg)
        return OpenRouterAPIError(error_msg)

    def _build_headers(self) -> Dict[str, str]:
        """
        Build request headers.

        Authorization header is required.
        HTTP-Referer and X-Title are optional but surface your app on
        the OpenRouter leaderboard.
        Reference: https://openrouter.ai/docs/api/reference/overview#headers
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": getattr(settings, "OPENROUTER_SITE_URL", ""),
            "X-Title": getattr(
                settings, "OPENROUTER_SITE_NAME", "Research AI Assistant"
            ),
        }

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        request_type: str = "summary",
        response_validator: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Send a chat completion request to OpenRouter with intelligent fallback and performance tracking.

        Args:
            system_prompt: Instruction block for the model (role: system).
            user_message:  The user-turn content containing paper metadata.
            temperature:   Sampling temperature. 0.3 keeps output factual.
            max_tokens:    Maximum tokens in the completion.
            request_type:  Type of request for tracking (summary, title, other).
            response_validator: Optional callable that raises if a model's
                content doesn't meet caller-specific expectations (e.g. isn't
                valid JSON). A raise here is treated like any other per-model
                failure and triggers fallback to the next model.

        Returns:
            The model's reply as a plain string.

        Raises:
            OpenRouterAPIError: On HTTP errors, malformed responses, or model-level error objects in the payload.

        Reference:
            https://openrouter.ai/docs/api/reference/overview#completions-request-format
        """
        models_to_try = self._models_for_request(request_type)
        deadline = self._deadline_for(request_type)

        last_error = None

        for attempt_num, model_name in enumerate(models_to_try, 1):
            attempt_timeout = self._attempt_timeout(deadline)
            if attempt_timeout is None:
                last_error = self._deadline_error(attempt_num - 1, last_error)
                break

            attempt = PerformanceTracker.start_attempt(
                model_name, request_type, user_message
            )

            try:
                logger.info(
                    f"Trying model {attempt_num}/{len(models_to_try)}: {model_name}"
                )

                # Get model-specific temperature
                model_temperature = PerformanceTracker.get_model_temperature(
                    model_name, temperature
                )

                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": model_temperature,
                    "max_tokens": max_tokens,
                    # Ask OpenRouter to drop reasoning tokens from the
                    # response entirely for models that support the
                    # separate `reasoning` field, instead of leaving it to
                    # each caller to notice and discard message.reasoning.
                    # Low effort stops reasoning from consuming the whole
                    # max_tokens budget and leaving message.content null.
                    "reasoning": {"effort": "low", "exclude": True},
                }

                # JSON mode is not supported consistently by free providers.
                # QA still validates/parses JSON through response_validator.
                if request_type in JSON_REQUEST_TYPES and self.use_json_mode:
                    payload["response_format"] = {"type": "json_object"}

                response = requests.post(
                    OPENROUTER_API_URL,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=attempt_timeout,
                )
                response.raise_for_status()

                data = response.json()

                # The API wraps model-level errors inside choices.
                # Reference: https://openrouter.ai/docs/api/reference/overview#finish-reason
                choices = data.get("choices", [])
                if not choices:
                    error_msg = f"OpenRouter returned no choices. Full response: {data}"
                    logger.warning(f"Model {model_name}: {error_msg}")
                    last_error = OpenRouterAPIError(error_msg)
                    attempt.failure(error_msg)
                    continue

                choice = choices[0]

                if choice.get("error"):
                    error_msg = f"OpenRouter model error: {choice['error']}"
                    logger.warning(f"Model {model_name}: {error_msg}")
                    last_error = OpenRouterAPIError(error_msg)
                    attempt.failure(error_msg)
                    continue

                content = choice.get("message", {}).get("content")
                if content is None:
                    error_msg = "OpenRouter response missing message.content."
                    # finish_reason "length" with high completion_tokens means
                    # the model spent max_tokens before producing content.
                    logger.warning(
                        f"Model {model_name}: {error_msg} "
                        f"finish_reason={choice.get('finish_reason')!r} "
                        f"max_tokens={max_tokens} usage={data.get('usage')} "
                        f"message_keys={sorted((choice.get('message') or {}).keys())}"
                    )
                    last_error = OpenRouterAPIError(error_msg)
                    attempt.failure(error_msg)
                    continue

                if response_validator is not None:
                    try:
                        response_validator(content)
                    except Exception as exc:
                        error_msg = (
                            f"Model {model_name} returned invalid content: {exc}"
                        )
                        logger.warning(error_msg)
                        last_error = OpenRouterAPIError(error_msg)
                        attempt.failure(error_msg)
                        continue

                attempt.success(content)

                logger.info(
                    f"OpenRouter completion: model={model_name} tokens={data.get('usage', {}).get('total_tokens')}"
                )

                return content.strip()

            except (
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                requests.exceptions.RequestException,
                ValueError,
            ) as exc:
                status_code = getattr(
                    getattr(exc, "response", None), "status_code", None
                )
                if status_code == 429:
                    retry_after = getattr(exc.response, "headers", {}).get(
                        "Retry-After"
                    )
                    error_msg = (
                        f"Model {model_name} was rate limited (429)"
                        f"{f'; retry after {retry_after}s' if retry_after else ''}."
                    )
                elif status_code in {400, 403, 404}:
                    error_msg = (
                        f"Model {model_name} is unavailable for this request "
                        f"(HTTP {status_code})."
                    )
                else:
                    error_msg = f"Model {model_name} failed: {str(exc)}"
                logger.warning(error_msg)
                last_error = OpenRouterAPIError(error_msg)
                attempt.failure(error_msg)
                continue

        # All models failed
        logger.error(
            f"All {len(models_to_try)} models failed. Last error: {last_error}"
        )
        raise last_error or OpenRouterAPIError("All available free models failed")

    def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        request_type: str = "summary",
        response_validator: Optional[Callable[[str], None]] = None,
    ):
        """
        Streaming variant of complete(). Yields (token: str) as they arrive,
        then raises on validation failure. Falls back across models the same
        way complete() does; streaming starts only once a model begins
        producing tokens.

        Yields:
            str — each content delta from the SSE stream.

        Raises:
            OpenRouterAPIError on total failure.
        """
        models_to_try = self._models_for_request(request_type)
        deadline = self._deadline_for(request_type)

        last_error = None
        # True once a token from an earlier, failed model has been yielded.
        # The caller has already shown those, so the next model's first
        # token is preceded by STREAM_RESET.
        stale_tokens_sent = False
        collected: List[str] = []

        for attempt_num, model_name in enumerate(models_to_try, 1):
            # Reaching another attempt means the previous one failed, so any
            # tokens it yielded are stale.
            if collected:
                stale_tokens_sent = True
            collected = []

            attempt_timeout = self._attempt_timeout(deadline)
            if attempt_timeout is None:
                last_error = self._deadline_error(attempt_num - 1, last_error)
                break

            attempt = PerformanceTracker.start_attempt(
                model_name, request_type, user_message
            )
            try:
                logger.info(
                    "Streaming model %d/%d: %s",
                    attempt_num, len(models_to_try), model_name,
                )
                model_temperature = PerformanceTracker.get_model_temperature(
                    model_name, temperature
                )
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": model_temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    "reasoning": {"effort": "low", "exclude": True},
                }
                if request_type in JSON_REQUEST_TYPES and self.use_json_mode:
                    payload["response_format"] = {"type": "json_object"}

                response = requests.post(
                    OPENROUTER_API_URL,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=attempt_timeout,
                    stream=True,
                )
                response.raise_for_status()

                finish_reason = None
                usage = None
                timed_out = False
                for line in response.iter_lines(decode_unicode=True):
                    # The requests timeout only bounds the gap between
                    # reads, so a model that keeps trickling tokens would
                    # otherwise run past the Q&A deadline.
                    if deadline is not None and time.monotonic() > deadline:
                        timed_out = True
                        response.close()
                        break
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except (ValueError, TypeError):
                        continue
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    finish_reason = choices[0].get("finish_reason") or finish_reason
                    delta = choices[0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        if not collected and stale_tokens_sent:
                            yield STREAM_RESET
                            stale_tokens_sent = False
                        collected.append(token)
                        yield token

                if timed_out:
                    error_msg = f"Model {model_name} stream passed the Q&A time limit."
                    attempt.failure(error_msg)
                    last_error = self._deadline_error(
                        attempt_num, OpenRouterAPIError(error_msg)
                    )
                    break

                content = "".join(collected)
                if not content:
                    error_msg = f"Model {model_name} streamed no content."
                    # finish_reason "length" means max_tokens was spent on
                    # reasoning before any content was produced.
                    logger.warning(
                        "%s finish_reason=%r max_tokens=%s usage=%s",
                        error_msg, finish_reason, max_tokens, usage,
                    )
                    last_error = OpenRouterAPIError(error_msg)
                    attempt.failure(error_msg)
                    continue

                if response_validator is not None:
                    try:
                        response_validator(content)
                    except Exception as exc:
                        error_msg = f"Model {model_name} streamed invalid content: {exc}"
                        logger.warning(
                            "%s finish_reason=%r max_tokens=%s usage=%s",
                            error_msg, finish_reason, max_tokens, usage,
                        )
                        last_error = OpenRouterAPIError(error_msg)
                        attempt.failure(error_msg)
                        continue

                attempt.success(content)
                logger.info("OpenRouter stream complete: model=%s", model_name)
                return

            except (
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                requests.exceptions.RequestException,
                ValueError,
            ) as exc:
                status_code = getattr(
                    getattr(exc, "response", None), "status_code", None
                )
                error_msg = f"Model {model_name} stream failed: {exc}"
                logger.warning(error_msg)
                last_error = OpenRouterAPIError(error_msg)
                attempt.failure(error_msg)
                continue

        raise last_error or OpenRouterAPIError("All available free models failed")
