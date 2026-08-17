from uuid import uuid4

from app.core.exceptions import NoRoadDataFoundError
from app.schemas.geojson import Feature, FeatureCollection
from app.schemas.intersection import IntersectionCreateRequest, IntersectionResponse, Location
from app.services.osm.client import OSMClient
from app.services.osm.parser import OSMParser


class IntersectionService:
    def __init__(self, osm_client: OSMClient, osm_parser: OSMParser) -> None:
        self.osm_client = osm_client
        self.osm_parser = osm_parser

    async def create_from_location(
        self, payload: IntersectionCreateRequest
    ) -> IntersectionResponse:
        raw_osm = await self.osm_client.fetch_roads(
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_meters=payload.radius_meters,
        )
        roads = self.osm_parser.parse_roads(raw_osm)
        if not roads:
            raise NoRoadDataFoundError()

        features = [
            Feature(
                geometry={"type": "LineString", "coordinates": road.coordinates},
                properties={
                    "id": road.id,
                    "featureType": "road",
                    "sources": road.sources,
                    "confidence": road.confidence,
                    **road.attributes,
                },
            )
            for road in roads
        ]

        return IntersectionResponse(
            intersectionId=str(uuid4()),
            location=Location(latitude=payload.latitude, longitude=payload.longitude),
            geojson=FeatureCollection(features=features),
        )


def get_intersection_service() -> IntersectionService:
    return IntersectionService(osm_client=OSMClient(), osm_parser=OSMParser())
