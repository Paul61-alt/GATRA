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
      cursor:default;
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

function LeafletMap({ all, hovered, onHover }) {
  const containerRef = _uR_map(null);
  const mapRef = _uR_map(null);
  const markersRef = _uR_map({});

  _uE_map(() => {
    if (!containerRef.current || mapRef.current) return;

    const coords = all.map(c => c.hqCoords);
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

    const offsets = applyClusterOffsets(all);

    all.forEach(c => {
      const [lat, lng] = c.hqCoords;
      const [dLat, dLng] = offsets[c.id] || [0, 0];

      const icon = L.divIcon({
        html: makeMarkerHtml(c, false),
        className: "",
        iconSize: null,       // let the pill size itself naturally
        iconAnchor: [0, 10],  // anchor left-centre of pill
      });

      const marker = L.marker([lat + dLat, lng + dLng], {
        icon,
        zIndexOffset: c.isSubject ? 1000 : 0,
      }).addTo(map);

      marker.on("mouseover", () => onHover(c.id));
      marker.on("mouseout", () => onHover(null));

      markersRef.current[c.id] = { marker, company: c };
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  _uE_map(() => {
    Object.entries(markersRef.current).forEach(([id, { marker, company }]) => {
      const isHovered = hovered === id;
      const icon = L.divIcon({
        html: makeMarkerHtml(company, isHovered),
        className: "",
        iconSize: null,
        iconAnchor: [0, 10],
      });
      marker.setIcon(icon);
      marker.setZIndexOffset(company.isSubject ? 1000 : isHovered ? 900 : 0);
    });
  }, [hovered]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: 580, background: "#f5f3ef", borderRadius: 0 }}
    />
  );
}

// ─── Main screen ───────────────────────────────────────────────────────────────
function MapScreen({ data }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];
  const [hovered, setHovered] = _uS_map(null);

  const byRegion = _uM_map(() => {
    const regions = { "North America": [], "Europe": [], "Asia / Pacific": [], "Latin America": [] };
    all.forEach(c => {
      const r = getRegion(c.hqCoords[0], c.hqCoords[1]);
      regions[r].push(c);
    });
    return regions;
  }, []);

  return (
    <div className="screen">
      <SectionH
        title="Geographic distribution"
        meta={`${all.length} headquarters`}
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
          <LeafletMap all={all} hovered={hovered} onHover={setHovered} />
        </div>

        {/* Region sidebar */}
        <div className="card">
          <div className="card-h">
            <h3>By region</h3>
            <span className="meta">{Object.keys(byRegion).length} regions</span>
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
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "7px 14px",
                      background: hovered === c.id ? "var(--bg-2)" : "transparent",
                      cursor: "default",
                    }}>
                    <span className={"dot " + (c.isSubject ? "subject" : c.threat === "high" ? "high" : c.threat === "medium" ? "med" : "low")}></span>
                    <LogoMark name={c.name} domain={c.domain} subject={c.isSubject} size="sm" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: c.isSubject ? 600 : 500, color: c.isSubject ? "var(--accent)" : "var(--fg)" }}>
                        {c.name}
                      </div>
                      <div className="mono dim" style={{ fontSize: 10 }}>{c.hq}</div>
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
