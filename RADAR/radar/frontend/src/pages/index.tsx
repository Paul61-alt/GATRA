import { useState, FormEvent } from "react";
import {
  RadarOutput,
  RadarCompany,
  CompanyProfile,
  CompetitorProfile,
} from "../types";
import { CompanyCard } from "../components/CompanyCard";
import { CompetitorGrid } from "../components/CompetitorGrid";
import { CompetitorMap } from "../components/CompetitorMap";
import { PricingSignalFeed } from "../components/PricingSignalFeed";
import { TopBar } from "../components/landing/TopBar";
import { Hero } from "../components/landing/Hero";
import { Footer } from "../components/landing/Footer";
import { OperationsConsole } from "../components/loading/OperationsConsole";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ─── Adapters: map RadarOutput → legacy component prop shapes ────────────────

function parseHqString(hq: string): { city: string | null; country: string | null } {
  if (!hq) return { city: null, country: null };
  const parts = hq.split(",").map((s) => s.trim());
  if (parts.length >= 2) {
    return { city: parts[0], country: parts[parts.length - 1] };
  }
  return { city: hq, country: null };
}

function radarCompanyToCompanyProfile(c: RadarCompany): CompanyProfile {
  const { city, country } = parseHqString(c.hq);
  const [lat, lng] = c.hqCoords ?? [null, null];

  return {
    name: c.name,
    domain: c.domain,
    summary: c.tagline ?? null,
    founded_year: c.founded ?? null,
    hq: { city, country, lat: lat ?? null, lng: lng ?? null },
    employees:
      c.employees != null
        ? { value: c.employees, confidence: "medium", source_url: null, extracted_at: "" }
        : null,
    funding: c.funding
      ? {
          total_raised_eur: {
            value: c.funding.total,
            confidence: "medium",
            source_url: null,
            extracted_at: "",
          },
          last_round: c.funding.lastRound ?? null,
          last_round_date: c.funding.lastRoundAt ?? null,
          rounds: [],
        }
      : null,
    growth_signals: c.notable ?? [],
    tech_stack: [],
    positioning: c.tagline ?? null,
    markets: c.category ? [{ id: c.category, label: c.category, primary: true }] : [],
    pipeline_run_id: c.id,
    analysis_version: "radar-v2",
  };
}

function radarCompanyToCompetitorProfile(c: RadarCompany): CompetitorProfile {
  const { city, country } = parseHqString(c.hq);
  const [lat, lng] = c.hqCoords ?? [null, null];

  return {
    name: c.name,
    website: c.domain,
    hq: { city, country, lat: lat ?? null, lng: lng ?? null },
    founded_year: c.founded ?? null,
    funding_stage: c.funding?.lastRound
      ? { value: c.funding.lastRound, confidence: "medium", source_url: null, extracted_at: "" }
      : null,
    employee_count:
      c.employees != null
        ? { value: c.employees, confidence: "medium", source_url: null, extracted_at: "" }
        : null,
    one_liner: c.tagline ?? null,
    differentiator: c.tagline ?? null,
    pricing: c.pricing
      ? {
          tiers: [
            {
              name: c.pricing.model ?? "Paid",
              price_monthly_eur: {
                value: c.pricing.startsAt,
                confidence: "medium",
                source_url: null,
                extracted_at: "",
              },
              price_annual_eur: null,
              features: [],
            },
          ],
          free_plan: null,
          source_url: null,
          extracted_at: "",
        }
      : null,
    recent_signals: c.notable ?? [],
    pipeline_run_id: c.id,
    analysis_version: "radar-v2",
  };
}

// ─── Background effects ───────────────────────────────────────────────────────

function GridBackground() {
  return (
    <div
      aria-hidden
      className="fixed inset-0 pointer-events-none"
      style={{
        backgroundImage:
          "linear-gradient(var(--line-subtle) 1px, transparent 1px), linear-gradient(90deg, var(--line-subtle) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
        opacity: 0.05,
        zIndex: 0,
      }}
    />
  );
}

function ScanLine() {
  return (
    <div
      aria-hidden
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: 0 }}
    >
      <div
        className="animate-scan w-full"
        style={{
          height: "1px",
          background:
            "linear-gradient(90deg, transparent 0%, var(--accent-500) 50%, transparent 100%)",
          opacity: 0.03,
        }}
      />
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function IndexPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RadarOutput | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const query = url.trim();
    if (!query) return;
    setError(null);
    setResult(null);
    setLoading(true);
  }

  function runQuery(query: string) {
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    setResult(null);
    setUrl(trimmed);
    setLoading(true);
  }

  const subjectProfile = result ? radarCompanyToCompanyProfile(result.subject) : null;
  const competitorProfiles = result
    ? result.competitors.map(radarCompanyToCompetitorProfile)
    : [];
  const isIdle = !loading && !result && !error;

  return (
    <div className="min-h-screen bg-surface-base text-fg-primary">
      {/* Landing */}
      {isIdle && (
        <>
          <GridBackground />
          <ScanLine />
          <TopBar />
          <Hero
            url={url}
            setUrl={setUrl}
            onSubmit={handleSubmit}
            onRunQuery={runQuery}
            disabled={loading}
          />
          <Footer />
        </>
      )}

      {/* Operations Console — shown while scan is in progress */}
      {loading && !result && (
        <OperationsConsole
          query={url}
          apiUrl={API_URL}
          onResult={(r) => {
            setResult(r);
            setLoading(false);
          }}
          onError={(e) => {
            setError(e);
            setLoading(false);
          }}
        />
      )}

      {/* Error state (post-load, not handled by console) */}
      {!loading && error && (
        <div className="max-w-6xl mx-auto px-6 py-12">
          <div className="flex items-center justify-between mb-8">
            <span className="font-mono font-semibold tracking-tight text-fg-primary">RADAR</span>
            <span className="font-mono text-sm text-fg-muted">{url}</span>
          </div>
          <div className="bg-tint-error border border-status-error/30 rounded-md p-4 text-status-error text-sm font-mono">
            {error}
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="max-w-6xl mx-auto px-6 py-12 space-y-10">
          <div className="flex items-center justify-between">
            <span className="font-mono font-semibold tracking-tight text-fg-primary">RADAR</span>
            <span className="font-mono text-sm text-fg-muted">{url}</span>
          </div>

          <div className="space-y-8">
            <p className="text-xs text-fg-muted font-mono">
              Scanned in {(result.query.durationMs / 1000).toFixed(1)}s ·{" "}
              {result.query.sourcesScanned} sources
            </p>

            {subjectProfile && <CompanyCard profile={subjectProfile} />}

            {competitorProfiles.length > 0 && (
              <>
                <div>
                  <h2 className="text-sm text-fg-muted uppercase tracking-wider mb-4">
                    {competitorProfiles.length} Competitors
                  </h2>
                  <CompetitorMap competitors={competitorProfiles} />
                </div>
                <CompetitorGrid competitors={competitorProfiles} />
                <PricingSignalFeed competitors={competitorProfiles} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
