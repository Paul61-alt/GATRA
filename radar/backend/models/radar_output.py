"""Pydantic models mirroring the data.js RadarData structure expected by the frontend."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

CapValue = Literal["full", "part", "none", "soon"]
ThreatLevel = Literal["high", "medium", "low"]
FundingStatus = Literal["enriched", "bootstrapped", "stealth", "not_found", "pending"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ScanQuery(_CamelModel):
    url: str
    name: str
    scanned_at: str  # ISO 8601
    duration_ms: int
    sources_scanned: int


class FundingRoundOut(_CamelModel):
    round: Optional[str] = None
    amount_eur: Optional[float] = None
    date: Optional[str] = None
    lead: Optional[str] = None


class FundingInfo(_CamelModel):
    # Backwards-compat fields (existing frontend keys)
    total: float  # in EUR (same currency as pipeline)
    last_round: str
    last_round_at: str  # "YYYY-MM"
    # F2: explicit status + provenance so empty timelines render distinct empty-states
    status: FundingStatus = "not_found"
    rounds: list[FundingRoundOut] = Field(default_factory=list)
    total_raised_eur: Optional[float] = None
    last_round_amount_eur: Optional[float] = None
    last_round_date: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "low"
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    extracted_at: Optional[str] = None


class PricingSummary(_CamelModel):
    model: str
    starts_at: Optional[float] = None   # None = sales-gated (no public price)
    mention: str
    sales_gated: bool = False


class NamedEntity(BaseModel):
    """Logo-ready entity: name + domain for img.logo.dev lookup.
    Plain BaseModel (no _CamelModel) — fields stay snake_case in JSON."""
    name: str
    domain: Optional[str] = None
    segment: Optional[str] = None    # customer segment classification
    industry: Optional[str] = None   # e.g. "Professional Services"
    evidence: Optional[str] = None   # outcome evidence (e.g. "49% turnover reduction")


class KeyPerson(BaseModel):
    """Founder/executive for Overview display. snake_case JSON."""
    name: str
    role: Optional[str] = None
    linkedin: Optional[str] = None  # full URL: https://linkedin.com/in/...
    background: Optional[str] = None  # raw bio sentence (parsed for prior companies in UI)


class ConfidencedValue(_CamelModel):
    """Mirrors backend DataPoint: value + confidence + provenance."""
    value: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    extracted_at: Optional[str] = None


class NewsItemOut(_CamelModel):
    date: Optional[str] = None
    headline: str
    source_url: Optional[str] = None


class LinkedInPostOut(_CamelModel):
    """A recent LinkedIn post, rendered as a link-preview card on the company screen."""
    date: Optional[str] = None
    author: Optional[str] = None
    excerpt: Optional[str] = None     # post body preview (falls back to signal headline)
    image_url: Optional[str] = None   # usually null — card is text-only when absent
    source_url: Optional[str] = None


class AcquisitionOut(_CamelModel):
    acquired: bool = False
    acquirer: Optional[str] = None
    amount_eur: Optional[float] = None
    year: Optional[int] = None
    source_url: Optional[str] = None


class MarketOut(_CamelModel):
    id: str
    label: str
    primary: bool = False


class Company(_CamelModel):
    id: str
    name: str
    domain: str
    tagline: str
    category: str
    sub_category: str
    hq: str
    hq_coords: tuple[float, float]
    offices: list[str] = Field(default_factory=list)
    founded: Optional[int] = None
    employees: Optional[int] = None
    employee_growth: float = 0.0
    funding: Optional[FundingInfo] = None
    investors: list[str] = Field(default_factory=list)
    pricing: Optional[PricingSummary] = None
    customers: Optional[int] = None
    avg_contract: Optional[float] = None
    arr: Optional[float] = None  # EUR
    notable: list[str] = Field(default_factory=list)
    # Frontend reads these in snake_case (overrides _CamelModel default)
    notable_customers: list[NamedEntity] = Field(
        default_factory=list, serialization_alias="notable_customers"
    )
    notable_investors: list[NamedEntity] = Field(
        default_factory=list, serialization_alias="notable_investors"
    )
    key_people: list[KeyPerson] = Field(
        default_factory=list, serialization_alias="key_people"
    )
    is_subject: bool = False
    similarity: Optional[float] = None
    threat: Optional[ThreatLevel] = None
    # GTM ribbon fields — snake_case in JSON
    business_model: Optional[str] = Field(default=None, serialization_alias="business_model")
    gtm_motion: Optional[str] = Field(default=None, serialization_alias="gtm_motion")
    pricing_model_kind: Optional[str] = Field(default=None, serialization_alias="pricing_model_kind")
    target_segment: Optional[str] = Field(default=None, serialization_alias="target_segment")
    geo_coverage: Optional[str] = Field(default=None, serialization_alias="geo_coverage")

    # V2 Overview fields — high-signal data exposed for redesign
    positioning: Optional[str] = None
    key_differentiator: Optional[ConfidencedValue] = None
    top_3_features: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    recent_news: list[NewsItemOut] = Field(default_factory=list)
    recent_linkedin_posts: list[LinkedInPostOut] = Field(default_factory=list)
    growth_signals: list[str] = Field(default_factory=list)
    funding_rounds: list[FundingRoundOut] = Field(default_factory=list)
    funding_stage: Optional[str] = None
    equity_story: Optional[str] = None
    acquisition: Optional[AcquisitionOut] = None
    target_verticals: list[str] = Field(default_factory=list)
    markets: list[MarketOut] = Field(default_factory=list)


class Feature(_CamelModel):
    group: str
    label: str


class PricingTier(_CamelModel):
    name: str
    price: str
    per: str
    features: list[str] = Field(default_factory=list)


class FundingEvent(_CamelModel):
    y: int
    q: int
    amt: float
    round_name: str = Field(alias="round")  # "round" is a Python builtin; alias keeps JS key correct


class RadarConfig(_CamelModel):
    axes: list[str]
    scores: dict[str, list[float]]
    defs: dict[str, str]


class RadarOutput(_CamelModel):
    query: ScanQuery
    subject: Company
    competitors: list[Company]
    features: list[Feature]
    capabilities: dict[str, list[CapValue]]
    pricing: dict[str, list[PricingTier]]
    funding: dict[str, list[FundingEvent]]
    radar: RadarConfig
