// copilot.jsx — Copilot AI chat panel (powered by Linkup)

const { useState: _uS_co, useRef: _uR_co, useEffect: _uE_co } = React;

async function fetchCopilotAnswer(query, scanContext) {
  const res = await fetch(`${window.RADAR_API}/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, context: scanContext }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json(); // { answer, sources: [{name, url, snippet, favicon}] }
}

function CopilotPanel({ open, onClose, data }) {
  const [messages, _setMessages] = _uS_co([]);
  const [input, setInput] = _uS_co("");
  const [loading, setLoading] = _uS_co(false);
  const [error, setError] = _uS_co(null);
  const endRef = _uR_co(null);
  const inputRef = _uR_co(null);

  _uE_co(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  _uE_co(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const buildContext = () => {
    if (!data) return "";
    const { subject, competitors = [] } = data;
    const topComp = competitors.slice(0, 5).map(c => c.name).join(", ");
    return `Subject company: ${subject.name} (${subject.domain}). Category: ${subject.category}. Top competitors: ${topComp}.`;
  };

  const doSubmit = async (q) => {
    if (!q || loading) return;
    setError(null);
    _setMessages(prev => [...prev, { role: "user", text: q }]);
    setLoading(true);
    try {
      const result = await fetchCopilotAnswer(q, buildContext());
      _setMessages(prev => [...prev, {
        role: "assistant",
        text: result.answer,
        sources: result.sources || [],
      }]);
    } catch (e) {
      setError(e.message);
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
          <svg width="16" height="16" viewBox="0 0 30 30" fill="var(--accent)" stroke="none">
            <path d="M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z"/>
          </svg>
          <span>Copilot</span>
        </div>
        <button className="xo-close" onClick={onClose} title="Close">
          <Ic d={<path d="M5 5l14 14M19 5 5 19"/>} sz={14} />
        </button>
      </div>

      {/* Messages */}
      <div className="xo-messages">
        {messages.length === 0 && (
          <div className="xo-empty">
            <svg width="32" height="32" viewBox="0 0 30 30" fill="var(--accent)" stroke="none" style={{opacity:.4}}>
              <path d="M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z"/>
            </svg>
            <p>Ask anything about this competitive landscape. Answers are sourced from the web in real time.</p>
            <div className="xo-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="xo-suggestion" onClick={() => doSubmit(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={"xo-msg xo-msg-" + m.role}>
            {m.role === "assistant" && (
              <div className="xo-msg-icon">
                <svg width="12" height="12" viewBox="0 0 30 30"
                  fill={m.isError ? "var(--negative)" : "var(--accent)"} stroke="none">
                  <path d="M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z"/>
                </svg>
              </div>
            )}
            <div className="xo-msg-body">
              <p>{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <div className="xo-sources">
                  <span className="xo-sources-label">Sources</span>
                  {m.sources.map((s, si) => (
                    <a key={si} className="xo-source-chip"
                      href={s.url} target="_blank" rel="noopener noreferrer"
                      title={s.snippet || s.name}>
                      {s.favicon && (
                        <img src={s.favicon} alt="" width={11} height={11}
                          style={{borderRadius:2, flexShrink:0, verticalAlign:"middle"}}
                          onError={e => e.target.style.display="none"} />
                      )}
                      {s.name}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="xo-msg xo-msg-assistant">
            <div className="xo-msg-icon">
              <svg width="12" height="12" viewBox="0 0 30 30" fill="var(--accent)" stroke="none">
                <path d="M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z"/>
              </svg>
            </div>
            <div className="xo-msg-body xo-typing">
              <span/><span/><span/>
            </div>
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
    </div>
  );
}

function CopilotTab({ active, onClick }) {
  return (
    <button
      className={"xo-tab-btn" + (active ? " active" : "")}
      onClick={onClick}
      title="Copilot AI"
    >
      <svg width="14" height="14" viewBox="0 0 30 30"
        fill={active ? "var(--accent)" : "var(--fg-3)"}
        stroke="none">
        <path d="M13.95 6.805l.654 3.06c.593 2.773 2.759 4.939 5.532 5.532l3.06.654c1.024.219 1.024 1.68 0 1.899l-3.06.654c-2.773.593-4.939 2.759-5.532 5.532l-.654 3.06c-.219 1.024-1.68 1.024-1.899 0l-.654-3.06c-.593-2.773-2.759-4.939-5.532-5.532l-3.06-.654c-1.024-.219-1.024-1.68 0-1.899l3.06-.654c2.773-.593 4.939-2.759 5.532-5.532l.654-3.06C12.269 5.781 13.731 5.781 13.95 6.805zM23.641 2.525l.588 2.119c.152.547.58.975 1.127 1.127l2.119.588c.65.18.65 1.102 0 1.282l-2.119.588c-.547.152-.975.58-1.127 1.127l-.588 2.119c-.18.65-1.102.65-1.282 0l-.588-2.119c-.152-.547-.58-.975-1.127-1.127l-2.119-.588c-.65-.18-.65-1.102 0-1.282l2.119-.588c.547-.152.975-.58 1.127-1.127l.588-2.119C22.539 1.875 23.461 1.875 23.641 2.525z"/>
      </svg>
      <span>Copilot</span>
    </button>
  );
}

Object.assign(window, { CopilotPanel, CopilotTab });
