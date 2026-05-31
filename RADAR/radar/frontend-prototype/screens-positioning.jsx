// screens-positioning.jsx — Positioning tab: 4 VC-oriented charts
//   1. Capital Efficiency Matrix (ARR × funding raised)
//   2. Funding Round Timeline (per-company round cadence)
//   3. Investor Concentration Graph (investor → company SVG network)
//   4. Customer Logo Overlap (contested-account matrix)

const ACCENT = "#b34a1f";
const LOGO_SIZE = 28;
const LOGO_HALF = LOGO_SIZE / 2;

function faviconUrl(domain) {
  if (!domain) return null;
  return `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${domain}&size=64`;
}

function preloadLogos(companies, onAllReady) {
  const logos = {};
  let pending = companies.length;
  if (pending === 0) { onAllReady(logos); return logos; }
  companies.forEach(c => {
    if (!c.domain) {
      pending--;
      if (pending === 0) onAllReady(logos);
      return;
    }
    const img = new Image();
    img.src = faviconUrl(c.domain);
    logos[c.id] = img;
    img.onload = img.onerror = () => {
      pending--;
      if (pending === 0) onAllReady(logos);
    };
  });
  return logos;
}

function drawLogoBox(ctx, img, c, px, py, half = LOGO_HALF) {
  ctx.save();
  ctx.strokeStyle = c.isSubject ? ACCENT : "#d0d0d0";
  ctx.lineWidth = c.isSubject ? 2 : 1.5;
  ctx.beginPath();
  ctx.roundRect(px - half - 2, py - half - 2, half * 2 + 4, half * 2 + 4, 5);
  ctx.stroke();
  if (img && img.complete && img.naturalWidth > 0) {
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(px - half, py - half, half * 2, half * 2, 4);
    ctx.clip();
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.drawImage(img, px - half, py - half, half * 2, half * 2);
    ctx.restore();
  } else {
    ctx.fillStyle = c.isSubject ? ACCENT + "22" : "rgba(0,0,0,0.08)";
    ctx.beginPath();
    ctx.roundRect(px - half, py - half, half * 2, half * 2, 4);
    ctx.fill();
    ctx.fillStyle = c.isSubject ? ACCENT : "#666";
    ctx.font = "bold 11px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const parts = c.name.split(/\s+/);
    const initials = (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
    ctx.fillText(initials, px, py);
  }
  ctx.restore();
}

// ────────────────────────────────────────────────────────────────
//  Chart 1 — Capital Efficiency Matrix (ARR × Funding, log-log)
// ────────────────────────────────────────────────────────────────
function CapitalEfficiencyMatrix({ companies, onPick }) {
  const canvasRef = React.useRef(null);
  const chartRef = React.useRef(null);
  const eligible = companies.filter(c => typeof c.arr === "number" && c.arr > 0 && c.funding?.total > 0);

  React.useEffect(() => {
    if (!canvasRef.current || typeof Chart === "undefined" || !eligible.length) return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    function build(logos) {
      const datasets = eligible.map(c => ({
        label: c.name,
        data: [{ x: c.funding.total, y: c.arr, _company: c }],
        pointRadius: LOGO_HALF + 2,
        pointHoverRadius: LOGO_HALF + 4,
        backgroundColor: "transparent",
        borderColor: "transparent",
      }));
      const moneyTicks = [1e5, 1e6, 1e7, 5e7, 1e8, 5e8, 1e9];
      chartRef.current = new Chart(canvasRef.current, {
        type: "scatter",
        data: { datasets },
        options: {
          responsive: true, maintainAspectRatio: true, aspectRatio: 2.4, animation: false,
          onClick(evt) {
            if (!chartRef.current) return;
            const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
            if (!pts.length) return;
            const c = datasets[pts[0].datasetIndex].data[0]._company;
            if (onPick) onPick(c);
          },
          scales: {
            x: {
              type: "logarithmic",
              title: { display: true, text: "Total funding raised →", font: { size: 10 }, color: "#bbb" },
              min: 1e6,
              ticks: {
                callback(v) { return moneyTicks.includes(v) ? fmtMoney(v) : null; },
                font: { size: 10 }, color: "#aaa", maxTicksLimit: 6,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
              afterBuildTicks(axis) {
                axis.ticks = moneyTicks
                  .filter(t => t >= axis.min && t <= axis.max * 2)
                  .map(t => ({ value: t }));
              },
            },
            y: {
              type: "logarithmic",
              title: { display: true, text: "ARR →", font: { size: 10 }, color: "#bbb" },
              min: 1e5,
              ticks: {
                callback(v) { return moneyTicks.includes(v) ? fmtMoney(v) : null; },
                font: { size: 10 }, color: "#aaa", maxTicksLimit: 6,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
              afterBuildTicks(axis) {
                axis.ticks = moneyTicks
                  .filter(t => t >= axis.min && t <= axis.max * 2)
                  .map(t => ({ value: t }));
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: () => "",
                label(ctx) {
                  const c = ctx.dataset.data[0]._company;
                  const ratio = c.arr / c.funding.total;
                  return [
                    c.name,
                    "ARR: " + fmtMoney(c.arr),
                    "Funding: " + fmtMoney(c.funding.total),
                    "Capital efficiency: " + ratio.toFixed(2) + "x",
                  ];
                },
              },
            },
          },
        },
        plugins: [{
          id: "ratioLines",
          beforeDatasetsDraw(chart) {
            const { ctx, chartArea, scales: { x, y } } = chart;
            if (!chartArea) return;
            ctx.save();
            ctx.strokeStyle = "rgba(120,120,120,0.15)";
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.fillStyle = "rgba(120,120,120,0.55)";
            ctx.font = "10px sans-serif";
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            const ratios = [
              { r: 1.0, label: "1.0× ARR/$" },
              { r: 0.5, label: "0.5×" },
              { r: 0.25, label: "0.25×" },
            ];
            ratios.forEach(({ r, label }) => {
              const x1 = x.min, x2 = x.max;
              const y1 = r * x1, y2 = r * x2;
              if (y1 < y.min && y2 < y.min) return;
              const px1 = x.getPixelForValue(x1);
              const py1 = y.getPixelForValue(Math.max(y1, y.min));
              const px2 = x.getPixelForValue(x2);
              const py2 = y.getPixelForValue(Math.min(y2, y.max));
              ctx.beginPath();
              ctx.moveTo(px1, py1);
              ctx.lineTo(px2, py2);
              ctx.stroke();
              ctx.fillText(label, px2 - 60, py2 - 6);
            });
            ctx.restore();
          },
        }, {
          id: "logoPoints",
          afterDatasetsDraw(chart) {
            chart.data.datasets.forEach((ds, i) => {
              const meta = chart.getDatasetMeta(i);
              const el = meta.data[0];
              if (!el) return;
              const c = ds.data[0]._company;
              drawLogoBox(chart.ctx, logos[c.id], c, el.x, el.y);
            });
          },
        }],
      });
    }

    const logos = preloadLogos(eligible, build);
    build(logos);

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [companies]);

  return (
    <div className="card">
      <div className="card-h">
        <h3>Capital efficiency</h3>
        <span className="meta">ARR per $ raised · {eligible.length} comps</span>
      </div>
      <div style={{padding:"16px 16px 8px"}}>
        {eligible.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No ARR data available for this cohort.</div>
          : <canvas ref={canvasRef} />
        }
      </div>
      <div style={{padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        Above the 1.0× line = punching above weight. Below 0.25× = capital-inefficient.
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Chart 2 — Funding Round Timeline
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
      "Seed": "#84cc16",
      "Series A": "#22d3ee",
      "Series B": "#3b82f6",
      "Series C": "#8b5cf6",
      "Series D": "#a855f7",
      "Series E": "#d946ef",
      "Series F": "#ec4899",
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
        pointRadius: (ctx) => {
          const amt = ctx.raw?._round?.amountEur || 0;
          return Math.max(6, Math.min(18, 6 + Math.log10(amt / 1e6 + 1) * 4));
        },
        pointHoverRadius: 22,
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
              callback(v) {
                const d = new Date(v);
                return d.getFullYear();
              },
              font: { size: 10 }, color: "#aaa", maxTicksLimit: 10,
            },
            grid: { color: "rgba(0,0,0,0.05)" },
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
            grid: { color: "rgba(0,0,0,0.05)" },
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
    "Seed": "#84cc16", "Series A": "#22d3ee", "Series B": "#3b82f6",
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
        <span>Bubble size ≈ round amount</span>
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
//  Chart 3 — Investor Concentration Graph (SVG)
// ────────────────────────────────────────────────────────────────
function InvestorConcentrationGraph({ companies, onPick }) {
  // Build investor → companies map
  const investorMap = new Map();
  companies.forEach(c => {
    (c.notable_investors || []).forEach(inv => {
      if (!inv.name) return;
      const key = inv.name.trim();
      if (!investorMap.has(key)) investorMap.set(key, { name: key, domain: inv.domain, companies: [] });
      investorMap.get(key).companies.push(c);
    });
  });

  // Sort investors: by count of cohort backings desc, then name
  const investors = [...investorMap.values()].sort((a, b) => b.companies.length - a.companies.length || a.name.localeCompare(b.name));
  // Cap to top 12 for readability; flag shared (count>=2) for emphasis
  const topInvestors = investors.slice(0, 12);
  const sharedCount = investors.filter(i => i.companies.length >= 2).length;

  const W = 520;
  const ROW_H = 26;
  const H = Math.max(topInvestors.length, companies.length) * ROW_H + 40;
  const COL_LEFT = 130;
  const COL_RIGHT = W - 130;

  return (
    <div className="card">
      <div className="card-h">
        <h3>Investor concentration</h3>
        <span className="meta">{investors.length} investors · {sharedCount} shared</span>
      </div>
      <div style={{padding:"12px 12px 6px", overflowX:"auto"}}>
        {investors.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No investor data.</div>
          : (
            <svg viewBox={`0 0 ${W} ${H}`} style={{width:"100%", height:H, maxHeight:380, display:"block"}}>
              <text x={20} y={18} fontSize={10} fill="#888" fontFamily="sans-serif">Investors</text>
              <text x={W - 20} y={18} fontSize={10} fill="#888" fontFamily="sans-serif" textAnchor="end">Companies</text>
              {/* Edges */}
              {topInvestors.flatMap((inv, i) =>
                inv.companies.map(c => {
                  const ci = companies.findIndex(x => x.id === c.id);
                  if (ci < 0) return null;
                  const y1 = 30 + i * ROW_H + ROW_H / 2;
                  const y2 = 30 + ci * ROW_H + ROW_H / 2;
                  return (
                    <line
                      key={`${inv.name}-${c.id}`}
                      x1={COL_LEFT} y1={y1}
                      x2={COL_RIGHT} y2={y2}
                      stroke={c.isSubject ? ACCENT : (inv.companies.length >= 2 ? "rgba(179,74,31,0.4)" : "rgba(0,0,0,0.15)")}
                      strokeWidth={c.isSubject ? 1.5 : 1}
                    />
                  );
                })
              )}
              {/* Investor nodes */}
              {topInvestors.map((inv, i) => {
                const y = 30 + i * ROW_H + ROW_H / 2;
                const r = 4 + Math.min(inv.companies.length, 5) * 2;
                const shared = inv.companies.length >= 2;
                return (
                  <g key={inv.name}>
                    <circle cx={COL_LEFT} cy={y} r={r} fill={shared ? ACCENT : "#888"} fillOpacity={shared ? 0.85 : 0.5} />
                    <text x={COL_LEFT - r - 6} y={y + 3} fontSize={11} fill="#333" textAnchor="end" fontFamily="sans-serif">
                      {inv.name} {inv.companies.length >= 2 ? `(${inv.companies.length})` : ""}
                    </text>
                  </g>
                );
              })}
              {/* Company nodes */}
              {companies.map((c, i) => {
                const y = 30 + i * ROW_H + ROW_H / 2;
                return (
                  <g key={c.id} style={{cursor:"pointer"}} onClick={() => onPick && onPick(c)}>
                    <rect
                      x={COL_RIGHT - 6} y={y - 8}
                      width={12} height={16} rx={3}
                      fill={c.isSubject ? ACCENT + "33" : "#f4f4f4"}
                      stroke={c.isSubject ? ACCENT : "#bbb"}
                      strokeWidth={c.isSubject ? 1.5 : 1}
                    />
                    <text x={COL_RIGHT + 14} y={y + 4} fontSize={11} fill="#333" fontFamily="sans-serif">
                      {c.name}
                    </text>
                  </g>
                );
              })}
            </svg>
          )
        }
      </div>
      <div style={{padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        Shared investors (orange) signal cohort conviction.
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Chart 4 — Customer Logo Overlap
// ────────────────────────────────────────────────────────────────
function CustomerLogoOverlap({ companies, onPick }) {
  // Build customer → companies map
  const customerMap = new Map();
  companies.forEach(c => {
    (c.notable_customers || []).forEach(cust => {
      if (!cust.name) return;
      const key = cust.name.trim();
      if (!customerMap.has(key)) customerMap.set(key, { name: key, domain: cust.domain, segments: new Set(), companyIds: new Set() });
      const entry = customerMap.get(key);
      entry.companyIds.add(c.id);
      if (cust.segment) entry.segments.add(cust.segment);
    });
  });

  // Sort: shared (count desc) first, then alphabetical
  const rows = [...customerMap.values()]
    .map(r => ({ ...r, count: r.companyIds.size }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));

  const sharedCount = rows.filter(r => r.count >= 2).length;

  return (
    <div className="card">
      <div className="card-h">
        <h3>Customer overlap</h3>
        <span className="meta">{rows.length} customers · {sharedCount} contested</span>
      </div>
      <div style={{padding:"6px 12px 12px", overflowX:"auto", maxHeight:380, overflowY:"auto"}}>
        {rows.length === 0
          ? <div style={{padding:"40px 0", textAlign:"center", color:"var(--fg-4)", fontSize:12}}>No customer data.</div>
          : (
            <table className="customer-overlap-table" style={{width:"100%", borderCollapse:"collapse", fontSize:11}}>
              <thead>
                <tr>
                  <th style={{textAlign:"left", padding:"6px 8px", color:"#888", fontWeight:500, position:"sticky", top:0, background:"var(--bg)", borderBottom:"1px solid var(--border)"}}>Customer</th>
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
                {rows.map(r => (
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
      <div style={{padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        Contested logos (×n) indicate ICP convergence.
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
          Four VC-grade views of the cohort. Click any company to drill in.
        </p>
      </div>

      <CapitalEfficiencyMatrix companies={all} onPick={handlePick} />

      <div className="positioning-grid">
        <InvestorConcentrationGraph companies={all} onPick={handlePick} />
        <CustomerLogoOverlap companies={all} onPick={handlePick} />
      </div>

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
              {typeof selected.arr === "number" ? " · ARR " + fmtMoney(selected.arr) : ""}
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
