import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT", "radar-hackathon")
_last_call: float = 0.0


async def geocode(city: str, country: str) -> Optional[tuple[float, float]]:
    """Return (lat, lng) for city+country via Nominatim. 1 req/s enforced."""
    global _last_call

    now = asyncio.get_event_loop().time()
    gap = now - _last_call
    if gap < 1.0:
        await asyncio.sleep(1.0 - gap)

    query = f"{city}, {country}"
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
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning("geocode failed query=%s error=%s", query, e)

    return None
