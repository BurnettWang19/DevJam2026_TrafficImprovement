from typing import Literal

from pydantic import BaseModel, Field


class AnalysisFinding(BaseModel):
    issue_type: str = Field(alias="issueType")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score: int | None = Field(default=None, ge=0, le=100)
    evidence: dict = Field(default_factory=dict)
    recommendations: list[dict] = Field(default_factory=list)
