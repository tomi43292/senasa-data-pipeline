from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
def health() -> dict[str, str]:  # type: ignore[misc]
    return {"status": "ok"}
