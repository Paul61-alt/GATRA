// screens-company.jsx — full competitor profile card tab
const { useState: _uS_co } = React;

// ─── Inline flag helper (self-contained, no dependency on components.jsx load order) ─
const _ISO = {
  "United States":"US","Australia":"AU","Israel":"IL","Czech Republic":"CZ",
  "India":"IN","Canada":"CA","Germany":"DE","France":"FR","United Kingdom":"GB",
  "Netherlands":"NL","Sweden":"SE","Singapore":"SG","Japan":"JP","Brazil":"BR",
  "Spain":"ES","Poland":"PL","Ukraine":"UA","Switzerland":"CH","Denmark":"DK",
  "Norway":"NO","Ireland":"IE","Portugal":"PT","New Zealand":"NZ",
  "South Korea":"KR","China":"CN","Mexico":"MX","Argentina":"AR",
  "South Africa":"ZA","Vancouver":"CA","Berlin":"DE","Prague":"CZ",
};
function _flag(hq) {
  if (!hq || hq === "N/A") return { flag: "🌐", iso: "—" };
  const country = hq.split(",").map(s => s.trim()).pop();
  const iso = _ISO[country] || country.slice(0, 2).toUpperCase();
  try {
    const flag = iso.split("").map(c => String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65)).join("");
    return { flag, iso };
  } catch(e) {
    return { flag: "🌐", iso };
  }
}

// ─── Screenshot via Thum.io (free, no API key) ────────────────────────────────
function LandingScreenshot({ domain }) {
  const [status, setStatus] = _uS_co("loading");
  // No crop param → Thum.io returns the full-page screenshot at native height
  const src = "https://image.thum.io/get/width/680/noanimate/https://" + domain;
  return (
    <div style={{
      position: "relative", borderRadius: 8,
      border: "1px solid var(--border)", overflow: "hidden",
      background: "var(--bg-2)",
      minHeight: status === "ok" ? 0 : 160,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {status !== "ok" && (
        <span style={{ fontSize: 11, color: "var(--fg-4)", fontFamily: "var(--font-mono)", padding: 20 }}>
          {status === "loading" ? "Loading screenshot…" : "Screenshot unavailable"}
        </span>
      )}
      <img
        src={src}
        alt=""
        onLoad={() => setStatus("ok")}
        onError={() => setStatus("error")}
        style={{
          width: "100%", height: "auto", display: status === "ok" ? "block" : "none",
          verticalAlign: "bottom",
        }}
      />
      {status === "ok" && (
        <a href={"https://" + domain} target="_blank" rel="noopener noreferrer"
          style={{
            position: "absolute", bottom: 7, right: 7,
            background: "rgba(0,0,0,0.5)", color: "#fff",
            fontSize: 10, fontFamily: "var(--font-mono)",
            padding: "2px 7px", borderRadius: 4, textDecoration: "none",
          }}>
          {domain} ↗
        </a>
      )}
    </div>
  );
}

// Grapheme-safe truncation — avoids splitting emoji / flags (🇫🇷) mid-cluster.
function _truncGraphemes(s, max) {
  if (!s) return "";
  let units;
  try {
    const seg = new Intl.Segmenter(undefined, { granularity: "grapheme" });
    units = Array.from(seg.segment(s), x => x.segment);
  } catch (e) {
    units = Array.from(s); // fallback: code points (old browsers)
  }
  return units.length > max ? units.slice(0, max).join("").trimEnd() + "…" : s;
}

// ─── Main screen ──────────────────────────────────────────────────────────────
function CompanyScreen({ data, companyId }) {
  const [liShowAll, setLiShowAll] = _uS_co(false);
  let c = null;
  try {
    c = companyId === data.subject.id
      ? data.subject
      : (data.competitors || []).find(x => x.id === companyId) || null;
  } catch(e) {}

  if (!c) return (
    <div className="screen">
      <p style={{ color: "var(--fg-4)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
        Company not found.
      </p>
    </div>
  );

  const { flag, iso } = _flag(c.hq);
  const caps = ((data.capabilities || {})[c.id]) || [];
  const features = data.features || [];
  const fullCount = caps.filter(x => x === "full").length;
  const partCount = caps.filter(x => x === "part").length;
  const noneCount = caps.filter(x => x === "none").length;
  const pricing = ((data.pricing || {})[c.id]) || [];
  const liPosts = (c.recentLinkedinPosts || []).filter(p => p && (p.excerpt || "").trim());

  const grouped = features.reduce((acc, f, i) => {
    if (!acc[f.group]) acc[f.group] = [];
    acc[f.group].push({ label: f.label, cap: caps[i] || "none" });
    return acc;
  }, {});

  return (
    <div className="screen">

      {/* ── Header: left = identity, right = screenshot ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24, marginBottom: 24, alignItems: "start" }}>

        {/* Left: logo + name + meta */}
        <div>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 14 }}>
            <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="lg" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 26, fontWeight: 500, letterSpacing: "-0.02em", margin: 0 }}>
                  {c.name}
                </h1>
                {c.isSubject
                  ? <span className="tag subject mono">SUBJECT</span>
                  : <ThreatTag level={c.threat} />}
              </div>
              <div className="mono" style={{ color: "var(--fg-4)", fontSize: 11, marginTop: 3 }}>
                {c.domain} {Icons.ext}
              </div>
            </div>
          </div>

          <p className="serif" style={{ fontSize: 13.5, color: "var(--fg-2)", margin: "0 0 16px", fontStyle: "italic", lineHeight: 1.65 }}>
            "{c.tagline}"
          </p>

          <div style={{ color: "var(--fg-3)", fontSize: 12 }}>
            <span className="row" style={{ gap: 8 }}>{Icons.building}
              <span>{c.category}{c.subCategory ? " — " + c.subCategory.slice(0, 80) : ""}</span>
            </span>
          </div>

          {(c.notable || []).length > 0 && (
            <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 5 }}>
              {c.notable.map(n => (
                <span key={n} className="tag" style={{ fontSize: 10, padding: "2px 7px" }}>{n}</span>
              ))}
            </div>
          )}
        </div>

        {/* Right: landing page screenshot */}
        {c.domain && (
          <div>
            <LandingScreenshot domain={c.domain} />
          </div>
        )}
      </div>

      {/* ── Stat strip ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="stat-row">
          <div className="stat">
            <div className="lbl">Founded</div>
            <div className="val" style={{ fontFamily: "var(--font-serif)" }}>{c.founded || "—"}</div>
          </div>
          <div className="stat">
            <div className="lbl">HQ</div>
            <div className="val">{flag} <span style={{ fontSize: 14, fontWeight: 500 }}>{iso}</span></div>
          </div>
          <div className="stat">
            <div className="lbl">Employees</div>
            <div className="val">{(c.employees || 0).toLocaleString()}</div>
          </div>
          <div className="stat">
            <div className="lbl">Total raised</div>
            <div className="val">{fmtFunding(c.funding)}</div>
            <div className="delta">{c.funding?.lastRound || "—"}</div>
          </div>
          {!c.isSubject && c.similarity != null && (
            <div className="stat">
              <div className="lbl">Similarity</div>
              <div className="val">{(c.similarity * 100).toFixed(0)}%</div>
            </div>
          )}
        </div>
      </div>

      {/* ── Two-col: pricing + positioning ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <div className="card">
          <div className="card-h"><h3>Pricing</h3></div>
          <div className="card-b">
            {pricing.length > 0 ? pricing.map((tier, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between",
                padding: "7px 10px", background: "var(--bg-2)", borderRadius: 5, marginBottom: 6,
              }}>
                <span style={{ fontWeight: 500, fontSize: 13 }}>{tier.name}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--fg-2)" }}>{tier.price} / {tier.per}</span>
              </div>
            )) : (
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: "var(--fg-2)" }}>{c.pricing?.model || "—"}</span>
                <span className="mono" style={{ color: "var(--fg-3)" }}>{c.pricing?.mention || "—"}</span>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Positioning</h3></div>
          <div className="card-b" style={{ fontSize: 13, color: "var(--fg-2)", lineHeight: 1.6 }}>
            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--fg-4)", marginBottom: 3 }}>Category</div>
            <div style={{ fontWeight: 500, color: "var(--fg)", marginBottom: 10 }}>{c.category || "—"}</div>
            <div className="mono" style={{ fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--fg-4)", marginBottom: 3 }}>Wedge</div>
            <div>{c.subCategory || "—"}</div>
          </div>
        </div>
      </div>

      {/* ── Recent LinkedIn activity (only if posts exist) ── */}
      {liPosts.length > 0 && (() => {
        const visibleLi = liShowAll ? liPosts : liPosts.slice(0, 3);
        return (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-h">
            <h3>Recent LinkedIn activity</h3>
            <span className="meta">
              <span className="li-mono" style={{ marginRight: 6, verticalAlign: "middle" }}>in</span>
              Last 12 months · {liPosts.length} post{liPosts.length > 1 ? "s" : ""}
            </span>
          </div>
          <div style={{ padding: "2px 0" }}>
            {visibleLi.map((p, i) => {
              // Backend caps excerpt at 300c (payload guard); we render up to 220 graphemes here.
              const preview = _truncGraphemes((p.excerpt || "").trim(), 220);
              let host = "";
              try { host = new URL(p.sourceUrl).host.replace(/^www\./, ""); } catch (e) {}
              return (
                <a
                  key={i}
                  className="li-post"
                  href={p.sourceUrl || undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ animationDelay: (i * 60) + "ms", cursor: p.sourceUrl ? "pointer" : "default" }}
                >
                  {p.imageUrl
                    ? <img className="li-thumb" src={p.imageUrl} alt=""
                        onError={(e) => { e.currentTarget.style.display = "none"; }} />
                    : <LogoMark name={p.author || c.name} domain={c.domain} size="sm" />}
                  <div className="li-body">
                    <div className="li-meta">
                      <span className="li-author">{p.author || c.name}</span>
                      <span className="li-mono" style={{ verticalAlign: "middle" }}>in</span>
                      {p.date && <span className="li-date">{fmtDate(p.date)}</span>}
                      <span className="li-cta">view post {Icons.ext}</span>
                    </div>
                    <p className="li-excerpt">{preview}</p>
                    {host && <span className="li-source">{Icons.ext} {host}</span>}
                  </div>
                </a>
              );
            })}
          </div>
          {liPosts.length > 3 && (
            <button className="li-more" onClick={() => setLiShowAll(v => !v)}>
              {liShowAll ? "show less" : `+${liPosts.length - 3} more`}
            </button>
          )}
        </div>
        );
      })()}

      {/* ── Funding · Team · Customers · Investors (reuse Overview-v2 cards) ── */}
      <FundingTimelineCard subject={c} />
      <div style={{ marginBottom: 20 }}><TeamCard subject={c} /></div>
      <CustomersStrip subject={c} />
      <InvestorsStrip subject={c} />

      {/* ── Feature coverage (only if features exist) ── */}
      {features.length > 0 && (
        <div className="card">
          <div className="card-h">
            <h3>Feature coverage</h3>
            <span className="meta">{fullCount} full · {partCount} partial · {noneCount} none</span>
          </div>
          <div style={{ padding: "12px 16px 4px" }}>
            <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden" }}>
              <div style={{ flex: fullCount, background: "var(--accent)", minWidth: fullCount ? 2 : 0 }} />
              <div style={{ flex: partCount, background: "var(--accent)", opacity: 0.4, minWidth: partCount ? 2 : 0 }} />
              <div style={{ flex: noneCount, background: "var(--bg-3)", minWidth: noneCount ? 2 : 0 }} />
            </div>
          </div>
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} style={{ padding: "12px 16px 8px", borderTop: "1px solid var(--border-dim)" }}>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--fg-4)", marginBottom: 8 }}>
                {group}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {items.map(({ label, cap }) => (
                  <span key={label} style={{
                    fontSize: 10.5, padding: "3px 8px", borderRadius: 4,
                    background: cap === "none" ? "var(--bg-3)" : "var(--accent)",
                    opacity: cap === "part" ? 0.45 : 1,
                    color: cap === "none" ? "var(--fg-4)" : "#fff",
                    fontWeight: 500,
                  }}>{label}</span>
                ))}
              </div>
            </div>
          ))}
          <div style={{ height: 8 }} />
        </div>
      )}

      {/* ── Footprint / verticals (reuse Overview-v2 card) ── */}
      <div style={{ marginTop: 20 }}><FootprintCard subject={c} /></div>

    </div>
  );
}

window.CompanyScreen = CompanyScreen;
