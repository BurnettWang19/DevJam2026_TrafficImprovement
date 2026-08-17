import asyncio
import base64
from dataclasses import dataclass, field
from uuid import uuid4

from app.agents.evaluator import EvaluatorAgent
from app.agents.intersection_classifier import IntersectionClassifierAgent
from app.agents.redesign_agent import RedesignAgent
from app.agents.render_agent import RenderAgent
from app.agents.specialists import CrosswalkAgent, LaneMarkingAgent, SidewalkAgent
from app.agents.vision_agent import VisionAgent
from app.core.config import settings
from app.core.exceptions import NoRoadDataFoundError
from app.core.prompt_loader import PromptLoader
from app.schemas.agent_outputs import Finding, SpecialistOutput
from app.schemas.analysis_result import (
    AnalysisRequest,
    ImagePayload,
    IntersectionAnalysisResponse,
)
from app.schemas.geojson import FeatureCollection
from app.schemas.intersection import Location
from app.services.cases.matcher import ClassicCaseMatcher
from app.services.cases.repository import ClassicCaseRepository
from app.services.gemini.client import GeminiClient
from app.services.geospatial.bounds import GeoBounds, square_bounds
from app.services.imagery.google_static_maps import GoogleStaticMapsProvider
from app.services.imagery.provider import ImageryArtifact
from app.services.osm.client import OSMClient
from app.services.osm.parser import OSMParser
from app.services.vector.fusion import VectorFusionService
from app.services.vector.validation import VectorRedesignService


@dataclass
class AnalysisContext:
    analysis_id: str
    request: AnalysisRequest
    bounds: GeoBounds
    original: FeatureCollection = field(default_factory=FeatureCollection)
    enriched: FeatureCollection = field(default_factory=FeatureCollection)
    imagery: ImageryArtifact | None = None
    findings: list[Finding] = field(default_factory=list)
    specialists: list[SpecialistOutput] = field(default_factory=list)


class AnalysisOrchestrator:
    def __init__(self) -> None:
        self.osm_client = OSMClient()
        self.osm_parser = OSMParser()
        self.imagery = GoogleStaticMapsProvider()
        self.prompt_loader = PromptLoader(settings.evaluation_prompt_path)
        self.case_repository = ClassicCaseRepository(settings.classic_cases_path)
        self.case_matcher = ClassicCaseMatcher()
        self.fusion = VectorFusionService()
        self.vector_redesign = VectorRedesignService()

    async def analyze(self, request: AnalysisRequest) -> IntersectionAnalysisResponse:
        bounds = square_bounds(request.latitude, request.longitude, request.side_length_meters)
        context = AnalysisContext(str(uuid4()), request, bounds)

        raw_osm, imagery = await asyncio.gather(
            self.osm_client.fetch_scene(bounds),
            self.imagery.fetch(request.latitude, request.longitude, request.side_length_meters),
        )
        context.original = self.osm_parser.parse_scene(raw_osm)
        if not any(
            feature.properties.get("featureType") == "road"
            for feature in context.original.features
        ):
            raise NoRoadDataFoundError()
        context.imagery = imagery

        gemini = GeminiClient()
        vision = await VisionAgent(gemini).extract(
            imagery,
            context.original,
            self.prompt_loader.load(),
        )
        context.enriched = self.fusion.fuse(
            context.original,
            vision,
            bounds,
            imagery.width,
            imagery.height,
        )

        evaluation = await EvaluatorAgent(gemini).evaluate(
            context.enriched,
            self.prompt_loader.load(),
        )
        context.findings.extend(evaluation.findings)
        if not evaluation.has_major_problem:
            return self._response(
                context,
                status="NO_PROBLEM",
                overall_score=evaluation.overall_score,
                problem_summary=evaluation.summary,
            )

        classification = await IntersectionClassifierAgent(gemini).classify(
            context.enriched,
            self.prompt_loader.load(),
        )
        if classification.intersection_type == "NOT_INTERSECTION":
            return self._response(
                context,
                status="NOT_INTERSECTION",
                overall_score=evaluation.overall_score,
                problem_summary=classification.reason,
                intersection_type=classification.intersection_type,
            )

        context.specialists = list(
            await asyncio.gather(
                CrosswalkAgent(gemini).analyze(
                    context.enriched,
                    self.prompt_loader.load(),
                    classification.intersection_type,
                ),
                SidewalkAgent(gemini).analyze(
                    context.enriched,
                    self.prompt_loader.load(),
                    classification.intersection_type,
                ),
                LaneMarkingAgent(gemini).analyze(
                    context.enriched,
                    self.prompt_loader.load(),
                    classification.intersection_type,
                ),
            )
        )
        context.findings = [
            finding
            for specialist in context.specialists
            for finding in specialist.findings
        ] or context.findings

        redesign = await RedesignAgent(gemini).redesign(
            context.enriched,
            context.specialists,
            self.prompt_loader.load(),
            bounds.as_dict(),
        )
        redesigned_geojson = self.vector_redesign.apply(
            context.enriched,
            redesign.operations,
            bounds,
        )
        rendered_bytes, rendered_mime = await RenderAgent(gemini).render(
            imagery.data,
            redesigned_geojson,
            redesign.summary,
            self.prompt_loader.load(),
        )
        matched_cases = self.case_matcher.match(
            self.case_repository.list(),
            classification.intersection_type,
            context.findings,
            settings.max_classic_case_matches,
        )
        return self._response(
            context,
            status="IMPROVEMENT_PROPOSED",
            overall_score=evaluation.overall_score,
            problem_summary=evaluation.summary,
            improvement_summary=redesign.summary,
            intersection_type=classification.intersection_type,
            redesigned_geojson=redesigned_geojson,
            rendered_image=self._image_payload(rendered_bytes, rendered_mime),
            matched_cases=matched_cases,
        )

    def _response(
        self,
        context: AnalysisContext,
        *,
        status: str,
        overall_score: int,
        problem_summary: str,
        improvement_summary: str = "",
        intersection_type: str | None = None,
        redesigned_geojson: FeatureCollection | None = None,
        rendered_image: ImagePayload | None = None,
        matched_cases: list | None = None,
    ) -> IntersectionAnalysisResponse:
        assert context.imagery is not None
        return IntersectionAnalysisResponse(
            analysisId=context.analysis_id,
            status=status,
            location=Location(latitude=context.request.latitude, longitude=context.request.longitude),
            bounds=context.bounds.as_dict(),
            intersectionType=intersection_type,
            overallScore=overall_score,
            problemSummary=problem_summary,
            improvementSummary=improvement_summary,
            findings=context.findings,
            matchedCases=matched_cases or [],
            originalGeojson=context.original,
            enrichedGeojson=context.enriched,
            redesignedGeojson=redesigned_geojson,
            sourceImage=self._image_payload(context.imagery.data, context.imagery.mime_type),
            renderedImage=rendered_image,
            metadata={
                "visionModel": settings.gemini_vision_model,
                "reasoningModel": settings.gemini_reasoning_model,
                "imageModel": settings.gemini_image_model,
                "conceptOnly": True,
            },
        )

    @staticmethod
    def _image_payload(data: bytes, mime_type: str) -> ImagePayload:
        encoded = base64.b64encode(data).decode("ascii")
        return ImagePayload(mimeType=mime_type, dataUrl=f"data:{mime_type};base64,{encoded}")


def get_analysis_orchestrator() -> AnalysisOrchestrator:
    return AnalysisOrchestrator()
