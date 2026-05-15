export interface DataPoint {
  value: string | number | null;
  confidence: "high" | "medium" | "low";
  source_url: string | null;
  extracted_at: string;
}

export interface HQ {
  city: string | null;
  country: string | null;
  lat: number | null;
  lng: number | null;
}

export interface FundingRound {
  round: string | null;
  amount_eur: number | null;
  date: string | null;
  lead: string | null;
}

export interface Funding {
  total_raised_eur: DataPoint | null;
  last_round: string | null;
  last_round_date: string | null;
  rounds: FundingRound[];
}

export interface Market {
  id: string;
  label: string;
  primary: boolean;
}

export interface CompanyProfile {
  name: string;
  domain: string;
  summary: string | null;
  founded_year: number | null;
  hq: HQ | null;
  employees: DataPoint | null;
  funding: Funding | null;
  growth_signals: string[];
  positioning: string | null;
  markets: Market[];
  pipeline_run_id: string;
  analysis_version: string;
}

export interface PricingTier {
  name: string | null;
  price_monthly_eur: DataPoint | null;
  price_annual_eur: DataPoint | null;
  features: string[];
}

export interface PricingSignal {
  tiers: PricingTier[];
  free_plan: boolean | null;
  source_url: string | null;
  extracted_at: string;
}

export interface CompetitorProfile {
  name: string;
  website: string;
  hq: HQ | null;
  founded_year: number | null;
  funding_stage: DataPoint | null;
  employee_count: DataPoint | null;
  one_liner: string | null;
  differentiator: string | null;
  pricing: PricingSignal | null;
  recent_signals: string[];
  pipeline_run_id: string;
  analysis_version: string;
}

export type PipelineStatus = "pending" | "running" | "completed" | "failed";

export interface PipelineRun {
  id: string;
  company_domain: string;
  status: PipelineStatus;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  company_profile: CompanyProfile | null;
  competitors: CompetitorProfile[];
  from_cache: boolean;
}
