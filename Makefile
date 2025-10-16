SHELL := pwsh

.PHONY: install dev lint format type test check api cli docker-up docker-down

install:
	poetry install --with dev

dev:
	pre-commit install

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

ty:
	mypy src

test:
	pytest

check: format ty test

api:
	uvicorn senasa_pipeline.presentation.api:app --reload

cli:
	poetry run senasa --help

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v
