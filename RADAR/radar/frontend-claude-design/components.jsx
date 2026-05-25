// components.jsx â shared UI primitives for Radar
// Exported via window globals at the bottom.

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// âââ Utility ââââââââââââââââââââââââââââââââââââââââââââââââââ
const fmtMoney = (n) => {
  if (n == null) return "â";
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(0) + "k";
  return "$" + n;
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
};

// âââ Sidebar ââââââââââââââââââââââââââââââââââââââââââââââââââ
function Sidebar({ view, onView, currentSubjectName }) {
  const items = [
    { key: "new",     label: "New scan",     icon: "zap" },
    { key: "home",    label: "Home",         icon: "list", meta: "12" },
    { key: "current", label: "Current scan", icon: "overview", meta: currentSubjectName || null },
  ];
  return (
    <aside className="sb">
      <div className="sb-brand">
        <div className="sb-logo">R</div>
        <div className="sb-name">Radar<small>v0.4</small></div>
      </div>

      <div style={{padding: "10px 12px"}}>
        <button className="tb-btn" style={{width:"100%", justifyContent:"flex-start", color:"var(--fg-3)"}}>
          {Icons.search}
          <span>Quick search</span>
          <span style={{marginLeft:"auto"}} className="kbd">âK</span>
        </button>
      </div>

      <div className="sb-sect">Workspace</div>
      {items.map(it => (
        <div key={it.key}
             className={"sb-item " + (view === it.key ? "active" : "")}
             onClick={() => onView(it.key)}>
          <span className="ic">{Icons[it.icon]}</span>
          <span>{it.label}</span>
          {it.meta && (
            <span className={it.key === "current" ? "sb-meta-name" : "kbd"}>
              {it.meta}
            </span>
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
function Topbar({ subject }) {
  return (
    <header className="tb">
      <div className="tb-crumbs">
        <span>Scans</span>
        <span className="sep">/</span>
        <b>{subject.name}</b>
        <span className="sep">Â·</span>
        <span className="mono" style={{fontSize:11.5}}>{subject.domain}</span>
        <span className="tb-pill">SUBJECT</span>
      </div>
      <div className="tb-spacer"></div>
      <button className="tb-btn">{Icons.bell}</button>
      <button className="tb-btn">{Icons.share}<span>Share</span></button>
      <button className="tb-btn">{Icons.download}<span>Export</span></button>
      <button className="tb-btn primary">{Icons.zap}<span>Re-scan</span></button>
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
          <span style={{width:14,height:14,display:"inline-grid",placeItems:"center"}}>{Icons[t.icon]}</span>
          <span>{t.label}</span>
          {t.count != null && <span className="count mono">{t.count}</span>}
        </div>
      ))}
    </nav>
  );
}

// âââ Logo placeholder âââââââââââââââââââââââââââââââââââââââââ
function LogoMark({ name, subject = false, size = "md" }) {
  const cls = "logo-mark " + (subject ? "subject " : "") + size;
  // Take first letter of company name, first letter of second word too if exists
  const parts = name.split(/\s+/);
  let label = parts[0][0];
  if (parts.length > 1) label += parts[1][0];
  // For single-word names with dots ("Settle.work") just first char
  return <div className={cls}>{label.toUpperCase()}</div>;
}

// âââ Threat tag âââââââââââââââââââââââââââââââââââââââââââââââ
function ThreatTag({ level }) {
  const labels = { high: "HIGH THREAT", medium: "MEDIUM", low: "LOW" };
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

// Export to window for cross-script access
Object.assign(window, {
  fmtMoney, fmtNum, fmtPct, fmtDate,
  Ic, Icons,
  Sidebar, Topbar, Tabs,
  LogoMark, ThreatTag, Bar, Sparkline, SectionH,
});
