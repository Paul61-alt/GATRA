// screens-overview.jsx â exec summary for the scan
const { useMemo: _uM_ov } = React;

function OverviewScreen({ data }) {
  const { subject, competitors } = data;
  const allCompanies = data.allCompanies;

  const totalRaised = competitors.reduce((s, c) => s + c.funding.total, 0);
  const totalEmployees = competitors.reduce((s, c) => s + c.employees, 0);
  const avgFunding = totalRaised / competitors.length;

  const topThreats = competitors
    .filter(c => c.threat === "high")
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, 3);

  return (
    <div className="screen">

      {/* ââ Header ââ */}
      <div style={{display:"flex", alignItems:"flex-start", gap: 20, marginBottom: 28}}>
        <LogoMark name={subject.name} subject={true} size="lg" />
        <div style={{flex:1, minWidth:0}}>
          <div style={{display:"flex", alignItems:"baseline", gap:10, flexWrap:"wrap"}}>
            <h1 style={{fontFamily:"var(--font-serif)", fontSize: 32, fontWeight: 500, letterSpacing:"-0.02em", margin:0}}>
              {subject.name}
            </h1>
            <span className="mono muted" style={{fontSize:12.5}}>{subject.domain} {Icons.ext}</span>
            <span className="tag subject mono">SUBJECT</span>
          </div>
          <p className="serif" style={{
            fontSize: 16, color:"var(--fg-2)", margin:"6px 0 0",
            maxWidth: 720, fontStyle:"italic"
          }}>
            "{subject.tagline}."
          </p>
          <div style={{display:"flex", gap:16, marginTop:14, flexWrap:"wrap", color:"var(--fg-3)", fontSize:12}}>
            <span className="row" style={{gap:6}}>{Icons.building} {subject.category} Â· {subject.subCategory}</span>
            <span className="row" style={{gap:6}}>{Icons.pin} {subject.hq}</span>
            <span className="row" style={{gap:6}}>{Icons.users} {subject.employees} employees Â· <span className="mono" style={{color:"var(--positive)"}}>+{fmtPct(subject.employeeGrowth)}</span> YoY</span>
            <span className="row" style={{gap:6}}>{Icons.cash} {fmtMoney(subject.funding.total)} raised Â· {subject.funding.lastRound}</span>
          </div>
        </div>
      </div>

      {/* ââ Stat row ââ */}
      <div className="card" style={{marginBottom: 20}}>
        <div className="stat-row">
          <div className="stat">
            <div className="lbl">Competitors mapped</div>
            <div className="val">{competitors.length}<span className="unit">companies</span></div>
            <div className="delta">3 high Â· 3 medium Â· 1 low threat</div>
          </div>
          <div className="stat">
            <div className="lbl">Combined funding</div>
            <div className="val">{fmtMoney(totalRaised)}</div>
            <div className="delta">Avg {fmtMoney(avgFunding)} per company</div>
          </div>
          <div className="stat">
            <div className="lbl">Total headcount</div>
            <div className="val">{totalEmployees.toLocaleString()}</div>
            <div className="delta">Subject is rank 7 / 8 by size</div>
          </div>
          <div className="stat">
            <div className="lbl">Most-funded peer</div>
            <div className="val" style={{fontFamily:"var(--font-serif)"}}>Pylon Pay</div>
            <div className="delta">{fmtMoney(540_000_000)} Â· 14Ã subject</div>
          </div>
        </div>
      </div>

      {/* ââ Two-col layout ââ */}
      <div style={{display:"grid", gridTemplateColumns:"1.4fr 1fr", gap: 20, alignItems:"start"}}>

        {/* Top threats */}
        <div className="card">
          <div className="card-h">
            <h3>Top threats</h3>
            <span className="meta">By similarity Ã momentum</span>
          </div>
          <div>
            {topThreats.map((c, i) => (
              <div key={c.id} style={{
                display:"grid", gridTemplateColumns:"auto 1fr auto auto auto",
                gap: 14, alignItems:"center",
                padding:"14px 16px",
                borderBottom: i < topThreats.length - 1 ? "1px solid var(--border-dim)" : "none",
              }}>
                <LogoMark name={c.name} />
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
                  <div className="mono" style={{fontSize:13, fontWeight:500, marginTop:4}}>{fmtMoney(c.funding.total)}</div>
                </div>
                <ThreatTag level={c.threat} />
              </div>
            ))}
          </div>
        </div>

        {/* Quick scan summary */}
        <div className="card">
          <div className="card-h">
            <h3>Analyst summary</h3>
            <span className="meta">Auto Â· {fmtDate(data.query.scannedAt.slice(0,7))}</span>
          </div>
          <div className="card-b" style={{fontSize: 13.5, lineHeight: 1.6, color:"var(--fg-2)"}}>
            <p style={{marginTop:0}}>
              <strong style={{color:"var(--fg)"}}>{subject.name}</strong> sits in the
              {" "}<strong style={{color:"var(--fg)"}}>Payment Infrastructure</strong> wedge of B2B Payments â
              squeezed between high-funded incumbents and a wave of API-first peers.
            </p>
            <p>
              The closest threats by product surface are <em>Vex</em> (spend management,
              7,800 customers) and <em>Ferrum</em> (embedded finance API, similar developer
              positioning). <em>Pylon Pay</em> is much larger but covers a different lane (cross-border).
            </p>
            <p>
              Defensible angle: <strong style={{color:"var(--accent)"}}>ISO 20022 native + open API</strong>.
              No competitor combines both at this depth. Risk: thin trust signal vs incumbents.
            </p>
            <hr className="divider" style={{margin:"12px 0"}}/>
            <div style={{display:"flex", gap:8, flexWrap:"wrap"}}>
              {subject.notable.map(n => (
                <span key={n} className="tag" style={{fontSize:11}}>{n}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ââ Positioning matrix (novel idea: 2D scatter) ââ */}
      <div style={{height: 20}}></div>
      <PositioningMatrix data={data} />

      {/* ââ Spectrum: similarity ladder ââ */}
      <div style={{height: 20}}></div>
      <SimilarityLadder data={data} />

    </div>
  );
}

// âââ Positioning matrix: funding Ã similarity ââââââââââââââââââ
function PositioningMatrix({ data }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];

  // X = similarity (0..1), Y = log10(funding+1)
  const W = 880, H = 360, padL = 56, padR = 24, padT = 30, padB = 44;
  const innerW = W - padL - padR, innerH = H - padT - padB;

  const fundingMax = Math.max(...all.map(c => c.funding.total));
  const yScale = (v) => {
    const log = Math.log10(v + 1);
    const max = Math.log10(fundingMax + 1);
    return innerH - (log / max) * innerH;
  };
  const xScale = (v) => v * innerW;

  // Y axis ticks (powers of 10)
  const yTicks = [1e6, 1e7, 1e8, 1e9].filter(t => t < fundingMax * 1.5);
  const xTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="card">
      <div className="card-h">
        <h3>Positioning matrix</h3>
        <span className="meta">Funding raised Ã Similarity to {data.subject.name}</span>
      </div>
      <div style={{padding:"16px 12px 6px"}}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{width:"100%", height:"auto", display:"block"}}>
          <g transform={`translate(${padL},${padT})`}>
            {/* gridlines */}
            {yTicks.map(t => (
              <g key={t}>
                <line x1={0} x2={innerW} y1={yScale(t)} y2={yScale(t)} stroke="var(--border-dim)" />
                <text x={-8} y={yScale(t) + 3} fontSize="10" textAnchor="end"
                      fill="var(--fg-4)" fontFamily="var(--font-mono)">
                  {fmtMoney(t)}
                </text>
              </g>
            ))}
            {xTicks.map(t => (
              <g key={t}>
                <line x1={xScale(t)} x2={xScale(t)} y1={0} y2={innerH} stroke="var(--border-dim)" />
                <text x={xScale(t)} y={innerH + 16} fontSize="10" textAnchor="middle"
                      fill="var(--fg-4)" fontFamily="var(--font-mono)">
                  {(t * 100).toFixed(0)}
                </text>
              </g>
            ))}
            {/* axes */}
            <line x1={0} x2={innerW} y1={innerH} y2={innerH} stroke="var(--border-strong)" />
            <line x1={0} x2={0} y1={0} y2={innerH} stroke="var(--border-strong)" />

            {/* axis labels */}
            <text x={innerW / 2} y={innerH + 36} fontSize="10" textAnchor="middle"
                  fill="var(--fg-4)" fontFamily="var(--font-mono)" letterSpacing="0.08em">
              SIMILARITY  â
            </text>
            <text x={-innerH / 2} y={-44} fontSize="10" textAnchor="middle"
                  transform="rotate(-90)"
                  fill="var(--fg-4)" fontFamily="var(--font-mono)" letterSpacing="0.08em">
              FUNDING RAISED  â
            </text>

            {/* quadrant labels */}
            <text x={innerW * 0.78} y={20} fontSize="10" fill="var(--fg-4)" fontFamily="var(--font-mono)">
              CLOSE & WELL-FUNDED
            </text>
            <text x={6} y={20} fontSize="10" fill="var(--fg-4)" fontFamily="var(--font-mono)">
              ADJACENT INCUMBENTS
            </text>
            <text x={6} y={innerH - 8} fontSize="10" fill="var(--fg-4)" fontFamily="var(--font-mono)">
              FRINGE
            </text>
            <text x={innerW * 0.78} y={innerH - 8} fontSize="10" fill="var(--fg-4)" fontFamily="var(--font-mono)">
              EMERGING THREATS
            </text>

            {/* points */}
            {all.map((c) => {
              const sim = c.isSubject ? 1 : c.similarity;
              const cx = xScale(sim);
              const cy = yScale(c.funding.total);
              const r = Math.max(8, Math.sqrt(c.employees) * 1.2);
              const isS = c.isSubject;
              return (
                <g key={c.id} transform={`translate(${cx},${cy})`}>
                  <circle r={r}
                          fill={isS ? "var(--accent)" : "var(--fg-2)"}
                          fillOpacity={isS ? 0.18 : 0.08}
                          stroke={isS ? "var(--accent)" : "var(--fg-2)"}
                          strokeWidth={isS ? 1.5 : 1}/>
                  <circle r={2.5} fill={isS ? "var(--accent)" : "var(--fg)"}/>
                  <text x={r + 6} y={4} fontSize="11.5"
                        fill={isS ? "var(--accent)" : "var(--fg)"}
                        fontWeight={isS ? 600 : 500}
                        fontFamily="var(--font-sans)">
                    {c.name}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
        <div style={{display:"flex", gap:16, padding:"4px 14px 6px", fontSize:11, color:"var(--fg-3)"}}>
          <span><span className="dot subject"></span> Subject</span>
          <span style={{display:"inline-flex", alignItems:"center", gap:6}}>
            <svg width="14" height="14"><circle cx="7" cy="7" r="6" fill="var(--fg-2)" fillOpacity=".08" stroke="var(--fg-2)"/></svg>
            Bubble = âemployees
          </span>
        </div>
      </div>
    </div>
  );
}

// âââ Similarity ladder (1D spectrum) ââââââââââââââââââââââââââ
function SimilarityLadder({ data }) {
  const { competitors } = data;
  const sorted = [...competitors].sort((a,b) => b.similarity - a.similarity);

  return (
    <div className="card">
      <div className="card-h">
        <h3>Similarity ladder</h3>
        <span className="meta">Competitors ranked by overlap with {data.subject.name}</span>
      </div>
      <div style={{padding:"4px 0"}}>
        {sorted.map((c, i) => (
          <div key={c.id} style={{
            display:"grid",
            gridTemplateColumns:"32px 28px 160px 1fr 80px",
            alignItems:"center", gap:14,
            padding:"10px 16px",
            borderBottom: i < sorted.length - 1 ? "1px solid var(--border-dim)" : "none",
          }}>
            <span className="mono dim" style={{fontSize:11}}>#{i + 1}</span>
            <LogoMark name={c.name} size="sm" />
            <div>
              <div style={{fontWeight:500}}>{c.name}</div>
              <div className="mono" style={{color:"var(--fg-4)", fontSize:10.5}}>{c.subCategory}</div>
            </div>
            <div style={{display:"flex", alignItems:"center", gap:10}}>
              <Bar value={c.similarity * 100} />
              <span className="mono" style={{fontSize:11, color:"var(--fg-3)", minWidth:32}}>
                {(c.similarity * 100).toFixed(0)}%
              </span>
            </div>
            <div style={{textAlign:"right"}}>
              <ThreatTag level={c.threat} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.OverviewScreen = OverviewScreen;
