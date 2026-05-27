// copilot.jsx — Copilot AI chat panel (powered by Linkup)

const { useState: _uS_co, useRef: _uR_co, useEffect: _uE_co } = React;

const AI_ICON_PATH = "M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z";

function AiIcon({ size = 16, fill = "var(--accent)", style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" fill={fill} stroke="none" style={style}>
      <path d={AI_ICON_PATH}/>
    </svg>
  );
}

async function fetchCopilotAnswer(query, context, history) {
  const res = await fetch(`${window.RADAR_API}/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, context, history }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Collapsed sources component ─────────────────────────────
function Sources({ sources }) {
  const [open, setOpen] = _uS_co(false);
  if (!sources || sources.length === 0) return null;

  const withFavicon = sources.filter(s => s.favicon);
  const shown = withFavicon.slice(0, 5);

  return (
    <div className="xo-sources-wrap">
      <button className="xo-sources-toggle" onClick={() => setOpen(v => !v)}>
        <div className="xo-favicon-stack">
          {shown.map((s, i) => (
            <img key={i} src={s.favicon} alt="" width={13} height={13}
              style={{borderRadius: 3, outline: "1.5px solid var(--surface)"}}
              onError={e => e.target.style.display = "none"} />
          ))}
          {sources.length > shown.length && (
            <span className="xo-favicon-more">+{sources.length - shown.length}</span>
          )}
        </div>
        <span className="xo-sources-label">
          {sources.length} source{sources.length > 1 ? "s" : ""}
        </span>
        <span className="xo-sources-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="xo-sources-list">
          {sources.map((s, i) => (
            <a key={i} className="xo-source-row"
              href={s.url} target="_blank" rel="noopener noreferrer"
              title={s.snippet || s.name}>
              {s.favicon && (
                <img src={s.favicon} alt="" width={12} height={12}
                  style={{borderRadius: 2, flexShrink: 0}}
                  onError={e => e.target.style.display = "none"} />
              )}
              <span className="xo-source-name">{s.name}</span>
              <span className="xo-source-arrow">↗</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Build rich context from scan data ───────────────────────
function buildContext(data) {
  if (!data) return "";
  const { subject, competitors = [] } = data;

  const fmtFunding = (c) => {
    const total = c.funding?.total;
    if (!total) return "bootstrapped";
    if (total >= 1e9) return `$${(total/1e9).toFixed(1)}B raised`;
    if (total >= 1e6) return `$${(total/1e6).toFixed(0)}M raised`;
    return `$${total} raised`;
  };

  const subjectLine = [
    `${subject.name} (${subject.domain})`,
    subject.category,
    subject.hq,
    `founded ${subject.founded}`,
    `${subject.employees} employees`,
    fmtFunding(subject),
    subject.pricing?.mention ? `pricing: ${subject.pricing.mention}` : null,
    subject.tagline,
  ].filter(Boolean).join(" · ");

  const competitorLines = competitors.map(c => [
    `${c.name} (${c.domain})`,
    `threat: ${c.threat}`,
    `similarity: ${c.similarity != null ? Math.round(c.similarity * 100) + "%" : "?"}`,
    `${c.employees || "?"} employees`,
    fmtFunding(c),
    c.pricing?.mention ? `pricing: ${c.pricing.mention}` : null,
    c.tagline,
  ].filter(Boolean).join(" · ")).join("\n");

  return `SUBJECT: ${subjectLine}\n\nCOMPETITORS:\n${competitorLines}`;
}

// ─── Main panel ───────────────────────────────────────────────
function CopilotPanel({ open, onClose, data }) {
  const [messages, _setMessages] = _uS_co([]);
  const [input, setInput] = _uS_co("");
  const [loading, setLoading] = _uS_co(false);
  const endRef = _uR_co(null);
  const inputRef = _uR_co(null);

  _uE_co(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  _uE_co(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const doSubmit = async (q) => {
    if (!q || loading) return;
    const newMsg = { role: "user", text: q };
    _setMessages(prev => [...prev, newMsg]);
    setLoading(true);

    // Send last 6 messages as history (excluding the one we just added)
    const history = messages.slice(-6).map(m => ({ role: m.role, text: m.text }));

    try {
      const result = await fetchCopilotAnswer(q, buildContext(data), history);
      _setMessages(prev => [...prev, {
        role: "assistant",
        text: result.answer,
        sources: result.sources || [],
      }]);
    } catch (e) {
      _setMessages(prev => [...prev, {
        role: "assistant",
        text: "Sorry, I couldn't get an answer right now.",
        sources: [],
        isError: true,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const submit = () => {
    const q = input.trim();
    if (!q) return;
    setInput("");
    doSubmit(q);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const SUGGESTIONS = [
    "What are the biggest threats in this market?",
    "How does the pricing compare across competitors?",
    "What recent news is there about the top competitors?",
  ];

  return (
    <div className={"xopilot-panel" + (open ? " open" : "")}>
      {/* Header */}
      <div className="xo-header">
        <div className="xo-header-title">
          <AiIcon size={16} />
          <span>Copilot</span>
        </div>
        {messages.length > 0 && (
          <button className="xo-new-chat" onClick={() => _setMessages([])} title="New chat">
            <Ic d={<><path d="M12 5v14M5 12h14"/></>} sz={13} />
            <span>New chat</span>
          </button>
        )}
        <button className="xo-close" onClick={onClose} title="Close">
          <Ic d={<path d="M5 5l14 14M19 5 5 19"/>} sz={14} />
        </button>
      </div>

      {/* Messages */}
      <div className="xo-messages">
        {messages.length === 0 && (
          <div className="xo-empty">
            <AiIcon size={32} style={{opacity: .4}} />
            <p>Ask anything about this competitive landscape. Answers are sourced from the web in real time.</p>
            <div className="xo-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="xo-suggestion" onClick={() => doSubmit(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={"xo-msg xo-msg-" + m.role}>
            {m.role === "assistant" && (
              <div className="xo-msg-icon">
                <AiIcon size={12} fill={m.isError ? "var(--negative)" : "var(--accent)"} />
              </div>
            )}
            <div className="xo-msg-body">
              <p>{m.text}</p>
              <Sources sources={m.sources} />
            </div>
          </div>
        ))}

        {loading && (
          <div className="xo-msg xo-msg-assistant">
            <div className="xo-msg-icon"><AiIcon size={12} /></div>
            <div className="xo-msg-body xo-typing"><span/><span/><span/></div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="xo-input-area">
        <textarea
          ref={inputRef}
          className="xo-input"
          placeholder="Ask about this scan…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
        />
        <button
          className={"xo-send" + (input.trim() ? " active" : "")}
          onClick={submit}
          disabled={!input.trim() || loading}
          title="Send"
        >
          <Ic d={<><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9l20-7z"/></>} sz={14} />
        </button>
      </div>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
        padding: "6px 0 10px",
        opacity: 0.45,
      }}>
        <img src="https://www.linkup.so/favicon.ico" alt="" width={11} height={11} style={{borderRadius: 2}} />
        <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.02em" }}>
          Powered by Linkup
        </span>
      </div>
    </div>
  );
}

function CopilotTab({ active, onClick }) {
  return (
    <button className={"xo-tab-btn" + (active ? " active" : "")} onClick={onClick} title="Copilot AI">
      <AiIcon size={14} fill={active ? "var(--accent)" : "var(--fg-3)"} />
      <span>Copilot</span>
    </button>
  );
}

Object.assign(window, { CopilotPanel, CopilotTab });
