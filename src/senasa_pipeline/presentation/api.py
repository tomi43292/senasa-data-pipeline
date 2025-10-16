from fastapi import FastAPI
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

app = FastAPI(title="SENASA Data Pipeline", version="0.1.0")

registry = CollectorRegistry()

@app.get("/health", tags=["health"])  # type: ignore[misc]
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/metrics")  # type: ignore[misc]
def metrics() -> Response:
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
