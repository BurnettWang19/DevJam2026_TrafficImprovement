from uuid import uuid4

from shapely.geometry import LineString, Polygon

from app.schemas.agent_outputs import GeometryOperation
from app.schemas.geojson import Feature, FeatureCollection
from app.services.geospatial.bounds import GeoBounds


class VectorRedesignService:
    def apply(
        self,
        scene: FeatureCollection,
        operations: list[GeometryOperation],
        bounds: GeoBounds,
    ) -> FeatureCollection:
        features = [feature.model_copy(deep=True) for feature in scene.features]
        by_id = {feature.properties.get("id"): feature for feature in features}

        for operation in operations:
            if operation.operation == "REMOVE" and operation.target_feature_id in by_id:
                target = by_id.pop(operation.target_feature_id)
                features.remove(target)
                continue
            geometry = self._validated_geometry(operation, bounds)
            if geometry is None:
                continue
            if operation.operation in {"MOVE", "REPLACE"} and operation.target_feature_id in by_id:
                target = by_id[operation.target_feature_id]
                target.geometry = geometry
                target.properties["redesignDescription"] = operation.description
                target.properties["sources"] = ["GEMINI_REDESIGN"]
                continue
            feature = Feature(
                geometry=geometry,
                properties={
                    "id": f"redesign_{uuid4().hex[:12]}",
                    "featureType": operation.feature_type,
                    "sources": ["GEMINI_REDESIGN"],
                    "confidence": 0.8,
                    "redesignDescription": operation.description,
                },
            )
            features.append(feature)
            by_id[feature.properties["id"]] = feature

        return FeatureCollection(features=features)

    @staticmethod
    def _validated_geometry(
        operation: GeometryOperation,
        bounds: GeoBounds,
    ) -> dict | None:
        if not operation.geometry_type or len(operation.coordinates) < 2:
            return None
        for coordinate in operation.coordinates:
            if len(coordinate) != 2:
                return None
            longitude, latitude = coordinate
            if not (bounds.west <= longitude <= bounds.east):
                return None
            if not (bounds.south <= latitude <= bounds.north):
                return None

        if operation.geometry_type == "Polygon":
            coordinates = list(operation.coordinates)
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            shape = Polygon(coordinates)
            if not shape.is_valid or shape.area == 0:
                return None
            return {"type": "Polygon", "coordinates": [coordinates]}

        shape = LineString(operation.coordinates)
        if not shape.is_valid or shape.length == 0:
            return None
        return {"type": "LineString", "coordinates": operation.coordinates}

