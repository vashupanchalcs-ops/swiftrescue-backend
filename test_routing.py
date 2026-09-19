import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from routing_provider import (
    TomTomRoutingProvider,
    validate_coordinates,
    format_tomtom_locations,
    get_cache_key,
    normalize_route_object,
)
from fastapi_app import app

# Sample realistic TomTom calculateRoute response
SAMPLE_TOMTOM_RESPONSE = {
    "formatVersion": "0.0.12",
    "routes": [
        {
            "summary": {
                "lengthInMeters": 15420,
                "travelTimeInSeconds": 1420,
                "trafficDelayInSeconds": 240,
                "trafficLengthInMeters": 2100,
                "departureTime": "2026-09-19T14:30:00Z",
                "arrivalTime": "2026-09-19T14:53:40Z",
                "noTrafficTravelTimeInSeconds": 1180,
                "historicTrafficTravelTimeInSeconds": 1250,
                "liveTrafficIncidentsTravelTimeInSeconds": 1420
            },
            "legs": [
                {
                    "summary": {
                        "lengthInMeters": 15420,
                        "travelTimeInSeconds": 1420
                    },
                    "points": [
                        {"latitude": 28.73777, "longitude": 77.30561},
                        {"latitude": 28.73850, "longitude": 77.30600},
                        {"latitude": 28.72000, "longitude": 77.32000},
                        {"latitude": 28.66920, "longitude": 77.45380}
                    ]
                }
            ],
            "sections": [
                {
                    "startPointIndex": 1,
                    "endPointIndex": 2,
                    "sectionType": "traffic",
                    "simpleCategory": "JAM",
                    "delayInSeconds": 240,
                    "magnitudeOfDelay": "MAJOR"
                }
            ],
            "guidance": {
                "instructions": [
                    {
                        "routeOffsetInMeters": 0,
                        "travelTimeInSeconds": 0,
                        "point": {"latitude": 28.73777, "longitude": 77.30561},
                        "instructionType": "START",
                        "street": "Main Road",
                        "message": "Head northeast on Main Road"
                    },
                    {
                        "routeOffsetInMeters": 250,
                        "travelTimeInSeconds": 45,
                        "point": {"latitude": 28.73850, "longitude": 77.30600},
                        "instructionType": "TURN",
                        "maneuver": "TURN_RIGHT",
                        "message": "Turn right onto Grand Trunk Rd"
                    },
                    {
                        "routeOffsetInMeters": 15420,
                        "travelTimeInSeconds": 1420,
                        "point": {"latitude": 28.66920, "longitude": 77.45380},
                        "instructionType": "FINISH",
                        "message": "Arrive at Hospital on your left"
                    }
                ]
            }
        }
    ]
}


class MockHTTPResponse:
    def __init__(self, data_dict, status=200):
        self._body = json.dumps(data_dict).encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_validate_coordinates():
    # Valid
    validate_coordinates(28.7377, 77.3056)
    validate_coordinates(-90.0, 180.0)

    # Invalid latitude
    with pytest.raises(ValueError, match="latitude"):
        validate_coordinates(95.0, 77.3056)

    # Invalid longitude
    with pytest.raises(ValueError, match="longitude"):
        validate_coordinates(28.7377, 185.0)


def test_format_tomtom_locations():
    loc = format_tomtom_locations(28.73777, 77.30561, 28.6692, 77.4538)
    # Must follow lat,lon:lat,lon
    assert loc == "28.737770,77.305610:28.669200,77.453800"


def test_normalize_route_object():
    norm = normalize_route_object(SAMPLE_TOMTOM_RESPONSE["routes"][0])

    # Check metrics
    assert norm["distance_m"] == 15420
    assert norm["duration_s"] == 1420
    assert norm["traffic_delay_s"] == 240
    assert norm["no_traffic_s"] == 1180
    assert norm["historic_s"] == 1250
    assert norm["live_s"] == 1420

    # Check traffic sections
    assert len(norm["traffic_sections"]) == 1
    assert norm["traffic_sections"][0]["category"] == "JAM"
    assert norm["traffic_sections"][0]["delay_s"] == 240

    # Check turn-by-turn steps
    assert len(norm["steps"]) == 3
    assert norm["steps"][1]["turn_type"] == "TURN_RIGHT"
    assert "Grand Trunk Rd" in norm["steps"][1]["instruction"]

    # Check GeoJSON LineString coordinates [lng, lat]
    geom = norm["geometry"]
    assert geom["type"] == "LineString"
    assert len(geom["coordinates"]) == 4
    # Ensure [lng, lat] order
    assert geom["coordinates"][0] == [77.30561, 28.73777]
    assert geom["coordinates"][-1] == [77.4538, 28.6692]


@patch("urllib.request.urlopen")
def test_provider_calculate_route(mock_urlopen):
    mock_urlopen.return_value = MockHTTPResponse(SAMPLE_TOMTOM_RESPONSE)

    provider = TomTomRoutingProvider(api_key="test_tomtom_key_123")
    result = provider.calculate_route(
        origin_lat=28.73777,
        origin_lng=77.30561,
        dest_lat=28.6692,
        dest_lng=77.4538,
        bypass_cache=True
    )

    assert result["distance_m"] == 15420
    assert result["duration_s"] == 1420
    assert result["traffic_delay_s"] == 240
    assert result["cached"] is False
    assert mock_urlopen.called


@patch("urllib.request.urlopen")
def test_provider_cache(mock_urlopen):
    mock_urlopen.return_value = MockHTTPResponse(SAMPLE_TOMTOM_RESPONSE)

    provider = TomTomRoutingProvider(api_key="test_tomtom_key_123")
    # First call - populates cache
    res1 = provider.calculate_route(28.73777, 77.30561, 28.6692, 77.4538)
    # Second call - should return cached
    res2 = provider.calculate_route(28.73777, 77.30561, 28.6692, 77.4538)

    assert res2["cached"] is True
    assert res2["distance_m"] == res1["distance_m"]


def test_provider_same_location_zero_distance():
    provider = TomTomRoutingProvider(api_key="test_key")
    result = provider.calculate_route(28.7377, 77.3056, 28.7377, 77.3056)
    assert result["distance_m"] == 0
    assert result["duration_s"] == 0
    assert result["traffic_delay_s"] == 0


@patch("urllib.request.urlopen")
def test_fastapi_post_route_endpoint(mock_urlopen):
    mock_urlopen.return_value = MockHTTPResponse(SAMPLE_TOMTOM_RESPONSE)

    client = TestClient(app)
    response = client.post(
        "/api/route",
        json={
            "origin_lat": 28.73777,
            "origin_lng": 77.30561,
            "dest_lat": 28.6692,
            "dest_lng": 77.4538,
            "travel_mode": "car",
            "max_alternatives": 1
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "distance_m" in data
    assert "duration_s" in data
    assert "traffic_delay_s" in data
    assert "no_traffic_s" in data
    assert "historic_s" in data
    assert "live_s" in data
    assert "traffic_sections" in data
    assert "steps" in data
    assert "geometry" in data
    assert data["geometry"]["type"] == "LineString"


def test_fastapi_health_and_stats():
    client = TestClient(app)
    health = client.get("/api/route/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    stats = client.get("/api/route/stats")
    assert stats.status_code == 200
    assert "count" in stats.json()
    assert stats.json()["limit"] == 2500
