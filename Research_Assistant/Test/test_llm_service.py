from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from Research_AI_Assistant.services.llm_service import (
    FallbackLLM,
    LLMError,
    get_llm,
)
from Research_AI_Assistant.services.ollama_service import (
    OllamaAPIError,
    OllamaService,
)
from Research_AI_Assistant.services.openrouter_service import (
    OpenRouterAPIError,
    OpenRouterService,
)

CFG = dict(RESEARCH_API_URL="https://x.example", RESEARCH_API_KEY="k",
           LLM_TIMEOUT=(6, 240), LLM_NUM_CTX=8192)
POST = "Research_AI_Assistant.services.ollama_service.requests.post"
GET = "Research_AI_Assistant.services.ollama_service.requests.get"
SLEEP = "Research_AI_Assistant.services.ollama_service.time.sleep"
KW = dict(system_prompt="s", user_message="u")


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def _submitted(job_id="j1"):
    return _resp(202, {"job_id": job_id, "status": "queued"})


def _job(status="completed", content="hi", **extra):
    body = {"job_id": "j1", "status": status, **extra}
    if status == "completed":
        body["result"] = {"content": content}
    return _resp(200, body)


@override_settings(**CFG)
class OllamaServiceTests(SimpleTestCase):
    def setUp(self):
        patcher = patch(SLEEP)
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch(GET)
    @patch(POST)
    def test_job_flow_sends_bearer_and_payload(self, post, get):
        post.return_value = _submitted()
        get.side_effect = [_job("queued"), _job("processing"), _job(content=" hi ")]
        out = OllamaService().complete(**KW, temperature=0.1, max_tokens=50)
        self.assertEqual(out, "hi")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://x.example/llm/jobs")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})
        self.assertEqual(kwargs["json"]["num_ctx"], 8192)
        self.assertEqual(kwargs["json"]["max_tokens"], 50)
        self.assertFalse(kwargs["json"]["json_mode"])
        self.assertEqual(get.call_args.args[0], "https://x.example/llm/jobs/j1")
        self.assertEqual(get.call_count, 3)

    @patch(GET)
    @patch(POST)
    def test_qa_requests_json_mode(self, post, get):
        post.return_value = _submitted()
        get.return_value = _job(content="{}")
        OllamaService().complete(**KW, request_type="qa")
        self.assertTrue(post.call_args.kwargs["json"]["json_mode"])

    @patch(POST)
    def test_404_on_submit_falls_back_to_blocking_llm(self, post):
        post.side_effect = [_resp(404), _resp(200, {"content": " hi "})]
        self.assertEqual(OllamaService().complete(**KW), "hi")
        self.assertEqual(post.call_args_list[1].args[0], "https://x.example/llm")
        self.assertEqual(post.call_args_list[1].kwargs["timeout"], (6, 240))

    @patch(POST)
    def test_network_error_wrapped(self, post):
        post.side_effect = requests.ConnectionError("boom https://secret.host")
        with self.assertRaises(OllamaAPIError) as ctx:
            OllamaService().complete(**KW)
        self.assertNotIn("secret.host", str(ctx.exception))

    @patch(POST)
    def test_submit_401_429_500_raise(self, post):
        for code in (401, 429, 500, 503):
            post.return_value = _resp(code)
            with self.assertRaises(OllamaAPIError):
                OllamaService().complete(**KW)

    @patch(POST)
    def test_submit_without_job_id_raises(self, post):
        post.return_value = _resp(202, {})
        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW)

    @patch(GET)
    @patch(POST)
    def test_failed_job_raises(self, post, get):
        post.return_value = _submitted()
        get.return_value = _job("failed", error="LLM request failed.")
        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW)

    @patch(GET)
    @patch(POST)
    def test_lost_job_404_raises(self, post, get):
        post.return_value = _submitted()
        get.return_value = _resp(404)
        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW)

    @patch(GET)
    @patch(POST)
    def test_empty_completed_content_raises(self, post, get):
        post.return_value = _submitted()
        get.return_value = _job(content="")
        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW)

    @patch(GET)
    @patch(POST)
    def test_one_dropped_poll_is_tolerated_three_are_not(self, post, get):
        post.return_value = _submitted()
        get.side_effect = [requests.ConnectionError("x"), _job()]
        self.assertEqual(OllamaService().complete(**KW), "hi")
        get.side_effect = requests.ConnectionError("x")
        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW)

    @override_settings(LLM_JOB_DEADLINE_SECONDS=10)
    @patch("Research_AI_Assistant.services.ollama_service.time.monotonic")
    @patch(GET)
    @patch(POST)
    def test_deadline_exceeded_raises(self, post, get, mono):
        post.return_value = _submitted()
        get.return_value = _job("processing")
        mono.side_effect = [0, 1, 5, 11]
        with self.assertRaises(OllamaAPIError) as ctx:
            OllamaService().complete(**KW)
        self.assertIn("timed out", str(ctx.exception))

    @patch(GET)
    @patch(POST)
    def test_validator_retries_once_then_succeeds(self, post, get):
        post.return_value = _submitted()
        get.side_effect = [_job(content="bad"), _job(content="good")]

        def validator(text):
            if text != "good":
                raise ValueError("format")

        self.assertEqual(OllamaService().complete(**KW, response_validator=validator), "good")
        self.assertEqual(post.call_count, 2)

    @patch(GET)
    @patch(POST)
    def test_validator_fails_twice_raises(self, post, get):
        post.return_value = _submitted()
        get.return_value = _job(content="bad")

        def validator(text):
            raise ValueError("format")

        with self.assertRaises(OllamaAPIError):
            OllamaService().complete(**KW, response_validator=validator)
        self.assertEqual(post.call_count, 2)

    @override_settings(RESEARCH_API_URL="", RESEARCH_API_KEY="")
    def test_unconfigured_raises(self):
        with self.assertRaises(OllamaAPIError):
            OllamaService()


class FallbackLLMTests(SimpleTestCase):
    def test_primary_success_never_builds_secondary(self):
        primary, factory = MagicMock(), MagicMock()
        primary.complete.return_value = "ok"
        self.assertEqual(FallbackLLM(primary, factory).complete(**KW), "ok")
        factory.assert_not_called()

    def test_primary_failure_uses_secondary_with_same_args(self):
        primary, secondary = MagicMock(), MagicMock()
        primary.complete.side_effect = OllamaAPIError("down")
        secondary.complete.return_value = "fallback"
        validator = lambda t: None
        out = FallbackLLM(primary, lambda: secondary).complete(
            **KW, request_type="qa", response_validator=validator
        )
        self.assertEqual(out, "fallback")
        self.assertEqual(secondary.complete.call_args.kwargs["request_type"], "qa")
        self.assertIs(secondary.complete.call_args.kwargs["response_validator"], validator)

    def test_both_fail_raises_llm_error(self):
        primary, secondary = MagicMock(), MagicMock()
        primary.complete.side_effect = OllamaAPIError("a")
        secondary.complete.side_effect = OpenRouterAPIError("b")
        with self.assertRaises(LLMError):
            FallbackLLM(primary, lambda: secondary).complete(**KW)

    def test_secondary_not_configured_raises_llm_error(self):
        primary = MagicMock()
        primary.complete.side_effect = OllamaAPIError("a")

        def factory():
            raise OpenRouterAPIError("OPENROUTER_API_KEY is not set")

        with self.assertRaises(LLMError):
            FallbackLLM(primary, factory).complete(**KW)

    def test_non_llm_errors_are_not_swallowed(self):
        primary = MagicMock()
        primary.complete.side_effect = KeyError("bug")
        with self.assertRaises(KeyError):
            FallbackLLM(primary, MagicMock()).complete(**KW)


@override_settings(**CFG)
class GetLLMTests(SimpleTestCase):
    @override_settings(LLM_BACKEND="ollama")
    def test_ollama_backend(self):
        self.assertIsInstance(get_llm(), OllamaService)

    @override_settings(LLM_BACKEND="ollama_then_openrouter", OPENROUTER_API_KEY="")
    def test_fallback_backend_builds_without_openrouter_key(self):
        # OpenRouter is constructed lazily, so a missing key must not break startup.
        self.assertIsInstance(get_llm(), FallbackLLM)

    @override_settings(
        LLM_BACKEND="ollama_then_openrouter",
        RESEARCH_API_URL="",
        RESEARCH_API_KEY="",
        OPENROUTER_API_KEY="k",
    )
    def test_fallback_backend_uses_openrouter_when_ollama_unconfigured(self):
        # A missing research server must degrade to OpenRouter, not raise.
        self.assertIsInstance(get_llm(), OpenRouterService)

    @override_settings(LLM_BACKEND="openrouter", OPENROUTER_API_KEY="")
    def test_openrouter_backend_without_key_raises_llm_error(self):
        with self.assertRaises(LLMError):
            get_llm()

    @override_settings(LLM_BACKEND="bogus")
    def test_invalid_backend(self):
        with self.assertRaises(LLMError):
            get_llm()

    def test_openrouter_error_is_llm_error(self):
        self.assertTrue(issubclass(OpenRouterAPIError, LLMError))
