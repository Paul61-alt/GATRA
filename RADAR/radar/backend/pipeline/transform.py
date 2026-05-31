"""Maps PipelineRun → RadarOutput for data.js generation.

Fields that require a future synthesize phase (features matrix, radar scores)
are filled with neutral placeholders. Similarity and threat are derived from
heuristics. All Positioning-chart fields (arr, funding_rounds, acquisition,
notable_*) are mapped symmetrically for subject and competitors.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from models.company import CompanyProfile, FundingRound, HQ
from models.competitor import CompetitorProfile
from models.pipeline import PipelineRun
from models.radar_output import (
    AcquisitionOut,
    Company,
    ConfidencedValue,
    Feature,
    FundingEvent,
    FundingInfo,
    FundingRoundOut,
    FundingStatus,
    KeyPerson,
    LinkedInPostOut,
    MarketOut,
    NamedEntity,
    NewsItemOut,
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


def _linkedin_posts_out(profile) -> list[LinkedInPostOut]:
    """Map recent LinkedIn signals → preview cards (excerpt falls back to headline). Cap 5.

    Accepts CompetitorProfile (has recent_linkedin_signals) or CompanyProfile (does
    not — yields [] via getattr until the subject carries LinkedIn signals).
    """
    out: list[LinkedInPostOut] = []
    for s in (getattr(profile, "recent_linkedin_signals", None) or [])[:5]:
        excerpt = (s.excerpt or s.signal or "").strip()
        if not excerpt:
            continue
        out.append(LinkedInPostOut(
            date=s.date,
            author=s.author,
            excerpt=excerpt,
            image_url=s.image_url,
            source_url=s.source_url,
        ))
    return out


def _map_pricing_tiers(profile: CompetitorProfile) -> list[PricingTier]:
    """Map CompetitorProfile.pricing.tiers → list[radar_output.PricingTier]."""
    if not profile.pricing:
        return []
    tiers: list[PricingTier] = []
    # Synthesize a Free tier when free_plan=True but no tier records present
    if profile.pricing.free_plan and not profile.pricing.tiers:
        tiers.append(PricingTier(name="Free", price="$0", per="month", features=[]))
    for t in profile.pricing.tiers:
        if t.price_monthly_usd is not None:
            price_str = "$0" if t.price_monthly_usd == 0 else f"${t.price_monthly_usd:,.0f}"
            per = "month"
        elif t.price_annual_usd is not None:
            price_str = f"${t.price_annual_usd:,.0f}"
            per = "year"
        else:
            price_str, per = "Custom", "contact"
        tiers.append(PricingTier(
            name=t.name or "Plan",
            price=price_str,
            per=per,
            features=(t.features or [])[:6],  # cap at 6 for UI
        ))
    return tiers


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


def _coerce_int(raw) -> int | None:
    """Strip commas, '+', whitespace; accept '25,000+' or '500 customers'."""
    if raw is None:
        return None
    try:
        match = re.search(r"\d[\d,]*", str(raw))
        return int(match.group().replace(",", "")) if match else None
    except (ValueError, TypeError):
        return None


def _coerce_float(raw) -> float | None:
    """Accept '100M', '$50,000,000', '25.5'. Returns None on garbage."""
    if raw is None:
        return None
    try:
        s = str(raw).replace(",", "").replace("$", "").replace("€", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if not match:
            return None
        value = float(match.group())
        # Suffix multipliers (M / B / K)
        rest = s[match.end():].upper().strip()
        if rest.startswith("B"):
            value *= 1_000_000_000
        elif rest.startswith("M"):
            value *= 1_000_000
        elif rest.startswith("K"):
            value *= 1_000
        return value
    except (ValueError, TypeError):
        return None


def _derive_funding_status(profile) -> FundingStatus:
    """F2: classify funding posture so the frontend can render distinct empty-states.
    LLM-explicit only — no founded_year heuristic (per F2 plan decision)."""
    if profile is None:
        return "pending"
    stage_raw = getattr(profile, "funding_stage", None)
    stage_val = ""
    if stage_raw is not None:
        sv = stage_raw.value if hasattr(stage_raw, "value") else stage_raw
        stage_val = (sv or "").strip().lower()
    if stage_val in ("bootstrapped", "self-funded"):
        return "bootstrapped"
    if stage_val == "stealth":
        return "stealth"
    f = getattr(profile, "funding", None)
    has_money = bool(
        (f and (f.rounds or f.total_raised_eur))
        or getattr(profile, "funding_total_usd", None)
        or getattr(profile, "last_round_type", None)
    )
    return "enriched" if has_money else "not_found"


def _build_funding_info(profile) -> FundingInfo:
    """F2: always return a FundingInfo (never None) so the frontend can branch on status.
    Backwards-compat fields (total / last_round / last_round_at) kept populated."""
    status = _derive_funding_status(profile)
    total_eur = 0.0
    last_round = ""
    last_round_at = ""
    rounds_out: list[FundingRoundOut] = []
    source_url = None
    evidence = None
    extracted_at = None
    confidence = "low"

    f = getattr(profile, "funding", None) if profile is not None else None
    if f:
        if f.total_raised_eur:
            total_eur = float(_coerce_float(f.total_raised_eur.value) or 0.0)
            source_url = f.total_raised_eur.source_url
            evidence = f.total_raised_eur.evidence
            extracted_at = f.total_raised_eur.extracted_at
            confidence = f.total_raised_eur.confidence or "low"
        last_round = f.last_round or getattr(profile, "last_round_type", None) or ""
        last_round_at = f.last_round_date or getattr(profile, "last_round_date", None) or ""
        for r in (f.rounds or []):
            rounds_out.append(FundingRoundOut(
                round=r.round,
                amount_eur=float(r.amount_eur) if r.amount_eur is not None else None,
                date=r.date,
                lead=r.lead,
            ))
    elif profile is not None and (getattr(profile, "funding_total_usd", None) or getattr(profile, "last_round_type", None)):
        # Competitor fallback: USD → EUR (rough)
        total_eur = float(getattr(profile, "funding_total_usd", None) or 0) * 0.92
        last_round = getattr(profile, "last_round_type", None) or ""
        last_round_at = getattr(profile, "last_round_date", None) or ""

    # Derive last_round_amount_eur: prefer most recent dated round, fall back to USD field
    last_round_amount_eur: Optional[float] = None
    dated_rounds = [r for r in rounds_out if r.amount_eur is not None and r.date]
    if dated_rounds:
        latest = max(dated_rounds, key=lambda r: r.date or "")
        last_round_amount_eur = latest.amount_eur
    elif profile is not None and getattr(profile, "last_round_amount_usd", None):
        last_round_amount_eur = float(profile.last_round_amount_usd) * 0.92

    # Backwards-compat fallback labels
    if not last_round:
        last_round = {
            "bootstrapped": "Bootstrapped",
            "stealth": "Stealth",
            "pending": "Pending",
            "not_found": "Unknown",
        }.get(status, "Unknown")

    return FundingInfo(
        total=total_eur,
        last_round=last_round,
        last_round_at=last_round_at,
        status=status,
        rounds=rounds_out,
        total_raised_eur=total_eur if total_eur > 0 else None,
        last_round_amount_eur=last_round_amount_eur,
        last_round_date=last_round_at or None,
        confidence=confidence,
        source_url=source_url,
        evidence=evidence,
        extracted_at=extracted_at,
    )


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

    funding_info = _build_funding_info(profile)

    # ARR (USD → EUR) for subject
    arr_eur: float | None = None
    if profile.arr_usd:
        arr_usd_val = _parse_money_usd(profile.arr_usd.value)
        arr_eur = arr_usd_val * 0.92 if arr_usd_val is not None else None

    # V2 Overview field mapping — additive plumbing for the redesigned screen
    key_diff = None
    if profile.key_differentiator:
        kd = profile.key_differentiator
        key_diff = ConfidencedValue(
            value=str(kd.value) if kd.value is not None else None,
            confidence=kd.confidence,
            source_url=kd.source_url,
            evidence=kd.evidence,
            extracted_at=kd.extracted_at,
        )

    funding_rounds_out = []
    if profile.funding and profile.funding.rounds:
        for r in profile.funding.rounds:
            funding_rounds_out.append(FundingRoundOut(
                round=r.round,
                amount_eur=float(r.amount_eur) if r.amount_eur is not None else None,
                date=r.date,
                lead=r.lead,
            ))

    news_out = [
        NewsItemOut(date=n.date, headline=n.headline, source_url=n.source_url)
        for n in (profile.recent_news or [])
        if n.headline
    ]

    linkedin_posts_out = _linkedin_posts_out(profile)

    acquisition_out = None
    if profile.acquisition:
        a = profile.acquisition
        acquisition_out = AcquisitionOut(
            acquired=a.acquired,
            acquirer=a.acquirer,
            amount_eur=float(a.amount_eur) if a.amount_eur is not None else None,
            year=a.year,
            source_url=a.source_url,
        )

    markets_out = [
        MarketOut(id=m.id, label=m.label, primary=m.primary)
        for m in (profile.markets or [])
    ]

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
        employee_growth=profile.employee_growth_yoy or 0.0,
        funding=funding_info,
        investors=[inv.name for inv in profile.notable_investors] if profile.notable_investors else [],
        pricing=PricingSummary(model="Custom", starts_at=None, mention="Contact sales", sales_gated=True),
        customers=_coerce_int(profile.customer_count.value) if profile.customer_count else None,
        arr=arr_eur,
        notable=profile.growth_signals[:5],
        notable_customers=[
            NamedEntity(
                name=c.name,
                domain=c.domain,
                segment=c.segment,
                industry=c.industry,
                evidence=c.evidence,
            )
            for c in profile.notable_customers
            if c.name
        ],
        notable_investors=[
            NamedEntity(name=i.name, domain=i.domain)
            for i in profile.notable_investors
            if i.name
        ],
        key_people=[
            KeyPerson(
                name=p.name,
                role=p.role,
                linkedin=p.linkedin,
                background=p.background,
            )
            for p in (profile.key_people or [])
            if p.name
        ],
        is_subject=True,
        business_model=profile.business_model.value if profile.business_model else None,
        gtm_motion=profile.gtm_motion.value if profile.gtm_motion else None,
        pricing_model_kind=profile.pricing_model.value if profile.pricing_model else None,
        target_segment=profile.target_segment.value if profile.target_segment else None,
        geo_coverage=profile.geo_coverage,
        # V2 fields
        positioning=profile.positioning,
        key_differentiator=key_diff,
        top_3_features=list(profile.top_3_features or []),
        tech_stack=list(profile.tech_stack or []),
        recent_news=news_out,
        recent_linkedin_posts=linkedin_posts_out,
        growth_signals=list(profile.growth_signals or []),
        funding_rounds=funding_rounds_out,
        funding_stage=profile.funding_stage,
        equity_story=profile.equity_story,
        acquisition=acquisition_out,
        target_verticals=list(profile.target_verticals or []),
        markets=markets_out,
    )


def _threat_from_score(score: int) -> str:
    """Map 0-100 threat score → ThreatLevel string."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    return "low"


_STOPWORDS = frozenset({
    "with", "that", "this", "from", "into", "their", "have", "been",
    "more", "than", "your", "will", "about", "which", "when", "what",
    "also", "using", "based", "platform", "software", "solution",
    "tool", "tools", "system", "helps", "help", "make",
})


def _compute_similarity(subject: CompanyProfile, competitor: CompetitorProfile) -> float:
    """Heuristic similarity score 0.0–1.0 based on keyword overlap.

    Compares subject positioning/markets vs competitor one_liner/differentiators.
    Jaccard similarity scaled to 0.50–1.00 range (all listed competitors are
    at least partially related).
    """
    subj_text = " ".join(filter(None, [
        subject.positioning or "",
        " ".join(m.label for m in (subject.markets or [])),
        subject.summary or "",
        " ".join(subject.top_3_features or []),
    ])).lower()

    comp_text = " ".join(filter(None, [
        competitor.one_liner or "",
        competitor.differentiator or "",
        " ".join(competitor.key_differentiators or []),
        competitor.target_segment or "",
    ])).lower()

    subj_words = {w for w in re.findall(r"\b[a-z]{4,}\b", subj_text) if w not in _STOPWORDS}
    comp_words = {w for w in re.findall(r"\b[a-z]{4,}\b", comp_text) if w not in _STOPWORDS}

    if not subj_words or not comp_words:
        return 0.5

    intersection = len(subj_words & comp_words)
    union = len(subj_words | comp_words)
    jaccard = intersection / union if union else 0.0

    # Scale: typical jaccard for competitive pairs ≈ 0.02–0.15
    # Map to 0.50–1.00 so UI always shows a meaningful bar.
    return round(min(1.0, 0.5 + jaccard * 4), 2)


def _parse_money_usd(raw) -> float | None:
    """Parse a DataPoint.value or raw number into a USD float, tolerating "$12M"/"12000000"/12000000."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace("$", "").replace("€", "").upper()
    mult = 1.0
    if s.endswith("B"):
        mult, s = 1_000_000_000.0, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000.0, s[:-1]
    elif s.endswith("K"):
        mult, s = 1_000.0, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _map_competitor(
    profile: CompetitorProfile,
    threat_score: int = 50,
    similarity: float = 0.5,
) -> Company:
    hq_str = _format_hq(profile.hq)
    hq_coords: tuple[float, float] = (
        (profile.hq.lat or 0.0, profile.hq.lng or 0.0)
        if profile.hq and (profile.hq.lat or profile.hq.lng)
        else (0.0, 0.0)
    )

    # Funding info object — always populated (F2: status enum drives empty-state rendering)
    funding_info = _build_funding_info(profile)

    # ARR + avg contract: USD → EUR
    arr_eur: float | None = None
    if profile.arr_usd:
        arr_usd_val = _parse_money_usd(profile.arr_usd.value)
        arr_eur = arr_usd_val * 0.92 if arr_usd_val is not None else None
    avg_contract_eur: float | None = None
    if profile.avg_contract_usd is not None:
        avg_contract_eur = float(profile.avg_contract_usd) * 0.92

    funding_rounds_out: list[FundingRoundOut] = []
    if profile.funding and profile.funding.rounds:
        for r in profile.funding.rounds:
            funding_rounds_out.append(FundingRoundOut(
                round=r.round,
                amount_eur=float(r.amount_eur) if r.amount_eur is not None else None,
                date=r.date,
                lead=r.lead,
            ))

    acquisition_out: AcquisitionOut | None = None
    if profile.acquisition:
        a = profile.acquisition
        acquisition_out = AcquisitionOut(
            acquired=a.acquired,
            acquirer=a.acquirer,
            amount_eur=float(a.amount_eur) if a.amount_eur is not None else None,
            year=a.year,
            source_url=a.source_url,
        )

    news_out: list[NewsItemOut] = []
    for s in (profile.structured_signals or []):
        if s.headline:
            news_out.append(NewsItemOut(date=s.date, headline=s.headline, source_url=s.source_url))

    linkedin_posts_out = _linkedin_posts_out(profile)

    # Pricing summary (Lane 2)
    pricing_summary = PricingSummary(model="Custom", starts_at=None, mention="Contact sales", sales_gated=True)
    if profile.pricing:
        model_kind = profile.pricing_model_kind.value if profile.pricing_model_kind else "Custom"
        # Prefer the LLM-extracted entry price; fall back to scanning tiers.
        starts_at = profile.pricing.starts_at_usd
        if starts_at is None:
            for t in profile.pricing.tiers:
                if t.price_monthly_usd is not None and t.price_monthly_usd > 0:
                    starts_at = int(t.price_monthly_usd)
                    break
        # Sales-gated = no public entry price and no free plan. A known entry
        # price (even for Enterprise-model vendors) is shown, not hidden.
        sales_gated = (not profile.pricing.free_plan) and (
            starts_at is None or starts_at == 0
        )
        # Use the LLM mention verbatim; only synthesize one when missing.
        mention = profile.pricing.mention
        if not mention:
            if profile.pricing.free_plan:
                mention = f"Free + paid from ${int(starts_at)}/mo" if starts_at else "Free plan available"
            elif starts_at:
                mention = f"Starts at ${int(starts_at)}/mo"
            else:
                mention = "Contact sales"
        pricing_summary = PricingSummary(
            model=model_kind, starts_at=starts_at, mention=mention, sales_gated=sales_gated
        )

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
        employee_growth=profile.employee_growth_yoy or 0.0,
        funding=funding_info,
        investors=[i.name for i in profile.notable_investors] if profile.notable_investors else [],
        pricing=pricing_summary,
        customers=int(profile.customer_count.value) if profile.customer_count and profile.customer_count.value else None,
        notable=profile.recent_signals[:5],
        notable_customers=[
            NamedEntity(
                name=c.name,
                domain=c.domain,
                segment=c.segment,
                evidence=c.evidence,
            )
            for c in (profile.notable_customers or [])
            if c.name
        ],
        notable_investors=[
            NamedEntity(name=i.name, domain=i.domain)
            for i in (profile.notable_investors or [])
            if i.name
        ],
        key_people=[
            KeyPerson(
                name=p.name,
                role=p.role,
                linkedin=p.linkedin,
                background=p.background,
            )
            for p in (profile.key_people or [])[:5]
            if p.name
        ],
        business_model=profile.business_model.value if profile.business_model else None,
        gtm_motion=profile.gtm_motion.value if profile.gtm_motion else None,
        pricing_model_kind=profile.pricing_model_kind.value if profile.pricing_model_kind else None,
        target_segment=profile.target_segment,
        geo_coverage=profile.geo_coverage,
        # Extended fields — symmetric with _map_subject for Positioning charts
        arr=arr_eur,
        avg_contract=avg_contract_eur,
        funding_rounds=funding_rounds_out,
        funding_stage=profile.funding_stage.value if profile.funding_stage else None,
        acquisition=acquisition_out,
        recent_news=news_out,
        recent_linkedin_posts=linkedin_posts_out,
        growth_signals=list(profile.recent_signals or []),
        similarity=similarity,
        threat=_threat_from_score(threat_score),
    )


def pipeline_run_to_radar_output(run: PipelineRun) -> RadarOutput:
    if not run.company_profile:
        raise ValueError("PipelineRun.company_profile is None — pipeline did not complete")

    subject = _map_subject(run.company_profile)

    # Build threat score lookup keyed by normalized domain
    # discover.py stores scores keyed by bare domain (e.g. "testgorilla.com")
    threat_scores: dict[str, int] = run.threat_scores or {}

    competitors: list[Company] = []
    for c_profile in run.competitors:
        domain_key = _parse_domain(c_profile.website)  # strips scheme + www
        threat_score = threat_scores.get(domain_key, 50)
        similarity = _compute_similarity(run.company_profile, c_profile)
        competitors.append(_map_competitor(c_profile, threat_score=threat_score, similarity=similarity))

    all_ids = [subject.id] + [c.id for c in competitors]

    # Funding events — subject + competitors (5-lanes Lane 1 populates competitor funding.rounds)
    funding_dict: dict[str, list[FundingEvent]] = {cid: [] for cid in all_ids}
    if run.company_profile.funding and run.company_profile.funding.rounds:
        funding_dict[subject.id] = _map_funding_events(
            run.company_profile.funding.rounds
        )
    for c_profile, c_company in zip(run.competitors, competitors):
        if c_profile.funding and c_profile.funding.rounds:
            funding_dict[c_company.id] = _map_funding_events(c_profile.funding.rounds)

    # Map pricing tiers from enriched competitor profiles
    pricing_dict: dict[str, list[PricingTier]] = {subject.id: []}
    for c_profile, c_company in zip(run.competitors, competitors):
        pricing_dict[c_company.id] = _map_pricing_tiers(c_profile)

    # Features + capabilities (Lane 5). Shared features identical across all competitors
    # of the run — take from the first competitor that has them populated.
    shared_features_pyd: list[Feature] = []
    for c_profile in run.competitors:
        if c_profile.features:
            shared_features_pyd = [
                Feature(group=f.group or "Core", label=f.label)
                for f in c_profile.features
            ]
            break

    capabilities_dict: dict[str, list[str]] = {cid: [] for cid in all_ids}
    if shared_features_pyd:
        feature_labels = [f.label for f in shared_features_pyd]
        for c_profile, c_company in zip(run.competitors, competitors):
            # Build a lookup of this competitor's capability values
            cap_map = {cell.feature: cell.value for cell in (c_profile.capabilities or [])}
            # For each shared feature label, get value (default "none")
            capabilities_dict[c_company.id] = [
                cap_map.get(label, "none") for label in feature_labels
            ]

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
        features=shared_features_pyd,
        capabilities=capabilities_dict,
        pricing=pricing_dict,
        funding=funding_dict,
        radar=radar,
    )
