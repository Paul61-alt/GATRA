// screens-pricing.jsx â pricing tiers comparison
function PricingScreen({ data, onOpenCompany }) {
  const { subject, competitors, pricing } = data;
  const all = [subject, ...competitors];

  return (
    <div className="screen">
      <SectionH title="Pricing comparison" meta="Public-list tiers Â· Custom enterprise pricing flagged" />

      {/* Snapshot row */}
      <div className="card" style={{marginBottom: 16}}>
        <div className="card-h">
          <h3>Pricing model snapshot</h3>
          <span className="meta">Headline pricing Â· entry tier</span>
        </div>
        <div style={{overflowX:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Company</th>
                <th>Model</th>
                <th>Entry tier</th>
                <th>Headline</th>
                <th className="num">Avg. contract</th>
                <th className="num">Customers</th>
              </tr>
            </thead>
            <tbody>
              {all.map(c => (
                <tr key={c.id} className={c.isSubject ? "subject-row" : ""}
                  onClick={() => !c.isSubject && onOpenCompany && onOpenCompany(c.id)}
                  style={{cursor: c.isSubject ? "default" : "pointer"}}>
                  <td>
                    <div className="name-cell">
                      <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
                      <span className="nm">{c.name}</span>
                    </div>
                  </td>
                  <td>{c.pricing.model}</td>
                  <td>{
                    c.pricing.salesGated
                      ? <span className="muted">Sur devis</span>
                      : (c.pricing.starts_at == null || c.pricing.starts_at === 0)
                        ? <span className="muted">Free / Usage</span>
                        : "€" + c.pricing.starts_at.toLocaleString()
                  }</td>
                  <td className="mono" style={{fontSize:11.5}}>{c.pricing.mention}</td>
                  <td className="num">{fmtMoney(c.avgContract)}</td>
                  <td className="num">{fmtNum(c.customers)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pricing tier cards per company */}
      <SectionH title="Tier breakdown" meta={`${all.length} pricing pages parsed`} />
      <div style={{display:"flex", flexDirection:"column", gap: 14}}>
        {all.map(c => (
          <PricingCompany key={c.id} c={c} tiers={pricing[c.id]} onOpenCompany={onOpenCompany} />
        ))}
      </div>
    </div>
  );
}

function PricingCompany({ c, tiers, onOpenCompany }) {
  tiers = tiers || [];
  return (
    <div className="card" style={{
      borderColor: c.isSubject ? "var(--accent-bg-2)" : "var(--border)",
    }}>
      <div className="card-h"
        onClick={() => !c.isSubject && onOpenCompany && onOpenCompany(c.id)}
        style={{
          background: c.isSubject ? "var(--accent-bg)" : "transparent",
          borderColor: c.isSubject ? "var(--accent-bg-2)" : "var(--border)",
          cursor: c.isSubject ? "default" : "pointer",
        }}>
        <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
        <h3 style={{color: c.isSubject ? "var(--accent-fg)" : "var(--fg)"}}>{c.name}</h3>
        {c.isSubject && <span className="tag subject mono" style={{fontSize:9}}>SUBJECT</span>}
        <span className="muted" style={{fontSize:11.5}}>Â· {c.pricing.model}</span>
        <span className="meta">{tiers.length} tier{tiers.length !== 1 ? "s" : ""}</span>
      </div>
      {tiers.length === 0 ? (
        <div style={{padding:16, fontSize:12, color:"var(--fg-3)"}}>
          {c.pricing.mention || "Custom enterprise pricing — contact sales."}
        </div>
      ) : (
      <div style={{display:"grid", gridTemplateColumns:`repeat(${tiers.length}, 1fr)`}}>
        {tiers.map((t, i) => (
          <div key={t.name} style={{
            padding: 16,
            borderRight: i < tiers.length - 1 ? "1px solid var(--border-dim)" : "none",
          }}>
            <div className="mono" style={{
              fontSize: 10, letterSpacing: "0.08em",
              textTransform: "uppercase", color: "var(--fg-4)",
            }}>{t.name}</div>
            <div style={{display:"flex", alignItems:"baseline", gap:6, marginTop: 4}}>
              <span className="serif" style={{
                fontSize: 22, fontWeight: 500, letterSpacing: "-0.02em",
                color: c.isSubject ? "var(--accent)" : "var(--fg)",
              }}>{t.price}</span>
              {t.per && <span className="mono dim" style={{fontSize:11}}>{t.per}</span>}
            </div>
            <ul style={{
              margin: "10px 0 0", padding: 0, listStyle: "none",
              fontSize: 12, color: "var(--fg-2)",
            }}>
              {t.features.map(f => (
                <li key={f} style={{display:"flex", alignItems:"flex-start", gap:7, padding: "3px 0"}}>
                  <span style={{color: c.isSubject ? "var(--accent)" : "var(--fg-3)", marginTop: 4}}>
                    <svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M1 4.5 4 7.5 8 1.5"/>
                    </svg>
                  </span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}

window.PricingScreen = PricingScreen;
