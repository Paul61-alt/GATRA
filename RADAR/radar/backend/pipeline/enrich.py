"""Phase 3 — ENRICH: deep competitor profiling via Linkup Research.

One Research(Investigate, depth=S) call per competitor, submitted as a single
batch via /v1/tasks. Returns structured CompetitorProfile with pricing tiers,
LinkedIn signals, recent signals, and funding details.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from clients.linkup_client import LinkupClient
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
        f"{name} ({domain}) deep competitive profile 2025-2026: "
        "pricing tiers with exact monthly and annual prices, free plan availability, recent price changes; "
        "recent product launches and AI features (2024-2026); "
        "funding stage, latest round amount and date, total raised, key investors; "
        "employee count and headcount growth signals; "
        "LinkedIn company page URL; "
        "CEO and founder LinkedIn profile URLs; "
        "recent public statements or LinkedIn posts from founders (last 6 months); "
        "key differentiators vs alternatives; "
        "target customer segments and notable customers; "
        "known weaknesses or limitations cited by users"
    )


def _make_tasks_payload(competitors: list[dict]) -> list[dict]:
    return [
        {
            "type": "research",
            "input": {
                "q": _research_query(
                    c.get("name") or c.get("website", ""),
                    c.get("website", ""),
                ),
                "mode": "Investigate",
                "depth": "S",
                "outputType": "structured",
                "structuredOutputSchema": json.dumps(COMPETITOR_SCHEMA),
            },
        }
        for c in competitors
    ]


def _parse_result(
    raw: dict,
    competitor: dict,
    now: str,
    run_id: str,
    coords,
) -> CompetitorProfile:
    output = raw.get("output", {})
    # Research structured output wraps data in "data" key; fall back to output itself
    data = output.get("data") or output
    sources = output.get("sources", [])
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


async def run(
    competitors: list[dict],
    linkup: LinkupClient,
    run_id: str,
    event_cb=None,
) -> list[CompetitorProfile]:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    logger.info("phase=ENRICH status=start count=%d", len(competitors))

    tasks_payload = _make_tasks_payload(competitors)
    task_results = await linkup.tasks(tasks_payload)

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

    profiles: list[CompetitorProfile] = []
    for i, c in enumerate(competitors):
        raw = task_results[i] if i < len(task_results) else {}
        coords = coords_list[i]
        try:
            profile = _parse_result(raw, c, now, run_id, coords)
        except Exception as e:
            logger.warning("enrich parse_error competitor=%s error=%s", c.get("name"), e)
            profile = CompetitorProfile(
                name=c.get("name", ""),
                website=c.get("website", ""),
                one_liner=c.get("one_liner"),
                pipeline_run_id=run_id,
            )
        profiles.append(profile)

    if event_cb:
        await event_cb({"phase": "ENRICH", "status": "batch_complete", "count": len(profiles)})

    logger.info(
        "phase=ENRICH status=ok count=%d duration=%.1fs",
        len(profiles),
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
