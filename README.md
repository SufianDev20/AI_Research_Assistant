# AI Research Assistant

A comprehensive Django-based web application that serves as an AI-powered research assistant for academic papers. The application integrates with the OpenAlex API to search, retrieve, and process academic paper metadata, and uses OpenRouter's free LLM models to generate individual paper summaries with proper academic citations.

## Features

### Core Functionality

- **OpenAlex API Integration**: Full integration with OpenAlex API using the pyalex library
- **OpenRouter LLM Integration**: Uses free models from OpenRouter to generate individual paper summaries
- **Paper Search Service**: Search academic papers with advanced filtering options
- **Author Search Service**: Search for academic authors via OpenAlex API
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
- **Cursor-based Pagination**: Efficient pagination for large result sets using OpenAlex cursor API

### Frontend Features

- **Modern UI**: Clean, responsive web interface with TailwindCSS and FontAwesome
- **Interactive Research View**: Dynamic chat-like interface for research conversations
- **Binder System**: Save and organize research conversations with custom colors and titles
- **Paper Cards**: Visual display of research papers with metadata and links
- **Load More Functionality**: Seamless pagination for browsing large result sets
- **Real-time Search**: Instant search with loading indicators and error handling
- **Keyboard Shortcuts**: Meta+K for quick search focus

### Search Filters Supported

- Query-based search
- Exclude retracted papers (default: true)
- Open access only filtering
- Open access status filtering (gold, green, hybrid, bronze)
- Configurable results per page (max 50)
- Cursor-based pagination for large result sets

## Technology Stack

### Backend

- **Framework**: Django 6.0+
- **API Client**: pyalex (OpenAlex Python client)
- **LLM Provider**: OpenRouter (free models)
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Environment Management**: django-environ
- **Rate Limiting**: django-ratelimit
- **Testing**: Django TestCase with unittest.mock
- **Logging**: Python logging with structured output

### Frontend

- **Template Engine**: Django Templates
- **CSS Framework**: TailwindCSS
- **Icons**: FontAwesome 6.6.0
- **JavaScript**: Vanilla JavaScript with modern ES6+ features
- **Architecture**: Component-based with DOM management

### External APIs

- **OpenAlex**: Academic paper metadata and citation data
- **OpenRouter**: LLM models for paper summarization

## Project Structure

```
AIResearchAssistant/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
└── Research_Assistant/                 # Main Django project
    ├── db.sqlite3                      # SQLite database (development)
    ├── manage.py                       # Django management script
    ├── test_api.py                     # API testing script
    ├── test_changes.py                 # Change verification script
    ├── summarise.py                    # LLM summarization test script
    ├── .env                            # Environment variables (create this)
    ├── Research_Assistant/             # Django project config
    │   ├── __init__.py
    │   ├── asgi.py                     # ASGI configuration
    │   ├── settings.py                 # Django settings
    │   ├── urls.py                     # Root URL configuration
    │   └── wsgi.py                     # WSGI configuration
    └── Research_AI_Assistant/          # Main Django app
        ├── __init__.py
        ├── admin.py                     # Django admin configuration
        ├── apps.py                      # App configuration
        ├── models.py                    # Database models
        ├── views.py                     # API views and endpoints
        ├── urls.py                      # App URL configuration
        ├── tests.py                     # Unit tests
        ├── migrations/                  # Database migrations
        ├── templates/                   # HTML templates
        │   ├── index.html               # Main frontend template
        │   └── static/                  # Static assets
        │       ├── styles.css          # Main stylesheet
        │       └── scripts.js           # Frontend JavaScript
        └── services/                    # Business logic services
            ├── __init__.py
            ├── extract_service.py       # Metadata extraction
            ├── openalex_service.py      # OpenAlex API client
            ├── openrouter_service.py    # OpenRouter LLM client
            └── prompt_builder.py        # LLM prompt construction
```

## Architecture Overview

### Backend Architecture

#### Models (`models.py`)

- **QueryLog**: Logs search queries for analytics without storing user PII
  - Fields: query_text, ranking_mode, result_count, created_at
  - Indexes: created_at, ranking_mode for efficient querying

#### Services Layer

- **OpenAlexService** (`openalex_service.py`): Handles OpenAlex API interactions
  - `search_papers()`: Search academic papers with filters and cursor pagination
  - `search_authors()`: Search academic authors
  - Uses pyalex library with proper error handling and rate limiting

- **OpenRouterService** (`openrouter_service.py`): Manages LLM interactions
  - `complete()`: Generate responses using OpenRouter free models
  - Fallback model system with 10 free models
  - Proper timeout and error handling

- **ExtractionService** (`extract_service.py`): Processes raw OpenAlex data
  - `extract_metadata()`: Converts raw work objects to structured metadata
  - Handles abstract reconstruction, author extraction, concept analysis

- **PromptBuilder** (`prompt_builder.py`): Constructs LLM prompts
  - `system_prompt`: Defines AI assistant behavior
  - `build_user_message()`: Formats paper data for LLM input

#### Views (`views.py`)

- **API Endpoints**:
  - `api_root()`: API information and available endpoints
  - `search()`: Main paper search endpoint with filtering
  - `search_authors()`: Author search endpoint
  - `summarise()`: LLM paper summarization endpoint
  - `generate_title()`: Generate conversation titles
  - `frontend()`: Render main web interface

#### Settings (`settings.py`)

- Environment-based configuration using django-environ
- Security headers and middleware configuration
- Database and static files configuration
- API keys and external service settings

### Frontend Architecture

#### JavaScript Application (`scripts.js`)

- **AppState**: Global state management
  - Research view state, binder management, pagination state
  - Search parameters, loading states, rate limiting

- **DOMManager**: DOM manipulation and event handling
  - Element caching, event listeners, UI updates
  - Search functionality, research view management

- **API Integration**:
  - `retrieveFromBackend()`: Backend API calls with cursor pagination
  - `generateResearchResponse()`: Main research workflow
  - `loadMorePapers()`: Pagination handling
  - `generateTitle()`: Conversation title generation

- **UI Components**:
  - Paper cards with metadata and links
  - Binder system with color customization
  - Real-time search with loading indicators
  - Modal system for research conversations

#### CSS (`styles.css`)

- Modern design with TailwindCSS
- Responsive layout for mobile and desktop
- Dark theme with accent colors
- Smooth transitions and hover effects
- Loading animations and status indicators

## Security & API Verification

### ✅ Security Best Practices Implemented

This project follows industry-standard security practices:

- **Environment Variables**: All API keys and secrets stored in `.env` file
- **No Hardcoded Secrets**: Zero hardcoded API keys or passwords in codebase
- **Backend-Only API Calls**: External API calls handled server-side, frontend never accesses external APIs directly
- **Rate Limiting**: Proper rate limiting for OpenAlex (100 req/s) and OpenRouter (20 req/min)
- **Input Validation**: Comprehensive parameter validation on all endpoints
- **CSRF Protection**: Django CSRF protection enabled for all forms and AJAX requests
- **Security Headers**: XSS protection, content type sniffing protection, clickjacking protection
- **SQL Injection Protection**: Django ORM prevents SQL injection attacks

### ✅ API Integration Verification

#### OpenAlex API

- **Base URL**: `https://api.openalex.org` ✅
- **Authentication**: API key via environment variables ✅
- **Library**: PyAlex v0.16 (official) ✅
- **Endpoints**: `/works`, `/authors` ✅
- **Rate Limits**: 100 requests/second ✅
- **Pagination**: Cursor-based pagination for efficiency ✅

#### OpenRouter API

- **Base URL**: `https://openrouter.ai/api/v1/chat/completions` ✅
- **Authentication**: Bearer token via environment variables ✅
- **Fallback Models**: 10 free models with error handling ✅
- **Rate Limits**: 20 requests/minute ✅
- **Timeout**: 30-second timeout for API calls ✅

#### PyAlex Library

- **Version**: 0.16 ✅
- **Configuration**: Proper API key setup ✅
- **Usage**: Works and Authors entities ✅
- **Metadata**: Comprehensive metadata extraction ✅

### 🔒 Frontend Security

- **No External API Calls**: Frontend only communicates with backend ✅
- **CSRF Tokens**: Properly implemented for all AJAX requests ✅
- **API Key Protection**: No keys exposed in JavaScript ✅
- **Input Sanitization**: HTML escaping for user content ✅

### ⚠️ Production Deployment Notes

Before deploying to production, ensure:

```python
# In settings.py
DEBUG = False  # Must be False in production
ALLOWED_HOSTS = ['yourdomain.com']  # Configure your domain
SECURE_SSL_REDIRECT = True  # Force HTTPS
SECURE_HSTS_SECONDS = 31536000  # HSTS header
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- pip package manager
- Git (for cloning)

### Quick Start with Git Clone

1. **Clone the repository**:

   ```bash
   git clone https://github.com/your-username/AIResearchAssistant.git
   cd AIResearchAssistant
   ```

2. **Navigate to project directory**:

   ```bash
   cd Research_Assistant
   ```

3. **Create and activate virtual environment**:

   **Windows:**

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   **Mac/Linux:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies from requirements.txt**:

   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**:
   Create a `.env` file in `Research_Assistant/` with:

   ```env
   SECRET_KEY=your_django_secret_key_here
   OPENALEX_EMAIL=your_email@example.com
   OPENALEX_API_KEY=<"Your API key">
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxx
   OPENROUTER_SITE_URL=http://127.0.0.1:8080
   OPENROUTER_SITE_NAME=Research AI Assistant
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

6. **Run database migrations**:

   ```bash
   python manage.py migrate
   ```

7. **Start the development server**:

   ```bash
   python manage.py runserver 8080
   ```

8. **Access the application**:
   Open your browser and navigate to `http://127.0.0.1:8080`

### Getting API Keys

#### OpenAlex API Key

1. Visit [OpenAlex Settings](https://openalex.org/settings/api)
2. Sign in or create an account
3. Generate an API key
4. Copy the key and add to your `.env` file

#### OpenRouter API Key

1. Visit [OpenRouter Dashboard](https://openrouter.ai/keys)
2. Sign up for a free account
3. Generate an API key
4. Copy the key and add to your `.env` file

### Environment Variables Reference

| Variable               | Required | Description                 | Default                 |
| ---------------------- | -------- | --------------------------- | ----------------------- |
| `SECRET_KEY`           | Yes      | Django secret key           | None                    |
| `OPENALEX_EMAIL`       | Yes      | Email for OpenAlex API      | None                    |
| `OPENALEX_API_KEY`     | No       | OpenAlex API key (optional) | None                    |
| `OPENROUTER_API_KEY`   | Yes      | OpenRouter API key          | None                    |
| `OPENROUTER_SITE_URL`  | No       | Site URL for OpenRouter     | `http://127.0.0.1:8080` |
| `OPENROUTER_SITE_NAME` | No       | Site name for OpenRouter    | `Research AI Assistant` |
| `DEBUG`                | No       | Django debug mode           | `True`                  |
| `ALLOWED_HOSTS`        | No       | Allowed hosts for Django    | `localhost,127.0.0.1`   |

## Testing

### Run Test Suite

```bash
# Run all tests
python manage.py test Research_AI_Assistant.tests

# Run specific test file
python test_api.py

# Run with verbosity
python manage.py test --verbosity=2
```

### Manual Testing

```bash
# Test API root
curl "http://127.0.0.1:8080/api/"

# Test error handling
curl "http://127.0.0.1:8080/api/search/"  # Missing query
curl "http://127.0.0.1:8080/api/search/?q=test&mode=invalid"  # Invalid mode

# Test all search modes
curl "http://127.0.0.0.1:8080/api/search/?q=neural+networks&mode=relevance&per_page=2"
curl "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=open_access&per_page=2"
curl "http://127.0.0.1:8080/api/search/?q=neural+networks&mode=best_match&per_page=2"

# Test cursor pagination
curl "http://127.0.0.1:8080/api/search/?q=machine+learning&per_page=5"
# Use next_cursor from response to get next page
```

### Test LLM Summarization

```bash
# Start the Django server
python manage.py runserver 8080

# In another terminal, test summarization
python summarise.py "machine learning"
```

### Sample LLM Response

When you run `python summarise.py "machine learning"`, you'll get individual summaries for each paper with bold headers and Harvard citations:

```text
**Paper [1]: Scikit-learn: Machine Learning in Python**
This paper introduces scikit-learn, a comprehensive Python library for machine learning that provides simple and efficient tools for data mining and data analysis. The library features various classification, regression, and clustering algorithms, including support vector machines, random forests, gradient boosting, k-means, and DBSCAN. Key contributions include a unified API design, extensive documentation, and integration with other scientific Python libraries like NumPy and SciPy. The authors demonstrate the library's effectiveness through benchmarks on standard datasets, showing competitive performance with established tools while maintaining ease of use. This work has significantly influenced the machine learning community by making advanced algorithms accessible to practitioners and researchers.

**Paper [2]: Genetic algorithms in search, optimization, and machine learning**
The book by Goldberg provides a comprehensive treatment of genetic algorithms and their applications in optimization and machine learning. It covers fundamental concepts including selection, crossover, and mutation operators, along with theoretical foundations and convergence properties. The author demonstrates practical applications across various domains including function optimization, machine learning classification tasks, and combinatorial optimization problems. Key insights include the role of population diversity, schema theory, and the building block hypothesis in explaining algorithm effectiveness. This seminal work established genetic algorithms as a powerful paradigm in evolutionary computation and continues to influence research in optimization and adaptive systems.

**Paper [3]: C4.5: Programs for Machine Learning**
This paper presents C4.5, an improved version of the ID3 decision tree algorithm for machine learning classification tasks. The system introduces several key enhancements including handling of continuous attributes, missing values, pruning to avoid overfitting, and rule generation from decision trees. The authors demonstrate significant improvements in accuracy and robustness compared to previous approaches through extensive experiments on benchmark datasets. C4.5's ability to generate human-readable rules while maintaining predictive power made it a cornerstone in early machine learning research and practical applications.

References

[1] Pedregosa, F.; Varoquaux, G.; Gramfort, A.; Michel, V.; Thirion, B.; Grisel, O.; Blondel, M.; Prettenhofer, P.; Weiss, R.; Dubourg, V.; Vanderplas, J.; Passos, A.; Cournapeau, D.; Brucher, M.; Perrot, M.; Duchesnay, E. (2011) 'Scikit-learn: Machine Learning in Python'. *Journal of Machine Learning Research*, 12, pp. 2825-2830.

[2] Goldberg, D.E. (1989) 'Genetic algorithms in search, optimization, and machine learning'. *Choice Reviews Online*.

[3] Quinlan, J.R. (1993) 'C4.5: Programs for Machine Learning'. *Morgan Kaufmann*.
```

### Test Coverage

The test suite covers:

- All search modes (relevance, open_access, best_match)
- Author search functionality
- Parameter validation and error handling
- JSON response structure validation
- OpenAlex API integration
- LLM summarization service
- Rate limiting behavior
- Cursor pagination functionality
- Database model operations
- Frontend JavaScript functions

## Development Guide

### Code Organization

#### Backend Structure

- **Models**: Django models with proper field types and constraints
- **Views**: Thin views that delegate business logic to services
- **Services**: Business logic separated from HTTP concerns
- **Settings**: Environment-based configuration

#### Frontend Structure

- **State Management**: Centralized AppState for global state
- **DOM Management**: DOMManager class for UI operations
- **API Layer**: Clean separation between UI and backend calls
- **Event Handling**: Event-driven architecture with proper delegation

### Adding New Features

1. **Backend Changes**:
   - Add new service methods in appropriate service files
   - Create new views for API endpoints
   - Update URL patterns
   - Add database models if needed

2. **Frontend Changes**:
   - Add new state to AppState
   - Implement UI methods in DOMManager
   - Add API calls to retrieveFromBackend or create new methods
   - Update HTML template with new elements

3. **Testing**:
   - Write unit tests for new service methods
   - Add integration tests for new endpoints
   - Test frontend functionality manually

### Code Style

- **Python**: Follow PEP 8, use type hints, docstrings for all public methods
- **JavaScript**: Use modern ES6+, camelCase naming, JSDoc comments
- **CSS**: Use BEM methodology, responsive design first
- **Database**: Use descriptive field names, proper indexes

### Performance Considerations

- **Database**: Use select_related/prefetch_related for queries
- **API**: Implement proper caching for frequently accessed data
- **Frontend**: Debounce search inputs, lazy load content
- **Rate Limiting**: Respect external API limits

## Deployment

### Production Setup

1. **Environment Configuration**:

   ```env
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   SECRET_KEY=your-production-secret-key
   ```

2. **Database Setup**:

   ```bash
   # Use PostgreSQL for production
   pip install psycopg2-binary
   # Update DATABASES in settings.py
   ```

3. **Static Files**:

   ```bash
   python manage.py collectstatic --noinput
   ```

4. **Web Server**:
   - Use Gunicorn or uWSGI with Nginx
   - Configure SSL certificates
   - Set up proper logging

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "manage.py", "runserver", "0.0.0.0:8080"]
```

### Environment Variables for Production

| Variable        | Production Value  | Description         |
| --------------- | ----------------- | ------------------- |
| `DEBUG`         | `False`           | Disable debug mode  |
| `ALLOWED_HOSTS` | `yourdomain.com`  | Allowed domains     |
| `SECRET_KEY`    | Strong random key | Django security     |
| `DATABASE_URL`  | PostgreSQL URL    | Production database |
| `STATIC_URL`    | `/static/`        | Static files URL    |
| `MEDIA_URL`     | `/media/`         | Media files URL     |

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError**: Ensure virtual environment is activated

   ```bash
   # Windows
   venv\Scripts\activate

   # Mac/Linux
   source venv/bin/activate
   ```

2. **API Key Errors**: Verify `.env` file is in `Research_Assistant/` directory

   ```bash
   # Check if env file exists and is readable
   ls -la .env
   cat .env
   ```

3. **Port Already in Use**: Change port or kill existing process

   ```bash
   # Use different port
   python manage.py runserver 8081

   # Or kill process on port 8080
   # Windows
   netstat -ano | findstr :8080
   taskkill /PID <PID> /F

   # Mac/Linux
   lsof -ti:8080 | xargs kill -9
   ```

4. **Migration Issues**: Reset database if needed

   ```bash
   # WARNING: This deletes all data
   rm db.sqlite3
   python manage.py migrate
   ```

5. **OpenAlex API Rate Limits**: Wait for rate limit reset or use API key

   ```bash
   # Check rate limit status
   curl -I https://api.openalex.org/works
   ```

6. **OpenRouter API Errors**: Verify API key and model availability
   ```bash
   # Test API key
   curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
        https://openrouter.ai/api/v1/models
   ```

### Development Tips

- Use `python manage.py check` to verify configuration
- Enable debug mode for development: `DEBUG=True` in `.env`
- Check logs with `python manage.py runserver --verbosity=2`
- Use Django shell for debugging: `python manage.py shell`
- Monitor database queries with Django Debug Toolbar

### Performance Issues

1. **Slow Search Results**:
   - Check OpenAlex API response times
   - Implement caching for frequent queries
   - Optimize database queries

2. **High Memory Usage**:
   - Limit per_page parameter
   - Use cursor pagination instead of offset
   - Implement result streaming

3. **Frontend Lag**:
   - Debounce search inputs
   - Implement virtual scrolling for large lists
   - Use requestAnimationFrame for animations

## Dependencies

### Core Dependencies (requirements.txt)

```
Django==6.0.3          # Web framework
pyalex==0.16          # OpenAlex API client
django-environ==0.11.2 # Environment variable management
django-ratelimit==4.1.0 # Rate limiting
```

### Additional Dependencies

- `requests` - HTTP client library (included with pyalex)
- `django-cors-headers` - CORS handling (if needed for APIs)
- `psycopg2-binary` - PostgreSQL adapter (production)

### Python Version

- **Required**: Python 3.8+
- **Tested**: Python 3.9, 3.10, 3.11
- **Recommended**: Python 3.11 for best performance

### Database Support

- **Development**: SQLite (default)
- **Production**: PostgreSQL (recommended)
- **Compatible**: MySQL, MariaDB (with appropriate Django backends)

### Browser Support

- **Modern**: Chrome 80+, Firefox 75+, Safari 13+, Edge 80+
- **Features**: ES6+, CSS Grid, Flexbox, Fetch API
- **Mobile**: Responsive design works on modern mobile browsers

## Contributing

### Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Code Review Guidelines

- Follow existing code style
- Add proper documentation
- Include tests for new features
- Update README if needed
- Ensure backward compatibility

### Bug Reports

- Use GitHub Issues for bug reports
- Include steps to reproduce
- Provide error logs
- Include environment details

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
- [FontAwesome](https://fontawesome.com/) for icons

## Changelog

### Version 1.0.0 (2025-03-15)

- Initial release with core functionality
- OpenAlex API integration for paper and author search
- OpenRouter LLM integration for paper summarization
- Modern web interface with binder system
- Cursor-based pagination for large result sets
- Comprehensive API documentation
- Security best practices implementation
- Rate limiting and error handling
- Full test coverage

### Version 1.1.0 (2025-03-15)

- Fixed "Load More Papers" button pagination issue
- Removed duplicate code and endpoints
- Improved cursor pagination implementation
- Enhanced error handling and validation
- Updated documentation with comprehensive details

---
