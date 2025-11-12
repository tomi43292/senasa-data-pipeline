# SENASA Data Pipeline

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Modern data pipeline for SENASA with Clean Architecture, FastAPI, and enterprise-grade tooling.

## 🏗️ Architecture

This project implements a production-ready ETL pipeline following **Clean Architecture** principles:

- **Domain Layer**: Pure business entities and interfaces
- **Application Layer**: Use cases and orchestration logic  
- **Infrastructure Layer**: External adapters and repositories
- **Presentation Layer**: FastAPI REST API and CLI interface

## 🚀 Tech Stack

- **Backend**: FastAPI, Uvicorn, Pydantic v2
- **Data Processing**: Pandas, Polars, DuckDB, Apache Arrow
- **Async**: Celery with Redis, HTTPx, Tenacity
- **DevOps**: Poetry, Ruff, MyPy, Pre-commit hooks
- **Monitoring**: Loguru, Prometheus metrics, Structlog
- **Testing**: Pytest with coverage and async support

## 📋 Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

## ⚙️ Environment Setup

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Configure your environment variables:

```bash
AFIP_CUIT=20123456789          # Your AFIP CUIT for authentication
HTTP_TIMEOUT=45                # HTTP request timeout in seconds
SESSION_TTL_HOURS=12           # Session validity period in hours
```

> ⚠️ **Security**: The `.env` file is excluded from version control and contains sensitive credentials.

## 🛠️ Installation & Setup

```bash
# Install dependencies
poetry install --with dev

# Set up pre-commit hooks
pre-commit install

# Activate virtual environment
poetry shell
```

## 🏃‍♂️ Quick Start

### API Server
```bash
poetry run uvicorn senasa_pipeline.presentation.api.main:app --reload
```

### CLI Interface
```bash
poetry run senasa --help
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/auth/ensure_session` | Ensures active SENASA session |
| `GET` | `/health` | Health check endpoint |
| `GET` | `/metrics` | Prometheus metrics |

## 🧪 Testing

```bash
# Run all tests with coverage
poetry run pytest --cov=src --cov-report=term-missing

# Run specific test file
poetry run pytest tests/unit/test_auth.py -v

# Run with performance profiling
poetry run pytest --benchmark-only
```

## 📊 Development

### Code Quality
- **Linting**: `poetry run ruff check --fix`
- **Formatting**: `poetry run ruff format`
- **Type Checking**: `poetry run mypy src`

### Database Migrations
```bash
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "description"
```

## 📈 Performance

- **Ruff**: 10-100x faster than traditional linting tools
- **Polars**: Out-of-core data processing for large datasets
- **Async/Await**: Non-blocking I/O for concurrent operations
- **Redis**: Session caching and Celery task queue

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 👤 Author

**Tomás Daniel González**
- LinkedIn: https://www.linkedin.com/in/tomas-daniel-gonzalez-1b9b4528b
- GitHub: https://github.com/tomi43292

---

⭐ If this project helped you, consider giving it a star!
