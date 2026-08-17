from dataclasses import dataclass, field


@dataclass(frozen=True)
class NormalizedRoad:
    id: str
    coordinates: list[tuple[float, float]]
    attributes: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=lambda: ["osm"])
    confidence: float = 1.0
