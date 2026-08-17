import httpx

from app.core.config import settings
from app.core.exceptions import OSMAPIError


class OSMClient:
    def __init__(self, overpass_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.overpass_url = overpass_url or settings.overpass_url
        self.timeout_seconds = timeout_seconds or settings.osm_timeout_seconds

    async def fetch_roads(
        self, latitude: float, longitude: float, radius_meters: int
    ) -> dict:
        query = self._build_road_query(latitude, longitude, radius_meters)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.overpass_url, data={"data": query})
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OSMAPIError() from exc

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
