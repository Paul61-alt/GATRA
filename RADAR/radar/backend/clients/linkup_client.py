import asyncio
import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

LINKUP_BASE = "https://api.linkup.so/v1"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 500, 502, 503}


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc.lstrip("www.")


class LinkupClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ["LINKUP_API_KEY"]
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict) -> Any:
        url = f"{LINKUP_BASE}{path}"
        async with httpx.AsyncClient(timeout=360) as client:
            for attempt in range(_MAX_RETRIES):
                r = await client.post(url, headers=self._headers, json=body)
                if r.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("linkup retry=%d status=%d wait=%ds", attempt + 1, r.status_code, wait)
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
        raise RuntimeError("Linkup max retries exceeded")

    async def _get(self, path: str) -> Any:
        url = f"{LINKUP_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def search(
        self,
        query: str,
        depth: str = "standard",
        output_type: str = "sourcedAnswer",
        schema: Optional[dict] = None,
        from_date: Optional[str] = None,
    ) -> dict:
        import json

        body: dict = {"q": query, "depth": depth, "outputType": output_type}
        if schema:
            body["structuredOutputSchema"] = json.dumps(schema)
            body["outputType"] = "structured"
            body["includeSources"] = True
        if from_date:
            body["fromDate"] = from_date
        return await self._post("/search", body)

    async def fetch(self, url: str, render_js: bool = False) -> dict:
        return await self._post("/fetch", {"url": url, "renderJs": render_js})

    async def fetch_with_fallback(self, url: str) -> dict:
        """fetch URL; on CloudflareError/FetchError fall back to text search."""
        try:
            return await self.fetch(url, render_js=True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 503):
                logger.warning("fetch blocked=%s falling back to search", url)
                domain = _extract_domain(url)
                return await self.search(
                    query=f"{domain} pricing plans 2025",
                    depth="standard",
                )
            raise

    async def tasks(self, requests_payload: list[dict]) -> list[dict]:
        """Submit batch tasks, poll until done, return results."""
        created = await self._post("/tasks", requests_payload)
        task_ids = [t["id"] for t in created]
        logger.info("linkup tasks_created=%d", len(task_ids))

        max_wait, interval = 300, 5
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            statuses = [
                (await self._get(f"/tasks/{tid}")) for tid in task_ids
            ]
            if all(s.get("status") in ("completed", "failed") for s in statuses):
                logger.info("linkup tasks_done elapsed=%ds", elapsed)
                return statuses
        raise TimeoutError(f"Linkup tasks not done after {max_wait}s")

    async def research(self, query: str) -> dict:
        """Beta deep research endpoint — always optional, never on critical path."""
        try:
            return await self._post("/research", {"q": query})
        except Exception as e:
            logger.warning("linkup research failed (beta) error=%s", e)
            return {}
