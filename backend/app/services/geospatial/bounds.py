from dataclasses import dataclass
from math import cos, pi


@dataclass(frozen=True)
class GeoBounds:
    south: float
    west: float
    north: float
    east: float

    def as_dict(self) -> dict[str, float]:
        return {
            "south": self.south,
            "west": self.west,
            "north": self.north,
            "east": self.east,
        }


def square_bounds(latitude: float, longitude: float, side_length_meters: int) -> GeoBounds:
    half = side_length_meters / 2
    latitude_delta = half / 111_320
    longitude_delta = half / (111_320 * cos(latitude * pi / 180))
    return GeoBounds(
        south=latitude - latitude_delta,
        west=longitude - longitude_delta,
        north=latitude + latitude_delta,
        east=longitude + longitude_delta,
    )


def pixel_to_lonlat(
    x: float,
    y: float,
    width: int,
    height: int,
    bounds: GeoBounds,
) -> list[float]:
    longitude = bounds.west + (x / width) * (bounds.east - bounds.west)
    latitude = bounds.north - (y / height) * (bounds.north - bounds.south)
    return [longitude, latitude]

