from pydantic import BaseModel, Field


class RoadFeature(BaseModel):
    id: str
    geometry: dict
    attributes: dict = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=lambda: ["osm"])
    confidence: float | None = Field(default=1.0, ge=0, le=1)
