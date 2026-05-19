"""Phase 3 — ENRICH: deep competitor profiling via Linkup /research.

Cap: only the top MAX_ENRICH competitors are enriched (top-1 at depth M,
positions 2..MAX_ENRICH at depth S). The remaining competitors are returned
as minimal stubs built from the discover payload — no Linkup call.

Override for demo/test: RADAR_MAX_ENRICH=1 env var caps to 1 competitor.
Default is 5. Production unaffected when env var is unset.
"""
import asyncio
import json
import logging
import os
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
from utils.geocoding import geocode

logger = logging.getLogger(__name__)

MAX_ENRICH = int(os.environ.get("RADAR_MAX_ENRICH", "5"))
DEPTH_TOP: Literal["M"] = "M"
DEPTH_REST: Literal["S"] = "S"

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
) -> CompetitorProfile:
    query = _research_query(
        competitor.get("name") or competitor.get("website", ""),
        competitor.get("website", ""),
    )
    result = await linkup.research_and_wait(query, depth=depth, structured_schema=schema)
    return _parse_result(result, competitor, now, run_id, coords)


async def run(
    competitors: list[dict],
    linkup: LinkupClient,
    run_id: str,
    event_cb=None,
) -> list[CompetitorProfile]:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    logger.info(
        "phase=ENRICH status=start total=%d enriching=%d stubs=%d",
        len(competitors),
        min(len(competitors), MAX_ENRICH),
        max(0, len(competitors) - MAX_ENRICH),
    )

    to_enrich = competitors[:MAX_ENRICH]
    tail = competitors[MAX_ENRICH:]

    # ── Budget guard ──────────────────────────────────────────────
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
        jobs.append(_enrich_one(c, depth, schema, linkup, run_id, now, coords_map.get(i)))

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
            }
        )

    logger.info(
        "phase=ENRICH status=ok total=%d enriched=%d stubs=%d duration=%.1fs",
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
