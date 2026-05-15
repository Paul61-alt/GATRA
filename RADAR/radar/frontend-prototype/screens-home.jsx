// screens-home.jsx â Home: list of companies the user has already scanned
const { useState: _uS_home } = React;

// Fictional history of past scans (subject of current scan is first row).
const PAST_SCANS = [
  { name: "Linq",            domain: "linq.io",            category: "B2B Payments Â· Payment Infrastructure", competitors: 8,  scannedAt: "2 hours ago",   pinned: true,  status: "fresh",  isCurrent: true },
  { name: "Modern Treasury", domain: "moderntreasury.com", category: "B2B Payments Â· Bank Operations",        competitors: 11, scannedAt: "Yesterday",     pinned: true,  status: "fresh" },
  { name: "Mercury",         domain: "mercury.com",        category: "B2B Banking Â· SMB Banking",             competitors: 14, scannedAt: "3 days ago",    pinned: false, status: "fresh" },
  { name: "Ramp",            domain: "ramp.com",           category: "B2B Payments Â· Spend Management",       competitors: 9,  scannedAt: "1 week ago",    pinned: true,  status: "stale" },
  { name: "Vanta",           domain: "vanta.com",          category: "Security Â· Compliance Automation",      competitors: 12, scannedAt: "2 weeks ago",   pinned: false, status: "stale" },
  { name: "Retool",          domain: "retool.com",         category: "Developer Tools Â· Internal Tooling",    competitors: 7,  scannedAt: "3 weeks ago",   pinned: false, status: "stale" },
  { name: "Hex",             domain: "hex.tech",           category: "Data Â· Notebooks & Analytics",          competitors: 10, scannedAt: "1 month ago",   pinned: false, status: "stale" },
  { name: "Persona",         domain: "withpersona.com",    category: "Identity Â· KYC / Verification",         competitors: 8,  scannedAt: "1 month ago",   pinned: false, status: "stale" },
  { name: "Statsig",         domain: "statsig.com",        category: "Developer Tools Â· Experimentation",     competitors: 6,  scannedAt: "2 months ago",  pinned: false, status: "stale" },
  { name: "Pylon",           domain: "usepylon.com",       category: "Customer Support Â· B2B SaaS",           competitors: 9,  scannedAt: "2 months ago",  pinned: false, status: "stale" },
  { name: "Browserbase",     domain: "browserbase.com",    category: "Developer Tools Â· Browser Infra",       competitors: 5,  scannedAt: "3 months ago",  pinned: false, status: "archived" },
  { name: "Resend",          domain: "resend.com",         category: "Developer Tools Â· Email API",           competitors: 7,  scannedAt: "3 months ago",  pinned: false, status: "archived" },
];

function HomeScreen({ onOpenCurrent, onNewScan }) {
  const [filter, setFilter] = _uS_home("all");
  const [q, setQ] = _uS_home("");

  const filtered = PAST_SCANS.filter(s => {
    if (filter === "pinned" && !s.pinned) return false;
    if (filter === "fresh" && s.status !== "fresh") return false;
    if (filter === "archived" && s.status !== "archived") return false;
    if (q && !(s.name.toLowerCase().includes(q.toLowerCase()) || s.domain.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });

  return (
    <div style={{flex:1, overflow:"auto", background:"var(--bg)"}}>
      {/* Page header */}
      <div style={{
        padding: "28px 36px 18px",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-2)",
      }}>
        <div style={{display:"flex", alignItems:"baseline", gap:12}}>
          <h1 className="serif" style={{
            fontSize: 26, fontWeight: 500, letterSpacing: "-0.02em",
            margin: 0, lineHeight: 1.1,
          }}>
            Your scans
          </h1>
          <span className="mono" style={{fontSize:11, color:"var(--fg-4)"}}>
            {PAST_SCANS.length} companies Â· last 90 days
          </span>
          <div style={{flex:1}}></div>
          <button className="tb-btn primary" onClick={onNewScan}>
            {Icons.zap}<span>New scan</span>
          </button>
        </div>
        <p style={{color:"var(--fg-3)", fontSize:13, margin:"6px 0 0", maxWidth:600}}>
          Every URL you've scanned. Pinned scans auto-refresh weekly; the rest stay frozen at scan time.
        </p>
      </div>

      {/* Toolbar */}
      <div style={{
        padding: "12px 36px",
        display: "flex", alignItems: "center", gap: 8,
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{
          display:"flex", alignItems:"center", gap:8,
          border:"1px solid var(--border)", borderRadius:6,
          padding:"6px 10px", background:"var(--surface)",
          minWidth: 260,
        }}>
          <span style={{color:"var(--fg-4)"}}>{Icons.search}</span>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Filter scans by name or domainâ¦"
            style={{
              flex:1, border:"none", outline:"none", background:"transparent",
              fontSize: 12.5, fontFamily: "var(--font-sans)", color:"var(--fg)",
            }}/>
        </div>

        <div style={{display:"flex", border:"1px solid var(--border)", borderRadius:6, overflow:"hidden"}}>
          {[
            { k: "all",      l: "All",      n: PAST_SCANS.length },
            { k: "pinned",   l: "Pinned",   n: PAST_SCANS.filter(s => s.pinned).length },
            { k: "fresh",    l: "Fresh",    n: PAST_SCANS.filter(s => s.status === "fresh").length },
            { k: "archived", l: "Archived", n: PAST_SCANS.filter(s => s.status === "archived").length },
          ].map((f, i, arr) => (
            <button key={f.k}
              onClick={() => setFilter(f.k)}
              style={{
                border:"none", background: filter === f.k ? "var(--bg)" : "var(--surface)",
                color: filter === f.k ? "var(--fg)" : "var(--fg-3)",
                padding:"6px 12px", fontSize:12,
                borderRight: i < arr.length - 1 ? "1px solid var(--border)" : "none",
                cursor:"pointer", fontWeight: filter === f.k ? 500 : 400,
                fontFamily:"var(--font-sans)",
              }}>
              {f.l} <span className="mono" style={{color:"var(--fg-4)", marginLeft:4, fontSize:10.5}}>{f.n}</span>
            </button>
          ))}
        </div>

        <div style={{flex:1}}></div>
        <button className="tb-btn">{Icons.filter}<span>Filter</span></button>
        <button className="tb-btn">{Icons.sort}<span>Sort: recent</span></button>
      </div>

      {/* Table */}
      <div style={{padding:"0 36px 48px"}}>
        <table className="h-table">
          <thead>
            <tr>
              <th style={{width:36}}></th>
              <th>Company</th>
              <th>Category</th>
              <th className="num">Competitors</th>
              <th>Last scan</th>
              <th>Status</th>
              <th style={{width:36}}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.domain}
                  onClick={() => onOpenCurrent(s)}
                  className={s.isCurrent ? "is-current" : ""}>
                <td>
                  <span style={{color: s.pinned ? "var(--accent)" : "var(--fg-5, #c8c3b8)"}}>
                    {Icons.pin}
                  </span>
                </td>
                <td>
                  <div style={{display:"flex", alignItems:"center", gap:10}}>
                    <LogoMark name={s.name} subject={s.isCurrent} size="sm" />
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
                  <span className={"h-status " + s.status}>
                    <span className="dot"></span>
                    {s.status === "fresh" && "Fresh"}
                    {s.status === "stale" && "Stale"}
                    {s.status === "archived" && "Archived"}
                  </span>
                </td>
                <td>
                  <span style={{color:"var(--fg-4)"}}>{Icons.arrowR}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div style={{
            padding:"60px 20px", textAlign:"center", color:"var(--fg-4)",
            fontSize:13,
          }}>
            No scans match that filter.
          </div>
        )}
      </div>
    </div>
  );
}

window.HomeScreen = HomeScreen;
