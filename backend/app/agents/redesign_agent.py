import json

from app.core.config import settings
from app.schemas.agent_outputs import RedesignOutput, SpecialistOutput
from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient


class RedesignAgent:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def redesign(
        self,
        scene: FeatureCollection,
        specialists: list[SpecialistOutput],
        system_prompt: str,
        bounds: dict[str, float],
    ) -> RedesignOutput:
        prompt = f"""
Consolidate the three specialist proposals into the smallest coherent set of road-design geometry
operations. Resolve conflicts between proposals. Coordinates must remain within these WGS84 bounds:
{json.dumps(bounds)}. Do not remove existing roads. Prefer moving/replacing deficient facilities and
adding only necessary safety features. Explain the redesign in Traditional Chinese.

Scene:
{json.dumps(scene.model_dump(by_alias=True), ensure_ascii=False)}

Specialist proposals:
{json.dumps([item.model_dump() for item in specialists], ensure_ascii=False)}
"""
        result = await self.client.structured(
            model=settings.gemini_reasoning_model,
            prompt=prompt,
            response_schema=RedesignOutput,
            system_instruction=system_prompt,
        )
        return RedesignOutput.model_validate(result)

