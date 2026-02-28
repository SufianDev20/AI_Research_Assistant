# AI Research Assistant

A Django-based web application that serves as an AI-powered research assistant for academic papers. The application integrates with the OpenAlex API to search, retrieve, and process academic paper metadata.

## Features

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

- **Backend**: Django
- **API Client**: pyalex (OpenAlex Python client)
- **Database**: SQLite (development)
- **Environment Management**: python-environ
- **Testing**: Django TestCase with unittest.mock

## Project Structure

```
Research_Assistant/
├── .env
├── db.sqlite3
├── manage.py
├── test_changes.py
├── test_api.py
├── Research_AI_Assistant/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   ├── tests.py
│   ├── migrations/
│   │   └── __init__.py
│   └── services/
│       ├── __init__.py
│       ├── openalex_service.py
│       └── extract_service.py
└── Research_Assistant/
    ├── __init__.py
    ├── settings.py
    ├── urls.py
    ├── asgi.py
    └── wsgi.py
```
```

## Installation & Setup

1. **Clone the repository** (if applicable) and navigate to the project directory

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install django pyalex python-environ
   ```

4. **Configure environment variables**:
   Create a `.env` file in `Research_Assistant/` with:
   ```
   SECRET_KEY=your_django_secret_key_here
   OPENALEX_EMAIL=your_email@example.com
   ```

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

#### `search_papers(query, per_page=25, page=1, exclude_retracted=True, open_access_only=False, oa_status=None)`

Search for academic papers using the OpenAlex API.

**Parameters:**
- `query` (str): Search query string
- `per_page` (int): Number of results per page (max 200)
- `exclude_retracted` (bool): Filter out retracted papers (default: True)
- `open_access_only` (bool): Return only open access papers (default: False)
- `oa_status` (str, optional): Open access type filter ('gold', 'green', 'hybrid', 'bronze')

**Returns:** List of work objects from OpenAlex API

**Raises:** `OpenAlexAPIError` if API request fails, `ValueError` if input parameters are invalid

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
- `is_open_access`: Boolean indicating OA status
- `oa_status`: Open access type (gold, green, hybrid, bronze, closed)
- `full_text_url`: PDF URL if available via best_oa_location

## Testing

Run tests with:
```bash
python manage.py test Research_AI_Assistant.tests
```

## Dependencies

- Django
- pyalex
- python-environ

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Acknowledgments

- [OpenAlex](https://openalex.org/) for providing comprehensive academic paper data
- [Django](https://www.djangoproject.com/) for the web framework
- [pyalex](https://github.com/J535D165/pyalex) for the Python OpenAlex client
