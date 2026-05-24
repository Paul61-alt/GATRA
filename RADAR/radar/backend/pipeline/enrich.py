"""Phase 3 — ENRICH: deep competitor profiling via Linkup /research.

Two modes (RADAR_ENRICH_MODE):
  - "batched" (default): ONE /research call with a structured schema covering
    ALL competitors. Single billing event (€1.50 vs N×€1.50), uniform enrichment
    across the cohort instead of top-K cap + empty stubs.
  - "legacy": N calls capped at MAX_ENRICH, tail returned as stubs.

Override for demo/test: RADAR_MAX_ENRICH=1 caps legacy mode to 1 competitor.
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Literal

from clients.linkup_client import (
    DAILY_HARD_CAP_EUR,
    DAILY_WARN_CAP_EUR,
    RESEARCH_COST_EUR,
    BudgetExceededError,
    LinkupClient,
    estimate_today_cost_eur,
)
from models.company import DataPoint, HQ
from models.competitor import (
    CompetitorProfile,
    LinkedInSignal,
    PricingSignal,
    PricingTier,
    RecentSignal,
)
from utils.dedup import normalize_domain
from utils.geocoding import geocode

logger = logging.getLogger(__name__)

ENRICH_MODE = os.environ.get("RADAR_ENRICH_MODE", "batched").lower()
MAX_ENRICH = int(os.environ.get("RADAR_MAX_ENRICH", "5"))
DEPTH_TOP: Literal["M"] = "M"
DEPTH_REST: Literal["S"] = "S"
DEPTH_BATCH: Literal["M"] = "M"  # Single call, mid-depth covers cohort breadth

COMPETITOR_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "linkedin_url": {"type": "string"},
        "hq_city": {"type": "string"},
        "hq_country": {"type": "string"},
        "founded_year": {"type": "integer"},
        "employee_count": {"type": "integer"},
        "funding_stage": {"type": "string"},
        "funding_total_usd": {"type": "integer"},
        "last_round_amount_usd": {"type": "integer"},
        "last_round_date": {"type": "string"},
        "last_round_type": {"type": "string"},
        "key_investors": {"type": "array", "items": {"type": "string"}},
        "one_liner": {"type": "string"},
        "key_differentiators": {"type": "array", "items": {"type": "string"}},
        "target_segment": {"type": "string"},
        "notable_customers": {"type": "array", "items": {"type": "string"}},
        "pricing": {
            "type": "object",
            "properties": {
                "free_plan": {"type": "boolean"},
                "tiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price_monthly_usd": {"type": "number"},
                            "price_annual_usd": {"type": "number"},
                            "features": {"type": "array", "items": {"type": "string"}},
                            "target": {"type": "string"},
                        },
                    },
                },
                "recent_changes": {"type": "string"},
            },
        },
        "founder_linkedin_urls": {"type": "array", "items": {"type": "string"}},
        "recent_linkedin_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "author": {"type": "string"},
                    "signal": {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
        "recent_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "headline": {"type": "string"},
                    "source_url": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["funding", "product", "hiring", "partnership", "press"],
                    },
                },
            },
        },
        "weaknesses": {"type": "array", "items": {"type": "string"}},
    },
}


def _research_query(name: str, domain: str) -> str:
    return (
        f"You are a competitive intelligence analyst building a deep benchmark profile of {name} ({domain}).\n\n"
        f"Search {domain}, {domain}/pricing, {domain}/plans, Crunchbase, LinkedIn, G2, Capterra, "
        f"TechCrunch, and recent news. Run several searches with adjacent keywords to ensure full breadth.\n\n"
        "Extract the following — include a source URL for each section:\n\n"
        f"PRICING: Visit {domain}/pricing and {domain}/plans. List every plan name, exact monthly USD price, "
        "exact annual USD price, free tier availability (true/false), any recent pricing changes.\n\n"
        f"FUNDING: Search Crunchbase and news for '{name} funding'. Extract: funding stage, latest round amount USD, "
        "round date (YYYY-MM-DD), round type (Seed/Series A/B/C/etc), total raised USD, all investor names.\n\n"
        f"COMPANY: Find the LinkedIn company page URL for {name}. Extract current employee count. "
        "Note any headcount growth signals from LinkedIn or news.\n\n"
        f"FOUNDERS: Find CEO and founder names for {name}. Extract their LinkedIn profile URLs. "
        "Search for recent LinkedIn posts or press statements from founders (last 6 months) — "
        "extract the key signal or quote for each.\n\n"
        f"SIGNALS: Search news and press from the last 6 months about {name}. "
        "For each item extract: date, headline, signal type (funding/product/hiring/partnership/press), source URL.\n\n"
        f"POSITIONING: List key differentiators of {name} vs alternatives. "
        "Identify primary target customer segment. List up to 5 publicly known customer names.\n\n"
        f"WEAKNESSES: Search G2, Capterra, Reddit, Hacker News for user complaints or limitations of {name}. "
        "List the most recurring themes."
    )


def _parse_result(
    raw: dict,
    competitor: dict,
    now: str,
    run_id: str,
    coords,
) -> CompetitorProfile:
    output = raw.get("output", {}) if isinstance(raw, dict) else {}
    # /research structured output wraps payload in "data"; fall back to output itself.
    data = output.get("data") or output or {}
    if not isinstance(data, dict):
        data = {}
    sources = output.get("sources", []) if isinstance(output, dict) else []
    src_url = sources[0].get("url") if sources else None
    # Dedup all source URLs — propagated to CompetitorProfile.source_urls
    _seen: set[str] = set()
    source_urls: list[str] = []
    for s in sources:
        if isinstance(s, dict):
            u = s.get("url")
            if u and u not in _seen:
                _seen.add(u)
                source_urls.append(u)

    # ── Pricing ───────────────────────────────────────────────────
    pricing_raw = data.get("pricing") or {}
    tiers = [
        PricingTier(
            name=t.get("name"),
            price_monthly_usd=t.get("price_monthly_usd"),
            price_annual_usd=t.get("price_annual_usd"),
            features=t.get("features", []),
            target=t.get("target"),
        )
        for t in pricing_raw.get("tiers", [])
    ]
    pricing = (
        PricingSignal(
            tiers=tiers,
            free_plan=pricing_raw.get("free_plan"),
            recent_changes=pricing_raw.get("recent_changes"),
            source_url=src_url,
            extracted_at=now,
        )
        if (tiers or pricing_raw)
        else None
    )

    # ── HQ + geocoding ────────────────────────────────────────────
    city = data.get("hq_city") or competitor.get("hq_city", "")
    country = data.get("hq_country") or competitor.get("hq_country", "")
    hq = None
    if city or country:
        hq = HQ(
            city=city,
            country=country,
            lat=coords[0] if isinstance(coords, tuple) else None,
            lng=coords[1] if isinstance(coords, tuple) else None,
        )

    # ── Structured signals ────────────────────────────────────────
    structured_signals = [
        RecentSignal(
            date=s.get("date"),
            headline=s.get("headline", ""),
            source_url=s.get("source_url"),
            type=s.get("type"),
        )
        for s in data.get("recent_signals", [])
        if s.get("headline")
    ]

    # ── LinkedIn signals ──────────────────────────────────────────
    linkedin_signals = [
        LinkedInSignal(
            date=s.get("date"),
            author=s.get("author"),
            signal=s.get("signal", ""),
            source_url=s.get("source_url"),
        )
        for s in data.get("recent_linkedin_signals", [])
        if s.get("signal")
    ]

    differentiators = data.get("key_differentiators", [])

    return CompetitorProfile(
        name=data.get("name") or competitor.get("name", ""),
        website=data.get("website") or competitor.get("website", ""),
        hq=hq,
        founded_year=data.get("founded_year") or competitor.get("founded_year"),
        funding_stage=DataPoint(
            value=data.get("funding_stage"),
            confidence="high",
            extracted_at=now,
        ) if data.get("funding_stage") else (
            DataPoint(value=competitor.get("funding_stage"), confidence="medium", extracted_at=now)
            if competitor.get("funding_stage") else None
        ),
        funding_total_usd=data.get("funding_total_usd"),
        last_round_amount_usd=data.get("last_round_amount_usd"),
        last_round_date=data.get("last_round_date"),
        last_round_type=data.get("last_round_type"),
        key_investors=data.get("key_investors", []),
        employee_count=DataPoint(
            value=data.get("employee_count") or competitor.get("employee_count"),
            confidence="medium",
            extracted_at=now,
        ) if (data.get("employee_count") or competitor.get("employee_count")) else None,
        one_liner=data.get("one_liner") or competitor.get("one_liner"),
        differentiator=differentiators[0] if differentiators else competitor.get("differentiator"),
        key_differentiators=differentiators,
        target_segment=data.get("target_segment"),
        notable_customers=data.get("notable_customers", []),
        weaknesses=data.get("weaknesses", []),
        pricing=pricing,
        recent_signals=[s.headline for s in structured_signals][:5],  # compat with transform.py
        structured_signals=structured_signals,
        linkedin_url=data.get("linkedin_url"),
        founder_linkedin_urls=data.get("founder_linkedin_urls", []),
        recent_linkedin_signals=linkedin_signals,
        source_urls=source_urls,
        pipeline_run_id=run_id,
    )


def _stub(competitor: dict, run_id: str, now: str) -> CompetitorProfile:
    """Minimal profile from a discover dict — no Linkup call."""
    city = competitor.get("hq_city")
    country = competitor.get("hq_country")
    hq = HQ(city=city, country=country) if (city or country) else None
    funding_stage_val = competitor.get("funding_stage")
    return CompetitorProfile(
        name=competitor.get("name") or competitor.get("website", ""),
        website=competitor.get("website", ""),
        hq=hq,
        founded_year=competitor.get("founded_year"),
        one_liner=competitor.get("one_liner"),
        differentiator=competitor.get("differentiator"),
        funding_stage=(
            DataPoint(value=funding_stage_val, confidence="low", extracted_at=now)
            if funding_stage_val else None
        ),
        pipeline_run_id=run_id,
    )


async def _geocode_all(competitors: list[dict]) -> dict[int, tuple]:
    """Parallel geocoding keyed by competitor index. Returns {} on full failure."""
    async def _noop():
        return None

    coords_list = await asyncio.gather(
        *[
            geocode(c.get("hq_city", ""), c.get("hq_country", ""))
            if (c.get("hq_city") or c.get("hq_country"))
            else _noop()
            for c in competitors
        ],
        return_exceptions=True,
    )
    out: dict[int, tuple] = {}
    for i, coords in enumerate(coords_list):
        if isinstance(coords, tuple):
            out[i] = coords
    return out


async def _enrich_one(
    competitor: dict,
    depth: Literal["S", "M"],
    schema: dict,
    linkup: LinkupClient,
    run_id: str,
    now: str,
    coords,
    event_cb=None,
) -> CompetitorProfile:
    name = competitor.get("name") or competitor.get("website", "")
    query = _research_query(name, competitor.get("website", ""))

    async def _on_poll(state: dict) -> None:
        if event_cb is None:
            return
        await event_cb({
            "phase": "ENRICH",
            "status": "polling",
            "competitor": name,
            "website": competitor.get("website", ""),
            "elapsed": state.get("elapsed", 0),
            "research_status": state.get("status"),
            "job_id": state.get("job_id"),
        })

    result = await linkup.research_and_wait(
        query, depth=depth, structured_schema=schema, on_poll=_on_poll
    )
    return _parse_result(result, competitor, now, run_id, coords)


def _normalize_name_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _batched_query(competitors: list[dict]) -> str:
    listed = "\n".join(
        f"{i+1}. {c.get('name','?')} — {c.get('website','?')}"
        for i, c in enumerate(competitors)
    )
    return (
        f"You are a competitive intelligence analyst. For EACH of the following "
        f"{len(competitors)} companies, build a deep benchmark profile. For EACH company "
        "separately, search their domain, /pricing, /plans, Crunchbase, LinkedIn, G2, "
        "Capterra, TechCrunch, and recent news.\n\n"
        f"Companies (return data for ALL {len(competitors)} of them, preserving the same names):\n"
        f"{listed}\n\n"
        "For EACH company extract:\n"
        "- name (exact match from the list above — CRITICAL for matching)\n"
        "- website, linkedin_url, hq_city, hq_country, founded_year, employee_count\n"
        "- funding_stage, funding_total_usd, last_round_amount_usd, last_round_date, last_round_type, key_investors\n"
        "- one_liner, key_differentiators, target_segment, notable_customers, weaknesses\n"
        "- pricing: free_plan (bool), tiers [{name, price_monthly_usd, price_annual_usd, features, target}], recent_changes\n"
        "- founder_linkedin_urls\n"
        "- recent_signals: array of {date, headline, source_url, type ∈ funding/product/hiring/partnership/press} — last 6 months\n"
        "- recent_linkedin_signals: array of {date, author, signal, source_url} from founders/execs — last 6 months\n\n"
        "Return as 'competitors' array with one object per company. "
        f"You MUST return all {len(competitors)} companies, in the SAME order as listed above. "
        "If you cannot find data for a field, omit it — do not guess."
    )


async def _enrich_batch(
    competitors: list[dict],
    linkup: LinkupClient,
    run_id: str,
    now: str,
    coords_map: dict[int, tuple],
    depth: Literal["S", "M", "L", "XL"] = DEPTH_BATCH,
    event_cb=None,
) -> list[CompetitorProfile]:
    """Single batched /research call covering all competitors.

    Falls back to _stub for any competitor the model failed to return data for.
    """
    batched_schema = {
        "type": "object",
        "properties": {
            "competitors": {
                "type": "array",
                "items": COMPETITOR_SCHEMA,
            }
        },
    }

    query = _batched_query(competitors)

    async def _on_poll(state: dict) -> None:
        if event_cb is None:
            return
        await event_cb({
            "phase": "ENRICH",
            "status": "polling",
            "competitor": f"batch of {len(competitors)}",
            "elapsed": state.get("elapsed", 0),
            "research_status": state.get("status"),
            "job_id": state.get("job_id"),
        })

    raw = await linkup.research_and_wait(
        query, depth=depth, structured_schema=batched_schema, on_poll=_on_poll
    )

    output = raw.get("output", {}) if isinstance(raw, dict) else {}
    data = output.get("data") or output or {}
    if not isinstance(data, dict):
        data = {}
    items = data.get("competitors", []) if isinstance(data, dict) else []
    sources = output.get("sources", []) if isinstance(output, dict) else []

    # Index returned items by normalized name and normalized domain
    by_key: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        kn = _normalize_name_key(item.get("name", ""))
        kw = normalize_domain(item.get("website", ""))
        if kn:
            by_key.setdefault(kn, item)
        if kw:
            by_key.setdefault(kw, item)

    profiles: list[CompetitorProfile] = []
    matched_count = 0
    for i, c in enumerate(competitors):
        kn = _normalize_name_key(c.get("name", ""))
        kw = normalize_domain(c.get("website", ""))
        matched = by_key.get(kn) or by_key.get(kw)
        if matched:
            # Reuse _parse_result by wrapping the matched item as if it were a raw /research payload.
            # Shared sources attach per-competitor — accurate at run level, not per-item.
            fake_raw = {"output": {"data": matched, "sources": sources}}
            profiles.append(_parse_result(fake_raw, c, now, run_id, coords_map.get(i)))
            matched_count += 1
        else:
            profiles.append(_stub(c, run_id, now))

    logger.info(
        "phase=ENRICH mode=batched returned=%d matched=%d stubbed=%d",
        len(items),
        matched_count,
        len(competitors) - matched_count,
    )
    return profiles


async def run(
    competitors: list[dict],
    linkup: LinkupClient,
    run_id: str,
    event_cb=None,
) -> list[CompetitorProfile]:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()

    if not competitors:
        return []

    # ── Batched mode (default) ────────────────────────────────────
    if ENRICH_MODE == "batched":
        logger.info(
            "phase=ENRICH mode=batched status=start total=%d depth=%s",
            len(competitors), DEPTH_BATCH,
        )
        estimated = RESEARCH_COST_EUR.get(DEPTH_BATCH, 1.5)
        cumul = estimate_today_cost_eur()
        if cumul + estimated > DAILY_HARD_CAP_EUR:
            raise BudgetExceededError(
                f"scan would exceed daily cap €{DAILY_HARD_CAP_EUR:.2f} "
                f"(today={cumul:.2f} + scan={estimated:.2f})"
            )
        if cumul + estimated > DAILY_WARN_CAP_EUR:
            logger.warning(
                "daily linkup spend nearing cap: today=%.2f + scan=%.2f", cumul, estimated
            )

        coords_map = await _geocode_all(competitors)
        profiles = await _enrich_batch(
            competitors, linkup, run_id, now, coords_map, depth=DEPTH_BATCH, event_cb=event_cb,
        )

        if event_cb:
            await event_cb({
                "phase": "ENRICH",
                "status": "batch_complete",
                "count": len(profiles),
                "mode": "batched",
            })
        logger.info(
            "phase=ENRICH mode=batched status=ok total=%d duration=%.1fs",
            len(profiles), time.monotonic() - t0,
        )
        return profiles

    # ── Legacy per-competitor mode (RADAR_ENRICH_MODE=legacy) ─────
    logger.info(
        "phase=ENRICH mode=legacy status=start total=%d enriching=%d stubs=%d",
        len(competitors),
        min(len(competitors), MAX_ENRICH),
        max(0, len(competitors) - MAX_ENRICH),
    )

    to_enrich = competitors[:MAX_ENRICH]
    tail = competitors[MAX_ENRICH:]

    if to_enrich:
        estimated = RESEARCH_COST_EUR[DEPTH_TOP] + max(0, len(to_enrich) - 1) * RESEARCH_COST_EUR[DEPTH_REST]
        cumul = estimate_today_cost_eur()
        if cumul + estimated > DAILY_HARD_CAP_EUR:
            raise BudgetExceededError(
                f"scan would exceed daily cap €{DAILY_HARD_CAP_EUR:.2f} "
                f"(today={cumul:.2f} + scan={estimated:.2f})"
            )
        if cumul + estimated > DAILY_WARN_CAP_EUR:
            logger.warning(
                "daily linkup spend nearing cap: today=%.2f + scan=%.2f", cumul, estimated
            )

    schema = COMPETITOR_SCHEMA
    coords_map = await _geocode_all(to_enrich)

    jobs = []
    for i, c in enumerate(to_enrich):
        depth = DEPTH_TOP if i == 0 else DEPTH_REST
        jobs.append(
            _enrich_one(c, depth, schema, linkup, run_id, now, coords_map.get(i), event_cb=event_cb)
        )

    results = await asyncio.gather(*jobs, return_exceptions=True)

    enriched: list[CompetitorProfile] = []
    for c, r in zip(to_enrich, results):
        if isinstance(r, Exception):
            logger.error("enrich failed for %s: %s", c.get("website"), r)
            enriched.append(_stub(c, run_id, now))
        else:
            enriched.append(r)

    stubs = [_stub(c, run_id, now) for c in tail]
    profiles = enriched + stubs

    if event_cb:
        await event_cb(
            {
                "phase": "ENRICH",
                "status": "batch_complete",
                "count": len(profiles),
                "enriched": len(enriched),
                "stubs": len(stubs),
                "mode": "legacy",
            }
        )

    logger.info(
        "phase=ENRICH mode=legacy status=ok total=%d enriched=%d stubs=%d duration=%.1fs",
        len(profiles),
        len(enriched),
        len(stubs),
        time.monotonic() - t0,
    )
    return profiles


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.enrich '<json array of competitor dicts>'", file=sys.stderr)
        sys.exit(1)

    competitors_raw = json.loads(sys.argv[1])
    client = LinkupClient()
    result = asyncio.run(run(competitors_raw, client, run_id="cli-test"))
    print(json.dumps([p.model_dump() for p in result], indent=2, ensure_ascii=False, default=str))
