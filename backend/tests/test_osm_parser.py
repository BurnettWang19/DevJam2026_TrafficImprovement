from app.services.osm.parser import OSMParser


def test_osm_parser_converts_highway_ways_to_normalized_roads() -> None:
    raw_osm = {
        "elements": [
            {"type": "node", "id": 1, "lat": 25.033, "lon": 121.565},
            {"type": "node", "id": 2, "lat": 25.034, "lon": 121.566},
            {
                "type": "way",
                "id": 10,
                "nodes": [1, 2],
                "tags": {"highway": "primary", "name": "Test Road"},
            },
        ]
    }

    roads = OSMParser().parse_roads(raw_osm)

    assert len(roads) == 1
    assert roads[0].id == "osm_way_10"
    assert roads[0].coordinates == [(121.565, 25.033), (121.566, 25.034)]
    assert roads[0].attributes["highway"] == "primary"
