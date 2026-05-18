"""Probe script — compare Linkup strategies for the UNDERSTAND phase.

Usage:
    cd /Users/paul.pietra/Dev/GATRA/RADAR/radar/backend
    source .venv/bin/activate
    python3 -m evals.probe_understand linear.app
    python3 -m evals.probe_understand linear.app --strategies search-std,search-deep
    python3 -m evals.probe_understand linear.app --all

Strategies:
    search-std   linkup.search depth=standard + enriched schema  (baseline)
    search-deep  linkup.search depth=deep + enriched schema
    fetch-claude linkup.fetch homepage -> Claude extracts CompanyProfile

Results cached in cache/probe_{domain}_{strategy}_{date}.json to avoid re-billing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from clients.claude_client import ClaudeClient
from clients.linkup_client import LinkupClient
from models.company import CompanyProfile, DataPoint, Funding, HQ, Market
from pipeline.understand import run as understand_run

logging.basicConfig(level=logging.WARNING)

# ── cache helpers ────────────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


def _cache_path(domain: str, strategy: str) -> Path:
    key = f"probe_{domain.replace('/', '_')}_{strategy}_{date.today()}.json"
    return _CACHE_DIR / key


def _cache_load(domain: str, strategy: str) -> Optional[dict]:
    p = _cache_path(domain, strategy)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _cache_save(domain: str, strategy: str, data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(domain, strategy).write_text(json.dumps(data, indent=2, default=str))


# ── strategies ───────────────────────────────────────────────────────────────
async def _run_search_std(domain: str, linkup: LinkupClient, _: ClaudeClient) -> CompanyProfile:
    return await understand_run(domain, linkup, depth="standard")


async def _run_search_deep(domain: str, linkup: LinkupClient, _: ClaudeClient) -> CompanyProfile:
    return await understand_run(domain, linkup, depth="deep")


async def _run_fetch_claude(domain: str, linkup: LinkupClient, claude: ClaudeClient) -> CompanyProfile:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    raw = await linkup.fetch(f"https://{domain}", render_js=True)
    content = raw.get("content") or raw.get("text") or raw.get("answer") or json.dumps(raw)

    system = (
        "You are a company analyst. Extract a structured company profile from webpage content. "
        "Return ONLY valid JSON with null for unknown fields. "
        "Fields: name, summary, founded_year, hq_city, hq_country, employees (int), "
        "geo_coverage (Local/National/Regional/Global), "
        "funding_total_eur (int), funding_last_round, positioning, "
        "target_segment (Enterprise/Mid-Market/SMB/Consumer/Mixed), "
        "business_model (B2B/B2C/B2B2C/Marketplace/API-Platform), "
        "gtm_motion (sales-led/product-led/marketing-led/community-led), "
        "pricing_model (Freemium/Subscription/Usage-based/Enterprise/Hybrid), "
        "key_differentiator (string, 20 words max), "
        "notable_customers (array of strings), "
        "tech_stack (array of strings, max 10 — e.g. AWS, Stripe, Segment, Vercel), "
        "growth_signals (array of strings), "
        "markets (array of {id, label, primary})"
    )
    user = f"Domain: {domain}\n\nWebpage content:\n{str(content)[:8000]}"

    try:
        data = claude.extract_json(system=system, user=user, max_tokens=2048)
    except Exception as e:
        print(f"  [fetch-claude] Claude parse failed: {e}")
        data = {}

    def _dp(value) -> Optional[DataPoint]:
        if value is None:
            return None
        return DataPoint(value=value, confidence="low", extracted_at=now)

    hq = None
    if data.get("hq_city") or data.get("hq_country"):
        hq = HQ(city=data.get("hq_city"), country=data.get("hq_country"))

    funding = None
    if data.get("funding_total_eur") or data.get("funding_last_round"):
        funding = Funding(
            total_raised_eur=_dp(data.get("funding_total_eur")),
            last_round=data.get("funding_last_round"),
        )

    markets = [
        Market(
            id=m.get("id", m.get("label", "").lower().replace(" ", "_")),
            label=m.get("label", ""),
            primary=m.get("primary", False),
        )
        for m in (data.get("markets") or [])
    ]

    return CompanyProfile(
        name=data.get("name") or domain,
        domain=domain,
        summary=data.get("summary"),
        founded_year=data.get("founded_year"),
        hq=hq,
        geo_coverage=data.get("geo_coverage"),
        employees=_dp(data.get("employees")),
        funding=funding,
        positioning=data.get("positioning"),
        target_segment=_dp(data.get("target_segment")),
        business_model=_dp(data.get("business_model")),
        gtm_motion=_dp(data.get("gtm_motion")),
        pricing_model=_dp(data.get("pricing_model")),
        key_differentiator=_dp(data.get("key_differentiator")),
        notable_customers=data.get("notable_customers") or [],
        tech_stack=data.get("tech_stack") or [],
        growth_signals=data.get("growth_signals") or [],
        markets=markets,
        pipeline_run_id="probe-fetch",
    )


STRATEGIES: dict[str, any] = {
    "search-std": _run_search_std,
    "search-deep": _run_search_deep,
    "fetch-claude": _run_fetch_claude,
}


# ── field extraction ─────────────────────────────────────────────────────────
def _field_summary(profile: CompanyProfile) -> dict[str, str]:
    def _trunc(v, n=28) -> str:
        s = str(v)
        return s[:n] + "…" if len(s) > n else s

    def _dp_val(dp: Optional[DataPoint]) -> str:
        if dp and dp.value is not None:
            return _trunc(dp.value)
        return "null"

    def _dp_conf(dp: Optional[DataPoint]) -> str:
        return dp.confidence if dp and dp.value is not None else "—"

    f = {}
    # Identity
    f["name"]           = profile.name or "null"
    f["website"]        = profile.website or "null"
    f["summary"]        = f"({len(profile.summary)} chars)" if profile.summary else "null"
    f["founded_year"]   = str(profile.founded_year) if profile.founded_year else "null"
    # Location
    f["hq.city"]        = profile.hq.city if profile.hq and profile.hq.city else "null"
    f["hq.country"]     = profile.hq.country if profile.hq and profile.hq.country else "null"
    f["geo_coverage"]   = profile.geo_coverage or "null"
    f["employees"]      = _dp_val(profile.employees)
    f["employees.conf"] = _dp_conf(profile.employees)
    # Funding
    f["funding.total"]  = _dp_val(profile.funding.total_raised_eur) if profile.funding else "null"
    f["funding.stage"]  = profile.funding_stage or "null"
    f["funding.round"]  = profile.funding.last_round if profile.funding and profile.funding.last_round else "null"
    f["funding.rounds#"]= str(len(profile.funding.rounds)) if profile.funding else "0"
    f["investors#"]     = str(len(profile.notable_investors))
    # Product
    f["positioning"]    = f"({len(profile.positioning)} chars)" if profile.positioning else "null"
    f["markets#"]       = str(len(profile.markets))
    f["target_segment"] = _dp_val(profile.target_segment)
    f["verticals#"]     = str(len(profile.target_verticals))
    f["business_model"] = _dp_val(profile.business_model)
    f["gtm_motion"]     = _dp_val(profile.gtm_motion)
    f["pricing_model"]  = _dp_val(profile.pricing_model)
    # Differentiation
    f["differentiator"] = _dp_val(profile.key_differentiator)
    f["top_features#"]  = str(len(profile.top_3_features))
    f["customers#"]     = str(len(profile.notable_customers))
    f["tech_stack#"]    = str(len(profile.tech_stack))
    # Team & signals
    f["key_people#"]    = str(len(profile.key_people))
    f["growth_signals#"]= str(len(profile.growth_signals))
    f["recent_news#"]   = str(len(profile.recent_news))
    return f


def _fill_score(fields: dict[str, str]) -> int:
    return sum(1 for v in fields.values() if v not in ("null", "0", "—"))


def _icon(v: str) -> str:
    return "✗" if v in ("null", "0", "—") else "✓"


# ── display ──────────────────────────────────────────────────────────────────
def _print_table(domain: str, results: dict[str, tuple[dict, float]]) -> None:
    strategies = list(results.keys())
    all_fields = list(next(iter(results.values()))[0].keys())

    col_w = max(22, max(len(s) for s in strategies) + 2)
    field_w = 18
    sep = "─" * (field_w + col_w * len(strategies))

    print(f"\nDomain: {domain}")
    print(sep)
    print(f"{'Field':<{field_w}}" + "".join(f"{s:<{col_w}}" for s in strategies))
    print(sep)

    for field in all_fields:
        row = f"{field:<{field_w}}"
        for s in strategies:
            fields, _ = results[s]
            v = fields.get(field, "null")
            cell = f"{_icon(v)} {v}"
            row += f"{cell:<{col_w}}"
        print(row)

    print(sep)
    score_row = f"{'Fill score':<{field_w}}"
    for s in strategies:
        fields, duration = results[s]
        score = _fill_score(fields)
        total = len(all_fields)
        cell = f"{score}/{total} ({int(score/total*100)}%)"
        score_row += f"{cell:<{col_w}}"
    print(score_row)

    dur_row = f"{'Duration':<{field_w}}"
    for s in strategies:
        _, duration = results[s]
        cell = f"{duration:.1f}s"
        dur_row += f"{cell:<{col_w}}"
    print(dur_row)
    print()


# ── main ─────────────────────────────────────────────────────────────────────
async def probe(domain: str, strategy_names: list[str]) -> None:
    linkup = LinkupClient()
    claude = ClaudeClient()
    results: dict[str, tuple[dict, float]] = {}

    for name in strategy_names:
        fn = STRATEGIES[name]
        cached = _cache_load(domain, name)
        if cached:
            print(f"  [{name}] cache hit")
            profile = CompanyProfile.model_validate(cached["profile"])
            duration = cached.get("duration", 0.0)
        else:
            print(f"  [{name}] calling Linkup…")
            t0 = time.monotonic()
            try:
                profile = await fn(domain, linkup, claude)
            except Exception as e:
                print(f"  [{name}] ERROR: {e}")
                continue
            duration = time.monotonic() - t0
            _cache_save(domain, name, {
                "profile": profile.model_dump(mode="json"),
                "duration": duration,
            })

        results[name] = (_field_summary(profile), duration)

    if results:
        _print_table(domain, results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Linkup strategies for understand phase")
    parser.add_argument("domain", help="Domain to analyze (e.g. linear.app)")
    parser.add_argument(
        "--strategies",
        default="search-std",
        help="Comma-separated: search-std,search-deep,fetch-claude  (default: search-std)",
    )
    parser.add_argument("--all", dest="all_strategies", action="store_true",
                        help="Run all 3 strategies")
    args = parser.parse_args()

    domain = args.domain.strip().lower()

    if args.all_strategies:
        strategy_names = list(STRATEGIES.keys())
    else:
        strategy_names = [s.strip() for s in args.strategies.split(",")]
        invalid = [s for s in strategy_names if s not in STRATEGIES]
        if invalid:
            print(f"Unknown strategies: {invalid}. Valid: {list(STRATEGIES.keys())}")
            sys.exit(1)

    asyncio.run(probe(domain, strategy_names))


if __name__ == "__main__":
    main()
