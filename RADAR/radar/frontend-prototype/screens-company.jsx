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

// ─── Main screen ──────────────────────────────────────────────────────────────
function CompanyScreen({ data, companyId }) {
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
  const fundingEvents = ((data.funding || {})[c.id] || []).filter(e => e.amt > 0);
  const caps = ((data.capabilities || {})[c.id]) || [];
  const features = data.features || [];
  const fullCount = caps.filter(x => x === "full").length;
  const partCount = caps.filter(x => x === "part").length;
  const noneCount = caps.filter(x => x === "none").length;
  const pricing = ((data.pricing || {})[c.id]) || [];

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
            <div className="val">{fmtMoney(c.funding?.total || 0)}</div>
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

      {/* ── Funding history ── */}
      {fundingEvents.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-h">
            <h3>Funding history</h3>
            <span className="meta">{fmtMoney(c.funding?.total || 0)} total raised</span>
          </div>
          <div style={{ padding: "4px 0" }}>
            {fundingEvents.map((ev, i) => {
              const maxAmt = Math.max(...fundingEvents.map(e => e.amt));
              return (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "80px 100px 1fr 90px",
                  alignItems: "center", gap: 16, padding: "10px 16px",
                  borderBottom: i < fundingEvents.length - 1 ? "1px solid var(--border-dim)" : "none",
                }}>
                  <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>Q{ev.q} {ev.y}</span>
                  <span className="tag" style={{ fontSize: 10 }}>{ev.round}</span>
                  <div style={{ height: 6, background: "var(--bg-3)", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{
                      height: "100%", borderRadius: 3,
                      width: Math.max(4, (ev.amt / maxAmt) * 100) + "%",
                      background: "var(--accent)",
                    }} />
                  </div>
                  <span className="mono" style={{ fontSize: 12, fontWeight: 500, textAlign: "right" }}>
                    {ev.amt >= 1 ? fmtMoney(ev.amt * 1e6) : "undisclosed"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

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

    </div>
  );
}

window.CompanyScreen = CompanyScreen;
