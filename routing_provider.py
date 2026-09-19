import os
import time
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

logger = logging.getLogger("routing_provider")

TOMTOM_ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
DEFAULT_CACHE_TTL_SECONDS = 45  # 30-60 sec cache as specified
MAX_DAILY_REQUESTS_WARN = 2400   # 2,500 free tier limit

# In-memory cache: key -> (timestamp, response_data)
_ROUTE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# Daily request counter
_USAGE_TRACKER = {
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "count": 0
}


def get_daily_usage() -> Dict[str, Any]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _USAGE_TRACKER["date"] != today:
        _USAGE_TRACKER["date"] = today
        _USAGE_TRACKER["count"] = 0
    return {
        "date": _USAGE_TRACKER["date"],
        "count": _USAGE_TRACKER["count"],
        "limit": 2500,
        "remaining": max(0, 2500 - _USAGE_TRACKER["count"])
    }


def _record_request_count() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _USAGE_TRACKER["date"] != today:
        _USAGE_TRACKER["date"] = today
        _USAGE_TRACKER["count"] = 0
    _USAGE_TRACKER["count"] += 1
    if _USAGE_TRACKER["count"] >= MAX_DAILY_REQUESTS_WARN:
        logger.warning(
            "CRITICAL: TomTom daily requests count is %d / 2500",
            _USAGE_TRACKER["count"]
        )


def validate_coordinates(lat: float, lng: float, name: str = "Coordinate") -> None:
    """Validate latitude and longitude ranges."""
    try:
        f_lat = float(lat)
        f_lng = float(lng)
    except (TypeError, ValueError):
        raise ValueError(f"{name} lat/lng must be numeric floats.")

    if not (-90.0 <= f_lat <= 90.0):
        raise ValueError(f"{name} latitude {f_lat} is out of valid range [-90, 90].")
    if not (-180.0 <= f_lng <= 180.0):
        raise ValueError(f"{name} longitude {f_lng} is out of valid range [-180, 180].")


def format_tomtom_locations(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> str:
    """
    Format coordinates in TomTom URL format: lat,lon:lat,lon.
    Enforces strict coordinate order so latitude and longitude never flip.
    """
    validate_coordinates(origin_lat, origin_lng, "Origin")
    validate_coordinates(dest_lat, dest_lng, "Destination")
    return f"{origin_lat:.6f},{origin_lng:.6f}:{dest_lat:.6f},{dest_lng:.6f}"


def get_cache_key(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, travel_mode: str, max_alt: int) -> str:
    # Round to 4 decimal places (~11 meters) to eliminate redundant calls for micro-deviations
    return f"{round(origin_lat, 4)},{round(origin_lng, 4)}->{round(dest_lat, 4)},{round(dest_lng, 4)}|{travel_mode}|{max_alt}"


def _clean_cache() -> None:
    now = time.time()
    expired = [k for k, (ts, _) in _ROUTE_CACHE.items() if now - ts > DEFAULT_CACHE_TTL_SECONDS * 2]
    for k in expired:
        _ROUTE_CACHE.pop(k, None)


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371000.0  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def normalize_route_object(route: Dict[str, Any]) -> Dict[str, Any]:
    summary = route.get("summary", {})
    legs = route.get("legs", [])
    sections = route.get("sections", [])
    guidance = route.get("guidance", {})

    distance_m = summary.get("lengthInMeters", 0)
    duration_s = summary.get("travelTimeInSeconds", 0)
    arrival_time = summary.get("arrivalTime")
    traffic_delay_s = summary.get("trafficDelayInSeconds", 0)

    # Traffic scenarios from computeTravelTimeFor=all
    no_traffic_s = summary.get("noTrafficTravelTimeInSeconds", duration_s)
    historic_s = summary.get("historicTrafficTravelTimeInSeconds", duration_s)
    live_s = summary.get("liveTrafficIncidentsTravelTimeInSeconds", duration_s)

    # Traffic sections: categorize segments (JAM, ROAD_WORK, CLOSURE, etc.)
    traffic_sections: List[Dict[str, Any]] = []
    for s in sections:
        traffic_sections.append({
            "start_index": s.get("startPointIndex", 0),
            "end_index": s.get("endPointIndex", 0),
            "section_type": s.get("sectionType", "traffic"),
            "category": s.get("simpleCategory", "JAM"),
            "delay_s": s.get("delayInSeconds", 0),
            "magnitude": s.get("magnitudeOfDelay", "UNKNOWN"),
        })

    # Turn-by-turn guidance steps
    raw_instructions = guidance.get("instructions", [])
    steps: List[Dict[str, Any]] = []
    for inst in raw_instructions:
        pt = inst.get("point", {})
        steps.append({
            "instruction": inst.get("message", ""),
            "distance_m": inst.get("routeOffsetInMeters", 0),
            "duration_s": inst.get("travelTimeInSeconds", 0),
            "turn_type": inst.get("maneuver", "") or inst.get("turnAngle", ""),
            "point": [pt.get("longitude", 0.0), pt.get("latitude", 0.0)] if pt else None,
        })

    # GeoJSON LineString coordinates: [[lng, lat], ...]
    points: List[List[float]] = []
    for leg in legs:
        for p in leg.get("points", []):
            points.append([p.get("longitude"), p.get("latitude")])

    geometry = {
        "type": "LineString",
        "coordinates": points
    }

    return {
        "distance_m": distance_m,
        "duration_s": duration_s,
        "arrival_time": arrival_time,
        "traffic_delay_s": traffic_delay_s,
        "no_traffic_s": no_traffic_s,
        "historic_s": historic_s,
        "live_s": live_s,
        "traffic_sections": traffic_sections,
        "steps": steps,
        "geometry": geometry,
    }


class TomTomRoutingProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("TOMTOM_API_KEY", "").strip()

    def calculate_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "car",
        max_alternatives: int = 1,
        bypass_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculates traffic-aware route between origin and destination using TomTom Routing API.
        Returns normalized JSON suitable for MapLibre and ETA dashboard.
        """
        validate_coordinates(origin_lat, origin_lng, "Origin")
        validate_coordinates(dest_lat, dest_lng, "Destination")

        # Zero distance check (same origin and destination)
        dist_direct = _haversine_distance_m(origin_lat, origin_lng, dest_lat, dest_lng)
        if dist_direct < 10.0:  # within 10 meters
            return {
                "distance_m": 0,
                "duration_s": 0,
                "arrival_time": datetime.now(timezone.utc).isoformat(),
                "traffic_delay_s": 0,
                "no_traffic_s": 0,
                "historic_s": 0,
                "live_s": 0,
                "traffic_sections": [],
                "steps": [],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[origin_lng, origin_lat], [dest_lng, dest_lat]]
                },
                "alternatives": [],
                "cached": False
            }

        # Cache check
        _clean_cache()
        cache_key = get_cache_key(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode, max_alternatives)
        if not bypass_cache and cache_key in _ROUTE_CACHE:
            ts, cached_data = _ROUTE_CACHE[cache_key]
            if time.time() - ts <= DEFAULT_CACHE_TTL_SECONDS:
                resp = dict(cached_data)
                resp["cached"] = True
                return resp

        if not self.api_key:
            # Fallback if key is missing
            raise ValueError(
                "TOMTOM_API_KEY is not configured in backend environment. "
                "Please add TOMTOM_API_KEY to .env."
            )

        locations_path = format_tomtom_locations(origin_lat, origin_lng, dest_lat, dest_lng)
        query_params = {
            "key": self.api_key,
            "traffic": "true",
            "computeTravelTimeFor": "all",
            "sectionType": "traffic",
            "instructionsType": "text",
            "routeType": "fastest",
            "travelMode": travel_mode,
            "maxAlternatives": str(max(0, min(2, max_alternatives))),
            "report": "effectiveSettings",
        }

        encoded_query = urllib.parse.urlencode(query_params)
        request_url = TOMTOM_ROUTING_URL.format(locations=locations_path) + "?" + encoded_query

        _record_request_count()
        req = urllib.request.Request(
            request_url,
            headers={
                "User-Agent": "Aarogya-Ambulance-System/1.0",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            if e.code == 400:
                raise ValueError("TomTom Error (400): Invalid coordinates or origin/destination point is too far from a drivable road.")
            elif e.code in (401, 403):
                raise ValueError(f"TomTom Authentication Error ({e.code}): Invalid or unauthorized TOMTOM_API_KEY.")
            elif e.code == 429:
                raise ValueError("TomTom Quota Exceeded (429): Daily rate limit (2,500 calls) or second limit exceeded.")
            else:
                raise RuntimeError(f"TomTom API Error ({e.code}): {err_body or e.reason}")
        except urllib.error.URLError as e:
            raise TimeoutError(f"Network error connecting to TomTom Routing API: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during route calculation: {str(e)}")

        routes = data.get("routes", [])
        if not routes:
            raise ValueError("No route found by TomTom for the specified locations.")

        primary_route = routes[0]
        normalized = normalize_route_object(primary_route)

        # Process alternative routes
        alternatives: List[Dict[str, Any]] = []
        for alt_route in routes[1:]:
            alternatives.append(normalize_route_object(alt_route))

        normalized["alternatives"] = alternatives
        normalized["cached"] = False

        # Store in cache
        _ROUTE_CACHE[cache_key] = (time.time(), normalized)
        return normalized


# Default singleton instance
default_provider = TomTomRoutingProvider()
