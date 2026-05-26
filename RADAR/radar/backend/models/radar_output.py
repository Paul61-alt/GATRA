"""Pydantic models mirroring the data.js RadarData structure expected by the frontend."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

CapValue = Literal["full", "part", "none", "soon"]
ThreatLevel = Literal["high", "medium", "low"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ScanQuery(_CamelModel):
    url: str
    name: str
    scanned_at: str  # ISO 8601
    duration_ms: int
    sources_scanned: int


class FundingInfo(_CamelModel):
    total: float  # in EUR (same currency as pipeline)
    last_round: str
    last_round_at: str  # "YYYY-MM"


class PricingSummary(_CamelModel):
    model: str
    starts_at: float
    mention: str


class NamedEntity(BaseModel):
    """Logo-ready entity: name + domain for img.logo.dev lookup.
    Plain BaseModel (no _CamelModel) — fields stay snake_case in JSON."""
    name: str
    domain: Optional[str] = None


class KeyPerson(BaseModel):
    """Founder/executive for Overview display. snake_case JSON."""
    name: str
    role: Optional[str] = None
    linkedin: Optional[str] = None  # full URL: https://linkedin.com/in/...


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
    arr: Optional[float] = None
    customers: Optional[int] = None
    avg_contract: Optional[float] = None
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
