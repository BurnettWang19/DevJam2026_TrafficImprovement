from services import cloud_history


def test_summary_contains_firestore_index_fields():
    result = {
        "session_id": "abc123",
        "input": {"lat": 25.04, "lng": 121.55, "size_m": 140},
        "score": {"score": 62, "severity_counts": {"HIGH": 2, "MEDIUM": 1}},
        "vector_summary": {"osm": {"road_names": ["忠孝東路", "敦化南路"]}},
        "verdict": "improved",
    }

    summary = cloud_history._summary(
        "abc123", result, "analyses/abc123/result.json",
        {"current_image": "analyses/abc123/images/current_image.png"},
    )

    assert summary["location"] == "忠孝東路 × 敦化南路"
    assert summary["score"] == 62
    assert summary["severity"]["high"] == 2
    assert summary["result_object"] == "analyses/abc123/result.json"


def test_record_id_rejects_firestore_paths():
    assert cloud_history._valid_record_id("abc_123-xyz")
    assert not cloud_history._valid_record_id("other/document")
