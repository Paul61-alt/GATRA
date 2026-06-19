// screens-timeline.jsx — custom SVG interactive timeline
const { useState: _uS_tl, useEffect: _uE_tl, useRef: _uR_tl, useCallback: _uC_tl, useMemo: _uMemo_tl } = React;

const ACCENT  = "#b34a1f";
const ROW_H   = 56;   // taller rows give vertical room
const LABEL_W = 200;
const AXIS_H  = 26;
const MIN_R   = 6;
const MAX_R   = ROW_H / 2 - 2;
const LOG_SCALE_RATIO_THRESHOLD = 100; // max/min disclosed amount ratio → auto log scale

const SORT_OPTIONS = [
  { key: "first",       label: "First raise" },
  { key: "last",        label: "Last raise"  },
  { key: "total_desc",  label: "Most raised" },
  { key: "total_asc",   label: "Least raised"},
];

function TimelineScreen({ data, onOpenCompany }) {
  const { subject, competitors, funding } = data;
  const all = [subject, ...competitors];

  // ── Compute default view window ───────────────────────────────────
  const allRoundsAll       = all.flatMap(c => funding[c.id] || []);
  const allRoundsDisclosed = allRoundsAll.filter(e => e.amt > 0);
  const earliestYear = allRoundsDisclosed.length
    ? Math.min(...allRoundsDisclosed.map(e => e.y))
    : new Date().getFullYear() - 5;
  const DEFAULT_START = new Date(earliestYear - 3, 0, 1).getTime();
  const DEFAULT_END   = new Date(2027, 11, 31).getTime();

  // Auto log-scale when funding amounts span > 2 orders of magnitude — otherwise
  // mega-rounds visually crush small seeds against the radius floor.
  const { minAmt, maxAmt, autoLog } = _uMemo_tl(() => {
    const disclosed = all.flatMap(c => (funding[c.id] || []).filter(e => e.amt > 0));
    if (!disclosed.length) return { minAmt: 0, maxAmt: 0, autoLog: false };
    const amts = disclosed.map(e => e.amt);
    const max = Math.max(...amts);
    const min = Math.min(...amts);
    return { minAmt: min, maxAmt: max, autoLog: max / min > LOG_SCALE_RATIO_THRESHOLD };
  }, [data]);

  const [view, setView]       = _uS_tl({ start: DEFAULT_START, end: DEFAULT_END });
  const [sortBy, setSortBy]   = _uS_tl("total_desc");
  const [selected, setSelected] = _uS_tl(null);
  const [tooltip, setTooltip] = _uS_tl(null);
  const [scaleOverride, setScaleOverride] = _uS_tl(null); // null = auto | "linear" | "log"
  const useLogScale = scaleOverride === null ? autoLog : scaleOverride === "log";

  const wrapRef = _uR_tl(null);
  const svgRef  = _uR_tl(null);
  const dragRef = _uR_tl(null);
  const [svgW, setSvgW] = _uS_tl(800);

  _uE_tl(() => {
    if (!wrapRef.current) return;
    const obs = new ResizeObserver(e => setSvgW(e[0].contentRect.width));
    obs.observe(wrapRef.current);
    return () => obs.disconnect();
  }, []);

  const toX = (ms) => ((ms - view.start) / (view.end - view.start)) * svgW;

  // ── Pan only (no scroll zoom) ────────────────────────────────────
  const onMouseDown = (e) => {
    e.preventDefault();
    dragRef.current = { clientX: e.clientX, start: view.start, end: view.end };
  };
  const onMouseMove = (e) => {
    if (!dragRef.current) return;
    const dur   = dragRef.current.end - dragRef.current.start;
    const delta = -((e.clientX - dragRef.current.clientX) / svgW) * dur;
    setView({ start: dragRef.current.start + delta, end: dragRef.current.end + delta });
  };
  const onMouseUp = () => { dragRef.current = null; };

  // ── Zoom helpers (buttons only) ──────────────────────────────────
  const zoomAround = (factor) => {
    setView(v => {
      const dur    = v.end - v.start;
      const center = (v.start + v.end) / 2;
      const newDur = Math.min(Math.max(dur * factor, 1.5e10), 9.5e11);
      return { start: center - newDur / 2, end: center + newDur / 2 };
    });
  };

  // ── Sort rows, subject always first ──────────────────────────────
  const rows = _uMemo_tl(() => {
    const sub   = all.find(c => c.isSubject);
    const comps = all.filter(c => !c.isSubject).map(c => {
      const rounds = funding[c.id] || [];
      // Sort by first/last *disclosed* raise — undisclosed rounds ignored for sort ordering.
      const disclosedYrs = rounds.filter(e => e.amt > 0).map(e => e.y);
      return {
        ...c, rounds,
        _total: (c.funding?.total || 0),
        _firstY: disclosedYrs[0] ?? 9999,
        _lastY: disclosedYrs[disclosedYrs.length - 1] ?? 0,
      };
    });

    comps.sort((a, b) => {
      if (sortBy === "first")      return a._firstY - b._firstY;
      if (sortBy === "last")       return b._lastY  - a._lastY;
      if (sortBy === "total_desc") return b._total  - a._total;
      if (sortBy === "total_asc")  return a._total  - b._total;
      return 0;
    });

    const subRounds = funding[sub.id] || [];
    return [
      { ...sub, rounds: subRounds, _total: sub.funding?.total || 0 },
      ...comps,
    ];
  }, [sortBy, data]);

  const radiusFor = (amt) => {
    if (!amt || amt <= 0 || maxAmt <= 0) return MIN_R;
    if (useLogScale) {
      const norm = Math.log10(amt + 1) / Math.log10(maxAmt + 1);
      return Math.max(MIN_R, Math.min(MAX_R, norm * MAX_R));
    }
    const norm = Math.sqrt(amt / maxAmt);
    return Math.max(MIN_R, Math.min(MAX_R, norm * MAX_R));
  };

  const enrichedRows = rows.map(c => ({
    ...c,
    rounds: c.rounds.map(e => ({
      ...e,
      ms: new Date(e.y, (e.q - 1) * 3, 15).getTime(),
      r: radiusFor(e.amt),
      undisclosed: !e.amt || e.amt <= 0,
    })),
  }));

  // ── Year ticks ───────────────────────────────────────────────────
  const startYear = new Date(view.start).getFullYear() - 1;
  const endYear   = new Date(view.end).getFullYear()   + 1;
  const yearTicks = [];
  for (let y = startYear; y <= endYear; y++) yearTicks.push(y);

  const svgH       = enrichedRows.length * ROW_H;
  const totalRaised = all.reduce((s, c) => s + (funding[c.id] || []).reduce((a, b) => a + (b.amt > 0 ? b.amt : 0), 0), 0);
  const totalEvents = allRoundsDisclosed.length;
  const undisclosedCount = allRoundsAll.length - allRoundsDisclosed.length;

  return (
    <div className="screen">
      <SectionH title="Funding timeline"
                meta={`${totalEvents} disclosed${undisclosedCount ? ` · ${undisclosedCount} undisclosed` : ""} · $${totalRaised.toFixed(0)}M total · ${useLogScale ? "log" : "linear"} scale`} />

      {/* Controls */}
      <div style={{display:"flex", gap:8, marginBottom:12, flexWrap:"wrap", alignItems:"center"}}>
        <button className="tb-btn" onClick={() => zoomAround(0.6)}>{Icons.plus}<span>Zoom in</span></button>
        <button className="tb-btn" onClick={() => zoomAround(1.7)}>{Icons.minus}<span>Zoom out</span></button>
        <button className="tb-btn" onClick={() => setView({ start: DEFAULT_START, end: DEFAULT_END })}>{Icons.map}<span>Fit all</span></button>

        <div style={{width:1, height:20, background:"var(--border)", margin:"0 4px"}}></div>

        <span style={{fontSize:11, color:"var(--fg-4)"}}>Sort:</span>
        {SORT_OPTIONS.map(o => (
          <button key={o.key}
                  className={"tb-btn" + (sortBy === o.key ? " primary" : "")}
                  onClick={() => setSortBy(o.key)}>
            {o.label}
          </button>
        ))}

        <div style={{marginLeft:"auto", display:"flex", alignItems:"center", gap:6}}>
          <span style={{fontSize:11, color:"var(--fg-4)"}}>Scale:</span>
          <button className={"tb-btn" + (!useLogScale ? " primary" : "")}
                  onClick={() => setScaleOverride("linear")}
                  title="Linear (sqrt) scale">Linear</button>
          <button className={"tb-btn" + (useLogScale ? " primary" : "")}
                  onClick={() => setScaleOverride("log")}
                  title={autoLog && minAmt > 0
                    ? `Log scale (auto-suggested: ratio ${Math.round(maxAmt / minAmt)}×)`
                    : "Log scale"}>Log</button>
          <div style={{width:1, height:20, background:"var(--border)", margin:"0 6px"}}></div>
          <svg width={12} height={12} style={{flexShrink:0}}>
            <polygon points="6,0 12,6 6,12 0,6" fill="#0ea5e9" fillOpacity={0.85} />
          </svg>
          <span style={{fontSize:11, color:"var(--fg-4)"}}>Founded year</span>
          <span style={{fontSize:11, color:"var(--fg-4)", marginLeft:4}}>· Drag to pan</span>
        </div>
      </div>

      {/* Timeline card */}
      <div className="card" style={{overflow:"hidden", padding:0}}>
        <div style={{display:"flex"}}>

          {/* ── Label column ─────────────────────────────────────── */}
          <div style={{width:LABEL_W, flexShrink:0, borderRight:"1px solid var(--border)"}}>
            <div style={{height:AXIS_H, borderBottom:"1px solid var(--border)", background:"var(--bg-2)"}}></div>
            {enrichedRows.map((c, i) => {
              const total = (funding[c.id] || []).reduce((s, e) => s + e.amt, 0);
              const status = c.funding?.status;
              // F2: empty row when no disclosed rounds + status is not "enriched"
              const showEmptyState = total <= 0 && status && status !== "enriched";
              return (
                <div key={c.id}
                  onClick={() => !c.isSubject && onOpenCompany && onOpenCompany(c.id)}
                  style={{
                    height:ROW_H,
                    display:"flex", alignItems:"center", gap:8,
                    padding:"0 10px",
                    borderBottom:"1px solid var(--border-dim)",
                    background: c.isSubject ? "rgba(179,74,31,0.04)" : i % 2 === 0 ? "var(--bg)" : "rgba(0,0,0,0.015)",
                    boxSizing:"border-box",
                    cursor: c.isSubject ? "default" : "pointer",
                  }}>
                  <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
                  <div style={{minWidth:0, flex:1}}>
                    <div style={{
                      fontSize:12, fontWeight:c.isSubject ? 600 : 500,
                      color:c.isSubject ? ACCENT : "var(--fg)",
                      whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
                    }}>{c.name}</div>
                    <div style={{fontSize:9.5, color:"var(--fg-4)", fontFamily:"var(--font-mono)"}}>
                      {showEmptyState
                        ? <RowEmptyState status={status} founded={c.founded} />
                        : total > 0 ? "€" + total.toFixed(0) + "M" : "—"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── SVG area ─────────────────────────────────────────── */}
          <div ref={wrapRef} style={{flex:1, overflow:"hidden", position:"relative",
               cursor: dragRef.current ? "grabbing" : "grab"}}>
            <svg ref={svgRef} width={svgW} height={svgH + AXIS_H}
                 style={{display:"block", userSelect:"none"}}
                 onMouseDown={onMouseDown}
                 onMouseMove={onMouseMove}
                 onMouseUp={onMouseUp}
                 onMouseLeave={onMouseUp}>

              {/* 1. Row backgrounds */}
              {enrichedRows.map((c, i) => (
                <rect key={c.id}
                      x={0} y={AXIS_H + i * ROW_H} width={svgW} height={ROW_H}
                      fill={c.isSubject ? "rgba(179,74,31,0.03)"
                            : i % 2 === 0 ? "var(--bg)" : "rgba(0,0,0,0.015)"} />
              ))}

              {/* 2. Vertical year grid lines — drawn AFTER backgrounds so visible on every row */}
              {yearTicks.map(y => {
                const x = toX(new Date(y, 0, 1).getTime());
                if (x < -1 || x > svgW + 1) return null;
                return (
                  <line key={y}
                        x1={x} y1={AXIS_H} x2={x} y2={svgH + AXIS_H}
                        stroke="var(--border-dim)" strokeWidth={1} />
                );
              })}

              {/* 3. Horizontal row dividers */}
              {enrichedRows.map((_, i) => (
                <line key={i}
                      x1={0} y1={AXIS_H + (i + 1) * ROW_H}
                      x2={svgW} y2={AXIS_H + (i + 1) * ROW_H}
                      stroke="var(--border-dim)" strokeWidth={1} />
              ))}

              {/* 4. Year axis bar */}
              <rect x={0} y={0} width={svgW} height={AXIS_H} fill="var(--bg-2)" />
              <line x1={0} y1={AXIS_H} x2={svgW} y2={AXIS_H}
                    stroke="var(--border)" strokeWidth={1} />
              {yearTicks.map(y => {
                const x = toX(new Date(y, 0, 1).getTime());
                if (x < -1 || x > svgW + 1) return null;
                return (
                  <g key={y}>
                    <line x1={x} y1={0} x2={x} y2={AXIS_H}
                          stroke="var(--border)" strokeWidth={1} />
                    <text x={x + 4} y={17} fontSize={10}
                          fill="var(--fg-4)" fontFamily="var(--font-mono)">{y}</text>
                  </g>
                );
              })}

              {/* 5 + 6. Per-row: clip → connector → bubbles (all inside the clip) */}
              <defs>
                {enrichedRows.map((c, i) => (
                  <clipPath key={c.id} id={`clip-${i}`}>
                    <rect x={0} y={AXIS_H + i * ROW_H}
                          width={svgW} height={ROW_H} />
                  </clipPath>
                ))}
              </defs>

              {/* Connector lines — outside clip so they reach off-screen bubbles cleanly */}
              {enrichedRows.map((c, i) => {
                const cy  = AXIS_H + i * ROW_H + ROW_H / 2;
                const isS = c.isSubject;
                if (c.rounds.length < 2) return null;
                return (
                  <polyline key={`line-${c.id}`}
                    points={c.rounds.map(e => `${toX(e.ms).toFixed(1)},${cy}`).join(" ")}
                    stroke={isS ? ACCENT : "#9ca3af"}
                    strokeWidth={isS ? 2.5 : 2}
                    fill="none" opacity={isS ? 0.85 : 0.75} />
                );
              })}

              {enrichedRows.map((c, i) => {
                const cy    = AXIS_H + i * ROW_H + ROW_H / 2;
                const isS   = c.isSubject;
                const color = isS ? ACCENT : "#6b7280";
                return (
                  <g key={c.id} clipPath={`url(#clip-${i})`}>
                    {/* Bubbles */}
                    {c.rounds.map((e, j) => {
                      const x   = toX(e.ms);
                      const amt = `$${Math.round(e.amt)}M`;
                      // r < 13 → too small for any text; 13–21 → amount only; ≥22 → round + amount
                      const showAmt   = !e.undisclosed && e.r >= 13;
                      const showRound = !e.undisclosed && e.r >= 22;
                      return (
                        <g key={j} style={{cursor:"pointer"}}
                           onClick={(ev) => { ev.stopPropagation(); setSelected({ company: c, round: e }); }}
                           onMouseEnter={() => setTooltip({ x, y: cy - e.r - 8, company: c, round: e })}
                           onMouseLeave={() => setTooltip(null)}>
                          {e.undisclosed ? (
                            <circle cx={x} cy={cy} r={e.r}
                                    fill="none" stroke={color} strokeWidth={1.5}
                                    strokeDasharray="3,2" opacity={isS ? 0.85 : 0.7} />
                          ) : (
                            <circle cx={x} cy={cy} r={e.r}
                                    fill={color} fillOpacity={isS ? 0.88 : 0.78}
                                    stroke="none" />
                          )}
                          {showRound && (
                            <text x={x} y={cy - 5} textAnchor="middle" dominantBaseline="middle"
                                  fontSize={7} fill="rgba(255,255,255,0.75)"
                                  fontFamily="monospace" fontWeight="500"
                                  style={{pointerEvents:"none"}}>
                              {e.round}
                            </text>
                          )}
                          {showAmt && (
                            <text x={x} y={showRound ? cy + 6 : cy}
                                  textAnchor="middle" dominantBaseline="middle"
                                  fontSize={showRound ? 9 : 8} fill="#fff"
                                  fontFamily="monospace" fontWeight="700"
                                  style={{pointerEvents:"none"}}>
                              {amt}
                            </text>
                          )}
                        </g>
                      );
                    })}
                  </g>
                );
              })}

              {/* F2: Empty-state placeholder for rows with no disclosed rounds */}
              {enrichedRows.map((c, i) => {
                if (c.rounds && c.rounds.length > 0) return null;
                const status = c.funding?.status;
                if (!status || status === "enriched") return null;
                const cy = AXIS_H + i * ROW_H + ROW_H / 2;
                const LABEL = {
                  bootstrapped: "BOOTSTRAPPED · no outside capital",
                  stealth:      "STEALTH · pre-launch",
                  not_found:    "NO DATA · funding not disclosed",
                  pending:      "ENRICHING…",
                };
                const COLOR = {
                  bootstrapped: "var(--fg-3)",
                  stealth:      "#0ea5e9",
                  not_found:    "var(--fg-4)",
                  pending:      "var(--accent, #ff5d00)",
                };
                return (
                  <g key={`empty-${c.id}`} style={{pointerEvents:"none"}}>
                    <line x1={0} y1={cy} x2={svgW} y2={cy}
                          stroke={COLOR[status]} strokeWidth={1}
                          strokeDasharray="4,3" opacity={0.35} />
                    <text x={svgW / 2} y={cy - 4} textAnchor="middle"
                          fontSize={9.5} fill={COLOR[status]}
                          fontFamily="var(--font-mono)" fontWeight={600}
                          opacity={0.9}>
                      {LABEL[status]}
                    </text>
                  </g>
                );
              })}

              {/* Founded year diamonds — rendered last so they appear on top of bubbles */}
              {enrichedRows.map((c, i) => {
                if (!c.founded) return null;
                const cy = AXIS_H + i * ROW_H + ROW_H / 2;
                const fx = toX(new Date(c.founded, 6, 1).getTime());
                const s  = 7;
                return (
                  <g key={`founded-${c.id}`} clipPath={`url(#clip-${i})`} style={{pointerEvents:"none"}}>
                    <polygon
                      points={`${fx},${cy - s} ${fx + s},${cy} ${fx},${cy + s} ${fx - s},${cy}`}
                      fill="#0ea5e9"
                      stroke="var(--bg)" strokeWidth={1.5} />
                  </g>
                );
              })}
            </svg>

            {/* Floating tooltip */}
            {tooltip && (
              <div style={{
                position:"absolute",
                left: Math.min(tooltip.x + 12, svgW - 170),
                top: Math.max(tooltip.y - 60, 4),
                background:"var(--bg)", border:"1px solid var(--border)",
                borderRadius:6, padding:"8px 12px",
                fontSize:12, lineHeight:1.6, pointerEvents:"none",
                boxShadow:"0 4px 16px rgba(0,0,0,0.12)", zIndex:10,
                whiteSpace:"nowrap",
              }}>
                <div style={{fontWeight:600, color:"var(--fg)"}}>{tooltip.company.name}</div>
                <div style={{color:"var(--fg-2)"}}>
                  {tooltip.round.round} · {tooltip.round.undisclosed
                    ? <i style={{color:"var(--fg-4)"}}>amount undisclosed</i>
                    : <b>${tooltip.round.amt}M</b>}
                </div>
                <div style={{color:"var(--fg-4)", fontFamily:"var(--font-mono)", fontSize:10.5}}>
                  Q{tooltip.round.q} {tooltip.round.y}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Selected panel */}
      {selected && (
        <div className="card" style={{marginTop:12, display:"flex", alignItems:"center", gap:14, padding:"12px 16px"}}>
          <LogoMark name={selected.company.name} domain={selected.company.domain} subject={selected.company.isSubject} />
          <div style={{flex:1}}>
            <div style={{fontWeight:600, fontSize:13}}>{selected.company.name}</div>
            <div className="mono" style={{fontSize:11.5, color:"var(--fg-3)", marginTop:2}}>
              {selected.round.round} · {selected.round.undisclosed ? "undisclosed" : `$${selected.round.amt}M`} · Q{selected.round.q} {selected.round.y}
            </div>
          </div>
          {!selected.company.isSubject && <ThreatTag level={selected.company.threat} />}
          <button onClick={() => setSelected(null)}
                  style={{background:"none",border:"none",cursor:"pointer",color:"var(--fg-4)"}}>
            {Icons.x}
          </button>
        </div>
      )}

      {/* Cumulative bar */}
      <div style={{height:16}}></div>
      <div className="card">
        <div className="card-h">
          <h3>Cumulative funding</h3>
          <span className="meta">Sorted high → low</span>
        </div>
        <div style={{padding:"12px 16px"}}>
          {[...all]
            .filter(c => (c.funding?.total || 0) > 0)
            .sort((a, b) => (b.funding?.total || 0) - (a.funding?.total || 0))
            .map(c => {
              const max = Math.max(...all.map(x => x.funding?.total || 0));
              const pct = ((c.funding?.total || 0) / max) * 100;
              return (
                <div key={c.id} style={{display:"grid", gridTemplateColumns:"140px 1fr 100px",
                     alignItems:"center", gap:12, padding:"6px 0"}}>
                  <span style={{fontSize:12.5, fontWeight:c.isSubject ? 600 : 500,
                       color:c.isSubject ? "var(--accent)" : "var(--fg)"}}>{c.name}</span>
                  <Bar value={pct} subject={c.isSubject} />
                  <span className="mono num" style={{fontSize:12,
                       color:c.isSubject ? "var(--accent)" : "var(--fg)"}}>
                    {fmtMoney(c.funding?.total || 0)}
                  </span>
                </div>
              );
            })}
        </div>
      </div>

      <div style={{height:16}}></div>
      <InvestorTable all={all} />
    </div>
  );
}

function InvestorTable({ all }) {
  const map = {};
  all.forEach(c => {
    (c.investors || []).forEach(inv => {
      if (!map[inv]) map[inv] = [];
      map[inv].push(c);
    });
  });
  const sorted = Object.entries(map).sort((a, b) => b[1].length - a[1].length);
  if (!sorted.length) return null;
  return (
    <div className="card">
      <div className="card-h">
        <h3>Investor overlap</h3>
        <span className="meta">Investors with stakes in 1+ company</span>
      </div>
      <div style={{overflowX:"auto"}}>
        <table className="tbl">
          <thead><tr><th>Investor</th><th className="num">Bets</th><th>Portfolio (this set)</th></tr></thead>
          <tbody>
            {sorted.map(([inv, list]) => (
              <tr key={inv}>
                <td style={{fontWeight:500}}>{inv}</td>
                <td className="num">{list.length}</td>
                <td>
                  <div style={{display:"flex", gap:6, flexWrap:"wrap"}}>
                    {list.map(c => (
                      <span key={c.id} className={"tag mono " + (c.isSubject ? "subject" : "")}
                            style={{fontSize:10.5}}>{c.name}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.TimelineScreen = TimelineScreen;
