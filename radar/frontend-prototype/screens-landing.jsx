// screens-landing.jsx — BYOK access gate.
// Tester pastes their own LinkUp key → we validate it (POST /linkup/validate,
// shows their balance) → key stored in localStorage → they enter the app and
// every scan runs on THEIR LinkUp credits (header attached by index.html patch).
// The key is the credential — no shared token to hand out. A discreet "internal
// access" link still lets us paste RADAR_SHARED_TOKEN for our own use.

function LandingScreen({ onEnter }) {
  const { useState } = React;
  const ACCENT = (window.RADAR_TWEAK_DEFAULTS && window.RADAR_TWEAK_DEFAULTS.accent) || "#b34a1f";

  const [key, setKey] = useState("");
  const [status, setStatus] = useState("idle"); // idle | validating | valid | invalid | error
  const [balance, setBalance] = useState(null);
  const [errMsg, setErrMsg] = useState("");

  async function validate(e) {
    if (e) e.preventDefault();
    const k = key.trim();
    if (!k) return;
    setStatus("validating");
    setErrMsg("");
    try {
      const res = await fetch(window.RADAR_API + "/linkup/validate", {
        method: "POST",
        headers: { "X-Linkup-Key": k },
      });
      if (!res.ok) {
        // 422 (missing) / 503 (kill switch) / 429 (rate limit) — treat as error
        const body = await res.json().catch(() => ({}));
        setStatus("error");
        setErrMsg(body.detail ? String(body.detail) : "Server error (" + res.status + ")");
        return;
      }
      const data = await res.json();
      if (data.valid) {
        // Persist immediately so subsequent /scan calls carry the key.
        window.radarSetLinkupKey(k);
        setBalance(typeof data.balanceUsd === "number" ? data.balanceUsd : null);
        setStatus("valid");
      } else {
        setStatus("invalid");
      }
    } catch (err) {
      setStatus("error");
      setErrMsg("Network error — check your connection or the backend URL.");
    }
  }

  function internalAccess() {
    const t = window.prompt("Internal access — paste shared token");
    if (t && t.trim()) {
      window.radarSetToken(t.trim());
      onEnter();
    }
  }

  const card = {
    display: "flex", flexDirection: "column", gap: 14,
    padding: 32, borderRadius: 14, background: "var(--bg, #faf9f7)",
    border: "1px solid var(--border, #e6e1d6)",
    boxShadow: "0 8px 40px rgba(20,17,13,0.08)", width: 400, maxWidth: "92vw",
  };
  const label = { fontSize: 13, color: "var(--fg-3, #6b6357)", lineHeight: 1.5 };

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "var(--bg-2, #f3f1ec)",
      fontFamily: "Roboto, system-ui, sans-serif", padding: 20,
    }}>
      <form onSubmit={validate} style={card}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 24, fontWeight: 700, color: "var(--fg, #14110d)", letterSpacing: -0.5 }}>Radar</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: ACCENT, textTransform: "uppercase", letterSpacing: 1 }}>BYOK</span>
        </div>
        <div style={label}>
          Competitive intelligence for VCs. Bring your own LinkUp key — scans run on
          your own credits, so you can test freely.
        </div>

        <input
          type="password"
          autoFocus
          placeholder="LinkUp API key"
          value={key}
          onChange={e => { setKey(e.target.value); if (status !== "idle") setStatus("idle"); }}
          style={{
            padding: "11px 13px", fontSize: 14, border: "1px solid var(--border-strong, #d3ccbd)",
            borderRadius: 8, outline: "none", fontFamily: "Roboto Mono, monospace",
            background: "white", color: "var(--fg, #14110d)",
          }}
        />

        {status === "valid" ? (
          <div style={{
            fontSize: 13, color: "var(--fg-2, #36312a)",
            background: "var(--bg-3, #ebe8e0)", borderRadius: 8, padding: "10px 12px",
          }}>
            ✓ Key valid{balance != null ? <> — <b>${balance.toFixed(2)}</b> credits available</> : ""}.
          </div>
        ) : null}
        {status === "invalid" ? (
          <div style={{ fontSize: 13, color: "#b3331f" }}>✗ This key was rejected by LinkUp. Check it and try again.</div>
        ) : null}
        {status === "error" ? (
          <div style={{ fontSize: 13, color: "#b3331f" }}>{errMsg}</div>
        ) : null}

        {status === "valid" ? (
          <button type="button" onClick={onEnter} style={btn(ACCENT)}>Enter Radar →</button>
        ) : (
          <button type="submit" disabled={status === "validating" || !key.trim()} style={{
            ...btn(ACCENT), opacity: (status === "validating" || !key.trim()) ? 0.55 : 1,
            cursor: (status === "validating" || !key.trim()) ? "default" : "pointer",
          }}>
            {status === "validating" ? "Testing…" : "Test my key"}
          </button>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 2 }}>
          <a href="https://app.linkup.so/api-keys" target="_blank" rel="noopener noreferrer"
             style={{ fontSize: 12, color: "var(--fg-4, #a09684)", textDecoration: "none" }}>
            How to get a LinkUp key ↗
          </a>
          <button type="button" onClick={internalAccess} style={{
            fontSize: 12, color: "var(--fg-4, #a09684)", background: "none",
            border: "none", cursor: "pointer", padding: 0,
          }}>Internal access</button>
        </div>
      </form>
    </div>
  );

  function btn(accent) {
    return {
      padding: "11px 16px", fontSize: 14, fontWeight: 600,
      background: accent, color: "white", border: "none",
      borderRadius: 8, cursor: "pointer",
    };
  }
}

window.LandingScreen = LandingScreen;
