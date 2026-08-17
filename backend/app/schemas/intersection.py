from pydantic import BaseModel, Field, field_validator

from app.schemas.geojson import FeatureCollection


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class IntersectionCreateRequest(Location):
    radius_meters: int = Field(default=100, ge=10, le=500, alias="radiusMeters")


class IntersectionResponse(BaseModel):
    intersection_id: str = Field(alias="intersectionId")
    location: Location
    geojson: FeatureCollection


class SourceRef(BaseModel):
    name: str
    external_id: str | None = None


class GeographicElement(BaseModel):
    id: str
    geometry: dict
    attributes: dict = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class IntersectionScene(BaseModel):
    id: str
    location: Location
    bounds: dict | None = None
    roads: list[GeographicElement] = Field(default_factory=list)
    lanes: list[GeographicElement] = Field(default_factory=list)
    crosswalks: list[GeographicElement] = Field(default_factory=list)
    sidewalks: list[GeographicElement] = Field(default_factory=list)
    stop_lines: list[GeographicElement] = Field(default_factory=list, alias="stopLines")
    traffic_islands: list[GeographicElement] = Field(default_factory=list, alias="trafficIslands")
    traffic_signals: list[GeographicElement] = Field(default_factory=list, alias="trafficSignals")
    barriers: list[GeographicElement] = Field(default_factory=list)

    @field_validator("bounds")
    @classmethod
    def bounds_must_be_geojson_like(cls, value: dict | None) -> dict | None:
        return value
