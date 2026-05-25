// screens-map.jsx â geographic distribution of competitors
const { useState: _uS_map, useMemo: _uM_map } = React;

// Simplified continent paths (Mercator approximation, 960 Ã 480)
// Stylised abstract silhouettes â not a topographic map.
const CONTINENTS = [
  // North America
  "M120,90 q-20,8 -28,28 q-4,18 4,40 q-8,12 -2,28 q4,12 16,18 q14,8 30,8 q18,2 36,-4 q14,-2 26,-12 q22,-2 36,12 q12,10 30,12 q14,2 28,-6 q16,-6 22,-22 q4,-12 -4,-26 q4,-14 -10,-22 q-8,-12 -22,-12 q-22,-12 -46,-12 q-26,-4 -54,-4 q-30,0 -50,4 q-6,-12 -12,-12 z",
  // Central America (small isthmus)
  "M210,200 q-6,4 -10,16 q0,16 8,28 q10,16 22,18 q12,2 18,-4 q4,-12 -2,-22 q-6,-16 -14,-26 q-10,-12 -22,-10 z",
  // South America
  "M260,250 q-14,4 -22,20 q-12,28 -16,60 q-4,30 4,60 q4,28 18,40 q14,10 26,2 q14,-10 18,-32 q10,-26 14,-58 q4,-30 -4,-58 q-6,-22 -16,-30 q-10,-8 -22,-4 z",
  // Europe
  "M460,90 q-14,4 -16,18 q-2,16 8,24 q4,12 18,16 q14,4 30,2 q16,-2 26,-12 q14,-2 22,-14 q6,-12 -2,-22 q-12,-12 -28,-12 q-22,-4 -42,-2 q-10,0 -16,2 z",
  // Africa
  "M470,160 q-12,8 -18,28 q-8,24 -8,52 q0,32 12,58 q14,28 32,32 q22,4 36,-12 q14,-14 18,-40 q8,-28 4,-58 q-2,-26 -16,-44 q-12,-14 -28,-18 q-18,-2 -32,2 z",
  // Asia (large blob)
  "M540,80 q-18,4 -26,18 q-6,16 0,30 q6,18 22,24 q-4,12 4,24 q10,16 30,20 q22,4 44,2 q24,4 48,2 q26,-2 50,-10 q22,-2 38,-14 q18,-10 24,-26 q6,-16 -2,-32 q-4,-16 -22,-22 q-22,-14 -52,-18 q-32,-6 -64,-4 q-30,-2 -56,2 q-20,0 -34,4 q-2,0 -4,0 z",
  // SE Asia + islands
  "M700,210 q-14,4 -18,18 q-2,16 10,24 q14,12 32,10 q18,2 30,-8 q12,-10 12,-22 q-2,-14 -16,-20 q-22,-6 -36,-4 q-8,0 -14,2 z",
  // Australia
  "M770,290 q-14,2 -22,14 q-6,16 4,28 q12,16 32,16 q22,2 38,-8 q16,-8 16,-22 q-2,-14 -16,-22 q-22,-8 -38,-8 q-8,0 -14,2 z",
  // UK / Ireland
  "M448,98 q-6,2 -8,10 q-2,10 4,16 q8,8 16,4 q6,-4 6,-12 q-2,-10 -10,-16 q-4,-2 -8,-2 z",
  // Japan
  "M850,140 q-4,2 -6,10 q0,10 6,18 q8,12 14,8 q6,-2 6,-12 q-2,-12 -8,-20 q-6,-6 -12,-4 z",
  // New Zealand
  "M870,330 q-4,2 -4,10 q0,10 6,12 q8,4 12,-2 q4,-6 0,-14 q-4,-8 -10,-8 q-2,0 -4,2 z",
];

// Lat/long â x/y on 960Ã480 equirectangular
function project(lat, lng) {
  const x = ((lng + 180) / 360) * 960;
  const y = ((90 - lat) / 180) * 480;
  return [x, y];
}

function MapScreen({ data }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];
  const [hovered, setHovered] = _uS_map(null);

  // Cluster by HQ for the side list
  const byRegion = _uM_map(() => {
    const regions = {
      "North America": [],
      "Europe": [],
      "Asia / Pacific": [],
      "Latin America": [],
    };
    const region = (lat, lng) => {
      if (lng > -30 && lng < 50 && lat > 30) return "Europe";
      if (lng > 50) return "Asia / Pacific";
      if (lat < 15) return "Latin America";
      return "North America";
    };
    all.forEach(c => {
      const r = region(c.hqCoords[0], c.hqCoords[1]);
      regions[r].push(c);
    });
    return regions;
  }, []);

  return (
    <div className="screen">
      <SectionH title="Geographic distribution" meta={`${all.length} headquarters Â· ${all.flatMap(c => c.offices).length} offices`}>
        <button className="tb-btn">{Icons.globe}<span>Toggle offices</span></button>
        <button className="tb-btn">{Icons.download}</button>
      </SectionH>

      <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap: 20, alignItems:"start"}}>

        {/* Map */}
        <div className="card" style={{overflow:"hidden"}}>
          <div className="card-h">
            <h3>World map</h3>
            <span className="meta">Equirectangular Â· stylised</span>
          </div>
          <div style={{padding: 10, background: "var(--bg-2)"}}>
            <svg viewBox="0 0 960 480" style={{width:"100%", height:"auto", display:"block", background: "var(--bg)"}}>
              {/* Grid */}
              <g stroke="var(--border-dim)" strokeWidth="0.5">
                {[-60,-30,0,30,60].map(lat => {
                  const y = ((90 - lat) / 180) * 480;
                  return <line key={lat} x1="0" x2="960" y1={y} y2={y} strokeDasharray={lat === 0 ? "none" : "1 4"}/>;
                })}
                {[-150,-120,-90,-60,-30,0,30,60,90,120,150].map(lng => {
                  const x = ((lng + 180) / 360) * 960;
                  return <line key={lng} x1={x} x2={x} y1="0" y2="480" strokeDasharray={lng === 0 ? "none" : "1 4"}/>;
                })}
              </g>

              {/* Lat/long labels */}
              <g fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-4)">
                <text x="6" y={(90/180)*480 + 4}>0Â°</text>
                <text x="6" y={(60/180)*480 + 4}>30Â°N</text>
                <text x="6" y={(120/180)*480 + 4}>30Â°S</text>
              </g>

              {/* Continents */}
              <g fill="var(--bg-3)" stroke="var(--border-strong)" strokeWidth="0.5">
                {CONTINENTS.map((d, i) => <path key={i} d={d}/>)}
              </g>

              {/* HQ pins */}
              {all.map(c => {
                const [x, y] = project(c.hqCoords[0], c.hqCoords[1]);
                const isS = c.isSubject;
                const isH = hovered === c.id;
                return (
                  <g key={c.id} transform={`translate(${x},${y})`}
                     onMouseEnter={() => setHovered(c.id)}
                     onMouseLeave={() => setHovered(null)}
                     style={{cursor:"default"}}>
                    {/* halo */}
                    <circle r={isS ? 18 : 12}
                            fill={isS ? "var(--accent)" : "var(--fg)"}
                            fillOpacity={isS ? 0.18 : 0.10}/>
                    <circle r={isS ? 6 : 4.5}
                            fill={isS ? "var(--accent)" : "var(--fg)"}
                            stroke="#fff" strokeWidth="1.5"/>
                    {(isS || isH) && (
                      <g>
                        <rect x="9" y="-12" width={c.name.length * 6.4 + 14} height="20"
                              rx="3" fill="#fff" stroke="var(--border-strong)" strokeWidth="0.5"/>
                        <text x="16" y="2"
                              fontFamily="var(--font-sans)"
                              fontSize="11"
                              fontWeight={isS ? 600 : 500}
                              fill={isS ? "var(--accent)" : "var(--fg)"}>
                          {c.name}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Region list */}
        <div className="card">
          <div className="card-h">
            <h3>By region</h3>
            <span className="meta">{Object.keys(byRegion).length} regions</span>
          </div>
          <div>
            {Object.entries(byRegion).filter(([_,v]) => v.length > 0).map(([region, list], idx) => (
              <div key={region}>
                <div style={{
                  padding:"10px 14px 4px",
                  borderTop: idx > 0 ? "1px solid var(--border)" : "none",
                  display:"flex", alignItems:"baseline", justifyContent:"space-between",
                }}>
                  <span style={{fontSize:11.5, fontWeight:600, letterSpacing:"-0.005em"}}>{region}</span>
                  <span className="mono dim" style={{fontSize:10}}>{list.length} cos.</span>
                </div>
                {list.map(c => (
                  <div key={c.id}
                       onMouseEnter={() => setHovered(c.id)}
                       onMouseLeave={() => setHovered(null)}
                       style={{
                         display:"flex", alignItems:"center", gap:10,
                         padding:"7px 14px",
                         background: hovered === c.id ? "var(--bg-2)" : "transparent",
                       }}>
                    <span className={"dot " + (c.isSubject ? "subject" : c.threat === "high" ? "high" : c.threat === "medium" ? "med" : "low")}></span>
                    <LogoMark name={c.name} subject={c.isSubject} size="sm" />
                    <div style={{flex:1, minWidth:0}}>
                      <div style={{fontSize:12.5, fontWeight: c.isSubject ? 600 : 500, color: c.isSubject ? "var(--accent)" : "var(--fg)"}}>{c.name}</div>
                      <div className="mono dim" style={{fontSize:10}}>{c.hq}</div>
                    </div>
                    <span className="mono dim" style={{fontSize:10}}>{c.offices.length} off.</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Office count by city */}
      <div style={{height: 20}}></div>
      <div className="card">
        <div className="card-h">
          <h3>Office presence</h3>
          <span className="meta">All offices across {all.length} companies</span>
        </div>
        <div style={{padding: 16}}>
          <OfficePresence all={all} />
        </div>
      </div>
    </div>
  );
}

// âââ Office presence: cities Ã companies grid ââââââââââââââââ
function OfficePresence({ all }) {
  // Collect all unique cities
  const cities = [...new Set(all.flatMap(c => c.offices))];

  return (
    <div style={{overflowX:"auto"}}>
      <table className="tbl" style={{minWidth: 800}}>
        <thead>
          <tr>
            <th style={{position:"sticky", left:0, background:"var(--bg-2)", zIndex:1}}>City</th>
            {all.map(c => (
              <th key={c.id} style={{textAlign:"center", padding: "8px 4px", minWidth: 36}}>
                <div style={{
                  writingMode: "vertical-rl",
                  transform: "rotate(180deg)",
                  height: 60, display:"inline-flex", alignItems:"center",
                  fontWeight: c.isSubject ? 600 : 500,
                  color: c.isSubject ? "var(--accent)" : "var(--fg-3)",
                  fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: 0,
                  textTransform: "none",
                }}>
                  {c.name}
                </div>
              </th>
            ))}
            <th className="num" style={{textAlign:"right"}}>Total</th>
          </tr>
        </thead>
        <tbody>
          {cities.map(city => {
            const total = all.filter(c => c.offices.includes(city)).length;
            return (
              <tr key={city}>
                <td style={{position:"sticky", left:0, background:"var(--surface)", zIndex:1, fontWeight:500}}>
                  {city}
                </td>
                {all.map(c => {
                  const has = c.offices.includes(city);
                  return (
                    <td key={c.id} style={{textAlign:"center", padding:"0"}}>
                      {has ? (
                        <span style={{
                          display:"inline-block",
                          width:8, height:8, borderRadius:2,
                          background: c.isSubject ? "var(--accent)" : "var(--fg-2)",
                        }}></span>
                      ) : (
                        <span className="dim">Â·</span>
                      )}
                    </td>
                  );
                })}
                <td className="num">{total}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

window.MapScreen = MapScreen;
