import { CompetitorProfile } from "../types";

const STAGE_STYLES: Record<string, string> = {
  seed: "bg-green-900/40 text-green-300 border-green-700/40",
  "series a": "bg-blue-900/40 text-blue-300 border-blue-700/40",
  "series b": "bg-purple-900/40 text-purple-300 border-purple-700/40",
  "series c+": "bg-orange-900/40 text-orange-300 border-orange-700/40",
  public: "bg-yellow-900/40 text-yellow-300 border-yellow-700/40",
  bootstrapped: "bg-slate-800/40 text-slate-400 border-slate-600/40",
};

function stageBadge(stage: string | null) {
  if (!stage) return null;
  const key = stage.toLowerCase();
  const cls =
    Object.entries(STAGE_STYLES).find(([k]) => key.includes(k))?.[1] ??
    "bg-[#1a1a1a] text-[#666]";
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${cls}`}>
      {stage}
    </span>
  );
}

interface Props {
  competitors: CompetitorProfile[];
}

export function CompetitorGrid({ competitors }: Props) {
  if (!competitors.length) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {competitors.map((c) => (
        <div key={c.website} className="bg-[#111118] border border-[#222] rounded-lg p-4 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-white text-sm">{c.name}</p>
              <a
                href={`https://${c.website}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-[#555] hover:text-[#888] transition-colors"
              >
                {c.website}
              </a>
            </div>
            {stageBadge(c.funding_stage?.value as string | null)}
          </div>

          {c.hq && (
            <p className="text-xs text-[#666]">
              📍 {c.hq.city}, {c.hq.country}
              {c.founded_year && ` · ${c.founded_year}`}
            </p>
          )}

          {c.differentiator && (
            <p className="text-xs text-[#999] leading-relaxed">{c.differentiator}</p>
          )}

          {c.recent_signals.length > 0 && (
            <div className="pt-1 border-t border-[#1a1a1a]">
              {c.recent_signals.slice(0, 2).map((s, i) => (
                <p key={i} className="text-[10px] text-[#555] truncate">▸ {s}</p>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
