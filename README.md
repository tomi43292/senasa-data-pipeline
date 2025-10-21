# README - SENASA Data Pipeline

Este proyecto implementa un pipeline ETL moderno para datos SENASA usando Clean Architecture y buenas prácticas.

## Requisitos
- Python 3.11+
- Poetry

## Variables de entorno (.env)
Crea un archivo `.env` en la raíz del proyecto basado en `.env.example`:

```
AFIP_CUIT=20123456789
HTTP_TIMEOUT=45
SESSION_TTL_HOURS=12
```

- `AFIP_CUIT`: CUIT utilizado para obtener token/sign del Portal AFIP.
- `HTTP_TIMEOUT`: Timeout (segundos) para requests HTTP.
- `SESSION_TTL_HOURS`: Horas de validez de la sesión SENASA antes de refrescar.

El archivo `.env` está ignorado por Git y no debe commitearse.

## Instalación
```powershell
poetry install --with dev
pre-commit install
```

## Levantar API local
```powershell
poetry run uvicorn senasa_pipeline.presentation.api.main:app --reload
```

## Endpoints
- `POST /v1/auth/ensure_session`: Garantiza sesión SENASA activa (usa .env)
- `GET /health`
- `GET /metrics`

## Tests
```powershell
poetry run pytest -q
```
