"""Eval standalone — Lane 3 LinkedIn batch via /search deep structured.

Validates the LinkedIn-only extraction prompt BEFORE integrating it into the
5-lanes ENRICH refactor. Uses /search depth=deep with structured outputType per
Linkup best practices ("LinkedIn extraction works exclusively through the
Search endpoint").

Cost: €0.055 / run.

Usage:
    cd RADAR/radar/backend && source .venv/bin/activate
    python -m evals.eval_linkedin_research
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from clients.linkup_client import LinkupClient

load_dotenv()


# ── Sample cohort (hardcoded) ─────────────────────────────────────────────────
COMPETITORS = [
    {"name": "Linear", "website": "linear.app"},
    {"name": "Notion", "website": "notion.so"},
    {"name": "Maki People", "website": "makipeople.com"},
]


# ── Schema (required + description per field per Linkup structured output guide)
LINKEDIN_BATCH_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {
            "type": "array",
            "description": "One object per company, same order and exact names as input list",
            "items": {
                "type": "object",
                "required": ["name", "linkedin_url"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact company name as provided in the input list — CRITICAL for matching",
                    },
                    "website": {
                        "type": "string",
                        "description": "Company website domain",
                    },
                    "linkedin_url": {
                        "type": "string",
                        "description": "Exact LinkedIn company page URL, format linkedin.com/company/<slug>",
                    },
                    "key_people": {
                        "type": "array",
                        "description": "Top 5 founders and executives from the LinkedIn company People tab",
                        "items": {
                            "type": "object",
                            "required": ["name", "linkedin"],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Full name",
                                },
                                "role": {
                                    "type": "string",
                                    "description": "Current job title (e.g. CEO, CTO, Co-founder)",
                                },
                                "linkedin": {
                                    "type": "string",
                                    "description": "Exact personal profile URL, format linkedin.com/in/<slug>",
                                },
                                "background": {
                                    "type": "string",
                                    "description": "One-sentence background including prior companies if visible",
                                },
                            },
                        },
                    },
                    "recent_linkedin_signals": {
                        "type": "array",
                        "description": "3-5 most recent public posts from the company page or its founders",
                        "items": {
                            "type": "object",
                            "required": ["date", "signal", "source_url"],
                            "properties": {
                                "date": {
                                    "type": "string",
                                    "description": "Post date YYYY-MM-DD",
                                },
                                "author": {
                                    "type": "string",
                                    "description": "Post author name (company or person)",
                                },
                                "signal": {
                                    "type": "string",
                                    "description": "Post headline or first 150 chars of post body",
                                },
                                "source_url": {
                                    "type": "string",
                                    "description": "Full post URL, format linkedin.com/posts/...",
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}


def _linkedin_batch_query(competitors: list[dict]) -> str:
    """v3 — soft employee-only filter; keep volume target of v1 (5 people, 3-5 posts)
    but require explicit employer verification on each person.

    v1 returned 5/5/5 people but Maki had 4 externals (Partner at UNLEASH etc).
    v2 was too aggressive — Linkup returned only 1/0/2 people overall.
    v3 = ask for 5 senior employees AND for each one require current employer = target
    company in the 'background' field. Filter (code-side) catches remaining externals.
    """
    listed = "\n".join(
        f"- {c['name']} ({c['website']})"
        for c in competitors
    )
    return (
        f"For each of the {len(competitors)} companies listed below, perform a LinkedIn-only "
        "extraction in three sequential steps.\n\n"
        f"Companies:\n{listed}\n\n"
        "STEP 1 — For each company, find its exact LinkedIn company page URL "
        "(format: linkedin.com/company/<slug>). The slug is usually derived from "
        "the company name or website domain.\n\n"
        "STEP 2 — Scrape each LinkedIn company page URL found in step 1. "
        "Return the profile details: linkedin_url, plus the 5 most senior employees "
        "from the People tab (CEO, CTO, CPO, co-founders, VP-level). "
        "For each person, you MUST verify that their CURRENT employer (as shown in their "
        "LinkedIn headline or top of Experience section) is the target company. "
        "If a person is listed on a partner / customer / event-speaker post but their "
        "current employer is a DIFFERENT company, DO NOT include them — go find another "
        "actual employee instead. Aim for 5 verified employees per company. "
        "For each: name, current role at THIS company, exact personal profile URL "
        "(linkedin.com/in/<slug>), and a one-sentence background that STARTS with their "
        "current role at the target company (e.g. 'CEO and co-founder of <CompanyName>, "
        "...').\n\n"
        "STEP 3 — For each company page, return the 3 to 5 MOST RECENT public posts "
        "from the company page or its founders (look back at least 12 months — do NOT "
        "return only 1 post if more are available). For each post: date (YYYY-MM-DD), "
        "author name, signal (post headline or first 150 chars), and full post URL "
        "(linkedin.com/posts/...).\n\n"
        "Return one object per company in the same order as the input list. "
        "Preserve company names EXACTLY as given (critical for matching). "
        "If LinkedIn does not yield a value for a field, set it to null. "
        "Do not fabricate values or pull from other sources."
    )


def _is_likely_external(person: dict, company_name: str) -> bool:
    """Reject people whose background hints they work elsewhere.

    Returns True if the person should be filtered out (not a real employee).
    """
    bg = (person.get("background") or "").lower()
    name = (company_name or "").lower()
    if not bg or not name:
        return False  # cannot decide → keep

    # Slug = first word of company name (e.g. "Maki People" → "maki")
    company_slug = name.split()[0]

    # External markers that imply different employer
    external_markers = [
        "partner at ",
        "speaker at ",
        "consultant",
        "advisor at ",
        " at capgemini",
        " at unleash",  # generic but specific cases from v1 fail
    ]
    # If background mentions an external marker AND does NOT mention the company → reject
    has_external = any(m in bg for m in external_markers)
    mentions_company = name in bg or company_slug in bg

    if has_external and not mentions_company:
        return True

    # If no mention of company at all → suspect
    if not mentions_company:
        return True

    return False


async def main() -> int:
    print(f"\n=== Lane 3 LinkedIn batch eval — {len(COMPETITORS)} companies ===\n")
    for c in COMPETITORS:
        print(f"  - {c['name']} ({c['website']})")

    query = _linkedin_batch_query(COMPETITORS)
    linkup = LinkupClient()

    t0 = time.monotonic()
    print(f"\nSubmitting /search depth=deep structured (cost ≈ €0.055)...\n")

    try:
        raw = await linkup.search(
            query=query,
            depth="deep",
            output_type="structured",
            schema=LINKEDIN_BATCH_SCHEMA,
        )
    except Exception as e:
        print(f"FAIL — Linkup call raised: {e}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - t0
    print(f"OK — Linkup call completed in {elapsed:.1f}s\n")

    # Persist raw result for inspection
    out_path = Path(__file__).resolve().parent / "eval_linkedin_research_result.json"
    out_path.write_text(json.dumps(raw, indent=2, default=str, ensure_ascii=False))
    print(f"Raw result saved → {out_path}\n")

    # ── Parse result ──────────────────────────────────────────────────────────
    # /search structured returns either {data: {...}, sources: [...]} or {answer: ...}
    data = raw.get("data") or raw.get("answer") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print(f"FAIL — could not decode 'answer' field as JSON", file=sys.stderr)
            return 1

    items = data.get("competitors", []) if isinstance(data, dict) else []
    if not items:
        print(f"FAIL — no 'competitors' array in response", file=sys.stderr)
        print(f"Raw data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}", file=sys.stderr)
        return 1

    # ── v2 Post-parsing filter: reject external partners/speakers/consultants ──
    print(f"=== v2 Post-parsing filter ===\n")
    filtered_summary = []
    for it in items:
        name = it.get("name", "?")
        raw_people = it.get("key_people") or []
        kept, rejected = [], []
        for p in raw_people:
            if _is_likely_external(p, name):
                rejected.append(p)
            else:
                kept.append(p)
        it["key_people"] = kept
        it["_rejected_externals"] = rejected
        filtered_summary.append((name, len(kept), len(rejected)))
        if rejected:
            print(f"  [{name}] rejected {len(rejected)} external(s):")
            for p in rejected:
                print(f"     - {p.get('name')} ({(p.get('background') or '')[:80]})")

    print()
    for name, k, r in filtered_summary:
        print(f"  → {name}: kept={k}, rejected={r}")

    # ── Assertions v2 ─────────────────────────────────────────────────────────
    print(f"\n=== Assertions v2 ===\n")

    failures: list[str] = []

    # A) Cohort cardinality
    print(f"[A] cohort returned: {len(items)} / {len(COMPETITORS)} expected")
    if len(items) != len(COMPETITORS):
        failures.append(f"cardinality: got {len(items)}, expected {len(COMPETITORS)}")

    # B) linkedin_url presence per competitor
    li_url_count = sum(1 for it in items if it.get("linkedin_url"))
    print(f"[B] linkedin_url extracted: {li_url_count} / {len(items)}")
    if li_url_count < len(items):
        missing = [it.get("name", "?") for it in items if not it.get("linkedin_url")]
        failures.append(f"linkedin_url missing for: {missing}")

    # C) ≥ 2 REAL employees per competitor (post-filter)
    print(f"[C] real employees per company (post-filter, ≥ 2 required):")
    for it in items:
        name = it.get("name", "?")
        n = len(it.get("key_people") or [])
        marker = "✓" if n >= 2 else "✗"
        print(f"    {marker} {name}: {n}")
        if n < 2:
            failures.append(f"real employees < 2 for {name} (got {n})")

    # D) ≥ 1 recent_linkedin_signal per competitor
    sig_counts = [len(it.get("recent_linkedin_signals") or []) for it in items]
    print(f"[D] recent_linkedin_signals counts: {sig_counts} (≥ 1 each required)")
    for it, n in zip(items, sig_counts):
        if n < 1:
            failures.append(f"recent_linkedin_signals == 0 for {it.get('name', '?')}")

    # E) URLs validity (linkedin.com/in/... + linkedin.com/company/...)
    bad_company_urls = [
        it.get("name", "?") for it in items
        if it.get("linkedin_url") and "linkedin.com/company/" not in it["linkedin_url"]
    ]
    if bad_company_urls:
        failures.append(f"linkedin_url not matching linkedin.com/company/ pattern: {bad_company_urls}")
    print(f"[E] linkedin_url pattern valid: {len(items) - len(bad_company_urls)} / {len(items)}")

    bad_people_urls = []
    for it in items:
        for p in (it.get("key_people") or []):
            if p.get("linkedin") and "linkedin.com/in/" not in p["linkedin"]:
                bad_people_urls.append(f"{it.get('name', '?')}/{p.get('name', '?')}")
    if bad_people_urls:
        failures.append(f"key_people.linkedin not matching linkedin.com/in/ pattern: {bad_people_urls}")
    total_people = sum(len(it.get("key_people") or []) for it in items)
    print(f"[F] key_people.linkedin pattern valid: {total_people - len(bad_people_urls)} / {total_people}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures:
        print(f"=== FAIL — {len(failures)} assertion(s) failed ===")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    else:
        print(f"=== PASS — all assertions OK, latency {elapsed:.1f}s ===")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
