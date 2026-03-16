# AI Research Assistant

A comprehensive Django-based web application that serves as an AI-powered research assistant for academic papers. The application integrates with the OpenAlex API to search, retrieve, and process academic paper metadata, and uses OpenRouter's free LLM models to generate individual paper summaries with proper academic citations.

## 🎯 Features

### Core Functionality

- **OpenAlex API Integration**: Full integration with OpenAlex API using the pyalex library
- **OpenRouter LLM Integration**: Uses free models from OpenRouter to generate individual paper summaries
- **Paper Search Service**: Search academic papers with advanced filtering options
- **Author Search Service**: Search for academic authors via OpenAlex API
- **Metadata Extraction**: Comprehensive extraction of paper metadata including title, authors, abstract, publication year, DOI, and research concepts
- **LLM Summarization**: Generate individual summaries for each paper with Harvard-style citations
- **Cursor-based Pagination**: Efficient pagination for large result sets using OpenAlex cursor API

### Frontend Features

- **Modern UI**: Clean, responsive web interface with dark theme
- **Interactive Research View**: Dynamic chat-like interface for research conversations
- **Binder System**: Save and organize research conversations with custom colors and titles
- **Paper Cards**: Visual display of research papers with metadata and links
- **Load More Functionality**: Seamless pagination for browsing large result sets
- **Real-time Search**: Instant search with loading indicators and error handling
- **Year Filter**: Single slider to filter papers by publication year (1900-2026)
- **Dynamic Tooltip**: Interactive year display when adjusting the filter

## 🖥️ Interface Screenshots

### Main Interface

![Main Interface](Research_Assistant/Research_AI_Assistant/templates/images/Interface.png)

### Year Filter Selection

![Year Filter 1](Research_Assistant/Research_AI_Assistant/templates/images/Filter1.png)

### Filter Options

![Year Filter 2](Research_Assistant/Research_AI_Assistant/templates/images/Filter2.png)

### Research Response View

![Response Page](Research_Assistant/Research_AI_Assistant/templates/images/ResponsePage.png)

## 🛠️ Technology Stack

### Backend

- **Framework**: Django 6.0+
- **API Client**: pyalex (OpenAlex Python client)
- **LLM Provider**: OpenRouter (free models)
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Environment Management**: django-environ
- **Rate Limiting**: django-ratelimit

### Frontend

- **Template Engine**: Django Templates
- **CSS Framework**: TailwindCSS
- **Icons**: FontAwesome 6.6.0
- **JavaScript**: Vanilla JavaScript with modern ES6+ features
- **Architecture**: Component-based with DOM management

### External APIs

- **OpenAlex**: Academic paper metadata and citation data
- **OpenRouter**: LLM models for paper summarization

## 📁 Project Structure

```
AIResearchAssistant/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
└── Research_Assistant/                 # Main Django project
    ├── manage.py                       # Django management script
    ├── test_api.py                     # API testing script
    ├── test_changes.py                 # Change verification script
    ├── summarise.py                    # LLM summarization test script
    ├── .env                            # Environment variables (create this)
    ├── Research_Assistant/             # Django project config
    │   ├── settings.py                 # Django settings
    │   └── urls.py                     # Root URL configuration
    └── Research_AI_Assistant/          # Main Django app
        ├── models.py                    # Database models
        ├── views.py                     # API views and endpoints
        ├── urls.py                      # App URL configuration
        ├── tests.py                     # Unit tests
        ├── templates/                   # HTML templates
        │   ├── index.html               # Main frontend template
        │   ├── images/                  # Interface screenshots
        │   │   ├── Interface.png
        │   │   ├── Filter 1.png
        │   │   ├── Filter 2.png
        │   │   └── Response Page.png
        │   └── static/                  # Static assets
        │       ├── styles.css          # Main stylesheet
        │       └── scripts.js           # Frontend JavaScript
        └── services/                    # Business logic services
            ├── openalex_service.py      # OpenAlex API client
            ├── openrouter_service.py    # OpenRouter LLM client
            ├── extract_service.py       # Metadata extraction
            └── prompt_builder.py        # LLM prompt construction
```

## 🚀 Installation & Setup

### Prerequisites

- Python 3.8+
- pip package manager
- Git (for cloning)

### Quick Start

1. **Clone the repository**:

   ```bash
   git clone https://github.com/your-username/AIResearchAssistant.git
   cd AIResearchAssistant
   cd Research_Assistant
   ```

2. **Create and activate virtual environment**:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Mac/Linux
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file with:

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

5. **Run database migrations**:

   ```bash
   python manage.py migrate
   ```

6. **Start the development server**:

   ```bash
   python manage.py runserver 8080
   ```

7. **Access the application**:
   Open your browser and navigate to `http://127.0.0.1:8080`

## 🔑 Getting API Keys

### OpenAlex API Key

1. Visit [OpenAlex Settings](https://openalex.org/settings/api)
2. Sign in or create an account
3. Generate an API key
4. Copy the key and add to your `.env` file

### OpenRouter API Key

1. Visit [OpenRouter Dashboard](https://openrouter.ai/keys)
2. Sign up for a free account
3. Generate an API key
4. Copy the key and add to your `.env` file

## 🧪 Testing

```bash
# Run all tests
python manage.py test Research_AI_Assistant.tests

# Test API endpoints
curl "http://127.0.0.1:8080/api/"
curl "http://127.0.0.1:8080/api/search/?q=machine+learning&per_page=5"
```

## 🔒 Security Features

- **Environment Variables**: All API keys stored in `.env` file
- **No Hardcoded Secrets**: Zero hardcoded API keys in codebase
- **Rate Limiting**: Proper rate limiting for OpenAlex (100 req/s) and OpenRouter (20 req/min)
- **CSRF Protection**: Django CSRF protection enabled
- **Input Validation**: Comprehensive parameter validation on all endpoints

## 🐛 Troubleshooting

### Common Issues

1. **ModuleNotFoundError**: Ensure virtual environment is activated
2. **API Key Errors**: Verify `.env` file is in `Research_Assistant/` directory
3. **Port Already in Use**: Change port or kill existing process
4. **OpenRouter Model Errors**: System automatically falls back to other free models

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### 📋 License Summary

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ✅ **Private use** allowed
- ⚠️ **Must include** license and copyright notice
- ⚠️ **No liability** - software provided "as-is"

## 🙏 Acknowledgments

### APIs & Data Sources

- [OpenAlex](https://openalex.org/) for comprehensive academic paper data
- [OpenRouter](https://openrouter.ai/) for LLM API access and free models

### Frameworks & Libraries

- [Django](https://www.djangoproject.com/) (BSD 3-Clause) - Web framework
- [pyalex](https://github.com/J535D165/pyalex) (MIT) - OpenAlex Python client
- [django-environ](https://github.com/joke2k/django-environ) (MIT) - Environment variable management
- [django-ratelimit](https://github.com/jsocol/django-ratelimit) (BSD 3-Clause) - Rate limiting
- [requests](https://requests.readthedocs.io/) (Apache 2.0) - HTTP client library

### Frontend Assets

- [FontAwesome](https://fontawesome.com/) (CC BY 4.0) - Icons
- [TailwindCSS](https://tailwindcss.com/) (MIT) - CSS framework (used in design inspiration)

### Special Thanks

- OpenAlex community for maintaining comprehensive academic research database
- OpenRouter for providing free LLM models for research applications
- Django community for excellent documentation and framework

---
