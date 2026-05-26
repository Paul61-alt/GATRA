// screens-overview.jsx — exec summary for the scan
const { useMemo: _uM_ov, useState: _uS_ov, useEffect: _uE_ov, useRef: _uR_ov } = React;

function TaglineCollapse({ text }) {
  const [expanded, setExpanded] = _uS_ov(false);
  const MAX = 180;
  const short = text && text.length > MAX;
  return (
    <p className="serif" style={{
      fontSize: 15, color:"var(--fg-2)", margin:"8px 0 0",
      fontStyle:"italic", lineHeight: 1.6,
    }}>
      "{expanded || !short ? text : text.slice(0, MAX) + "…"}"
      {short && (
        <button onClick={() => setExpanded(v => !v)} style={{
          background:"none", border:"none", padding:"0 0 0 6px",
          color:"var(--accent)", fontSize:12, cursor:"pointer",
          fontFamily:"var(--font-mono)", fontStyle:"normal",
        }}>
          {expanded ? "collapse" : "read more"}
        </button>
      )}
    </p>
  );
}

function OverviewScreen({ data, onOpenCompany, loadingPhase = 2 }) {
  const { subject, competitors } = data;

  const totalRaised = competitors.reduce((s, c) => s + (c.funding?.total || 0), 0);
  const highCount   = competitors.filter(c => c.threat === "high").length;
  const medCount    = competitors.filter(c => c.threat === "medium").length;
  const lowCount    = competitors.filter(c => c.threat === "low").length;
  const mostFunded  = [...competitors].sort((a, b) => (b.funding?.total || 0) - (a.funding?.total || 0))[0];
  const topThreats  = competitors.slice().sort((a, b) => b.similarity - a.similarity).slice(0, 4);

  const subjectReady    = loadingPhase >= 1;
  const competitorsReady = loadingPhase >= 2;

  return (
    <div className="screen">

      {/* ── Header ── */}
      <div style={{marginBottom:28}}>
        <div style={{display:"flex", alignItems:"center", gap:14, flexWrap:"wrap"}}>
          {subjectReady
            ? <LogoMark name={subject.name} domain={subject.domain} subject={true} size="lg" />
            : <Skel w={40} h={40} radius={8} />
          }
          {subjectReady
            ? <h1 style={{fontFamily:"var(--font-serif)", fontSize:32, fontWeight:500, letterSpacing:"-0.02em", margin:0}}>{subject.name}</h1>
            : <Skel w={180} h={28} radius={6} />
          }
          {/* Domain always visible */}
          <a href={`https://${subject.domain}`} target="_blank" rel="noopener noreferrer"
            className="mono muted"
            style={{fontSize:12.5, color:"inherit", textDecoration:"none"}}
            onClick={e => e.stopPropagation()}>
            {subject.domain} {Icons.ext}
          </a>
          {subjectReady && <span className="tag subject mono">SUBJECT</span>}
        </div>
        <div style={{marginTop:10}}>
          {subjectReady
            ? <TaglineCollapse text={subject.tagline} />
            : <><Skel w="80%" h={12} radius={4} style={{marginBottom:6}} /><Skel w="60%" h={12} radius={4} /></>
          }
        </div>
        <div style={{display:"flex", gap:16, marginTop:10, flexWrap:"wrap", color:"var(--fg-3)", fontSize:12}}>
          {subjectReady ? (
            <>
              <span className="row" style={{gap:6}}>{Icons.building} {subject.category} · {subject.subCategory}</span>
              <span className="row" style={{gap:6}}>{Icons.pin} {subject.hq}</span>
            </>
          ) : (
            <><Skel w={160} h={11} radius={3} /><Skel w={100} h={11} radius={3} /></>
          )}
        </div>
      </div>

      {/* ── Subject stat row ── */}
      <div className="card" style={{marginBottom:20}}>
        <div className="stat-row">
          {subjectReady ? (
            <>
              <div className="stat">
                <div className="lbl">Founded</div>
                <div className="val" style={{fontFamily:"var(--font-serif)"}}>{subject.founded}</div>
                <div className="delta">{subject.hq?.split(",")[0]}</div>
              </div>
              <div className="stat">
                <div className="lbl">Employees</div>
                <div className="val">{(subject.employees || 0).toLocaleString()}</div>
                <div className="delta"><span style={{color:"var(--positive)"}}>+{fmtPct(subject.employeeGrowth)}</span> YoY</div>
              </div>
              <div className="stat">
                <div className="lbl">Total raised</div>
                <div className="val">{fmtMoney(subject.funding?.total || 0)}</div>
                <div className="delta">{subject.funding?.lastRound} · {fmtDate(subject.funding?.lastRoundAt || "")}</div>
              </div>
              <div className="stat">
                <div className="lbl">ARR</div>
                <div className="val">{subject.arr ? fmtMoney(subject.arr) : "—"}</div>
                <div className="delta">{subject.customers ? fmtNum(subject.customers) + " customers" : "—"}</div>
              </div>
            </>
          ) : (
            [0,1,2,3].map(i => (
              <div className="stat" key={i}>
                <Skel w={60} h={9} radius={3} style={{marginBottom:8}} />
                <Skel w={80} h={22} radius={4} style={{marginBottom:6}} />
                <Skel w={100} h={9} radius={3} />
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Notable customers ── */}
      {subjectReady && subject.notable_customers && subject.notable_customers.length > 0 && (
        <div className="card" style={{marginBottom:20}}>
          <div className="card-h">
            <h3>Notable customers</h3>
            <span className="meta">{subject.notable_customers.length} highlighted</span>
          </div>
          <div style={{
            display:"flex", alignItems:"center", gap:0,
            padding:"0",
            flexWrap:"wrap",
          }}>
            {subject.notable_customers.map((c, i) => (
              <a key={c.domain} href={`https://${c.domain}`} target="_blank" rel="noopener noreferrer"
                style={{
                  display:"flex", alignItems:"center", gap:10,
                  padding:"12px 20px",
                  flex:"0 0 auto",
                  textDecoration:"none",
                  borderRadius:6,
                  transition:"background .15s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <img
                  src={`https://img.logo.dev/${c.domain}?token=pk_OyZO8po6QHG5X9zwE8ayZQ&size=40&format=png`}
                  width={24} height={24}
                  alt={c.name}
                  style={{borderRadius:5, objectFit:"contain", background:"var(--bg-2)"}}
                  onError={e => { e.target.style.display = "none"; }}
                />
                <span style={{fontSize:13, fontWeight:500, color:"var(--fg-2)", whiteSpace:"nowrap"}}>{c.name}</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ── Notable investors ── */}
      {subjectReady && subject.notable_investors && subject.notable_investors.length > 0 && (
        <div className="card" style={{marginBottom:20}}>
          <div className="card-h">
            <h3>Notable investors</h3>
            <span className="meta">{subject.notable_investors.length} highlighted</span>
          </div>
          <div style={{display:"flex", alignItems:"center", flexWrap:"wrap", padding:"0"}}>
            {subject.notable_investors.map((c) => (
              <a key={c.domain} href={`https://${c.domain}`} target="_blank" rel="noopener noreferrer"
                style={{
                  display:"flex", alignItems:"center", gap:10,
                  padding:"12px 20px", flex:"0 0 auto",
                  textDecoration:"none", borderRadius:6, transition:"background .15s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <img
                  src={`https://img.logo.dev/${c.domain}?token=pk_OyZO8po6QHG5X9zwE8ayZQ&size=40&format=png`}
                  width={24} height={24}
                  alt={c.name}
                  style={{borderRadius:5, objectFit:"contain", background:"var(--bg-2)"}}
                  onError={e => { e.target.style.display = "none"; }}
                />
                <span style={{fontSize:13, fontWeight:500, color:"var(--fg-2)", whiteSpace:"nowrap"}}>{c.name}</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ── Two-col layout ── */}
      <div style={{display:"grid", gridTemplateColumns:"1.4fr 1fr", gap: 20, alignItems:"start"}}>

        {/* Top threats */}
        <div className="card">
          <div className="card-h">
            <h3>Top threats</h3>
            <span className="meta">By similarity × momentum</span>
          </div>
          {!competitorsReady ? (
            <div style={{padding:"8px 0"}}>
              {[0,1,2,3].map(i => (
                <div key={i} style={{display:"flex", gap:12, alignItems:"center", padding:"14px 16px", borderBottom: i<3?"1px solid var(--border-dim)":"none"}}>
                  <Skel w={28} h={28} radius={6} style={{flexShrink:0}} />
                  <div style={{flex:1}}>
                    <Skel w={100} h={12} radius={3} style={{marginBottom:6}} />
                    <Skel w="80%" h={10} radius={3} />
                  </div>
                  <Skel w={70} h={10} radius={3} />
                  <Skel w={50} h={10} radius={3} />
                </div>
              ))}
            </div>
          ) : (
          <div>
            {topThreats.map((c, i) => (
              <div key={c.id}
                onClick={() => onOpenCompany && onOpenCompany(c.id)}
                style={{
                  display:"grid", gridTemplateColumns:"auto 1fr auto auto auto",
                  gap: 14, alignItems:"center",
                  padding:"14px 16px",
                  borderBottom: i < topThreats.length - 1 ? "1px solid var(--border-dim)" : "none",
                  cursor:"pointer",
                }}>
                <LogoMark name={c.name} domain={c.domain} />
                <div>
                  <div style={{display:"flex", gap:8, alignItems:"baseline"}}>
                    <span style={{fontWeight:500, color:"var(--fg)"}}>{c.name}</span>
                    <span className="mono dim" style={{fontSize:11}}>{c.domain}</span>
                  </div>
                  <div className="muted" style={{fontSize:12, marginTop:2}}>{c.tagline}</div>
                </div>
                <div style={{minWidth: 110}}>
                  <div className="mono" style={{fontSize:10, color:"var(--fg-4)", letterSpacing:"0.06em", textTransform:"uppercase"}}>Similarity</div>
                  <div style={{display:"flex", alignItems:"center", gap:8, marginTop:4}}>
                    <Bar value={c.similarity * 100} />
                    <span className="mono" style={{fontSize:11.5, fontWeight:500}}>{(c.similarity * 100).toFixed(0)}</span>
                  </div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div className="mono" style={{fontSize:10, color:"var(--fg-4)", letterSpacing:"0.06em", textTransform:"uppercase"}}>Funding</div>
                  <div className="mono" style={{fontSize:13, fontWeight:500, marginTop:4}}>{fmtMoney((c.funding?.total || 0))}</div>
                </div>
                <ThreatTag level={c.threat} />
              </div>
            ))}
          </div>
          )}
        </div>

        {/* Quick scan summary */}
        <div className="card">
          <div className="card-h">
            <h3>Analyst summary</h3>
            <span className="meta">Auto · {fmtDate(data.query.scannedAt.slice(0,7))}</span>
          </div>
          {!competitorsReady ? (
            <div className="card-b">
              {[1, 0.7, 0.5].map((w, i) => <Skel key={i} w={`${w*100}%`} h={11} radius={3} style={{marginBottom:8, display:"block"}} />)}
              <div style={{height:1, background:"var(--border)", margin:"12px 0"}} />
              <div style={{display:"flex", gap:6, flexWrap:"wrap"}}>
                {[80,110,90,130,70].map((w,i) => <Skel key={i} w={w} h={22} radius={4} />)}
              </div>
            </div>
          ) : (
            <div className="card-b" style={{fontSize: 13.5, lineHeight: 1.6, color:"var(--fg-2)"}}>
              <p style={{marginTop:0}}>
                <strong style={{color:"var(--fg)"}}>{subject.name}</strong> operates in
                {" "}<strong style={{color:"var(--fg)"}}>{subject.category}</strong> — {subject.subCategory}.
                {" "}{competitors.length} competitors mapped in this space.
              </p>
              <p>
                Most-funded rival: <strong style={{color:"var(--accent)"}}>{mostFunded?.name}</strong> at {fmtMoney(mostFunded?.funding?.total || 0)}.
                {" "}{highCount} high-threat · {medCount} medium · {lowCount} low.
              </p>
              <hr className="divider" style={{margin:"12px 0"}}/>
              <div style={{display:"flex", gap:8, flexWrap:"wrap"}}>
                {subject.notable.map(n => (
                  <span key={n} className="tag" style={{fontSize:11}}>{n}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>


    </div>
  );
}

// PositioningMatrix moved to screens-positioning.jsx
function PositioningMatrix({ data, onOpenCompany }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];
  const canvasRef = _uR_ov(null);
  const chartRef = _uR_ov(null);
  const [selected, setSelected] = _uS_ov(null);
  const LOGO_SIZE = 28;
  const LOGO_HALF = LOGO_SIZE / 2;

  _uE_ov(() => {
    if (!canvasRef.current || typeof Chart === "undefined") return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    const accentColor = "#b34a1f";

    // Pre-load logos
    const logos = {};
    let loaded = 0;
    const total = all.length;

    function buildChart() {
      const datasets = all.map(c => ({
        label: c.name,
        data: [{
          x: c.founded || 2000,
          y: Math.max(c.funding?.total || 1, 1e5),
          _company: c,
        }],
        pointRadius: LOGO_HALF + 2,
        pointHoverRadius: LOGO_HALF + 4,
        backgroundColor: "transparent",
        borderColor: "transparent",
      }));

      const cleanTicks = [1e5, 1e6, 1e7, 5e7, 1e8, 5e8, 1e9];

      chartRef.current = new Chart(canvasRef.current, {
        type: "scatter",
        data: { datasets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 2.4,
          animation: false,
          onClick(evt) {
            if (!chartRef.current) return;
            const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
            if (!pts.length) { setSelected(null); return; }
            const c = datasets[pts[0].datasetIndex].data[0]._company;
            if (onOpenCompany && !c.isSubject) { onOpenCompany(c.id); return; }
            setSelected(c);
          },
          scales: {
            x: {
              title: { display: true, text: "Founded →", font: { size: 10 }, color: "#bbb" },
              min: Math.min(...all.map(c => c.founded || 2000)) - 2,
              max: new Date().getFullYear() + 1,
              ticks: {
                callback: v => Number.isInteger(v) ? v : null,
                font: { size: 10 }, color: "#aaa",
                maxTicksLimit: 8,
                stepSize: 2,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
            },
            y: {
              type: "logarithmic",
              title: { display: true, text: "Funding →", font: { size: 10 }, color: "#bbb" },
              min: 5e4,
              ticks: {
                callback(v) {
                  if (cleanTicks.includes(v)) return fmtMoney(v);
                  return null;
                },
                font: { size: 10 }, color: "#aaa",
                maxTicksLimit: 7,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
              afterBuildTicks(axis) {
                axis.ticks = cleanTicks
                  .filter(t => t >= axis.min && t <= axis.max * 2)
                  .map(t => ({ value: t }));
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label(ctx) {
                  const c = ctx.dataset.data[0]._company;
                  return [
                    c.name,
                    "Founded: " + (c.founded || "—"),
                    "Funding: " + fmtMoney(c.funding?.total || 0),
                  ];
                },
                title: () => "",
              },
            },
          },
        },
        plugins: [{
          id: "logoPoints",
          afterDatasetsDraw(chart) {
            const ctx2 = chart.ctx;
            chart.data.datasets.forEach((ds, i) => {
              const meta = chart.getDatasetMeta(i);
              const el = meta.data[0];
              if (!el) return;
              const c = ds.data[0]._company;
              const px = el.x, py = el.y;

              ctx2.save();
              // border: accent for subject, light grey for others
              ctx2.strokeStyle = c.isSubject ? accentColor : "#d0d0d0";
              ctx2.lineWidth = c.isSubject ? 2 : 1.5;
              ctx2.beginPath();
              ctx2.roundRect(px - LOGO_HALF - 2, py - LOGO_HALF - 2, LOGO_SIZE + 4, LOGO_SIZE + 4, 5);
              ctx2.stroke();

              const img = logos[c.id];
              if (img && img.complete && img.naturalWidth > 0) {
                ctx2.save();
                ctx2.beginPath();
                ctx2.roundRect(px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE, 4);
                ctx2.clip();
                ctx2.fillStyle = "#fff";
                ctx2.fill();
                ctx2.drawImage(img, px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE);
                ctx2.restore();
              } else {
                // fallback: initials
                ctx2.fillStyle = c.isSubject ? accentColor + "22" : "rgba(0,0,0,0.08)";
                ctx2.beginPath();
                ctx2.roundRect(px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE, 4);
                ctx2.fill();
                ctx2.fillStyle = c.isSubject ? accentColor : "#666";
                ctx2.font = "bold 11px sans-serif";
                ctx2.textAlign = "center";
                ctx2.textBaseline = "middle";
                const parts = c.name.split(/\s+/);
                const initials = (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
                ctx2.fillText(initials, px, py);
              }
              ctx2.restore();
            });
          },
        }],
      });
    }

    // Load all logos then build chart; redraw as each loads
    all.forEach(c => {
      if (!c.domain) { loaded++; if (loaded === total) buildChart(); return; }
      const img = new Image();
      img.src = `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${c.domain}&size=64`;
      logos[c.id] = img;
      img.onload = () => {
        loaded++;
        if (loaded === total) buildChart();
        else if (chartRef.current) chartRef.current.update("none");
      };
      img.onerror = () => {
        loaded++;
        if (loaded === total) buildChart();
      };
    });
    if (all.every(c => !c.domain)) buildChart();

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [data]);

  return (
    <div className="card">
      <div className="card-h">
        <h3>Positioning matrix</h3>
        <span className="meta">Funding raised (log) × Founded year</span>
      </div>
      <div style={{padding:"16px 16px 8px"}}>
        <canvas ref={canvasRef} />
      </div>
      {selected && (
        <div style={{
          margin:"0 16px 14px",
          padding:"12px 14px",
          background:"var(--bg-2)",
          borderRadius:6,
          border:"1px solid var(--border)",
          display:"flex", alignItems:"center", gap:14,
        }}>
          <LogoMark name={selected.name} domain={selected.domain} subject={selected.isSubject} />
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontWeight:600, fontSize:13}}>{selected.name}</div>
            <div className="mono" style={{fontSize:11, color:"var(--fg-3)", marginTop:2}}>
              {selected.subCategory} · {fmtMoney(selected.funding?.total || 0)} raised
              {!selected.isSubject && " · " + (selected.similarity * 100).toFixed(0) + "% similarity"}
            </div>
          </div>
          {!selected.isSubject && <ThreatTag level={selected.threat} />}
          <button onClick={() => setSelected(null)} style={{background:"none",border:"none",cursor:"pointer",color:"var(--fg-4)"}}>
            {Icons.x}
          </button>
        </div>
      )}
      <div style={{display:"flex", gap:16, padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
        <span>Click a logo to inspect</span>
        <span style={{marginLeft:"auto"}}><span style={{display:"inline-block",width:10,height:10,border:"2px solid #b34a1f",borderRadius:2,marginRight:4}}></span>Subject</span>
      </div>
    </div>
  );
}

window.OverviewScreen = OverviewScreen;
