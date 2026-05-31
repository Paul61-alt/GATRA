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
from typing import Literal, Optional

from clients.linkup_client import (
    DAILY_HARD_CAP_EUR,
    DAILY_WARN_CAP_EUR,
    RESEARCH_COST_EUR,
    BudgetExceededError,
    LinkupClient,
    estimate_today_cost_eur,
)
from models.company import (
    AcquisitionInfo,
    CustomerExample,
    DataPoint,
    Funding,
    FundingRound,
    HQ,
    Investor,
    KeyPerson,
    PricingTier,
)
from pipeline.understand import _norm_segment
from models.competitor import (
    CapabilityCell,
    CompetitorProfile,
    Feature,
    LinkedInSignal,
    PricingSignal,
    RecentSignal,
)
from utils.dedup import normalize_domain
from utils.geocoding import geocode

logger = logging.getLogger(__name__)

ENRICH_MODE = os.environ.get("RADAR_ENRICH_MODE", "5_lanes").lower()
MAX_ENRICH = int(os.environ.get("RADAR_MAX_ENRICH", "5"))
DEPTH_TOP: Literal["M"] = "M"
DEPTH_REST: Literal["S"] = "S"
DEPTH_BATCH: Literal["M"] = "M"  # Single call, mid-depth covers cohort breadth
# /research is $1.50 FLAT regardless of depth (S/M/L/XL) — see linkup_client.
# So S is strictly worse: same price, shallowest result. Live probe on the
# Finary cohort showed depth=S returned near-empty funding/employee data for
# all 10 competitors, while depth=L returned full profiles (employees, founding
# year, funding rounds, investors). Default to L: same cost, far richer data.
# Latency cost ~ a few extra minutes per lane.
_ALLOWED_DEPTHS = {"S", "M", "L", "XL"}
_raw_depth = os.environ.get("RADAR_ENRICH_DEPTH_LANE", "L").upper()
if _raw_depth not in _ALLOWED_DEPTHS:
    logger.warning(
        "invalid RADAR_ENRICH_DEPTH_LANE=%s → fallback to L (allowed: %s)",
        _raw_depth, sorted(_ALLOWED_DEPTHS),
    )
    _raw_depth = "L"
DEPTH_LANE: Literal["S", "M", "L", "XL"] = _raw_depth  # type: ignore[assignment]

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
        "notable_customers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":     {"type": "string"},
                    "segment":  {"type": "string", "enum": ["Grand compte", "ETI", "PME", "Startup", "Consumer"]},
                    "industry": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
        },
        "acquisition": {
            "type": "object",
            "properties": {
                "acquired":    {"type": "boolean"},
                "acquirer":    {"type": "string"},
                "amount_eur":  {"type": "integer"},
                "year":        {"type": "integer"},
                "source_url":  {"type": "string"},
            },
        },
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
        "Identify primary target customer segment. "
        "List up to 5 publicly known customers — for each, classify: "
        "'Grand compte' (CAC40/Fortune500), 'ETI' (mid-size 250-5000 employees), "
        "'PME' (<250 employees), 'Startup', or 'Consumer'. Include industry and any concrete result.\n\n"
        f"ACQUISITION: Find whether {name} has been acquired. "
        "If yes: acquirer name, amount in EUR, year, source URL. If not acquired, return acquired=false.\n\n"
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
            name=_strip_md_links(t.get("name")),
            price_monthly_usd=t.get("price_monthly_usd"),
            price_annual_usd=t.get("price_annual_usd"),
            features=[_strip_md_links(f) for f in (t.get("features") or [])],
            target=_strip_md_links(t.get("target")),
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
            excerpt=s.get("excerpt"),
            image_url=s.get("image_url"),
            source_url=s.get("source_url"),
        )
        for s in data.get("recent_linkedin_signals", [])
        if s.get("signal") or s.get("excerpt")
    ]

    differentiators = data.get("key_differentiators", [])

    notable_customers = [
        CustomerExample(
            name=c.get("name", ""),
            domain=c.get("domain"),
            segment=_norm_segment(c.get("segment")),
            industry=c.get("industry"),
            evidence=c.get("evidence"),
        )
        for c in (data.get("notable_customers") or [])
        if isinstance(c, dict) and c.get("name")
    ]

    acquisition_raw = data.get("acquisition") or {}
    acquisition = None
    if acquisition_raw and isinstance(acquisition_raw, dict):
        acquisition = AcquisitionInfo(
            acquired=acquisition_raw.get("acquired", False),
            acquirer=acquisition_raw.get("acquirer"),
            amount_eur=acquisition_raw.get("amount_eur"),
            year=acquisition_raw.get("year"),
            source_url=acquisition_raw.get("source_url"),
        )

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
        notable_customers=notable_customers,
        acquisition=acquisition,
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


async def _fill_missing_coords(profiles: list[CompetitorProfile]) -> None:
    """Re-geocode profiles whose hq has city/country but missing lat/lng.

    Initial _geocode_all runs before LLM enrichment, so shortlist competitors
    without hq_city/hq_country in the input dict have no coords. After LLM
    fills hq.city/country, re-geocode in place.
    """
    targets: list[tuple[int, str, str]] = []
    for i, p in enumerate(profiles):
        if not p.hq:
            continue
        if p.hq.lat is not None and p.hq.lng is not None:
            continue
        city = p.hq.city or ""
        country = p.hq.country or ""
        if city or country:
            targets.append((i, city, country))

    if not targets:
        return

    results = await asyncio.gather(
        *[geocode(city, country) for _, city, country in targets],
        return_exceptions=True,
    )
    for (i, _, _), coords in zip(targets, results):
        if isinstance(coords, tuple):
            profiles[i].hq.lat = coords[0]
            profiles[i].hq.lng = coords[1]


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
        "- one_liner, key_differentiators, target_segment, weaknesses\n"
        "- notable_customers: array of {name, segment (Grand compte/ETI/PME/Startup/Consumer), industry, evidence}\n"
        "- acquisition: {acquired (bool), acquirer, amount_eur, year, source_url} — return acquired=false if not acquired\n"
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


# ═════════════════════════════════════════════════════════════════════════════
#  5-LANES MODE  (RADAR_ENRICH_MODE=5_lanes, default)
# ═════════════════════════════════════════════════════════════════════════════
# Each of the 5 lanes is ONE batched call covering ALL competitors for one
# theme (instead of N×5 per-competitor calls). Total = 5 calls / scan.
# Lanes 1,2,4,5 use /research depth=M (€0.50 each).
# Lane 3 (LinkedIn) uses /search depth=deep structured (€0.055) per Linkup docs
# ("LinkedIn extraction works exclusively through the Search endpoint").
# Cost per scan: 4 × €0.50 + €0.055 = €2.055.
#
# Key schema rule discovered during eval rounds: do NOT use `required` on
# inner items — Linkup pads with dummy strings ("null", "placeholder")
# instead of omitting. Use code-side filters for null/dummy entries.


def _company_listing(competitors: list[dict]) -> str:
    """Standard listing format. `name=` explicit to prevent Linkup from
    capturing wrapping format as the name field (eval round 4 lesson).
    """
    return "\n".join(
        f'  {i+1}. name="{c.get("name","?")}", website="{c.get("website","?")}"'
        for i, c in enumerate(competitors)
    )


# ── LANE 1 schema + prompt ────────────────────────────────────────────────────
_LANE1_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Exact name from input list"},
        "website": {"type": "string"},
        "hq_city": {"type": "string"},
        "hq_country": {"type": "string"},
        "founded_year": {"type": "integer"},
        "employee_count": {"type": "integer"},
        "employee_growth_yoy": {"type": "number", "description": "YoY headcount change as decimal (0.12 = +12%)"},
        "funding_stage": {"type": "string"},
        "funding_status": {
            "type": "string",
            "enum": ["Funded", "Bootstrapped", "Stealth", "Unknown"],
            "description": "Explicit funding posture: Funded if any disclosed round; Bootstrapped if founders publicly self-funded / no VC; Stealth if company explicitly in stealth mode; Unknown otherwise.",
        },
        "funding_total_usd": {"type": "integer"},
        "last_round_amount_usd": {"type": "integer"},
        "last_round_date": {"type": "string"},
        "last_round_type": {"type": "string"},
        "funding_rounds": {
            "type": "array",
            "description": "All known investment rounds, ordered oldest to newest",
            "items": {
                "type": "object",
                "properties": {
                    "round": {"type": "string", "description": "Seed / Series A / Series B / etc."},
                    "amount_usd": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD or YYYY-MM"},
                    "lead": {"type": "string", "description": "Lead investor name"},
                },
            },
        },
        "notable_investors": {
            "type": "array",
            "description": "Distinct investor list across all rounds",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": "string", "description": "Investor website domain (for logo lookup)"},
                },
            },
        },
        "arr_usd": {"type": "number", "description": "Annual Recurring Revenue in USD, only if publicly disclosed"},
        "customer_count": {"type": "integer", "description": "Total customer count if announced"},
        "avg_contract_usd": {"type": "number", "description": "Average contract value USD if disclosed"},
        "acquisition": {
            "type": "object",
            "properties": {
                "acquired": {"type": "boolean"},
                "acquirer": {"type": "string"},
                "amount_eur": {"type": "integer"},
                "year": {"type": "integer"},
                "source_url": {"type": "string"},
            },
        },
    },
}

LANE1_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {"type": "array", "items": _LANE1_ITEM_SCHEMA},
    },
}


def _lane1_query(competitors: list[dict]) -> str:
    return (
        f"You are a venture-capital analyst. For each of the {len(competitors)} companies "
        "below, build an identity + financial profile from Crunchbase, Pitchbook, Dealroom, "
        "TechCrunch, Les Echos, official press releases, and LinkedIn About sections.\n\n"
        f"Companies:\n{_company_listing(competitors)}\n\n"
        "For EACH company extract:\n"
        "- name (EXACTLY as listed above), website, hq_city, hq_country, founded_year\n"
        "- employee_count (current LinkedIn headcount as integer)\n"
        "- employee_growth_yoy (year-over-year change as decimal: +12% → 0.12)\n"
        "- funding_stage (Seed / Series A / B / C / Public / Bootstrapped)\n"
        "- funding_status: 'Funded' if any disclosed round; 'Bootstrapped' if founders publicly state self-funded / no VC / never raised; 'Stealth' if company explicitly operating in stealth mode; 'Unknown' otherwise.\n"
        "- funding_total_usd (cumulative raised in USD)\n"
        "- last_round_amount_usd, last_round_date (YYYY-MM-DD), last_round_type\n"
        "- funding_rounds: COMPLETE history — array of {round, amount_usd, date, lead} "
        "ordered chronologically. Aim for 2-5 rounds when available.\n"
        "- notable_investors: distinct VCs/angels/corporates across all rounds. "
        "For each: {name, domain}. The domain is the investor's website "
        "(e.g. 'sequoiacap.com' for Sequoia Capital) — critical for logo display.\n"
        "- arr_usd: ONLY if publicly disclosed (funding press, podcast). Do NOT estimate.\n"
        "- customer_count: ONLY if officially announced.\n"
        "- avg_contract_usd: ONLY if disclosed.\n"
        "- acquisition: {acquired, acquirer, amount_eur, year, source_url}. "
        "Return acquired=false if not acquired.\n\n"
        "Omit any field you cannot verify — do NOT pad with placeholders or guess. "
        "Return one object per company in the SAME order as the input list."
    )


# ── LANE 2 schema + prompt — PRICING ──────────────────────────────────────────
_LANE2_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "pricing_model_kind": {
            "type": "string",
            "description": "One of: Freemium, Subscription, Usage-based, Enterprise, Hybrid",
        },
        "free_plan": {"type": "boolean"},
        "starts_at_usd": {"type": "number", "description": "Lowest paid tier monthly USD price, 0 if free, null if Enterprise-only"},
        "mention": {"type": "string", "description": "UI-displayable tagline e.g. 'Starts at $20/user/mo' or 'Contact sales'"},
        "tiers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tier name (e.g. Free, Pro, Business, Enterprise)"},
                    "price_monthly_usd": {"type": "number"},
                    "price_annual_usd": {"type": "number"},
                    "features": {"type": "array", "items": {"type": "string"}, "description": "Top 3-6 features unlocked at this tier"},
                    "target": {"type": "string", "description": "Target segment (Solo / Team / Business / Enterprise)"},
                },
            },
        },
        "recent_changes": {"type": "string", "description": "Recent pricing changes if any, with date and source"},
    },
}

LANE2_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {"type": "array", "items": _LANE2_ITEM_SCHEMA},
    },
}


def _lane2_query(competitors: list[dict]) -> str:
    return (
        f"You are a SaaS pricing analyst. For each of the {len(competitors)} companies "
        "below, extract their CURRENT pricing structure from their public pricing pages "
        "({domain}/pricing, {domain}/plans), G2, Capterra, and reverse-engineering posts.\n\n"
        f"Companies:\n{_company_listing(competitors)}\n\n"
        "For EACH company extract:\n"
        "- pricing_model_kind: one of Freemium, Subscription, Usage-based, Enterprise, Hybrid\n"
        "- free_plan: true/false\n"
        "- starts_at_usd: lowest paid tier monthly USD (0 if free plan only, null if Enterprise-only / contact sales)\n"
        "- mention: short UI tagline e.g. 'Starts at $20/user/mo' or 'Contact sales' or 'Free + paid plans from $8/mo'\n"
        "- tiers: array of {name, price_monthly_usd, price_annual_usd, features (3-6 strings), target}. "
        "Include ALL public tiers (e.g. Free, Pro, Business, Enterprise). For Enterprise tiers without "
        "public price, set price_monthly_usd=null and target='Enterprise'.\n"
        "- recent_changes: any pricing change in last 12 months (date + source). "
        "Leave blank if none.\n\n"
        "Omit any field you cannot verify — do NOT invent prices. "
        "Return one object per company in the SAME order as the input list. "
        "Preserve company names EXACTLY."
    )


# ── LANE 3 schema + prompt — LINKEDIN (ported from validated eval) ────────────
_LANE3_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "linkedin_url": {"type": "string", "description": "Exact LinkedIn company URL, format linkedin.com/company/<slug>"},
        "key_people": {
            "type": "array",
            "description": "Senior employees from the People tab. Omit entries you cannot fully verify.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "linkedin": {"type": "string", "description": "Personal profile URL, format linkedin.com/in/<slug>"},
                    "background": {"type": "string", "description": "MUST mention the target company by name"},
                },
            },
        },
        "recent_linkedin_signals": {
            "type": "array",
            "description": "Recent public posts (company page or founders). Omit slots you cannot fully populate.",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "author": {"type": "string"},
                    "signal": {"type": "string", "description": "Post headline or first 150 chars"},
                    "excerpt": {"type": "string", "description": "First ~280 chars of the post body text, verbatim. Null if not readable."},
                    "image_url": {"type": "string", "description": "Direct URL of the post's main image (og:image / media.licdn.com) if any, else null."},
                    "source_url": {"type": "string", "description": "Full post URL"},
                },
            },
        },
    },
}

LANE3_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {"type": "array", "items": _LANE3_ITEM_SCHEMA},
    },
}


def _lane3_query(competitors: list[dict]) -> str:
    return (
        f"For each of the {len(competitors)} companies listed below, perform a LinkedIn-only "
        "extraction in three sequential steps. The 'name' field in your output must be "
        "EXACTLY the name string given below (without the website).\n\n"
        f"Companies:\n{_company_listing(competitors)}\n\n"
        "STEP 1 — For each company, find its exact LinkedIn company page URL "
        "(format: linkedin.com/company/<slug>). The slug is usually derived from "
        "the company name or website domain.\n\n"
        "STEP 2 — Scrape each LinkedIn company page URL found in step 1. "
        "Return the profile details: linkedin_url, plus the 5 most senior CURRENT EMPLOYEES "
        "from the People tab (CEO, CTO, CPO, co-founders, VP-level). For each person: "
        "name, current role AT THIS COMPANY (not at a previous employer), exact personal "
        "profile URL (linkedin.com/in/<slug>), and a one-sentence background that mentions "
        "the target company by name (e.g. 'Co-founder & CTO at <CompanyName>...'). "
        "Include only people who currently work at the target company — exclude external "
        "partners, customers, or event speakers mentioned in posts.\n\n"
        "STEP 3 — For each company page, return the 3 to 5 MOST RECENT public posts "
        "from the company page or its founders (last 12 months). For each post: "
        "date (YYYY-MM-DD), author name, signal (post headline or first 150 chars), "
        "excerpt (first ~280 chars of the post body, verbatim), "
        "image_url (direct URL of the post's main image / og:image / media.licdn.com "
        "if the post has one, else null), "
        "and full post URL (linkedin.com/posts/...).\n\n"
        "Return one object per company in the same order as the input list. "
        "Preserve company names EXACTLY as given. "
        "If LinkedIn does not yield a value for a field, set it to null. "
        "Do not fabricate values or pull from other sources."
    )


# ── LANE 4 schema + prompt — NEWS + GTM POSITIONING ───────────────────────────
_LANE4_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "one_liner": {"type": "string", "description": "Single-sentence pitch from homepage"},
        "key_differentiators": {"type": "array", "items": {"type": "string"}, "description": "3-5 unique selling points"},
        "weaknesses": {"type": "array", "items": {"type": "string"}, "description": "Recurring user complaints from G2/Capterra/Reddit"},
        "target_segment": {
            "type": "string",
            "description": "Primary customer segment: Grand compte / ETI / PME / Startup / Consumer",
        },
        "business_model": {
            "type": "string",
            "description": "B2B, B2C, B2B2C, Marketplace, or API/Platform",
        },
        "gtm_motion": {
            "type": "string",
            "description": "sales-led, product-led, marketing-led, or community-led",
        },
        "geo_coverage": {
            "type": "string",
            "description": "Local, National, Regional, or Global",
        },
        "recent_signals": {
            "type": "array",
            "description": "5-10 most significant signals in last 6 months. Omit entries you cannot fully populate.",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "headline": {"type": "string"},
                    "source_url": {"type": "string"},
                    "type": {"type": "string", "description": "One of: funding, product, hiring, partnership, press"},
                },
            },
        },
    },
}

LANE4_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {"type": "array", "items": _LANE4_ITEM_SCHEMA},
    },
}


def _lane4_query(competitors: list[dict]) -> str:
    return (
        f"You are a competitive intelligence analyst. For each of the {len(competitors)} "
        "companies below, analyse their positioning, go-to-market motion, and recent news. "
        "Sources: company homepage, About page, press releases, TechCrunch, Sifted, "
        "VentureBeat, Reddit, G2, Capterra.\n\n"
        f"Companies:\n{_company_listing(competitors)}\n\n"
        "For EACH company extract:\n"
        "- one_liner: single-sentence value prop from their homepage\n"
        "- key_differentiators: 3-5 unique selling points vs alternatives\n"
        "- weaknesses: 2-4 recurring user complaints from G2/Capterra/Reddit/Hacker News\n"
        "- target_segment: PRIMARY customer segment — pick one of: 'Grand compte' "
        "(Fortune 500 / CAC40), 'ETI' (250-5000 employees), 'PME' (<250 employees), "
        "'Startup', or 'Consumer' (B2C)\n"
        "- business_model: pick one of: B2B, B2C, B2B2C, Marketplace, API/Platform\n"
        "- gtm_motion: pick one based on their primary homepage CTA — "
        "'sales-led' (CTA = Book demo / Talk to sales / Contact us), "
        "'product-led' (CTA = Start free / Sign up / Try free), "
        "'marketing-led' (CTA = Read whitepaper / Download report), "
        "'community-led' (CTA = Join community / Slack invite)\n"
        "- geo_coverage: pick one of: Local (1 city/country), National, Regional (continent), Global\n"
        "- recent_signals: 5-10 most significant news items from the last 6 months. "
        "For each: date (YYYY-MM-DD), headline, source_url, type. "
        "type MUST be one of: funding / product / hiring / partnership / press.\n\n"
        "Omit any field you cannot verify — do NOT invent classifications. "
        "Return one object per company in the SAME order as the input list. "
        "Preserve company names EXACTLY."
    )


# ── LANE 5 schema + prompt — FEATURES + CAPABILITIES + CUSTOMERS ──────────────
_LANE5_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "capabilities": {
            "type": "array",
            "description": "Per-feature coverage. One entry per feature listed at run level.",
            "items": {
                "type": "object",
                "properties": {
                    "feature": {"type": "string", "description": "Feature label (must match the shared features list above)"},
                    "value": {"type": "string", "description": "One of: full / part / none / soon"},
                },
            },
        },
        "notable_customers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": "string", "description": "Customer website domain for logo lookup"},
                    "segment": {"type": "string", "description": "Grand compte / ETI / PME / Startup / Consumer"},
                    "industry": {"type": "string"},
                    "evidence": {"type": "string", "description": "Case study URL or quote"},
                },
            },
        },
    },
}

LANE5_SCHEMA = {
    "type": "object",
    "required": ["features", "competitors"],
    "properties": {
        "features": {
            "type": "array",
            "description": "Shared feature axes across the cohort (6-10 items). Same for all competitors.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Feature name (e.g. 'Real-time collaboration')"},
                    "group": {"type": "string", "description": "Category: Core / Pricing / Integrations / Enterprise / Mobile"},
                },
            },
        },
        "competitors": {"type": "array", "items": _LANE5_ITEM_SCHEMA},
    },
}


def _lane5_query(competitors: list[dict], subject: dict | None = None) -> str:
    subject_name = (subject or {}).get("name", "the subject company")
    subject_domain = (subject or {}).get("website") or (subject or {}).get("domain", "")
    return (
        f"You are a product analyst building a feature comparison matrix. "
        f"The subject is {subject_name} ({subject_domain}). Compare it against the "
        f"{len(competitors)} competitors below.\n\n"
        f"Competitors:\n{_company_listing(competitors)}\n\n"
        "STEP 1 — Identify 6 to 10 KEY FEATURES that matter when comparing these products. "
        "Group them by category (Core / Pricing / Integrations / Enterprise / Mobile). "
        "Return as 'features' array with {label, group}. The SAME features list must be "
        "used to score every competitor — choose features that are meaningful for all.\n\n"
        "STEP 2 — For EACH competitor, return a 'capabilities' array with one entry per "
        "feature defined in step 1. Each entry: {feature: '<exact label>', value: '<one of full/part/none/soon>'}. "
        "'full' = covered with a dedicated feature. 'part' = partial / limited coverage. "
        "'none' = not supported. 'soon' = on public roadmap.\n\n"
        "STEP 3 — For EACH competitor, also return notable_customers: 3-5 publicly known "
        "customers with {name, domain, segment (Grand compte/ETI/PME/Startup/Consumer), "
        "industry, evidence (case study URL or quote)}.\n\n"
        "Omit any capability you cannot verify — do NOT guess. "
        "Return one competitor object per company in the SAME order as the input list. "
        "Preserve company names EXACTLY."
    )


# ── Generic lane runner ───────────────────────────────────────────────────────

async def _run_research_lane(
    lane_name: str,
    competitors: list[dict],
    query: str,
    schema: dict,
    linkup: LinkupClient,
    event_cb=None,
) -> dict:
    """Run one /research lane, return raw output dict. Emits SSE per poll."""
    async def _on_poll(state: dict) -> None:
        if event_cb is None:
            return
        await event_cb({
            "phase": "ENRICH",
            "status": "polling",
            "lane": lane_name,
            "competitor": f"cohort of {len(competitors)}",
            "elapsed": state.get("elapsed", 0),
            "research_status": state.get("status"),
            "job_id": state.get("job_id"),
        })
    raw = await linkup.research_and_wait(
        query, depth=DEPTH_LANE, structured_schema=schema, on_poll=_on_poll
    )
    return raw


async def _run_search_lane(
    lane_name: str,
    competitors: list[dict],
    query: str,
    schema: dict,
    linkup: LinkupClient,
    event_cb=None,
) -> dict:
    """Run one /search deep structured lane (used by Lane 3 LinkedIn)."""
    if event_cb:
        await event_cb({
            "phase": "ENRICH",
            "status": "polling",
            "lane": lane_name,
            "competitor": f"cohort of {len(competitors)}",
            "elapsed": 0,
            "research_status": "running",
        })
    raw = await linkup.search(
        query=query,
        depth="deep",
        output_type="structured",
        schema=schema,
    )
    return raw


def _extract_competitors_list(raw: dict) -> list[dict]:
    """Parse competitors[] from either /research ({output:{data:{competitors:[]}}})
    or /search ({data:{competitors:[]}}) response shape."""
    if not isinstance(raw, dict):
        return []
    output = raw.get("output")
    data = None
    if isinstance(output, dict):
        data = output.get("data") or output
    else:
        data = raw.get("data") or raw.get("answer") or raw
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, dict):
        return []
    items = data.get("competitors", [])
    return items if isinstance(items, list) else []


def _extract_sources_urls(raw: dict) -> list[str]:
    if not isinstance(raw, dict):
        return []
    sources = []
    output = raw.get("output")
    if isinstance(output, dict):
        sources = output.get("sources") or []
    if not sources:
        sources = raw.get("sources") or []
    urls: list[str] = []
    seen: set[str] = set()
    for s in sources:
        if isinstance(s, dict):
            u = s.get("url")
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def _index_by_key(items: list[dict]) -> dict[str, dict]:
    """Index items by both normalized name and normalized domain for matching."""
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
    return by_key


# ── Aggregation: merge 5 raw outputs into one CompetitorProfile per competitor

def _aggregate_lanes(
    competitors: list[dict],
    lane1_raw,
    lane2_raw,
    lane3_raw,
    lane4_raw,
    lane5_raw,
    run_id: str,
    now: str,
    coords_map: dict[int, tuple],
) -> list[CompetitorProfile]:
    """Merge 5 lane outputs into per-competitor CompetitorProfile.

    Lane failures (exceptions or empty) degrade gracefully — fields from other
    lanes still populate the profile.
    """
    def _safe_items(raw) -> list[dict]:
        if isinstance(raw, Exception):
            logger.warning("lane failed with exception: %s", raw)
            return []
        return _extract_competitors_list(raw)

    items1 = _index_by_key(_safe_items(lane1_raw))
    items2 = _index_by_key(_safe_items(lane2_raw))
    items3 = _index_by_key(_safe_items(lane3_raw))
    items4 = _index_by_key(_safe_items(lane4_raw))
    items5 = _index_by_key(_safe_items(lane5_raw))

    # Shared features from lane 5 (run-level)
    features_raw: list[dict] = []
    if not isinstance(lane5_raw, Exception) and isinstance(lane5_raw, dict):
        output5 = lane5_raw.get("output") or lane5_raw
        data5 = output5.get("data") if isinstance(output5, dict) else None
        data5 = data5 or output5 if isinstance(output5, dict) else {}
        if isinstance(data5, dict):
            features_raw = data5.get("features") or []
    shared_features = [
        Feature(label=f.get("label", ""), group=f.get("group"))
        for f in features_raw
        if isinstance(f, dict) and f.get("label")
    ]

    # All-lanes source URLs dedup
    all_sources: list[str] = []
    seen_src: set[str] = set()
    for raw in (lane1_raw, lane2_raw, lane3_raw, lane4_raw, lane5_raw):
        if isinstance(raw, Exception):
            continue
        for u in _extract_sources_urls(raw):
            if u not in seen_src:
                seen_src.add(u)
                all_sources.append(u)

    profiles: list[CompetitorProfile] = []
    for i, c in enumerate(competitors):
        kn = _normalize_name_key(c.get("name", ""))
        kw = normalize_domain(c.get("website", ""))

        def _lookup(idx: dict) -> dict:
            return idx.get(kn) or idx.get(kw) or {}

        l1 = _lookup(items1)
        l2 = _lookup(items2)
        l3 = _lookup(items3)
        l4 = _lookup(items4)
        l5 = _lookup(items5)

        profile = _merge_one_competitor(
            c, l1, l2, l3, l4, l5,
            shared_features, all_sources,
            run_id, now, coords_map.get(i),
        )
        profiles.append(profile)
    return profiles


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _strip_md_links(s):
    """Drop markdown citations [source title](url) entirely; collapse whitespace.

    LLM pricing output appends citation links to structured field values
    (e.g. "Subscription [ITQlick](http…)"). The bracketed text is the source
    title, not part of the value, so the whole link is removed. No-op on
    None / non-str."""
    if not isinstance(s, str):
        return s
    cleaned = _MD_LINK_RE.sub("", s)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(" .,;|-").strip()


def _dp_or_none(value, confidence: str, now: str) -> Optional[DataPoint]:
    value = _strip_md_links(value)
    if value is None or value == "":
        return None
    return DataPoint(value=value, confidence=confidence, extracted_at=now)


def _filter_real_keypeople(raw_people: list[dict], company_name: str) -> list[KeyPerson]:
    """Drop null/placeholder padding + external partners (mirror of eval filter)."""
    out: list[KeyPerson] = []
    name = (company_name or "").lower()
    company_slug = name.split()[0] if name else ""
    for p in raw_people or []:
        if not isinstance(p, dict):
            continue
        pname = p.get("name")
        plinkedin = p.get("linkedin") or ""
        if not pname or pname == "null" or str(pname).lower() == "none":
            continue
        if plinkedin and ("placeholder" in plinkedin.lower() or plinkedin == "null"):
            plinkedin = None  # keep the person but drop the bad URL
        # External marker check
        bg = (p.get("background") or "").lower()
        role = (p.get("role") or "").lower()
        haystack = f"{role} {bg}"
        if haystack.strip() and name:
            external = ("partner at " in haystack or "speaker at " in haystack
                        or "advisor at " in haystack or "consultant" in haystack)
            mentions = name in haystack or (company_slug and company_slug in haystack)
            if external and not mentions:
                continue
            if not mentions:
                continue
        out.append(KeyPerson(
            name=pname,
            role=p.get("role"),
            background=p.get("background"),
            linkedin=plinkedin or None,
        ))
    return out


def _merge_one_competitor(
    competitor: dict,
    l1: dict, l2: dict, l3: dict, l4: dict, l5: dict,
    shared_features: list[Feature],
    all_sources: list[str],
    run_id: str,
    now: str,
    coords,
) -> CompetitorProfile:
    """Combine the 5 lane outputs into one CompetitorProfile."""
    name = l1.get("name") or l3.get("name") or competitor.get("name", "")
    website = l1.get("website") or competitor.get("website", "")

    # ── HQ + geocoding ────────────────────────────────────────────
    hq = None
    city = l1.get("hq_city") or competitor.get("hq_city")
    country = l1.get("hq_country") or competitor.get("hq_country")
    if city or country:
        hq = HQ(
            city=city,
            country=country,
            lat=coords[0] if isinstance(coords, tuple) else None,
            lng=coords[1] if isinstance(coords, tuple) else None,
        )

    # ── Funding history (lane 1) ──────────────────────────────────
    rounds = []
    for r in (l1.get("funding_rounds") or []):
        if not isinstance(r, dict):
            continue
        amt_usd = r.get("amount_usd")
        amt_eur = int(amt_usd * 0.92) if isinstance(amt_usd, (int, float)) else None
        rounds.append(FundingRound(
            round=r.get("round"),
            amount_eur=amt_eur,
            date=r.get("date"),
            lead=r.get("lead"),
        ))
    funding_obj = None
    funding_total_usd = l1.get("funding_total_usd")
    funding_total_eur = int(funding_total_usd * 0.92) if isinstance(funding_total_usd, (int, float)) else None
    total_raised_dp = _dp_or_none(funding_total_eur, "high", now)
    if rounds or total_raised_dp or l1.get("last_round_type"):
        funding_obj = Funding(
            total_raised_eur=total_raised_dp,
            last_round=l1.get("last_round_type"),
            last_round_date=l1.get("last_round_date"),
            rounds=rounds,
        )

    notable_investors = [
        Investor(name=i.get("name", ""), domain=i.get("domain"))
        for i in (l1.get("notable_investors") or [])
        if isinstance(i, dict) and i.get("name")
    ]

    # ── Acquisition ───────────────────────────────────────────────
    acq_raw = l1.get("acquisition") or {}
    acquisition = None
    if isinstance(acq_raw, dict) and acq_raw:
        acquisition = AcquisitionInfo(
            acquired=acq_raw.get("acquired", False),
            acquirer=acq_raw.get("acquirer"),
            amount_eur=acq_raw.get("amount_eur"),
            year=acq_raw.get("year"),
            source_url=acq_raw.get("source_url"),
        )

    # ── Pricing (lane 2) ──────────────────────────────────────────
    tiers = [
        PricingTier(
            name=_strip_md_links(t.get("name")),
            price_monthly_usd=t.get("price_monthly_usd"),
            price_annual_usd=t.get("price_annual_usd"),
            features=[_strip_md_links(f) for f in (t.get("features") or [])],
            target=_strip_md_links(t.get("target")),
        )
        for t in (l2.get("tiers") or [])
        if isinstance(t, dict)
    ]
    pricing_signal = None
    if tiers or l2.get("free_plan") is not None or l2.get("mention"):
        pricing_signal = PricingSignal(
            tiers=tiers,
            free_plan=l2.get("free_plan"),
            mention=_strip_md_links(l2.get("mention")),
            starts_at_usd=l2.get("starts_at_usd"),
            recent_changes=l2.get("recent_changes"),
            source_url=all_sources[0] if all_sources else None,
            extracted_at=now,
        )

    # ── LinkedIn (lane 3) ─────────────────────────────────────────
    key_people = _filter_real_keypeople(l3.get("key_people") or [], name)
    linkedin_signals = [
        LinkedInSignal(
            date=s.get("date"),
            author=s.get("author"),
            signal=s.get("signal", ""),
            excerpt=s.get("excerpt"),
            image_url=s.get("image_url"),
            source_url=s.get("source_url"),
        )
        for s in (l3.get("recent_linkedin_signals") or [])
        if isinstance(s, dict) and (s.get("signal") or s.get("excerpt"))
    ]
    linkedin_url = l3.get("linkedin_url")
    founder_linkedin_urls = [p.linkedin for p in key_people if p.linkedin]

    # ── News + GTM (lane 4) ───────────────────────────────────────
    structured_signals = [
        RecentSignal(
            date=s.get("date"),
            headline=s.get("headline", ""),
            source_url=s.get("source_url"),
            type=s.get("type"),
        )
        for s in (l4.get("recent_signals") or [])
        if isinstance(s, dict) and s.get("headline")
    ]
    business_model_dp = _dp_or_none(l4.get("business_model"), "high", now)
    gtm_motion_dp = _dp_or_none(l4.get("gtm_motion"), "high", now)
    geo_coverage = l4.get("geo_coverage")

    # ── Features + capabilities + customers (lane 5) ──────────────
    capabilities_raw = l5.get("capabilities") or []
    valid_caps = {"full", "part", "none", "soon"}
    capabilities = [
        CapabilityCell(feature=c.get("feature", ""), value=c.get("value", "none"))
        for c in capabilities_raw
        if isinstance(c, dict) and c.get("feature") and c.get("value") in valid_caps
    ]

    notable_customers = [
        CustomerExample(
            name=c.get("name", ""),
            domain=c.get("domain"),
            segment=_norm_segment(c.get("segment")),
            industry=c.get("industry"),
            evidence=c.get("evidence"),
        )
        for c in (l5.get("notable_customers") or [])
        if isinstance(c, dict) and c.get("name")
    ]

    # ── Pricing model kind (lane 2) ───────────────────────────────
    pricing_model_kind_dp = _dp_or_none(l2.get("pricing_model_kind"), "high", now)

    # ── Funding stage ─────────────────────────────────────────────
    funding_stage_dp = _dp_or_none(l1.get("funding_stage"), "high", now)
    if funding_stage_dp is None and competitor.get("funding_stage"):
        funding_stage_dp = DataPoint(value=competitor["funding_stage"], confidence="medium", extracted_at=now)
    # F2: LLM-emitted funding_status overrides stage when it carries posture info.
    # "Bootstrapped"/"Stealth" are mutually exclusive with numeric stages — prefer them.
    funding_status_raw = l1.get("funding_status")
    if funding_status_raw in ("Bootstrapped", "Stealth"):
        funding_stage_dp = DataPoint(value=funding_status_raw, confidence="high", extracted_at=now)

    # ── Employee count ────────────────────────────────────────────
    employee_count_dp = _dp_or_none(l1.get("employee_count"), "medium", now)
    arr_dp = _dp_or_none(l1.get("arr_usd"), "high", now)
    customer_count_dp = _dp_or_none(l1.get("customer_count"), "high", now)

    # ── Differentiators / weaknesses (lane 4) ─────────────────────
    differentiators = l4.get("key_differentiators") or []
    weaknesses = l4.get("weaknesses") or []
    one_liner = l4.get("one_liner") or competitor.get("one_liner")

    return CompetitorProfile(
        name=name,
        website=website,
        hq=hq,
        founded_year=l1.get("founded_year") or competitor.get("founded_year"),
        funding_stage=funding_stage_dp,
        funding_total_usd=l1.get("funding_total_usd"),
        last_round_amount_usd=l1.get("last_round_amount_usd"),
        last_round_date=l1.get("last_round_date"),
        last_round_type=l1.get("last_round_type"),
        key_investors=[i.name for i in notable_investors],  # legacy mirror
        notable_investors=notable_investors,
        funding=funding_obj,
        acquisition=acquisition,
        employee_count=employee_count_dp,
        employee_growth_yoy=l1.get("employee_growth_yoy"),
        key_people=key_people,
        arr_usd=arr_dp,
        customer_count=customer_count_dp,
        avg_contract_usd=l1.get("avg_contract_usd"),
        one_liner=one_liner,
        differentiator=differentiators[0] if differentiators else None,
        key_differentiators=differentiators,
        target_segment=_norm_segment(l4.get("target_segment")),
        notable_customers=notable_customers,
        weaknesses=weaknesses,
        business_model=business_model_dp,
        gtm_motion=gtm_motion_dp,
        pricing_model_kind=pricing_model_kind_dp,
        geo_coverage=geo_coverage,
        pricing=pricing_signal,
        features=shared_features,
        capabilities=capabilities,
        recent_signals=[s.headline for s in structured_signals][:5],
        structured_signals=structured_signals,
        linkedin_url=linkedin_url,
        founder_linkedin_urls=founder_linkedin_urls,
        recent_linkedin_signals=linkedin_signals,
        source_urls=all_sources,
        pipeline_run_id=run_id,
    )


# ═════════════════════════════════════════════════════════════════════════════


def _persist_raw_lanes(run_id: str, domain: Optional[str], lanes: list[tuple]) -> None:
    """Serialize (lane_name, query, raw) tuples and hand them to the cache layer.

    `raw` may be an Exception (asyncio.gather return_exceptions=True) — store it
    as an error marker rather than dropping it, so a failed-but-billed lane is
    still accounted for. Never raises: this is the safety net, not a gate.
    """
    try:
        payload = []
        for lane_name, query, raw in lanes:
            if isinstance(raw, Exception):
                payload.append({
                    "lane": lane_name, "query": query,
                    "raw": None, "is_error": True, "error": str(raw),
                })
            else:
                payload.append({
                    "lane": lane_name, "query": query,
                    "raw": raw, "is_error": False,
                })
        from utils import cache_set_raw_lanes
        cache_set_raw_lanes(run_id, domain, payload)
    except Exception as e:  # belt + suspenders — capture must never break a scan
        logger.error("raw lanes capture failed run_id=%s: %s", run_id, e, exc_info=True)


async def run(
    competitors: list[dict],
    linkup: LinkupClient,
    run_id: str,
    event_cb=None,
    subject: dict | None = None,
    byok: bool = False,
    domain: str | None = None,
) -> list[CompetitorProfile]:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()

    if not competitors:
        return []

    # ── 5-lanes mode (default) ────────────────────────────────────
    if ENRICH_MODE == "5_lanes":
        # 4 × /research depth=M + 1 × /search deep = 4 × €0.50 + €0.055 = €2.055
        estimated = 4 * RESEARCH_COST_EUR + 0.055
        # BYOK: a tester's own-key spend is theirs — don't gate it on our daily
        # cap nor read our ledger for it.
        if not byok:
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

        logger.info(
            "phase=ENRICH mode=5_lanes status=start total=%d depth=%s estimated_eur=%.2f",
            len(competitors), DEPTH_LANE, estimated,
        )

        coords_task = asyncio.create_task(_geocode_all(competitors))

        # Build queries up-front so we can persist them alongside their raw
        # responses (the "calls I launched" + "the data I got back").
        q1 = _lane1_query(competitors)
        q2 = _lane2_query(competitors)
        q3 = _lane3_query(competitors)
        q4 = _lane4_query(competitors)
        q5 = _lane5_query(competitors, subject)

        lane1_raw, lane2_raw, lane3_raw, lane4_raw, lane5_raw = await asyncio.gather(
            _run_research_lane("identity_funding", competitors, q1, LANE1_SCHEMA, linkup, event_cb),
            _run_research_lane("pricing", competitors, q2, LANE2_SCHEMA, linkup, event_cb),
            _run_search_lane("linkedin", competitors, q3, LANE3_SCHEMA, linkup, event_cb),
            _run_research_lane("news_gtm", competitors, q4, LANE4_SCHEMA, linkup, event_cb),
            _run_research_lane("features", competitors, q5, LANE5_SCHEMA, linkup, event_cb),
            return_exceptions=True,
        )

        # ── STOP THE SILENCE — a lane that raised is swallowed by
        # return_exceptions=True and degrades to empty data downstream, which is
        # indistinguishable from "genuinely no data". Surface failed lanes loudly
        # (ERROR log + SSE event) so a paid-but-empty lane is never silent. ──
        _lane_results = [
            ("identity_funding", lane1_raw), ("pricing", lane2_raw),
            ("linkedin", lane3_raw), ("news_gtm", lane4_raw), ("features", lane5_raw),
        ]
        failed_lanes = [name for name, raw in _lane_results if isinstance(raw, Exception)]
        if failed_lanes:
            for name, raw in _lane_results:
                if isinstance(raw, Exception):
                    logger.error(
                        "phase=ENRICH lane=%s FAILED run_id=%s error=%s",
                        name, run_id, raw, exc_info=raw,
                    )
            if event_cb:
                await event_cb({
                    "phase": "ENRICH", "status": "lane_errors",
                    "failed_lanes": failed_lanes,
                    "detail": f"{len(failed_lanes)}/5 enrichment lanes failed — "
                              "some competitor data unavailable (not 'not found').",
                })

        # ── CAPTURE RAW NOW — Linkup has already billed. Persist before any
        # fragile parsing/synthesis downstream can lose the paid data. Wrapped
        # so a capture failure can never crash the scan it is protecting. ──
        _persist_raw_lanes(
            run_id, domain,
            [
                ("identity_funding", q1, lane1_raw),
                ("pricing", q2, lane2_raw),
                ("linkedin", q3, lane3_raw),
                ("news_gtm", q4, lane4_raw),
                ("features", q5, lane5_raw),
            ],
        )

        coords_map = await coords_task

        profiles = _aggregate_lanes(
            competitors, lane1_raw, lane2_raw, lane3_raw, lane4_raw, lane5_raw,
            run_id, now, coords_map,
        )

        await _fill_missing_coords(profiles)

        if event_cb:
            await event_cb({
                "phase": "ENRICH",
                "status": "batch_complete",
                "count": len(profiles),
                "mode": "5_lanes",
            })
        logger.info(
            "phase=ENRICH mode=5_lanes status=ok total=%d duration=%.1fs",
            len(profiles), time.monotonic() - t0,
        )
        return profiles

    # ── Batched mode ──────────────────────────────────────────────
    if ENRICH_MODE == "batched":
        logger.info(
            "phase=ENRICH mode=batched status=start total=%d depth=%s",
            len(competitors), DEPTH_BATCH,
        )
        estimated = RESEARCH_COST_EUR
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

        await _fill_missing_coords(profiles)

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
        estimated = len(to_enrich) * RESEARCH_COST_EUR
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

    await _fill_missing_coords(profiles)

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
