"""
Client for the university research server's LLM endpoints, which forward to
Ollama /api/chat. Same complete() signature as OpenRouterService so callers
do not change. Uses POST /llm/jobs + GET /llm/jobs/{id} (async, avoids the
Cloudflare tunnel's ~100 s request limit); falls back to blocking POST /llm
if the server predates the job endpoints.

Settings (see settings.py):
    RESEARCH_API_URL, RESEARCH_API_KEY   shared with the local corpus client
    LLM_TIMEOUT      (connect, read) seconds, blocking /llm fallback only
    LLM_JOB_DEADLINE_SECONDS   total time to wait for one async job
    LLM_NUM_CTX      context window requested per call (server caps it)

Ollama references:
    https://docs.ollama.com/api/chat
    https://docs.ollama.com/context-length
"""
import logging
import time
from typing import Callable, Optional

import requests
from django.conf import settings

from .llm_service import LLMError

logger = logging.getLogger(__name__)

# Task types whose prompts demand a JSON reply (qa_llm.QA_SYSTEM_PROMPT).
JSON_REQUEST_TYPES = {"qa"}

# Submit and poll requests return immediately; only the job itself is slow.
SHORT_TIMEOUT = (6, 30)
POLL_INTERVAL_SECONDS = 2


class OllamaAPIError(LLMError):
    """Raised when the Ollama endpoint fails or returns unusable output."""


class OllamaService:
    def __init__(self) -> None:
        self.base_url: str = (getattr(settings, "RESEARCH_API_URL", "") or "").rstrip("/")
        self.api_key: str = getattr(settings, "RESEARCH_API_KEY", "") or ""
        self.timeout = getattr(settings, "LLM_TIMEOUT", (6, 240))
        self.job_deadline: int = int(getattr(settings, "LLM_JOB_DEADLINE_SECONDS", 240))
        self.num_ctx: int = int(getattr(settings, "LLM_NUM_CTX", 8192))
        if not (self.base_url and self.api_key):
            raise OllamaAPIError("RESEARCH_API_URL and RESEARCH_API_KEY must be set.")

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    @staticmethod
    def _check_status(response, ok: tuple) -> None:
        if response.status_code == 401:
            logger.error("Ollama endpoint rejected the key (401). Key expired or wrong.")
            raise OllamaAPIError("Ollama authentication failed.")
        if response.status_code not in ok:
            logger.warning("Ollama endpoint returned HTTP %s", response.status_code)
            raise OllamaAPIError(f"Ollama server HTTP {response.status_code}.")

    @staticmethod
    def _content_of(data) -> str:
        try:
            content = str(data.get("content") or "").strip()
        except AttributeError as exc:
            raise OllamaAPIError("Ollama server returned an invalid payload.") from exc
        if not content:
            raise OllamaAPIError("Ollama returned an empty response.")
        return content

    def _request(self, path: str, payload: dict, timeout):
        """POST payload to path, wrapping any network failure. Does not
        check the status code: callers inspect the raw response first
        (_post needs to see a 404 before validating status)."""
        try:
            return requests.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Ollama request to %s failed: %s", path, exc)
            raise OllamaAPIError("Ollama server unreachable.") from exc

    def _post(self, payload: dict) -> str:
        """Submit an async job and poll it, so no single request outlives the
        tunnel's ~100 s limit. Falls back to blocking POST /llm on servers
        that do not have /llm/jobs yet (404)."""
        response = self._request("/llm/jobs", payload, SHORT_TIMEOUT)

        if response.status_code == 404:
            logger.info("Server has no /llm/jobs; using blocking /llm.")
            return self._post_blocking(payload)
        self._check_status(response, ok=(200, 202))

        try:
            job_id = response.json()["job_id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaAPIError("Ollama server returned an invalid payload.") from exc
        return self._poll_job(job_id)

    def _poll_job(self, job_id: str) -> str:
        deadline = time.monotonic() + self.job_deadline
        poll_errors = 0
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
            try:
                response = requests.get(
                    f"{self.base_url}/llm/jobs/{job_id}",
                    headers=self._headers,
                    timeout=SHORT_TIMEOUT,
                )
            except requests.RequestException as exc:
                # A single dropped poll should not discard a job that is still running.
                poll_errors += 1
                logger.warning("Ollama job poll failed (%d/3): %s", poll_errors, exc)
                if poll_errors >= 3:
                    raise OllamaAPIError("Ollama server unreachable.") from exc
                continue
            poll_errors = 0

            if response.status_code == 404:
                # In-memory jobs are lost if the server restarts.
                raise OllamaAPIError("Ollama job was lost (server restarted?).")
            self._check_status(response, ok=(200,))

            try:
                job = response.json()
                job_status = job.get("status")
            except (ValueError, AttributeError) as exc:
                raise OllamaAPIError("Ollama server returned an invalid payload.") from exc
            if job_status == "completed":
                return self._content_of(job.get("result"))
            if job_status == "failed":
                raise OllamaAPIError(f"Ollama job failed: {job.get('error') or 'unknown'}.")
        raise OllamaAPIError(f"Ollama job timed out after {self.job_deadline}s.")

    def _post_blocking(self, payload: dict) -> str:
        response = self._request("/llm", payload, self.timeout)
        self._check_status(response, ok=(200,))
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaAPIError("Ollama server returned an invalid payload.") from exc
        return self._content_of(data)

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        request_type: str = "summary",
        response_validator: Optional[Callable[[str], None]] = None,
    ) -> str:
        payload = {
            "system_prompt": system_prompt,
            "user_message": user_message,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "num_ctx": self.num_ctx,
            "json_mode": request_type in JSON_REQUEST_TYPES,
        }

        last_error: Optional[Exception] = None
        # One retry, only when the reply fails the caller's format check.
        # Network and HTTP errors are not retried so a fallback starts fast.
        for attempt in (1, 2):
            content = self._post(payload)
            if response_validator is None:
                return content
            try:
                response_validator(content)
                return content
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Ollama reply failed validation (attempt %d/2): %s", attempt, exc
                )
        raise OllamaAPIError("Ollama reply did not match the required format.") from last_error
