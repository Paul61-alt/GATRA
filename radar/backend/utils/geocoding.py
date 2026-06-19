import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# OSM Nominatim's usage policy explicitly rejects generic/stock User-Agents
# (a bare "radar-hackathon" gets HTTP 403 "Access blocked"). Identify the app
# and let deploys override with a contact address via NOMINATIM_USER_AGENT.
_USER_AGENT = os.environ.get(
    "NOMINATIM_USER_AGENT",
    "RADAR-competitive-intel/1.0 (+https://github.com/Paul61-alt)",
)
_last_call: float = 0.0

# In-process cache: city+country -> coords-or-None (negative results cached too,
# so a miss is not re-queried within a run).
_cache: dict[str, Optional[tuple[float, float]]] = {}

# Static fast-path for common tech hubs. Hits skip the network entirely — zero
# latency, no rate limit, no 403. Nominatim stays the fallback for everything
# else. Keyed by lowercased city name.
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "san francisco": (37.7749, -122.4194),
    "new york": (40.7128, -74.0060),
    "new york city": (40.7128, -74.0060),
    "san diego": (32.7157, -117.1611),
    "los angeles": (34.0522, -118.2437),
    "seattle": (47.6062, -122.3321),
    "austin": (30.2672, -97.7431),
    "boston": (42.3601, -71.0589),
    "chicago": (41.8781, -87.6298),
    "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207),
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),
    "munich": (48.1351, 11.5820),
    "amsterdam": (52.3676, 4.9041),
    "dublin": (53.3498, -6.2603),
    "barcelona": (41.3851, 2.1734),
    "madrid": (40.4168, -3.7038),
    "stockholm": (59.3293, 18.0686),
    "zurich": (47.3769, 8.5417),
    "tel aviv": (32.0853, 34.7818),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),
    "tokyo": (35.6762, 139.6503),
    "prague": (50.0755, 14.4378),
}


async def geocode(city: str, country: str) -> Optional[tuple[float, float]]:
    """Return (lat, lng) for city+country. Tries an in-process cache, then a
    static city table, then Nominatim (1 req/s). Returns None on miss/failure."""
    global _last_call

    city = (city or "").strip()
    country = (country or "").strip()
    if not city and not country:
        return None

    key = f"{city.lower()}, {country.lower()}"
    if key in _cache:
        return _cache[key]

    # Static fast-path — no network.
    static = _CITY_COORDS.get(city.lower())
    if static is not None:
        _cache[key] = static
        return static

    now = asyncio.get_event_loop().time()
    gap = now - _last_call
    if gap < 1.0:
        await asyncio.sleep(1.0 - gap)

    query = f"{city}, {country}"
    coords: Optional[tuple[float, float]] = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                _NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
            )
            r.raise_for_status()
            results = r.json()
            _last_call = asyncio.get_event_loop().time()
            if results:
                coords = float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning("geocode failed query=%s error=%s", query, e)

    _cache[key] = coords
    return coords
