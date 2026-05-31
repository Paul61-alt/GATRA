// screens-map.jsx — geographic distribution of competitors (Leaflet real map)
const { useState: _uS_map, useMemo: _uM_map, useEffect: _uE_map, useRef: _uR_map } = React;

// ─── Region bucket helper ──────────────────────────────────────────────────────
function getRegion(lat, lng) {
  if (lng > -30 && lng < 60 && lat > 30) return "Europe";
  if (lng >= 60) return "Asia / Pacific";
  if (lat < 15 && lng < -30) return "Latin America";
  if (lat < 15 && lng >= 60) return "Asia / Pacific";
  return "North America";
}

// hq sometimes arrives as a dirty citation blob ("London [Harver - 2026…](url), …").
// Keep the leading location, drop any bracket/paren citation tail.
function cleanHq(hq) {
  if (!hq) return "";
  return String(hq).split(/\s*[\[(]/)[0].trim().replace(/,\s*$/, "");
}

// Treat [0,0] / null / missing as "no HQ resolved" — never plot null island.
function hasValidCoords(c) {
  if (!c || !Array.isArray(c.hqCoords) || c.hqCoords.length < 2) return false;
  const [lat, lng] = c.hqCoords;
  if (typeof lat !== "number" || typeof lng !== "number") return false;
  if (Math.abs(lat) < 0.5 && Math.abs(lng) < 0.5) return false;
  return true;
}

// ─── Leaflet map component (imperative, no react-leaflet needed) ───────────────
// Build the HTML for a logo pill marker
function makeMarkerHtml(c, isHovered) {
  const faviconUrl = c.domain
    ? `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${c.domain}&size=32`
    : null;
  const initials = c.name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const accentColor = "#b34a1f";
  const border = c.isSubject
    ? `2px solid ${accentColor}`
    : isHovered ? "2px solid #555" : "1.5px solid #d0d0d0";
  const shadow = c.isSubject
    ? `0 2px 8px rgba(179,74,31,0.35)`
    : isHovered ? "0 2px 8px rgba(0,0,0,0.18)" : "0 1px 4px rgba(0,0,0,0.12)";

  // 20×20 favicon box so the pill width is driven by name text, not icon
  const logoHtml = faviconUrl
    ? `<img src="${faviconUrl}" alt=""
          style="width:20px;height:20px;object-fit:contain;border-radius:3px;flex-shrink:0;display:block"
          onerror="this.style.display='none'" />`
    : `<span style="width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:${c.isSubject ? accentColor : "#666"};flex-shrink:0">${initials}</span>`;

  return `
    <div style="
      display:inline-flex;align-items:center;gap:5px;
      padding:4px 8px 4px 5px;
      background:#fff;
      border:${border};
      border-radius:7px;
      box-shadow:${shadow};
      white-space:nowrap;
      cursor:pointer;
    ">
      ${logoHtml}
      <span style="
        font-family:-apple-system,BlinkMacSystemFont,sans-serif;
        font-size:11.5px;
        font-weight:${c.isSubject ? 700 : 500};
        color:${c.isSubject ? accentColor : "#1a1a1a"};
        letter-spacing:-0.02em;
        line-height:1;
      ">${c.name}</span>
    </div>
  `;
}

// Compute small lat/lng offsets for companies sharing the same city coords
function applyClusterOffsets(all) {
  // Group by rounded coords (same city = within 0.05°)
  const groups = {};
  all.forEach(c => {
    const key = `${Math.round(c.hqCoords[0] * 20)}:${Math.round(c.hqCoords[1] * 20)}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(c);
  });
  // For each group with >1 member, spread them in a row with a small lat offset
  const offsets = {};
  Object.values(groups).forEach(group => {
    if (group.length === 1) {
      offsets[group[0].id] = [0, 0];
      return;
    }
    // Sort: subject first
    group.sort((a, b) => (b.isSubject ? 1 : 0) - (a.isSubject ? 1 : 0));
    const step = 0.6; // degrees — visually ~a pill height apart at zoom 2
    group.forEach((c, i) => {
      offsets[c.id] = [i * step, 0];
    });
  });
  return offsets;
}

// ─── Single metric row inside the preview card (skips empty values) ────────────
function MapInfoRow({ label, value }) {
  if (value == null || value === "" || value === "—") return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "3px 0", fontSize: 12 }}>
      <span className="mono dim" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.03em", flexShrink: 0 }}>{label}</span>
      <span style={{ color: "var(--fg)", fontWeight: 500, textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );
}

// ─── Floating competitor preview card (hover preview / click-pinned) ───────────
function CompetitorCard({ company, pinned, onOpen, onClose, onHover }) {
  const c = company;
  const sim = c.isSubject ? null : c.similarity;
  const pricing = c.pricing ? (c.pricing.mention || c.pricing.model) : null;
  const funding = fmtFunding(c.funding);

  return (
    <div
      onMouseEnter={() => onHover(c.id)}
      onMouseLeave={() => onHover(null)}
      style={{
        width: 264,
        background: "var(--surface)",
        border: c.isSubject ? "1px solid var(--accent)" : "1px solid var(--border)",
        borderRadius: "var(--radius-lg, 10px)",
        boxShadow: "0 4px 16px rgba(0,0,0,.12)",
        overflow: "hidden",
        fontFamily: "var(--font-sans)",
      }}
    >
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "11px 12px 9px" }}>
        <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: c.isSubject ? "var(--accent)" : "var(--fg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</div>
          <div className="mono dim" style={{ fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{cleanHq(c.hq) || c.domain || ""}</div>
        </div>
        {c.threat && !c.isSubject && <ThreatTag level={c.threat} />}
        {pinned && (
          <button onClick={onClose} aria-label="Close" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--fg-3)", padding: 2, display: "flex", flexShrink: 0 }}>{Icons.x}</button>
        )}
      </div>

      {/* key metrics */}
      <div style={{ padding: "2px 12px 8px", borderTop: "1px solid var(--border-dim)" }}>
        <MapInfoRow label="Employees" value={c.employees != null ? fmtNum(c.employees) : null} />
        <MapInfoRow label="Funding" value={funding !== "—" ? funding : null} />
        <MapInfoRow label="ARR" value={c.arr != null ? fmtMoney(c.arr) : null} />
        <MapInfoRow label="Similarity" value={sim != null ? fmtPct(sim) : null} />
        <MapInfoRow label="Pricing" value={pricing} />
      </div>

      {/* top features */}
      {Array.isArray(c.top3Features) && c.top3Features.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: "0 12px 10px" }}>
          {c.top3Features.slice(0, 3).map((f, i) => (
            <span key={i} style={{ fontSize: 10, padding: "2px 7px", background: "var(--bg-2)", border: "1px solid var(--border-dim)", borderRadius: 99, color: "var(--fg-2)", whiteSpace: "nowrap" }}>{f}</span>
          ))}
        </div>
      )}

      {/* CTAs */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 12px", borderTop: "1px solid var(--border-dim)", background: "var(--surface-2, #fbfaf7)" }}>
        {!c.isSubject && (
          <button
            onClick={() => onOpen(c.id)}
            style={{ flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 5, padding: "6px 10px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: "var(--radius, 6px)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
          >
            View profile {Icons.arrowR}
          </button>
        )}
        {c.domain && (
          <a
            href={`https://${c.domain}`} target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="mono"
            style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--fg-3)", textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0, padding: c.isSubject ? "6px 0" : 0 }}
          >
            {c.domain} {Icons.ext}
          </a>
        )}
      </div>
    </div>
  );
}

function LeafletMap({ all, hovered, pinned, onHover, onSelect, onOpenCompany }) {
  const containerRef = _uR_map(null);
  const mapRef = _uR_map(null);
  const markersRef = _uR_map({});
  const [, setTick] = _uS_map(0); // bump to re-position the card on pan/zoom

  _uE_map(() => {
    if (!containerRef.current || mapRef.current) return;

    const plotted = all.filter(hasValidCoords);
    const coords = plotted.length ? plotted.map(c => c.hqCoords) : [[20, 0]];
    const avgLat = coords.reduce((s, [lat]) => s + lat, 0) / coords.length;
    const avgLng = coords.reduce((s, [, lng]) => s + lng, 0) / coords.length;

    const map = L.map(containerRef.current, {
      center: [avgLat, avgLng],
      zoom: 2,
      zoomControl: true,
      attributionControl: true,
    });

    // Light tiles without any text labels
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
      { attribution: '© <a href="https://carto.com">CARTO</a>', maxZoom: 19 }
    ).addTo(map);

    const offsets = applyClusterOffsets(plotted);

    plotted.forEach(c => {
      const [lat, lng] = c.hqCoords;
      const [dLat, dLng] = offsets[c.id] || [0, 0];
      const latlng = [lat + dLat, lng + dLng];

      const icon = L.divIcon({
        html: makeMarkerHtml(c, false),
        className: "",
        iconSize: null,       // let the pill size itself naturally
        iconAnchor: [0, 10],  // anchor left-centre of pill
      });

      const marker = L.marker(latlng, {
        icon,
        zIndexOffset: c.isSubject ? 1000 : 0,
      }).addTo(map);

      marker.on("mouseover", () => onHover(c.id));
      marker.on("mouseout", () => onHover(null));
      marker.on("click", (e) => { L.DomEvent.stopPropagation(e); onSelect(c.id); });

      markersRef.current[c.id] = { marker, company: c, latlng };
    });

    // Click empty map → dismiss any pinned card; pan/zoom → re-anchor card.
    map.on("click", () => onSelect(null));
    map.on("move zoom resize", () => setTick(t => t + 1));

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  _uE_map(() => {
    Object.entries(markersRef.current).forEach(([id, { marker, company }]) => {
      const isActive = hovered === id || pinned === id;
      const icon = L.divIcon({
        html: makeMarkerHtml(company, isActive),
        className: "",
        iconSize: null,
        iconAnchor: [0, 10],
      });
      marker.setIcon(icon);
      marker.setZIndexOffset(company.isSubject ? 1000 : isActive ? 900 : 0);
    });
  }, [hovered, pinned]);

  // Resolve which card to show (pinned wins over hover) and where to anchor it.
  const activeId = pinned || hovered;
  const entry = activeId ? markersRef.current[activeId] : null;
  let cardPos = null;
  if (entry && mapRef.current) {
    const pt = mapRef.current.latLngToContainerPoint(entry.latlng);
    const size = mapRef.current.getSize();
    const CARD_W = 264;
    let left = pt.x + 10;
    if (left + CARD_W > size.x - 8) left = pt.x - CARD_W - 10;
    if (left < 8) left = 8;
    const placeAbove = pt.y > size.y - 250;
    const top = placeAbove ? pt.y - 6 : pt.y + 24;
    cardPos = { left, top, placeAbove };
  }

  return (
    <div style={{ position: "relative", width: "100%", height: 580 }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%", background: "#f5f3ef" }} />
      {entry && cardPos && (
        <div
          style={{
            position: "absolute",
            zIndex: 400,
            left: cardPos.left,
            top: cardPos.top,
            transform: cardPos.placeAbove ? "translateY(-100%)" : "none",
          }}
        >
          <CompetitorCard
            company={entry.company}
            pinned={!!pinned}
            onOpen={onOpenCompany}
            onClose={() => onSelect(null)}
            onHover={onHover}
          />
        </div>
      )}
    </div>
  );
}

// ─── Main screen ───────────────────────────────────────────────────────────────
function MapScreen({ data, onOpenCompany }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];
  const [hovered, setHovered] = _uS_map(null);
  const [pinned, setPinned] = _uS_map(null);
  const hoverTimer = _uR_map(null);

  // Hover with a short grace delay so the mouse can travel marker → card.
  const onHover = (id) => {
    clearTimeout(hoverTimer.current);
    if (id == null) hoverTimer.current = setTimeout(() => setHovered(null), 150);
    else setHovered(id);
  };
  // Marker click toggles a pinned card; map-background click (id null) clears it.
  const onSelect = (id) => {
    clearTimeout(hoverTimer.current);
    if (id == null) { setPinned(null); return; }
    setPinned(prev => (prev === id ? null : id));
  };

  _uE_map(() => {
    const onKey = (e) => { if (e.key === "Escape") { setPinned(null); setHovered(null); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const byRegion = _uM_map(() => {
    const regions = {
      "North America": [], "Europe": [], "Asia / Pacific": [], "Latin America": [],
      "Location unknown": [],
    };
    all.forEach(c => {
      if (!hasValidCoords(c)) {
        regions["Location unknown"].push(c);
        return;
      }
      const r = getRegion(c.hqCoords[0], c.hqCoords[1]);
      regions[r].push(c);
    });
    return regions;
  }, []);

  return (
    <div className="screen">
      <SectionH
        title="Geographic distribution"
        meta={`${all.filter(hasValidCoords).length} / ${all.length} headquarters`}
      >
        <button className="tb-btn">{Icons.download}</button>
      </SectionH>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 20, alignItems: "start" }}>

        {/* Real Leaflet map */}
        <div className="card" style={{ overflow: "hidden", padding: 0 }}>
          <div className="card-h" style={{ padding: "10px 14px" }}>
            <h3>World map</h3>
            <span className="meta">Click to zoom</span>
          </div>
          <LeafletMap all={all} hovered={hovered} pinned={pinned} onHover={onHover} onSelect={onSelect} onOpenCompany={onOpenCompany} />
        </div>

        {/* Region sidebar */}
        <div className="card">
          <div className="card-h">
            <h3>By region</h3>
            <span className="meta">{Object.entries(byRegion).filter(([, v]) => v.length > 0).length} regions</span>
          </div>
          <div>
            {Object.entries(byRegion).filter(([, v]) => v.length > 0).map(([region, list], idx) => (
              <div key={region}>
                <div style={{
                  padding: "10px 14px 4px",
                  borderTop: idx > 0 ? "1px solid var(--border)" : "none",
                  display: "flex", alignItems: "baseline", justifyContent: "space-between",
                }}>
                  <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: "-0.005em" }}>{region}</span>
                  <span className="mono dim" style={{ fontSize: 10 }}>{list.length} cos.</span>
                </div>
                {list.map(c => (
                  <div key={c.id}
                    onMouseEnter={() => setHovered(c.id)}
                    onMouseLeave={() => onHover(null)}
                    onClick={() => { if (onOpenCompany && !c.isSubject) onOpenCompany(c.id); }}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "7px 14px",
                      background: hovered === c.id || pinned === c.id ? "var(--bg-2)" : "transparent",
                      cursor: c.isSubject ? "default" : "pointer",
                    }}>
                    <span className={"dot " + (c.isSubject ? "subject" : c.threat === "high" ? "high" : c.threat === "medium" ? "med" : "low")}></span>
                    <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: c.isSubject ? 600 : 500, color: c.isSubject ? "var(--accent)" : "var(--fg)" }}>
                        {c.name}
                      </div>
                      <div className="mono dim" style={{ fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{cleanHq(c.hq)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// placeholder so nothing breaks if referenced elsewhere
function OfficePresence({ all }) {
  return null;
}

window.MapScreen = MapScreen;
