from typing import Any

from app.domain.road import NormalizedRoad
from app.schemas.geojson import Feature, FeatureCollection


class OSMParser:
    def parse_scene(self, raw_osm: dict[str, Any]) -> FeatureCollection:
        elements = raw_osm.get("elements", [])
        nodes = {
            element["id"]: [element["lon"], element["lat"]]
            for element in elements
            if element.get("type") == "node"
            and "lat" in element
            and "lon" in element
            and "id" in element
        }
        features: list[Feature] = []

        for element in elements:
            tags = element.get("tags", {})
            if element.get("type") == "node" and element.get("id") in nodes and tags:
                feature_type = self._node_feature_type(tags)
                if feature_type:
                    features.append(
                        Feature(
                            geometry={"type": "Point", "coordinates": nodes[element["id"]]},
                            properties=self._properties(element, tags, feature_type),
                        )
                    )
                continue

            if element.get("type") != "way" or "highway" not in tags:
                continue
            coordinates = [nodes[node_id] for node_id in element.get("nodes", []) if node_id in nodes]
            if len(coordinates) < 2:
                continue
            feature_type = self._way_feature_type(tags)
            features.append(
                Feature(
                    geometry={"type": "LineString", "coordinates": coordinates},
                    properties=self._properties(element, tags, feature_type),
                )
            )
        return FeatureCollection(features=features)

    @staticmethod
    def _properties(element: dict[str, Any], tags: dict[str, Any], feature_type: str) -> dict:
        return {
            "id": f"osm_{element['type']}_{element['id']}",
            "osmId": element["id"],
            "featureType": feature_type,
            "sources": ["OSM"],
            "confidence": 1.0,
            "tags": tags,
            "name": tags.get("name"),
            "highway": tags.get("highway"),
            "lanes": tags.get("lanes"),
            "oneway": tags.get("oneway"),
            "sidewalk": tags.get("sidewalk"),
            "crossing": tags.get("crossing"),
            "cycleway": tags.get("cycleway"),
        }

    @staticmethod
    def _way_feature_type(tags: dict[str, Any]) -> str:
        highway = tags.get("highway")
        footway = tags.get("footway")
        if footway == "crossing" or highway == "crossing":
            return "crosswalk"
        if footway == "sidewalk" or highway in {"footway", "pedestrian", "path", "steps"}:
            return "sidewalk"
        if highway == "cycleway" or tags.get("cycleway"):
            return "cycleway"
        return "road"

    @staticmethod
    def _node_feature_type(tags: dict[str, Any]) -> str | None:
        highway = tags.get("highway")
        if highway == "crossing":
            return "crosswalk"
        if highway == "traffic_signals":
            return "traffic_signal"
        if highway in {"stop", "give_way"}:
            return "traffic_control"
        return None

    def parse_roads(self, raw_osm: dict[str, Any]) -> list[NormalizedRoad]:
        elements = raw_osm.get("elements", [])
        nodes = {
            element["id"]: (element["lon"], element["lat"])
            for element in elements
            if element.get("type") == "node"
            and "lat" in element
            and "lon" in element
            and "id" in element
        }

        roads: list[NormalizedRoad] = []
        for element in elements:
            if element.get("type") != "way":
                continue

            tags = element.get("tags", {})
            if "highway" not in tags:
                continue

            coordinates = [
                nodes[node_id] for node_id in element.get("nodes", []) if node_id in nodes
            ]
            if len(coordinates) < 2:
                continue

            roads.append(
                NormalizedRoad(
                    id=f"osm_way_{element['id']}",
                    coordinates=coordinates,
                    attributes={
                        "osmId": element["id"],
                        "name": tags.get("name"),
                        "highway": tags.get("highway"),
                        "lanes": tags.get("lanes"),
                        "oneway": tags.get("oneway"),
                        "surface": tags.get("surface"),
                    },
                )
            )

        return roads
