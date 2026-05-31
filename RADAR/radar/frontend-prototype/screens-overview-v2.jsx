// screens-overview-v2.jsx — Overview redesign (A/B test version)
// 7 zones: Hero · At-a-glance · Moat · News+Momentum · Funding timeline · Team · Footprint
const { useMemo: _uM_v2, useState: _uS_v2 } = React;

function _initials(name) {
  if (!name) return "?";
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "?";
}

function _avatarHue(name) {
  const a = name?.charCodeAt(0) || 0;
  const b = name?.charCodeAt(1) || 0;
  return (a * 37 + b * 11) % 360;
}

function _dedupNews(items) {
  if (!Array.isArray(items)) return [];
  const sig = n => (n.date || "") + "|" + (n.headline || "").toLowerCase().replace(/[^a-z0-9 ]+/g, "").slice(0, 30);
  const groups = new Map();
  for (const n of items) {
    if (!n || !n.headline) continue;
    const k = sig(n);
    if (!groups.has(k)) {
      groups.set(k, { date: n.date, headline: n.headline, sources: [] });
    }
    if (n.sourceUrl) groups.get(k).sources.push(n.sourceUrl);
  }
  return [...groups.values()].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
}

function _personBucket(role) {
  const r = (role || "").toLowerCase();
  if (/\bco[-\s]?founder|\bfounder\b/.test(r)) return "founders";
  return "execs";
}

function _fmtRoundDate(iso) {
  if (!iso) return "";
  const [y, m] = iso.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return (months[parseInt(m, 10) - 1] || "") + " " + y;
}

function _roundLetter(roundName) {
  if (!roundName) return "?";
  const r = roundName.toLowerCase();
  if (r.includes("seed")) return "S";
  if (r.includes("pre-seed") || r.includes("preseed")) return "P";
  const match = roundName.match(/series\s+([a-z])/i);
  if (match) return match[1].toUpperCase();
  return roundName[0].toUpperCase();
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function HeroRibbon({ subject, scannedAt }) {
  const { flag } = countryFlag(subject.hq);
  const positioning = subject.positioning || subject.tagline;
  return (
    <div style={{marginBottom: 24}}>
      <div style={{display:"flex", alignItems:"center", gap:14, flexWrap:"wrap"}}>
        <LogoMark name={subject.name} domain={subject.domain} subject={true} size="lg" />
        <h1 style={{fontFamily:"var(--font-serif)", fontSize:32, fontWeight:500, letterSpacing:"-0.02em", margin:0}}>
          {subject.name}
        </h1>
        <a href={`https://${subject.domain}`} target="_blank" rel="noopener noreferrer"
          className="mono muted"
          style={{fontSize:12.5, color:"inherit", textDecoration:"none"}}>
          {subject.domain} {Icons.ext}
        </a>
        <span className="tag subject mono">SUBJECT</span>
      </div>
      {positioning && (
        <p className="serif" style={{
          fontSize: 16,
          color: "var(--fg-2)",
          margin: "10px 0 0",
          lineHeight: 1.55,
          maxWidth: 820,
        }}>
          {positioning}
        </p>
      )}
      <div style={{display:"flex", gap:18, marginTop:12, flexWrap:"wrap", color:"var(--fg-3)", fontSize:12}}>
        {subject.hq && (
          <span className="row" style={{gap:6}}>{Icons.pin} {flag} {subject.hq}</span>
        )}
        {subject.geo_coverage && (
          <span className="row" style={{gap:6}}>🌐 {subject.geo_coverage}</span>
        )}
        {subject.founded && (
          <span className="row" style={{gap:6}}>{Icons.building} founded {subject.founded}</span>
        )}
        {scannedAt && (
          <span className="row mono" style={{gap:6, marginLeft:"auto", fontSize:11, color:"var(--fg-4)"}}>
            🕐 scanned {fmtRelTime(scannedAt)}
          </span>
        )}
      </div>
    </div>
  );
}

function AtAGlanceBar({ subject }) {
  const cells = [
    { lbl: "Employees", val: subject.employees ? fmtNum(subject.employees) : "—", level: subject.employees ? "high" : "low" },
    { lbl: "Stage", val: subject.fundingStage || subject.funding?.lastRound || "—", level: subject.fundingStage ? "high" : "medium" },
    { lbl: "Total raised", val: fmtFunding(subject.funding), level: subject.funding?.status === "enriched" ? "high" : subject.funding?.status === "bootstrapped" ? "medium" : "low" },
    { lbl: "Business model", val: subject.business_model || "—", level: subject.business_model ? "high" : "low" },
    { lbl: "GTM motion", val: subject.gtm_motion || "—", level: subject.gtm_motion ? "high" : "low" },
    { lbl: "Target segment", val: subject.target_segment || "—", level: subject.target_segment ? "high" : "low" },
  ];
  return (
    <div className="card" style={{marginBottom: 20}}>
      <div className="kv-row">
        {cells.map((c, i) => (
          <div key={i} className="kv-cell">
            <div className="kv-lbl">
              <ConfidenceDot level={c.level} />
              {c.lbl}
            </div>
            <div className="kv-val">{c.val}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MoatCard({ subject }) {
  const kd = subject.keyDifferentiator;
  const features = subject.top3Features || [];
  const stack = subject.techStack || [];
  if (!kd && features.length === 0 && stack.length === 0) return null;
  return (
    <div className="card">
      <div className="card-h">
        <h3>The Moat</h3>
        <span className="meta">What makes them different</span>
      </div>
      <div className="card-b" style={{padding: 16}}>
        {kd && (
          <div style={{marginBottom: 14}}>
            <div className="zone-h" style={{marginBottom: 6}}>
              <span className="meta">Key differentiator</span>
              <ConfidenceDot
                level={kd.confidence || "medium"}
                sourceUrl={kd.sourceUrl}
                evidence={kd.evidence || kd.value}
                extractedAt={kd.extractedAt}
              />
            </div>
            <p style={{margin: 0, fontSize: 14, lineHeight: 1.55, color: "var(--fg)", fontWeight: 500}}>
              {kd.value}
            </p>
          </div>
        )}
        {features.length > 0 && (
          <div style={{marginBottom: 14}}>
            <div className="zone-h" style={{marginBottom: 6}}>
              <span className="meta">Top features</span>
            </div>
            <ul style={{margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.6, color: "var(--fg-2)"}}>
              {features.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </div>
        )}
        {stack.length > 0 && (
          <div>
            <div className="zone-h" style={{marginBottom: 8}}>
              <span className="meta">Tech stack</span>
            </div>
            <div style={{display: "flex", flexWrap: "wrap", gap: 6}}>
              {stack.map((t, i) => <span key={i} className="chip">{t}</span>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function NewsMomentumCard({ subject }) {
  const news = _uM_v2(() => _dedupNews(subject.recentNews || []), [subject.recentNews]);
  const signals = subject.growthSignals || subject.notable || [];
  const [showAll, setShowAll] = _uS_v2(false);
  if (news.length === 0 && signals.length === 0) return null;
  const visibleNews = showAll ? news : news.slice(0, 5);
  return (
    <div className="card">
      <div className="card-h">
        <h3>News & Momentum</h3>
        <span className="meta">Recent signals</span>
      </div>
      {news.length > 0 && (
        <div>
          {visibleNews.map((n, i) => (
            <div key={i} className="news-row">
              <span className="news-date">{n.date || "—"}</span>
              <span className="news-headline">{n.headline}</span>
              {n.sources.length > 1 ? (
                <CitationPopover
                  evidence={`${n.sources.length} sources covered this`}
                  sourceUrl={n.sources[0]}
                >
                  <span className="news-count">{n.sources.length} sources</span>
                </CitationPopover>
              ) : n.sources[0] ? (
                <a className="news-count" href={n.sources[0]} target="_blank" rel="noopener noreferrer"
                  style={{textDecoration: "none"}}>
                  source ↗
                </a>
              ) : null}
            </div>
          ))}
          {news.length > 5 && (
            <button
              onClick={() => setShowAll(v => !v)}
              style={{
                width: "100%", padding: "10px 16px", border: "none",
                background: "transparent", color: "var(--accent)",
                fontFamily: "var(--font-mono)", fontSize: 11, cursor: "pointer",
                borderTop: "1px solid var(--border-dim)",
              }}>
              {showAll ? "show less" : `+${news.length - 5} more`}
            </button>
          )}
        </div>
      )}
      {signals.length > 0 && (
        <div style={{padding: "14px 16px", borderTop: news.length > 0 ? "1px solid var(--border)" : "none"}}>
          <div className="zone-h" style={{marginBottom: 8}}>
            <span className="meta">Growth signals</span>
          </div>
          <ul style={{margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.65, color: "var(--fg-2)"}}>
            {signals.slice(0, 6).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function FundingTimelineCard({ subject }) {
  const rounds = subject.fundingRounds || [];
  const total = subject.funding?.total || 0;
  if (rounds.length === 0 && !subject.equityStory) return null;
  const sorted = [...rounds].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  return (
    <div className="card" style={{marginBottom: 20}}>
      <div className="card-h">
        <h3>Funding timeline</h3>
        <span className="meta">
          {total > 0 ? fmtMoney(total) + " across " : ""}{rounds.length} round{rounds.length === 1 ? "" : "s"}
          {subject.fundingStage ? " · stage " + subject.fundingStage : ""}
        </span>
      </div>
      {sorted.length > 0 && (
        <div>
          {sorted.map((r, i) => (
            <div key={i} className="round-card">
              <div className="round-chip">{_roundLetter(r.round)}</div>
              <div>
                <div className="round-amt">{r.amountEur ? fmtMoney(r.amountEur) : "—"}</div>
                <div className="round-meta">
                  {r.round || "Round"} · {_fmtRoundDate(r.date) || "date unknown"}
                  {r.lead && <> · led by <strong style={{color: "var(--fg-2)"}}>{r.lead}</strong></>}
                </div>
              </div>
              <span className="mono" style={{fontSize: 11, color: "var(--fg-4)"}}>{r.date}</span>
            </div>
          ))}
        </div>
      )}
      {subject.equityStory && (
        <div style={{padding: "14px 16px", borderTop: "1px solid var(--border)", fontSize: 12.5, lineHeight: 1.65, color: "var(--fg-3)", fontStyle: "italic"}}>
          {subject.equityStory}
        </div>
      )}
    </div>
  );
}

function TeamCard({ subject }) {
  const people = (subject.key_people || []).filter(p => p && p.name);
  const [filter, setFilter] = _uS_v2("founders");
  if (people.length === 0) return null;
  const bucketed = people.map(p => ({ ...p, bucket: _personBucket(p.role) }));
  const counts = {
    founders: bucketed.filter(p => p.bucket === "founders").length,
    execs: bucketed.filter(p => p.bucket === "execs").length,
    all: bucketed.length,
  };
  const filtered = filter === "all" ? bucketed : bucketed.filter(p => p.bucket === filter);
  const tabs = [
    { key: "founders", label: `Founders (${counts.founders})` },
    { key: "execs", label: `Execs (${counts.execs})` },
    { key: "all", label: `All (${counts.all})` },
  ];
  return (
    <div className="card">
      <div className="card-h">
        <h3>Team</h3>
        <div style={{display: "flex", gap: 4}}>
          {tabs.map(t => (
            <button key={t.key}
              onClick={() => setFilter(t.key)}
              style={{
                fontFamily: "var(--font-mono)", fontSize: 10.5,
                padding: "4px 10px",
                border: "1px solid " + (filter === t.key ? "var(--accent)" : "var(--border)"),
                background: filter === t.key ? "var(--accent-bg)" : "var(--bg)",
                color: filter === t.key ? "var(--accent-fg)" : "var(--fg-3)",
                borderRadius: 4,
                cursor: "pointer",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{padding: 6}}>
        {filtered.map(p => {
          const hue = _avatarHue(p.name);
          const hasLink = !!p.linkedin;
          const Tag = hasLink ? "a" : "div";
          const props = hasLink
            ? { href: p.linkedin, target: "_blank", rel: "noopener noreferrer" }
            : {};
          return (
            <Tag key={p.name} {...props} className="person-row" style={hasLink ? {cursor: "pointer", color: "inherit", textDecoration: "none"} : {}}>
              <div style={{
                width: 36, height: 36, borderRadius: "50%",
                background: `hsl(${hue}, 35%, 78%)`,
                color: "#222", fontSize: 12, fontWeight: 600,
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
              }}>{_initials(p.name)}</div>
              <div style={{flex: 1, minWidth: 0}}>
                <div style={{display: "flex", gap: 8, alignItems: "baseline"}}>
                  <span style={{fontSize: 13.5, fontWeight: 500, color: "var(--fg)"}}>{p.name}</span>
                  {p.role && <span style={{fontSize: 11, color: "var(--fg-4)"}}>{p.role}</span>}
                </div>
                {p.background && (
                  <p style={{margin: "3px 0 0", fontSize: 12, color: "var(--fg-3)", lineHeight: 1.5, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical"}}>
                    {p.background}
                  </p>
                )}
              </div>
              {hasLink && <span className="mono" style={{fontSize: 10, color: "var(--fg-4)"}}>↗</span>}
            </Tag>
          );
        })}
      </div>
    </div>
  );
}

function CustomersStrip({ subject }) {
  const customers = subject.notable_customers || [];
  if (customers.length === 0) return null;
  return (
    <div className="card" style={{marginBottom: 20}}>
      <div className="card-h">
        <h3>Notable customers</h3>
        <span className="meta">{customers.length} highlighted</span>
      </div>
      <div style={{display: "flex", flexWrap: "wrap", padding: 4}}>
        {customers.map(c => (
          <CitationPopover key={c.domain || c.name}
            evidence={c.evidence}
            sourceUrl={c.domain ? `https://${c.domain}` : null}>
            <a
              href={c.domain ? `https://${c.domain}` : "#"}
              target="_blank" rel="noopener noreferrer"
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 16px",
                textDecoration: "none", borderRadius: 6,
                transition: "background .15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              {c.domain && (
                <img
                  src={`https://img.logo.dev/${c.domain}?token=pk_OyZO8po6QHG5X9zwE8ayZQ&size=40&format=png`}
                  width={22} height={22}
                  alt={c.name}
                  style={{borderRadius: 4, objectFit: "contain", background: "var(--bg-2)"}}
                  onError={e => { e.target.style.display = "none"; }}
                />
              )}
              <div style={{display: "flex", flexDirection: "column", lineHeight: 1.2}}>
                <span style={{fontSize: 12.5, fontWeight: 500, color: "var(--fg-2)", whiteSpace: "nowrap"}}>{c.name}</span>
                {c.industry && (
                  <span style={{fontSize: 10, color: "var(--fg-4)", fontFamily: "var(--font-mono)", whiteSpace: "nowrap"}}>{c.industry}</span>
                )}
              </div>
            </a>
          </CitationPopover>
        ))}
      </div>
    </div>
  );
}

function InvestorsStrip({ subject }) {
  const investors = subject.notable_investors || [];
  if (investors.length === 0) return null;
  return (
    <div className="card" style={{marginBottom: 20}}>
      <div className="card-h">
        <h3>Notable investors</h3>
        <span className="meta">{investors.length} highlighted</span>
      </div>
      <div style={{display: "flex", flexWrap: "wrap", padding: 4}}>
        {investors.map(c => (
          <a key={c.name + (c.domain || "")}
            href={c.domain ? `https://${c.domain}` : "#"}
            target="_blank" rel="noopener noreferrer"
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 16px",
              textDecoration: "none", borderRadius: 6,
              transition: "background .15s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            {c.domain && (
              <img
                src={`https://img.logo.dev/${c.domain}?token=pk_OyZO8po6QHG5X9zwE8ayZQ&size=40&format=png`}
                width={22} height={22}
                alt={c.name}
                style={{borderRadius: 4, objectFit: "contain", background: "var(--bg-2)"}}
                onError={e => { e.target.style.display = "none"; }}
              />
            )}
            <span style={{fontSize: 12.5, fontWeight: 500, color: "var(--fg-2)", whiteSpace: "nowrap"}}>{c.name}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

function FootprintCard({ subject }) {
  const verticals = subject.targetVerticals || [];
  const markets = subject.markets || [];
  if (verticals.length === 0 && markets.length === 0) return null;
  return (
    <div className="card">
      <div className="card-h">
        <h3>Footprint</h3>
        <span className="meta">Where they play</span>
      </div>
      <div className="card-b" style={{padding: 16}}>
        {markets.length > 0 && (
          <div style={{marginBottom: 14}}>
            <div className="zone-h" style={{marginBottom: 8}}>
              <span className="meta">Markets</span>
            </div>
            <div style={{display: "flex", flexWrap: "wrap", gap: 6}}>
              {markets.map((m, i) => (
                <span key={i} className={m.primary ? "chip chip--accent" : "chip"}>
                  {m.label}{m.primary && " ★"}
                </span>
              ))}
            </div>
          </div>
        )}
        {verticals.length > 0 && (
          <div style={{marginBottom: 14}}>
            <div className="zone-h" style={{marginBottom: 8}}>
              <span className="meta">Target verticals</span>
            </div>
            <div style={{display: "flex", flexWrap: "wrap", gap: 6}}>
              {verticals.map((v, i) => <span key={i} className="chip chip--solid">{v}</span>)}
            </div>
          </div>
        )}
        {subject.geo_coverage && (
          <div>
            <div className="zone-h" style={{marginBottom: 6}}>
              <span className="meta">Geographic coverage</span>
            </div>
            <p style={{margin: 0, fontSize: 13, color: "var(--fg-2)"}}>🌐 {subject.geo_coverage}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main screen
// ─────────────────────────────────────────────────────────────────────────────

function OverviewScreenV2({ data, onOpenCompany, loadingPhase = 2 }) {
  const { subject, query } = data;
  if (!subject) return null;

  const ready = loadingPhase >= 1;
  if (!ready) {
    // Match V1 skeleton density so the layout doesn't jump
    return (
      <div className="screen">
        <Skel w={260} h={28} radius={6} style={{marginBottom: 14}} />
        <Skel w="80%" h={12} radius={4} style={{marginBottom: 24}} />
        <div className="card" style={{marginBottom: 20, padding: 14}}>
          <Skel w="100%" h={42} radius={4} />
        </div>
        <Skel w="100%" h={180} radius={6} />
      </div>
    );
  }

  return (
    <div className="screen">
      {/* Zone A */}
      <HeroRibbon subject={subject} scannedAt={query?.scannedAt} />

      {/* Zone B */}
      <AtAGlanceBar subject={subject} />

      {/* Zone C + D — two columns */}
      <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start", marginBottom: 20}}>
        <MoatCard subject={subject} />
        <NewsMomentumCard subject={subject} />
      </div>

      {/* Zone E */}
      <FundingTimelineCard subject={subject} />

      {/* Customers + Investors strips */}
      <CustomersStrip subject={subject} />
      <InvestorsStrip subject={subject} />

      {/* Zone F + G — two columns */}
      <div style={{display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, alignItems: "start"}}>
        <TeamCard subject={subject} />
        <FootprintCard subject={subject} />
      </div>
    </div>
  );
}

window.OverviewScreenV2 = OverviewScreenV2;
