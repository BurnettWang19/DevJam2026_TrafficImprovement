import json

from app.core.config import settings
from app.schemas.agent_outputs import IntersectionClassification
from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient


class IntersectionClassifierAgent:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def classify(
        self,
        scene: FeatureCollection,
        system_prompt: str,
    ) -> IntersectionClassification:
        prompt = f"""
Classify the road topology represented by this GeoJSON. Return NOT_INTERSECTION when the scene
contains only a road segment and no actual road junction. Base the answer on road centerline
connectivity, not visual guesswork. Explain briefly in Traditional Chinese.

GeoJSON:
{json.dumps(scene.model_dump(by_alias=True), ensure_ascii=False)}
"""
        result = await self.client.structured(
            model=settings.gemini_reasoning_model,
            prompt=prompt,
            response_schema=IntersectionClassification,
            system_instruction=system_prompt,
        )
        return IntersectionClassification.model_validate(result)
