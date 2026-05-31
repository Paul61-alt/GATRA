"""POC — Lane 3 LinkedIn via /research depth=S, PER company in parallel.

Compares against frozen /search deep batched eval (eval_linkedin_research.py).

Architecture difference:
  - Frozen eval: 1 /search deep batched call with N companies → €0.055 total
    Result: null-padding from Linkup, 0-1 real employee per company
  - This POC: N /research depth=S parallel calls (1 per company) → €0.25 × N
    Hypothesis: focused single-company prompt + /research's agentic loop yields
    higher real-employee count + complete linkedin_url + signals

Cost: 3 companies × €0.25 = €0.75 / run.

Usage:
    cd RADAR/radar/backend && source .venv/bin/activate
    python -m evals.eval_linkedin_research_poc
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from clients.linkup_client import LinkupClient

load_dotenv()


COMPETITORS = [
    {"name": "Linear", "website": "linear.app"},
    {"name": "Notion", "website": "notion.so"},
    {"name": "Maki People", "website": "makipeople.com"},
]


# Per-company schema (no `required` to avoid null-padding behaviour observed
# with /search deep — keep this hypothesis testable for /research as well).
LINKEDIN_SINGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Exact company name as provided in input",
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
            "description": "Top 5 senior CURRENT employees from the LinkedIn People tab. Omit any entry that cannot be fully verified — do NOT pad with placeholders or null values.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full name",
                    },
                    "role": {
                        "type": "string",
                        "description": "Current job title at this company",
                    },
                    "linkedin": {
                        "type": "string",
                        "description": "Exact personal profile URL, format linkedin.com/in/<slug>",
                    },
                    "background": {
                        "type": "string",
                        "description": "One-sentence background starting with current role at the target company",
                    },
                },
            },
        },
        "recent_linkedin_signals": {
            "type": "array",
            "description": "3-5 most recent public posts from the company page or its founders. Omit if not retrievable — do NOT pad.",
            "items": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Post date YYYY-MM-DD",
                    },
                    "author": {
                        "type": "string",
                        "description": "Post author name",
                    },
                    "signal": {
                        "type": "string",
                        "description": "Post headline or first 150 chars",
                    },
                    "source_url": {
                        "type": "string",
                        "description": "Full post URL, format linkedin.com/posts/...",
                    },
                },
            },
        },
    },
}


def _linkedin_single_query(name: str, website: str) -> str:
    """Per-company prompt — focused, no multi-entity ordering constraints."""
    return (
        f"Perform a LinkedIn-only research on {name} ({website}) in three sequential steps.\n\n"
        f"STEP 1 — Find the exact LinkedIn company page URL for {name} "
        f"(format: linkedin.com/company/<slug>). The slug is derived from the company name "
        f"or website domain.\n\n"
        f"STEP 2 — Scrape that LinkedIn company page and return the profile details: "
        f"linkedin_url, plus the 5 most senior CURRENT EMPLOYEES of {name} from the People tab "
        f"(CEO, CTO, CPO, co-founders, VP-level). For each person: name, current role AT {name} "
        f"(not at a previous employer), exact personal profile URL (linkedin.com/in/<slug>), "
        f"and a one-sentence background that begins with their current role at {name} "
        f"(e.g. 'Co-founder & CTO at {name}, ...'). "
        f"Include only people who currently work at {name} — exclude external partners, "
        f"customers, advisors, or event speakers merely mentioned in posts. "
        f"If fewer than 5 verified employees can be found, return only the verified ones — "
        f"do NOT pad with placeholders or null entries.\n\n"
        f"STEP 3 — Return the 3 to 5 MOST RECENT public posts from {name}'s company page "
        f"or its founders (last 12 months). For each: date (YYYY-MM-DD), author name, "
        f"signal (post headline or first 150 chars), full post URL (linkedin.com/posts/...).\n\n"
        f"If a field cannot be retrieved from LinkedIn, OMIT it from the response. "
        f"Do not fabricate values or pull from other sources. Do not invent placeholder data."
    )


def _is_invalid_person(person: dict, company_name: str) -> bool:
    """Reject null padding, placeholder strings, and clearly external people."""
    name = (person.get("name") or "").strip().lower()
    linkedin = (person.get("linkedin") or "").strip().lower()

    if not name or name == "null":
        return True
    if not linkedin or "placeholder" in linkedin or linkedin == "null":
        return True

    bg = (person.get("background") or "").lower()
    role = (person.get("role") or "").lower()
    haystack = f"{role} {bg}"
    cname = (company_name or "").lower()
    if not haystack.strip() or not cname:
        return False

    company_slug = cname.split()[0]
    external_markers = [
        "partner at ", "speaker at ", "advisor at ",
        " at capgemini", " at unleash", " at deloitte",
        "consultant",
    ]
    has_external = any(m in haystack for m in external_markers)
    mentions_company = cname in haystack or company_slug in haystack

    if has_external and not mentions_company:
        return True
    if not mentions_company:
        return True
    return False


async def _research_one(linkup: LinkupClient, company: dict, event_log: list) -> dict:
    """Single /research depth=S call for one company."""
    name = company["name"]
    website = company["website"]
    query = _linkedin_single_query(name, website)

    async def _on_poll(state: dict):
        elapsed = state.get("elapsed", 0)
        if int(elapsed) % 30 == 0:  # log every ~30s
            event_log.append(f"[{name}] poll t={elapsed:.0f}s status={state.get('status')}")

    t0 = time.monotonic()
    try:
        raw = await linkup.research_and_wait(
            query=query,
            depth="S",
            structured_schema=LINKEDIN_SINGLE_SCHEMA,
            on_poll=_on_poll,
            max_wait=900,
        )
        elapsed = time.monotonic() - t0
        return {"company": company, "raw": raw, "elapsed": elapsed, "error": None}
    except Exception as e:
        return {"company": company, "raw": None, "elapsed": time.monotonic() - t0, "error": str(e)}


async def main() -> int:
    print("\n=== POC Lane 3 LinkedIn — /research depth=S per company ===")
    print(f"Companies ({len(COMPETITORS)}):")
    for c in COMPETITORS:
        print(f"  - {c['name']} ({c['website']})")
    print(f"\nExpected cost: {len(COMPETITORS)} × €0.25 = €{len(COMPETITORS) * 0.25:.2f}")
    print(f"Submitting {len(COMPETITORS)} parallel /research depth=S calls...\n")

    linkup = LinkupClient()
    event_log: list = []
    t0 = time.monotonic()

    results = await asyncio.gather(
        *[_research_one(linkup, c, event_log) for c in COMPETITORS],
        return_exceptions=False,
    )

    total_elapsed = time.monotonic() - t0
    print(f"All calls completed in {total_elapsed:.1f}s (parallel)\n")

    # Persist raw results
    out_path = Path(__file__).resolve().parent / "eval_linkedin_research_poc_result.json"
    out_path.write_text(json.dumps(
        [{"company": r["company"], "raw": r["raw"], "elapsed": r["elapsed"], "error": r["error"]} for r in results],
        indent=2, default=str, ensure_ascii=False,
    ))
    print(f"Raw results saved → {out_path}\n")

    # ── Parse results ─────────────────────────────────────────────────────────
    items: list = []
    for r in results:
        if r["error"]:
            print(f"  [{r['company']['name']}] ERROR: {r['error']}")
            continue
        raw = r["raw"] or {}
        # /research structured returns {output: {data: {...}, sources: [...]}}
        output = raw.get("output") or raw or {}
        if not isinstance(output, dict):
            output = {}
        data = output.get("data") or output.get("answer") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                print(f"  [{r['company']['name']}] WARN: 'data' not JSON-parseable")
                data = {}
        # Inject the input name in case Linkup returned slightly different
        if isinstance(data, dict):
            data.setdefault("name", r["company"]["name"])
            data.setdefault("website", r["company"]["website"])
            data["_elapsed"] = r["elapsed"]
            items.append(data)

    # ── Apply filter ──────────────────────────────────────────────────────────
    print("\n=== Post-parsing filter ===\n")
    for it in items:
        name = it.get("name", "?")
        raw_people = it.get("key_people") or []
        kept, rejected = [], []
        for p in raw_people:
            if _is_invalid_person(p, name):
                rejected.append(p)
            else:
                kept.append(p)
        it["key_people"] = kept
        it["_rejected"] = rejected
        if rejected:
            print(f"  [{name}] rejected {len(rejected)} (null/placeholder/external):")
            for p in rejected:
                tag = p.get("name") or "<null>"
                print(f"     - {tag} (linkedin={p.get('linkedin')!r})")

    # ── Side-by-side comparison ───────────────────────────────────────────────
    print("\n=== Per-company summary ===\n")
    for it in items:
        n = it.get("name", "?")
        url = it.get("linkedin_url")
        ppl = it.get("key_people") or []
        sigs = it.get("recent_linkedin_signals") or []
        el = it.get("_elapsed", 0)
        print(f"━━━ {n} (elapsed {el:.1f}s) ━━━")
        print(f"  linkedin_url: {url}")
        print(f"  real key_people: {len(ppl)}")
        for p in ppl[:5]:
            print(f"    - {p.get('name')} | {p.get('role')} | linkedin={p.get('linkedin')}")
            if p.get("background"):
                print(f"      bg: {p['background'][:100]}")
        print(f"  signals: {len(sigs)}")
        for s in sigs[:3]:
            print(f"    - [{s.get('date')}] {s.get('author','?')}: {(s.get('signal') or '')[:80]}")
        print()

    # ── Assertions ────────────────────────────────────────────────────────────
    print("=== Assertions ===\n")
    failures: list[str] = []

    if len(items) != len(COMPETITORS):
        failures.append(f"cardinality: got {len(items)}, expected {len(COMPETITORS)}")
    print(f"[A] cohort: {len(items)} / {len(COMPETITORS)}")

    li_url_count = sum(1 for it in items if it.get("linkedin_url"))
    print(f"[B] linkedin_url extracted: {li_url_count} / {len(items)}")
    if li_url_count < len(items):
        failures.append(f"linkedin_url missing: {[it.get('name') for it in items if not it.get('linkedin_url')]}")

    print("[C] real employees post-filter (≥ 2 ideal):")
    for it in items:
        n = it.get("name", "?")
        k = len(it.get("key_people") or [])
        marker = "✓" if k >= 2 else ("⚠" if k == 1 else "✗")
        print(f"    {marker} {n}: {k}")
        if k == 0:
            failures.append(f"real employees == 0 for {n}")

    sig_counts = [len(it.get("recent_linkedin_signals") or []) for it in items]
    print(f"[D] signals counts: {sig_counts}")
    for it, n in zip(items, sig_counts):
        if n < 1:
            failures.append(f"signals == 0 for {it.get('name','?')}")

    print()
    if failures:
        print(f"=== POC FAIL — {len(failures)} assertion(s) ===")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    else:
        print(f"=== POC PASS — total latency {total_elapsed:.1f}s, est cost €{len(COMPETITORS) * 0.25:.2f} ===")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
