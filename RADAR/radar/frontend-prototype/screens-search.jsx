// screens-search.jsx — URL input + real /scan API call with animated UI
const { useState: _uS_search, useEffect: _uE_search } = React;

const LinkupLogo = ({ size = 16 }) => (
  <img
    src="https://www.google.com/s2/favicons?domain=linkup.so&sz=32"
    width={size}
    height={size}
    alt="Linkup"
    style={{
      display: "inline-block",
      verticalAlign: "middle",
      borderRadius: 3,
    }}
  />
);

function isValidUrl(value) {
  const v = value.trim();
  if (!v) return false;
  // Accept with or without protocol, but must have a dot (TLD) and no spaces
  const withProtocol =
    v.startsWith("http://") || v.startsWith("https://") ? v : "https://" + v;
  try {
    const u = new URL(withProtocol);
    // Must have a hostname with a dot (e.g. example.com, not just "Notion")
    return u.hostname.includes(".") && !u.hostname.startsWith(".");
  } catch {
    return false;
  }
}

function SearchScreen({ active, onComplete, onScanStart, onDiscoverComplete, onCancel }) {
  const [phase, setPhase] = _uS_search("input");
  const [url, setUrl] = _uS_search("");
  const [urlError, setUrlError] = _uS_search(null);
  const [step, setStep] = _uS_search(0);
  const [foundCount, setFoundCount] = _uS_search(0);
  const [sources, setSources] = _uS_search(0);
  const [error, setError] = _uS_search(null);

  // The scanning loader stays up while a scan is in flight (the app owns the
  // hand-off to the dashboard via `view`). Once the app clears the in-flight
  // scan (complete / error / cancel), re-arm the URL form here.
  _uE_search(() => {
    if (!active && phase === "scanning") {
      setPhase("input");
      setUrl("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const SCAN_STEPS = [
    { label: "Resolving target", detail: "DNS + HTTP handshake" },
    {
      label: "Reading homepage & sitemap",
      detail: "Extracting product surface",
    },
    { label: "Inferring category", detail: "Market classification" },
    { label: "Searching market corpus", detail: "1,200+ sources via Linkup" },
    { label: "Ranking competitors", detail: "Similarity scoring" },
    { label: "Hydrating profiles", detail: "Funding · pricing · features" },
    { label: "Building radar matrix", detail: "6 dimensions × N companies" },
  ];

  // Refs survive re-renders without relaunching the effect → timer keeps
  // running across step changes (otherwise resetting startedAt makes target
  // fall back to 1200, and Math.max freezes the counter at its current value)
  const startedAtRef = React.useRef(0);
  const stepRef = React.useRef(step);
  stepRef.current = step;

  // Abort handle for in-flight /scan/discover. Cancel button calls .abort()
  // → fetch rejects → Starlette receives client disconnect → cancels the
  // request task → httpx.AsyncClient closes the connection to Linkup, which
  // stops burning credits on the in-flight /search call.
  const abortRef = React.useRef(null);
  // Set true on cancel — guards late setState writes from the start() coroutine
  // after the user has already returned to the input phase.
  const cancelledRef = React.useRef(false);

  _uE_search(() => {
    if (phase !== "scanning") return;
    startedAtRef.current = Date.now();
    let cancelled = false;
    let timer = null;

    const CORPUS_STEP_INDEX = 3;

    const schedule = () => {
      if (cancelled) return;
      const interval = stepRef.current === CORPUS_STEP_INDEX ? 180 : 320;

      setSources((s) => {
        const elapsedSec = (Date.now() - startedAtRef.current) / 1000;
        const target = 300 * (1 - Math.exp(-elapsedSec / 12));
        const delta = (target - s) * 0.07 + Math.random() * 2;
        return Math.min(300, Math.max(s, Math.floor(s + delta)));
      });

      timer = setTimeout(schedule, interval);
    };
    schedule();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [phase]);

  const PHASE_STEP = {
    "UNDERSTAND:start": 0,
    "UNDERSTAND:ok": 2,
    "DISCOVER:start": 3,
    "DISCOVER:ok": 4,
    "ENRICH:start": 5,
    "ENRICH:ok": 6,
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const start = async () => {
    setUrlError(null);
    if (!url.trim()) {
      setUrlError("Please enter a URL to analyse.");
      return;
    }
    if (!isValidUrl(url)) {
      setUrlError("Please enter a valid URL — e.g. https://example.com");
      return;
    }

    setStep(0);
    setSources(0);
    setFoundCount(0);
    setError(null);
    setPhase("scanning");
    cancelledRef.current = false;
    abortRef.current = new AbortController();
    // Generate run_id client-side so localStorage can track this scan *before*
    // the backend response arrives → refresh during discover is recoverable.
    const runId = (window.crypto?.randomUUID?.()) ||
      `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    if (onScanStart) onScanStart(url.trim(), runId);

    // ── Animate the step indicator while /scan/discover runs (UNDERSTAND ~10s + DISCOVER ~5s)
    const animate = (async () => {
      setStep(PHASE_STEP["UNDERSTAND:start"]);
      await sleep(2500);
      if (cancelledRef.current) return;
      setStep(PHASE_STEP["UNDERSTAND:ok"]);
      await sleep(4000);
      if (cancelledRef.current) return;
      setStep(PHASE_STEP["DISCOVER:start"]);
    })();

    let discoverResult;
    try {
      const resp = await fetch(`${window.RADAR_API}/scan/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), runId }),
        signal: abortRef.current.signal,
      });
      if (cancelledRef.current) return;
      if (!resp.ok) {
        const txt = await resp.text();
        if (cancelledRef.current) return;
        setError(`Backend error ${resp.status}: ${txt.slice(0, 240)}`);
        setPhase("input");
        return;
      }
      discoverResult = await resp.json();
      if (cancelledRef.current) return;
    } catch (err) {
      // AbortError is the user clicking Cancel — silent, no error toast.
      if (cancelledRef.current || err?.name === "AbortError") return;
      setError(`Network error: ${err.message || err}`);
      setPhase("input");
      return;
    }
    await animate;
    if (cancelledRef.current) return;

    setStep(PHASE_STEP["DISCOVER:ok"]);
    setFoundCount((discoverResult.candidates || []).length);

    if (onDiscoverComplete) {
      // Keep the scanning loader up — the app holds it for the loading floor and
      // then hides this screen by switching `view`. The `active` effect re-arms
      // the URL form when the scan ends. Resetting here would drop the loader.
      onDiscoverComplete(discoverResult);
    } else if (onComplete) {
      // Legacy: caller wants full RadarOutput — keep prototype-style fallback
      onComplete(discoverResult);
      setPhase("input");
      setUrl("");
    }
  };

  const cancelScan = () => {
    cancelledRef.current = true;
    if (abortRef.current) abortRef.current.abort();
    setPhase("input");
    if (onCancel) onCancel();
  };

  const handleUrlChange = (e) => {
    setUrl(e.target.value);
    if (urlError) setUrlError(null);
  };

  // ——— Input phase ————————————————————————————————
  if (phase === "input") {
    return (
      <div
        style={{
          flex: 1,
          display: "grid",
          placeItems: "center",
          padding: "56px 32px",
          background: "var(--bg)",
        }}
      >
        <div style={{ width: "min(560px, 92vw)" }}>
          {/* Header */}
          <div style={{ marginBottom: 32 }}>
            <div
              className="mono"
              style={{
                fontSize: 10,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: "var(--fg-4)",
                marginBottom: 12,
              }}
            >
              Competitive Intelligence
            </div>
            <h1
              className="serif"
              style={{
                fontSize: 34,
                fontWeight: 500,
                letterSpacing: "-0.025em",
                margin: "0 0 12px",
                lineHeight: 1.15,
                color: "var(--fg)",
              }}
            >
              Run a new competitive analysis
            </h1>
            <p
              style={{
                color: "var(--fg-3)",
                fontSize: 13.5,
                margin: 0,
                lineHeight: 1.65,
              }}
            >
              Enter a product URL. Radar reads the product surface, searches
              1,200+ sources, and returns a ranked competitive map with funding,
              features, pricing and geography.
            </p>
          </div>

          {/* System error */}
          {error && (
            <div
              style={{
                padding: "10px 14px",
                marginBottom: 16,
                borderRadius: 6,
                background: "var(--negative-bg, #fdf2f2)",
                border: "1px solid var(--negative, #c0392b)",
                color: "var(--negative, #c0392b)",
                fontSize: 12,
                fontFamily: "var(--font-mono)",
              }}
            >
              {error}
            </div>
          )}

          {/* URL input */}
          <div style={{ marginBottom: urlError ? 6 : 20 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                border: urlError
                  ? "1px solid var(--negative, #c0392b)"
                  : "1px solid var(--border-strong)",
                borderRadius: 8,
                background: "var(--surface)",
                boxShadow: urlError ? "none" : "var(--shadow-sm)",
                overflow: "hidden",
                transition: "border-color .15s",
              }}
            >
              <span
                style={{
                  padding: "0 12px",
                  color: "var(--fg-4)",
                  flexShrink: 0,
                }}
              >
                {Icons.link}
              </span>
              <input
                value={url}
                onChange={handleUrlChange}
                onKeyDown={(e) => e.key === "Enter" && start()}
                placeholder="https://example.com"
                autoFocus
                style={{
                  flex: 1,
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  padding: "14px 0",
                  fontSize: 14,
                  fontFamily: "var(--font-mono)",
                  color: "var(--fg)",
                }}
              />
              <button
                className="tb-btn primary"
                onClick={start}
                style={{ margin: 6, padding: "8px 16px", flexShrink: 0 }}
              >
                Analyse {Icons.arrowR}
              </button>
            </div>
            {urlError && (
              <div
                style={{
                  fontSize: 11.5,
                  color: "var(--negative, #c0392b)",
                  marginTop: 6,
                  paddingLeft: 2,
                  fontFamily: "var(--font-mono)",
                }}
              >
                {urlError}
              </div>
            )}
          </div>

          {/* Quick examples */}
          <div
            style={{
              marginBottom: 36,
              display: "flex",
              gap: 6,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <span
              style={{ fontSize: 11, color: "var(--fg-4)", marginRight: 2 }}
            >
              Examples:
            </span>
            {[
              "https://linq.io",
              "https://vex.finance",
              "https://modern-treasury.com",
            ].map((s) => (
              <button
                key={s}
                className="tag mono"
                onClick={() => {
                  setUrl(s);
                  setUrlError(null);
                }}
                style={{
                  cursor: "pointer",
                  fontSize: 11,
                  border: "none",
                  background: "none",
                  padding: "3px 8px",
                }}
              >
                {s.replace("https://", "")}
              </button>
            ))}
          </div>

          {/* Stats */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3,1fr)",
              gap: 1,
              border: "1px solid var(--border)",
              borderRadius: 8,
              overflow: "hidden",
              background: "var(--border)",
            }}
          >
            {[
              {
                k: "Sources scanned",
                v: "1,200+",
                d: "Crunchbase · Pitchbook · LinkedIn · G2",
              },
              {
                k: "Avg. scan time",
                v: "~60s",
                d: "Parallel search via Linkup",
              },
              {
                k: "Pipeline phases",
                v: "3",
                d: "Understand → Discover → Enrich",
              },
            ].map((s) => (
              <div
                key={s.k}
                style={{ background: "var(--surface)", padding: "16px 18px" }}
              >
                <div
                  className="mono"
                  style={{
                    fontSize: 9.5,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "var(--fg-4)",
                    marginBottom: 4,
                  }}
                >
                  {s.k}
                </div>
                <div
                  className="serif"
                  style={{
                    fontSize: 20,
                    fontWeight: 500,
                    letterSpacing: "-0.02em",
                    marginBottom: 4,
                    color: "var(--fg)",
                  }}
                >
                  {s.v}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--fg-3)",
                    lineHeight: 1.4,
                  }}
                >
                  {s.d}
                </div>
              </div>
            ))}
          </div>

          {/* Linkup attribution */}
          <div
            style={{
              marginTop: 28,
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface)",
            }}
          >
            <LinkupLogo />
            <span style={{ fontSize: 11.5, color: "var(--fg-3)" }}>
              Powered by{" "}
              <a
                href="https://linkup.so"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--fg-2)",
                  fontWeight: 500,
                  textDecoration: "none",
                  borderBottom: "1px solid var(--border-strong)",
                }}
              >
                Linkup
              </a>{" "}
              — real-time web search powering market discovery
            </span>
          </div>
        </div>
      </div>
    );
  }

  // ——— Scanning phase ————————————————————————————————
  return (
    <div
      style={{
        flex: 1,
        display: "grid",
        placeItems: "center",
        padding: "56px 32px",
        background: "var(--bg)",
      }}
    >
      <div style={{ width: "min(620px, 92vw)" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 18,
          }}
        >
          <div>
            <div
              className="mono"
              style={{
                fontSize: 9.5,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: "var(--fg-4)",
                marginBottom: 6,
              }}
            >
              Competitive Intelligence
            </div>
            <h1
              className="serif"
              style={{
                fontSize: 22,
                fontWeight: 500,
                margin: 0,
                letterSpacing: "-0.015em",
              }}
            >
              Analysing{" "}
              <span
                style={{
                  color: "var(--accent)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 18,
                  letterSpacing: 0,
                }}
              >
                {url.replace(/^https?:\/\//, "")}
              </span>
            </h1>
          </div>
          <div style={{ flex: 1 }} />
          <div
            style={{
              padding: "4px 10px",
              borderRadius: 4,
              background: "var(--accent-bg, rgba(99,102,241,.1))",
              border: "1px solid var(--accent-border, rgba(99,102,241,.25))",
              color: "var(--accent)",
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span className="dot-pulse" style={{ transform: "scale(.7)" }}>
              <i></i>
              <i></i>
              <i></i>
            </span>
            Scanning
          </div>
        </div>

        <p
          style={{
            color: "var(--fg-4)",
            fontSize: 12.5,
            marginTop: 0,
            marginBottom: 24,
            fontFamily: "var(--font-mono)",
          }}
        >
          Do not refresh — this takes ~60 seconds across 1,200+ sources.
        </p>

        {/* Scan steps */}
        <div className="card" style={{ padding: 0, marginBottom: 12 }}>
          <div
            className="card-h"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <h3>Scan pipeline</h3>
            <span className="meta mono" style={{ fontSize: 11 }}>
              Step {step + 1} / {SCAN_STEPS.length}
            </span>
          </div>
          <div style={{ padding: "4px 0" }}>
            {SCAN_STEPS.map((s, i) => {
              const state =
                i < step ? "done" : i === step ? "active" : "pending";
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "8px 16px",
                    fontSize: 12.5,
                    opacity: state === "pending" ? 0.4 : 1,
                    transition: "opacity .3s",
                    borderBottom:
                      i < SCAN_STEPS.length - 1
                        ? "1px solid var(--border)"
                        : "none",
                  }}
                >
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      display: "grid",
                      placeItems: "center",
                      flexShrink: 0,
                    }}
                  >
                    {state === "done" && (
                      <span style={{ color: "var(--positive)" }}>
                        {Icons.check}
                      </span>
                    )}
                    {state === "active" && (
                      <span
                        className="dot-pulse"
                        style={{ transform: "scale(.8)" }}
                      >
                        <i></i>
                        <i></i>
                        <i></i>
                      </span>
                    )}
                    {state === "pending" && (
                      <span style={{ color: "var(--fg-4)" }}>
                        {Icons.minus}
                      </span>
                    )}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      color: state === "active" ? "var(--fg)" : "var(--fg-2)",
                      fontWeight: state === "active" ? 500 : 400,
                    }}
                  >
                    {s.label}
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 10.5,
                      letterSpacing: "0.02em",
                      color:
                        state === "pending" ? "var(--fg-4)" : "var(--fg-3)",
                    }}
                  >
                    {state === "pending" ? "—" : s.detail}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live counters */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 1,
            border: "1px solid var(--border)",
            borderRadius: 8,
            overflow: "hidden",
            background: "var(--border)",
            marginBottom: 16,
          }}
        >
          {[
            {
              label: "Sources searched",
              value: sources.toLocaleString(),
              accent: false,
            },
            {
              label: "Competitors found",
              value: foundCount,
              accent: foundCount > 0,
            },
            { label: "Elapsed", value: <ElapsedTimer />, accent: false },
          ].map((c, i) => (
            <div
              key={i}
              style={{ background: "var(--surface)", padding: "12px 16px" }}
            >
              <div
                className="mono"
                style={{
                  fontSize: 9.5,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: "var(--fg-4)",
                  marginBottom: 4,
                }}
              >
                {c.label}
              </div>
              <div
                className="serif mono"
                style={{
                  fontSize: 20,
                  fontWeight: 500,
                  letterSpacing: "-0.01em",
                  color: c.accent ? "var(--accent)" : "var(--fg)",
                }}
              >
                {c.value}
              </div>
            </div>
          ))}
        </div>

        {/* Linkup attribution */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <LinkupLogo />
            <span style={{ fontSize: 11, color: "var(--fg-4)" }}>
              Market search powered by{" "}
              <a
                href="https://linkup.so"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--fg-3)",
                  textDecoration: "none",
                  borderBottom: "1px solid var(--border-strong)",
                }}
              >
                Linkup
              </a>
            </span>
          </div>
        </div>

        <button
          className="tb-btn"
          onClick={cancelScan}
          style={{ color: "var(--fg-4)", fontSize: 12 }}
        >
          Cancel analysis
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
