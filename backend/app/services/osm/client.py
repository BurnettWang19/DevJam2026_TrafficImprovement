import httpx

from app.core.config import settings
from app.core.exceptions import OSMAPIError
from app.services.geospatial.bounds import GeoBounds


class OSMClient:
    def __init__(
        self,
        overpass_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.overpass_url = overpass_url or settings.overpass_url
        self.timeout_seconds = timeout_seconds or settings.osm_timeout_seconds

    async def fetch_roads(
        self, latitude: float, longitude: float, radius_meters: int
    ) -> dict:
        query = self._build_road_query(latitude, longitude, radius_meters)
        endpoints = list(dict.fromkeys([self.overpass_url, settings.overpass_fallback_url]))
        last_error: Exception | None = None

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "RoadIntersectionAI/0.1"},
        ) as client:
            for endpoint in endpoints:
                try:
                    response = await client.post(endpoint, data={"data": query})
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc

        raise OSMAPIError() from last_error

    async def fetch_scene(self, bounds: GeoBounds) -> dict:
        query = self._build_scene_query(bounds)
        endpoints = list(dict.fromkeys([self.overpass_url, settings.overpass_fallback_url]))
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "RoadIntersectionAI/0.1"},
        ) as client:
            for endpoint in endpoints:
                try:
                    response = await client.post(endpoint, data={"data": query})
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
        raise OSMAPIError() from last_error

    @staticmethod
    def _build_road_query(latitude: float, longitude: float, radius_meters: int) -> str:
        return f"""
        [out:json][timeout:25];
        (
          way(around:{radius_meters},{latitude},{longitude})["highway"]
            ["highway"!~"footway|path|cycleway|steps|pedestrian|platform|corridor"];
        );
        out body;
        >;
        out skel qt;
        """

    @staticmethod
    def _build_scene_query(bounds: GeoBounds) -> str:
        bbox = f"{bounds.south},{bounds.west},{bounds.north},{bounds.east}"
        return f"""
        [out:json][timeout:25];
        (
          way({bbox})["highway"];
          node({bbox})["highway"~"crossing|traffic_signals|stop|give_way"];
          way({bbox})["traffic_calming"];
          way({bbox})["barrier"];
        );
        out body;
        >;
        out skel qt;
        """
