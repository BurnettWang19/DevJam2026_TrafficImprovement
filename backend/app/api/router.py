from fastapi import APIRouter

from app.api.intersections import router as intersections_router

api_router = APIRouter()


@api_router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(intersections_router)
