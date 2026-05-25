import { CompetitorProfile } from "../types";

interface Props {
  competitors: CompetitorProfile[];
}

export function PricingSignalFeed({ competitors }: Props) {
  const withPricing = competitors.filter((c) => c.pricing?.tiers.length);
  const withSignals = competitors.filter((c) => c.recent_signals.length);

  if (!withSignals.length && !withPricing.length) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-xs text-[#555] uppercase tracking-wider">Recent signals</h3>
      {withSignals.map((c) => (
        <div key={c.website} className="bg-[#111118] border border-[#222] rounded-lg p-3 space-y-1">
          <p className="text-sm font-semibold text-white">{c.name}</p>
          {c.recent_signals.slice(0, 3).map((s, i) => (
            <p key={i} className="text-xs text-[#888] leading-relaxed">▸ {s}</p>
          ))}
        </div>
      ))}
    </div>
  );
}
