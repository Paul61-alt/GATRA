"""Probe script — test DISCOVER + ENRICH phases using a cached UNDERSTAND profile.

Usage:
    cd /Users/paul.pietra/Dev/GATRA/RADAR/radar/backend
    source .venv/bin/activate

    # Use a cached understand profile (default strategy: fetch-claude)
    python3 -m evals.probe_post_understand doctolib.fr

    # Specify which understand cache to load from
    python3 -m evals.probe_post_understand doctolib.fr --from search-std
    python3 -m evals.probe_post_understand doctolib.fr --from fetch-claude

    # Force re-run (ignore discover/enrich cache)
    python3 -m evals.probe_post_understand doctolib.fr --force

Cache files:
    cache/probe_{domain}_{strategy}_{date}.json        — UNDERSTAND (read-only)
    cache/probe_{domain}_discover_{date}.json          — DISCOVER output
    cache/probe_{domain}_enrich_{date}.json            — ENRICH output
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

from clients.linkup_client import LinkupClient
from models.company import CompanyProfile
from models.competitor import CompetitorProfile
from pipeline.discover import run as discover_run
from pipeline.enrich import run as enrich_run

logging.basicConfig(level=logging.WARNING)

_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


# ── cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(domain: str, key: str) -> Path:
    filename = f"probe_{domain.replace('/', '_')}_{key}_{date.today()}.json"
    return _CACHE_DIR / filename


def _cache_load(domain: str, key: str) -> Optional[dict]:
    p = _cache_path(domain, key)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _cache_save(domain: str, key: str, data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(domain, key).write_text(json.dumps(data, indent=2, default=str))


def _load_understand_profile(domain: str, strategy: str) -> CompanyProfile:
    """Load CompanyProfile from a probe_understand cache file."""
    cached = _cache_load(domain, strategy)
    if not cached:
        # Try any available file for this domain/strategy (any date)
        pattern = f"probe_{domain.replace('/', '_')}_{strategy}_*.json"
        matches = sorted(_CACHE_DIR.glob(pattern), reverse=True)
        if not matches:
            raise FileNotFoundError(
                f"No UNDERSTAND cache found for domain={domain} strategy={strategy}.\n"
                f"Run first: python3 -m evals.probe_understand {domain} --strategies {strategy}"
            )
        print(f"  [understand] using stale cache: {matches[0].name}")
        cached = json.loads(matches[0].read_text())

    return CompanyProfile.model_validate(cached["profile"])


# ── display helpers ───────────────────────────────────────────────────────────

def _print_separator(title: str = "") -> None:
    sep = "─" * 70
    if title:
        pad = (70 - len(title) - 2) // 2
        print(f"{'─' * pad} {title} {'─' * (70 - pad - len(title) - 2)}")
    else:
        print(sep)


def _print_company_profile(profile: CompanyProfile) -> None:
    _print_separator("UNDERSTAND profile loaded")
    print(f"  name:        {profile.name}")
    print(f"  domain:      {profile.domain}")
    print(f"  positioning: {(profile.positioning or 'null')[:80]}")
    print(f"  markets:     {', '.join(m.label for m in profile.markets) or 'null'}")
    print(f"  segment:     {profile.target_segment.value if profile.target_segment else 'null'}")
    print()


def _print_discover_results(competitors: list[dict], duration: float) -> None:
    _print_separator(f"DISCOVER — {len(competitors)} competitors ({duration:.1f}s)")
    for i, c in enumerate(competitors, 1):
        name = c.get("name", "?")
        website = c.get("website", "—")
        stage = c.get("funding_stage") or "—"
        employees = c.get("employee_count") or "—"
        one_liner = (c.get("one_liner") or "")[:60]
        print(f"  {i:>2}. {name:<25} {website:<30} {stage:<12} {employees}")
        if one_liner:
            print(f"       {one_liner}")
    print()


def _print_enrich_results(profiles: list[CompetitorProfile], duration: float) -> None:
    _print_separator(f"ENRICH — {len(profiles)} profiles ({duration:.1f}s)")
    for p in profiles:
        pricing_src = (
            p.pricing.source_url[:50] if p.pricing and p.pricing.source_url else "no pricing"
        )
        signals_count = len(p.recent_signals)
        print(f"  {p.name:<30} pricing_src={pricing_src}")
        if p.recent_signals:
            for sig in p.recent_signals[:3]:
                print(f"    • {sig[:80]}")
        else:
            print(f"    • (no signals)")
        print()


# ── main probe ────────────────────────────────────────────────────────────────

async def probe(domain: str, understand_strategy: str, force: bool) -> None:
    # ── Step 0: load UNDERSTAND profile ──────────────────────────────────────
    print(f"\nDomain: {domain}  |  UNDERSTAND strategy: {understand_strategy}")
    profile = _load_understand_profile(domain, understand_strategy)
    _print_company_profile(profile)

    # ── Step 1: DISCOVER ──────────────────────────────────────────────────────
    discover_cached = _cache_load(domain, "discover") if not force else None
    if discover_cached:
        print(f"  [discover] cache hit")
        competitors = discover_cached["competitors"]
        discover_duration = discover_cached.get("duration", 0.0)
    else:
        print(f"  [discover] calling Linkup (depth=deep)…")
        linkup = LinkupClient()
        t0 = time.monotonic()
        competitors = await discover_run(profile, linkup)
        discover_duration = time.monotonic() - t0
        _cache_save(domain, "discover", {
            "competitors": competitors,
            "duration": discover_duration,
        })

    _print_discover_results(competitors, discover_duration)

    if not competitors:
        print("  No competitors found — skipping ENRICH.")
        return

    # ── Step 2: ENRICH ────────────────────────────────────────────────────────
    enrich_cached = _cache_load(domain, "enrich") if not force else None
    if enrich_cached:
        print(f"  [enrich] cache hit")
        profiles = [CompetitorProfile.model_validate(p) for p in enrich_cached["profiles"]]
        enrich_duration = enrich_cached.get("duration", 0.0)
    else:
        print(f"  [enrich] calling Linkup ({len(competitors)} competitors × 2 tasks)…")
        linkup = LinkupClient()
        t0 = time.monotonic()
        profiles = await enrich_run(competitors, linkup, run_id="probe-post-understand")
        enrich_duration = time.monotonic() - t0
        _cache_save(domain, "enrich", {
            "profiles": [p.model_dump(mode="json") for p in profiles],
            "duration": enrich_duration,
        })

    _print_enrich_results(profiles, enrich_duration)

    _print_separator("SUMMARY")
    print(f"  Company:     {profile.name}")
    print(f"  Competitors: {len(competitors)} found, {len(profiles)} enriched")
    pricing_ok = sum(1 for p in profiles if p.pricing and p.pricing.source_url)
    signals_ok = sum(1 for p in profiles if p.recent_signals)
    print(f"  Pricing src: {pricing_ok}/{len(profiles)}")
    print(f"  Signals:     {signals_ok}/{len(profiles)}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test DISCOVER + ENRICH from a cached UNDERSTAND profile"
    )
    parser.add_argument("domain", help="Domain (e.g. doctolib.fr)")
    parser.add_argument(
        "--from",
        dest="understand_strategy",
        default="fetch-claude",
        help="Which UNDERSTAND cache to load: search-std, search-deep, fetch-claude (default: fetch-claude)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore DISCOVER/ENRICH cache and re-run (still reuses UNDERSTAND cache)",
    )
    args = parser.parse_args()
    asyncio.run(probe(args.domain.strip().lower(), args.understand_strategy, args.force))


if __name__ == "__main__":
    main()
