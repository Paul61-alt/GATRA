import { useState, FormEvent } from "react";
import { PipelineRun } from "../types";
import { CompanyCard } from "../components/CompanyCard";
import { CompetitorGrid } from "../components/CompetitorGrid";
import { CompetitorMap } from "../components/CompetitorMap";
import { PricingSignalFeed } from "../components/PricingSignalFeed";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function IndexPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PipelineRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail?.error ?? `HTTP ${res.status}`);
      }

      const data: PipelineRun = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#e8e8e8]">
      <div className="max-w-6xl mx-auto px-6 py-12 space-y-10">
        {/* Header */}
        <div>
          <h1 className="font-mono text-4xl font-bold text-white tracking-tight">RADAR</h1>
          <p className="text-[#555] text-sm uppercase tracking-widest mt-1">
            Competitor Intelligence · Powered by Linkup
          </p>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="doctolib.fr"
            className="flex-1 bg-[#111118] border border-[#333] rounded-md px-4 py-2.5 text-white font-mono placeholder-[#444] focus:outline-none focus:border-[#555]"
          />
          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="bg-white text-black font-mono font-bold px-6 py-2.5 rounded-md disabled:opacity-40 hover:bg-[#e0e0e0] transition-colors"
          >
            {loading ? "Analyzing…" : "Analyze →"}
          </button>
        </form>

        {/* Error */}
        {error && (
          <div className="bg-red-900/20 border border-red-700/40 rounded-md p-4 text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-2">
            {["UNDERSTAND", "DISCOVER", "ENRICH"].map((phase) => (
              <div key={phase} className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                <span className="font-mono text-sm text-[#666]">{phase}</span>
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-8">
            {result.from_cache && (
              <p className="text-xs text-[#555] font-mono">⚡ Served from cache</p>
            )}

            {result.company_profile && (
              <CompanyCard profile={result.company_profile} />
            )}

            {result.competitors.length > 0 && (
              <>
                <div>
                  <h2 className="text-sm text-[#555] uppercase tracking-wider mb-4">
                    {result.competitors.length} Competitors
                  </h2>
                  <CompetitorMap competitors={result.competitors} />
                </div>

                <CompetitorGrid competitors={result.competitors} />

                <PricingSignalFeed competitors={result.competitors} />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
