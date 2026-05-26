// screens-home.jsx — Home: list of companies the user has already scanned
const { useState: _uS_home, useEffect: _uE_home, useRef: _uR_home } = React;

const PAST_SCANS = [
  { name: "Linear",          domain: "linear.app",         category: "Developer Tools · Project Management",   competitors: 8,  scannedAt: "2 hours ago",   status: "fresh",    isCurrent: true },
  { name: "Modern Treasury", domain: "moderntreasury.com", category: "B2B Payments · Bank Operations",        competitors: 11, scannedAt: "Yesterday",     status: "fresh" },
  { name: "Mercury",         domain: "mercury.com",        category: "B2B Banking · SMB Banking",             competitors: 14, scannedAt: "3 days ago",    status: "fresh" },
  { name: "Ramp",            domain: "ramp.com",           category: "B2B Payments · Spend Management",       competitors: 9,  scannedAt: "1 week ago",    status: "stale" },
  { name: "Vanta",           domain: "vanta.com",          category: "Security · Compliance Automation",      competitors: 12, scannedAt: "2 weeks ago",   status: "stale" },
  { name: "Retool",          domain: "retool.com",         category: "Developer Tools · Internal Tooling",    competitors: 7,  scannedAt: "3 weeks ago",   status: "stale" },
  { name: "Hex",             domain: "hex.tech",           category: "Data · Notebooks & Analytics",          competitors: 10, scannedAt: "1 month ago",   status: "stale" },
  { name: "Persona",         domain: "withpersona.com",    category: "Identity · KYC / Verification",         competitors: 8,  scannedAt: "1 month ago",   status: "stale" },
  { name: "Statsig",         domain: "statsig.com",        category: "Developer Tools · Experimentation",     competitors: 6,  scannedAt: "2 months ago",  status: "stale" },
  { name: "Pylon",           domain: "usepylon.com",       category: "Customer Support · B2B SaaS",           competitors: 9,  scannedAt: "2 months ago",  status: "stale" },
  { name: "Browserbase",     domain: "browserbase.com",    category: "Developer Tools · Browser Infra",       competitors: 5,  scannedAt: "3 months ago",  status: "archived" },
  { name: "Resend",          domain: "resend.com",         category: "Developer Tools · Email API",           competitors: 7,  scannedAt: "3 months ago",  status: "archived" },
];

function RowMenu({ scan, onRescan, onDelete }) {
  const [open, setOpen] = _uS_home(false);
  const [confirming, setConfirming] = _uS_home(false);
  const ref = _uR_home(null);

  _uE_home(() => {
    if (!open) return;
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setConfirming(false); } };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} style={{position:"relative"}} onClick={e => e.stopPropagation()}>
      <button
        onClick={() => { setOpen(v => !v); setConfirming(false); }}
        style={{
          background:"none", border:"none", cursor:"pointer",
          color:"var(--fg-4)", padding:"4px 6px", borderRadius:4,
          fontSize:15, lineHeight:1,
        }}
        title="More options"
      >
        ···
      </button>
      {open && (
        <div style={{
          position:"absolute", right:0, top:"100%", marginTop:4,
          background:"var(--surface)", border:"1px solid var(--border)",
          borderRadius:8, boxShadow:"0 4px 16px rgba(0,0,0,.1)",
          minWidth:148, zIndex:100, overflow:"hidden",
        }}>
          {!confirming ? (
            <>
              <button
                onClick={() => { setOpen(false); onRescan(scan); }}
                style={{
                  display:"flex", alignItems:"center", gap:8,
                  width:"100%", padding:"9px 14px", border:"none",
                  background:"none", cursor:"pointer", fontSize:12.5,
                  color:"var(--fg)", fontFamily:"var(--font-sans)", textAlign:"left",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
                onMouseLeave={e => e.currentTarget.style.background = "none"}
              >
                {Icons.zap} Re-scan
              </button>
              <div style={{height:1, background:"var(--border)", margin:"2px 0"}} />
              <button
                onClick={() => setConfirming(true)}
                style={{
                  display:"flex", alignItems:"center", gap:8,
                  width:"100%", padding:"9px 14px", border:"none",
                  background:"none", cursor:"pointer", fontSize:12.5,
                  color:"var(--negative, #c0392b)", fontFamily:"var(--font-sans)", textAlign:"left",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--negative-bg, #fdf2f2)"}
                onMouseLeave={e => e.currentTarget.style.background = "none"}
              >
                {Icons.x} Delete
              </button>
            </>
          ) : (
            <div style={{padding:"12px 14px"}}>
              <div style={{fontSize:12, color:"var(--fg-2)", marginBottom:10, lineHeight:1.4}}>
                Delete <strong>{scan.name}</strong>?
              </div>
              <div style={{display:"flex", gap:6}}>
                <button
                  onClick={() => { setOpen(false); setConfirming(false); onDelete(scan); }}
                  style={{
                    flex:1, padding:"6px 0", border:"none", borderRadius:5,
                    background:"var(--negative, #c0392b)", color:"#fff",
                    fontSize:12, fontWeight:600, cursor:"pointer",
                    fontFamily:"var(--font-sans)",
                  }}
                >
                  Delete
                </button>
                <button
                  onClick={() => setConfirming(false)}
                  style={{
                    flex:1, padding:"6px 0", border:"1px solid var(--border)", borderRadius:5,
                    background:"none", color:"var(--fg-2)",
                    fontSize:12, cursor:"pointer", fontFamily:"var(--font-sans)",
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HomeScreen({ onOpenCurrent, onNewScan, scanInProgress, showToast }) {
  const [q, setQ] = _uS_home("");
  const [scans, setScans] = _uS_home(PAST_SCANS);

  const handleRescan = (scan) => {
    setScans(prev => prev.map(s =>
      s.domain === scan.domain ? { ...s, status: "scanning" } : s
    ));
    setTimeout(() => {
      setScans(prev => prev.map(s =>
        s.domain === scan.domain ? { ...s, status: "fresh", scannedAt: "Just now" } : s
      ));
      if (showToast) showToast({
        label: `Re-scan complete — ${scan.name}`,
        action: null,
      });
    }, 10000);
  };

  const handleDelete = (scan) => {
    setScans(prev => prev.filter(s => s.domain !== scan.domain));
  };

  const filtered = scans.filter(s => {
    if (!q) return true;
    return s.name.toLowerCase().includes(q.toLowerCase()) ||
           s.domain.toLowerCase().includes(q.toLowerCase());
  });

  return (
    <div style={{flex:1, overflow:"auto", background:"var(--bg)"}}>
      {/* Page header */}
      <div style={{
        padding:"28px 36px 18px",
        borderBottom:"1px solid var(--border)",
        background:"var(--bg-2)",
      }}>
        <div style={{display:"flex", alignItems:"baseline", gap:12}}>
          <h1 className="serif" style={{
            fontSize:26, fontWeight:500, letterSpacing:"-0.02em",
            margin:0, lineHeight:1.1,
          }}>
            Your analyses
          </h1>
          <span className="mono" style={{fontSize:11, color:"var(--fg-4)"}}>
            {scans.length} companies · last 90 days
          </span>
          <div style={{flex:1}} />
          <button className="tb-btn primary" onClick={onNewScan}>
            {Icons.zap}<span>New analysis</span>
          </button>
        </div>
        <p style={{color:"var(--fg-3)", fontSize:13, margin:"6px 0 0", maxWidth:600}}>
          Every URL you've analysed, ranked by recency.
        </p>
      </div>

      {/* Toolbar */}
      <div style={{
        padding:"12px 36px",
        display:"flex", alignItems:"center", gap:8,
        borderBottom:"1px solid var(--border)",
      }}>
        <div style={{
          display:"flex", alignItems:"center", gap:8,
          border:"1px solid var(--border)", borderRadius:6,
          padding:"6px 10px", background:"var(--surface)",
          minWidth:260,
        }}>
          <span style={{color:"var(--fg-4)"}}>{Icons.search}</span>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search"
            style={{
              flex:1, border:"none", outline:"none", background:"transparent",
              fontSize:12.5, fontFamily:"var(--font-sans)", color:"var(--fg)",
            }}
          />
          {q && (
            <button
              onClick={() => setQ("")}
              style={{border:"none", background:"none", cursor:"pointer", color:"var(--fg-4)", padding:0, lineHeight:1}}
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div style={{padding:"0 36px 48px"}}>
        <table className="h-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Category</th>
              <th className="num">Competitors</th>
              <th>Last scan</th>
              <th>Status</th>
              <th style={{width:36}}></th>
            </tr>
          </thead>
          <tbody>
            {scanInProgress && (
              <tr
                style={{opacity:1, background:"var(--accent-bg, rgba(179,74,31,.04))", cursor: scanInProgress.done ? "pointer" : "default"}}
                onClick={scanInProgress.done ? onOpenCurrent : undefined}
              >
                <td>
                  <div style={{display:"flex", alignItems:"center", gap:10}}>
                    <img
                      src={`https://www.google.com/s2/favicons?domain=${scanInProgress.domain}&sz=32`}
                      width={20} height={20}
                      alt={scanInProgress.domain}
                      style={{borderRadius:4, flexShrink:0, opacity: scanInProgress.done ? 1 : .6}}
                    />
                    <div>
                      <div style={{fontWeight:500, color:"var(--fg)", fontSize:13}}>
                        {scanInProgress.domain}
                        {!scanInProgress.done && (
                          <span className="tag mono" style={{marginLeft:8, fontSize:9.5, padding:"1px 5px", background:"var(--accent-bg)", color:"var(--accent)", border:"1px solid var(--accent-border, rgba(179,74,31,.2))"}}>
                            SCANNING
                          </span>
                        )}
                        {scanInProgress.done && (
                          <span className="tag mono" style={{marginLeft:8, fontSize:9.5, padding:"1px 5px", background:"var(--positive-bg, #eaf5ee)", color:"var(--positive, #1a7a3e)", border:"1px solid rgba(26,122,62,.2)"}}>
                            CURRENT
                          </span>
                        )}
                      </div>
                      <div className="mono" style={{fontSize:11, color:"var(--fg-4)"}}>{scanInProgress.domain}</div>
                    </div>
                  </div>
                </td>
                <td style={{color:"var(--fg-4)", fontSize:12.5}}>—</td>
                <td className="num mono" style={{color:"var(--fg-4)"}}>—</td>
                <td style={{color:"var(--fg-3)", fontSize:12.5}}>Just now</td>
                <td>
                  {!scanInProgress.done ? (
                    <span style={{display:"inline-flex", alignItems:"center", gap:6, fontSize:11.5, color:"var(--accent)"}}>
                      <span className="dot-pulse" style={{transform:"scale(.75)"}}><i></i><i></i><i></i></span>
                      Scanning
                    </span>
                  ) : (
                    <span className="h-status fresh"><span className="dot"></span>Fresh</span>
                  )}
                </td>
                <td>
                  <RowMenu
                    scan={{ name: scanInProgress.domain, domain: scanInProgress.domain }}
                    onRescan={() => {}}
                    onDelete={() => {}}
                  />
                </td>
              </tr>
            )}
            {filtered.map(s => (
              <tr key={s.domain}
                  onClick={() => onOpenCurrent(s)}
                  className={s.isCurrent ? "is-current" : ""}>
                <td>
                  <div style={{display:"flex", alignItems:"center", gap:10}}>
                    <img
                      src={`https://www.google.com/s2/favicons?domain=${s.domain}&sz=32`}
                      width={20} height={20}
                      alt={s.name}
                      style={{borderRadius:4, flexShrink:0}}
                    />
                    <div>
                      <div style={{fontWeight:500, color:"var(--fg)", fontSize:13}}>
                        {s.name}
                        {s.isCurrent && (
                          <span className="tag subject mono" style={{marginLeft:8, fontSize:9.5, padding:"1px 5px"}}>
                            CURRENT
                          </span>
                        )}
                      </div>
                      <div className="mono" style={{fontSize:11, color:"var(--fg-4)"}}>{s.domain}</div>
                    </div>
                  </div>
                </td>
                <td style={{color:"var(--fg-2)", fontSize:12.5}}>{s.category}</td>
                <td className="num mono" style={{color:"var(--fg-2)"}}>{s.competitors}</td>
                <td style={{color:"var(--fg-3)", fontSize:12.5}}>{s.scannedAt}</td>
                <td>
                  {s.status === "scanning" ? (
                    <span style={{display:"inline-flex", alignItems:"center", gap:6, fontSize:11.5, color:"var(--accent)"}}>
                      <span className="dot-pulse" style={{transform:"scale(.75)"}}><i></i><i></i><i></i></span>
                      Scanning
                    </span>
                  ) : (
                    <span className={"h-status " + s.status}>
                      <span className="dot"></span>
                      {s.status === "fresh" && "Fresh"}
                      {s.status === "stale" && "Stale"}
                      {s.status === "archived" && "Archived"}
                    </span>
                  )}
                </td>
                <td>
                  <RowMenu scan={s} onRescan={handleRescan} onDelete={handleDelete} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div style={{
            padding:"60px 20px", textAlign:"center", color:"var(--fg-4)", fontSize:13,
          }}>
            No analyses match that search.
          </div>
        )}
      </div>
    </div>
  );
}

window.HomeScreen = HomeScreen;
