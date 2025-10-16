FROM python:3.11-slim AS base

# Install uv (ultra-fast installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install deps
RUN uv pip install --system -e ".[dev]"

# Copy source
COPY src ./src

# Install package
RUN uv pip install --system -e .

EXPOSE 8000
CMD ["uvicorn","senasa_pipeline.presentation.api:app","--host","0.0.0.0","--port","8000"]
