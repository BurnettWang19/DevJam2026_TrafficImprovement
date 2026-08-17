import json

from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient


class RenderAgent:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def render(
        self,
        source_image: bytes,
        redesigned: FeatureCollection,
        summary: str,
        system_prompt: str,
    ) -> tuple[bytes, str]:
        prompt = f"""
Create a north-up, top-down conceptual road-design visualization by editing the provided satellite
image. Preserve buildings, parcels and geographic context. Overlay the redesigned intersection with
precise, clean engineering-style markings: white crosswalks and lane lines, pale concrete sidewalks,
green protected cycling space, and landscaped pedestrian refuge islands. Do not add labels or text.
This is a concept visualization, not a construction drawing.

Road-design authority and evaluation criteria:
{system_prompt}

Design summary: {summary}
Redesigned GeoJSON: {json.dumps(redesigned.model_dump(by_alias=True), ensure_ascii=False)}
"""
        return await self.client.generate_image(prompt=prompt, source_image=source_image)
