// app.jsx — top-level wiring: workspace tabs + dynamic company tabs
const { useState: _uS_app, useEffect: _uE_app } = React;

const SCAN_TABS = [
  { key: "overview",  label: "Overview",    icon: "overview" },
  { key: "list",      label: "Competitors", icon: "list",    count: 8 },
  { key: "compare",   label: "Compare",     icon: "compare" },
  { key: "map",       label: "Map",         icon: "map" },
  { key: "features",  label: "Features",    icon: "features" },
  { key: "pricing",   label: "Pricing",     icon: "pricing" },
  { key: "timeline",  label: "Timeline",    icon: "timeline" },
];

function App() {
  const [tweaks, setTweak] = useTweaks(window.RADAR_TWEAK_DEFAULTS);
  const [data, setData] = _uS_app(window.RADAR_DATA);
  const [view, setView] = _uS_app("new");
  const [activeTab, setActiveTab] = _uS_app("overview");
  // Array of company IDs with open tabs (preserves order)
  const [openCompanyIds, setOpenCompanyIds] = _uS_app([]);

  _uE_app(() => {
    document.documentElement.setAttribute("data-density", tweaks.density);
  }, [tweaks.density]);

  const handleScanComplete = (scanData) => {
    window.RADAR_DATA = scanData;
    setData(scanData);
    setView("current");
  };

  const openCompany = (id) => {
    setOpenCompanyIds(prev => prev.includes(id) ? prev : [...prev, id]);
    setActiveTab("company:" + id);
  };

  const closeCompany = (id) => {
    setOpenCompanyIds(prev => {
      const next = prev.filter(x => x !== id);
      // If closing the active tab, move to the previous company tab or "list"
      if (activeTab === "company:" + id) {
        const idx = prev.indexOf(id);
        const fallback = next[idx - 1] ? "company:" + next[idx - 1] : next[idx] ? "company:" + next[idx] : "list";
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
  const tabs = [...SCAN_TABS, ...companyTabs];

  return (
    <div className="app" data-screen-label={
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
        {view === "new" && <SearchScreen onComplete={handleScanComplete} />}

        {view === "home" && (
          <HomeScreen
            onOpenCurrent={() => setView("current")}
            onNewScan={() => setView("new")}
          />
        )}

        {view === "current" && data && (
          <>
            <Topbar subject={data.subject} />
            <Tabs tabs={tabs} active={activeTab} onTab={setActiveTab} />
            <div className="content">
              {activeTab === "overview"  && <OverviewScreen  data={data} onOpenCompany={openCompany} />}
              {activeTab === "list"      && <ListScreen      data={data} onOpenCompany={openCompany} />}
              {activeTab === "compare"   && <CompareScreen   data={data} onOpenCompany={openCompany} />}
              {activeTab === "map"       && <MapScreen       data={data} onOpenCompany={openCompany} />}
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

      <RadarTweaksPanel t={tweaks} setTweak={setTweak} onJumpToSearch={() => setView("new")} />
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
