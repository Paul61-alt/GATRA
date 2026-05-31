import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

LINKUP_BASE = "https://api.linkup.so/v1"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 500, 502, 503}

# Cost model per Linkup official pricing (2026-05 docs).
# /research: $1.50 FLAT regardless of depth (S/M/L/XL) — depth-tiered table was wrong.
# /search standard = €0.006, /search deep or with structured output = €0.055.
# /fetch = €0.001-0.005.
RESEARCH_COST_EUR: float = 1.50
SEARCH_COST_EUR: dict[str, float] = {"standard": 0.006, "deep": 0.055, "structured": 0.055}
FETCH_COST_EUR = 0.005
# Env-overridable so a scan can be sandboxed below the default cap.
DAILY_HARD_CAP_EUR = float(os.environ.get("RADAR_DAILY_HARD_CAP_EUR", "8.0"))
DAILY_WARN_CAP_EUR = float(os.environ.get("RADAR_DAILY_WARN_CAP_EUR", "5.0"))


class BudgetExceededError(RuntimeError):
    """Raised when a scan would push cumulative daily Linkup spend above the hard cap."""


_call_count: dict[str, int] = {}
_LEDGER_PATH = Path(__file__).resolve().parents[2] / "cache" / "linkup_usage.jsonl"
_ledger_loaded = False


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc.lstrip("www.")


def _load_ledger() -> None:
    global _ledger_loaded
    if _ledger_loaded:
        return
    _ledger_loaded = True
    if not _LEDGER_PATH.exists():
        return
    try:
        with _LEDGER_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("linkup ledger skip malformed line")
                    continue
                if entry.get("status") != "ok":
                    continue
                date = entry.get("date")
                if not date:
                    continue
                # Exempt polling GETs (/tasks/{id}, /research/{id}) — they don't
                # count against daily call budget. Mirror _check_daily_budget.
                ep = entry.get("endpoint", "")
                if ep.startswith("/tasks/") or ep.startswith("/research/"):
                    continue
                _call_count[date] = _call_count.get(date, 0) + 1
    except OSError as e:
        logger.warning("linkup ledger read failed error=%s", e)


def _record_call(endpoint: str, status: str, cost_eur: float = 0.0) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "date": datetime.now(timezone.utc).date().isoformat(),
        "endpoint": endpoint,
        "status": status,
        "cost_eur": cost_eur,
    }
    try:
        _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        logger.warning("linkup ledger write failed error=%s", e)

    # Dual-write to Supabase (best effort — jsonl above stays source of truth)
    try:
        from utils.cache import _sb
        sb = _sb()
        if sb is not None:
            sb.table("radar_usage_events").insert({
                "ts": entry["ts"],
                "endpoint": entry["endpoint"],
                "status": entry["status"],
                "cost_eur": entry["cost_eur"],
            }).execute()
    except Exception as e:
        logger.warning("supabase usage_events insert failed: %s", e)


def estimate_today_cost_eur() -> float:
    """Sum cost_eur field from today's ledger entries (ok status only)."""
    today = datetime.now(timezone.utc).date().isoformat()
    if not _LEDGER_PATH.exists():
        return 0.0
    total = 0.0
    try:
        with _LEDGER_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("date") != today:
                    continue
                if entry.get("status") != "ok":
                    continue
                try:
                    total += float(entry.get("cost_eur", 0) or 0)
                except (TypeError, ValueError):
                    continue
    except OSError as e:
        logger.warning("linkup ledger read failed error=%s", e)
    return total


def _kill_switch_check() -> None:
    if os.environ.get("RADAR_KILL_SWITCH", "").lower() in ("1", "true", "on"):
        raise RuntimeError(
            "Linkup calls disabled by RADAR_KILL_SWITCH. "
            "Unset in .env after reviewing usage to re-enable."
        )


def _check_daily_budget(endpoint: str) -> None:
    _kill_switch_check()
    # Status-poll GETs (/tasks/{id}, /research/{id}) don't bill LinkUp — exempt from budget.
    if endpoint.startswith("/tasks/") or endpoint.startswith("/research/"):
        return
    _load_ledger()
    budget = int(os.environ.get("RADAR_DAILY_BUDGET", "50"))
    today = datetime.now(timezone.utc).date().isoformat()
    used = _call_count.get(today, 0)
    if used >= budget:
        _record_call(endpoint, "budget_exceeded")
        raise BudgetExceededError(
            f"Linkup daily budget exceeded: {used}/{budget} calls on {today}"
        )
    _call_count[today] = used + 1
    if used and used % 10 == 0:
        logger.warning("linkup daily_usage=%d/%d date=%s", used, budget, today)


def get_usage_today() -> dict:
    _load_ledger()
    today = datetime.now(timezone.utc).date().isoformat()
    budget = int(os.environ.get("RADAR_DAILY_BUDGET", "50"))
    return {"date": today, "used": _call_count.get(today, 0), "budget": budget}


def record_scan_delta(
    scan_id: str,
    phase: str,
    balance_before_usd: float | None,
    balance_after_usd: float | None,
    duration_s: float,
) -> None:
    """Append scan-level USD delta to ledger + Supabase (mirror of _record_call).

    Cost computed from balance delta = ground truth from Linkup billing API,
    in contrast to the per-call cost_eur estimates recorded by _record_call.
    """
    cost_usd: float | None = None
    if balance_before_usd is not None and balance_after_usd is not None:
        cost_usd = max(0.0, balance_before_usd - balance_after_usd)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "date": datetime.now(timezone.utc).date().isoformat(),
        "endpoint": "scan_delta",
        "status": "ok" if cost_usd is not None else "missing_balance",
        "scan_id": scan_id,
        "phase": phase,
        "balance_before_usd": balance_before_usd,
        "balance_after_usd": balance_after_usd,
        "cost_usd": cost_usd,
        "duration_s": duration_s,
    }
    try:
        _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        logger.warning("linkup ledger scan_delta write failed error=%s", e)

    try:
        from utils.cache import _sb
        sb = _sb()
        if sb is not None:
            # TODO: requires migration on radar_usage_events to add columns:
            #   scan_id text, phase text, balance_before_usd numeric,
            #   balance_after_usd numeric, cost_usd numeric, duration_s numeric.
            # Until applied, this insert silently fails — JSONL ledger above is source of truth.
            sb.table("radar_usage_events").insert({
                "ts": entry["ts"],
                "endpoint": entry["endpoint"],
                "status": entry["status"],
                "scan_id": scan_id,
                "phase": phase,
                "balance_before_usd": balance_before_usd,
                "balance_after_usd": balance_after_usd,
                "cost_usd": cost_usd,
                "duration_s": duration_s,
            }).execute()
    except Exception as e:
        logger.warning("supabase scan_delta insert failed: %s", e)


class LinkupClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        # BYOK ("bring your own key"): when a caller passes an explicit api_key
        # (a tester's own LinkUp key), this client must NOT count against our
        # daily caps nor write to our usage ledger — their spend is on their
        # account. Falls back to our env key for our own scans (byok=False).
        self.byok = api_key is not None
        self._api_key = api_key or os.environ["LINKUP_API_KEY"]
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict, cost_eur: float = 0.0) -> Any:
        # BYOK: kill-switch still applies (our emergency brake) but neither our
        # daily budget nor our ledger track a tester's own-key spend.
        if self.byok:
            _kill_switch_check()
        else:
            _check_daily_budget(path)
        url = f"{LINKUP_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=360) as client:
                for attempt in range(_MAX_RETRIES):
                    r = await client.post(url, headers=self._headers, json=body)
                    if r.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning("linkup retry=%d status=%d wait=%ds", attempt + 1, r.status_code, wait)
                        await asyncio.sleep(wait)
                        continue
                    r.raise_for_status()
                    if not self.byok:
                        _record_call(path, "ok", cost_eur=cost_eur)
                    return r.json()
        except Exception:
            if not self.byok:
                _record_call(path, "error")
            raise
        if not self.byok:
            _record_call(path, "error")
        raise RuntimeError("Linkup max retries exceeded")

    async def _get(self, path: str) -> Any:
        if self.byok:
            _kill_switch_check()
        else:
            _check_daily_budget(path)
        url = f"{LINKUP_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for attempt in range(_MAX_RETRIES):
                    r = await client.get(url, headers=self._headers)
                    if r.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning("linkup GET retry=%d status=%d wait=%ds", attempt + 1, r.status_code, wait)
                        await asyncio.sleep(wait)
                        continue
                    r.raise_for_status()
                    if not self.byok:
                        _record_call(path, "ok")
                    return r.json()
        except Exception:
            if not self.byok:
                _record_call(path, "error")
            raise
        if not self.byok:
            _record_call(path, "error")
        raise RuntimeError("Linkup GET max retries exceeded")

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

        # Cost: structured output billed as "deep" tier (€0.055) per Linkup pricing.
        if schema:
            cost = SEARCH_COST_EUR["structured"]
        elif depth == "deep":
            cost = SEARCH_COST_EUR["deep"]
        else:
            cost = SEARCH_COST_EUR["standard"]
        return await self._post("/search", body, cost_eur=cost)

    async def fetch(self, url: str, render_js: bool = False) -> dict:
        return await self._post("/fetch", {"url": url, "renderJs": render_js}, cost_eur=FETCH_COST_EUR)

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
        """Submit batch tasks, poll until done, return results.

        Each task in batch billed individually; approximate as one /research per task.
        """
        per_task_cost = RESEARCH_COST_EUR
        total_cost = per_task_cost * len(requests_payload)
        created = await self._post("/tasks", requests_payload, cost_eur=total_cost)
        task_ids = [t["id"] for t in created]
        logger.info("linkup tasks_created=%d", len(task_ids))

        # Exponential backoff per Linkup recommendation: start 2s, double up to 10s.
        max_wait, interval, max_interval = 600, 2, 10
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
            interval = min(interval * 2, max_interval)
        raise TimeoutError(f"Linkup tasks not done after {max_wait}s")

    async def research(
        self,
        query: str,
        depth: Literal["S", "M", "L", "XL"] = "S",
        structured_schema: Optional[dict] = None,
    ) -> dict:
        """Submit a /research job. Returns submission dict (typically {id, status:'pending'}).

        Billable: cost depends on depth tier (RESEARCH_COST_EUR).
        """
        body: dict = {
            "q": query,
            "mode": "investigate",
            "depth": depth,
            "outputType": "sourcedAnswer",
        }
        if structured_schema:
            body["outputType"] = "structured"
            body["structuredOutputSchema"] = json.dumps(structured_schema)
        cost = RESEARCH_COST_EUR
        return await self._post("/research", body, cost_eur=cost)

    async def wait_for_research(
        self,
        job_id: str,
        max_wait: int = 600,
        initial_interval: int = 2,
        max_interval: int = 10,
        on_poll=None,
    ) -> dict:
        """Poll /research/{id} until status in {completed, failed} or max_wait elapsed.

        Polling GETs are budget-exempt (see _check_daily_budget).
        Optional on_poll(dict) async callback fires each iteration (for SSE progress).

        Exponential backoff per Linkup recommendation: start 2s, double up to 10s.
        Keeps tail-latency low on fast jobs without spamming long ones.
        """
        elapsed = 0
        interval = initial_interval
        while elapsed < max_wait:
            result = await self._get(f"/research/{job_id}")
            status = result.get("status")
            if status in {"completed", "failed"}:
                return result
            if on_poll is not None:
                try:
                    await on_poll({"elapsed": elapsed, "status": status, "job_id": job_id})
                except Exception as e:
                    logger.warning("on_poll callback failed error=%s", e)
            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * 2, max_interval)
        raise TimeoutError(f"research job {job_id} not done after {max_wait}s")

    async def balance(self) -> float | None:
        """GET /v1/credits/balance → current USD credit balance, or None on error.

        Direct httpx call: bypasses budget tracking + ledger (this is account
        metadata, not a billable Linkup call).
        """
        url = f"{LINKUP_BASE}/credits/balance"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url, headers=self._headers)
                r.raise_for_status()
                data = r.json()
                balance = data.get("balance")
                if balance is None:
                    logger.warning("linkup balance unexpected response shape=%s", data)
                    return None
                return float(balance)
        except Exception as e:
            logger.warning("linkup balance fetch failed error=%s", e)
            return None

    async def research_and_wait(
        self,
        query: str,
        depth: Literal["S", "M", "L", "XL"] = "S",
        structured_schema: Optional[dict] = None,
        max_wait: int = 600,
        initial_interval: int = 2,
        max_interval: int = 10,
        on_poll=None,
    ) -> dict:
        """Submit + poll. Raises if the job fails or times out."""
        submitted = await self.research(query, depth=depth, structured_schema=structured_schema)
        job_id = submitted.get("id")
        if not job_id:
            raise RuntimeError(f"research submit returned no id: {submitted}")
        result = await self.wait_for_research(
            job_id,
            max_wait=max_wait,
            initial_interval=initial_interval,
            max_interval=max_interval,
            on_poll=on_poll,
        )
        if result.get("status") == "failed":
            raise RuntimeError(f"research job {job_id} failed: {result.get('error')}")
        return result

