from math import cos, log2, pi

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ExternalServiceError
from app.services.imagery.provider import ImageryArtifact


class GoogleStaticMapsProvider:
    async def fetch(self, latitude: float, longitude: float, side_length_meters: int) -> ImageryArtifact:
        if not settings.google_maps_api_key:
            raise ConfigurationError(
                "GOOGLE_MAPS_API_KEY_MISSING",
                "Set GOOGLE_MAPS_API_KEY in backend/.env and enable Maps Static API billing.",
            )

        meters_per_pixel = side_length_meters / settings.imagery_width
        zoom = round(log2(156543.03392 * cos(latitude * pi / 180) / meters_per_pixel))
        zoom = max(1, min(21, zoom))
        params = {
            "center": f"{latitude},{longitude}",
            "zoom": zoom,
            "size": f"{settings.imagery_width}x{settings.imagery_height}",
            "scale": settings.imagery_scale,
            "maptype": "satellite",
            "format": "png",
            "key": settings.google_maps_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/staticmap",
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                "IMAGERY_FETCH_FAILED",
                "Unable to fetch the licensed satellite image from Google Maps Static API.",
            ) from exc

        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise ExternalServiceError(
                "IMAGERY_FETCH_FAILED",
                "Google Maps Static API did not return an image. Check API key and billing settings.",
            )
        return ImageryArtifact(
            data=response.content,
            mime_type=content_type.split(";")[0],
            width=settings.imagery_width * settings.imagery_scale,
            height=settings.imagery_height * settings.imagery_scale,
        )

