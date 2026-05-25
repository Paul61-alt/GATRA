// screens-timeline.jsx â funding events on a horizontal time axis with swimlanes
const { useMemo: _uM_tl } = React;

function TimelineScreen({ data }) {
  const { subject, competitors, funding } = data;
  const all = [subject, ...competitors];

  const minYear = 2016, maxYear = 2026;
  const years = [];
  for (let y = minYear; y <= maxYear; y++) years.push(y);

  // Stats
  const totalEvents = all.reduce((s, c) => s + funding[c.id].length, 0);
  const totalRaised = all.reduce((s, c) => s + funding[c.id].reduce((a, b) => a + b.amt, 0), 0);

  const yearToX = (y, q) => ((y - minYear) + (q - 1) / 4) / (maxYear - minYear);

  return (
    <div className="screen">
      <SectionH title="Funding timeline" meta={`${totalEvents} rounds Â· $${totalRaised.toFixed(0)}M total`} />

      {/* Swimlane chart */}
      <div className="card" style={{overflow:"hidden"}}>
        <div className="card-h">
          <h3>Funding events</h3>
          <span className="meta">Bubble area â round size Â· {minYear} â {maxYear}</span>
        </div>
        <div style={{padding: "20px 8px 12px", overflowX:"auto"}}>
          <div style={{minWidth: 900}}>
            {/* X axis */}
            <div style={{display:"grid", gridTemplateColumns:"160px 1fr", gap:0, paddingRight: 16}}>
              <div></div>
              <div style={{
                position:"relative", height: 26,
                borderBottom: "1px solid var(--border)",
              }}>
                {years.map(y => (
                  <div key={y} style={{
                    position:"absolute",
                    left: ((y - minYear) / (maxYear - minYear)) * 100 + "%",
                    top: 0, bottom: 0,
                    transform: "translateX(-50%)",
                    fontFamily: "var(--font-mono)", fontSize: 10,
                    color: y === 2026 ? "var(--fg-4)" : "var(--fg-3)",
                    display:"flex", alignItems:"center",
                  }}>{y}</div>
                ))}
              </div>
            </div>

            {/* Lanes */}
            {all.map(c => {
              const events = funding[c.id];
              const total = events.reduce((s, e) => s + e.amt, 0);
              const isS = c.isSubject;
              return (
                <div key={c.id} style={{
                  display:"grid", gridTemplateColumns:"160px 1fr", gap:0,
                  paddingRight: 16,
                  background: isS ? "var(--accent-bg)" : "transparent",
                  borderBottom: "1px solid var(--border-dim)",
                }}>
                  {/* Lane label */}
                  <div style={{
                    display:"flex", alignItems:"center", gap:8,
                    padding:"10px 12px",
                    borderRight: "1px solid var(--border-dim)",
                  }}>
                    <LogoMark name={c.name} subject={isS} size="sm" />
                    <div style={{minWidth:0, flex:1}}>
                      <div style={{
                        fontSize:12, fontWeight: isS ? 600 : 500,
                        color: isS ? "var(--accent)" : "var(--fg)",
                      }}>{c.name}</div>
                      <div className="mono dim" style={{fontSize:10}}>${total.toFixed(0)}M total</div>
                    </div>
                  </div>
                  {/* Events */}
                  <div style={{position:"relative", height: 50}}>
                    {/* Connecting line */}
                    {events.length > 1 && (
                      <div style={{
                        position:"absolute",
                        left: yearToX(events[0].y, events[0].q) * 100 + "%",
                        right: (1 - yearToX(events[events.length - 1].y, events[events.length - 1].q)) * 100 + "%",
                        top: "50%", height: 1.5,
                        background: isS ? "var(--accent)" : "var(--fg-4)",
                        opacity: isS ? 0.6 : 0.4,
                      }}></div>
                    )}
                    {events.map((e, i) => {
                      const x = yearToX(e.y, e.q);
                      const r = Math.max(8, Math.min(26, Math.sqrt(e.amt) * 2));
                      return (
                        <div key={i} style={{
                          position:"absolute",
                          left: x * 100 + "%",
                          top: "50%",
                          transform: "translate(-50%, -50%)",
                        }}>
                          <div style={{
                            width: r * 2, height: r * 2,
                            borderRadius: "50%",
                            background: isS ? "var(--accent)" : "var(--fg-2)",
                            opacity: isS ? 0.85 : 0.75,
                            border: "2px solid " + (isS ? "var(--accent-bg)" : "var(--bg)"),
                            display:"grid", placeItems:"center",
                            color: "#fff",
                            fontFamily:"var(--font-mono)", fontSize: r > 12 ? 10 : 8,
                            fontWeight: 500,
                            cursor: "default",
                          }} title={`${e.round}: $${e.amt}M (Q${e.q} ${e.y})`}>
                            ${e.amt}
                          </div>
                          <div style={{
                            position:"absolute", left: "50%", top: -4,
                            transform: "translate(-50%, -100%)",
                            fontFamily:"var(--font-mono)", fontSize: 9,
                            color: "var(--fg-3)", whiteSpace: "nowrap",
                            opacity: r > 10 ? 1 : 0,
                          }}>{e.round}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Cumulative bar by company */}
      <div style={{height: 16}}></div>
      <div className="card">
        <div className="card-h">
          <h3>Cumulative funding</h3>
          <span className="meta">Sorted high â low</span>
        </div>
        <div style={{padding: "12px 16px"}}>
          {[...all].sort((a, b) => b.funding.total - a.funding.total).map(c => {
            const max = Math.max(...all.map(x => x.funding.total));
            const pct = (c.funding.total / max) * 100;
            return (
              <div key={c.id} style={{
                display:"grid", gridTemplateColumns:"140px 1fr 100px",
                alignItems:"center", gap:12,
                padding: "6px 0",
              }}>
                <span style={{
                  fontSize:12.5,
                  fontWeight: c.isSubject ? 600 : 500,
                  color: c.isSubject ? "var(--accent)" : "var(--fg)",
                }}>{c.name}</span>
                <Bar value={pct} subject={c.isSubject}/>
                <span className="mono num" style={{fontSize:12, color: c.isSubject ? "var(--accent)" : "var(--fg)"}}>
                  {fmtMoney(c.funding.total)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Investor overlap */}
      <div style={{height: 16}}></div>
      <InvestorTable all={all}/>
    </div>
  );
}

function InvestorTable({ all }) {
  // Collect all investors with their portfolio companies
  const map = {};
  all.forEach(c => {
    c.investors.forEach(inv => {
      if (!map[inv]) map[inv] = [];
      map[inv].push(c);
    });
  });
  const sorted = Object.entries(map).sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="card">
      <div className="card-h">
        <h3>Investor overlap</h3>
        <span className="meta">Investors with stakes in 1+ company in this set</span>
      </div>
      <div style={{overflowX:"auto"}}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Investor</th>
              <th className="num">Bets</th>
              <th>Portfolio (this set)</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(([inv, list]) => (
              <tr key={inv}>
                <td style={{fontWeight: 500}}>{inv}</td>
                <td className="num">{list.length}</td>
                <td>
                  <div style={{display:"flex", gap:6, flexWrap:"wrap"}}>
                    {list.map(c => (
                      <span key={c.id} className={"tag mono " + (c.isSubject ? "subject" : "")}
                            style={{fontSize: 10.5}}>
                        {c.name}
                      </span>
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
