"""eval_to_data_js.py — Demo adapter for the new Positioning charts.

Reads the cached eval enrichment output (`eval_enrich_4comp_result.json`,
HR-tech cohort: HireVue / Paradox / TestGorilla / Harver) and rewrites the
`subject` + `competitors[]` arrays in `frontend-prototype/data.js`.

TestGorilla is used as the subject (only non-acquired comp). Other three become
competitors. All Positioning-chart fields (`arr`, `fundingRounds`,
`notable_investors`, `notable_customers`, `acquisition`, …) are populated.

Other top-level keys in data.js (features / capabilities / pricing / radar) are
preserved as-is so the other tabs keep loading without crash.

Usage:
    python -m utils.eval_to_data_js
"""
from __future__ import annotations

import json
import re
from pathlib import Path

USD_TO_EUR = 0.92

EVAL_JSON = Path(__file__).resolve().parents[1] / "evals" / "eval_enrich_4comp_result.json"
DATA_JS = Path(__file__).resolve().parents[3] / "radar" / "frontend-prototype" / "data.js"

assert EVAL_JSON.exists(), f"Eval JSON not found: {EVAL_JSON}"
assert DATA_JS.parent.exists(), f"Frontend dir not found: {DATA_JS.parent}"

# Static HQ city → (lat, lng) for known cohort cities. Avoids hitting geocoding API.
HQ_COORDS: dict[str, tuple[float, float]] = {
    "Salt Lake City": (40.7608, -111.8910),
    "Scottsdale": (33.4942, -111.9261),
    "Amsterdam": (52.3676, 4.9041),
    "London": (51.5074, -0.1278),
    "Paris": (48.8566, 2.3522),
}

# Threat / similarity scoring for the demo cohort (deterministic VC framing)
COHORT = {
    "subject": "TestGorilla",
    "competitors": [
        ("HireVue", 0.84, "high"),
        ("Paradox", 0.78, "high"),
        ("Harver", 0.72, "medium"),
    ],
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _strip_citation(s):
    """LLM occasionally appends '[citation](url)' to plain string values. Strip it."""
    if not isinstance(s, str):
        return s
    return re.sub(r"\s*\[.*", "", s).strip()


def _to_num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("$", "").replace("€", "").upper()
    mult = 1.0
    if s.endswith("B"):
        mult, s = 1e9, s[:-1]
    elif s.endswith("M"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("K"):
        mult, s = 1e3, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _coerce_str_field(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("value")
    return _strip_citation(v)


def _convert(raw: dict, *, is_subject: bool, similarity: float, threat: str) -> dict:
    name = raw["name"]

    arr_usd = _to_num(raw.get("arr_usd"))
    arr_eur = arr_usd * USD_TO_EUR if arr_usd else None

    funding_total_usd = _to_num(raw.get("funding_total_usd")) or 0.0
    funding_total_eur = funding_total_usd * USD_TO_EUR

    avg_contract_usd = _to_num(raw.get("avg_contract_usd"))
    avg_contract_eur = avg_contract_usd * USD_TO_EUR if avg_contract_usd else None

    funding_rounds: list[dict] = []
    for r in (raw.get("funding_rounds") or []):
        amt_usd = _to_num(r.get("amount_usd"))
        funding_rounds.append({
            "round": r.get("round"),
            "date": r.get("date"),
            "amountEur": amt_usd * USD_TO_EUR if amt_usd else None,
        })

    last_round = funding_rounds[-1] if funding_rounds else {}
    funding_status = "enriched" if funding_total_eur > 0 else "not_found"

    funding_info = {
        "total": funding_total_eur,
        "lastRound": last_round.get("round") or "",
        "lastRoundAt": last_round.get("date") or "",
        "status": funding_status,
        "rounds": funding_rounds,
        "totalRaisedEur": funding_total_eur or None,
    }

    hq_city = raw.get("hq_city") or ""
    hq_country = raw.get("hq_country") or ""
    hq_str = ", ".join(p for p in [hq_city, hq_country] if p)
    coords = HQ_COORDS.get(hq_city, (0.0, 0.0))

    employee_count_raw = raw.get("employee_count")
    if isinstance(employee_count_raw, dict):
        employee_count_raw = employee_count_raw.get("value")
    try:
        employee_count = int(re.search(r"\d+", str(employee_count_raw)).group())
    except (AttributeError, ValueError, TypeError):
        employee_count = None

    employee_growth = raw.get("employee_growth_yoy")
    employee_growth = float(employee_growth) if isinstance(employee_growth, (int, float)) else 0.0

    customer_count_raw = raw.get("customer_count")
    customers = None
    if customer_count_raw is not None:
        n = _to_num(customer_count_raw)
        customers = int(n) if n else None

    acquisition_raw = raw.get("acquisition") or {}
    acquisition = {
        "acquired": bool(acquisition_raw.get("acquired", False)),
        "acquirer": _strip_citation(acquisition_raw.get("acquirer")),
        "year": acquisition_raw.get("year"),
        "sourceUrl": acquisition_raw.get("source_url"),
    }

    funding_stage_clean = _coerce_str_field(raw.get("funding_stage"))

    return {
        "id": _slug(name),
        "name": name,
        "domain": raw.get("website_domain") or "",
        "tagline": raw.get("tagline") or "",
        "category": raw.get("category") or "HR Technology",
        "subCategory": raw.get("sub_category") or "",
        "hq": hq_str,
        "hqCoords": list(coords),
        "offices": [hq_city] if hq_city else [],
        "founded": raw.get("founded_year"),
        "employees": employee_count,
        "employeeGrowth": employee_growth,
        "funding": funding_info,
        "fundingRounds": funding_rounds,
        "fundingStage": funding_stage_clean,
        "investors": [i.get("name") for i in (raw.get("notable_investors") or []) if i.get("name")],
        "notable_investors": raw.get("notable_investors") or [],
        "notable_customers": raw.get("notable_customers") or [],
        "key_people": raw.get("key_people") or [],
        "customers": customers,
        "arr": arr_eur,
        "avgContract": avg_contract_eur,
        "business_model": _coerce_str_field(raw.get("business_model")),
        "gtm_motion": _coerce_str_field(raw.get("gtm_motion")),
        "target_segment": _coerce_str_field(raw.get("target_segment")),
        "geo_coverage": _coerce_str_field(raw.get("geo_coverage")),
        "acquisition": acquisition,
        "recentNews": raw.get("recent_news") or [],
        "recentLinkedinPosts": [
            {
                "date": s.get("date"),
                "author": s.get("author"),
                "excerpt": (s.get("excerpt") or s.get("signal") or "").strip(),
                "imageUrl": s.get("image_url"),
                "sourceUrl": s.get("source_url"),
            }
            for s in (raw.get("recent_linkedin_signals") or [])[:5]
            if (s.get("excerpt") or s.get("signal"))
        ],
        "growthSignals": raw.get("growth_signals") or [],
        "top3Features": raw.get("top_3_features") or [],
        "targetVerticals": raw.get("target_verticals") or [],
        "isSubject": is_subject,
        "similarity": similarity,
        "threat": threat,
        "pricing": {"model": "Custom", "starts_at": 0, "mention": "Contact sales"},
    }


def main() -> None:
    eval_data = json.loads(EVAL_JSON.read_text())["completed"]

    subject = _convert(
        eval_data[COHORT["subject"]],
        is_subject=True,
        similarity=1.0,
        threat="high",
    )
    competitors = [
        _convert(eval_data[n], is_subject=False, similarity=s, threat=t)
        for (n, s, t) in COHORT["competitors"]
    ]

    text = DATA_JS.read_text()
    m = re.search(
        r"window\.RADAR_DATA\s*=\s*(\{.*?\});\s*\n\s*window\.RADAR_DATA\.allCompanies",
        text,
        re.DOTALL,
    )
    existing = json.loads(m.group(1)) if m else {}

    existing["subject"] = subject
    existing["competitors"] = competitors

    if "query" in existing:
        existing["query"]["name"] = subject["name"]
        existing["query"]["url"] = f"https://{subject['domain']}"
    else:
        existing["query"] = {
            "url": f"https://{subject['domain']}",
            "name": subject["name"],
            "scannedAt": "2026-05-29T00:00:00Z",
            "durationMs": 0,
            "sourcesScanned": 0,
        }

    all_companies = [subject] + competitors

    out = (
        "// Auto-generated by utils/eval_to_data_js.py — Positioning demo data.\n"
        f"window.RADAR_DATA = {json.dumps(existing, indent=2, ensure_ascii=False)};\n\n"
        f"window.RADAR_DATA.allCompanies = {json.dumps(all_companies, indent=2, ensure_ascii=False)};\n"
    )
    DATA_JS.write_text(out, encoding="utf-8")

    print(f"Wrote {DATA_JS}")
    print(f"  subject = {subject['name']}  ARR={subject['arr']!r}  funding={subject['funding']['total']:.0f} EUR")
    for c in competitors:
        print(f"  comp    = {c['name']:<12}  ARR={c['arr']!r}  funding={c['funding']['total']:.0f} EUR  rounds={len(c['fundingRounds'])}  invs={len(c['notable_investors'])}  custs={len(c['notable_customers'])}")


if __name__ == "__main__":
    main()
