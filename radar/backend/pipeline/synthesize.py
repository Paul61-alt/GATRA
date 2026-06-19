"""Phase 4 — SYNTHESIZE: derive radar axis scores from extracted data.

Replaces transform.py's placeholder [50]*6 with deterministic heuristics.
Each axis scored 0..100 from concrete signals (features, funding, pricing,
customers). Returns {entity_id: [Breadth, Depth, Global, Developer, Pricing, Trust]}.

Heuristics intentionally explicit — no LLM call. Cost = 0, latency = ~ms.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from models.company import CompanyProfile
from models.competitor import CompetitorProfile

logger = logging.getLogger(__name__)

AXES = ["Breadth", "Depth", "Global", "Developer", "Pricing", "Trust"]

_DEV_PATTERN = re.compile(
    r"\b(api|apis|sdk|webhook|integration|developer|docs|cli|openapi|graphql)\b",
    re.IGNORECASE,
)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _age_years(founded: int | None) -> int:
    if not founded:
        return 0
    return max(0, datetime.now(timezone.utc).year - founded)


def _dev_signal_count(*texts) -> int:
    """Count developer-keyword hits across given strings/lists."""
    count = 0
    for t in texts:
        if not t:
            continue
        if isinstance(t, list):
            blob = " ".join(str(x) for x in t if x)
        else:
            blob = str(t)
        count += len(_DEV_PATTERN.findall(blob))
    return count


def _extract_int(value) -> int:
    """Parse first integer from arbitrary value (e.g. '200-500' → 200)."""
    if value is None:
        return 0
    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else 0


def _score_subject(profile: CompanyProfile) -> list[float]:
    # Breadth — product surface
    breadth = (
        len(profile.top_3_features) * 10
        + len(profile.target_verticals) * 5
        + len(profile.notable_customers) * 5
        + (10 if profile.markets else 0)
    )

    # Depth — signal density
    depth = (
        len(profile.growth_signals) * 8
        + len(profile.recent_news) * 6
        + (10 if profile.business_model and profile.business_model.value else 0)
    )

    # Global — geo + capital scale
    geo_score_map = {"Global": 90, "Regional": 70, "National": 45, "Local": 20}
    geo_score = geo_score_map.get(profile.geo_coverage or "", 35)
    funding_bonus = 0.0
    if profile.funding and profile.funding.total_raised_eur:
        try:
            f = float(profile.funding.total_raised_eur.value or 0)
            funding_bonus = min(15, f / 10_000_000)  # +1pt per €10M, cap 15
        except (TypeError, ValueError):
            pass
    global_ = geo_score + funding_bonus

    # Developer — API/SDK presence
    diff_value = profile.key_differentiator.value if profile.key_differentiator else None
    dev_hits = _dev_signal_count(
        profile.positioning,
        diff_value,
        profile.top_3_features,
        profile.tech_stack,
    )
    developer = 30 + dev_hits * 15

    # Pricing — model accessibility
    pricing_value = profile.pricing_model.value if profile.pricing_model else None
    pricing_map = {
        "Freemium": 85,
        "Subscription": 65,
        "Usage-based": 60,
        "Hybrid": 55,
        "Enterprise/Sur devis": 30,
    }
    pricing = pricing_map.get(pricing_value or "", 50)

    # Trust — durability + traction
    age = _age_years(profile.founded_year)
    employees_int = _extract_int(profile.employees.value if profile.employees else None)
    funding_total = 0.0
    if profile.funding and profile.funding.total_raised_eur:
        try:
            funding_total = float(profile.funding.total_raised_eur.value or 0)
        except (TypeError, ValueError):
            pass
    trust = (
        min(30, age * 2)
        + min(25, employees_int / 20)
        + min(25, funding_total / 4_000_000)  # €100M ≈ 25 pts
        + len(profile.notable_customers) * 3
        + len(profile.notable_investors) * 2
    )

    return [
        _clamp(breadth),
        _clamp(depth),
        _clamp(global_),
        _clamp(developer),
        _clamp(pricing),
        _clamp(trust),
    ]


def _score_competitor(profile: CompetitorProfile) -> list[float]:
    # Breadth
    tiers_count = len(profile.pricing.tiers) if profile.pricing else 0
    breadth = (
        len(profile.key_differentiators) * 8
        + len(profile.notable_customers) * 5
        + tiers_count * 6
        + (10 if profile.target_segment else 0)
    )

    # Depth
    depth = (
        len(profile.structured_signals) * 7
        + len(profile.recent_linkedin_signals) * 5
        + len(profile.weaknesses) * 3
        + (10 if profile.one_liner else 0)
    )

    # Global
    age = _age_years(profile.founded_year)
    funding_score = 0.0
    if profile.funding_total_usd:
        funding_score = min(40, profile.funding_total_usd / 5_000_000)  # $200M ≈ 40 pts
    hq_outside_fr = 0
    if profile.hq and profile.hq.country and profile.hq.country.lower() not in {"france", "fr"}:
        hq_outside_fr = 15
    global_ = min(35, age * 2) + funding_score + hq_outside_fr

    # Developer
    dev_hits = _dev_signal_count(
        profile.one_liner,
        profile.differentiator,
        profile.key_differentiators,
    )
    developer = 25 + dev_hits * 18

    # Pricing — free plan / SMB-friendly entry tier
    pricing_score = 50.0
    if profile.pricing:
        if profile.pricing.free_plan:
            pricing_score = 90
        elif profile.pricing.tiers:
            prices = [
                t.price_monthly_usd
                for t in profile.pricing.tiers
                if t.price_monthly_usd is not None
            ]
            if prices:
                min_price = min(prices)
                if min_price == 0:
                    pricing_score = 88
                elif min_price < 30:
                    pricing_score = 75
                elif min_price < 100:
                    pricing_score = 60
                elif min_price < 300:
                    pricing_score = 45
                else:
                    pricing_score = 30

    # Trust
    employees_int = _extract_int(
        profile.employee_count.value if profile.employee_count else None
    )
    funding_usd = profile.funding_total_usd or 0
    trust = (
        min(30, age * 2)
        + min(25, employees_int / 20)
        + min(25, funding_usd / 4_000_000)
        + len(profile.notable_customers) * 3
        + len(profile.key_investors) * 2
    )

    return [
        _clamp(breadth),
        _clamp(depth),
        _clamp(global_),
        _clamp(developer),
        _clamp(pricing_score),
        _clamp(trust),
    ]


def run(
    subject: CompanyProfile,
    competitors: list[CompetitorProfile],
) -> dict[str, list[float]]:
    """Produce {entity_id: [6 axis scores]} for subject + all competitors."""
    t0 = time.monotonic()
    scores: dict[str, list[float]] = {}
    subject_id = _slug(subject.name)
    scores[subject_id] = _score_subject(subject)

    for c in competitors:
        cid = _slug(c.name)
        if cid in scores:
            # Duplicate slug — keep first (matches transform behaviour)
            continue
        scores[cid] = _score_competitor(c)

    logger.info(
        "phase=SYNTHESIZE status=ok entities=%d duration=%.2fs",
        len(scores),
        time.monotonic() - t0,
    )
    return scores


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.synthesize <pipeline_run.json>", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(open(sys.argv[1]).read())
    from models.pipeline import PipelineRun
    pr = PipelineRun.model_validate(raw)
    if not pr.company_profile:
        print("company_profile missing", file=sys.stderr)
        sys.exit(1)
    result = run(pr.company_profile, pr.competitors)
    print(json.dumps(result, indent=2))
