"""Maps PipelineRun → RadarOutput for data.js generation.

Fields that require a future synthesize phase (similarity, threat, features matrix,
radar scores, arr, customers, avg_contract) are filled with neutral placeholders.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from models.company import CompanyProfile, FundingRound, HQ
from models.competitor import CompetitorProfile
from models.pipeline import PipelineRun
from models.radar_output import (
    Company,
    Feature,
    FundingEvent,
    FundingInfo,
    PricingSummary,
    PricingTier,
    RadarConfig,
    RadarOutput,
    ScanQuery,
)

_DEFAULT_RADAR_AXES = ["Breadth", "Depth", "Global", "Developer", "Pricing", "Trust"]
_DEFAULT_RADAR_DEFS = {
    "Breadth": "Breadth of product surface (modules, use-cases)",
    "Depth": "Depth within core payment workflows",
    "Global": "Geographic and currency coverage",
    "Developer": "API quality, docs, embedded SDKs",
    "Pricing": "Price-competitiveness for SMB/mid-market",
    "Trust": "Compliance, brand and customer logos",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _parse_domain(website: str) -> str:
    if "://" not in website:
        website = "https://" + website
    parsed = urlparse(website)
    return parsed.netloc.lstrip("www.") or website


def _format_hq(hq: HQ | None) -> str:
    if not hq:
        return ""
    return ", ".join(p for p in [hq.city, hq.country] if p)


def _date_to_y_q(date_str: str | None) -> tuple[int, int] | None:
    """Convert "YYYY-MM" or "YYYY-MM-DD" to (year, quarter)."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return year, (month - 1) // 3 + 1
    except (ValueError, IndexError):
        return None


def _map_funding_events(rounds: list[FundingRound]) -> list[FundingEvent]:
    events: list[FundingEvent] = []
    for r in rounds:
        yq = _date_to_y_q(r.date)
        if yq is None:
            continue
        y, q = yq
        amt = round((r.amount_eur or 0) / 1_000_000, 1)  # EUR → M€
        events.append(FundingEvent(y=y, q=q, amt=amt, round_name=r.round or "Unknown"))
    return events


def _employees_int(raw) -> int | None:
    if raw is None:
        return None
    try:
        # Handle ranges like "200-500" by taking the first number
        match = re.search(r"\d+", str(raw))
        return int(match.group()) if match else None
    except (ValueError, TypeError):
        return None


def _map_subject(profile: CompanyProfile) -> Company:
    hq_str = _format_hq(profile.hq)
    hq_coords: tuple[float, float] = (
        (profile.hq.lat or 0.0, profile.hq.lng or 0.0)
        if profile.hq and (profile.hq.lat or profile.hq.lng)
        else (0.0, 0.0)
    )

    primary_market = next(
        (m.label for m in profile.markets if m.primary),
        profile.markets[0].label if profile.markets else "Technology",
    )

    funding_info = None
    if profile.funding:
        f = profile.funding
        total = float(f.total_raised_eur.value or 0) if f.total_raised_eur else 0.0
        funding_info = FundingInfo(
            total=total,
            last_round=f.last_round or "Unknown",
            last_round_at=f.last_round_date or "",
        )

    return Company(
        id=_slug(profile.name),
        name=profile.name,
        domain=profile.domain,
        tagline=profile.summary or profile.positioning or "",
        category=primary_market,
        sub_category=profile.positioning or primary_market,
        hq=hq_str,
        hq_coords=hq_coords,
        offices=[profile.hq.city] if profile.hq and profile.hq.city else [],
        founded=profile.founded_year,
        employees=_employees_int(profile.employees.value if profile.employees else None),
        employee_growth=0.0,
        funding=funding_info,
        investors=[],
        pricing=PricingSummary(model="Custom", starts_at=0, mention="Contact sales"),
        notable=profile.growth_signals[:5],
        is_subject=True,
    )


def _map_competitor(profile: CompetitorProfile) -> Company:
    hq_str = _format_hq(profile.hq)
    hq_coords: tuple[float, float] = (
        (profile.hq.lat or 0.0, profile.hq.lng or 0.0)
        if profile.hq and (profile.hq.lat or profile.hq.lng)
        else (0.0, 0.0)
    )

    pricing_model = "Custom"
    if profile.funding_stage and profile.funding_stage.value:
        pricing_model = f"{profile.funding_stage.value} stage"

    return Company(
        id=_slug(profile.name),
        name=profile.name,
        domain=_parse_domain(profile.website),
        tagline=profile.one_liner or profile.differentiator or "",
        category="Technology",
        sub_category=profile.differentiator or "Technology",
        hq=hq_str,
        hq_coords=hq_coords,
        offices=[profile.hq.city] if profile.hq and profile.hq.city else [],
        founded=profile.founded_year,
        employees=_employees_int(
            profile.employee_count.value if profile.employee_count else None
        ),
        employee_growth=0.0,
        investors=[],
        pricing=PricingSummary(model=pricing_model, starts_at=0, mention="Contact sales"),
        notable=profile.recent_signals[:5],
        # Placeholders — overwritten by synthesize phase once implemented
        similarity=0.5,
        threat="medium",
    )


def pipeline_run_to_radar_output(run: PipelineRun) -> RadarOutput:
    if not run.company_profile:
        raise ValueError("PipelineRun.company_profile is None — pipeline did not complete")

    subject = _map_subject(run.company_profile)
    competitors = [_map_competitor(c) for c in run.competitors]
    all_ids = [subject.id] + [c.id for c in competitors]

    # Funding events (subject only; competitors have no round history in current models)
    funding_dict: dict[str, list[FundingEvent]] = {cid: [] for cid in all_ids}
    if run.company_profile.funding and run.company_profile.funding.rounds:
        funding_dict[subject.id] = _map_funding_events(
            run.company_profile.funding.rounds
        )

    # Empty pricing tiers — populated by synthesize phase (still pending for tiers)
    pricing_dict: dict[str, list[PricingTier]] = {cid: [] for cid in all_ids}

    # Radar scores: from synthesize phase if available, else neutral 50/100 fallback
    if run.radar_scores:
        scores_dict = {
            cid: run.radar_scores.get(cid, [50.0] * len(_DEFAULT_RADAR_AXES))
            for cid in all_ids
        }
    else:
        scores_dict = {cid: [50.0] * len(_DEFAULT_RADAR_AXES) for cid in all_ids}
    radar = RadarConfig(
        axes=_DEFAULT_RADAR_AXES,
        scores=scores_dict,
        defs=_DEFAULT_RADAR_DEFS,
    )

    scanned_at = run.completed_at or run.created_at

    duration_ms = 0
    if run.completed_at and run.created_at:
        try:
            t0 = datetime.fromisoformat(run.created_at)
            t1 = datetime.fromisoformat(run.completed_at)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    # Aggregate unique source URLs across all phases (understand + discover + enrich)
    _all_sources: set[str] = set()
    if run.company_profile.source_urls:
        _all_sources.update(run.company_profile.source_urls)
    if run.discover_source_urls:
        _all_sources.update(run.discover_source_urls)
    for c in run.competitors:
        if c.source_urls:
            _all_sources.update(c.source_urls)
    sources_scanned = len(_all_sources)

    return RadarOutput(
        query=ScanQuery(
            url=run.company_domain,
            name=run.company_profile.name,
            scanned_at=scanned_at,
            duration_ms=duration_ms,
            sources_scanned=sources_scanned,
        ),
        subject=subject,
        competitors=competitors,
        features=[],                                    # populated by synthesize phase
        capabilities={cid: [] for cid in all_ids},     # populated by synthesize phase
        pricing=pricing_dict,
        funding=funding_dict,
        radar=radar,
    )
