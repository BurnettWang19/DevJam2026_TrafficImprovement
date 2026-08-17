from fastapi.testclient import TestClient

from app.api.intersections import get_intersection_service
from app.main import app
from app.schemas.geojson import Feature, FeatureCollection
from app.schemas.intersection import IntersectionCreateRequest, IntersectionResponse, Location


class StubIntersectionService:
    async def create_from_location(
        self, payload: IntersectionCreateRequest
    ) -> IntersectionResponse:
        return IntersectionResponse(
            intersectionId="test-id",
            location=Location(latitude=payload.latitude, longitude=payload.longitude),
            geojson=FeatureCollection(
                features=[
                    Feature(
                        geometry={
                            "type": "LineString",
                            "coordinates": [[121.565, 25.033], [121.566, 25.034]],
                        },
                        properties={"featureType": "road"},
                    )
                ]
            ),
        )


def test_create_intersection_validates_coordinates() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/intersections",
        json={"latitude": 95, "longitude": 121.565, "radiusMeters": 100},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"


def test_create_intersection_returns_geojson() -> None:
    app.dependency_overrides[get_intersection_service] = lambda: StubIntersectionService()
    client = TestClient(app)

    response = client.post(
        "/api/intersections",
        json={"latitude": 25.033, "longitude": 121.565, "radiusMeters": 100},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intersectionId"] == "test-id"
    assert body["geojson"]["type"] == "FeatureCollection"
    assert body["geojson"]["features"][0]["geometry"]["type"] == "LineString"

    app.dependency_overrides.clear()
