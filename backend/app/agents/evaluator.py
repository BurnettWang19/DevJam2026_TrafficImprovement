import json

from app.core.config import settings
from app.schemas.agent_outputs import EvaluationOutput
from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient


class EvaluatorAgent:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

    async def evaluate(
        self,
        scene: FeatureCollection,
        system_prompt: str,
    ) -> EvaluationOutput:
        prompt = f"""
Evaluate this intersection strictly according to the system instruction. Evidence must cite
feature IDs from the GeoJSON. Set has_major_problem=true only when the supplied criteria identify
a meaningful safety or design deficiency. Return concise Traditional Chinese explanations.

GeoJSON:
{json.dumps(scene.model_dump(by_alias=True), ensure_ascii=False)}
"""
        result = await self.client.structured(
            model=settings.gemini_reasoning_model,
            prompt=prompt,
            response_schema=EvaluationOutput,
            system_instruction=system_prompt,
        )
        return EvaluationOutput.model_validate(result)

