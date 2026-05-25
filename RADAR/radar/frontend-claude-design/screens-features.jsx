// screens-features.jsx â capability matrix
const { useState: _uS_feat } = React;

function FeaturesScreen({ data }) {
  const { features, capabilities, subject, competitors } = data;
  const all = [subject, ...competitors];

  const [highlightDelta, setHighlightDelta] = _uS_feat(true);

  // Group features by group
  const groups = features.reduce((acc, f, i) => {
    if (!acc[f.group]) acc[f.group] = [];
    acc[f.group].push({ ...f, index: i });
    return acc;
  }, {});

  // Coverage stats
  const coverage = all.map(c => {
    const caps = capabilities[c.id];
    const full = caps.filter(x => x === "full").length;
    const part = caps.filter(x => x === "part").length;
    return {
      id: c.id, name: c.name, isSubject: c.isSubject,
      full, part, none: caps.length - full - part,
      score: full + part * 0.5,
    };
  }).sort((a, b) => b.score - a.score);

  return (
    <div className="screen">
      <SectionH title="Features matrix" meta={`${features.length} capabilities Ã ${all.length} companies`}>
        <button className="tb-btn"
                onClick={() => setHighlightDelta(v => !v)}
                style={{borderColor: highlightDelta ? "var(--fg)" : "var(--border)"}}>
          {Icons.zap}<span>Highlight gaps vs. {subject.name}</span>
        </button>
        <button className="tb-btn">{Icons.download}</button>
      </SectionH>

      {/* Coverage rank strip */}
      <div className="card" style={{marginBottom: 16}}>
        <div className="card-h">
          <h3>Coverage ranking</h3>
          <span className="meta">Full = 1 Â· Partial = 0.5 Â· None = 0</span>
        </div>
        <div style={{padding: "12px 16px"}}>
          {coverage.map((c, i) => (
            <div key={c.id} style={{
              display:"grid", gridTemplateColumns:"24px 110px 1fr 110px",
              alignItems:"center", gap:12,
              padding:"6px 0",
            }}>
              <span className="mono dim" style={{fontSize:11}}>#{i + 1}</span>
              <span style={{
                fontWeight: c.isSubject ? 600 : 500,
                color: c.isSubject ? "var(--accent)" : "var(--fg)",
                fontSize: 12.5,
              }}>{c.name}</span>
              <div style={{display:"flex", gap:0, height:10, borderRadius:3, overflow:"hidden", background:"var(--bg-3)"}}>
                <div style={{flex: c.full, background: c.isSubject ? "var(--accent)" : "var(--fg-2)"}}></div>
                <div style={{flex: c.part, background: c.isSubject ? "var(--accent-bg-2)" : "var(--fg-4)"}}></div>
                <div style={{flex: c.none, background:"transparent"}}></div>
              </div>
              <div className="mono" style={{fontSize:11, color:"var(--fg-3)", textAlign:"right"}}>
                <span style={{color: c.isSubject ? "var(--accent)" : "var(--fg)"}}>{c.full}</span>
                <span className="dim"> / {c.part} / {c.none}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Matrix */}
      <div className="card" style={{overflow:"hidden"}}>
        <div style={{overflowX:"auto"}}>
          <table className="tbl" style={{minWidth: 1100}}>
            <thead>
              <tr>
                <th style={{minWidth: 220, background:"var(--bg-2)"}}>Capability</th>
                {all.map(c => (
                  <th key={c.id} style={{
                    textAlign:"center", padding:"10px 4px", minWidth: 64,
                    background: c.isSubject ? "var(--accent-bg)" : "var(--bg-2)",
                  }}>
                    <div style={{display:"flex", flexDirection:"column", alignItems:"center", gap:4}}>
                      <LogoMark name={c.name} subject={c.isSubject} size="sm"/>
                      <span style={{
                        fontWeight: c.isSubject ? 600 : 500,
                        color: c.isSubject ? "var(--accent)" : "var(--fg-2)",
                        fontSize: 10.5, fontFamily: "var(--font-sans)",
                        letterSpacing: 0, textTransform: "none",
                      }}>
                        {c.name}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(groups).map(([groupName, items]) => (
                <React.Fragment key={groupName}>
                  <tr>
                    <td colSpan={all.length + 1} style={{
                      padding:"10px 12px 6px",
                      background:"var(--bg-2)",
                      borderTop:"1px solid var(--border)",
                      borderBottom:"1px solid var(--border)",
                    }}>
                      <span className="mono" style={{
                        fontSize: 10, letterSpacing: "0.1em",
                        textTransform: "uppercase", color: "var(--fg-3)",
                        fontWeight: 600,
                      }}>{groupName}</span>
                    </td>
                  </tr>
                  {items.map(f => {
                    const subjectCap = capabilities[subject.id][f.index];
                    return (
                      <tr key={f.index}>
                        <td style={{paddingLeft: 20, fontWeight: 400, color:"var(--fg-2)"}}>{f.label}</td>
                        {all.map(c => {
                          const cap = capabilities[c.id][f.index];
                          const isGap = highlightDelta && !c.isSubject &&
                                        ((subjectCap === "full" && cap !== "full") ||
                                         (cap === "full" && subjectCap !== "full"));
                          return (
                            <td key={c.id} style={{
                              textAlign:"center", padding: 0,
                              background: c.isSubject ? "var(--accent-bg)" : (isGap ? "rgba(154,64,32,0.05)" : "transparent"),
                            }}>
                              <CapCell value={cap} subject={c.isSubject}
                                       compareTo={!c.isSubject ? subjectCap : null}
                                       highlight={isGap}/>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{display:"flex", gap:18, marginTop:14, fontSize:11.5, color:"var(--fg-3)"}}>
        <span><CapGlyph value="full"/> Full</span>
        <span><CapGlyph value="part"/> Partial</span>
        <span><CapGlyph value="none"/> None</span>
        <span><CapGlyph value="soon"/> On roadmap</span>
        <span style={{marginLeft:12}}>
          <span style={{
            display:"inline-block", width:10, height:10, marginRight:6,
            background:"rgba(154,64,32,0.12)",
            border:"1px solid rgba(154,64,32,0.3)",
          }}></span>
          Gap vs. {subject.name}
        </span>
      </div>
    </div>
  );
}

function CapCell({ value, subject, compareTo, highlight }) {
  return (
    <div style={{
      display:"grid", placeItems:"center",
      height: "var(--row-h)",
    }}>
      <CapGlyph value={value} subject={subject}/>
    </div>
  );
}

function CapGlyph({ value, subject = false }) {
  if (value === "full") {
    return (
      <span style={{
        display:"inline-grid", placeItems:"center",
        width: 18, height: 18, borderRadius: 9,
        background: subject ? "var(--accent)" : "var(--fg)",
        color: "#fff",
      }}>
        <svg width="11" height="11" viewBox="0 0 24 24" stroke="currentColor"
             strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="m4 12 5 5L20 6"/>
        </svg>
      </span>
    );
  }
  if (value === "part") {
    return (
      <span style={{
        display:"inline-grid", placeItems:"center",
        width: 18, height: 18, borderRadius: 9,
        background: "var(--bg-3)",
        border: "1px solid var(--border-strong)",
        color: "var(--fg-3)",
      }}>
        <span style={{
          width: 10, height: 10, borderRadius: 5,
          background: "linear-gradient(90deg, var(--fg-2) 0 50%, transparent 50% 100%)",
        }}></span>
      </span>
    );
  }
  if (value === "soon") {
    return (
      <span style={{
        display:"inline-grid", placeItems:"center",
        width: 18, height: 18, borderRadius: 9,
        border: "1px dashed var(--fg-4)",
        color: "var(--fg-4)",
        fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 600,
      }}>S</span>
    );
  }
  return (
    <span style={{
      display:"inline-block",
      width: 8, height: 1, background: "var(--fg-5)",
    }}></span>
  );
}

window.FeaturesScreen = FeaturesScreen;
