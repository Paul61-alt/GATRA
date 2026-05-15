from typing import List, Literal, Optional
from pydantic import BaseModel


class DataPoint(BaseModel):
    value: Optional[str | int | float] = None
    confidence: Literal["high", "medium", "low"] = "medium"
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    extracted_at: str


class HQ(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class FundingRound(BaseModel):
    round: Optional[str] = None
    amount_eur: Optional[int] = None
    date: Optional[str] = None
    lead: Optional[str] = None


class Funding(BaseModel):
    total_raised_eur: Optional[DataPoint] = None
    last_round: Optional[str] = None
    last_round_date: Optional[str] = None
    rounds: List[FundingRound] = []


class Market(BaseModel):
    id: str
    label: str
    primary: bool = False


class KeyPerson(BaseModel):
    name: str
    role: Optional[str] = None
    background: Optional[str] = None
    linkedin: Optional[str] = None


class NewsItem(BaseModel):
    date: Optional[str] = None
    headline: str
    source_url: Optional[str] = None


class CompanyProfile(BaseModel):
    # Identity
    name: str
    domain: str
    website: Optional[str] = None
    summary: Optional[str] = None
    founded_year: Optional[int] = None

    # Location & size
    hq: Optional[HQ] = None
    geo_coverage: Optional[str] = None
    employees: Optional[DataPoint] = None

    # Funding
    funding: Optional[Funding] = None
    funding_stage: Optional[str] = None
    notable_investors: List[str] = []

    # Product & market
    positioning: Optional[str] = None
    markets: List[Market] = []
    target_segment: Optional[DataPoint] = None
    target_verticals: List[str] = []
    business_model: Optional[DataPoint] = None
    gtm_motion: Optional[DataPoint] = None
    pricing_model: Optional[DataPoint] = None

    # Differentiation
    key_differentiator: Optional[DataPoint] = None
    top_3_features: List[str] = []
    notable_customers: List[str] = []

    # Team
    key_people: List[KeyPerson] = []

    # Signals
    growth_signals: List[str] = []
    recent_news: List[NewsItem] = []

    # Pipeline meta
    pipeline_run_id: str
    analysis_version: str = "4.0"
