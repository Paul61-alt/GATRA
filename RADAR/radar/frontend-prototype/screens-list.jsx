// screens-list.jsx â competitors as a sortable, dense table + per-company drawer
const { useState: _uS_list } = React;

function ListScreen({ data, onOpenCard }) {
  const { competitors, subject } = data;
  const [sortKey, setSortKey] = _uS_list("similarity");
  const [sortDir, setSortDir] = _uS_list("desc");
  const [filterThreat, setFilterThreat] = _uS_list("all");

  const rows = [subject, ...competitors];
  const filtered = filterThreat === "all"
    ? rows
    : rows.filter(r => r.isSubject || r.threat === filterThreat);

  const sorted = [...filtered].sort((a, b) => {
    if (a.isSubject) return -1;
    if (b.isSubject) return 1;
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === "funding") { av = a.funding.total; bv = b.funding.total; }
    if (typeof av === "string") return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === "asc" ? av - bv : bv - av;
  });

  const headers = [
    { k: "name",        label: "Company",       align: "left" },
    { k: "subCategory", label: "Wedge",         align: "left" },
    { k: "hq",          label: "HQ",            align: "left" },
    { k: "founded",     label: "Founded",       align: "right" },
    { k: "employees",   label: "Employees",     align: "right" },
    { k: "funding",     label: "Raised",        align: "right" },
    { k: "arr",         label: "Est. ARR",      align: "right" },
    { k: "customers",   label: "Customers",     align: "right" },
    { k: "similarity",  label: "Sim.",          align: "right" },
    { k: "threat",      label: "Threat",        align: "left" },
  ];

  const toggleSort = (k) => {
    if (sortKey === k) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(k); setSortDir("desc"); }
  };

  return (
    <div className="screen">
      <SectionH title="All companies" meta={`${competitors.length + 1} total Â· 1 subject Â· ${competitors.length} peers`}>
        <div style={{display:"flex", gap:6}}>
          {["all", "high", "medium", "low"].map(t => (
            <button key={t}
                    className="tb-btn"
                    onClick={() => setFilterThreat(t)}
                    style={{
                      borderColor: filterThreat === t ? "var(--fg)" : "var(--border)",
                      color: filterThreat === t ? "var(--fg)" : "var(--fg-3)",
                      textTransform: "capitalize", fontSize: 11.5,
                    }}>
              {t === "all" ? "All" : <><span className={"dot " + (t === "medium" ? "med" : t)}></span> {t}</>}
            </button>
          ))}
          <button className="tb-btn">{Icons.filter}<span>Filter</span></button>
          <button className="tb-btn">{Icons.download}</button>
        </div>
      </SectionH>

      <div className="card" style={{overflow:"hidden"}}>
        <div style={{overflowX:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                {headers.map(h => (
                  <th key={h.k}
                      style={{textAlign: h.align, cursor:"default"}}
                      onClick={() => toggleSort(h.k)}>
                    <span style={{display:"inline-flex", alignItems:"center", gap:4}}>
                      {h.label}
                      {sortKey === h.k && (
                        <span style={{color:"var(--fg-2)"}}>
                          {sortDir === "asc" ? "â" : "â"}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
                <th style={{width: 36}}></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(c => (
                <tr key={c.id}
                    className={c.isSubject ? "subject-row" : ""}
                    onClick={() => onOpenCard && onOpenCard(c.id)}
                    style={{cursor:"default"}}>
                  <td>
                    <div className="name-cell">
                      <LogoMark name={c.name} subject={c.isSubject} size="sm" />
                      <div style={{minWidth:0}}>
                        <div className="nm" style={{display:"flex", alignItems:"center", gap:6}}>
                          {c.name}
                          {c.isSubject && <span className="tag subject mono" style={{fontSize:9, padding:"1px 5px"}}>SUBJECT</span>}
                        </div>
                        <div className="dom">{c.domain}</div>
                      </div>
                    </div>
                  </td>
                  <td>{c.subCategory}</td>
                  <td className="muted">{c.hq}</td>
                  <td className="num">{c.founded}</td>
                  <td className="num">
                    <span style={{display:"inline-flex", alignItems:"baseline", gap:6}}>
                      {c.employees.toLocaleString()}
                      <span className="mono" style={{fontSize:10, color: c.employeeGrowth > 0.3 ? "var(--positive)" : "var(--fg-4)"}}>
                        +{(c.employeeGrowth * 100).toFixed(0)}%
                      </span>
                    </span>
                  </td>
                  <td className="num">{fmtMoney(c.funding.total)}</td>
                  <td className="num">{fmtMoney(c.arr)}</td>
                  <td className="num">{fmtNum(c.customers)}</td>
                  <td className="num" style={{minWidth: 100}}>
                    {c.isSubject
                      ? <span className="dim">â</span>
                      : (
                        <div style={{display:"flex", alignItems:"center", gap:6, justifyContent:"flex-end"}}>
                          <Bar value={c.similarity * 100} />
                          <span style={{minWidth:24}}>{(c.similarity * 100).toFixed(0)}</span>
                        </div>
                      )
                    }
                  </td>
                  <td>
                    {c.isSubject
                      ? <span className="tag subject mono" style={{fontSize:9}}>â</span>
                      : <ThreatTag level={c.threat} />}
                  </td>
                  <td style={{textAlign:"right"}}>
                    <span className="dim" style={{cursor:"default"}}>{Icons.arrowR}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Profile cards (compact one-pagers) */}
      <div style={{height: 28}}></div>
      <SectionH title="Profile cards" meta="Compact one-pager per company" />
      <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(360px, 1fr))", gap: 14}}>
        {[subject, ...competitors].map(c => (
          <ProfileCard key={c.id} c={c} data={data} />
        ))}
      </div>
    </div>
  );
}

// âââ Profile card (compact) âââââââââââââââââââââââââââââââââââ
function ProfileCard({ c, data }) {
  const caps = data.capabilities[c.id] || [];
  const fullCount = caps.filter(x => x === "full").length;
  const totalCaps = data.features.length;

  return (
    <div className="card" style={{
      padding: 0,
      borderColor: c.isSubject ? "var(--accent-bg-2)" : "var(--border)",
      background: c.isSubject ? "var(--accent-bg)" : "var(--surface)",
    }}>
      {/* Header */}
      <div style={{padding:"14px 14px 10px", display:"flex", gap:10, alignItems:"flex-start"}}>
        <LogoMark name={c.name} subject={c.isSubject} />
        <div style={{flex:1, minWidth:0}}>
          <div style={{display:"flex", alignItems:"center", gap:6, flexWrap:"wrap"}}>
            <span style={{fontWeight:600, fontSize:14}}>{c.name}</span>
            {c.isSubject
              ? <span className="tag subject mono" style={{fontSize:9}}>SUBJECT</span>
              : <ThreatTag level={c.threat} />}
          </div>
          <div className="mono" style={{color:"var(--fg-4)", fontSize:10.5, marginTop:1}}>{c.domain} {Icons.ext}</div>
        </div>
      </div>

      <div style={{padding:"0 14px 10px", fontSize:12.5, color:"var(--fg-2)", lineHeight:1.45}}>
        "{c.tagline}"
      </div>

      {/* Stats grid */}
      <div style={{
        display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr",
        borderTop:"1px solid " + (c.isSubject ? "var(--accent-bg-2)" : "var(--border)"),
        borderBottom:"1px solid " + (c.isSubject ? "var(--accent-bg-2)" : "var(--border)"),
      }}>
        {[
          { k: "Founded",   v: c.founded, mono: true },
          { k: "HQ",        v: c.hq.split(",")[0], mono: false },
          { k: "Employees", v: c.employees.toLocaleString(), mono: true },
          { k: "Raised",    v: fmtMoney(c.funding.total), mono: true },
        ].map((s, i) => (
          <div key={s.k} style={{padding:"8px 10px", borderRight: i < 3 ? "1px solid " + (c.isSubject ? "var(--accent-bg-2)" : "var(--border-dim)") : "none"}}>
            <div className="mono" style={{fontSize:9, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--fg-4)"}}>{s.k}</div>
            <div style={{fontSize:13, fontWeight:500, marginTop:2, fontFamily: s.mono ? "var(--font-mono)" : "inherit"}}>{s.v}</div>
          </div>
        ))}
      </div>

      {/* Body */}
      <div style={{padding:"10px 14px"}}>
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"baseline", fontSize:11.5}}>
          <span className="mono" style={{fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--fg-4)"}}>Pricing</span>
          <span className="mono" style={{fontSize:11, color:"var(--fg-2)"}}>{c.pricing.mention}</span>
        </div>
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"baseline", fontSize:11.5, marginTop:6}}>
          <span className="mono" style={{fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--fg-4)"}}>Last round</span>
          <span className="mono" style={{fontSize:11, color:"var(--fg-2)"}}>{c.funding.lastRound} Â· {fmtDate(c.funding.lastRoundAt)}</span>
        </div>
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"baseline", fontSize:11.5, marginTop:6}}>
          <span className="mono" style={{fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--fg-4)"}}>Feature coverage</span>
          <span className="mono" style={{fontSize:11, color:"var(--fg-2)"}}>{fullCount}/{totalCaps} full</span>
        </div>
        <div style={{marginTop:6}}>
          <Bar value={(fullCount / totalCaps) * 100} subject={c.isSubject} />
        </div>

        <div style={{marginTop:10, display:"flex", flexWrap:"wrap", gap:5}}>
          {c.notable.map(n => (
            <span key={n} className="tag" style={{fontSize:10, padding:"1px 6px"}}>{n}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

window.ListScreen = ListScreen;
