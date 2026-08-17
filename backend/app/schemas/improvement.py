from pydantic import BaseModel, Field


class ImprovementRecommendation(BaseModel):
    id: str
    description: str
    geometry_changes: list[dict] = Field(default_factory=list, alias="geometryChanges")
