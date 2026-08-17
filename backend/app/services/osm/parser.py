from typing import Any

from app.domain.road import NormalizedRoad


class OSMParser:
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
