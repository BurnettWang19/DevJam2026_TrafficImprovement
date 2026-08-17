from dataclasses import dataclass


@dataclass(frozen=True)
class IntersectionLocation:
    latitude: float
    longitude: float
