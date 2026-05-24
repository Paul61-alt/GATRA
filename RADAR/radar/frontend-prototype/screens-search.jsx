// screens-search.jsx — URL input + real /scan API call with animated UI
const { useState: _uS_search, useEffect: _uE_search } = React;

function SearchScreen({ onComplete }) {
  const [phase, setPhase] = _uS_search("input"); // input | scanning
  const [url, setUrl] = _uS_search("");
  const [step, setStep] = _uS_search(0);
  const [foundCount, setFoundCount] = _uS_search(0);
  const [sources, setSources] = _uS_search(0);
  const [error, setError] = _uS_search(null);

  const SCAN_STEPS = [
    { label: "Resolving target",           detail: "DNS + HTTP handshake" },
    { label: "Reading homepage + sitemap",  detail: "Extracting product surface" },
    { label: "Inferring category",          detail: "Market classification" },
    { label: "Searching market corpus",     detail: "1,200+ sources scanned" },
    { label: "Ranking competitors",         detail: "Similarity scoring" },
    { label: "Hydrating profiles",          detail: "Funding · pricing · features" },
    { label: "Building radar matrix",       detail: "6 dimensions × N companies" },
  ];

  // Animate sources counter while scanning (step driven by real SSE events)
  _uE_search(() => {
    if (phase !== "scanning") return;
    let cancelled = false;
    const tick = setInterval(() => {
      if (cancelled) return;
      setSources(s => Math.min(1247, s + Math.floor(20 + Math.random() * 80)));
    }, 220);
    return () => { cancelled = true; clearInterval(tick); };
  }, [phase]);

  const PHASE_STEP = {
    "UNDERSTAND:start": 0,
    "UNDERSTAND:ok":    2,
    "DISCOVER:start":   3,
    "DISCOVER:ok":      4,
    "ENRICH:start":     5,
    "ENRICH:ok":        6,
  };

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const start = async () => {
    if (!url.trim()) return;
    setStep(0); setSources(0); setFoundCount(0); setError(null);
    setPhase("scanning");

    const result = window.RADAR_DATA;
    if (!result) {
      setError("No cached data found — add a scan result to data.js first.");
      setPhase("input");
      return;
    }

    // Simulate SSE phase events with realistic delays
    const emit = async (phase, status, extra) => {
      const key = `${phase}:${status}`;
      if (key in PHASE_STEP) setStep(PHASE_STEP[key]);
      if (key === "DISCOVER:ok") setFoundCount(extra?.count ?? (result.competitors?.length || 0));
    };

    await emit("UNDERSTAND", "start");
    await sleep(1500);
    await emit("UNDERSTAND", "ok");
    await sleep(1500);
    await emit("DISCOVER", "start");
    await sleep(1200);
    await emit("DISCOVER", "ok");
    await sleep(2000);
    await emit("ENRICH", "start");
    await sleep(2000);
    await emit("ENRICH", "ok");
    await sleep(600);

    if (!result.allCompanies) {
      const subject = result.subject ? [result.subject] : [];
      const competitors = (result.competitors || []).slice().sort(
        (a, b) => (b.similarity || 0) - (a.similarity || 0)
      );
      result.allCompanies = [...subject, ...competitors];
    }
    onComplete(result);
  };

  // ——— Input phase ————————————————————————————————
  if (phase === "input") {
    return (
      <div style={{flex:1, display:"grid", placeItems:"center", padding:"56px 32px", background:"var(--bg)"}}>
        <div style={{width:"min(540px, 92vw)"}}>
          <div className="mono" style={{fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", color:"var(--fg-4)", marginBottom:14}}>
            New scan
          </div>
          <h1 className="serif" style={{
            fontSize: 38, fontWeight: 500, letterSpacing: "-0.02em",
            margin: "0 0 14px", lineHeight: 1.1
          }}>
            Find every competitor of any company.
          </h1>
          <p style={{color:"var(--fg-3)", fontSize:14, marginTop:0, marginBottom: 28}}>
            Paste a URL. Radar reads the product, scans 1,200+ sources,
            and returns a ranked competitive set with funding, features, pricing and geography.
          </p>

          {error && (
            <div style={{
              padding: "10px 14px", marginBottom: 16, borderRadius: 6,
              background: "var(--negative-bg, #fdf2f2)", border: "1px solid var(--negative, #c0392b)",
              color: "var(--negative, #c0392b)", fontSize: 12, fontFamily: "var(--font-mono)",
            }}>
              {error}
            </div>
          )}

          <div style={{
            display:"flex", alignItems:"center", gap: 0,
            border: "1px solid var(--border-strong)",
            borderRadius: 8, background: "var(--surface)",
            boxShadow: "var(--shadow-sm)",
            overflow: "hidden",
          }}>
            <span style={{padding:"0 12px", color:"var(--fg-4)"}}>{Icons.link}</span>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && start()}
              placeholder="linq.io"
              style={{
                flex:1, border:"none", outline:"none", background:"transparent",
                padding: "14px 0", fontSize: 15, fontFamily: "var(--font-mono)",
                color: "var(--fg)",
              }}/>
            <button className="tb-btn primary"
                    onClick={start}
                    style={{margin:6, padding: "8px 14px"}}>
              Run scan {Icons.arrowR}
            </button>
          </div>

          <div style={{marginTop:24, display:"flex", gap:8, flexWrap:"wrap"}}>
            <span className="muted" style={{fontSize:11.5, marginRight:4}}>Try:</span>
            {["linq.io", "vex.finance", "modern-treasury.com"].map(s => (
              <span key={s} className="tag mono" onClick={() => setUrl(s)}
                    style={{cursor:"pointer"}}>{s}</span>
            ))}
          </div>

          <div style={{marginTop: 56, display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap: 14}}>
            {[
              { k: "Sources scanned",   v: "1,200+",  d: "Crunchbase · Pitchbook · LinkedIn · G2 · public web" },
              { k: "Avg. scan time",    v: "~60s",    d: "Parallel agentic search via Linkup" },
              { k: "Pipeline phases",   v: "3",       d: "Understand → Discover → Enrich" },
            ].map(s => (
              <div key={s.k}>
                <div className="mono" style={{fontSize:10, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--fg-4)"}}>{s.k}</div>
                <div className="serif" style={{fontSize:22, fontWeight:500, marginTop:2, letterSpacing:"-0.02em"}}>{s.v}</div>
                <div style={{fontSize:11, color:"var(--fg-3)", marginTop:2}}>{s.d}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ——— Scanning phase ————————————————————————————————
  return (
    <div style={{flex:1, display:"grid", placeItems:"center", padding:"56px 32px", background:"var(--bg)"}}>
      <div style={{width:"min(620px, 92vw)"}}>
        <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:14}}>
          <span className="mono" style={{fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", color:"var(--fg-4)"}}>New scan</span>
          <div style={{flex:1}}></div>
          <span className="tag subject mono" style={{fontSize:10}}>SCANNING</span>
        </div>

        <h1 className="serif" style={{fontSize:24, fontWeight:500, margin:"0 0 4px", letterSpacing:"-0.01em"}}>
          Mapping the competitive set for <span style={{color:"var(--accent)"}}>{url}</span>
        </h1>
        <p style={{color:"var(--fg-3)", fontSize:13, marginTop:0, marginBottom:28}}>
          Don't refresh — this takes ~60 seconds across 1,200+ sources.
        </p>

        {/* Scan steps */}
        <div className="card" style={{padding: 0}}>
          <div className="card-h">
            <h3>Scan trace</h3>
            <span className="meta">Step {step + 1} / {SCAN_STEPS.length}</span>
          </div>
          <div style={{padding: "8px 0"}}>
            {SCAN_STEPS.map((s, i) => {
              const state = i < step ? "done" : i === step ? "active" : "pending";
              return (
                <div key={i} style={{
                  display:"flex", alignItems:"center", gap:12,
                  padding:"7px 16px", fontSize:12.5,
                  opacity: state === "pending" ? 0.45 : 1,
                  transition: "opacity .25s",
                }}>
                  <div style={{width:14,height:14,display:"grid",placeItems:"center"}}>
                    {state === "done" && (
                      <span style={{color:"var(--positive)"}}>{Icons.check}</span>
                    )}
                    {state === "active" && (
                      <span className="dot-pulse" style={{transform:"scale(.85)"}}><i></i><i></i><i></i></span>
                    )}
                    {state === "pending" && (
                      <span className="dim">{Icons.minus}</span>
                    )}
                  </div>
                  <div style={{flex:1, color: state === "active" ? "var(--fg)" : "var(--fg-2)"}}>
                    {s.label}
                  </div>
                  <div className="mono" style={{fontSize:11, color: state === "pending" ? "var(--fg-4)" : "var(--fg-3)"}}>
                    {state === "pending" ? "—" : s.detail}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live counters */}
        <div style={{display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap: 12, marginTop: 12}}>
          <div className="card" style={{padding: "12px 14px"}}>
            <div className="mono" style={{fontSize:10, letterSpacing:"0.08em", color:"var(--fg-4)", textTransform:"uppercase"}}>Sources</div>
            <div className="serif" style={{fontSize:22, fontWeight:500, letterSpacing:"-0.02em"}}>{sources.toLocaleString()}</div>
          </div>
          <div className="card" style={{padding: "12px 14px"}}>
            <div className="mono" style={{fontSize:10, letterSpacing:"0.08em", color:"var(--fg-4)", textTransform:"uppercase"}}>Competitors found</div>
            <div className="serif" style={{fontSize:22, fontWeight:500, letterSpacing:"-0.02em", color: foundCount > 0 ? "var(--accent)" : "var(--fg)"}}>{foundCount}</div>
          </div>
          <div className="card" style={{padding: "12px 14px"}}>
            <div className="mono" style={{fontSize:10, letterSpacing:"0.08em", color:"var(--fg-4)", textTransform:"uppercase"}}>Elapsed</div>
            <div className="serif mono" style={{fontSize:22, fontWeight:500, letterSpacing:"-0.02em"}}>
              <ElapsedTimer />
            </div>
          </div>
        </div>

        <button className="tb-btn"
                onClick={() => setPhase("input")}
                style={{marginTop:16, color:"var(--fg-3)"}}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function ElapsedTimer() {
  const [t, setT] = _uS_search(0);
  _uE_search(() => {
    const start = Date.now();
    const id = setInterval(() => setT((Date.now() - start) / 1000), 100);
    return () => clearInterval(id);
  }, []);
  return <span>{t.toFixed(1)}s</span>;
}

window.SearchScreen = SearchScreen;
