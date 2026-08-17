from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.agent_outputs import Finding
from app.schemas.geojson import FeatureCollection
from app.schemas.intersection import Location


class AnalysisRequest(Location):
    side_length_meters: int = Field(default=200, ge=20, le=500, alias="sideLengthMeters")


class ClassicCaseMatch(BaseModel):
    id: str
    title: str
    location: str
    summary: str
    source_url: str = Field(alias="sourceUrl")
    before_image_url: str | None = Field(default=None, alias="beforeImageUrl")
    after_image_url: str | None = Field(default=None, alias="afterImageUrl")
    match_reason: str = Field(alias="matchReason")
    score: float = Field(ge=0, le=1)


class ImagePayload(BaseModel):
    mime_type: str = Field(alias="mimeType")
    data_url: str = Field(alias="dataUrl")


class IntersectionAnalysisResponse(BaseModel):
    analysis_id: str = Field(alias="analysisId")
    status: Literal[
        "NO_PROBLEM",
        "NOT_INTERSECTION",
        "IMPROVEMENT_PROPOSED",
        "ANALYSIS_FAILED",
    ]
    location: Location
    bounds: dict[str, float]
    intersection_type: str | None = Field(default=None, alias="intersectionType")
    overall_score: int | None = Field(default=None, alias="overallScore")
    problem_summary: str = Field(default="", alias="problemSummary")
    improvement_summary: str = Field(default="", alias="improvementSummary")
    findings: list[Finding] = Field(default_factory=list)
    matched_cases: list[ClassicCaseMatch] = Field(default_factory=list, alias="matchedCases")
    original_geojson: FeatureCollection = Field(alias="originalGeojson")
    enriched_geojson: FeatureCollection = Field(alias="enrichedGeojson")
    redesigned_geojson: FeatureCollection | None = Field(default=None, alias="redesignedGeojson")
    source_image: ImagePayload | None = Field(default=None, alias="sourceImage")
    rendered_image: ImagePayload | None = Field(default=None, alias="renderedImage")
    metadata: dict[str, Any] = Field(default_factory=dict)
