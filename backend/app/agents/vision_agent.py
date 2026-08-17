import json

from app.core.config import settings
from app.schemas.agent_outputs import VisionExtraction
from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient
from app.services.imagery.provider import ImageryArtifact


class VisionAgent:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def extract(
        self,
        image: ImageryArtifact,
        osm_scene: FeatureCollection,
        system_prompt: str,
    ) -> VisionExtraction:
        prompt = f"""
Analyze this north-up satellite image of a road intersection. Detect only visible vector
features that are missing or incomplete in the supplied OpenStreetMap data: lane markings,
stop lines, channelization lines, crosswalks, sidewalk edges, traffic islands, and cycleways.
Return pixel coordinates in the original {image.width}x{image.height} image coordinate system,
where (0,0) is top-left. Do not invent obscured features. Use confidence below 0.6 when unsure.

Existing OSM GeoJSON:
{json.dumps(osm_scene.model_dump(by_alias=True), ensure_ascii=False)}
"""
        result = await self.client.structured(
            model=settings.gemini_vision_model,
            prompt=prompt,
            response_schema=VisionExtraction,
            system_instruction=system_prompt,
            image=image.data,
            image_mime_type=image.mime_type,
        )
        return VisionExtraction.model_validate(result)
