"""POC — Linkup /v1/research endpoint test.

Compare Research (Investigate) vs current enrich approach on a known competitor.
Supports both sourcedAnswer (text) and structured (JSON schema) output.

Usage:
    cd /Users/paul.pietra/Dev/GATRA/radar/backend
    source .venv/bin/activate
    python3 -m evals.poc_research linear.app
    python3 -m evals.poc_research linear.app --structured
    python3 -m evals.poc_research notion.so --structured --depth S
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from clients.linkup_client import LinkupClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

COST_BY_DEPTH = {"S": 0.25, "M": 0.50, "L": 1.50, "XL": 2.50}
POLL_INTERVAL = 10

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


def _build_query(name: str, domain: str) -> str:
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


async def run_research(domain: str, depth: str = "S", structured: bool = False) -> None:
    client = LinkupClient()

    name = domain.split(".")[0].capitalize()
    query = _build_query(name, domain)
    output_type = "structured" if structured else "sourcedAnswer"

    print(f"\n{'='*60}")
    print(f"TARGET       : {domain}")
    print("ENDPOINT     : POST /v1/research")
    print("MODE         : Investigate")
    print(f"DEPTH        : {depth}  (est. ${COST_BY_DEPTH.get(depth, '?')} / {_depth_eta(depth)})")
    print(f"OUTPUT TYPE  : {output_type}")
    print(f"QUERY        : {query[:120]}...")
    print(f"{'='*60}\n")

    t0 = time.monotonic()

    body: dict = {
        "q": query,
        "mode": "Investigate",
        "depth": depth,
        "outputType": output_type,
    }
    if structured:
        body["structuredOutputSchema"] = json.dumps(COMPETITOR_SCHEMA)

    submit_resp = await client._post("/research", body)
    task_id = submit_resp.get("id")
    if not task_id:
        print(f"ERROR: no task_id in response: {submit_resp}")
        return

    print(f"Task submitted → id={task_id}")
    print(f"Polling every {POLL_INTERVAL}s ...\n")

    elapsed = 0
    timeout = 600
    result = None
    while elapsed < timeout:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        status_resp = await client._get(f"/research/{task_id}")
        status = status_resp.get("status", "unknown")
        print(f"  [{elapsed:>4}s] status={status}")

        if status == "completed":
            result = status_resp
            break
        if status == "failed":
            print(f"\nFAILED: {status_resp}")
            return

    total = time.monotonic() - t0
    if not result:
        print(f"\nTIMEOUT after {timeout}s")
        return

    output = result.get("output", {})

    print(f"\n{'='*60}")
    print(f"COMPLETED in {total:.1f}s")
    print(f"{'='*60}\n")

    if structured:
        # For structured output, show the parsed JSON data
        data = output.get("data") or output
        sources = output.get("sources", [])
        print("--- STRUCTURED DATA ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # Field completeness check
        print("\n--- FIELD COMPLETENESS ---")
        top_fields = [
            "name", "website", "linkedin_url", "hq_city", "founded_year",
            "employee_count", "funding_stage", "funding_total_usd",
            "one_liner", "key_differentiators", "pricing",
            "founder_linkedin_urls", "recent_linkedin_signals", "recent_signals", "weaknesses",
        ]
        for f in top_fields:
            val = data.get(f)
            filled = "✓" if val not in (None, [], {}, "") else "✗"
            print(f"  {filled} {f}: {str(val)[:80] if val else 'MISSING'}")

        print(f"\n  Sources: {len(sources)}")

        # Pricing tiers summary
        pricing = data.get("pricing") or {}
        tiers = pricing.get("tiers", [])
        print(f"\n--- PRICING ({len(tiers)} tiers) ---")
        for t in tiers:
            print(f"  {t.get('name')} — ${t.get('price_monthly_usd')}/mo · ${t.get('price_annual_usd')}/yr")

        # LinkedIn signals
        li_signals = data.get("recent_linkedin_signals", [])
        print(f"\n--- LINKEDIN SIGNALS ({len(li_signals)}) ---")
        for s in li_signals:
            print(f"  [{s.get('date')}] {s.get('author')} — {s.get('signal', '')[:100]}")

    else:
        answer = output.get("answer", "")
        sources = output.get("sources", [])
        print(f"SOURCES: {len(sources)}")
        print("\n--- ANSWER ---")
        print(answer)

        print(f"\n--- SOURCES ({len(sources)}) ---")
        for i, s in enumerate(sources, 1):
            url = s.get("url", "")
            name_s = s.get("name", "")
            snippet = s.get("snippet", "")[:120]
            print(f"  [{i:2}] {url}")
            print(f"       {name_s} — {snippet}")

        from urllib.parse import urlparse
        source_domains: dict[str, int] = {}
        for s in sources:
            d = urlparse(s.get("url", "")).netloc.lstrip("www.")
            source_domains[d] = source_domains.get(d, 0) + 1

        print("\n--- SOURCE DOMAIN BREAKDOWN ---")
        for domain_s, count in sorted(source_domains.items(), key=lambda x: -x[1]):
            print(f"  {count:2}x  {domain_s}")

    print("\n--- SUMMARY ---")
    print(f"  Latency       : {total:.1f}s")
    print(f"  Est. cost     : ${COST_BY_DEPTH.get(depth, '?')}")
    print(f"  Output type   : {output_type}")

    suffix = "structured" if structured else "text"
    out_path = f"/tmp/poc_research_{domain}_{depth}_{suffix}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nRaw output saved → {out_path}")


def _depth_eta(depth: str) -> str:
    return {"S": "2-5 min", "M": "3-7 min", "L": "5-10 min", "XL": "10-20 min"}.get(depth, "?")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="POC: Linkup Research endpoint")
    parser.add_argument("domain", help="Competitor domain (e.g. notion.so)")
    parser.add_argument("--depth", default="S", choices=["S", "M", "L", "XL"])
    parser.add_argument("--structured", action="store_true", help="Use structured JSON output instead of text")
    args = parser.parse_args()
    asyncio.run(run_research(args.domain, args.depth, args.structured))
