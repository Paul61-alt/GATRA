// app.jsx — top-level wiring: workspace tabs + dynamic company tabs
const { useState: _uS_app, useEffect: _uE_app, useRef: _uR_app } = React;

// ─── localStorage helpers for refresh-recovery of an in-flight scan ───────────
const ACTIVE_SCAN_KEY = "radar:activeScan";

function _readActiveScan() {
  try {
    const raw = localStorage.getItem(ACTIVE_SCAN_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function _writeActiveScan(scan) {
  try { localStorage.setItem(ACTIVE_SCAN_KEY, JSON.stringify(scan)); } catch {}
}

function _clearActiveScan() {
  try { localStorage.removeItem(ACTIVE_SCAN_KEY); } catch {}
}

// ─── PasswordGate ────────────────────────────────────────────────────────────
// Wraps <App/>. If no token in localStorage, renders a single-input form. On
// submit, stores token + re-renders children. Backend rejects with 401 if the
// token doesn't match RADAR_SHARED_TOKEN — caller can clear token + retry.
function PasswordGate({ children }) {
  const [hasToken, setHasToken] = _uS_app(!!window.radarGetToken());
  const [input, setInput] = _uS_app("");

  if (hasToken) return children;

  function submit(e) {
    e.preventDefault();
    const t = input.trim();
    if (!t) return;
    window.radarSetToken(t);
    setHasToken(true);
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "var(--bg, #faf8f5)",
      fontFamily: "Roboto, system-ui, sans-serif",
    }}>
      <form onSubmit={submit} style={{
        display: "flex", flexDirection: "column", gap: 16,
        padding: 32, borderRadius: 12, background: "white",
        boxShadow: "0 4px 24px rgba(0,0,0,0.08)", width: 360, maxWidth: "90vw",
      }}>
        <div style={{ fontSize: 20, fontWeight: 600, color: "#0a0a0a" }}>Radar — Access</div>
        <div style={{ fontSize: 13, color: "#666", lineHeight: 1.4 }}>
          Enter the shared access token to use this demo. Reach out for credentials.
        </div>
        <input
          type="password"
          autoFocus
          placeholder="Access token"
          value={input}
          onChange={e => setInput(e.target.value)}
          style={{
            padding: "10px 12px", fontSize: 14, border: "1px solid #ddd",
            borderRadius: 6, outline: "none", fontFamily: "Roboto Mono, monospace",
          }}
        />
        <button type="submit" style={{
          padding: "10px 16px", fontSize: 14, fontWeight: 500,
          background: "#b34a1f", color: "white", border: "none",
          borderRadius: 6, cursor: "pointer",
        }}>Enter</button>
      </form>
    </div>
  );
}

const SCAN_TABS = [
  { key: "overview",  label: "Overview",    icon: "overview" },
  { key: "list",      label: "Competitors", icon: "list" },
  // { key: "compare",   label: "Compare",     icon: "compare" },   // hidden
  { key: "map",       label: "Map",         icon: "map" },
  { key: "positioning", label: "Positioning", icon: "compare" },
  // { key: "features",  label: "Features",    icon: "features" },  // hidden
  { key: "pricing",   label: "Pricing",     icon: "pricing" },
  { key: "timeline",  label: "Timeline",    icon: "timeline" },
  { key: "memo",      label: "Mémo",        icon: "memo" },
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
  // Scan in progress: null | { url, domain, startedAt }
  const [scanInProgress, setScanInProgress] = _uS_app(null);
  // HITL: result of /scan/discover, fed to SelectScreen
  const [discoverResult, setDiscoverResult] = _uS_app(null);

  // Minimum time the full-screen scanning loader stays up before we flip to the
  // dashboard. A floor, never a cap: if DISCOVER takes longer we transition when
  // it lands. Keeps the user on the loader for at least this long.
  const SCAN_MIN_LOADING_MS = 20000;
  const scanStartMsRef = _uR_app(0);
  const floorTimerRef = _uR_app(null);

  // Skeleton staging: show full skeleton, then reveal the subject frame after a beat.
  // Held in a ref so we can cancel a pending reveal if the scan bounces back to "new".
  const phaseTimerRef = _uR_app(null);
  const stageSubject = () => {
    setLoadingPhase(0);
    if (phaseTimerRef.current) clearTimeout(phaseTimerRef.current);
    phaseTimerRef.current = setTimeout(() => setLoadingPhase(1), 1800);
  };
  const cancelStage = () => {
    if (phaseTimerRef.current) { clearTimeout(phaseTimerRef.current); phaseTimerRef.current = null; }
    if (floorTimerRef.current) { clearTimeout(floorTimerRef.current); floorTimerRef.current = null; }
  };

  // Flip from the full-screen scanning loader to the dashboard (Overview tab) and
  // begin skeleton staging. Single entry point so the loader floor controls timing.
  const transitionToDashboard = () => {
    if (floorTimerRef.current) { clearTimeout(floorTimerRef.current); floorTimerRef.current = null; }
    setActiveTab("overview");
    setView("current");
    if (!data) stageSubject();
  };

  // True once the scan has been on the loader for at least the floor duration.
  const floorElapsed = () =>
    scanStartMsRef.current > 0 && (Date.now() - scanStartMsRef.current) >= SCAN_MIN_LOADING_MS;

  _uE_app(() => {
    document.documentElement.setAttribute("data-density", tweaks.density);
  }, [tweaks.density]);

  // ─── Refresh recovery: on mount, restore any in-flight scan from localStorage ─
  // Runs once. Reads the saved {runId, url, domain, phase} → calls /scan/status
  // → either hydrates the final result, restores in-progress UI + polls, or
  // shows an "expired" toast and clears the entry.
  _uE_app(() => {
    const saved = _readActiveScan();
    if (!saved || !saved.runId) return;

    (async () => {
      let resp;
      try {
        resp = await fetch(`${window.RADAR_API}/scan/status/${saved.runId}`);
      } catch {
        return;  // network error on cold open — keep entry, user can retry
      }
      if (resp.status === 404) {
        _clearActiveScan();
        setToast({ label: `Scan expiré pour ${saved.domain} — relance.`, action: null });
        return;
      }
      if (!resp.ok) return;
      const status = await resp.json();

      // Final result available → hydrate straight to current view.
      if (status.result) {
        window.RADAR_DATA = status.result;
        setData(status.result);
        setLoadingPhase(2);
        setView("current");
        _clearActiveScan();
        return;
      }
      // Hard error → clear + toast.
      if (status.status === "error") {
        _clearActiveScan();
        setToast({ label: `Scan failed: ${status.error || "unknown"}`, action: null });
        return;
      }
      // Still running — show the skeleton current view (covers all phases uniformly)
      // and poll /scan/status until either result/error or DISCOVER ok (→ enrich).
      setScanInProgress({
        url: saved.url, domain: saved.domain, runId: saved.runId, startedAt: saved.startedAt,
      });
      setView("current");
      stageSubject();
      pollScanStatus(saved.runId);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = () => {
    setData(null);
    setView("home");
  };

  // Open a saved scan from Home/history: fetch the full RadarOutput for that
  // domain from the backend, then show it. Without this the app would render
  // whatever `data` is already in memory (e.g. the bundled data.js demo blob),
  // so every history click looked like the same wrong company.
  const handleOpenScan = async (scan) => {
    const domain = scan?.domain;
    if (!domain) { setView("current"); return; }
    let resp;
    try {
      resp = await fetch(`${window.RADAR_API}/scans/${encodeURIComponent(domain)}/latest`);
    } catch (err) {
      setToast({ label: `Chargement échoué (réseau) pour ${domain}`, action: null });
      return;
    }
    if (!resp.ok) {
      setToast({
        label: resp.status === 404
          ? `Aucun scan enregistré pour ${domain}.`
          : `Chargement échoué ${resp.status} pour ${domain}.`,
        action: null,
      });
      return;
    }
    const full = await resp.json();
    window.RADAR_DATA = full;
    setData(full);
    setLoadingPhase(2);
    setActiveTab("overview");
    setOpenCompanyIds([]);
    setView("current");
  };

  // Resume loading view from Home when user clicks the in-flight scan row.
  // If no prior data, synth a stub so OverviewScreen can render skeletons.
  const handleResumeLoading = () => {
    setView("current");
  };

  const handleRescan = () => {
    setIsRescanning(true);
    setTimeout(() => {
      setIsRescanning(false);
      setToast({ label: `Re-scan complete — ${data?.subject?.name}`, action: null });
    }, 10000);
  };

  const handleScanStart = (url, runId) => {
    const domain = url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    const startedAt = new Date().toISOString();
    // Clear any residual data (demo blob or a previous scan) so it can never leak
    // into the new scan's dashboard while skeletons/enrich load.
    setData(null);
    scanStartMsRef.current = Date.now();
    setScanInProgress({ url, domain, runId, startedAt });
    _writeActiveScan({ runId, url, domain, phase: "DISCOVER", startedAt });
    // Stay on the full-screen scanning loader (view stays "new"). The dashboard
    // is shown later via transitionToDashboard once the loading floor passes —
    // see handleDiscoverComplete / handleEnrichComplete.
    setActiveTab("overview");
  };

  // Tear down all in-flight scan state and return to the New/loader screen.
  // Clears the floor timer (so it can't flip to an empty dashboard), stops any
  // poller, and drops scanInProgress — which re-arms SearchScreen's URL form via
  // its `active` effect. Used by cancel and every enrich/poll error path.
  const failScan = (label) => {
    cancelStage();
    pollAbortRef.current.stop = true;
    scanStartMsRef.current = 0;
    setScanInProgress(null);
    _clearActiveScan();
    if (label) setToast({ label, action: null });
    setView("new");
  };

  // User clicked Cancel on the scanning loader. SearchScreen already aborted its
  // own fetch; just tear down app-side state (no toast).
  const handleScanCancel = () => failScan(null);

  // Auto-enrich: DISCOVER finished → pick top 10 by threat_score and trigger enrich
  // (Candidates are already sorted by threat_score desc in backend discover.py.)
  const handleDiscoverComplete = (result) => {
    const candidates = result?.candidates || [];
    const topDomains = candidates.slice(0, Math.min(10, candidates.length)).map(c => c.domain);

    if (topDomains.length === 0) {
      failScan("No competitors found — try another URL");
      return;
    }

    setDiscoverResult(result);
    // Bump localStorage phase so refresh recovery knows we're past DISCOVER
    const prior = _readActiveScan();
    if (prior) _writeActiveScan({ ...prior, phase: "ENRICH", runId: result.runId, domain: result.companyDomain });
    runEnrich(result.runId, topDomains);
    // Loader floor: keep the scanning screen up until SCAN_MIN_LOADING_MS has
    // elapsed, then flip to the dashboard. Subject + competitors fill in there
    // progressively as ENRICH streams. The floor is a minimum, never a cap.
    if (floorElapsed()) {
      transitionToDashboard();
    } else {
      const remaining = SCAN_MIN_LOADING_MS - (Date.now() - scanStartMsRef.current);
      floorTimerRef.current = setTimeout(transitionToDashboard, Math.max(0, remaining));
    }
  };

  // Auto-enrich SSE consumer: POST /scan/enrich and stream until result/error.
  const runEnrich = async (runId, selectedDomains) => {
    let resp;
    try {
      resp = await fetch(`${window.RADAR_API}/scan/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, selected: selectedDomains }),
      });
    } catch (err) {
      failScan(`Enrich failed (network): ${err.message || err}`);
      return;
    }

    if (!resp.ok) {
      const txt = await resp.text();
      // 409 = a pipeline is already running for this run_id (e.g. duplicate from refresh
      // race). Fall back to polling /scan/status — the in-flight pipeline writes there.
      if (resp.status === 409) {
        pollScanStatus(runId);
        return;
      }
      const msg = resp.status === 404
        ? "Session expirée. Relance un scan."
        : `Enrich failed ${resp.status}: ${txt.slice(0, 200)}`;
      failScan(msg);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop();
      for (const evt of events) {
        const dataLine = evt.split("\n").find(l => l.startsWith("data: "));
        if (!dataLine) continue;
        let payload;
        try { payload = JSON.parse(dataLine.slice(6)); } catch { continue; }
        if (payload.result) {
          handleEnrichComplete(payload.result);
          return;
        }
        if (payload.error) {
          failScan(`Enrich error: ${payload.error}`);
          return;
        }
      }
    }
  };

  // ─── Refresh recovery: poll /scan/status until result/error/expired ──────────
  // Used after a refresh (mount-time restore) and as fallback when /scan/enrich
  // returns 409 (pipeline already running server-side).
  const pollAbortRef = _uR_app({ stop: false });

  const pollScanStatus = async (runId) => {
    pollAbortRef.current.stop = false;
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    let consecutive404 = 0;
    while (!pollAbortRef.current.stop) {
      let resp;
      try {
        resp = await fetch(`${window.RADAR_API}/scan/status/${runId}`);
      } catch (err) {
        await sleep(2000);
        continue;
      }
      if (resp.status === 404) {
        consecutive404 += 1;
        if (consecutive404 >= 2) {
          failScan("Scan expiré — relance une analyse.");
          return;
        }
        await sleep(2000);
        continue;
      }
      consecutive404 = 0;
      if (!resp.ok) {
        await sleep(2000);
        continue;
      }
      const status = await resp.json();
      if (status.result) {
        handleEnrichComplete(status.result);
        return;
      }
      if (status.status === "error") {
        failScan(`Scan failed: ${status.error || "unknown error"}`);
        return;
      }
      // DISCOVER finished but enrich hasn't been kicked off yet (client refreshed
      // between phases) → trigger it now. handleDiscoverComplete will re-POST
      // /scan/enrich; if a pipeline is still running server-side the 409 path
      // will resume polling here.
      if (status.phase === "DISCOVER" && status.status === "ok" && status.discoverResult) {
        pollAbortRef.current.stop = true;
        handleDiscoverComplete(status.discoverResult);
        return;
      }
      await sleep(2000);
    }
  };

  // HITL: ENRICH+SYNTHESIZE stream finished — load full data. Only flip to the
  // dashboard if the loading floor already passed; otherwise the pending floor
  // timer (armed in handleDiscoverComplete) flips us over with the data in place.
  const handleEnrichComplete = (radarOutput) => {
    window.RADAR_DATA = radarOutput;
    setData(radarOutput);
    setDiscoverResult(null);
    setLoadingPhase(2);
    setScanInProgress(prev => prev ? { ...prev, done: true } : null);
    if (floorElapsed()) {
      if (floorTimerRef.current) { clearTimeout(floorTimerRef.current); floorTimerRef.current = null; }
      setActiveTab("overview");
      setView("current");
    }
    _clearActiveScan();
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
      view === "new"    ? "01 New scan" :
      view === "home"   ? "02 Home"     :
                          "03 Current scan"
    }>
      <Sidebar
        view={view}
        onView={setView}
        hasCurrent={!!(data || scanInProgress)}
        currentSubjectName={
          scanInProgress && !scanInProgress.done
            ? scanInProgress.domain
            : data?.subject?.name || null
        }
      />

      <div className="main">
        {/* Always mounted so scan timers survive tab switches */}
        <div style={{display: view === "new" ? "flex" : "none", flex:1, flexDirection:"column"}}>
          <SearchScreen
            active={!!scanInProgress}
            onComplete={handleScanComplete}
            onScanStart={handleScanStart}
            onDiscoverComplete={handleDiscoverComplete}
            onCancel={handleScanCancel}
          />
        </div>

        {view === "home" && (
          <HomeScreen
            onOpenCurrent={handleOpenScan}
            onResumeLoading={handleResumeLoading}
            onNewScan={() => setView("new")}
            scanInProgress={scanInProgress}
            showToast={(t) => setToast(t)}
          />
        )}

        {view === "current" && (() => {
          // Build stub data when scan in progress and we have no prior payload.
          // Lets OverviewScreen render skeletons under loadingPhase < 2.
          const displayData = data || (scanInProgress ? {
            subject: {
              name: scanInProgress.domain,
              domain: scanInProgress.domain,
              tagline: "",
              category: "",
              subCategory: "",
              hq: "",
              founded: "",
              employees: 0,
              funding: { total: 0, lastRound: "" },
              notable: [],
            },
            competitors: [],
            query: { name: scanInProgress.domain, scannedAt: scanInProgress.startedAt },
          } : null);
          if (!displayData) return null;
          return (
          <>
            <Topbar
              subject={displayData.subject}
              data={displayData}
              onDelete={handleDelete}
              onRescan={handleRescan}
              isRescanning={isRescanning}
            />
            <Tabs tabs={tabs} active={activeTab} onTab={setActiveTab} />
            <div className="content">
              {activeTab === "overview"  && <OverviewScreenV2 data={displayData} onOpenCompany={openCompany} loadingPhase={loadingPhase} />}
              {activeTab === "list"      && <ListScreen      data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "compare"   && <CompareScreen   data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "map"         && <MapScreen         data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "positioning" && <PositioningScreen data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "features"  && <FeaturesScreen  data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "pricing"   && <PricingScreen   data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "timeline"  && <TimelineScreen  data={displayData} onOpenCompany={openCompany} />}
              {activeTab === "memo"      && <MemoScreen      data={displayData} />}
              {openCompanyIds.map(id => (
                activeTab === "company:" + id && (
                  <CompanyScreen key={id} data={displayData} companyId={id} onOpenCompany={openCompany} />
                )
              ))}
            </div>
          </>
          );
        })()}
      </div>

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

ReactDOM.createRoot(document.getElementById("root")).render(
  <PasswordGate><App/></PasswordGate>
);
