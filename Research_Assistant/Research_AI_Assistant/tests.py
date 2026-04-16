"""
Tests for Research AI Assistant.

Covers:
  - OpenAlexService: paper and author search
  - ExtractionService: metadata extraction, abstract reconstruction, concepts
  - OpenAlex views: search and author endpoints
  - OpenRouterService.complete(): success and failure paths
  - prompt_builder: build_user_message() and SYSTEM_PROMPT
  - Summarise view: valid input, missing fields, upstream errors
"""

import json
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .services.openalex_service import OpenAlexService, OpenAlexAPIError
from .services.extract_service import ExtractionService
from .services.openrouter_service import OpenRouterService, OpenRouterAPIError
from .services.prompt_builder import system_prompt, build_user_message


# ---------------------------------------------------------------------------
# OpenAlex service tests
# ---------------------------------------------------------------------------


class TestOpenAlexService(TestCase):
    """Test cases for OpenAlexService class."""

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_success_default(self, mock_works_class):
        """Test successful paper search with default parameters."""
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result

        mock_search_result.filter.return_value = mock_search_result

        mock_results = [{"id": "1", "title": "Test Paper"}]
        mock_search_result.get.return_value = mock_results

        service = OpenAlexService()
        result = service.search_papers("machine learning")

        self.assertEqual(result, mock_results)
        mock_works_class.assert_called_once()
        mock_works_instance.search.assert_called_once_with("machine learning")
        mock_search_result.filter.assert_called_once_with(is_retracted=False)
        mock_search_result.get.assert_called_once_with(per_page=25, page=1)

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_with_filters(self, mock_works_class):
        """Test paper search with all filters enabled."""
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result

        mock_search_result.filter.return_value = mock_search_result

        mock_results = [{"id": "2", "title": "Open Access Paper"}]
        mock_search_result.get.return_value = mock_results

        service = OpenAlexService()
        result = service.search_papers(
            query="AI",
            per_page=10,
            page=3,
            exclude_retracted=False,
            open_access_only=True,
            oa_status="gold",
        )

        self.assertEqual(result, mock_results)
        self.assertEqual(mock_search_result.filter.call_count, 2)
        mock_search_result.filter.assert_any_call(is_oa=True)
        mock_search_result.filter.assert_any_call(oa_status="gold")
        mock_search_result.get.assert_called_once_with(per_page=10, page=3)

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_no_filters(self, mock_works_class):
        """Test paper search with no filters."""
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result

        mock_search_result.filter.return_value = mock_search_result

        mock_results = [{"id": "3", "title": "Any Paper"}]
        mock_search_result.get.return_value = mock_results

        service = OpenAlexService()
        result = service.search_papers(
            query="physics",
            page=2,
            exclude_retracted=False,
            open_access_only=False,
            oa_status=None,
        )

        self.assertEqual(result, mock_results)
        mock_search_result.filter.assert_not_called()
        mock_search_result.get.assert_called_once_with(per_page=25, page=2)

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_api_error(self, mock_works_class):
        """Test that OpenAlexAPIError is raised on API failure."""
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result
        mock_search_result.filter.return_value = mock_search_result

        mock_search_result.get.side_effect = Exception("API timeout")

        service = OpenAlexService()

        with self.assertRaises(OpenAlexAPIError) as cm:
            service.search_papers("error query", page=5)

        self.assertIn("Failed to retrieve papers from OpenAlex", str(cm.exception))


# ---------------------------------------------------------------------------
# OpenAlex view tests
# ---------------------------------------------------------------------------


class TestOpenAlexViews(TestCase):
    """Integration tests for the API endpoints defined in views."""

    def setUp(self):
        self.client = Client()

    def test_works_search_missing_query(self):
        resp = self.client.get(reverse("research_ai_assistant:openalex_works_search"))
        self.assertEqual(resp.status_code, 400)
        content = resp.json()
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], "missing_query")

    @patch("Research_AI_Assistant.views.OpenAlexService.search_papers")
    def test_works_search_success(self, mock_search_papers):
        mock_search_papers.return_value = [{"id": "W1"}]

        resp = self.client.get(
            reverse("research_ai_assistant:openalex_works_search"),
            {"q": "test", "per_page": "2", "page": "3"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["results"], [{"id": "W1"}])
        self.assertEqual(data["page"], 3)
        self.assertEqual(data["per_page"], 2)
        self.assertEqual(data["query"], "test")
        mock_search_papers.assert_called_once_with(query="test", per_page=2, page=3)

    def test_authors_search_missing_query(self):
        resp = self.client.get(reverse("research_ai_assistant:openalex_authors_search"))
        self.assertEqual(resp.status_code, 400)
        content = resp.json()
        self.assertEqual(content["error"]["code"], "missing_query")

    @patch("Research_AI_Assistant.views.OpenAlexService.search_authors")
    def test_authors_search_success(self, mock_search_authors):
        mock_search_authors.return_value = [{"id": "A1"}]

        resp = self.client.get(
            reverse("research_ai_assistant:openalex_authors_search"), {"q": "foo"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [{"id": "A1"}])
        mock_search_authors.assert_called_once_with(query="foo", per_page=10, page=1)


# ---------------------------------------------------------------------------
# Extraction service tests
# ---------------------------------------------------------------------------


class TestExtractionService(TestCase):
    """Test cases for Extraction_Service class."""

    def test_extract_metadata_full(self):
        """Test extract_metadata with complete work data."""
        mock_work = {
            "id": "https://openalex.org/W123456789",
            "title": "Sample Research Paper",
            "authorships": [
                {
                    "author": {
                        "display_name": "John Doe",
                        "orcid": "0000-0000-0000-0001",
                    },
                    "institutions": [{"display_name": "University A"}],
                },
                {
                    "author": {"display_name": "Jane Smith", "orcid": None},
                    "institutions": [{"display_name": "University B"}],
                },
            ],
            "abstract_inverted_index": {
                "This": [0],
                "is": [1],
                "a": [2],
                "sample": [3],
                "abstract": [4],
            },
            "publication_year": 2023,
            "doi": "10.1234/sample.doi",
            "cited_by_count": 50,
            "concepts": [
                {"display_name": "Computer Science", "score": 0.9},
                {"display_name": "Artificial Intelligence", "score": 0.8},
                {"display_name": "Machine Learning", "score": 0.7},
                {"display_name": "Data Science", "score": 0.6},
                {"display_name": "Statistics", "score": 0.5},
                {"display_name": "Extra Concept", "score": 0.4},
            ],
            "primary_location": {"source": {"display_name": "Journal of AI"}},
            "best_oa_location": {"pdf_url": "https://example.com/fulltext.pdf"},
            "open_access": {"is_oa": True, "oa_status": "gold"},
        }

        result = ExtractionService.extract_metadata(mock_work)

        expected = {
            "openalex_id": "https://openalex.org/W123456789",
            "title": "Sample Research Paper",
            "authors": [
                {
                    "name": "John Doe",
                    "orcid": "0000-0000-0000-0001",
                    "institutions": ["University A"],
                },
                {"name": "Jane Smith", "orcid": "", "institutions": ["University B"]},
            ],
            "abstract": "This is a sample abstract",
            "publication_year": 2023,
            "doi": "10.1234/sample.doi",
            "cited_by_count": 50,
            "concepts": [
                {"name": "Computer Science", "score": 0.9},
                {"name": "Artificial Intelligence", "score": 0.8},
                {"name": "Machine Learning", "score": 0.7},
                {"name": "Data Science", "score": 0.6},
                {"name": "Statistics", "score": 0.5},
            ],
            "source": "Journal of AI",
            "is_open_access": True,
            "oa_status": "gold",
            "full_text_url": "https://example.com/fulltext.pdf",
        }

        self.assertEqual(result, expected)

    def test_extract_metadata_minimal(self):
        """Test extract_metadata with minimal work data."""
        mock_work = {"id": "https://openalex.org/W987654321", "title": "Minimal Paper"}

        result = ExtractionService.extract_metadata(mock_work)

        expected = {
            "openalex_id": "https://openalex.org/W987654321",
            "title": "Minimal Paper",
            "authors": [],
            "abstract": "",
            "publication_year": None,
            "doi": "",
            "cited_by_count": 0,
            "concepts": [],
            "source": None,
            "is_open_access": False,
            "oa_status": None,
            "full_text_url": None,
        }

        self.assertEqual(result, expected)

    def test_extract_authors(self):
        """Test _extract_authors method."""
        mock_work = {
            "authorships": [
                {
                    "author": {"display_name": "Author One", "orcid": "orcid123"},
                    "institutions": [
                        {"display_name": "Inst A"},
                        {"display_name": "Inst B"},
                    ],
                }
            ]
        }

        authors = ExtractionService._extract_authors(mock_work)

        expected = [
            {
                "name": "Author One",
                "orcid": "orcid123",
                "institutions": ["Inst A", "Inst B"],
            }
        ]

        self.assertEqual(authors, expected)

    def test_reconstruct_abstract(self):
        """Test _reconstruct_abstract method."""
        mock_work = {
            "abstract_inverted_index": {"Hello": [0], "world": [1], "test": [2]}
        }

        abstract = ExtractionService._reconstruct_abstract(mock_work)

        self.assertEqual(abstract, "Hello world test")

    def test_reconstruct_abstract_none(self):
        """Test _reconstruct_abstract with no abstract."""
        mock_work = {}

        abstract = ExtractionService._reconstruct_abstract(mock_work)

        self.assertEqual(abstract, "")

    def test_extract_concepts(self):
        """Test _extract_concepts method."""
        mock_work = {
            "concepts": [
                {"display_name": "Concept A", "score": 0.9},
                {"display_name": "Concept B", "score": 0.8},
                {"display_name": "Concept C", "score": 0.7},
                {"display_name": "Concept D", "score": 0.6},
                {"display_name": "Concept E", "score": 0.5},
                {"display_name": "Concept F", "score": 0.4},
            ]
        }

        concepts = ExtractionService._extract_concepts(mock_work)

        expected = [
            {"name": "Concept A", "score": 0.9},
            {"name": "Concept B", "score": 0.8},
            {"name": "Concept C", "score": 0.7},
            {"name": "Concept D", "score": 0.6},
            {"name": "Concept E", "score": 0.5},
        ]

        self.assertEqual(concepts, expected)


# ---------------------------------------------------------------------------
# Full text URL and author search tests
# ---------------------------------------------------------------------------


class TestExtractFullTextUrl(TestCase):
    """Test cases for _extract_full_text_url method."""

    def test_extract_full_text_url_from_best_oa(self):
        """Test extracting URL from best_oa_location."""
        mock_work = {
            "best_oa_location": {"pdf_url": "https://oa.example.com/paper.pdf"}
        }

        url = ExtractionService._extract_full_text_url(mock_work)

        self.assertEqual(url, "https://oa.example.com/paper.pdf")

    def test_extract_full_text_url_from_content_urls(self):
        """Test extracting URL from content_urls when best_oa not available."""
        mock_work = {"content_urls": {"pdf": "https://content.example.com/paper.pdf"}}

        url = ExtractionService._extract_full_text_url(mock_work)

        self.assertEqual(url, "https://content.example.com/paper.pdf")

    def test_extract_full_text_url_none(self):
        """Test returning None when no full text URL available."""
        mock_work = {}

        url = ExtractionService._extract_full_text_url(mock_work)

        self.assertIsNone(url)

    @patch("Research_AI_Assistant.services.openalex_service.Authors")
    def test_search_authors_success(self, mock_authors_class):
        """Ensure author search produces expected results."""
        mock_authors_instance = Mock()
        mock_authors_class.return_value = mock_authors_instance
        mock_query = Mock()
        mock_authors_instance.search.return_value = mock_query
        mock_query.get.return_value = [{"id": "A1", "name": "Alice"}]

        service = OpenAlexService()
        result = service.search_authors("Alice", per_page=5, page=2)
        self.assertEqual(result, [{"id": "A1", "name": "Alice"}])
        mock_query.get.assert_called_once_with(per_page=5, page=2)

    @patch("Research_AI_Assistant.services.openalex_service.Authors")
    def test_search_authors_error(self, mock_authors_class):
        mock_instance = Mock()
        mock_authors_class.return_value = mock_instance
        mock_query = Mock()
        mock_instance.search.return_value = mock_query
        mock_query.get.side_effect = Exception("timeout")

        service = OpenAlexService()
        with self.assertRaises(OpenAlexAPIError):
            service.search_authors("fail")


# ---------------------------------------------------------------------------
# Shared fixtures for OpenRouter tests
# ---------------------------------------------------------------------------

MOCK_PAPERS = [
    {
        "openalex_id": "https://openalex.org/W1",
        "title": "Deep Learning for NLP",
        "authors": [
            {"name": "Jane Smith", "orcid": "0000-0001", "institutions": ["MIT"]},
            {"name": "John Doe", "orcid": "", "institutions": ["Stanford"]},
        ],
        "abstract": "We study deep learning methods for natural language processing.",
        "publication_year": 2022,
        "doi": "10.1234/dlnlp",
        "cited_by_count": 120,
        "concepts": [
            {"name": "Deep Learning", "score": 0.95},
            {"name": "NLP", "score": 0.88},
        ],
        "source": "Journal of AI Research",
        "is_open_access": True,
        "oa_status": "gold",
        "full_text_url": "https://example.com/paper1.pdf",
    },
    {
        "openalex_id": "https://openalex.org/W2",
        "title": "Transformer Architectures",
        "authors": [
            {"name": "Alice Wang", "orcid": "", "institutions": ["Oxford"]},
        ],
        "abstract": "An overview of transformer architectures in modern AI.",
        "publication_year": 2021,
        "doi": "10.5678/transformers",
        "cited_by_count": 300,
        "concepts": [
            {"name": "Transformers", "score": 0.99},
        ],
        "source": "Nature Machine Intelligence",
        "is_open_access": False,
        "oa_status": None,
        "full_text_url": None,
    },
]

MOCK_SUMMARY = (
    "Recent research has explored deep learning for NLP [1] and transformer "
    "architectures [2]. Smith et al. demonstrate strong results [1], while "
    "Wang provides a comprehensive overview [2].\n\n"
    "References\n"
    "[1] Smith, J. and Doe, J. (2022) 'Deep Learning for NLP'. "
    "Journal of AI Research. doi: 10.1234/dlnlp\n"
    "[2] Wang, A. (2021) 'Transformer Architectures'. "
    "Nature Machine Intelligence. doi: 10.5678/transformers"
)


# ---------------------------------------------------------------------------
# OpenRouter service tests
# ---------------------------------------------------------------------------


@override_settings(OPENROUTER_API_KEY="test-key-123")
class TestOpenRouterService(TestCase):
    """Unit tests for OpenRouterService.complete()."""

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_success(self, mock_post):
        """Returns stripped content string on a valid 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "gen-abc123",
            "model": "mistralai/mistral-7b-instruct:free",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": f"  {MOCK_SUMMARY}  "},
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 80,
                "total_tokens": 180,
            },
        }
        mock_post.return_value = mock_response

        service = OpenRouterService()
        result = service.complete(
            system_prompt=system_prompt,
            user_message="test user message",
        )

        self.assertEqual(result, MOCK_SUMMARY)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0], "https://openrouter.ai/api/v1/chat/completions"
        )

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_sends_correct_payload(self, mock_post):
        """Verifies model, messages structure, temperature, and max_tokens in payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
        }
        mock_post.return_value = mock_response

        service = OpenRouterService()
        service.complete(
            system_prompt="sys prompt",
            user_message="user msg",
            temperature=0.5,
            max_tokens=800,
        )

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["temperature"], 0.5)
        self.assertEqual(payload["max_tokens"], 800)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][0]["content"], "sys prompt")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(payload["messages"][1]["content"], "user msg")

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_sends_auth_header(self, mock_post):
        """Authorization header must use the configured API key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
        }
        mock_post.return_value = mock_response

        service = OpenRouterService()
        service.complete(system_prompt="s", user_message="u")

        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer test-key-123")
        self.assertEqual(headers["Content-Type"], "application/json")

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_empty_choices(self, mock_post):
        """Raises OpenRouterAPIError when choices list is empty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("no choices", str(cm.exception))

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_model_error_in_choice(self, mock_post):
        """Raises OpenRouterAPIError when choices[0].error is present."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "error": {"code": 429, "message": "Rate limit exceeded"},
                    "finish_reason": "error",
                }
            ]
        }
        mock_post.return_value = mock_response

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("model error", str(cm.exception).lower())

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_missing_content(self, mock_post):
        """Raises OpenRouterAPIError when message.content is None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": None}, "finish_reason": "stop"}]
        }
        mock_post.return_value = mock_response

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("message.content", str(cm.exception))

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_http_error(self, mock_post):
        """Raises OpenRouterAPIError on non-2xx HTTP status."""
        import requests as req_lib

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("401", str(cm.exception))

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_timeout(self, mock_post):
        """Raises OpenRouterAPIError with a timeout message on request timeout."""
        import requests as req_lib

        mock_post.side_effect = req_lib.exceptions.Timeout()

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("timed out", str(cm.exception))

    @patch("Research_AI_Assistant.services.openrouter_service.requests.post")
    def test_complete_raises_on_non_json_response(self, mock_post):
        """Raises OpenRouterAPIError when response body is not valid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("no json")
        mock_post.return_value = mock_response

        service = OpenRouterService()
        with self.assertRaises(OpenRouterAPIError) as cm:
            service.complete(system_prompt="s", user_message="u")

        self.assertIn("non-JSON", str(cm.exception))

    def test_init_raises_without_api_key(self):
        """Raises OpenRouterAPIError at init time when API key is missing."""
        with self.settings(OPENROUTER_API_KEY=""):
            with self.assertRaises(OpenRouterAPIError) as cm:
                OpenRouterService()

            self.assertIn("OPENROUTER_API_KEY", str(cm.exception))

    @override_settings(
        OPENROUTER_API_KEY="key", OPENROUTER_MODEL="google/gemma-7b:free"
    )
    def test_init_uses_custom_model_from_settings(self):
        """OPENROUTER_MODEL setting overrides the default model."""
        service = OpenRouterService()
        self.assertEqual(service.model, "google/gemma-7b:free")


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


class TestPromptBuilder(TestCase):
    """Unit tests for build_user_message() and SYSTEM_PROMPT."""

    def test_system_prompt_contains_citation_instruction(self):
        """SYSTEM_PROMPT must instruct the model to use [N] inline markers."""
        self.assertIn("[N]", system_prompt)
        self.assertIn("Harvard", system_prompt)

    def test_system_prompt_forbids_fabrication(self):
        """SYSTEM_PROMPT must explicitly prohibit fabrication."""
        self.assertIn("fabricat", system_prompt.lower())

    def test_system_prompt_requires_references_section(self):
        """SYSTEM_PROMPT must instruct the model to output a References section."""
        self.assertIn("References", system_prompt)

    def test_build_user_message_numbers_papers(self):
        """Each paper must appear as [1], [2], etc. in the user message."""
        msg = build_user_message(MOCK_PAPERS, "deep learning")
        self.assertIn("Paper [1]", msg)
        self.assertIn("Paper [2]", msg)

    def test_build_user_message_includes_query(self):
        """The original search query must appear in the user message."""
        msg = build_user_message(MOCK_PAPERS, "deep learning NLP")
        self.assertIn("deep learning NLP", msg)

    def test_build_user_message_includes_title(self):
        """Each paper's title must appear in the user message."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("Deep Learning for NLP", msg)
        self.assertIn("Transformer Architectures", msg)

    def test_build_user_message_includes_doi(self):
        """Each paper's DOI must appear in the user message."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("10.1234/dlnlp", msg)
        self.assertIn("10.5678/transformers", msg)

    def test_build_user_message_includes_abstract(self):
        """Each paper's abstract must appear in the user message."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("natural language processing", msg)

    def test_build_user_message_includes_authors(self):
        """Author names must appear in the user message."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("Jane Smith", msg)
        self.assertIn("Alice Wang", msg)

    def test_build_user_message_includes_year(self):
        """Publication year must appear for each paper."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("2022", msg)
        self.assertIn("2021", msg)

    def test_build_user_message_missing_abstract_shows_na(self):
        """Papers with no abstract must show 'N/A' rather than an empty string."""
        papers = [
            {
                "title": "No Abstract Paper",
                "authors": [],
                "abstract": "",
                "publication_year": 2020,
                "doi": "",
                "cited_by_count": 0,
                "concepts": [],
                "source": None,
                "is_open_access": False,
            }
        ]
        msg = build_user_message(papers, "test")
        self.assertIn("Abstract: N/A", msg)

    def test_build_user_message_empty_papers(self):
        """Empty paper list returns a no-results message, not an error."""
        msg = build_user_message([], "test query")
        self.assertIn("No papers", msg)

    def test_build_user_message_includes_synthesis_instruction(self):
        """User message must end with an instruction to write the synthesis."""
        msg = build_user_message(MOCK_PAPERS, "q")
        self.assertIn("synthesis", msg.lower())


@override_settings(OPENROUTER_API_KEY="test-key-123")
class TestSummariseView(TestCase):
    """Integration tests for POST /api/summarise/."""

    def setUp(self):
        self.client = Client()

    @patch("Research_AI_Assistant.views.OpenRouterService")
    def test_summarise_success(self, mock_service_class):
        """Returns 200 with summary, paper_count, and query on valid input."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = MOCK_SUMMARY
        mock_service_class.return_value = mock_instance

        payload = {"query": "deep learning", "papers": MOCK_PAPERS}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["summary"], MOCK_SUMMARY)
        self.assertEqual(data["paper_count"], 2)
        self.assertEqual(data["query"], "deep learning")

    @patch("Research_AI_Assistant.views.OpenRouterService")
    def test_summarise_calls_complete_with_correct_args(self, mock_service_class):
        """View must pass SYSTEM_PROMPT and a user message built from the papers."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "summary text"
        mock_service_class.return_value = mock_instance

        payload = {"query": "transformers", "papers": MOCK_PAPERS}
        self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        mock_instance.complete.assert_called_once()
        call_kwargs = mock_instance.complete.call_args[1]
        self.assertEqual(call_kwargs["system_prompt"], system_prompt)
        self.assertIn("transformers", call_kwargs["user_message"])

    def test_summarise_missing_query_returns_400(self):
        """Missing 'query' field must return 400."""
        payload = {"papers": MOCK_PAPERS}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("query", resp.json()["error"].lower())

    def test_summarise_missing_papers_returns_400(self):
        """Missing 'papers' field must return 400."""
        payload = {"query": "deep learning"}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("papers", resp.json()["error"].lower())

    def test_summarise_empty_papers_list_returns_400(self):
        """Empty 'papers' list must return 400."""
        payload = {"query": "deep learning", "papers": []}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_summarise_invalid_json_body_returns_400(self):
        """Malformed JSON body must return 400."""
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data="not json at all",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("JSON", resp.json()["error"])

    @patch("Research_AI_Assistant.views.OpenRouterService")
    def test_summarise_openrouter_api_error_returns_502(self, mock_service_class):
        """OpenRouterAPIError from complete() must return 502."""
        mock_instance = MagicMock()
        mock_instance.complete.side_effect = OpenRouterAPIError("upstream failure")
        mock_service_class.return_value = mock_instance

        payload = {"query": "deep learning", "papers": MOCK_PAPERS}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 502)
        self.assertIn("upstream failure", resp.json()["error"])

    @patch("Research_AI_Assistant.views.OpenRouterService")
    def test_summarise_missing_api_key_returns_503(self, mock_service_class):
        """OpenRouterAPIError raised at service init (no key) must return 503."""
        mock_service_class.side_effect = OpenRouterAPIError(
            "OPENROUTER_API_KEY is not set"
        )

        payload = {"query": "deep learning", "papers": MOCK_PAPERS}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 503)

    @patch("Research_AI_Assistant.views.OpenRouterService")
    def test_summarise_caps_papers_at_20(self, mock_service_class):
        """View must silently cap the paper list at 20 before calling the LLM."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "summary"
        mock_service_class.return_value = mock_instance

        many_papers = [MOCK_PAPERS[0]] * 25
        payload = {"query": "q", "papers": many_papers}
        resp = self.client.post(
            reverse("research_ai_assistant:summarise"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["paper_count"], 20)

    def test_summarise_get_request_returns_405(self):
        """GET on /api/summarise/ must return 405 Method Not Allowed."""
        resp = self.client.get(reverse("research_ai_assistant:summarise"))
        self.assertEqual(resp.status_code, 405)
