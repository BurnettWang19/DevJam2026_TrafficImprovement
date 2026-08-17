from typing import Literal

from pydantic import BaseModel, Field


FeatureType = Literal[
    "road",
    "lane_marking",
    "stop_line",
    "crosswalk",
    "sidewalk",
    "traffic_island",
    "cycleway",
]


class PixelVector(BaseModel):
    feature_type: FeatureType
    geometry_type: Literal["LineString", "Polygon"]
    pixel_coordinates: list[list[float]]
    confidence: float = Field(ge=0, le=1)


class VisionExtraction(BaseModel):
    vectors: list[PixelVector] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    category: Literal["crosswalk", "sidewalk", "lane_marking", "overall"]
    title: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score: int = Field(ge=0, le=100)
    evidence_feature_ids: list[str] = Field(default_factory=list)
    recommendation: str


class EvaluationOutput(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    has_major_problem: bool
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class IntersectionClassification(BaseModel):
    intersection_type: Literal[
        "ORTHOGONAL",
        "T_JUNCTION",
        "SKEWED",
        "ROUNDABOUT",
        "MULTI_LEG",
        "OTHER_INTERSECTION",
        "NOT_INTERSECTION",
    ]
    confidence: float = Field(ge=0, le=1)
    reason: str


class GeometryOperation(BaseModel):
    operation: Literal["ADD", "MOVE", "REPLACE", "REMOVE"]
    feature_type: FeatureType
    target_feature_id: str | None = None
    geometry_type: Literal["LineString", "Polygon"] | None = None
    coordinates: list[list[float]] = Field(default_factory=list)
    description: str


class SpecialistOutput(BaseModel):
    category: Literal["crosswalk", "sidewalk", "lane_marking"]
    findings: list[Finding] = Field(default_factory=list)
    proposed_operations: list[GeometryOperation] = Field(default_factory=list)


class RedesignOutput(BaseModel):
    summary: str
    operations: list[GeometryOperation] = Field(default_factory=list)
