from fastapi import FastAPI
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from senasa_pipeline.presentation.api.routes.senasa import router as senasa_router
from senasa_pipeline.presentation.api.routes.health import router as health_router

app = FastAPI(title="SENASA Data Pipeline", version="0.2.0")
app.include_router(health_router)
app.include_router(senasa_router)

registry = CollectorRegistry()

@app.get("/metrics")
def metrics() -> Response:  # type: ignore[misc]
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
