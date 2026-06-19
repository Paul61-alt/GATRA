"""POC ENRICH — 4 parallel /research calls with live tracker.

Each competitor gets its own /research depth=M structured call. Progress is
rendered live via rich.live; results are written incrementally to
`evals/eval_enrich_4comp_result.json` as each job completes.

Cost: 4 × $1.50 = ~€5.60.

Usage:
    cd radar/backend && source .venv/bin/activate
    python -m evals.eval_enrich_4comp
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from clients.linkup_client import LinkupClient, RESEARCH_COST_EUR
from utils.linkup_tracker import LinkupTracker

load_dotenv()


# ── Cohort POC ───────────────────────────────────────────────────────────────
COMPETITORS: list[dict] = [
    {"name": "HireVue",     "website": "hirevue.com"},
    {"name": "Paradox",     "website": "paradox.ai"},
    {"name": "Harver",      "website": "harver.com"},
    {"name": "TestGorilla", "website": "testgorilla.com"},
]


# ── Schema (no top-level required[]; descriptions on every field) ────────────
ENRICH_BATCH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "description": "One object per company, same order and exact names as input list",
            "items": {
                "type": "object",
                "properties": {
                    # ── Identity ─────────────────────────────────────────────
                    "name": {
                        "type": "string",
                        "description": "Exact company name from input list — CRITICAL for matching",
                    },
                    "website": {"type": "string", "description": "Company domain"},
                    "tagline": {"type": "string", "description": "One-sentence elevator pitch"},
                    "category": {"type": "string", "description": "Primary market category (e.g. HR Technology)"},
                    "sub_category": {"type": "string", "description": "Specific niche within category"},
                    "linkedin_url": {"type": "string", "description": "linkedin.com/company/<slug>"},
                    "hq_city": {"type": "string"},
                    "hq_country": {"type": "string"},
                    "founded_year": {"type": "integer"},
                    "employee_count": {
                        "type": "integer",
                        "description": "Current count from LinkedIn About",
                    },
                    "employee_growth_yoy": {
                        "type": "number",
                        "description": "Year-over-year change as decimal (0.12 = +12%)",
                    },
                    # ── Positioning ─────────────────────────────────────────
                    "business_model": {
                        "type": "string",
                        "description": "B2B|B2C|B2B2C|Marketplace|API",
                    },
                    "gtm_motion": {
                        "type": "string",
                        "description": "sales-led|product-led|marketing-led|community-led",
                    },
                    "geo_coverage": {
                        "type": "string",
                        "description": "Local|National|Regional|Global",
                    },
                    "target_segment": {
                        "type": "string",
                        "description": "Enterprise|Mid-Market|SMB|Consumer|Mixed",
                    },
                    "target_verticals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-5 industries",
                    },
                    "top_3_features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top 3 product features",
                    },
                    "key_differentiator": {
                        "type": "string",
                        "description": "Single line, max 20 words",
                    },
                    # ── Pricing ─────────────────────────────────────────────
                    "pricing_model_kind": {
                        "type": "string",
                        "description": "Freemium|Subscription|Usage-based|Enterprise|Hybrid",
                    },
                    "pricing": {
                        "type": "object",
                        "properties": {
                            "free_plan": {"type": "boolean"},
                            "starts_at_usd": {
                                "type": "number",
                                "description": "Public starting price USD/month, 0 if custom",
                            },
                            "mention": {
                                "type": "string",
                                "description": "Public pricing mention (e.g. 'From $99/user/month' or 'Contact sales')",
                            },
                            "tiers": {
                                "type": "array",
                                "description": "Omit if no public pricing — do NOT pad with placeholders",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "price_monthly_usd": {"type": "number"},
                                        "price_annual_usd": {"type": "number"},
                                        "target": {"type": "string"},
                                        "features": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            "recent_changes": {"type": "string"},
                        },
                    },
                    # ── Funding ─────────────────────────────────────────────
                    "funding_stage": {
                        "type": "string",
                        "description": "Seed|Series A/B/C/D+|Public|Bootstrapped|Acquired",
                    },
                    "funding_total_usd": {"type": "integer"},
                    "funding_rounds": {
                        "type": "array",
                        "description": "All publicly known rounds — omit array if unknown",
                        "items": {
                            "type": "object",
                            "properties": {
                                "round": {"type": "string", "description": "e.g. Seed, Series A"},
                                "date": {"type": "string", "description": "YYYY-MM-DD"},
                                "amount_usd": {"type": "integer"},
                                "lead": {"type": "string", "description": "Lead investor name"},
                            },
                        },
                    },
                    "notable_investors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "domain": {
                                    "type": "string",
                                    "description": "Investor's homepage domain if known",
                                },
                            },
                        },
                    },
                    "acquisition": {
                        "type": "object",
                        "properties": {
                            "acquired": {"type": "boolean"},
                            "acquirer": {"type": "string"},
                            "year": {"type": "integer"},
                            "amount_usd": {"type": "integer"},
                            "source_url": {"type": "string"},
                        },
                    },
                    # ── Traction ────────────────────────────────────────────
                    "arr_usd": {
                        "type": "number",
                        "description": "Only if explicitly disclosed in press / interviews",
                    },
                    "customer_count": {
                        "type": "integer",
                        "description": "Only if announced publicly",
                    },
                    "avg_contract_usd": {
                        "type": "number",
                        "description": "Only if disclosed",
                    },
                    # ── Team ────────────────────────────────────────────────
                    "key_people": {
                        "type": "array",
                        "description": "Top 5 senior CURRENT employees from LinkedIn People tab. Omit if cannot verify — do NOT pad with null entries.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {
                                    "type": "string",
                                    "description": "Current role at this company",
                                },
                                "linkedin": {
                                    "type": "string",
                                    "description": "linkedin.com/in/<slug>",
                                },
                                "background": {
                                    "type": "string",
                                    "description": "One-sentence background starting with current role at this company",
                                },
                            },
                        },
                    },
                    # ── Customers ───────────────────────────────────────────
                    "notable_customers": {
                        "type": "array",
                        "description": "5-10 publicly mentioned customers — omit if none verified",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "domain": {"type": "string"},
                                "segment": {
                                    "type": "string",
                                    "description": "Grand compte|ETI|PME|Startup|Consumer",
                                },
                                "industry": {"type": "string"},
                                "evidence": {
                                    "type": "string",
                                    "description": "Quote, case-study URL, or logo placement",
                                },
                            },
                        },
                    },
                    # ── Signals ─────────────────────────────────────────────
                    "recent_news": {
                        "type": "array",
                        "description": "5 most recent press items from last 12 months",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "description": "YYYY-MM-DD"},
                                "headline": {"type": "string"},
                                "source_url": {"type": "string"},
                            },
                        },
                    },
                    "growth_signals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-5 one-sentence growth events (hires, launches, expansion, partnerships)",
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top 3 public complaints from G2/Capterra/Reddit",
                    },
                },
            },
        }
    },
}


def build_query(competitors: list[dict]) -> str:
    """Dynamic prompt builder — future input will come from DISCOVER output."""
    listed = "\n".join(
        f"{i+1}. {c['name']} (https://www.{c['website']})"
        for i, c in enumerate(competitors)
    )
    plural = "company" if len(competitors) == 1 else f"{len(competitors)} companies"
    return (
        f"Build a comprehensive competitive intelligence profile for the "
        f"{plural} listed below. Return facts only, not reasoning.\n\n"
        f"Companies:\n{listed}\n\n"
        "Gather the following from public sources (company website, Crunchbase, "
        "LinkedIn, TechCrunch, G2, Capterra, press releases). For EACH company "
        "extract:\n\n"
        "IDENTITY\n"
        "- name (EXACT match from list above — CRITICAL for matching)\n"
        "- website domain, tagline (one-sentence elevator pitch)\n"
        "- category (primary market, e.g. 'HR Technology'), sub_category (specific niche)\n"
        "- linkedin_url (linkedin.com/company/<slug>)\n"
        "- hq_city, hq_country, founded_year\n"
        "- employee_count (LinkedIn About) and employee_growth_yoy as decimal (0.12 = +12%)\n\n"
        "POSITIONING\n"
        "- business_model: B2B, B2C, B2B2C, Marketplace, or API/Platform\n"
        "- gtm_motion: sales-led, product-led, marketing-led, or community-led\n"
        "- geo_coverage: Local, National, Regional, or Global\n"
        "- target_segment: Enterprise, Mid-Market, SMB, Consumer, or Mixed\n"
        "- target_verticals (3-5 industries)\n"
        "- top_3_features, key_differentiator (max 20 words)\n\n"
        "PRICING (from /pricing or /plans page)\n"
        "- pricing_model_kind: Freemium, Subscription, Usage-based, Enterprise, or Hybrid\n"
        "- pricing.free_plan (bool), starts_at_usd (0 if custom), mention\n"
        "- pricing.tiers: array of {name, price_monthly_usd, price_annual_usd, target, features[]}\n\n"
        "FUNDING (Crunchbase + press releases)\n"
        "- funding_stage, funding_total_usd\n"
        "- funding_rounds: array of {round, date YYYY-MM-DD, amount_usd, lead}\n"
        "- notable_investors: array of {name, domain}\n"
        "- acquisition: {acquired (bool), acquirer, year, amount_usd, source_url}\n\n"
        "TRACTION (only if explicitly disclosed in press or filings)\n"
        "- arr_usd, customer_count, avg_contract_usd — omit if not stated, do NOT estimate\n\n"
        "TEAM\n"
        "- key_people: top 5 senior CURRENT employees from LinkedIn People tab. "
        "For each: name, current role AT THIS COMPANY, linkedin URL "
        "(linkedin.com/in/<slug>), one-sentence background starting with "
        "current role at this company. Include only people currently employed at "
        "this company — exclude external partners, advisors, event speakers.\n\n"
        "CUSTOMERS\n"
        "- notable_customers: 5-10 customers mentioned on company website or case "
        "studies. For each: name, domain, segment (Grand compte/ETI/PME/Startup/Consumer), "
        "industry, evidence (quote / case-study URL / logo placement)\n\n"
        "SIGNALS (last 12 months)\n"
        "- recent_news: 5 most recent press items {date YYYY-MM-DD, headline, source_url}\n"
        "- growth_signals: 3-5 one-sentence growth events\n"
        "- weaknesses: top 3 user complaints from G2 / Capterra / Reddit\n\n"
        "OUTPUT FORMAT\n"
        "Return JSON {\"competitors\": [...]} with one entry per company, preserving "
        "the input ORDER and EXACT company names. If a field cannot be retrieved, "
        "OMIT it from the response — do NOT pad with null or placeholder values. "
        "Do not fabricate data."
    )


def _extract_competitor_payload(raw: dict, expected_name: str) -> dict:
    """Pull the single competitor dict out of a /research response.

    /research wraps structured output as {output: {<schema_root>}}. Our schema
    root is {competitors: [...]}. We sent ONE competitor per call, so we expect
    the array to contain a single item. Falls back to top-level fields if the
    array is empty or the wrapper is missing.
    """
    output = raw.get("output") if isinstance(raw, dict) else None
    if not isinstance(output, dict):
        return {}
    items = output.get("competitors")
    if isinstance(items, list) and items:
        for it in items:
            if isinstance(it, dict) and (it.get("name") or "").lower() == expected_name.lower():
                return it
        if isinstance(items[0], dict):
            return items[0]
    if "name" in output or "linkedin_url" in output:
        return output
    return {}


async def _run_one(linkup: LinkupClient, comp: dict, tracker: LinkupTracker) -> dict:
    """Single /research call for one competitor, wired into tracker."""
    name = comp["name"]
    try:
        result = await linkup.research_and_wait(
            query=build_query([comp]),
            depth="M",
            structured_schema=ENRICH_BATCH_SCHEMA,
            on_poll=tracker.make_callback(name),
            max_wait=900,
        )
        payload = _extract_competitor_payload(result, name)
        tracker.mark_completed(name, payload or result.get("output") or {})
        return {"company": comp, "raw": result, "payload": payload, "error": None}
    except Exception as e:
        tracker.mark_failed(name, repr(e))
        return {"company": comp, "raw": None, "payload": {}, "error": repr(e)}


async def main() -> int:
    print(f"\n=== POC ENRICH — {len(COMPETITORS)} parallel /research depth=M ===\n")
    for c in COMPETITORS:
        print(f"  - {c['name']} ({c['website']})")
    print(f"\nExpected cost: {len(COMPETITORS)} × €{RESEARCH_COST_EUR:.2f} = "
          f"€{len(COMPETITORS) * RESEARCH_COST_EUR:.2f}")
    print("\nLaunching… live progress will appear below. "
          "Watch evals/eval_enrich_4comp_result.json grow as jobs complete.\n")

    out_path = Path(__file__).resolve().parent / "eval_enrich_4comp_result.json"
    tracker = LinkupTracker(
        title=f"ENRICH POC — {len(COMPETITORS)} parallel /research",
        output_path=out_path,
    )
    for c in COMPETITORS:
        tracker.register_job(
            label=c["name"],
            endpoint="/research depth=M",
            cost_eur=RESEARCH_COST_EUR,
        )

    linkup = LinkupClient()
    t0 = time.monotonic()

    with tracker.live():
        results = await asyncio.gather(
            *[_run_one(linkup, c, tracker) for c in COMPETITORS],
            return_exceptions=False,
        )

    elapsed = time.monotonic() - t0

    # ── Post-run summary ─────────────────────────────────────────────────────
    summary = tracker.summary()
    print(f"\n=== Run finished in {elapsed:.0f}s ===")
    print(f"  Completed: {summary['completed']}/{summary['total']}")
    print(f"  Failed:    {summary['failed']}")
    print(f"  Cost:      ~€{summary['cost_eur_estimated']:.2f}")
    print(f"\nResult file: {out_path}")
    print("\nField coverage per competitor:")
    for r in results:
        name = r["company"]["name"]
        payload = r.get("payload") or {}
        if not payload:
            print(f"  ✗ {name}: empty payload (error: {r.get('error')})")
            continue
        filled = [k for k, v in payload.items() if v not in (None, "", [], {})]
        print(f"  ✓ {name}: {len(filled)} fields filled — {', '.join(filled[:10])}...")

    # ── Persist final raw dump for inspection ────────────────────────────────
    raw_dump = {
        r["company"]["name"]: {
            "company": r["company"],
            "payload": r["payload"],
            "error": r["error"],
            "raw_output_keys": list(r["raw"].get("output", {}).keys()) if (r["raw"] and isinstance(r["raw"].get("output"), dict)) else [],
        }
        for r in results
    }
    raw_path = Path(__file__).resolve().parent / "eval_enrich_4comp_raw.json"
    raw_path.write_text(json.dumps(raw_dump, indent=2, ensure_ascii=False, default=str))
    print(f"\nRaw payload dump: {raw_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
