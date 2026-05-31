// screens-memo.jsx — VC comparative memo: pick a template, auto-fill from the
// gathered scan data, render read-only with source citations, export to PDF.
// Templates: built-in generalist + VC-defined custom (localStorage).
const { useState: _uS_mo, useEffect: _uE_mo, useRef: _uR_mo } = React;

// ─── Built-in generalist template (mirrors backend GENERALIST_TEMPLATE) ───────
const MEMO_GENERALIST = {
  id: "generalist-vc",
  name: "Mémo VC généraliste",
  builtin: true,
  sections: [
    { id: "exec-summary", title: "Executive Summary", instruction: "2-3 phrases: qui est le sujet, où il se situe vs le champ concurrentiel, et le risque concurrentiel principal." },
    { id: "market",       title: "Market & Category", instruction: "Définir la catégorie et le segment à partir de category/positioning. Citer les acteurs. Pas d'invention de TAM — seulement ce que la donnée montre." },
    { id: "landscape",    title: "Competitive Landscape", instruction: "Classer les concurrents par menace et similarité. Pour chaque concurrent à forte menace, une ligne sur le pourquoi." },
    { id: "positioning",  title: "Per-Competitor Positioning", instruction: "Pour les 3-4 plus menaçants, contraster keyDifferentiator et targetSegment vs le sujet. Citer chaque affirmation." },
    { id: "moats",        title: "Moats & Differentiation", instruction: "Ce qui est défendable pour le sujet vs le champ. Signaler où la preuve est mince." },
    { id: "traction",     title: "Traction & Funding Signals", instruction: "Comparer funding, effectifs, signaux récents. Citer chaque chiffre." },
    { id: "risks",        title: "Risks & Threats", instruction: "Menaces concurrentielles concrètes ancrées dans la donnée. Marquer tout inconnu 'Non disponible'." },
    { id: "reco",         title: "Recommendation", instruction: "Verdict côté investisseur (surveiller / creuser / signal-pass). Lier aux preuves citées ; aucun fait nouveau." },
  ],
};

const MEMO_TPL_KEY = "radar:memoTemplates";
const _slugId = () => "sec-" + Math.random().toString(36).slice(2, 8);

function _readTemplates() {
  try {
    const raw = localStorage.getItem(MEMO_TPL_KEY);
    const list = raw ? JSON.parse(raw) : [];
    // Drop malformed/legacy entries so a bad template can't crash the picker or generate.
    return Array.isArray(list)
      ? list.filter(t => t && t.id && Array.isArray(t.sections) && t.sections.length)
      : [];
  } catch { return []; }
}
function _writeTemplates(list) {
  try { localStorage.setItem(MEMO_TPL_KEY, JSON.stringify(list)); } catch {}
}

// ─── Minimal markdown → JSX (bold, bullet lists, paragraphs) ──────────────────
function _renderInline(text) {
  // **bold** → <strong>. Split on the pattern, keep odd indices bold.
  const parts = String(text).split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) => (i % 2 === 1 ? <strong key={i}>{p}</strong> : p));
}
function MemoBody({ body }) {
  if (!body) return null;
  const lines = String(body).split(/\n/);
  const blocks = [];
  let list = null;
  const flush = () => { if (list) { blocks.push(<ul key={"ul" + blocks.length} className="pr-list" style={{ margin: "6px 0" }}>{list}</ul>); list = null; } };
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line) { flush(); return; }
    const m = line.match(/^[-*•]\s+(.*)$/);
    if (m) { (list = list || []).push(<li key={i}>{_renderInline(m[1])}</li>); return; }
    flush();
    blocks.push(<p key={i} style={{ margin: "6px 0", lineHeight: 1.55 }}>{_renderInline(line)}</p>);
  });
  flush();
  return <div>{blocks}</div>;
}

// ─── Citations block (reuses CitationPopover + ConfidenceDot) ─────────────────
function MemoCitations({ citations }) {
  if (!citations || !citations.length) return null;
  return (
    <div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px dashed var(--border)", display: "flex", flexDirection: "column", gap: 5 }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: .4, color: "var(--fg-4)", fontFamily: "var(--font-mono)" }}>Sources</div>
      {citations.map((c, i) => (
        <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 11.5 }}>
          <window.ConfidenceDot level={c.confidence || "medium"} sourceUrl={c.sourceUrl} evidence={c.claim} />
          <div style={{ flex: 1, color: "var(--fg-2)" }}>
            {c.company && <span style={{ fontWeight: 600 }}>{c.company} — </span>}
            <window.CitationPopover evidence={c.claim} sourceUrl={c.sourceUrl}>
              <span>{c.claim}</span>
            </window.CitationPopover>
            {c.sourceUrl && (
              <a href={c.sourceUrl} target="_blank" rel="noopener noreferrer"
                style={{ marginLeft: 6, color: "var(--accent, #b34a1f)", textDecoration: "none", fontFamily: "var(--font-mono)", fontSize: 10.5 }}>
                ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Custom template builder ──────────────────────────────────────────────────
function MemoBuilder({ draft, setDraft, onSave, onCancel }) {
  const setSection = (i, patch) => setDraft({ ...draft, sections: draft.sections.map((s, j) => j === i ? { ...s, ...patch } : s) });
  const addSection = () => setDraft({ ...draft, sections: [...draft.sections, { id: _slugId(), title: "Nouvelle section", instruction: "" }] });
  const delSection = (i) => setDraft({ ...draft, sections: draft.sections.filter((_, j) => j !== i) });
  const move = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= draft.sections.length) return;
    const s = [...draft.sections];
    [s[i], s[j]] = [s[j], s[i]];
    setDraft({ ...draft, sections: s });
  };
  const canSave = draft.name.trim() && draft.sections.length > 0 && draft.sections.every(s => s.title.trim());

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 18, background: "var(--surface)", marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <input value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })}
          placeholder="Nom du template (ex: Mémo seed B2B SaaS)"
          style={{ flex: 1, fontSize: 14, fontWeight: 600, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg)", color: "var(--fg)" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {draft.sections.map((s, i) => (
          <div key={s.id} style={{ display: "flex", gap: 8, alignItems: "flex-start", border: "1px solid var(--border)", borderRadius: 8, padding: 10, background: "var(--bg)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <button className="tb-btn" onClick={() => move(i, -1)} disabled={i === 0} style={{ padding: 2, opacity: i === 0 ? .3 : 1 }} title="Monter">{window.Icons.arrowU}</button>
              <button className="tb-btn" onClick={() => move(i, 1)} disabled={i === draft.sections.length - 1} style={{ padding: 2, opacity: i === draft.sections.length - 1 ? .3 : 1 }} title="Descendre">{window.Icons.arrowD}</button>
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
              <input value={s.title} onChange={e => setSection(i, { title: e.target.value })}
                placeholder="Titre de section"
                style={{ fontSize: 13, fontWeight: 600, padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 5, background: "var(--surface)", color: "var(--fg)" }} />
              <textarea value={s.instruction} onChange={e => setSection(i, { instruction: e.target.value })}
                placeholder="Instruction: que doit contenir cette section ? (Claude la remplit depuis la data du scan)"
                rows={2}
                style={{ fontSize: 12, padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 5, background: "var(--surface)", color: "var(--fg-2)", resize: "vertical", fontFamily: "var(--font-sans)" }} />
            </div>
            <button className="tb-btn" onClick={() => delSection(i)} style={{ padding: 4, color: "var(--negative, #c0392b)" }} title="Supprimer">{window.Icons.trash}</button>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button className="tb-btn" onClick={addSection}>{window.Icons.plus}<span>Ajouter une section</span></button>
        <div style={{ flex: 1 }} />
        <button className="tb-btn" onClick={onCancel}>Annuler</button>
        <button className="tb-btn primary" onClick={onSave} disabled={!canSave} style={{ opacity: canSave ? 1 : .5 }}>Sauvegarder le template</button>
      </div>
    </div>
  );
}

// ─── Main screen ──────────────────────────────────────────────────────────────
function MemoScreen({ data }) {
  const subject = data?.subject;
  const [templates, setTemplates] = _uS_mo(_readTemplates());
  const [selectedId, setSelectedId] = _uS_mo(MEMO_GENERALIST.id);
  const [builderDraft, setBuilderDraft] = _uS_mo(null); // null = builder closed
  const [memo, setMemo] = _uS_mo(null);
  const [loading, setLoading] = _uS_mo(false);
  const [error, setError] = _uS_mo(null);

  const allTemplates = [MEMO_GENERALIST, ...templates];
  const selected = allTemplates.find(t => t.id === selectedId) || MEMO_GENERALIST;

  if (!subject) {
    return <div className="screen" style={{ padding: 40, color: "var(--fg-3)" }}>Aucun scan chargé.</div>;
  }

  const openNewBuilder = () => setBuilderDraft({ id: _slugId(), name: "", sections: MEMO_GENERALIST.sections.map(s => ({ ...s })) });
  const openEditBuilder = (t) => setBuilderDraft({ ...t, sections: t.sections.map(s => ({ ...s })) });

  const saveTemplate = () => {
    const clean = { ...builderDraft, name: builderDraft.name.trim() };
    const next = templates.some(t => t.id === clean.id)
      ? templates.map(t => t.id === clean.id ? clean : t)
      : [...templates, clean];
    setTemplates(next);
    _writeTemplates(next);
    setSelectedId(clean.id);
    setBuilderDraft(null);
  };
  const deleteTemplate = (id) => {
    const next = templates.filter(t => t.id !== id);
    setTemplates(next);
    _writeTemplates(next);
    if (selectedId === id) setSelectedId(MEMO_GENERALIST.id);
  };

  const generate = async () => {
    setLoading(true); setError(null); setMemo(null);
    const template = { id: selected.id, name: selected.name, sections: selected.sections.map(s => ({ id: s.id, title: s.title, instruction: s.instruction })) };
    try {
      const resp = await fetch(`${window.RADAR_API}/scan/memo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: subject.domain, template }),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(resp.status === 404 ? "Scan introuvable côté serveur — relance un scan." : `Erreur ${resp.status}: ${txt.slice(0, 120)}`);
      }
      setMemo(await resp.json());
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  const exportMemoPDF = () => {
    if (!memo) return;
    const existing = document.getElementById("radar-print-root");
    if (existing) existing.remove();
    const el = document.createElement("div");
    el.id = "radar-print-root";
    document.body.appendChild(el);
    ReactDOM.createRoot(el).render(<window.MemoPrintReport memo={memo} subject={subject} />);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      window.print();
      setTimeout(() => el.remove(), 1000);
    }));
  };

  return (
    <div className="screen" style={{ padding: "24px 28px", maxWidth: 920, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: .5, color: "var(--fg-4)", fontFamily: "var(--font-mono)" }}>Mémo comparatif</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: "4px 0 0", color: "var(--fg)" }}>{subject.name} <span style={{ color: "var(--fg-4)", fontWeight: 400 }}>vs. landscape</span></h1>
        </div>
      </div>

      {/* Template controls */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 18 }}>
        <span style={{ fontSize: 12, color: "var(--fg-3)" }}>Template</span>
        <select value={selectedId} onChange={e => { setSelectedId(e.target.value); setBuilderDraft(null); }}
          style={{ fontSize: 13, padding: "7px 10px", border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface)", color: "var(--fg)", minWidth: 220 }}>
          {allTemplates.map(t => <option key={t.id} value={t.id}>{t.name}{t.builtin ? " (par défaut)" : ""}</option>)}
        </select>
        <button className="tb-btn" onClick={openNewBuilder}>{window.Icons.plus}<span>Nouveau template</span></button>
        {!selected.builtin && (
          <>
            <button className="tb-btn" onClick={() => openEditBuilder(selected)}>Éditer</button>
            <button className="tb-btn" style={{ color: "var(--negative, #c0392b)" }} onClick={() => deleteTemplate(selected.id)}>{window.Icons.trash}</button>
          </>
        )}
        <div style={{ flex: 1 }} />
        <button className="tb-btn primary" onClick={generate} disabled={loading} style={{ opacity: loading ? .6 : 1 }}>
          {loading
            ? <><span className="dot-pulse" style={{ transform: "scale(.75)" }}><i></i><i></i><i></i></span><span>Génération…</span></>
            : <>{window.Icons.zap}<span>Générer le mémo</span></>}
        </button>
        {memo && <button className="tb-btn" onClick={exportMemoPDF}>{window.Icons.download}<span>PDF</span></button>}
      </div>

      {builderDraft && <MemoBuilder draft={builderDraft} setDraft={setBuilderDraft} onSave={saveTemplate} onCancel={() => setBuilderDraft(null)} />}

      {error && (
        <div style={{ padding: "10px 14px", border: "1px solid var(--negative, #c0392b)", borderRadius: 8, color: "var(--negative, #c0392b)", fontSize: 13, marginBottom: 16 }}>{error}</div>
      )}

      {!memo && !loading && !error && (
        <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--fg-4)", border: "1px dashed var(--border)", borderRadius: 10 }}>
          <p style={{ fontSize: 13, margin: 0 }}>Choisis un template puis génère un mémo comparatif sourcé à partir des données du scan.</p>
          <p style={{ fontSize: 11.5, marginTop: 8 }}>Chaque affirmation est reliée à sa source. Les données manquantes sont marquées <b>Non disponible</b> — rien n'est inventé.</p>
        </div>
      )}

      {/* Rendered memo */}
      {memo && (
        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div style={{ fontSize: 11, color: "var(--fg-4)", fontFamily: "var(--font-mono)" }}>
            {memo.templateName} · généré le {new Date(memo.generatedAt).toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
          {memo.sections.map(s => (
            <section key={s.id}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "var(--fg)" }}>{s.title}</h2>
                <window.ConfidenceDot level={s.confidence || "medium"} />
                {s.hasGaps && (
                  <span style={{ fontSize: 10.5, color: "var(--fg-4)", fontFamily: "var(--font-mono)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 6px" }}>Données incomplètes</span>
                )}
              </div>
              <div style={{ fontSize: 13.5, color: "var(--fg-2)" }}><MemoBody body={s.body} /></div>
              <MemoCitations citations={s.citations} />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

window.MemoScreen = MemoScreen;
