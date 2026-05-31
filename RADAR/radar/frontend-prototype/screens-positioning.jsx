// screens-positioning.jsx — Positioning tab: reliable-data comparison views
//   1. Cohort Comparison  — ranked horizontal bar charts on fields we collect well
//                           (funding, headcount, capital intensity, age, funding velocity)
//   2. Investor Concentration — ranked bars of investors backing >1 cohort company
//   3. Customer Overlap   — contested-account matrix (contested-first, collapsible tail)
//   4. Funding Round Timeline — per-company round cadence
//
// ARR/valuation deliberately NOT charted: ARR is disclosed by too few companies to
// compare a cohort, and valuation is only captured as narrative text, not a number.

const ACCENT = "#b34a1f";
const NEUTRAL = "#bdb6a8";        // competitor bar fill (warm gray, matches stone palette)
const NEUTRAL_DIM = "#d8d2c6";
const NOW_YEAR = 2026;

function truncName(name, n = 14) {
  return name.length > n ? name.slice(0, n - 1) + "…" : name;
}

// ────────────────────────────────────────────────────────────────
//  Chart 1 — Cohort Comparison (small-multiples of ranked bar charts)
// ────────────────────────────────────────────────────────────────
function RankedBarChart({ title, sub, companies, valueFn, fmt, onPick }) {
  const canvasRef = React.useRef(null);
  const chartRef = React.useRef(null);

  // Build + sort rows once per render; reused by effect and empty-state guard.
  const rows = companies
    .map(c => ({ c, v: valueFn(c) }))
    .filter(r => Number.isFinite(r.v) && r.v > 0)
    .sort((a, b) => b.v - a.v);

  React.useEffect(() => {
    if (!canvasRef.current || typeof Chart === "undefined" || rows.length < 2) return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    chartRef.current = new Chart(canvasRef.current, {
      type: "bar",
      data: {
        labels: rows.map(r => truncName(r.c.name)),
        datasets: [{
          data: rows.map(r => r.v),
          backgroundColor: rows.map(r => r.c.isSubject ? ACCENT : NEUTRAL),
          borderColor: rows.map(r => r.c.isSubject ? ACCENT : NEUTRAL_DIM),
          borderWidth: 1,
          borderRadius: 3,
          barThickness: 16,
          maxBarThickness: 18,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        layout: { padding: { right: 56 } }, // room for value labels at bar tips
        onClick(evt) {
          if (!chartRef.current) return;
          const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
          if (!pts.length) return;
          const r = rows[pts[0].index];
          if (r && onPick) onPick(r.c);
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(0,0,0,0.05)", drawTicks: false },
            ticks: { display: false },
            border: { display: false },
          },
          y: {
            grid: { display: false },
            ticks: {
              font: { size: 10.5 },
              color: (ctx) => (rows[ctx.index] && rows[ctx.index].c.isSubject ? ACCENT : "#6b6357"),
            },
            border: { display: false },
          },
        },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
      plugins: [{
        id: "valueLabels",
        afterDatasetsDraw(chart) {
          const { ctx } = chart;
          const meta = chart.getDatasetMeta(0);
          ctx.save();
          ctx.font = "10px " + (getComputedStyle(document.body).getPropertyValue("--font-mono") || "monospace");
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          meta.data.forEach((bar, i) => {
            const r = rows[i];
            if (!r) return;
            ctx.fillStyle = r.c.isSubject ? ACCENT : "#8a8174";
            ctx.fillText(fmt(r.v), bar.x + 6, bar.y);
          });
          ctx.restore();
        },
      }],
    });

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [companies]);

  const h = rows.length * 26 + 16;

  return (
    <div>
      <div style={{display:"flex", alignItems:"baseline", gap:6, marginBottom:8}}>
        <span style={{fontSize:11.5, fontWeight:600, color:"var(--fg-2)"}}>{title}</span>
        {sub && <span className="mono" style={{fontSize:9.5, color:"var(--fg-4)", textTransform:"uppercase", letterSpacing:"0.04em"}}>{sub}</span>}
      </div>
      {rows.length < 2
        ? <div style={{padding:"24px 0", textAlign:"center", color:"var(--fg-4)", fontSize:11}}>Not enough data to compare.</div>
        : <div style={{position:"relative", height:h}}><canvas ref={canvasRef} /></div>
      }
    </div>
  );
}

function CohortComparison({ companies, onPick }) {
  const metrics = [
    { key: "funding",  title: "Total funding raised", valueFn: c => c.funding?.total, fmt: fmtMoney },
    { key: "emp",      title: "Headcount", sub: "employees", valueFn: c => c.employees, fmt: fmtNum },
    { key: "intensity",title: "Capital intensity", sub: "€ / employee",
      valueFn: c => (c.funding?.total && c.employees) ? c.funding.total / c.employees : null,
      fmt: v => fmtMoney(v) },
    { key: "age",      title: "Company age", sub: "years", valueFn: c => (c.founded ? NOW_YEAR - c.founded : null), fmt: v => v + "y" },
    { key: "velocity", title: "Funding velocity", sub: "€ raised / year",
      valueFn: c => {
        const age = c.founded ? NOW_YEAR - c.founded : null;
        return (age && age > 0 && c.funding?.total) ? c.funding.total / age : null;
      },
      fmt: v => fmtMoney(v) },
    { key: "growth", title: "Headcount growth", sub: "YoY %",
      valueFn: c => (c.employeeGrowth > 0 ? c.employeeGrowth : null), fmt: v => fmtPct(v) },
  ];

  return (
    <div className="card">
      <div className="card-h">
        <h3>Cohort comparison</h3>
        <span className="meta">{companies.length} companies · sourced metrics</span>
      </div>
      <div style={{
        display:"grid",
        gridTemplateColumns:"repeat(auto-fit, minmax(260px, 1fr))",
        gap:"20px 28px",
        padding:"18px 16px 6px",
      }}>
        {metrics.map(m => (
          <RankedBarChart
            key={m.key}
            title={m.title}
            sub={m.sub}
            companies={companies}
            valueFn={m.valueFn}
            fmt={m.fmt}
            onPick={onPick}
          />
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Positioning map — target segment × GTM motion (signature VC 2×2)
// ────────────────────────────────────────────────────────────────
const SEG_AXIS = ["SMB", "Mid-Market", "Enterprise"];
const GTM_AXIS = ["Product-led", "Hybrid", "Sales-led"];

function segScore(s) {
  if (!s) return null;
  const t = s.toLowerCase();
  if (t.includes("enterprise")) return 3;
  if (t.includes("mid") || t.includes("mixed")) return 2;
  if (t.includes("smb") || t.includes("small") || t.includes("pme") || t.includes("startup")) return 1;
  return null;
}
function gtmScore(s) {
  if (!s) return null;
  const t = s.toLowerCase();
  if (t.includes("sales")) return 3;
  if (t.includes("hybrid") || t.includes("mixed")) return 2;
  if (t.includes("product") || t.includes("plg") || t.includes("marketing")) return 1;
  return null;
}

function PositioningMap({ companies, onPick }) {
  const canvasRef = React.useRef(null);
  const chartRef = React.useRef(null);

  const points = companies
    .map((c, i) => ({ c, x: segScore(c.target_segment), y: gtmScore(c.gtm_motion), i }))
    .filter(p => p.x != null && p.y != null);

  React.useEffect(() => {
    if (!canvasRef.current || typeof Chart === "undefined" || !points.length) return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    // Deterministic jitter so companies sharing a cell don't fully overlap.
    const jit = (n) => ((n % 5) - 2) * 0.07;
    const data = points.map(p => ({ x: p.x + jit(p.i), y: p.y + jit(p.i + 2), _p: p }));

    chartRef.current = new Chart(canvasRef.current, {
      type: "scatter",
      data: {
        datasets: [{
          data,
          pointRadius: 7,
          pointHoverRadius: 9,
          backgroundColor: points.map(p => p.c.isSubject ? ACCENT : NEUTRAL),
          borderColor: points.map(p => p.c.isSubject ? ACCENT : NEUTRAL_DIM),
          borderWidth: 1.5,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: true, aspectRatio: 2.2, animation: false,
        layout: { padding: { top: 8, right: 12, bottom: 4, left: 4 } },
        onClick(evt) {
          if (!chartRef.current) return;
          const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
          if (!pts.length) return;
          const p = data[pts[0].index]._p;
          if (p && onPick) onPick(p.c);
        },
        scales: {
          x: {
            min: 0.5, max: 3.5,
            title: { display: true, text: "Target segment →", font: { size: 10 }, color: "#bbb" },
            ticks: { stepSize: 1, callback: v => SEG_AXIS[v - 1] || "", font: { size: 10 }, color: "#888" },
            grid: { color: "rgba(0,0,0,0.05)" },
          },
          y: {
            min: 0.5, max: 3.5,
            title: { display: true, text: "Go-to-market motion →", font: { size: 10 }, color: "#bbb" },
            ticks: { stepSize: 1, callback: v => GTM_AXIS[v - 1] || "", font: { size: 10 }, color: "#888" },
            grid: { color: "rgba(0,0,0,0.05)" },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: () => "",
              label(ctx) {
                const p = ctx.raw._p;
                return [p.c.name, "Segment: " + (p.c.target_segment || "—"), "GTM: " + (p.c.gtm_motion || "—")];
              },
            },
          },
        },
      },
      plugins: [{
        id: "mapLabels",
        afterDatasetsDraw(chart) {
          const { ctx } = chart;
          const meta = chart.getDatasetMeta(0);
          ctx.save();
          ctx.font = "11px " + (getComputedStyle(document.body).getPropertyValue("--font-sans") || "sans-serif");
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          meta.data.forEach((pt, i) => {
            const p = data[i]._p;
            if (!p) return;
            ctx.fillStyle = p.c.isSubject ? ACCENT : "#6b6357";
            ctx.font = (p.c.isSubject ? "600 " : "") + "11px " + (getComputedStyle(document.body).getPropertyValue("--font-sans") || "sans-serif");
            ctx.fillText(truncName(p.c.name, 16), pt.x, pt.y + 9);
          });
          ctx.restore();
        },
      }],
    });

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [companies]);

  const skipped = companies.length - points.length;

  return (
    <div className="card">
      <div className="card-h">
        <h3>Positioning map</h3>
        <span className="meta">segment × GTM motion</span>
      </div>
      <div style={{padding:"16px 16px 8px"}}>
        {points.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No segment / GTM data to map.</div>
          : <canvas ref={canvasRef} />
        }
      </div>
      <div style={{padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        Where each player sits by who they sell to and how they sell.
        {skipped > 0 && ` ${skipped} omitted (unclassified).`}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Chart 2 — Investor Concentration (ranked bars of shared investors)
// ────────────────────────────────────────────────────────────────
function InvestorConcentrationGraph({ companies, onPick }) {
  // Build investor → companies map
  const investorMap = new Map();
  companies.forEach(c => {
    (c.notable_investors || []).forEach(inv => {
      const key = cleanLabel(inv.name);
      if (!key) return;
      if (!investorMap.has(key)) investorMap.set(key, { name: key, companies: [] });
      investorMap.get(key).companies.push(c);
    });
  });

  const allInvestors = [...investorMap.values()];
  // Only investors backing ≥2 cohort companies carry signal; rank by count desc.
  const shared = allInvestors
    .filter(i => i.companies.length >= 2)
    .sort((a, b) => b.companies.length - a.companies.length || a.name.localeCompare(b.name));
  const maxCount = shared.length ? shared[0].companies.length : 1;

  return (
    <div className="card">
      <div className="card-h">
        <h3>Investor concentration</h3>
        <span className="meta">{allInvestors.length} investors · {shared.length} shared</span>
      </div>
      <div style={{padding:"14px 16px 6px"}}>
        {shared.length === 0
          ? (
            // No shared backers — fall back to a per-company investor roster so the card stays useful.
            <div style={{display:"flex", flexDirection:"column", gap:10}}>
              <div style={{fontSize:11, color:"var(--fg-4)", marginBottom:2}}>No investor backs more than one company here — backers by company:</div>
              {companies.map(c => (
                <div key={c.id} style={{display:"flex", gap:8, alignItems:"baseline"}}>
                  <span
                    onClick={() => onPick && onPick(c)}
                    style={{flex:"0 0 110px", fontSize:11.5, fontWeight:c.isSubject ? 600 : 500, color:c.isSubject ? ACCENT : "var(--fg-2)", cursor:"pointer"}}>
                    {truncName(c.name, 16)}
                  </span>
                  <div style={{display:"flex", flexWrap:"wrap", gap:4}}>
                    {(c.notable_investors || []).length === 0
                      ? <span style={{fontSize:10, color:"var(--fg-4)"}}>—</span>
                      : c.notable_investors.map((inv, k) => (
                        <span key={k} style={{fontSize:10, padding:"2px 7px", borderRadius:10, background:"var(--bg-2)", color:"var(--fg-3)", border:"1px solid var(--border)"}}>
                          {cleanLabel(inv.name)}
                        </span>
                      ))}
                  </div>
                </div>
              ))}
            </div>
          )
          : (
            <div style={{display:"flex", flexDirection:"column", gap:12}}>
              {shared.map(inv => (
                <div key={inv.name}>
                  <div style={{display:"flex", alignItems:"baseline", justifyContent:"space-between", marginBottom:4}}>
                    <span style={{fontSize:12, fontWeight:600, color:"var(--fg-2)"}}>{inv.name}</span>
                    <span className="mono" style={{fontSize:10.5, color:ACCENT, fontWeight:600}}>{inv.companies.length} backings</span>
                  </div>
                  <div style={{height:8, borderRadius:4, background:"var(--bg-3)", overflow:"hidden"}}>
                    <div style={{height:"100%", width:(inv.companies.length / maxCount * 100) + "%", background:ACCENT, opacity:0.85, borderRadius:4}} />
                  </div>
                  <div style={{display:"flex", flexWrap:"wrap", gap:5, marginTop:6}}>
                    {inv.companies.map(c => (
                      <span
                        key={c.id}
                        onClick={() => onPick && onPick(c)}
                        style={{
                          fontSize:10, padding:"2px 7px", borderRadius:10, cursor:"pointer",
                          background:c.isSubject ? "var(--accent-bg)" : "var(--bg-2)",
                          color:c.isSubject ? "var(--accent-fg)" : "var(--fg-3)",
                          border:"1px solid " + (c.isSubject ? "var(--accent)" : "var(--border)"),
                          fontWeight:c.isSubject ? 600 : 400,
                        }}>
                        {c.name}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </div>
      <div style={{padding:"6px 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        Investors backing multiple cohort companies signal where smart money concentrates.
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Chart 3 — Overlap Matrix (generic: customers OR verticals)
//    extract(company) → string[] of entity names. Contested-first,
//    collapsible tail. Reused by CustomerLogoOverlap + VerticalOverlap.
// ────────────────────────────────────────────────────────────────
function OverlapMatrix({ companies, onPick, title, rowLabel, hint, extract }) {
  const [showAll, setShowAll] = React.useState(false);

  // Build entity → companies map
  const entMap = new Map();
  companies.forEach(c => {
    extract(c).forEach(name => {
      const key = (name || "").trim();
      if (!key) return;
      if (!entMap.has(key)) entMap.set(key, { name: key, companyIds: new Set() });
      entMap.get(key).companyIds.add(c.id);
    });
  });

  // Sort: shared (count desc) first, then alphabetical
  const allRows = [...entMap.values()]
    .map(r => ({ ...r, count: r.companyIds.size }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));

  const contested = allRows.filter(r => r.count >= 2);
  const tailCount = allRows.length - contested.length;
  // Default view: contested only (the signal). If none contested, show first 8 so card isn't empty.
  const visible = showAll
    ? allRows
    : (contested.length ? contested : allRows.slice(0, 8));

  return (
    <div className="card">
      <div className="card-h">
        <h3>{title}</h3>
        <span className="meta">{allRows.length} {rowLabel} · {contested.length} contested</span>
      </div>
      <div style={{padding:"6px 12px 6px", overflowX:"auto", maxHeight:340, overflowY:"auto"}}>
        {allRows.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No {rowLabel} data.</div>
          : (
            <table className="customer-overlap-table" style={{width:"100%", borderCollapse:"collapse", fontSize:11}}>
              <thead>
                <tr>
                  <th style={{textAlign:"left", padding:"6px 8px", color:"#888", fontWeight:500, position:"sticky", top:0, background:"var(--bg)", borderBottom:"1px solid var(--border)", textTransform:"capitalize"}}>{rowLabel.replace(/s$/, "")}</th>
                  {companies.map(c => (
                    <th key={c.id}
                        title={c.name}
                        style={{textAlign:"center", padding:"6px 4px", color:c.isSubject ? ACCENT : "#888", fontWeight:c.isSubject ? 600 : 500, position:"sticky", top:0, background:"var(--bg)", borderBottom:"1px solid var(--border)", minWidth:50, cursor:"pointer"}}
                        onClick={() => onPick && onPick(c)}>
                      {c.name.length > 9 ? c.name.slice(0, 8) + "…" : c.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map(r => (
                  <tr key={r.name} style={{borderBottom:"1px solid var(--border-dim, rgba(0,0,0,0.05))"}}>
                    <td style={{padding:"5px 8px", color:"#333", fontWeight:r.count >= 2 ? 600 : 400}}>
                      {r.name}
                      {r.count >= 2 && <span style={{marginLeft:6, color:ACCENT, fontSize:9, letterSpacing:"0.05em"}}>×{r.count}</span>}
                    </td>
                    {companies.map(c => (
                      <td key={c.id} style={{textAlign:"center", padding:"5px 4px"}}>
                        {r.companyIds.has(c.id)
                          ? <span style={{display:"inline-block", width:10, height:10, borderRadius:"50%", background:c.isSubject ? ACCENT : "#444"}}></span>
                          : <span style={{color:"#ddd"}}>·</span>
                        }
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>
      <div style={{padding:"4px 16px 12px", fontSize:11, color:"var(--fg-3)", display:"flex", alignItems:"center", gap:10}}>
        <span>{hint}</span>
        {tailCount > 0 && (
          <button
            onClick={() => setShowAll(s => !s)}
            style={{marginLeft:"auto", background:"none", border:"1px solid var(--border)", borderRadius:5, padding:"3px 9px", fontSize:10.5, color:"var(--fg-3)", cursor:"pointer"}}>
            {showAll ? "Show contested only" : `Show all ${allRows.length}`}
          </button>
        )}
      </div>
    </div>
  );
}

// Strip markdown-link junk that leaks into some sourced strings, e.g.
// "Retail [Harver: ...](https://…)" → "Retail", "Insight Partners [..](..)" → "Insight Partners".
function cleanLabel(v) {
  return (v || "").split(/\s*\[/)[0].trim();
}

function CustomerLogoOverlap({ companies, onPick }) {
  return (
    <OverlapMatrix
      companies={companies} onPick={onPick}
      title="Customer overlap" rowLabel="customers"
      hint="Contested logos (×n) indicate ICP convergence."
      extract={c => (c.notable_customers || []).map(x => x.name)}
    />
  );
}

function VerticalOverlap({ companies, onPick }) {
  return (
    <OverlapMatrix
      companies={companies} onPick={onPick}
      title="Vertical overlap" rowLabel="verticals"
      hint="Contested verticals (×n) are the crowded battlegrounds."
      extract={c => (c.targetVerticals || []).map(cleanLabel)}
    />
  );
}

// ────────────────────────────────────────────────────────────────
//  Chart 4 — Funding Round Timeline (simplified bubble sizing)
// ────────────────────────────────────────────────────────────────
function FundingRoundTimeline({ companies, onPick }) {
  const canvasRef = React.useRef(null);
  const chartRef = React.useRef(null);
  const rows = companies.filter(c => (c.fundingRounds || []).length > 0);

  React.useEffect(() => {
    if (!canvasRef.current || typeof Chart === "undefined" || !rows.length) return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    // Stable y-axis: subject at top, rest in given order
    const yLabels = rows.map(c => c.name);
    const yIndex = (name) => yLabels.length - 1 - yLabels.indexOf(name); // top = subject

    const allDates = rows.flatMap(c =>
      c.fundingRounds.map(r => r.date ? new Date(r.date).getTime() : null).filter(Boolean)
    );
    const xMin = Math.min(...allDates);
    const xMax = Math.max(...allDates);
    const xPad = (xMax - xMin) * 0.05;

    const roundColors = {
      "Pre-Seed": "#a3e635",
      "Seed": "#84cc16",
      "Series A": "#22d3ee",
      "Series B": "#3b82f6",
      "Series C": "#8b5cf6",
      "Series D": "#a855f7",
      "Series E": "#d946ef",
      "Series F": "#ec4899",
    };

    // 3 fixed size buckets by round amount — replaces noisy log-radius scaling.
    const bucketRadius = (amt) => {
      if (!amt) return 5;
      if (amt < 5e6) return 6;
      if (amt < 5e7) return 9;
      return 13;
    };

    const datasets = rows.map(c => {
      const dated = c.fundingRounds.filter(r => r.date);
      return {
        label: c.name,
        data: dated.map(r => ({
          x: new Date(r.date).getTime(),
          y: yIndex(c.name),
          _company: c,
          _round: r,
        })),
        backgroundColor: dated.map(r => roundColors[r.round] || "#888"),
        borderColor: c.isSubject ? ACCENT : "rgba(0,0,0,0.25)",
        borderWidth: c.isSubject ? 2 : 1,
        pointRadius: (ctx) => bucketRadius(ctx.raw?._round?.amountEur || 0),
        pointHoverRadius: (ctx) => bucketRadius(ctx.raw?._round?.amountEur || 0) + 3,
      };
    });

    chartRef.current = new Chart(canvasRef.current, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: true, aspectRatio: 3.2, animation: false,
        onClick(evt) {
          if (!chartRef.current) return;
          const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
          if (!pts.length) return;
          const pt = datasets[pts[0].datasetIndex].data[pts[0].index];
          if (onPick) onPick(pt._company);
        },
        scales: {
          x: {
            type: "linear",
            min: xMin - xPad,
            max: xMax + xPad,
            title: { display: true, text: "Date →", font: { size: 10 }, color: "#bbb" },
            ticks: {
              callback(v) { return new Date(v).getFullYear(); },
              font: { size: 10 }, color: "#aaa", maxTicksLimit: 8,
            },
            grid: { color: "rgba(0,0,0,0.04)" },
          },
          y: {
            min: -0.5, max: yLabels.length - 0.5,
            ticks: {
              callback(v) {
                const idx = yLabels.length - 1 - v;
                return yLabels[idx] || "";
              },
              font: { size: 11 }, color: "#666",
              stepSize: 1,
            },
            grid: { color: "rgba(0,0,0,0.04)" },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: () => "",
              label(ctx) {
                const r = ctx.raw._round;
                const c = ctx.raw._company;
                return [
                  c.name + " · " + (r.round || "—"),
                  r.date || "",
                  r.amountEur ? "Amount: " + fmtMoney(r.amountEur) : "Amount: undisclosed",
                ];
              },
            },
          },
        },
      },
    });

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [companies]);

  // Legend for round colors
  const stagesPresent = [...new Set(rows.flatMap(c => c.fundingRounds.map(r => r.round)).filter(Boolean))];
  const roundColors = {
    "Pre-Seed": "#a3e635", "Seed": "#84cc16", "Series A": "#22d3ee", "Series B": "#3b82f6",
    "Series C": "#8b5cf6", "Series D": "#a855f7", "Series E": "#d946ef", "Series F": "#ec4899",
  };

  return (
    <div className="card">
      <div className="card-h">
        <h3>Funding round cadence</h3>
        <span className="meta">{rows.reduce((n, c) => n + c.fundingRounds.length, 0)} rounds · {rows.length} companies</span>
      </div>
      <div style={{padding:"16px 16px 8px"}}>
        {rows.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No funding round data.</div>
          : <canvas ref={canvasRef} />
        }
      </div>
      <div style={{display:"flex", gap:14, flexWrap:"wrap", padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        <span>Dot size ≈ round amount (small / mid / large)</span>
        {stagesPresent.map(s => (
          <span key={s} style={{display:"inline-flex", alignItems:"center", gap:4}}>
            <span style={{width:10, height:10, borderRadius:"50%", background:roundColors[s] || "#888", display:"inline-block"}} />
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Top-level screen
// ────────────────────────────────────────────────────────────────
function PositioningScreen({ data, onOpenCompany }) {
  const { subject, competitors } = data;
  const all = React.useMemo(() => [subject, ...competitors], [data]);
  const [selected, setSelected] = React.useState(null);

  const handlePick = React.useCallback((c) => {
    if (!c) return;
    if (onOpenCompany && !c.isSubject) { onOpenCompany(c.id); return; }
    setSelected(c);
  }, [onOpenCompany]);

  return (
    <div className="screen positioning-page">
      <div style={{marginBottom:20}}>
        <div className="mono" style={{fontSize:10, letterSpacing:"0.14em", textTransform:"uppercase", color:"var(--fg-4)", marginBottom:8}}>
          Competitive Intelligence
        </div>
        <h1 className="serif" style={{fontSize:26, fontWeight:500, letterSpacing:"-0.02em", margin:0}}>
          Positioning
        </h1>
        <p style={{color:"var(--fg-3)", fontSize:13, marginTop:6, marginBottom:0}}>
          Cohort compared on reliable, sourced metrics. Click any company to drill in.
        </p>
      </div>

      <CohortComparison companies={all} onPick={handlePick} />

      <PositioningMap companies={all} onPick={handlePick} />

      <div className="positioning-grid">
        <VerticalOverlap companies={all} onPick={handlePick} />
        <CustomerLogoOverlap companies={all} onPick={handlePick} />
      </div>

      <InvestorConcentrationGraph companies={all} onPick={handlePick} />

      <FundingRoundTimeline companies={all} onPick={handlePick} />

      {selected && (
        <div style={{
          position:"sticky", bottom:12, marginTop:12, padding:"12px 14px",
          background:"var(--bg-2)", borderRadius:6,
          border:"1px solid var(--border)",
          display:"flex", alignItems:"center", gap:14,
          boxShadow:"0 4px 12px rgba(0,0,0,0.06)",
        }}>
          <LogoMark name={selected.name} domain={selected.domain} subject={selected.isSubject} />
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontWeight:600, fontSize:13}}>{selected.name}</div>
            <div className="mono" style={{fontSize:11, color:"var(--fg-3)", marginTop:2}}>
              {selected.subCategory || selected.category} · Founded {selected.founded || "—"} · {fmtMoney(selected.funding?.total || 0)} raised
              {typeof selected.employees === "number" ? " · " + fmtNum(selected.employees) + " emp" : ""}
            </div>
          </div>
          {!selected.isSubject && <ThreatTag level={selected.threat} />}
          <button onClick={() => setSelected(null)} style={{background:"none", border:"none", cursor:"pointer", color:"var(--fg-4)"}}>
            {Icons.x}
          </button>
        </div>
      )}
    </div>
  );
}

window.PositioningScreen = PositioningScreen;
