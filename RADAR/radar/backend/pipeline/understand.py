"""Phase 1 — UNDERSTAND: build CompanyProfile for a domain."""
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from clients.linkup_client import LinkupClient
from models.company import (
    CompanyProfile, DataPoint, Funding, FundingRound, HQ,
    KeyPerson, Market, NewsItem,
)
from utils.geocoding import geocode

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]

_SCHEMA = {
    "type": "object",
    "properties": {
        # ── IDENTITY ─────────────────────────────────────────────
        "name":         {"type": "string"},
        "website":      {"type": "string"},
        "summary":      {"type": "string"},
        "founded_year": {"type": "integer"},

        # ── LOCATION & SIZE ───────────────────────────────────────
        "hq_city":    {"type": "string"},
        "hq_country": {"type": "string"},
        "geo_coverage": {
            "type": "string",
            "enum": ["Local", "National", "Regional", "Global"],
        },
        "employees": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },

        # ── FUNDING ───────────────────────────────────────────────
        "funding_total_eur": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "funding_stage":          {"type": "string"},
        "funding_last_round":     {"type": "string"},
        "funding_last_round_date":{"type": "string"},
        "funding_rounds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "round":      {"type": "string"},
                    "amount_eur": {"type": "integer"},
                    "date":       {"type": "string"},
                    "lead":       {"type": "string"},
                },
            },
        },
        "notable_investors": {
            "type": "array",
            "items": {"type": "string"},
        },

        # ── PRODUCT & MARKET ──────────────────────────────────────
        "positioning": {"type": "string"},
        "markets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id":      {"type": "string"},
                    "label":   {"type": "string"},
                    "primary": {"type": "boolean"},
                },
            },
        },
        "target_segment": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "enum": ["Enterprise", "Mid-Market", "SMB", "Consumer", "Mixed"],
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
                "evidence":   {"type": "string"},
            },
        },
        "target_verticals": {
            "type": "array",
            "items": {"type": "string"},
        },
        "business_model": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "enum": ["B2B", "B2C", "B2B2C", "Marketplace", "API/Platform"],
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "gtm_motion": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "enum": ["sales-led", "product-led", "marketing-led", "community-led"],
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "pricing_model": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "enum": ["Freemium", "Subscription", "Usage-based", "Enterprise/Sur devis", "Hybrid"],
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },

        # ── DIFFERENTIATION ───────────────────────────────────────
        "key_differentiator": {
            "type": "object",
            "properties": {
                "value":      {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "top_3_features": {
            "type": "array",
            "items": {"type": "string"},
        },
        "notable_customers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tech_stack": {
            "type": "array",
            "items": {"type": "string"},
        },

        # ── TEAM ──────────────────────────────────────────────────
        "key_people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":       {"type": "string"},
                    "role":       {"type": "string"},
                    "background": {"type": "string"},
                    "linkedin":   {"type": "string"},
                },
            },
        },

        # ── SIGNALS ───────────────────────────────────────────────
        "growth_signals": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recent_news": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date":       {"type": "string"},
                    "headline":   {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
    },
}


def _understand_query(domain: str) -> str:
    return (
        f"You are a company intelligence analyst. Build a complete profile of {domain}.\n\n"
        f"Search {domain}, {domain}/about, {domain}/team, {domain}/pricing, Crunchbase, LinkedIn, "
        f"Pitchbook, TechCrunch, and recent news. Run adjacent searches for "
        f"'{domain} funding', '{domain} employees', '{domain} customers' to ensure breadth.\n\n"
        "Extract the following — cite source URL for each section:\n\n"
        f"IDENTITY: Official company name, website URL, founding year.\n\n"
        f"HQ: Headquarters city and country. Geographic coverage (Local/National/Regional/Global).\n\n"
        f"FUNDING: Total raised EUR, all funding rounds (amount, date, lead investor), "
        "current stage (Seed/Series A/B/C+/Public/Bootstrapped), notable investors.\n\n"
        f"EMPLOYEES: Current headcount with source and confidence level.\n\n"
        f"POSITIONING: One-paragraph business description. Main product markets and verticals. "
        "Target customer segment (Enterprise/Mid-Market/SMB/Consumer/Mixed) — cite homepage or press evidence.\n\n"
        f"BUSINESS MODEL: B2B/B2C/B2B2C/Marketplace/API-Platform. "
        "GTM motion (sales-led/product-led/marketing-led/community-led). "
        "Pricing model (Freemium/Subscription/Usage-based/Enterprise/Hybrid).\n\n"
        f"PRODUCT: Key differentiator in 20 words max. Top 3 features. "
        "3-5 notable customers or client logos visible on website.\n\n"
        f"TECH: Main technology stack (max 10 tools, e.g. AWS, Stripe, Vercel, Postgres).\n\n"
        f"TEAM: Founders and key executives — name, role, background, LinkedIn URL for each.\n\n"
        f"SIGNALS: Recent growth signals (headcount growth, geo expansion, new products). "
        "Last 3 notable news items with date and source URL."
    )


async def run(
    domain: str,
    linkup: LinkupClient,
    run_id: str | None = None,
    depth: str = "standard",
    event_cb: Optional[EventCallback] = None,
) -> CompanyProfile:
    t0 = time.monotonic()
    run_id = run_id or str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async def emit(event: dict) -> None:
        if event_cb:
            try:
                await event_cb(event)
            except Exception as _e:
                logger.debug("understand emit error ignored: %s", _e)

    logger.info("phase=UNDERSTAND company=%s status=start", domain)

    raw = await linkup.search(
        depth=depth,
        query=_understand_query(domain),
        schema=_SCHEMA,
    )

    data: dict = raw.get("data") or raw.get("answer") or raw.get("output") or {}
    sources: list = raw.get("sources", [])
    src_url = sources[0].get("url") if sources else None
    # Dedup + filter empties — preserves order of first occurrence
    _seen: set[str] = set()
    source_urls: list[str] = []
    for s in sources:
        if isinstance(s, dict):
            u = s.get("url")
            if u and u not in _seen:
                _seen.add(u)
                source_urls.append(u)

    # Emit source_consulted for each URL returned by Linkup
    for src in sources:
        src_item_url = src.get("url", "")
        if src_item_url:
            try:
                from urllib.parse import urlparse as _urlparse
                src_domain = _urlparse(src_item_url).netloc.lstrip("www.") or src_item_url[:100]
            except Exception:
                src_domain = src_item_url[:100]
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "source_consulted",
                "payload": {"url": src_item_url[:100], "domain": src_domain[:100]},
            })

    def _dp_obj(obj) -> DataPoint | None:
        """Parse a DataPoint object returned by Linkup structured output."""
        if not isinstance(obj, dict):
            return None
        value = obj.get("value")
        if value is None:
            return None
        return DataPoint(
            value=value,
            confidence=obj.get("confidence", "medium"),
            source_url=obj.get("source_url") or src_url,
            evidence=obj.get("evidence"),
            extracted_at=now,
        )

    # Emit field_extracted for key scalar fields
    _field_emit_map = [
        ("founded_year",   data.get("founded_year"),   0.9),
        ("hq_city",        data.get("hq_city"),        0.9),
        ("hq_country",     data.get("hq_country"),     0.9),
        ("funding_stage",  data.get("funding_stage"),  0.85),
        ("geo_coverage",   data.get("geo_coverage"),   0.8),
    ]
    for _field, _value, _conf in _field_emit_map:
        if _value is not None:
            _str_value = str(_value)[:100]
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {"field": _field, "value": _str_value, "confidence": _conf},
            })

    # Emit for structured DataPoint fields with their own confidence
    _dp_field_map = [
        ("employees",        data.get("employees")),
        ("funding_total_eur", data.get("funding_total_eur")),
        ("target_segment",   data.get("target_segment")),
        ("business_model",   data.get("business_model")),
        ("pricing_model",    data.get("pricing_model")),
    ]
    for _field, _obj in _dp_field_map:
        if isinstance(_obj, dict) and _obj.get("value") is not None:
            _conf_raw = _obj.get("confidence", "medium")
            _conf_num = {"high": 0.95, "medium": 0.75, "low": 0.5}.get(str(_conf_raw), 0.75)
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {
                    "field": _field,
                    "value": str(_obj["value"])[:100],
                    "confidence": _conf_num,
                },
            })

    hq = None
    if data.get("hq_city") or data.get("hq_country"):
        city, country = data.get("hq_city"), data.get("hq_country")
        coords = await geocode(city or "", country or "")
        hq = HQ(
            city=city,
            country=country,
            lat=coords[0] if coords else None,
            lng=coords[1] if coords else None,
        )
        if coords:
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {
                    "field": "hq.coords",
                    "value": f"{coords[0]:.4f},{coords[1]:.4f}",
                    "confidence": 0.99,
                },
            })

    funding_rounds = [
        FundingRound(
            round=r.get("round"),
            amount_eur=r.get("amount_eur"),
            date=r.get("date"),
            lead=r.get("lead"),
        )
        for r in (data.get("funding_rounds") or [])
    ]

    funding = None
    if data.get("funding_total_eur") or data.get("funding_last_round") or funding_rounds:
        funding = Funding(
            total_raised_eur=_dp_obj(data.get("funding_total_eur")),
            last_round=data.get("funding_last_round"),
            last_round_date=data.get("funding_last_round_date"),
            rounds=funding_rounds,
        )

    markets = [
        Market(
            id=m.get("id", m.get("label", "unknown").lower().replace(" ", "_")),
            label=m.get("label", ""),
            primary=m.get("primary", False),
        )
        for m in (data.get("markets") or [])
    ] or [
        Market(
            id=v.lower().replace(" ", "_"),
            label=v,
            primary=i == 0,
        )
        for i, v in enumerate(data.get("target_verticals") or [])
    ]

    key_people = [
        KeyPerson(
            name=p.get("name", ""),
            role=p.get("role"),
            background=p.get("background"),
            linkedin=p.get("linkedin"),
        )
        for p in (data.get("key_people") or [])
        if p.get("name")
    ]

    recent_news = [
        NewsItem(
            date=n.get("date"),
            headline=n.get("headline", ""),
            source_url=n.get("source_url"),
        )
        for n in (data.get("recent_news") or [])
        if n.get("headline")
    ]

    profile = CompanyProfile(
        name=data.get("name") or domain,
        domain=domain,
        website=data.get("website"),
        summary=data.get("summary"),
        founded_year=data.get("founded_year"),
        hq=hq,
        geo_coverage=data.get("geo_coverage"),
        employees=_dp_obj(data.get("employees")),
        funding=funding,
        funding_stage=data.get("funding_stage"),
        notable_investors=data.get("notable_investors") or [],
        positioning=data.get("positioning"),
        markets=markets,
        target_segment=_dp_obj(data.get("target_segment")),
        target_verticals=data.get("target_verticals") or [],
        business_model=_dp_obj(data.get("business_model")),
        gtm_motion=_dp_obj(data.get("gtm_motion")),
        pricing_model=_dp_obj(data.get("pricing_model")),
        key_differentiator=_dp_obj(data.get("key_differentiator")),
        top_3_features=data.get("top_3_features") or [],
        notable_customers=data.get("notable_customers") or [],
        tech_stack=data.get("tech_stack") or [],
        key_people=key_people,
        growth_signals=data.get("growth_signals") or [],
        recent_news=recent_news,
        source_urls=source_urls,
        pipeline_run_id=run_id,
    )

    logger.info("phase=UNDERSTAND company=%s status=ok duration=%.1fs", domain, time.monotonic() - t0)
    return profile


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.understand <domain>", file=sys.stderr)
        sys.exit(1)

    client = LinkupClient()
    result = asyncio.run(run(sys.argv[1].strip().lower(), client))
    print(result.model_dump_json(indent=2))
