// screens-select.jsx — HITL candidate selection between /scan/discover and /scan/enrich
const { useState: _uS_sel, useEffect: _uE_sel } = React;

// Approximate cost per enriched competitor (Linkup /research depth=M)
const COST_PER_COMPETITOR_EUR = 0.5;

function SelectScreen({ discoverResult, onEnrichComplete, onBack, onScanStart }) {
  const [selected, setSelected] = _uS_sel(() => new Set());
  const [enrichPhase, setEnrichPhase] = _uS_sel("idle"); // idle | streaming | error
  const [progress, setProgress] = _uS_sel({ done: 0, total: 0, current: null });
  const [error, setError] = _uS_sel(null);

  const candidates = discoverResult?.candidates || [];
  const companyName = discoverResult?.companyName || "Subject";
  const companyTagline = discoverResult?.companyTagline || "";
  const totalSelected = selected.size;
  const estimatedCost = (totalSelected * COST_PER_COMPETITOR_EUR).toFixed(2);

  const toggle = (domain) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(candidates.map((c) => c.domain)));
  const clearAll = () => setSelected(new Set());

  const submit = async () => {
    if (totalSelected === 0 || enrichPhase === "streaming") return;
    setError(null);
    setEnrichPhase("streaming");
    setProgress({ done: 0, total: totalSelected, current: null });
    if (onScanStart) onScanStart(discoverResult.companyDomain || companyName);

    let resp;
    try {
      resp = await fetch(`${window.RADAR_API}/scan/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          runId: discoverResult.runId,
          selected: Array.from(selected),
        }),
      });
    } catch (err) {
      setEnrichPhase("error");
      setError(`Network error: ${err.message || err}`);
      return;
    }

    if (!resp.ok) {
      const txt = await resp.text();
      setEnrichPhase("error");
      if (resp.status === 404) {
        setError("Session expirée (2h max). Relance un scan depuis l'écran d'accueil.");
      } else {
        setError(`Backend error ${resp.status}: ${txt.slice(0, 240)}`);
      }
      return;
    }

    // Parse SSE stream
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop(); // keep last partial chunk
      for (const evt of events) {
        const dataLine = evt
          .split("\n")
          .find((l) => l.startsWith("data: "));
        if (!dataLine) continue;
        let payload;
        try {
          payload = JSON.parse(dataLine.slice(6));
        } catch {
          continue;
        }
        if (payload.result) {
          if (onEnrichComplete) onEnrichComplete(payload.result);
          return;
        }
        if (payload.error) {
          setEnrichPhase("error");
          setError(payload.error);
          return;
        }
        if (payload.phase === "ENRICH") {
          if (payload.status === "progress") {
            setProgress((p) => ({
              ...p,
              done: payload.done ?? p.done,
              total: payload.total ?? p.total,
            }));
          }
          if (payload.status === "polling" && payload.competitor) {
            setProgress((p) => ({ ...p, current: payload.competitor }));
          }
        }
      }
    }
  };

  // ── Streaming UI ────────────────────────────────────────────────────────────
  if (enrichPhase === "streaming") {
    const pct = progress.total > 0
      ? Math.round((progress.done / progress.total) * 100)
      : 0;
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
            Phase 3 · Enrichissement
          </div>
          <h2
            className="serif"
            style={{ fontSize: 28, fontWeight: 500, color: "var(--fg)", marginBottom: 8 }}
          >
            Analyse en cours…
          </h2>
          <div style={{ fontSize: 14, color: "var(--fg-3)", marginBottom: 32 }}>
            Recherche approfondie sur {totalSelected} concurrent{totalSelected > 1 ? "s" : ""}.
          </div>
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 20,
              marginBottom: 16,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                color: "var(--fg-3)",
                marginBottom: 12,
                fontFamily: "var(--font-mono)",
              }}
            >
              <span>
                ENRICH {progress.done} / {progress.total}
              </span>
              <span>{pct}%</span>
            </div>
            <div
              style={{
                height: 4,
                background: "var(--bg-3)",
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${pct}%`,
                  background: "var(--accent)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            {progress.current && (
              <div
                style={{
                  marginTop: 14,
                  fontSize: 13,
                  color: "var(--fg-2)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                → {progress.current}
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: "var(--fg-4)" }}>
            Tu peux laisser cet onglet ouvert — la requête continue en arrière-plan.
          </div>
        </div>
      </div>
    );
  }

  // ── Error UI ─────────────────────────────────────────────────────────────────
  if (enrichPhase === "error") {
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
          <div
            style={{
              background: "var(--negative-bg)",
              border: "1px solid var(--negative)",
              borderRadius: 8,
              padding: 20,
              marginBottom: 16,
              color: "var(--negative)",
              fontSize: 14,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Erreur</div>
            <div>{error}</div>
          </div>
          <button
            onClick={onBack}
            style={{
              padding: "10px 18px",
              background: "var(--fg)",
              color: "var(--bg)",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            Retour
          </button>
        </div>
      </div>
    );
  }

  // ── Selection UI (default) ───────────────────────────────────────────────────
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: "var(--bg)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "32px 40px 20px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <div style={{ maxWidth: 880, margin: "0 auto" }}>
          <div
            className="mono"
            style={{
              fontSize: 10,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--fg-4)",
              marginBottom: 8,
            }}
          >
            Phase 2 · Sélection · {candidates.length} candidats trouvés
          </div>
          <h1
            className="serif"
            style={{
              fontSize: 26,
              fontWeight: 500,
              color: "var(--fg)",
              marginBottom: 6,
            }}
          >
            Concurrents de {companyName}
          </h1>
          {companyTagline && (
            <div style={{ fontSize: 14, color: "var(--fg-3)", marginBottom: 18 }}>
              {companyTagline}
            </div>
          )}
          <div
            style={{
              display: "flex",
              gap: 16,
              alignItems: "center",
              fontSize: 12,
              color: "var(--fg-3)",
            }}
          >
            <span>
              Coche les concurrents que tu veux analyser en profondeur.
            </span>
            <button
              onClick={selectAll}
              style={{
                background: "none",
                border: "none",
                color: "var(--accent)",
                cursor: "pointer",
                fontSize: 12,
                textDecoration: "underline",
                padding: 0,
              }}
            >
              Tout sélectionner
            </button>
            <button
              onClick={clearAll}
              style={{
                background: "none",
                border: "none",
                color: "var(--fg-3)",
                cursor: "pointer",
                fontSize: 12,
                textDecoration: "underline",
                padding: 0,
              }}
            >
              Tout désélectionner
            </button>
          </div>
        </div>
      </div>

      {/* Candidate list — scrollable */}
      <div style={{ flex: 1, overflow: "auto", padding: "20px 40px" }}>
        <div style={{ maxWidth: 880, margin: "0 auto" }}>
          {candidates.length === 0 && (
            <div
              style={{
                padding: 40,
                textAlign: "center",
                color: "var(--fg-3)",
                fontSize: 14,
              }}
            >
              Aucun concurrent trouvé.
            </div>
          )}
          {candidates.map((c, i) => {
            const isSelected = selected.has(c.domain);
            return (
              <div
                key={c.domain || i}
                onClick={() => toggle(c.domain)}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 14,
                  padding: "14px 16px",
                  background: isSelected ? "var(--accent-bg)" : "var(--surface)",
                  border: `1px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
                  borderRadius: 8,
                  marginBottom: 8,
                  cursor: "pointer",
                  transition: "background 0.15s, border-color 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.background = "var(--bg-2)";
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.background = "var(--surface)";
                }}
              >
                <div
                  style={{
                    width: 18,
                    height: 18,
                    border: `1.5px solid ${isSelected ? "var(--accent)" : "var(--border-strong)"}`,
                    borderRadius: 4,
                    background: isSelected ? "var(--accent)" : "transparent",
                    display: "grid",
                    placeItems: "center",
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  {isSelected && (
                    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2.5 6.5L5 9L9.5 3"
                        stroke="white"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 10,
                      marginBottom: 4,
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: 15,
                        color: "var(--fg)",
                      }}
                    >
                      {c.name}
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 11, color: "var(--fg-4)" }}
                    >
                      {c.domain}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: "var(--fg-3)",
                      lineHeight: 1.45,
                    }}
                  >
                    {c.tagline || "—"}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sticky footer with CTA */}
      <div
        style={{
          padding: "18px 40px",
          borderTop: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <div
          style={{
            maxWidth: 880,
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 24,
          }}
        >
          <div>
            <div
              className="mono"
              style={{
                fontSize: 11,
                color: "var(--fg-3)",
                marginBottom: 2,
              }}
            >
              {totalSelected} / {candidates.length} sélectionnés
            </div>
            <div style={{ fontSize: 12, color: "var(--fg-4)" }}>
              Coût estimé : ~€{estimatedCost} · ENRICH + SYNTHESIZE
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={onBack}
              style={{
                padding: "10px 18px",
                background: "transparent",
                color: "var(--fg-3)",
                border: "1px solid var(--border-strong)",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              Retour
            </button>
            <button
              onClick={submit}
              disabled={totalSelected === 0}
              style={{
                padding: "10px 22px",
                background:
                  totalSelected === 0 ? "var(--bg-3)" : "var(--accent)",
                color: totalSelected === 0 ? "var(--fg-4)" : "#fff",
                border: "none",
                borderRadius: 6,
                cursor: totalSelected === 0 ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Analyser {totalSelected > 0 ? `${totalSelected} concurrent${totalSelected > 1 ? "s" : ""}` : ""}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
