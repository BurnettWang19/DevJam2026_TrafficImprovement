import json

from app.core.config import settings
from app.schemas.agent_outputs import SpecialistOutput
from app.schemas.geojson import FeatureCollection
from app.services.gemini.client import GeminiClient


SPECIALIST_RULES = {
    "crosswalk": "Check setback, crossing length, continuity, refuge space, visibility and turning conflicts.",
    "sidewalk": "Check continuity, effective width, corner waiting space, accessibility and obstructions.",
    "lane_marking": "Check offset turn lanes, channelization, stop lines, turning paths and pedestrian/bicycle conflicts.",
}


class SpecialistAgent:
    def __init__(self, category: str, client: GeminiClient) -> None:
        self.category = category
        self.client = client

    async def analyze(
        self,
        scene: FeatureCollection,
        system_prompt: str,
        intersection_type: str,
    ) -> SpecialistOutput:
        prompt = f"""
You are the {self.category} specialist for a {intersection_type} intersection.
{SPECIALIST_RULES[self.category]}
Use the system instruction as the design authority. Cite evidence IDs. Propose only necessary
geometry operations using WGS84 [longitude, latitude] coordinates already inside the scene area.
Return Traditional Chinese descriptions. If no issue exists, return empty findings and operations.

GeoJSON:
{json.dumps(scene.model_dump(by_alias=True), ensure_ascii=False)}
"""
        result = await self.client.structured(
            model=settings.gemini_reasoning_model,
            prompt=prompt,
            response_schema=SpecialistOutput,
            system_instruction=system_prompt,
        )
        output = SpecialistOutput.model_validate(result)
        output.category = self.category  # Enforce the role even if the model mislabeled it.
        return output


class CrosswalkAgent(SpecialistAgent):
    def __init__(self, client: GeminiClient) -> None:
        super().__init__("crosswalk", client)


class SidewalkAgent(SpecialistAgent):
    def __init__(self, client: GeminiClient) -> None:
        super().__init__("sidewalk", client)


class LaneMarkingAgent(SpecialistAgent):
    def __init__(self, client: GeminiClient) -> None:
        super().__init__("lane_marking", client)

