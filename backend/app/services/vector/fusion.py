from uuid import uuid4

from app.schemas.agent_outputs import VisionExtraction
from app.schemas.geojson import Feature, FeatureCollection
from app.services.geospatial.bounds import GeoBounds, pixel_to_lonlat


class VectorFusionService:
    def fuse(
        self,
        osm: FeatureCollection,
        extraction: VisionExtraction,
        bounds: GeoBounds,
        image_width: int,
        image_height: int,
    ) -> FeatureCollection:
        features = list(osm.features)
        for vector in extraction.vectors:
            if vector.confidence < 0.6 or len(vector.pixel_coordinates) < 2:
                continue
            coordinates = [
                pixel_to_lonlat(point[0], point[1], image_width, image_height, bounds)
                for point in vector.pixel_coordinates
                if len(point) == 2
            ]
            if len(coordinates) < 2:
                continue
            if vector.geometry_type == "Polygon" and coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            geometry_coordinates = [coordinates] if vector.geometry_type == "Polygon" else coordinates
            features.append(
                Feature(
                    geometry={
                        "type": vector.geometry_type,
                        "coordinates": geometry_coordinates,
                    },
                    properties={
                        "id": f"gemini_{uuid4().hex[:12]}",
                        "featureType": vector.feature_type,
                        "sources": ["GEMINI_VISION"],
                        "confidence": vector.confidence,
                    },
                )
            )
        return FeatureCollection(features=features)
