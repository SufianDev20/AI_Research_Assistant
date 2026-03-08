# AI Research Assistant

A Django-based web application that serves as an AI-powered research assistant for academic papers. The application integrates with the OpenAlex API to search, retrieve, and process academic paper metadata, and uses OpenRouter's free LLM models to generate individual paper summaries with proper academic citations.

## Features

- **OpenAlex API Integration**: Full integration with OpenAlex API using the pyalex library
- **OpenRouter LLM Integration**: Uses free models from OpenRouter to generate individual paper summaries
- **Paper Search Service**: Search academic papers with advanced filtering options
- **Author Search Service**: Search for academic authors via OpenAlex API
- **Multiple Search Endpoints**: Both processed and raw OpenAlex data access
- **Query Analytics**: Database logging of search queries for analytics (no PII stored)
- **Metadata Extraction**: Comprehensive extraction of paper metadata including:
  - Title, authors, and affiliations
  - Abstract reconstruction from inverted index
  - Publication year, DOI, and citation count
  - Research concepts/topics (top 5)
  - Source publication details
  - Full text PDF URLs (when available)
- **LLM Summarization**: Generate individual summaries for each paper with Harvard-style citations
- **Rate Limiting**: Proper rate limiting following OpenRouter and OpenAlex API policies
- **Comprehensive Testing**: Unit tests for all service methods with proper mocking

### Search Filters Supported

- Query-based search
- Exclude retracted papers (default: true)
- Open access only filtering
- Open access status filtering (gold, green, hybrid, bronze)
- Configurable results per page (max 50)
- Pagination support for large result sets

## Technology Stack

- **Backend**: Django 6.0+
- **API Client**: pyalex (OpenAlex Python client)
- **LLM Provider**: OpenRouter (free models)
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Environment Management**: python-environ
- **Rate Limiting**: django-ratelimit
- **Testing**: Django TestCase with unittest.mock
- **Logging**: Python logging with structured output

## Project Structure

```
AIResearchAssistant/
├── .git/
├── README.md
├── requirements.txt
└── Research_Assistant/
    ├── db.sqlite3
    ├── manage.py
    ├── summarise.py
    ├── test_api.py
    ├── test_changes.py
    ├── Research_AI_Assistant/
    │   ├── __init__.py
    │   ├── admin.py
    │   ├── apps.py
    │   ├── models.py
    │   ├── settings.py
    │   ├── tests.py
    │   ├── urls.py
    │   ├── views.py
    │   ├── migrations/
    │   └── services/
    │       ├── __init__.py
    │       ├── extract_service.py
    │       ├── openalex_service.py
    │       ├── openrouter_service.py
    │       └── prompt_builder.py
    └── Research_Assistant/
        ├── __init__.py
        ├── asgi.py
        ├── settings.py
        ├── urls.py
        └── wsgi.py
```

````

## Installation & Setup

1. **Clone the repository** (if applicable) and navigate to the project directory

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
````

3. **Install dependencies**:

   ```bash
   pip install django pyalex python-environ requests django-ratelimit
   ```

4. **Configure environment variables**:
   Create a `.env` file in `Research_Assistant/` with:

   ```
   SECRET_KEY=your_django_secret_key_here
   OPENALEX_EMAIL=your_email@example.com
   OPENALEX_API_KEY=<"Your API key">
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxx
   OPENROUTER_SITE_URL=http://127.0.0.1:8080
   OPENROUTER_SITE_NAME=Research AI Assistant
   ```

5. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

## Testing

### Run Test Suite

```bash
python test_api.py
```

### Manual Testing

```bash
# Test API root
curl "http://127.0.0.1:8080/api/"

# Test error handling
curl "http://127.0.0.1:8080/api/search/"  # Missing query
curl "http://127.0.0.1:8080/api/search/?q=test&mode=invalid"  # Invalid mode

# Test all search modes
curl "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=relevance&per_page=2"
curl "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=open_access&per_page=2"
curl "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=best_match&per_page=2"
```
### Test Coverage
The test suite covers:
- All search modes (relevance, open_access, best_match)
- Parameter validation
- Error handling (missing query, invalid mode)
- JSON response structure
- OpenAlex API integration
=======
### Test LLM Summarization
```bash
# Start the Django server
python manage.py runserver 8080

# In another terminal, test summarization
python summarise.py "machine learning"
```

### Sample LLM Response

When you run `python summarise.py "machine learning"`, you'll get individual summaries for each paper with bold headers and Harvard citations:

````
**Paper [1]: Scikit-learn: Machine Learning in Python**
This paper introduces scikit-learn, a comprehensive Python library for machine learning that provides simple and efficient tools for data mining and data analysis. The library features various classification, regression, and clustering algorithms, including support vector machines, random forests, gradient boosting, k-means, and DBSCAN. Key contributions include a unified API design, extensive documentation, and integration with other scientific Python libraries like NumPy and SciPy. The authors demonstrate the library's effectiveness through benchmarks on standard datasets, showing competitive performance with established tools while maintaining ease of use. This work has significantly influenced the machine learning community by making advanced algorithms accessible to practitioners and researchers.

**Paper [2]: Genetic algorithms in search, optimization, and machine learning**
The book by Goldberg provides a comprehensive treatment of genetic algorithms and their applications in optimization and machine learning. It covers fundamental concepts including selection, crossover, and mutation operators, along with theoretical foundations and convergence properties. The author demonstrates practical applications across various domains including function optimization, machine learning classification tasks, and combinatorial optimization problems. Key insights include the role of population diversity, schema theory, and the building block hypothesis in explaining algorithm effectiveness. This seminal work established genetic algorithms as a powerful paradigm in evolutionary computation and continues to influence research in optimization and adaptive systems.

**Paper [3]: C4.5: Programs for Machine Learning**
This paper presents C4.5, an improved version of the ID3 decision tree algorithm for machine learning classification tasks. The system introduces several key enhancements including handling of continuous attributes, missing values, pruning to avoid overfitting, and rule generation from decision trees. The authors demonstrate significant improvements in accuracy and robustness compared to previous approaches through extensive experiments on benchmark datasets. C4.5's ability to generate human-readable rules while maintaining predictive power made it a cornerstone in early machine learning research and practical applications.

References

[1] Pedregosa, F.; Varoquaux, G.; Gramfort, A.; Michel, V.; Thirion, B.; Grisel, O.; Blondel, M.; Prettenhofer, P.; Weiss, R.; Dubourg, V.; Vanderplas, J.; Passos, A.; Cournapeau, D.; Brucher, M.; Perrot, M.; Duchesnay, E. (2011) 'Scikit-learn: Machine Learning in Python'. *Journal of Machine Learning Research*, 12, pp. 2825�2830.

[2]Goldberg, D.E. (1989) 'Genetic algorithms in search, optimization, and machine learning'. *Choice Reviews Online*.

[3] Quinlan, J.R. (1993) 'C4.5: Programs for Machine Learning'. *Morgan Kaufmann*.

### Test Coverage

The test suite covers:

- All search modes (relevance, open_access, best_match)
- Author search functionality
- OpenAlex raw works endpoint
- Parameter validation
- Error handling (missing query, invalid mode)
- JSON response structure
- OpenAlex API integration
- LLM summarization service
- Rate limiting behavior
## API Reference

### Endpoints

#### GET `/api/`

Root endpoint providing API information and available endpoints.

#### GET `/api/search/`

Search for academic papers with processed metadata.

**Parameters:**

- `q` (required): Search query
- `mode`: `relevance` | `open_access` | `best_match` (default: relevance)
- `per_page`: Results per page (1-50, default: 25)
- `page`: Page number (default: 1)
- `oa_status`: Open access filter (`gold`, `green`, `hybrid`, `bronze`)

#### GET `/api/openalex/works/`

Search papers via OpenAlex API with raw data format.

**Parameters:**

- `q` (required): Search query
- `per_page`: Results per page (1-50, default: 25)
- `page`: Page number (default: 1)

#### GET `/api/openalex/authors/`

Search for academic authors via OpenAlex API.

**Parameters:**

- `q` (required): Author search query
- `per_page`: Results per page (1-50, default: 10)
- `page`: Page number (default: 1)

#### POST `/api/summarise/`

Generate individual summaries for each paper using LLM.

**Body:**

```json
{
  "query": "machine learning",
  "papers": [...]
}
```

**Response:**

```json
{
  "summary": "Individual paper summaries with citations...",
  "paper_count": 3,
  "query": "machine learning"
}
```

### Database Models

#### QueryLog

Logs each search query for analytics (no user PII stored).

**Fields:**
- `query_text`: Search query string (max 500 chars)
- `ranking_mode`: Search mode used (relevance/open_access/best_match)
- `result_count`: Number of results returned
- `created_at`: Timestamp of the query

**Indexes:** Created_at and ranking_mode for efficient querying

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

- Django >= 6.0
- pyalex >= 1.0
- requests >= 2.25
- python-environ >= 0.12
- django-ratelimit >= 4.0

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
- [OpenRouter](https://openrouter.ai/docs/quickstart) for the LLM API
````
