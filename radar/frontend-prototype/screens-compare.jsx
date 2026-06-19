// screens-compare.jsx â radar chart comparison
const { useState: _uS_cmp, useMemo: _uM_cmp } = React;

function CompareScreen({ data, onOpenCompany }) {
  const { subject, competitors, radar } = data;
  const [selected, setSelected] = _uS_cmp(competitors.slice(0, 3).map(c => c.id));

  const toggleCompetitor = (id) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id].slice(-4));
  };

  // Subject is always shown
  const shown = [
    { ...subject, scores: radar.scores[subject.id] || [], color: "var(--accent)", isSubject: true },
    ...selected.map((id, i) => {
      const c = competitors.find(x => x.id === id);
      if (!c) return null;
      const palette = ["#3a576b", "#5a6b4a", "#6b5a4a", "#4a5a6b"];
      return { ...c, scores: radar.scores[id] || [], color: palette[i % palette.length] };
    }).filter(Boolean),
  ];

  return (
    <div className="screen">
      <SectionH title="Side-by-side comparison" meta="Radar visualisation across 6 dimensions" />

      <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap: 20, alignItems:"start"}}>

        {/* Radar chart */}
        <div className="card">
          <div className="card-h">
            <h3>Capability radar</h3>
            <span className="meta">Hover an axis Â· Click name to toggle</span>
          </div>
          <div style={{padding: 16}}>
            <RadarChart axes={radar.axes} entries={shown} defs={radar.defs}/>
            {/* Legend */}
            <div style={{display:"flex", flexWrap:"wrap", gap:14, marginTop:8, justifyContent:"center"}}>
              {shown.map(e => (
                <div key={e.id} style={{display:"flex", alignItems:"center", gap:6, fontSize:12}}>
                  <span style={{
                    width:10, height:10, borderRadius:2, background: e.color,
                    border: e.isSubject ? "none" : "1px solid " + e.color,
                  }}></span>
                  <span style={{
                    fontWeight: e.isSubject ? 600 : 500,
                    color: e.isSubject ? "var(--accent)" : "var(--fg)",
                  }}>{e.name}</span>
                  {e.isSubject && <span className="mono dim" style={{fontSize:10}}>(you)</span>}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Picker */}
        <div className="card">
          <div className="card-h">
            <h3>Compared against</h3>
            <span className="meta">{selected.length} / 4</span>
          </div>
          <div style={{padding:"4px 0"}}>
            {/* subject pinned */}
            <div style={{
              display:"flex", alignItems:"center", gap:10,
              padding:"10px 14px",
              background:"var(--accent-bg)",
              borderTop:"1px solid var(--accent-bg-2)",
              borderBottom:"1px solid var(--accent-bg-2)",
            }}>
              <span style={{width:10, height:10, borderRadius:2, background:"var(--accent)"}}></span>
              <LogoMark name={subject.name} domain={subject.domain} subject={true} size="sm" />
              <span style={{fontWeight:500, color:"var(--accent-fg)"}}>{subject.name}</span>
              <span className="tag subject mono" style={{marginLeft:"auto", fontSize:9}}>PINNED</span>
            </div>

            {competitors.map(c => {
              const checked = selected.includes(c.id);
              return (
                <div key={c.id}
                     style={{
                       display:"flex", alignItems:"center", gap:10,
                       padding:"8px 14px",
                       borderBottom:"1px solid var(--border-dim)",
                       opacity: checked ? 1 : 0.6,
                       cursor:"default",
                     }}>
                  <span onClick={() => toggleCompetitor(c.id)} style={{
                    width:14, height:14, borderRadius:3,
                    border: "1.5px solid " + (checked ? "var(--fg)" : "var(--fg-4)"),
                    background: checked ? "var(--fg)" : "transparent",
                    display:"grid", placeItems:"center", flexShrink:0, cursor:"pointer",
                  }}>
                    {checked && <span style={{color:"#fff"}}>{Icons.check}</span>}
                  </span>
                  <div onClick={() => onOpenCompany && onOpenCompany(c.id)}
                    style={{display:"flex", alignItems:"center", gap:8, flex:1, minWidth:0, cursor:"pointer"}}>
                    <LogoMark name={c.name} domain={c.domain} size="sm" />
                    <div style={{minWidth:0, flex:1}}>
                      <div style={{fontWeight:500, fontSize:12.5}}>{c.name}</div>
                      <div className="mono dim" style={{fontSize:10}}>{c.subCategory}</div>
                    </div>
                  </div>
                  <ThreatTag level={c.threat} />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Score deltas: subject vs each */}
      <div style={{height: 20}}></div>
      <div className="card">
        <div className="card-h">
          <h3>Where {subject.name} wins / loses</h3>
          <span className="meta">Î vs. each competitor on every axis</span>
        </div>
        <div style={{overflowX:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Competitor</th>
                {radar.axes.map(a => <th key={a} style={{textAlign:"center"}}>{a}</th>)}
                <th style={{textAlign:"right"}}>Net Î</th>
              </tr>
            </thead>
            <tbody>
              {shown.filter(e => !e.isSubject).map(e => {
                const subjectScores = radar.scores[subject.id] || [];
                const deltas = e.scores.map((s, i) => subjectScores[i] - s);
                const net = deltas.reduce((a, b) => a + b, 0);
                return (
                  <tr key={e.id} onClick={() => onOpenCompany && onOpenCompany(e.id)} style={{cursor:"pointer"}}>
                    <td>
                      <div className="name-cell">
                        <LogoMark name={e.name} domain={e.domain} size="sm" />
                        <span className="nm">{e.name}</span>
                      </div>
                    </td>
                    {deltas.map((d, i) => (
                      <td key={i} className="num" style={{textAlign:"center"}}>
                        <DeltaCell d={d} />
                      </td>
                    ))}
                    <td className="num" style={{
                      fontWeight: 600,
                      color: net > 0 ? "var(--positive)" : net < 0 ? "var(--negative)" : "var(--fg-3)",
                    }}>
                      {net > 0 ? "+" : ""}{net}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function DeltaCell({ d }) {
  const sign = d > 0 ? "+" : "";
  const color = d > 10 ? "var(--positive)" : d < -10 ? "var(--negative)" : d === 0 ? "var(--fg-4)" : "var(--fg-3)";
  const bg = d > 10 ? "var(--positive-bg)" : d < -10 ? "var(--negative-bg)" : "transparent";
  return (
    <span style={{
      display:"inline-block", padding: "1px 7px", minWidth: 32,
      borderRadius: 4, color, background: bg,
      fontFamily: "var(--font-mono)", fontSize: 11.5,
    }}>
      {sign}{d}
    </span>
  );
}

// âââ Radar chart ââââââââââââââââââââââââââââââââââââââââââââââ
function RadarChart({ axes, entries, defs }) {
  const W = 540, H = 420;
  const cx = W / 2, cy = H / 2 + 6;
  const R = 150;
  const N = axes.length;
  const angle = (i) => -Math.PI / 2 + (i / N) * Math.PI * 2;
  const point = (i, v) => {
    const r = (v / 100) * R;
    return [cx + Math.cos(angle(i)) * r, cy + Math.sin(angle(i)) * r];
  };

  const rings = [25, 50, 75, 100];

  const polygonPath = (scores) => scores.map((v, i) => {
    const [x, y] = point(i, v);
    return (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ") + " Z";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{width:"100%", height:"auto", display:"block", maxHeight:440}}>
      {/* Rings */}
      {rings.map(r => {
        const path = axes.map((_, i) => {
          const [x, y] = point(i, r);
          return (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1);
        }).join(" ") + " Z";
        return <path key={r} d={path}
                     fill={r === 100 ? "var(--bg-2)" : "none"}
                     fillOpacity={r === 100 ? 0.5 : 0}
                     stroke="var(--border)" strokeDasharray={r === 100 ? "none" : "2 3"} />;
      })}
      {/* Spokes */}
      {axes.map((_, i) => {
        const [x, y] = point(i, 100);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border)" />;
      })}
      {/* Ring labels */}
      {rings.map(r => (
        <text key={r} x={cx + 4} y={cy - (r/100) * R + 3}
              fontSize="9" fill="var(--fg-4)"
              fontFamily="var(--font-mono)">{r}</text>
      ))}

      {/* Polygons (subject last so on top â actually render subject last) */}
      {[...entries].sort((a,b) => (a.isSubject ? 1 : -1)).map(e => (
        <g key={e.id}>
          <path d={polygonPath(e.scores)}
                fill={e.color}
                fillOpacity={e.isSubject ? 0.18 : 0.06}
                stroke={e.color}
                strokeWidth={e.isSubject ? 2 : 1.25}
                strokeLinejoin="round"/>
          {e.scores.map((v, i) => {
            const [x, y] = point(i, v);
            return <circle key={i} cx={x} cy={y} r={e.isSubject ? 3 : 2.5}
                           fill={e.color} stroke="#fff" strokeWidth={e.isSubject ? 1.5 : 1}/>;
          })}
        </g>
      ))}

      {/* Axis labels */}
      {axes.map((a, i) => {
        const [x, y] = point(i, 118);
        const anchor = Math.abs(Math.cos(angle(i))) < 0.2 ? "middle"
                     : Math.cos(angle(i)) > 0 ? "start" : "end";
        return (
          <text key={a} x={x} y={y + 4}
                fontSize="11.5" fill="var(--fg)"
                textAnchor={anchor}
                fontFamily="var(--font-sans)" fontWeight="500"
                style={{textTransform:"uppercase", letterSpacing:"0.06em"}}>
            <title>{defs[a]}</title>{a}
          </text>
        );
      })}
    </svg>
  );
}

window.CompareScreen = CompareScreen;
