from fastapi import APIRouter, Depends

from app.schemas.intersection import IntersectionCreateRequest, IntersectionResponse
from app.services.intersection_service import IntersectionService, get_intersection_service

router = APIRouter(prefix="/intersections", tags=["intersections"])


@router.post("", response_model=IntersectionResponse)
async def create_intersection(
    payload: IntersectionCreateRequest,
    service: IntersectionService = Depends(get_intersection_service),
) -> IntersectionResponse:
    return await service.create_from_location(payload)
