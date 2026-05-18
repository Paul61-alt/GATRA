from typing import List, Optional
from pydantic import BaseModel

from models.company import DataPoint, HQ


class PricingTier(BaseModel):
    name: Optional[str] = None
    price_monthly_usd: Optional[float] = None
    price_annual_usd: Optional[float] = None
    price_monthly_eur: Optional[DataPoint] = None   # kept for backward compat
    price_annual_eur: Optional[DataPoint] = None    # kept for backward compat
    features: List[str] = []
    target: Optional[str] = None


class PricingSignal(BaseModel):
    tiers: List[PricingTier] = []
    free_plan: Optional[bool] = None
    recent_changes: Optional[str] = None
    source_url: Optional[str] = None
    extracted_at: str


class LinkedInSignal(BaseModel):
    date: Optional[str] = None
    author: Optional[str] = None
    signal: str
    source_url: Optional[str] = None


class RecentSignal(BaseModel):
    date: Optional[str] = None
    headline: str
    source_url: Optional[str] = None
    type: Optional[str] = None  # funding | product | hiring | partnership | press


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
    key_investors: List[str] = []

    # ── Team & size ───────────────────────────────────────────────
    employee_count: Optional[DataPoint] = None

    # ── Positioning ───────────────────────────────────────────────
    one_liner: Optional[str] = None
    differentiator: Optional[str] = None            # kept for compat (first of key_differentiators)
    key_differentiators: List[str] = []
    target_segment: Optional[str] = None
    notable_customers: List[str] = []
    weaknesses: List[str] = []

    # ── Pricing ───────────────────────────────────────────────────
    pricing: Optional[PricingSignal] = None

    # ── Signals ───────────────────────────────────────────────────
    recent_signals: List[str] = []                  # kept for compat with transform.py (List[str])
    structured_signals: List[RecentSignal] = []

    # ── LinkedIn ──────────────────────────────────────────────────
    linkedin_url: Optional[str] = None
    founder_linkedin_urls: List[str] = []
    recent_linkedin_signals: List[LinkedInSignal] = []

    # ── Meta ──────────────────────────────────────────────────────
    pipeline_run_id: str
    analysis_version: str = "4.0"
