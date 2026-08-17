from fastapi import APIRouter, Depends

from app.schemas.analysis_result import AnalysisRequest, IntersectionAnalysisResponse
from app.services.analysis_orchestrator import AnalysisOrchestrator, get_analysis_orchestrator

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=IntersectionAnalysisResponse)
async def analyze_intersection(
    payload: AnalysisRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_analysis_orchestrator),
) -> IntersectionAnalysisResponse:
    return await orchestrator.analyze(payload)
