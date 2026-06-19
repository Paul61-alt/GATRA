"""Eval standalone — Lane 3 LinkedIn batch via /search deep structured.

Validates the LinkedIn-only extraction prompt BEFORE integrating it into the
5-lanes ENRICH refactor. Uses /search depth=deep with structured outputType per
Linkup best practices ("LinkedIn extraction works exclusively through the
Search endpoint").

Cost: €0.055 / run.

Usage:
    cd radar/backend && source .venv/bin/activate
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
# Round 5 = lightweight 1-company eval to validate the 4 fixes (schema without
# `required`, prompt listing format, filter null/placeholder, filter externals)
# at minimal cost (€0.055). Linear chosen as best-indexed reference.
# Round 6 = validate image_url + excerpt extraction on a LESS-FAMOUS company
# (Maki People, not a daily-posting brand like Linear) — image reliability beyond
# famous brands is the gate for the LinkedIn-posts-preview feature (2026-05-31).
COMPETITORS = [
    {"name": "Maki People", "website": "makipeople.com"},
]


# ── Schema (required + description per field per Linkup structured output guide)
# IMPORTANT: schema does NOT use `required` on inner items. Linkup's behavior is to
# pad with dummy strings ("null", "placeholder") when required fields can't be
# populated, instead of omitting the item. Discovered in eval round 4 (2026-05-27).
LINKEDIN_BATCH_SCHEMA = {
    "type": "object",
    "required": ["competitors"],
    "properties": {
        "competitors": {
            "type": "array",
            "description": "One object per company, same order and exact names as input list",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact company name as provided in the input list (just the name, not the website in parens) — CRITICAL for matching",
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
                        "description": "Senior employees from the LinkedIn company People tab. Omit any entry you cannot fully verify — do NOT pad with placeholders.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Full name of the employee",
                                },
                                "role": {
                                    "type": "string",
                                    "description": "Current job title at the target company (e.g. CEO, CTO, Co-founder)",
                                },
                                "linkedin": {
                                    "type": "string",
                                    "description": "Exact personal profile URL, format linkedin.com/in/<slug>",
                                },
                                "background": {
                                    "type": "string",
                                    "description": "One-sentence background, MUST mention the target company by name",
                                },
                            },
                        },
                    },
                    "recent_linkedin_signals": {
                        "type": "array",
                        "description": "Recent public posts from the company page or its founders. Omit slots you cannot fully populate.",
                        "items": {
                            "type": "object",
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
                                "excerpt": {
                                    "type": "string",
                                    "description": "First ~280 characters of the post body text, verbatim. Longer than signal — used for the preview card. Null if body not readable.",
                                },
                                "image_url": {
                                    "type": "string",
                                    "description": "Direct URL of the post's main image (og:image / media.licdn.com), if the post has one. Null if the post is text-only.",
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
    """Final — v1 wording (high volume) + light verification cue. Code-side
    filter catches externals (partners, customers, speakers).

    Lessons from 3 eval runs:
      v1 (loose): 5/5/5 people, 5/5/5 signals — but Maki had 4 partners as fake employees
      v2 (strict employee-only): Linkup returned 1/0/2 — too few signals & people
      v3 (soft + volume target): Linkup padded with nulls, only 1 real employee each
    → variance in Linkup deep search is high; restrictive prompts make it shy.
    Combine v1 phrasing (max volume) + post-parsing filter that drops null entries
    and externals.
    """
    listed = "\n".join(
        f"  {i+1}. name=\"{c['name']}\", website=\"{c['website']}\""
        for i, c in enumerate(competitors)
    )
    return (
        f"For each of the {len(competitors)} companies listed below, perform a LinkedIn-only "
        "extraction in three sequential steps. The 'name' field in your output must be "
        "EXACTLY the name string given below (without the website).\n\n"
        f"Companies:\n{listed}\n\n"
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
        "Preserve company names EXACTLY as given (critical for matching). "
        "If LinkedIn does not yield a value for a field, set it to null. "
        "Do not fabricate values or pull from other sources."
    )


def _is_invalid_person(person: dict, company_name: str) -> bool:
    """Reject people that are null padding or clearly external.

    Returns True if the entry should be filtered out.
    """
    # Reject null padding — Linkup returns:
    #  - JSON null when omitting (rare)
    #  - String "null" when `required` forces a value (common, discovered round 4)
    #  - URL "linkedin.com/in/placeholder/" for required URL fields with no real data
    pname = person.get("name")
    plinkedin = person.get("linkedin") or ""
    if not pname or pname == "null" or pname.lower() == "none":
        return True
    if not plinkedin or "placeholder" in plinkedin.lower() or plinkedin == "null":
        return True

    bg = (person.get("background") or "").lower()
    role = (person.get("role") or "").lower()
    haystack = f"{role} {bg}"
    name = (company_name or "").lower()
    if not haystack.strip() or not name:
        return False  # cannot decide → keep (assume employee)

    company_slug = name.split()[0]  # "Maki People" → "maki"

    external_markers = [
        "partner at ", "speaker at ", "advisor at ",
        " at capgemini", " at unleash", " at deloitte",
        "consultant",
    ]
    has_external = any(m in haystack for m in external_markers)
    mentions_company = name in haystack or company_slug in haystack

    if has_external and not mentions_company:
        return True
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
    print("\nSubmitting /search depth=deep structured (cost ≈ €0.055)...\n")

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
            print("FAIL — could not decode 'answer' field as JSON", file=sys.stderr)
            return 1

    items = data.get("competitors", []) if isinstance(data, dict) else []
    if not items:
        print("FAIL — no 'competitors' array in response", file=sys.stderr)
        print(f"Raw data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}", file=sys.stderr)
        return 1

    # ── Post-parsing filter: reject null padding + external partners/speakers ──
    print("=== Post-parsing filter ===\n")
    filtered_summary = []
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
        it["_rejected_externals"] = rejected
        filtered_summary.append((name, len(kept), len(rejected)))
        if rejected:
            print(f"  [{name}] rejected {len(rejected)} entries (null padding or external):")
            for p in rejected:
                tag = "null" if not p.get("name") else (p.get("background") or "")[:80]
                print(f"     - {p.get('name') or '<null>'} ({tag})")

    print()
    for name, k, r in filtered_summary:
        print(f"  → {name}: kept={k}, rejected={r}")

    # ── Assertions v2 ─────────────────────────────────────────────────────────
    print("\n=== Assertions v2 ===\n")

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

    # C) ≥ 1 REAL employee per competitor (post-filter)
    # Lowered from 2 → 1 after observing Linkup variance: poorly-indexed startups
    # may only yield 1 verified employee. We still warn when < 2 (nice-to-have).
    print("[C] real employees per company (post-filter, ≥ 1 required, ≥ 2 ideal):")
    for it in items:
        name = it.get("name", "?")
        n = len(it.get("key_people") or [])
        if n == 0:
            marker = "✗"
            failures.append(f"real employees == 0 for {name}")
        elif n == 1:
            marker = "⚠"
            print(f"    {marker} {name}: {n}  (works but ideal ≥ 2)")
            continue
        else:
            marker = "✓"
        print(f"    {marker} {name}: {n}")

    # D) ≥ 1 recent_linkedin_signal per competitor
    sig_counts = [len(it.get("recent_linkedin_signals") or []) for it in items]
    print(f"[D] recent_linkedin_signals counts: {sig_counts} (≥ 1 each required)")
    for it, n in zip(items, sig_counts):
        if n < 1:
            failures.append(f"recent_linkedin_signals == 0 for {it.get('name', '?')}")

    # D2) GATE — image_url + excerpt fill rate (decides image-card vs text-only)
    all_sigs = [s for it in items for s in (it.get("recent_linkedin_signals") or [])]
    n_total = len(all_sigs)
    def _filled(s, key):
        v = s.get(key)
        return bool(v) and str(v).strip().lower() not in ("null", "none")
    n_img = sum(1 for s in all_sigs if _filled(s, "image_url"))
    n_exc = sum(1 for s in all_sigs if _filled(s, "excerpt"))
    n_exc_long = sum(
        1 for s in all_sigs
        if _filled(s, "excerpt") and len((s.get("excerpt") or "")) > len((s.get("signal") or ""))
    )
    print(f"\n[D2] preview-field fill rate over {n_total} posts:")
    if n_total:
        print(f"     image_url present : {n_img}/{n_total} ({100*n_img//n_total}%)")
        print(f"     excerpt present   : {n_exc}/{n_total} ({100*n_exc//n_total}%)")
        print(f"     excerpt > signal  : {n_exc_long}/{n_total} (richer than headline)")
        for s in all_sigs:
            img = "🖼" if _filled(s, "image_url") else "  "
            exc_len = len((s.get("excerpt") or ""))
            print(f"       {img} excerpt={exc_len}c  {(s.get('signal') or '')[:60]!r}")
    print("     → decision: image_url ≥ ~40% ⇒ ship image cards; else text-only card.")

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
