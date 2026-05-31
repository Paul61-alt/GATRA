from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel
from urllib.parse import urlparse

from models.company import (
    AcquisitionInfo,
    CustomerExample,
    DataPoint,
    Funding,
    HQ,
    Investor,
    KeyPerson,
    LinkedInSignal,
    PricingTier,
)


# ── DISCOVER phase models ──────────────────────────────────────────────────────

def _normalize_domain(raw: str) -> str:
    """Strip scheme, www., trailing slash from a URL or domain string."""
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    return parsed.netloc.lstrip("www.").rstrip("/").lower()


class _CamelDiscoverModel(BaseModel):
    """Base for DISCOVER response models — emits camelCase via Pydantic alias generator.

    Matches RadarOutput convention (see radar_output.py:_CamelModel).
    """
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DiscoverCandidate(_CamelDiscoverModel):
    """Lightweight candidate returned by DISCOVER phase — enough for VC to select."""
    name: str
    domain: str    # normalized: no https://, no www., no trailing /
    tagline: str   # 1-sentence elevator pitch

    @field_validator("domain", mode="before")
    @classmethod
    def normalise_domain(cls, v: str) -> str:
        return _normalize_domain(v) if v else v


class DiscoverResult(_CamelDiscoverModel):
    """Response shape for POST /scan/discover. Emits camelCase keys."""
    run_id: str
    company_name: str
    company_domain: str
    company_tagline: str
    candidates: List[DiscoverCandidate]
    scanned_at: str   # ISO 8601
    sources_count: int


class PricingSignal(BaseModel):
    tiers: List[PricingTier] = []
    free_plan: Optional[bool] = None
    mention: Optional[str] = None              # UI tagline straight from the LLM
    starts_at_usd: Optional[float] = None      # lowest paid tier; None = sales-gated
    recent_changes: Optional[str] = None
    source_url: Optional[str] = None
    extracted_at: str


class RecentSignal(BaseModel):
    date: Optional[str] = None
    headline: str
    source_url: Optional[str] = None
    type: Optional[str] = None  # funding | product | hiring | partnership | press


class Feature(BaseModel):
    """One axis of the features matrix, shared across all competitors of a run."""
    label: str
    group: Optional[str] = None  # e.g. "Core", "Pricing", "Integrations"


class CapabilityCell(BaseModel):
    """A competitor's coverage on one Feature axis."""
    feature: str  # matches Feature.label
    value: Literal["full", "part", "none", "soon"]


class CompetitorProfile(BaseModel):
    # ── Core identity ─────────────────────────────────────────────
    name: str
    website: str
    hq: Optional[HQ] = None
    founded_year: Optional[int] = None

    # ── Financials ────────────────────────────────────────────────
    funding_stage: Optional[DataPoint] = None
    funding_total_usd: Optional[int] = None
    last_round_amount_usd: Optional[int] = None
    last_round_date: Optional[str] = None
    last_round_type: Optional[str] = None
    key_investors: List[str] = []                   # kept for legacy mode compat (string list)
    notable_investors: List[Investor] = []          # NEW: structured investors with optional domains
    funding: Optional[Funding] = None               # NEW: multi-round history for Timeline tab
    acquisition: Optional[AcquisitionInfo] = None

    # ── Team & size ───────────────────────────────────────────────
    employee_count: Optional[DataPoint] = None
    employee_growth_yoy: Optional[float] = None     # NEW: fraction (0.12 = +12%)
    key_people: List[KeyPerson] = []                # NEW: name/role/background/linkedin

    # ── Traction ──────────────────────────────────────────────────
    arr_usd: Optional[DataPoint] = None             # NEW
    customer_count: Optional[DataPoint] = None      # NEW
    avg_contract_usd: Optional[float] = None        # NEW

    # ── Positioning ───────────────────────────────────────────────
    one_liner: Optional[str] = None
    differentiator: Optional[str] = None            # kept for compat (first of key_differentiators)
    key_differentiators: List[str] = []
    target_segment: Optional[str] = None
    notable_customers: List[CustomerExample] = []
    weaknesses: List[str] = []

    # ── GTM dimensions (NEW) ──────────────────────────────────────
    business_model: Optional[DataPoint] = None      # B2B / B2C / B2B2C / Marketplace / API
    gtm_motion: Optional[DataPoint] = None          # sales-led / product-led / marketing-led / community-led
    pricing_model_kind: Optional[DataPoint] = None  # Freemium / Subscription / Usage / Enterprise / Hybrid
    geo_coverage: Optional[str] = None              # Local / National / Regional / Global

    # ── Pricing ───────────────────────────────────────────────────
    pricing: Optional[PricingSignal] = None

    # ── Features matrix (NEW, Lane 5) ─────────────────────────────
    features: List[Feature] = []                    # ⚠ same axes across cohort (run-level)
    capabilities: List[CapabilityCell] = []         # this competitor's coverage per feature

    # ── Signals ───────────────────────────────────────────────────
    recent_signals: List[str] = []                  # kept for compat with transform.py (List[str])
    structured_signals: List[RecentSignal] = []

    # ── LinkedIn ──────────────────────────────────────────────────
    linkedin_url: Optional[str] = None
    founder_linkedin_urls: List[str] = []
    recent_linkedin_signals: List[LinkedInSignal] = []

    # ── Sources ───────────────────────────────────────────────────
    source_urls: List[str] = []

    # ── Meta ──────────────────────────────────────────────────────
    pipeline_run_id: str
    analysis_version: str = "5.0"  # bumped: 5-lanes architecture
