from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import Mock, patch
from .services.openalex_service import OpenAlexService, OpenAlexAPIError
from .services.extract_service import ExtractionService


class TestOpenAlexService(TestCase):
    """Test cases for OpenAlexService class."""

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_success_default(self, mock_works_class):
        """Test successful paper search with default parameters."""
        # Setup mock chain
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result

        # Mock the filter chain - filter returns the same object for chaining
        mock_search_result.filter.return_value = mock_search_result

        mock_results = [{"id": "1", "title": "Test Paper"}]
        mock_search_result.get.return_value = mock_results

        service = OpenAlexService()
        result = service.search_papers("machine learning")

        self.assertEqual(result, mock_results)
        mock_works_class.assert_called_once()
        mock_works_instance.search.assert_called_once_with("machine learning")
        # Check filters: exclude_retracted=True by default
        mock_search_result.filter.assert_called_once_with(is_retracted=False)
        mock_search_result.get.assert_called_once_with(per_page=25, page=1)

    @patch("Research_AI_Assistant.services.openalex_service.Works")
    def test_search_papers_with_filters(self, mock_works_class):
        """Test paper search with all filters enabled."""
        mock_works_instance = Mock()
        mock_works_class.return_value = mock_works_instance

        mock_search_result = Mock()
        mock_works_instance.search.return_value = mock_search_result

        # Mock filter chain - each filter returns the same object
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
        # Check no exclude_retracted filter since False
        # But filter is called for is_oa=True and oa_status='gold'
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
        # No filters should be called
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

        # Simulate API error
        mock_search_result.get.side_effect = Exception("API timeout")

        service = OpenAlexService()

        with self.assertRaises(OpenAlexAPIError) as cm:
            service.search_papers("error query", page=5)

        self.assertIn("Failed to retrieve papers from OpenAlex", str(cm.exception))


class TestOpenAlexViews(TestCase):
    """Integration tests for the API endpoints defined in views."""

    def setUp(self):
        self.client = Client()

    def test_works_search_missing_query(self):
        resp = self.client.get(reverse("openalex_works_search"))
        self.assertEqual(resp.status_code, 400)
        content = resp.json()
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], "missing_query")

    @patch("Research_AI_Assistant.views.OpenAlexService.search_papers")
    def test_works_search_success(self, mock_search_papers):
        mock_search_papers.return_value = [{"id": "W1"}]

        resp = self.client.get(
            reverse("openalex_works_search"),
            {"q": "test", "per_page": "2", "page": "3"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["results"], [{"id": "W1"}])
        self.assertEqual(data["page"], 3)
        self.assertEqual(data["per_page"], 2)
        self.assertEqual(data["query"], "test")
        mock_search_papers.assert_called_once_with("test", per_page=2, page=3)

    def test_authors_search_missing_query(self):
        resp = self.client.get(reverse("openalex_authors_search"))
        self.assertEqual(resp.status_code, 400)
        content = resp.json()
        self.assertEqual(content["error"]["code"], "missing_query")

    @patch("Research_AI_Assistant.views.OpenAlexService.search_authors")
    def test_authors_search_success(self, mock_search_authors):
        mock_search_authors.return_value = [{"id": "A1"}]

        resp = self.client.get(reverse("openalex_authors_search"), {"q": "foo"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"], [{"id": "A1"}])
        mock_search_authors.assert_called_once_with("foo", per_page=10, page=1)


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

    # ---- new tests for authors search ----
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
