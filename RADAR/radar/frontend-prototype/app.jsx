// app.jsx — top-level wiring: workspace tabs + dynamic company tabs
const { useState: _uS_app, useEffect: _uE_app } = React;

const SCAN_TABS = [
  { key: "overview",    label: "Overview",    icon: "overview" },
  { key: "list",        label: "Competitors", icon: "list" },
  { key: "map",         label: "Map",         icon: "map" },
  { key: "positioning", label: "Positioning", icon: "compare" },
  { key: "timeline",    label: "Timeline",    icon: "timeline" },
  { key: "features",    label: "Features",    icon: "features", comingSoon: true },
  { key: "pricing",     label: "Pricing",     icon: "pricing",  comingSoon: true },
];

function App() {
  const [tweaks, setTweak] = useTweaks(window.RADAR_TWEAK_DEFAULTS);
  const [data, setData] = _uS_app(window.RADAR_DATA);
  const [view, setView] = _uS_app("new");
  const [isRescanning, setIsRescanning] = _uS_app(false);
  // 0 = full skeleton, 1 = subject loaded, 2 = all loaded
  const [loadingPhase, setLoadingPhase] = _uS_app(2);
  const [activeTab, setActiveTab] = _uS_app("overview");
  const [openCompanyIds, setOpenCompanyIds] = _uS_app([]);
  const [xopilotOpen, setXopilotOpen] = _uS_app(false);
  // Scan in progress: null | { url, domain, startedAt }
  const [scanInProgress, setScanInProgress] = _uS_app(null);

  _uE_app(() => {
    document.documentElement.setAttribute("data-density", tweaks.density);
  }, [tweaks.density]);

  const handleDelete = () => {
    setData(null);
    setView("home");
  };

  const handleRescan = () => {
    setIsRescanning(true);
    setTimeout(() => {
      setIsRescanning(false);
      setToast({ label: `Re-scan complete — ${data?.subject?.name}`, action: null });
    }, 10000);
  };

  const handleScanStart = (url) => {
    const domain = url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    setScanInProgress({ url, domain, startedAt: new Date().toISOString() });
    // Navigate immediately with skeletons — no need to sit on the scan animation
    setLoadingPhase(0);
    setView("current");
    setTimeout(() => setLoadingPhase(1), 1800);
    setTimeout(() => setLoadingPhase(2), 6800);
  };

  // Toast: null | { label, action }
  const [toast, setToast] = _uS_app(null);

  const handleScanComplete = (scanData) => {
    window.RADAR_DATA = scanData;
    setData(scanData);
    setScanInProgress(prev => prev ? { ...prev, done: true } : null);
    // User is already on the current view watching skeletons — nothing to do.
    // If they navigated away before skeletons finished, show a toast.
    if (view !== "current") {
      setToast({
        label: `Analysis ready — ${scanData.subject?.name || scanData.query?.name}`,
        action: () => { setView("current"); setToast(null); },
      });
    }
  };

  const [tabBeforeCompany, setTabBeforeCompany] = _uS_app("overview");

  const openCompany = (id) => {
    if (data && id === data.subject.id) return;
    setOpenCompanyIds(prev => prev.includes(id) ? prev : [...prev, id]);
    setTabBeforeCompany(activeTab.startsWith("company:") ? tabBeforeCompany : activeTab);
    setActiveTab("company:" + id);
  };

  const closeCompany = (id) => {
    setOpenCompanyIds(prev => {
      const next = prev.filter(x => x !== id);
      if (activeTab === "company:" + id) {
        const idx = prev.indexOf(id);
        const fallback = next[idx - 1] ? "company:" + next[idx - 1] : next[idx] ? "company:" + next[idx] : tabBeforeCompany;
        setActiveTab(fallback);
      }
      return next;
    });
  };

  // Build tab list: static + one tab per open company
  const companyTabs = openCompanyIds.map(id => {
    const all = data ? [data.subject, ...(data.competitors || [])] : [];
    const company = all.find(c => c.id === id);
    return {
      key: "company:" + id,
      label: company?.name || id,
      icon: null,
      onClose: () => closeCompany(id),
    };
  });
  const tabs = [
    ...SCAN_TABS.filter(t => !t.comingSoon),
    ...SCAN_TABS.filter(t =>  t.comingSoon),
    ...companyTabs,
  ];

  return (
    <div className={"app" + (xopilotOpen ? " xo-open" : "")} data-screen-label={
      view === "new"  ? "01 New scan" :
      view === "home" ? "02 Home"     :
                        "03 Current scan"
    }>
      <Sidebar
        view={view}
        onView={setView}
        currentSubjectName={data ? data.subject.name : null}
      />

      <div className="main">
        {/* Always mounted so scan timers survive tab switches */}
        <div style={{display: view === "new" ? "flex" : "none", flex:1, flexDirection:"column"}}>
          <SearchScreen
            onComplete={handleScanComplete}
            onScanStart={handleScanStart}
          />
        </div>

        {view === "home" && (
          <HomeScreen
            onOpenCurrent={() => setView("current")}
            onNewScan={() => setView("new")}
            scanInProgress={scanInProgress}
            showToast={(t) => setToast(t)}
          />
        )}

        {view === "current" && data && (
          <>
            <Topbar
              subject={data.subject}
              data={data}
              onDelete={handleDelete}
              onRescan={handleRescan}
              isRescanning={isRescanning}
            />
            <Tabs tabs={tabs} active={activeTab} onTab={setActiveTab}
              xopilotOpen={xopilotOpen} onXopilot={() => setXopilotOpen(v => !v)} />
            <div className="content">
              {activeTab === "overview"  && <OverviewScreen  data={data} onOpenCompany={openCompany} loadingPhase={loadingPhase} />}
              {activeTab === "list"      && <ListScreen      data={data} onOpenCompany={openCompany} />}
              {activeTab === "compare"   && <CompareScreen   data={data} onOpenCompany={openCompany} />}
              {activeTab === "map"         && <MapScreen         data={data} onOpenCompany={openCompany} />}
              {activeTab === "positioning" && <PositioningScreen data={data} onOpenCompany={openCompany} />}
              {activeTab === "features"  && <FeaturesScreen  data={data} onOpenCompany={openCompany} />}
              {activeTab === "pricing"   && <PricingScreen   data={data} onOpenCompany={openCompany} />}
              {activeTab === "timeline"  && <TimelineScreen  data={data} onOpenCompany={openCompany} />}
              {openCompanyIds.map(id => (
                activeTab === "company:" + id && (
                  <CompanyScreen key={id} data={data} companyId={id} onOpenCompany={openCompany} />
                )
              ))}
            </div>
          </>
        )}
      </div>

      <CopilotPanel
        open={xopilotOpen}
        onClose={() => setXopilotOpen(false)}
        data={data}
      />

      <RadarTweaksPanel t={tweaks} setTweak={setTweak} onJumpToSearch={() => setView("new")} />

      {toast && (
        <div style={{
          position:"fixed", bottom:24, right:24, zIndex:9999,
          display:"flex", alignItems:"center", gap:12,
          padding:"14px 16px",
          background:"var(--fg)", color:"var(--bg)",
          borderRadius:10, boxShadow:"0 4px 24px rgba(0,0,0,.18)",
          fontSize:13, fontWeight:500, maxWidth:340,
          animation:"toast-in .2s ease",
        }}>
          <span style={{flex:1}}>{toast.label}</span>
          {toast.action && (
            <button
              onClick={toast.action}
              style={{
                background:"var(--accent)", color:"#fff", border:"none",
                borderRadius:6, padding:"6px 12px", fontSize:12,
                fontWeight:600, cursor:"pointer", whiteSpace:"nowrap",
                fontFamily:"var(--font-sans)",
              }}
            >
              View →
            </button>
          )}
          <button
            onClick={() => setToast(null)}
            style={{
              background:"none", border:"none", color:"var(--bg)",
              opacity:.5, cursor:"pointer", fontSize:16, padding:"0 2px",
              lineHeight:1,
            }}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Tweaks Panel ─────────────────────────────────────────────────────────────
function RadarTweaksPanel({ t, setTweak, onJumpToSearch }) {
  return (
    <TweaksPanel>
      <TweakSection label="Display" />
      <TweakRadio label="Density" value={t.density} options={["compact", "comfortable"]}
        onChange={(v) => setTweak("density", v)} />
      <TweakSection label="Brand accent" />
      <TweakColor label="Subject highlight" value={t.accent}
        options={["#b34a1f", "#1f6b3d", "#1a3a6b", "#5a3d8a", "#0a0a0a"]}
        onChange={(v) => {
          setTweak("accent", v);
          const root = document.documentElement;
          root.style.setProperty("--accent", v);
          const map = {
            "#b34a1f": ["#c2541f", "#fdf2ea", "#f7e5d4", "#6b2811"],
            "#1f6b3d": ["#1f7547", "#eaf3ed", "#d4e7da", "#0e3a20"],
            "#1a3a6b": ["#1f4480", "#e9eef5", "#d3dcec", "#0e1f3a"],
            "#5a3d8a": ["#6b48a3", "#efe9f5", "#dcd0eb", "#2e1f47"],
            "#0a0a0a": ["#1a1a1a", "#efeeec", "#e0dfdc", "#000000"],
          };
          const [a2, bg, bg2, fg] = map[v] || map["#b34a1f"];
          root.style.setProperty("--accent-2", a2);
          root.style.setProperty("--accent-bg", bg);
          root.style.setProperty("--accent-bg-2", bg2);
          root.style.setProperty("--accent-fg", fg);
        }}
      />
      <TweakSection label="Navigation" />
      {onJumpToSearch && <TweakButton onClick={onJumpToSearch}>Re-run scan from URL</TweakButton>}
      <TweakSection label="About" />
      <div style={{ fontSize: 11, color: "var(--fg-3)", lineHeight: 1.5, padding: "0 2px" }}>
        Radar is a prototype for VC due-diligence competitive scans.
        Compact mode tightens the table density to investor-deck levels.
      </div>
    </TweaksPanel>
  );
}

// ─── Apply persisted accent on first render ───────────────────────────────────
(function applyInitialAccent() {
  const t = window.RADAR_TWEAK_DEFAULTS;
  const root = document.documentElement;
  const map = {
    "#b34a1f": ["#c2541f", "#fdf2ea", "#f7e5d4", "#6b2811"],
    "#1f6b3d": ["#1f7547", "#eaf3ed", "#d4e7da", "#0e3a20"],
    "#1a3a6b": ["#1f4480", "#e9eef5", "#d3dcec", "#0e1f3a"],
    "#5a3d8a": ["#6b48a3", "#efe9f5", "#dcd0eb", "#2e1f47"],
    "#0a0a0a": ["#1a1a1a", "#efeeec", "#e0dfdc", "#000000"],
  };
  if (t.accent && map[t.accent]) {
    root.style.setProperty("--accent", t.accent);
    const [a2, bg, bg2, fg] = map[t.accent];
    root.style.setProperty("--accent-2", a2);
    root.style.setProperty("--accent-bg", bg);
    root.style.setProperty("--accent-bg-2", bg2);
    root.style.setProperty("--accent-fg", fg);
  }
  root.setAttribute("data-density", t.density || "comfortable");
})();

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
