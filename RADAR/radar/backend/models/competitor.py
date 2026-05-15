from typing import List, Optional
from pydantic import BaseModel

from models.company import DataPoint, HQ


class PricingTier(BaseModel):
    name: Optional[str] = None
    price_monthly_eur: Optional[DataPoint] = None
    price_annual_eur: Optional[DataPoint] = None
    features: List[str] = []


class PricingSignal(BaseModel):
    tiers: List[PricingTier] = []
    free_plan: Optional[bool] = None
    source_url: Optional[str] = None
    extracted_at: str


class CompetitorProfile(BaseModel):
    name: str
    website: str
    hq: Optional[HQ] = None
    founded_year: Optional[int] = None
    funding_stage: Optional[DataPoint] = None
    employee_count: Optional[DataPoint] = None
    one_liner: Optional[str] = None
    differentiator: Optional[str] = None
    pricing: Optional[PricingSignal] = None
    recent_signals: List[str] = []
    pipeline_run_id: str
    analysis_version: str = "3.0"
