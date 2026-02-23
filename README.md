# AI Research Assistant

A Django-based web application that serves as an AI-powered research assistant for academic papers. The application integrates with the OpenAlex API to search, retrieve, and process academic paper metadata.

## Features

### Current Implementation
- **OpenAlex API Integration**: Full integration with OpenAlex API using the pyalex library
- **Paper Search Service**: Search academic papers with advanced filtering options
- **Metadata Extraction**: Comprehensive extraction of paper metadata including:
  - Title, authors, and affiliations
  - Abstract reconstruction from inverted index
  - Publication year, DOI, and citation count
  - Research concepts/topics (top 5)
  - Source publication details
  - Full text PDF URLs (when available)
- **Comprehensive Testing**: Unit tests for all service methods with proper mocking

### Search Filters Supported
- Query-based search
- Exclude retracted papers (default: true)
- Open access only filtering
- Open access status filtering (gold, green, hybrid, bronze)
- Configurable results per page (max 200)

## Technology Stack

- **Backend**: Django 6.0.2
- **API Client**: pyalex
- **Database**: SQLite (development)
- **Environment Management**: django-environ
- **Testing**: Django TestCase with unittest.mock

## Project Structure

Research_Assistant/
├── Research_AI_Assistant/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/
│   │   └── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── openalex_service.py    # OpenAlex API client
│   │   └── extract_service.py     # Metadata extraction service
│   └── tests.py            # Unit tests for services
├── Research_Assistant/
│   ├── __init__.py
│   ├── settings.py         # Django settings
│   ├── urls.py             # URL routing
│   ├── asgi.py
│   └── wsgi.py
├── db.sqlite3              # SQLite database
├── manage.py               # Django management script
├── .env                    # Environment variables
└── .gitignore

## Installation & Setup

1. **Clone the repository** (if applicable) and navigate to the project directory

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install django pyalex python-environ
   ```

4. **Configure environment variables**:
   Create a `.env` file in the project root with:
   ```
   SECRET_KEY=your_django_secret_key_here
   OPENALEX_EMAIL=your_email@example.com
   ```

   > **Note**: OpenAlex requires an email address for API access. See [OpenAlex API documentation](https://docs.openalex.org/) for details.

5. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Run tests**:
   ```bash
   python manage.py test
   ```

7. **Start the development server**:
   ```bash
   python manage.py runserver
   ```

## API Reference

### OpenAlexService

#### `search_papers(query, per_page=25, exclude_retracted=True, open_access_only=False, oa_status=None)`

Search for academic papers using the OpenAlex API.

**Parameters:**
- `query` (str): Search query string
- `per_page` (int): Number of results per page (max 200)
- `exclude_retracted` (bool): Filter out retracted papers (default: True)
- `open_access_only` (bool): Return only open access papers (default: False)
- `oa_status` (str, optional): Open access type filter ('gold', 'green', 'hybrid', 'bronze')

**Returns:** List of work objects from OpenAlex API

**Raises:** `OpenAlexAPIError` if API request fails

### ExtractionService

#### `extract_metadata(work)`

Extract structured metadata from an OpenAlex work object.

**Parameters:**
- `work` (dict): Raw work object from OpenAlex API

**Returns:** Dictionary containing extracted metadata:
- `openalex_id`: OpenAlex work ID
- `title`: Paper title
- `authors`: List of author dictionaries with name, ORCID, and institutions
- `abstract`: Reconstructed abstract text
- `publication_year`: Year of publication
- `doi`: Digital Object Identifier
- `cited_by_count`: Number of citations
- `concepts`: Top 5 research concepts with scores
- `source`: Primary publication source name
- `full_text_url`: PDF URL if available

## Testing

The project includes comprehensive unit tests for the service layer:

- `TestOpenAlexService.test_search_papers_success_default`: Tests default search behavior
- `TestOpenAlexService.test_search_papers_with_filters`: Tests search with all filters applied
- `TestOpenAlexService.test_search_papers_no_filters`: Tests search with no filters
- `TestOpenAlexService.test_search_papers_api_error`: Tests error handling

Run tests with:
```bash
python manage.py test Research_AI_Assistant.tests
```

## Future Development

The following components are planned for future implementation:

- Django models for data persistence
- REST API views and endpoints
- Web interface for paper search and display
- User authentication and saved searches
- Advanced filtering and sorting options
- Citation network visualization
- Integration with other academic APIs (Google Scholar, Semantic Scholar)

## Dependencies

- Django == 6.0.2
- pyalex
- django-environ

MIT License

Copyright (c) 2026 SufianDev20

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


## Acknowledgments

- [OpenAlex](https://openalex.org/) for providing comprehensive academic paper data
- [Django](https://www.djangoproject.com/) for the web framework
- [pyalex](https://github.com/J535D165/pyalex) for the Python OpenAlex client
