import os
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from routing_provider import default_provider, TomTomRoutingProvider, get_daily_usage, validate_coordinates

logger = logging.getLogger("fastapi_routing")

app = FastAPI(
    title="Aarogya TomTom Routing Service",
    description="Traffic-aware routing service using TomTom Routing API with live traffic analysis.",
    version="1.0.0"
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://book-your-amb.vercel.app",
        "https://project-frontend-mauve-chi.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RouteRequest(BaseModel):
    origin_lat: float = Field(..., description="Origin latitude (-90 to 90)")
    origin_lng: float = Field(..., description="Origin longitude (-180 to 180)")
    dest_lat: float = Field(..., description="Destination latitude (-90 to 90)")
    dest_lng: float = Field(..., description="Destination longitude (-180 to 180)")
    travel_mode: Optional[str] = Field("car", description="Travel mode (default: car for ambulance dispatch)")
    max_alternatives: Optional[int] = Field(1, description="Max alternative routes (0-2)")

    @field_validator("origin_lat", "dest_lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude {v} must be between -90 and 90.")
        return v

    @field_validator("origin_lng", "dest_lng")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude {v} must be between -180 and 180.")
        return v


@app.get("/api/route/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "provider": "TomTom Orbis Routing",
        "version": "1.0.0"
    }


@app.get("/api/route/stats")
def route_stats() -> Dict[str, Any]:
    """Returns current daily requests tracking against TomTom 2,500 free tier limit."""
    return get_daily_usage()


@app.post("/api/route")
def calculate_route(payload: RouteRequest) -> Dict[str, Any]:
    """
    POST /api/route:
    Input: origin and destination lat/lng.
    Output: Normalized traffic-aware routing JSON with ETA, free-flow vs historic vs live scenarios,
    traffic sections, turn-by-turn steps, and GeoJSON LineString geometry.
    """
    try:
        route_data = default_provider.calculate_route(
            origin_lat=payload.origin_lat,
            origin_lng=payload.origin_lng,
            dest_lat=payload.dest_lat,
            dest_lng=payload.dest_lng,
            travel_mode=payload.travel_mode or "car",
            max_alternatives=payload.max_alternatives if payload.max_alternatives is not None else 1,
        )
        return route_data
    except ValueError as e:
        msg = str(e)
        if "429" in msg or "Quota" in msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg)
        elif "Authentication" in msg or "401" in msg or "403" in msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to calculate route: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/route")
def calculate_route_get(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lng: float = Query(..., description="Origin longitude"),
    dest_lat: float = Query(..., description="Destination latitude"),
    dest_lng: float = Query(..., description="Destination longitude"),
    travel_mode: Optional[str] = Query("car"),
    max_alternatives: Optional[int] = Query(1)
) -> Dict[str, Any]:
    """GET convenience wrapper for browser / test calls."""
    req = RouteRequest(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        travel_mode=travel_mode,
        max_alternatives=max_alternatives
    )
    return calculate_route(req)
