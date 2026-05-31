// components.jsx â shared UI primitives for Radar
// Exported via window globals at the bottom.

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// âââ Utility ââââââââââââââââââââââââââââââââââââââââââââââââââ
const fmtMoney = (n) => {
  if (n == null) return "â";
  if (n >= 1e9) return "€" + (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return "€" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "€" + (n / 1e3).toFixed(0) + "k";
  return "€" + n;
};
// F2: status-aware funding label so bootstrapped/stealth/not_found don't render as "$0"
const fmtFunding = (f) => {
  if (!f) return "—";
  if (f.status === "bootstrapped") return "Bootstrapped";
  if (f.status === "stealth")      return "Stealth";
  if (f.status === "pending")      return "Enriching…";
  if (f.status === "not_found")    return "—";
  return fmtMoney(f.total || 0);
};
const fmtNum = (n) => {
  if (n == null) return "â";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
};
const fmtPct = (n, d = 0) => (n == null ? "â" : (n * 100).toFixed(d) + "%");
const fmtDate = (s) => {
  if (!s) return "â";
  const [y, m] = s.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m, 10) - 1]} '${y.slice(2)}`;
};

// âââ Icons (line, 14Ã14 default, currentColor) ââââââââââââââââ
const Ic = ({ d, sz = 14, sw = 1.5, fill = "none", style }) => (
  <svg width={sz} height={sz} viewBox="0 0 24 24" fill={fill} stroke="currentColor"
       strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" style={style}>
    {d}
  </svg>
);
const Icons = {
  search:    <Ic d={<><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>} />,
  overview:  <Ic d={<><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></>} />,
  list:      <Ic d={<><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/></>} />,
  compare:   <Ic d={<><path d="M12 3v18"/><path d="m7 8 5-5 5 5"/><path d="m7 16 5 5 5-5"/></>} />,
  map:       <Ic d={<><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></>} />,
  features:  <Ic d={<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></>} />,
  pricing:   <Ic d={<><path d="M20 12V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h6"/><path d="M16 18h6M19 15v6"/></>} />,
  timeline:  <Ic d={<><path d="M3 12h18"/><circle cx="6" cy="12" r="2"/><circle cx="13" cy="12" r="2"/><circle cx="20" cy="12" r="2"/></>} />,
  download:  <Ic d={<><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"/></>} />,
  share:     <Ic d={<><circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="m9 13 6 4M9 11l6-4"/></>} />,
  bell:      <Ic d={<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></>} />,
  filter:    <Ic d={<path d="M3 5h18l-7 8v6l-4 2v-8z"/>} />,
  sort:      <Ic d={<><path d="M7 3v18m0 0-3-3m3 3 3-3"/><path d="M17 21V3m0 0-3 3m3-3 3 3"/></>} />,
  more:      <Ic d={<><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>} />,
  ext:       <Ic d={<><path d="M7 7h10v10"/><path d="M7 17 17 7"/></>} />,
  check:     <Ic d={<path d="m4 12 5 5L20 6"/>} />,
  x:         <Ic d={<path d="M5 5l14 14M19 5 5 19"/>} />,
  minus:     <Ic d={<path d="M5 12h14"/>} />,
  plus:      <Ic d={<><path d="M12 5v14M5 12h14"/></>} />,
  pin:       <Ic d={<><circle cx="12" cy="10" r="3"/><path d="M12 2c-3.5 0-7 3-7 7 0 5 7 13 7 13s7-8 7-13c0-4-3.5-7-7-7Z"/></>} />,
  globe:     <Ic d={<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></>} />,
  arrowR:    <Ic d={<><path d="M5 12h14M13 5l7 7-7 7"/></>} />,
  arrowU:    <Ic d={<path d="M12 19V5m0 0-6 6m6-6 6 6"/>} />,
  arrowD:    <Ic d={<path d="M12 5v14m0 0-6-6m6 6 6-6"/>} />,
  zap:       <Ic d={<path d="M13 2 3 14h7l-1 8 10-12h-7z"/>} />,
  building:  <Ic d={<><rect x="4" y="3" width="16" height="18"/><path d="M9 9h.01M14 9h.01M9 13h.01M14 13h.01M9 17h.01M14 17h.01"/></>} />,
  users:     <Ic d={<><circle cx="9" cy="8" r="3.5"/><path d="M3 21c0-3 3-6 6-6s6 3 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M21 19c0-2-2-4-4.5-4"/></>} />,
  cash:      <Ic d={<><rect x="3" y="6" width="18" height="12" rx="1"/><circle cx="12" cy="12" r="2.5"/></>} />,
  link:      <Ic d={<><path d="M9 15a4 4 0 0 1 0-6l3-3a4 4 0 1 1 6 6l-1 1"/><path d="M15 9a4 4 0 0 1 0 6l-3 3a4 4 0 1 1-6-6l1-1"/></>} />,
  trend:     <Ic d={<><path d="M3 17 9 11l4 4 8-8"/><path d="M14 4h7v7"/></>} />,
  trash:     <Ic d={<><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></>} />,
  chevD:     <Ic d={<path d="m6 9 6 6 6-6"/>} />,
  memo:      <Ic d={<><path d="M5 3h10l4 4v14H5z"/><path d="M15 3v4h4"/><path d="M9 12h6M9 16h6M9 8h2"/></>} />,
};

// âââ Sidebar ââââââââââââââââââââââââââââââââââââââââââââââââââ
function Sidebar({ view, onView, currentSubjectName }) {
  const items = [
    { key: "new",     label: "New scan",     icon: "zap" },
    { key: "home",    label: "Home",         icon: "list" },
    { key: "current", label: "Current scan", icon: "overview", meta: currentSubjectName || null },
  ];
  return (
    <aside className="sb">
      <div className="sb-brand">
        <svg viewBox="0 0 79 56" style={{width:28,height:20,flexShrink:0}} xmlns="http://www.w3.org/2000/svg" fillRule="evenodd" clipRule="evenodd">
          <g>
            <path d="M28.203,19.607c-1.356,0.147 -8.172,0.153 -15.681,5.958c-5.599,4.328 -6.763,10.718 -11.279,7.592c-4.724,-3.27 4.994,-13.084 12.733,-17.014c23.211,-11.787 52.909,5.415 51.319,32.977c-0.272,4.723 -7.132,4.355 -7.121,0.016c0.004,-1.594 1.155,-12.257 -8.321,-21.65c-8.402,-8.329 -19.808,-7.941 -21.65,-7.878Z" fill="#ff5d00"/>
            <path d="M34.236,0.182c0.1,0.256 -0.151,0.566 -0.051,0.822c0.078,0.202 1.082,0.15 1.177,0.145c0.617,-0.032 0.52,-0.188 1.147,-0.698c1.119,0.188 2.239,0.375 3.358,0.563c-1.038,1.849 1.077,0.317 1.153,0.261c2.265,0.582 2.231,0.574 4.477,1.264c-0.031,0.058 -0.383,0.729 -0.383,0.729c0.159,0.241 1.088,-0.4 1.17,-0.457c2.1,0.836 24.443,8.135 30.632,34.244c-0.162,0.093 -0.398,-0.141 -0.56,-0.048c-0.128,0.074 -0.136,0.832 -0.025,0.88c0.232,0.101 0.526,-0.139 0.757,-0.038c0.346,1.899 0.322,1.862 0.597,3.735c-0.096,0.057 -1.029,-0.088 -0.714,1.901c0.062,0.39 0.098,0.404 0.13,0.416c0.421,0.161 0.424,-0.204 0.839,-0.046c0.173,3.576 1.171,9.417 -4.544,8.568c-0.213,-0.34 0.209,-0.386 -0.004,-0.726c-0.038,-0.06 -0.085,0.055 -0.751,-0.481c-0.78,-0.627 -0.752,-0.682 -0.838,-0.679c-0.173,0.005 -0.311,0.184 -0.484,0.189c-0.272,-0.572 -0.242,-0.563 -0.382,-1.199c0.967,-1.135 0.726,-1.242 0.746,-2.656c0.004,-0.275 0.048,-3.352 -0.159,-3.435c-0.245,-0.099 -0.546,0.147 -0.792,0.049c-0.43,-3.096 -0.182,-3.266 -1.826,-8.671c0.558,-0.449 0.757,-0.469 0.49,-1.125c-0.232,-0.569 -0.336,-0.009 -0.726,0.463c-3.752,-9.39 -7.532,-14.154 -16.081,-20.271c-1.887,-1.11 -1.847,-1.132 -3.773,-2.204c0.04,-0.639 0.305,-0.841 -0.302,-1.015c-0.508,-0.146 -0.424,0.107 -0.762,0.515c-6.461,-2.956 -9.693,-3.323 -13.523,-3.791c0.386,-0.753 0.454,-0.749 0.416,-0.811c-0.149,-0.245 -1.764,-0.181 -1.918,-0.175c-0.632,0.025 -0.318,0.329 0.011,0.836c-2.076,-0.059 -2.045,-0.063 -4.146,-0.08c-0.082,-0.133 0.047,-0.632 -0.757,-0.696c-0.185,-0.015 -2.213,-0.174 -2.317,0.093c-0.099,0.254 0.16,0.563 0.061,0.817c-0.754,0.062 -3.22,0.773 -4.799,-1.213c-0.327,-0.412 -1.035,-1.77 -0.517,-3.333c0.629,-1.896 3.083,-2.352 3.411,-2.412c0.233,0.364 0.054,0.866 1.526,0.673c0.392,-0.052 0.404,-0.081 0.417,-0.113c0.163,-0.397 -0.205,-0.402 -0.044,-0.795c4.934,-0.301 4.917,-0.165 8.661,0.003Z" fill="#ff5d00"/>
            <path d="M33.476,25.07c-0.362,0.51 -0.612,0.779 0.004,0.891c0.755,0.137 0.735,-0.03 1.155,-0.68c2.668,0.683 6.133,1.239 11.006,5.668c-0.003,0.159 -0.171,0.284 -0.174,0.443c-0.025,1.555 0.49,1.417 2.019,1.487c1.273,1.623 1.254,1.603 2.341,3.364c-0.053,-0.016 -1.128,-0.739 -0.737,0.131c0.046,0.102 0.068,0.212 0.113,0.314c0.374,0.841 0.937,0.317 1.014,0.315c0.459,0.97 3.694,7.806 2.067,13.25c-0.285,0.955 -1.643,1.873 -1.822,1.994c-1.526,-2.263 -2.964,-0.216 -3.107,-0.012c-4.297,-3.023 0.462,-5.677 -4.2,-13.202c-1.958,-3.161 -5.083,-4.892 -5.618,-5.188c-3.248,-1.799 -7.863,-1.846 -8.564,-1.854c-0.069,-0.061 -2.495,-2.217 -1.149,0.132c-6.594,1.545 -10.552,4.118 -12.535,12.089c-0.462,-0.276 -0.745,-0.532 -0.754,0.021c-0.012,0.713 0.031,0.725 0.602,1.136c0.015,0.997 0.031,1.994 0.046,2.991c-0.047,0.026 -0.745,-0.359 -0.719,0.766c0.016,0.701 0.577,0.712 0.662,0.77c-0.41,0.845 -0.668,2.684 -3.859,2.673c0.052,-0.686 0.309,-1.069 -0.359,-0.942c0,0 -0.732,0.536 -0.795,0.582c-0.664,-0.438 -2.659,-0.765 -2.055,-7.963c0.41,-4.891 3.711,-9.887 4.216,-10.651c0.437,0.018 0.658,0.43 1.438,-0.658c0.015,-0.021 0.45,-0.627 -0.143,-0.297c-0.076,0.043 -0.07,0.04 -0.951,0.541c7.668,-9.75 19.078,-8.334 20.855,-8.114Z" fill="#ff5d00"/>
          </g>
          <path d="M30.343,36.995c5.166,0 9.36,4.194 9.36,9.36c0,5.166 -4.194,9.36 -9.36,9.36c-5.166,0 -9.36,-4.194 -9.36,-9.36c0,-5.166 4.194,-9.36 9.36,-9.36Zm0,6c-1.854,0 -3.36,1.506 -3.36,3.36c0,1.854 1.506,3.36 3.36,3.36c1.854,0 3.36,-1.506 3.36,-3.36c0,-1.854 -1.506,-3.36 -3.36,-3.36Z" fill="#ff5d00"/>
        </svg>
        <svg viewBox="0 0 160 47" style={{height:14,width:"auto"}} xmlns="http://www.w3.org/2000/svg" fillRule="evenodd" clipRule="evenodd">
          <text x="-3.25px" y="45.5px" style={{fontFamily:"'AvantGardeITCbyBT-Demi','AvantGarde Bk BT',sans-serif",fontWeight:700,fontSize:64,fill:"var(--fg)"}} >radar</text>
        </svg>
      </div>
      <div style={{marginTop: 32}} />
      {items.map(it => (
        <div key={it.key}
             className={"sb-item " + (view === it.key ? "active" : "")}
             onClick={() => onView(it.key)}>
          <span className="ic">{Icons[it.icon]}</span>
          <span>{it.label}</span>
          {it.meta && (
            <span className="sb-meta-name">{it.meta}</span>
          )}
        </div>
      ))}

      <div className="sb-foot">
        <div className="sb-avatar">JM</div>
        <div className="sb-foot-meta">
          <b>Index Ventures</b>
          <div>Investment team</div>
        </div>
      </div>
    </aside>
  );
}

// âââ Topbar âââââââââââââââââââââââââââââââââââââââââââââââââââ
// ─── Skeleton loader ──────────────────────────────────────────
function Skel({ w = "100%", h = 14, radius = 4, style = {} }) {
  return (
    <div className="skel" style={{width: w, height: h, borderRadius: radius, ...style}} />
  );
}

// ─── Print report (all sections, PDF export) ──────────────────
function PrintReport({ data }) {
  if (!data) return null;
  const { subject, competitors = [] } = data;
  const sorted = [...competitors].sort((a, b) => b.similarity - a.similarity);
  const totalRaised = competitors.reduce((s, c) => s + (c.funding?.total || 0), 0);

  return (
    <div className="print-report">
      <div className="pr-cover">
        <div className="pr-eyebrow">Competitive Analysis</div>
        <h1 className="pr-title">{subject.name}</h1>
        <div className="pr-sub">
          <a href={`https://${subject.domain}`}>{subject.domain}</a>
          &nbsp;·&nbsp;{subject.category}&nbsp;·&nbsp;{subject.hq}
        </div>
        <div className="pr-meta-row">
          <div><div className="pr-lbl">Founded</div><div className="pr-val">{subject.founded}</div></div>
          <div><div className="pr-lbl">Employees</div><div className="pr-val">{(subject.employees||0).toLocaleString()}</div></div>
          <div><div className="pr-lbl">Total raised</div><div className="pr-val">{fmtFunding(subject.funding)}</div></div>
          <div><div className="pr-lbl">Stage</div><div className="pr-val">{subject.funding?.lastRound||"—"}</div></div>
          <div><div className="pr-lbl">Competitors mapped</div><div className="pr-val">{competitors.length}</div></div>
          <div><div className="pr-lbl">Total market raised</div><div className="pr-val">{fmtMoney(totalRaised)}</div></div>
        </div>
        <p className="pr-tagline">{subject.tagline}</p>
      </div>

      <div className="pr-section">
        <h2 className="pr-h2">Competitor landscape</h2>
        <table className="pr-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Category</th>
              <th>HQ</th>
              <th style={{textAlign:"right"}}>Employees</th>
              <th style={{textAlign:"right"}}>Funding</th>
              <th>Stage</th>
              <th style={{textAlign:"right"}}>Similarity</th>
              <th>Threat</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(c => (
              <tr key={c.id}>
                <td><strong>{c.name}</strong><div style={{fontSize:10,color:"#888"}}>{c.domain}</div></td>
                <td style={{fontSize:11}}>{c.subCategory || c.category}</td>
                <td style={{fontSize:11}}>{c.hq?.split(",")[0]}</td>
                <td style={{textAlign:"right"}}>{c.employees ? fmtNum(c.employees) : "—"}</td>
                <td style={{textAlign:"right"}}>{fmtFunding(c.funding)}</td>
                <td style={{fontSize:11}}>{c.funding?.lastRound||"—"}</td>
                <td style={{textAlign:"right"}}>{c.similarity != null ? (c.similarity*100).toFixed(0)+"%" : "—"}</td>
                <td><span style={{
                  padding:"2px 6px", borderRadius:3, fontSize:10, fontWeight:600, textTransform:"uppercase",
                  background: c.threat==="high"?"#fdecea":c.threat==="medium"?"#fef7e0":"#eaf5ee",
                  color: c.threat==="high"?"#c0392b":c.threat==="medium"?"#a07000":"#1a7a3e",
                }}>{c.threat||"—"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pr-section">
        <h2 className="pr-h2">Key highlights — {subject.name}</h2>
        <ul className="pr-list">
          {(subject.notable||[]).map((n,i) => <li key={i}>{n}</li>)}
        </ul>
      </div>

      <div className="pr-section">
        <h2 className="pr-h2">Top competitors — detail</h2>
        {sorted.slice(0,5).map(c => (
          <div key={c.id} className="pr-co-block">
            <div className="pr-co-head">
              <strong>{c.name}</strong>
              <span style={{fontSize:11,color:"#888",marginLeft:8}}>{c.domain}</span>
              <span style={{marginLeft:"auto",fontSize:11}}>{fmtFunding(c.funding)}{c.funding?.status === "enriched" ? " raised" : ""} · {c.employees ? fmtNum(c.employees)+" employees" : ""}</span>
            </div>
            <p style={{fontSize:12,color:"#444",margin:"4px 0 6px"}}>{c.tagline}</p>
            <ul className="pr-list">
              {(c.notable||[]).slice(0,3).map((n,i) => <li key={i}>{n}</li>)}
            </ul>
          </div>
        ))}
      </div>

      <div className="pr-footer">
        Generated by Radar · {new Date().toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric"})}
      </div>
    </div>
  );
}

// Print view for a generated comparative memo (reuses .print-report / .pr-* CSS).
function MemoPrintReport({ memo, subject }) {
  if (!memo) return null;
  const renderBody = (body) =>
    String(body || "").split(/\n/).map((l) => l.trim()).filter(Boolean).map((l, i) => {
      const txt = l.replace(/\*\*(.+?)\*\*/g, "$1").replace(/^[-*•]\s+/, "• ");
      return <p key={i} style={{ fontSize: 12, color: "#333", margin: "5px 0", lineHeight: 1.5 }}>{txt}</p>;
    });
  return (
    <div className="print-report">
      <div className="pr-cover">
        <div className="pr-eyebrow">Comparative VC Memo</div>
        <h1 className="pr-title">{memo.subjectName || subject?.name}</h1>
        <div className="pr-sub">
          {subject?.domain && <a href={`https://${subject.domain}`}>{subject.domain}</a>}
          {subject?.category ? <>&nbsp;·&nbsp;{subject.category}</> : null}
        </div>
        <p className="pr-tagline">{memo.templateName}</p>
      </div>
      {memo.sections.map((s) => (
        <div key={s.id} className="pr-section">
          <h2 className="pr-h2">{s.title}{s.hasGaps ? "  —  (données incomplètes)" : ""}</h2>
          {renderBody(s.body)}
          {s.citations && s.citations.length > 0 && (
            <ul className="pr-list" style={{ marginTop: 6 }}>
              {s.citations.map((c, i) => (
                <li key={i} style={{ fontSize: 10.5, color: "#666" }}>
                  {c.company ? c.company + " — " : ""}{c.claim}
                  {c.sourceUrl ? <> · <a href={c.sourceUrl}>{c.sourceUrl}</a></> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      <div className="pr-footer">
        Generated by Radar · {memo.generatedAt ? new Date(memo.generatedAt).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : ""}
      </div>
    </div>
  );
}

function Topbar({ subject, data, onDelete, onRescan, isRescanning }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef(null);

  useEffect(() => {
    if (!exportOpen) return;
    const h = e => { if (exportRef.current && !exportRef.current.contains(e.target)) setExportOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [exportOpen]);

  const exportCSV = () => {
    setExportOpen(false);
    const competitors = data?.competitors || [];
    const rows = [
      ["Name","Domain","Category","Similarity","Threat","Funding","Last Round","Employees","HQ"],
      ...competitors.map(c => [
        c.name, c.domain, c.subCategory || c.category,
        c.similarity != null ? (c.similarity * 100).toFixed(0) + "%" : "",
        c.threat || "",
        c.funding?.total ? "€" + (c.funding.total / 1e6).toFixed(1) + "M" : "",
        c.funding?.lastRound || "",
        c.employees || "",
        c.hq || "",
      ])
    ];
    const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${subject.name.toLowerCase().replace(/\s+/g,"-")}-competitive-analysis.csv`;
    a.click();
  };

  const exportPDF = () => {
    setExportOpen(false);
    // Render the full print report then print
    const existing = document.getElementById("radar-print-root");
    if (existing) existing.remove();
    const el = document.createElement("div");
    el.id = "radar-print-root";
    document.body.appendChild(el);
    ReactDOM.createRoot(el).render(<PrintReport data={data} />);
    // Give React one frame to render, then print
    requestAnimationFrame(() => requestAnimationFrame(() => {
      window.print();
      setTimeout(() => el.remove(), 1000);
    }));
  };

  return (
    <header className="tb">
      <div className="tb-crumbs">
        <b>{subject.name}</b>
        <a href={`https://${subject.domain}`} target="_blank" rel="noopener noreferrer"
          className="mono"
          style={{fontSize:11.5, color:"var(--fg-4)", textDecoration:"none", marginLeft:8}}
          onMouseEnter={e => e.target.style.color="var(--fg-2)"}
          onMouseLeave={e => e.target.style.color="var(--fg-4)"}
        >{subject.domain}</a>
      </div>
      <div className="tb-spacer"></div>

      {!confirmDelete ? (
        <button className="tb-btn" style={{color:"var(--negative, #c0392b)"}}
          onClick={() => setConfirmDelete(true)}>
          {Icons.trash}<span>Delete</span>
        </button>
      ) : (
        <div style={{display:"flex", alignItems:"center", gap:6, padding:"0 4px"}}>
          <span style={{fontSize:12, color:"var(--fg-2)"}}>Delete this analysis?</span>
          <button className="tb-btn" style={{color:"var(--negative,#c0392b)", fontWeight:600}}
            onClick={() => { setConfirmDelete(false); onDelete && onDelete(); }}>
            Confirm
          </button>
          <button className="tb-btn" onClick={() => setConfirmDelete(false)}>Cancel</button>
        </div>
      )}

      <div ref={exportRef} style={{position:"relative"}}>
        <button className="tb-btn" onClick={() => setExportOpen(v => !v)}>
          {Icons.download}<span>Export</span>{Icons.chevD}
        </button>
        {exportOpen && (
          <div style={{
            position:"absolute", right:0, top:"calc(100% + 6px)",
            background:"var(--surface)", border:"1px solid var(--border)",
            borderRadius:8, boxShadow:"0 4px 16px rgba(0,0,0,.1)",
            minWidth:160, zIndex:200, overflow:"hidden",
          }}>
            <button onClick={exportPDF} style={{
              display:"flex", alignItems:"center", gap:10,
              width:"100%", padding:"10px 14px", border:"none",
              background:"none", cursor:"pointer", fontSize:12.5,
              color:"var(--fg)", fontFamily:"var(--font-sans)", textAlign:"left",
            }}
              onMouseEnter={e => e.currentTarget.style.background="var(--bg-2)"}
              onMouseLeave={e => e.currentTarget.style.background="none"}>
              {Icons.download}
              <div>
                <div style={{fontWeight:500}}>PDF report</div>
                <div style={{fontSize:11, color:"var(--fg-4)", marginTop:1}}>Full analysis, print-ready</div>
              </div>
            </button>
            <div style={{height:1, background:"var(--border)"}} />
            <button onClick={exportCSV} style={{
              display:"flex", alignItems:"center", gap:10,
              width:"100%", padding:"10px 14px", border:"none",
              background:"none", cursor:"pointer", fontSize:12.5,
              color:"var(--fg)", fontFamily:"var(--font-sans)", textAlign:"left",
            }}
              onMouseEnter={e => e.currentTarget.style.background="var(--bg-2)"}
              onMouseLeave={e => e.currentTarget.style.background="none"}>
              {Icons.list}
              <div>
                <div style={{fontWeight:500}}>CSV spreadsheet</div>
                <div style={{fontSize:11, color:"var(--fg-4)", marginTop:1}}>Competitor table, all fields</div>
              </div>
            </button>
          </div>
        )}
      </div>

      <button className="tb-btn primary" onClick={onRescan} disabled={isRescanning}
        style={{opacity: isRescanning ? .6 : 1}}>
        {isRescanning
          ? <><span className="dot-pulse" style={{transform:"scale(.75)"}}><i></i><i></i><i></i></span><span>Scanning…</span></>
          : <>{Icons.zap}<span>Re-scan</span></>
        }
      </button>
    </header>
  );
}

// âââ Tabs âââââââââââââââââââââââââââââââââââââââââââââââââââââ
function Tabs({ tabs, active, onTab }) {
  return (
    <nav className="tabs">
      {tabs.map(t => (
        <div key={t.key}
             className={"tab " + (active === t.key ? "active" : "")}
             onClick={() => onTab(t.key)}>
          {t.icon && (
            <span style={{width:14,height:14,display:"inline-grid",placeItems:"center"}}>{Icons[t.icon]}</span>
          )}
          <span>{t.label}</span>
          {t.count != null && <span className="count mono">{t.count}</span>}
          {t.onClose && (
            <span
              onClick={e => { e.stopPropagation(); t.onClose(); }}
              style={{
                display: "inline-grid", placeItems: "center",
                width: 14, height: 14, borderRadius: 3,
                marginLeft: 2, opacity: 0.5,
                cursor: "pointer",
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = 1}
              onMouseLeave={e => e.currentTarget.style.opacity = 0.5}
            >
              {Icons.x}
            </span>
          )}
        </div>
      ))}
    </nav>
  );
}

// âââ Logo placeholder âââââââââââââââââââââââââââââââââââââââââ
function LogoMark({ name, domain, subject = false, size = "md" }) {
  const cls = "logo-mark " + (subject ? "subject " : "") + size;
  const parts = name.split(/\s+/);
  let label = parts[0][0];
  if (parts.length > 1) label += parts[1][0];

  const [imgOk, setImgOk] = React.useState(!!domain);
  const px = size === "lg" ? 64 : size === "sm" ? 24 : 32;
  const src = domain
    ? `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${domain}&size=${px * 2}`
    : null;

  if (src && imgOk) {
    return (
      <div className={cls} style={{background:"var(--surface)", border:"1px solid var(--border-dim)", overflow:"hidden", padding: size === "lg" ? 6 : 3}}>
        <img
          src={src}
          alt={name}
          style={{width:"100%", height:"100%", objectFit:"contain", display:"block"}}
          onError={() => setImgOk(false)}
        />
      </div>
    );
  }
  return <div className={cls}>{label.toUpperCase()}</div>;
}

// âââ Threat tag âââââââââââââââââââââââââââââââââââââââââââââââ
function ThreatTag({ level }) {
  const labels = { high: "HIGH", medium: "MEDIUM", low: "LOW" };
  const cls = level === "high" ? "high" : level === "medium" ? "med" : "low";
  return <span className={"tag " + cls}><span className={"dot " + cls}></span>{labels[level]}</span>;
}

// âââ Mini bar chart âââââââââââââââââââââââââââââââââââââââââââ
function Bar({ value, max = 100, subject = false }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={"bar " + (subject ? "subject" : "")}>
      <i style={{ width: pct + "%" }}></i>
    </div>
  );
}

// âââ Sparkline âââââââââââââââââââââââââââââââââââââââââââââââââ
function Sparkline({ values, subject = false }) {
  const max = Math.max(...values, 1);
  return (
    <div className={"spark " + (subject ? "subject" : "")}>
      {values.map((v, i) => (
        <i key={i} style={{ height: Math.max(2, (v / max) * 22) + "px" }} />
      ))}
    </div>
  );
}

// âââ Section heading âââââââââââââââââââââââââââââââââââââââââ
function SectionH({ title, meta, children }) {
  return (
    <div className="section-h">
      <h2>{title}</h2>
      <div style={{display:"flex", alignItems:"center", gap:12}}>
        {meta && <span className="meta">{meta}</span>}
        {children}
      </div>
    </div>
  );
}

// ─── Country flag helper (shared across screens) ──────────────────────────────
const COUNTRY_ISO_MAP = {
  "United States": "US", "Australia": "AU", "Israel": "IL", "Czech Republic": "CZ",
  "India": "IN", "Canada": "CA", "Germany": "DE", "France": "FR",
  "United Kingdom": "GB", "Netherlands": "NL", "Sweden": "SE", "Finland": "FI",
  "Singapore": "SG", "Japan": "JP", "Brazil": "BR", "Spain": "ES",
  "Poland": "PL", "Ukraine": "UA", "Romania": "RO", "Hungary": "HU",
  "Switzerland": "CH", "Austria": "AT", "Belgium": "BE", "Denmark": "DK",
  "Norway": "NO", "Ireland": "IE", "Portugal": "PT", "New Zealand": "NZ",
  "South Korea": "KR", "China": "CN", "Philippines": "PH", "Indonesia": "ID",
  "Mexico": "MX", "Argentina": "AR", "Colombia": "CO", "Chile": "CL",
  "South Africa": "ZA", "Nigeria": "NG", "Kenya": "KE",
};

function countryFlag(hqString) {
  if (!hqString) return { flag: "🌐", iso: "—" };
  const parts = hqString.split(",").map(s => s.trim());
  const country = parts[parts.length - 1];
  const iso = COUNTRY_ISO_MAP[country] || country.slice(0, 2).toUpperCase();
  const flag = iso.length === 2
    ? iso.split("").map(c => String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65)).join("")
    : "🌐";
  return { flag, iso };
}

// ─── V2 Overview primitives ───────────────────────────────────
function fmtRelTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = (Date.now() - then) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  if (diff < 2592000) return Math.floor(diff / 86400) + "d ago";
  if (diff < 31536000) return Math.floor(diff / 2592000) + "mo ago";
  return Math.floor(diff / 31536000) + "y ago";
}

function CitationPopover({ children, evidence, sourceUrl, extractedAt }) {
  const [open, setOpen] = useState(false);
  if (!evidence && !sourceUrl) return children;
  return (
    <span
      className="citation-trigger"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      {open && (
        <div className="citation-popover">
          {evidence && <p className="ev">"{evidence}"</p>}
          {sourceUrl && (
            <a className="src" href={sourceUrl} target="_blank" rel="noopener noreferrer">
              {sourceUrl}
            </a>
          )}
          {extractedAt && <span className="ts">extracted {fmtRelTime(extractedAt)}</span>}
        </div>
      )}
    </span>
  );
}

function ConfidenceDot({ level = "medium", sourceUrl, evidence, extractedAt }) {
  return (
    <CitationPopover evidence={evidence} sourceUrl={sourceUrl} extractedAt={extractedAt}>
      <span
        className={`confidence-dot confidence-dot--${level}`}
        title={`confidence: ${level}`}
        aria-label={`confidence ${level}`}
      />
    </CitationPopover>
  );
}

// ─── F2: Funding status empty-state pill ──────────────────────
// Renders nothing for status "enriched" — only used when rounds.length === 0.
function RowEmptyState({ status, founded }) {
  const COPY = {
    bootstrapped: { label: "Bootstrapped", hint: "No outside capital",    color: "var(--fg-3)" },
    stealth:      { label: "Stealth",      hint: founded ? `Founded ${founded}` : "Pre-launch", color: "#0ea5e9" },
    not_found:    { label: "No data",      hint: "Funding not disclosed", color: "var(--fg-4)" },
    pending:      { label: "Enriching…",   hint: "Lane 1 in progress",    color: "var(--accent, #ff5d00)" },
  };
  const c = COPY[status];
  if (!c) return null;
  return (
    <span style={{ fontSize: 10.5, color: c.color, fontFamily: "var(--font-mono)", display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{
        padding: "1px 6px", borderRadius: 3,
        border: `1px solid ${c.color}`,
        opacity: 0.95, fontWeight: 500, letterSpacing: 0.2,
      }}>{c.label}</span>
      <span style={{ color: "var(--fg-4)" }}>{c.hint}</span>
    </span>
  );
}

// Export to window for cross-script access
Object.assign(window, {
  fmtMoney, fmtNum, fmtPct, fmtDate, fmtRelTime, fmtFunding,
  Ic, Icons,
  Sidebar, Topbar, Tabs,
  LogoMark, ThreatTag, Bar, Sparkline, SectionH,
  countryFlag,
  ConfidenceDot, CitationPopover,
  RowEmptyState,
  MemoPrintReport,
});
