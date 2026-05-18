import { CompanyProfile } from "../types";

interface Props {
  profile: CompanyProfile;
}

export function CompanyCard({ profile }: Props) {
  const funding = profile.funding?.total_raised_eur?.value;
  const employees = profile.employees?.value;

  return (
    <div className="bg-[#111118] border border-[#222] rounded-lg p-5 space-y-3">
      <div>
        <h2 className="text-xl font-semibold text-white">{profile.name}</h2>
        <p className="text-sm text-[#666]">{profile.domain}</p>
      </div>

      {profile.positioning && (
        <p className="text-sm text-[#aaa] leading-relaxed">{profile.positioning}</p>
      )}

      <div className="flex flex-wrap gap-4 text-sm">
        {profile.hq?.city && (
          <span className="text-[#888]">
            📍 {profile.hq.city}, {profile.hq.country}
          </span>
        )}
        {profile.founded_year && (
          <span className="text-[#888]">🗓 Founded {profile.founded_year}</span>
        )}
        {employees && (
          <span className="text-[#888]">👥 {employees.toLocaleString()} employees</span>
        )}
        {funding && (
          <span className="text-[#888]">
            💰 €{(Number(funding) / 1_000_000).toFixed(0)}M raised
          </span>
        )}
      </div>

      {profile.markets.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {profile.markets.map((m) => (
            <span
              key={m.id}
              className={`text-xs px-2 py-1 rounded ${
                m.primary
                  ? "bg-blue-900/40 text-blue-300 border border-blue-700/40"
                  : "bg-[#1a1a1a] text-[#666]"
              }`}
            >
              {m.label}
            </span>
          ))}
        </div>
      )}

      {profile.growth_signals.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-[#555] uppercase tracking-wider">Growth signals</p>
          {profile.growth_signals.slice(0, 3).map((signal, i) => (
            <p key={i} className="text-xs text-[#888]">▸ {signal}</p>
          ))}
        </div>
      )}

      {profile.tech_stack && profile.tech_stack.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-[#555] uppercase tracking-wider">Tech stack</p>
          <div className="flex flex-wrap gap-2">
            {profile.tech_stack.slice(0, 10).map((tool, i) => (
              <span
                key={i}
                className="text-xs px-2 py-1 rounded bg-[#1a1a1a] text-[#aaa] border border-[#222]"
              >
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
