"""
This is the OpenRouter API logic for LLM inference
Sends structured paper metadata to a free OpenRouter model and returns a Harvard-style cited summary.

References:
1)OpenRouter QuickStart: https://openrouter.ai/docs/quickstart
2)OpenRouter API overview:https://openrouter.ai/docs/api/reference/overview
"""

import logging
import time
from typing import Dict

import requests
from django.conf import settings

from .performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default free model.
# Browse free models at https://openrouter.ai/models?max_price=0
DEFAULT_MODEL = "arcee-ai/trinity-mini:free"

# List of all available free models for fallback
FREE_MODELS = [
    "arcee-ai/trinity-mini:free",
    "arcee-ai/trinity-large-preview:free",
    "google/gemma-3-4b-it:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "stepfun/step-3.5-flash:free",
    "z-ai/glm-4.5-air:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-120b:free",
]


class OpenRouterAPIError(Exception):
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
        self.timeout: int = getattr(settings, "OPENROUTER_TIMEOUT_SECONDS", 30)

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
    ) -> str:
        """
        Send a chat completion request to OpenRouter with intelligent fallback and performance tracking.

        Args:
            system_prompt: Instruction block for the model (role: system).
            user_message:  The user-turn content containing paper metadata.
            temperature:   Sampling temperature. 0.3 keeps output factual.
            max_tokens:    Maximum tokens in the completion.
            request_type:  Type of request for tracking (summary, title, other).

        Returns:
            The model's reply as a plain string.

        Raises:
            OpenRouterAPIError: On HTTP errors, malformed responses, or model-level error objects in the payload.

        Reference:
            https://openrouter.ai/docs/api/reference/overview#completions-request-format
        """
        # Get intelligent model order based on performance
        models_to_try = PerformanceTracker.get_intelligent_model_order(
            FREE_MODELS.copy()
        )

        # Move the default model to the front if it's not already
        if self.model in models_to_try:
            models_to_try.remove(self.model)
            models_to_try.insert(0, self.model)

        last_error = None

        for attempt, model_name in enumerate(models_to_try, 1):
            request_start_time = time.time()
            request_id, query_hash = PerformanceTracker.log_request_start(
                model_name, request_type, user_message
            )

            try:
                logger.info(
                    f"Trying model {attempt}/{len(models_to_try)}: {model_name}"
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
                }

                response = requests.post(
                    OPENROUTER_API_URL,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=self.timeout,
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

                    # Log failure
                    response_time = time.time() - request_start_time
                    PerformanceTracker.log_request_failure(
                        model_name,
                        request_id,
                        request_type,
                        response_time,
                        error_msg,
                        query_hash,
                    )
                    continue

                choice = choices[0]

                if choice.get("error"):
                    error_msg = f"OpenRouter model error: {choice['error']}"
                    logger.warning(f"Model {model_name}: {error_msg}")
                    last_error = OpenRouterAPIError(error_msg)

                    # Log failure
                    response_time = time.time() - request_start_time
                    PerformanceTracker.log_request_failure(
                        model_name,
                        request_id,
                        request_type,
                        response_time,
                        error_msg,
                        query_hash,
                    )
                    continue

                content = choice.get("message", {}).get("content")
                if content is None:
                    error_msg = "OpenRouter response missing message.content."
                    logger.warning(f"Model {model_name}: {error_msg}")
                    last_error = OpenRouterAPIError(error_msg)

                    # Log failure
                    response_time = time.time() - request_start_time
                    PerformanceTracker.log_request_failure(
                        model_name,
                        request_id,
                        request_type,
                        response_time,
                        error_msg,
                        query_hash,
                    )
                    continue

                # Log success
                response_time = time.time() - request_start_time
                PerformanceTracker.log_request_success(
                    model_name,
                    request_id,
                    request_type,
                    response_time,
                    content,
                    query_hash,
                )

                logger.info(
                    f"OpenRouter completion: model={model_name} tokens={data.get('usage', {}).get('total_tokens')} time={response_time:.2f}s"
                )

                return content.strip()

            except (
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                requests.exceptions.RequestException,
                ValueError,
            ) as exc:
                error_msg = f"Model {model_name} failed: {str(exc)}"
                logger.warning(error_msg)
                last_error = OpenRouterAPIError(error_msg)

                # Log failure
                response_time = time.time() - request_start_time
                PerformanceTracker.log_request_failure(
                    model_name,
                    request_id,
                    request_type,
                    response_time,
                    error_msg,
                    query_hash,
                )
                continue

        # All models failed
        logger.error(
            f"All {len(models_to_try)} models failed. Last error: {last_error}"
        )
        raise last_error or OpenRouterAPIError("All available free models failed")
