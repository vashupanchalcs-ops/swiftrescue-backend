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
OSRM_ENDPOINTS = [
    "https://router.project-osrm.org/route/v1/driving",
    "https://routing.openstreetmap.de/routed-car/route/v1/driving",
]
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


def format_tomtom_locations(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, waypoints: Optional[List[Tuple[float, float]]] = None) -> str:
    """
    Format coordinates in TomTom URL format: lat,lon[:lat,lon...]:lat,lon.
    Enforces strict coordinate order so latitude and longitude never flip.
    """
    validate_coordinates(origin_lat, origin_lng, "Origin")
    parts = [f"{origin_lat:.6f},{origin_lng:.6f}"]
    if waypoints:
        for i, (w_lat, w_lng) in enumerate(waypoints):
            validate_coordinates(w_lat, w_lng, f"Waypoint {i+1}")
            parts.append(f"{w_lat:.6f},{w_lng:.6f}")
    validate_coordinates(dest_lat, dest_lng, "Destination")
    parts.append(f"{dest_lat:.6f},{dest_lng:.6f}")
    return ":".join(parts)


def get_cache_key(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, travel_mode: str, max_alt: int, waypoints: Optional[List[Tuple[float, float]]] = None) -> str:
    wp_str = ""
    if waypoints:
        wp_str = "_" + "_".join(f"{round(w[0], 4)},{round(w[1], 4)}" for w in waypoints)
    return f"{round(origin_lat, 4)},{round(origin_lng, 4)}{wp_str}->{round(dest_lat, 4)},{round(dest_lng, 4)}|{travel_mode}|{max_alt}"


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


def _calculate_osrm_route(points: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Fetch road route from OSRM public routing API.
    points: [(lat, lng), ...] in traversal order.
    Returns normalized route structure.
    """
    coord_str = ";".join([f"{lng:.6f},{lat:.6f}" for lat, lng in points])
    last_err = None

    for base_url in OSRM_ENDPOINTS:
        url = f"{base_url}/{coord_str}?overview=full&geometries=geojson&steps=true"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Aarogya-Ambulance-System/1.0",
                "Accept": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            routes = data.get("routes", [])
            if not routes:
                continue
            r0 = routes[0]
            steps = []
            for leg in r0.get("legs", []):
                for s in leg.get("steps", []):
                    m = s.get("maneuver", {})
                    loc = m.get("location")
                    steps.append({
                        "instruction": s.get("name") or m.get("type", "Proceed"),
                        "distance_m": round(s.get("distance", 0)),
                        "duration_s": round(s.get("duration", 0)),
                        "turn_type": m.get("modifier") or m.get("type", "straight"),
                        "point": [loc[0], loc[1]] if (loc and len(loc) >= 2) else None,
                    })

            dist_m = round(r0.get("distance", 0))
            dur_s = round(r0.get("duration", 0))

            return {
                "distance_m": dist_m,
                "duration_s": dur_s,
                "arrival_time": datetime.now(timezone.utc).isoformat(),
                "traffic_delay_s": 0,
                "no_traffic_s": dur_s,
                "historic_s": dur_s,
                "live_s": dur_s,
                "traffic_sections": [],
                "steps": steps,
                "geometry": r0.get("geometry", {
                    "type": "LineString",
                    "coordinates": [[p[1], p[0]] for p in points]
                }),
                "alternatives": [],
                "provider": "osrm",
                "cached": False,
            }
        except Exception as e:
            last_err = e
            continue

    if last_err:
        logger.warning("OSRM routing endpoints failed: %s", last_err)
    return _calculate_haversine_fallback(points)


def _calculate_haversine_fallback(points: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Fallback when offline or external routing unavailable:
    Calculates great-circle distance and returns straight/interpolated GeoJSON.
    """
    total_dist = 0.0
    for i in range(len(points) - 1):
        total_dist += _haversine_distance_m(points[i][0], points[i][1], points[i+1][0], points[i+1][1])

    dur_s = max(60, round(total_dist / 7.78))

    coords = [[p[1], p[0]] for p in points]
    steps = [
        {"instruction": f"Proceed to waypoint {i+1}", "distance_m": 0, "duration_s": 0, "turn_type": "straight", "point": coords[i]}
        for i in range(len(points))
    ]

    return {
        "distance_m": round(total_dist),
        "duration_s": dur_s,
        "arrival_time": datetime.now(timezone.utc).isoformat(),
        "traffic_delay_s": 0,
        "no_traffic_s": dur_s,
        "historic_s": dur_s,
        "live_s": dur_s,
        "traffic_sections": [],
        "steps": steps,
        "geometry": {
            "type": "LineString",
            "coordinates": coords
        },
        "alternatives": [],
        "provider": "haversine_fallback",
        "cached": False,
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
        waypoints: Optional[List[Tuple[float, float]]] = None,
        travel_mode: str = "car",
        max_alternatives: int = 1,
        bypass_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculates traffic-aware route between origin and destination.
        Tier 1: TomTom Routing API (if TOMTOM_API_KEY present).
        Tier 2: OSRM (Open Source Routing Machine) road-following route.
        Tier 3: Haversine fallback (offline).
        """
        validate_coordinates(origin_lat, origin_lng, "Origin")
        validate_coordinates(dest_lat, dest_lng, "Destination")
        if waypoints:
            for i, (w_lat, w_lng) in enumerate(waypoints):
                validate_coordinates(w_lat, w_lng, f"Waypoint {i+1}")

        # Zero distance check (same origin and destination without waypoints)
        if not waypoints:
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
                    "provider": "direct",
                    "cached": False
                }

        # Cache check
        _clean_cache()
        cache_key = get_cache_key(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode, max_alternatives, waypoints)
        if not bypass_cache and cache_key in _ROUTE_CACHE:
            ts, cached_data = _ROUTE_CACHE[cache_key]
            if time.time() - ts <= DEFAULT_CACHE_TTL_SECONDS:
                resp = dict(cached_data)
                resp["cached"] = True
                return resp

        # Tier 1: TomTom API if key configured
        if self.api_key:
            try:
                locations_path = format_tomtom_locations(origin_lat, origin_lng, dest_lat, dest_lng, waypoints)
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

                with urllib.request.urlopen(req, timeout=10) as response:
                    body = response.read().decode("utf-8")
                    data = json.loads(body)

                routes = data.get("routes", [])
                if routes:
                    primary_route = routes[0]
                    normalized = normalize_route_object(primary_route)

                    # Process alternative routes
                    alternatives: List[Dict[str, Any]] = []
                    for alt_route in routes[1:]:
                        alternatives.append(normalize_route_object(alt_route))

                    normalized["alternatives"] = alternatives
                    normalized["provider"] = "tomtom"
                    normalized["cached"] = False

                    # Store in cache
                    _ROUTE_CACHE[cache_key] = (time.time(), normalized)
                    return normalized
            except Exception as e:
                logger.warning("TomTom API call failed, falling back to OSRM: %s", e)

        # Tier 2: OSRM road route
        all_points = [(origin_lat, origin_lng)]
        if waypoints:
            all_points.extend(waypoints)
        all_points.append((dest_lat, dest_lng))

        normalized = _calculate_osrm_route(all_points)
        _ROUTE_CACHE[cache_key] = (time.time(), normalized)
        return normalized


# Default singleton instance
default_provider = TomTomRoutingProvider()
