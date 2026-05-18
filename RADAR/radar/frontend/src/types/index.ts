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
  tech_stack: string[];
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

// ─── RadarOutput types (from /scan/stream final result) ──────────────────────

export interface ScanQuery {
  url: string;
  name: string;
  scannedAt: string;
  durationMs: number;
  sourcesScanned: number;
}

export interface FundingInfo {
  total: number;
  lastRound: string;
  lastRoundAt: string;
}

export interface PricingSummary {
  model: string;
  startsAt: number;
  mention: string;
}

export type ThreatLevel = "high" | "medium" | "low";
export type CapValue = "full" | "part" | "none" | "soon";

export interface RadarCompany {
  id: string;
  name: string;
  domain: string;
  tagline: string;
  category: string;
  subCategory: string;
  hq: string;
  hqCoords: [number, number];
  offices?: string[];
  founded?: number | null;
  employees?: number | null;
  employeeGrowth?: number;
  funding?: FundingInfo | null;
  investors?: string[];
  pricing?: PricingSummary | null;
  arr?: number | null;
  customers?: number | null;
  avgContract?: number | null;
  notable?: string[];
  isSubject?: boolean;
  similarity?: number | null;
  threat?: ThreatLevel | null;
}

export interface RadarFeature {
  group: string;
  label: string;
}

export interface RadarPricingTier {
  name: string;
  price: string;
  per: string;
  features?: string[];
}

export interface RadarFundingEvent {
  y: number;
  q: number;
  amt: number;
  round: string;
}

export interface RadarConfig {
  axes: string[];
  scores: Record<string, number[]>;
  defs: Record<string, string>;
}

export interface RadarOutput {
  query: ScanQuery;
  subject: RadarCompany;
  competitors: RadarCompany[];
  features: RadarFeature[];
  capabilities: Record<string, CapValue[]>;
  pricing: Record<string, RadarPricingTier[]>;
  funding: Record<string, RadarFundingEvent[]>;
  radar: RadarConfig;
}

// ─── Pipeline phase event (from SSE stream) ───────────────────────────────────

export type PhaseStatus = "idle" | "running" | "done" | "error";

export interface PhaseState {
  UNDERSTAND: PhaseStatus;
  DISCOVER: PhaseStatus;
  ENRICH: PhaseStatus;
}

// ─────────────────────────────────────────────────────────────────────────────

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
