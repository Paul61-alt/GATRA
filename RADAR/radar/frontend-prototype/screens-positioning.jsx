// screens-positioning.jsx — Positioning matrix tab (funding × founded year)
const { useState: _uS_pos, useEffect: _uE_pos, useRef: _uR_pos } = React;

function PositioningScreen({ data, onOpenCompany }) {
  const { subject, competitors } = data;
  const all = [subject, ...competitors];
  const canvasRef = _uR_pos(null);
  const chartRef = _uR_pos(null);
  const [selected, setSelected] = _uS_pos(null);
  const LOGO_SIZE = 28;
  const LOGO_HALF = LOGO_SIZE / 2;

  _uE_pos(() => {
    if (!canvasRef.current || typeof Chart === "undefined") return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }

    const accentColor = "#b34a1f";
    const logos = {};
    let loaded = 0;
    const total = all.length;

    function buildChart() {
      const datasets = all.map(c => ({
        label: c.name,
        data: [{
          x: c.founded || 2000,
          y: Math.max(c.funding?.total || 1, 1e5),
          _company: c,
        }],
        pointRadius: LOGO_HALF + 2,
        pointHoverRadius: LOGO_HALF + 4,
        backgroundColor: "transparent",
        borderColor: "transparent",
      }));

      const cleanTicks = [1e5, 1e6, 1e7, 5e7, 1e8, 5e8, 1e9];

      chartRef.current = new Chart(canvasRef.current, {
        type: "scatter",
        data: { datasets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 2.6,
          animation: false,
          onClick(evt) {
            if (!chartRef.current) return;
            const pts = chartRef.current.getElementsAtEventForMode(evt, "nearest", { intersect: false }, false);
            if (!pts.length) { setSelected(null); return; }
            const c = datasets[pts[0].datasetIndex].data[0]._company;
            if (onOpenCompany && !c.isSubject) { onOpenCompany(c.id); return; }
            setSelected(c);
          },
          scales: {
            x: {
              title: { display: true, text: "Founded →", font: { size: 10 }, color: "#bbb" },
              min: Math.min(...all.map(c => c.founded || 2000)) - 2,
              max: new Date().getFullYear() + 1,
              ticks: {
                callback: v => Number.isInteger(v) ? v : null,
                font: { size: 10 }, color: "#aaa",
                maxTicksLimit: 8,
                stepSize: 2,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
            },
            y: {
              type: "logarithmic",
              title: { display: true, text: "Funding raised →", font: { size: 10 }, color: "#bbb" },
              min: 5e4,
              ticks: {
                callback(v) {
                  if (cleanTicks.includes(v)) return fmtMoney(v);
                  return null;
                },
                font: { size: 10 }, color: "#aaa",
                maxTicksLimit: 7,
              },
              grid: { color: "rgba(0,0,0,0.05)" },
              afterBuildTicks(axis) {
                axis.ticks = cleanTicks
                  .filter(t => t >= axis.min && t <= axis.max * 2)
                  .map(t => ({ value: t }));
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label(ctx) {
                  const c = ctx.dataset.data[0]._company;
                  return [
                    c.name,
                    "Founded: " + (c.founded || "—"),
                    "Funding: " + fmtMoney(c.funding?.total || 0),
                  ];
                },
                title: () => "",
              },
            },
          },
        },
        plugins: [{
          id: "logoPoints",
          afterDatasetsDraw(chart) {
            const ctx2 = chart.ctx;
            chart.data.datasets.forEach((ds, i) => {
              const meta = chart.getDatasetMeta(i);
              const el = meta.data[0];
              if (!el) return;
              const c = ds.data[0]._company;
              const px = el.x, py = el.y;

              ctx2.save();
              ctx2.strokeStyle = c.isSubject ? accentColor : "#d0d0d0";
              ctx2.lineWidth = c.isSubject ? 2 : 1.5;
              ctx2.beginPath();
              ctx2.roundRect(px - LOGO_HALF - 2, py - LOGO_HALF - 2, LOGO_SIZE + 4, LOGO_SIZE + 4, 5);
              ctx2.stroke();

              const img = logos[c.id];
              if (img && img.complete && img.naturalWidth > 0) {
                ctx2.save();
                ctx2.beginPath();
                ctx2.roundRect(px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE, 4);
                ctx2.clip();
                ctx2.fillStyle = "#fff";
                ctx2.fill();
                ctx2.drawImage(img, px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE);
                ctx2.restore();
              } else {
                ctx2.fillStyle = c.isSubject ? accentColor + "22" : "rgba(0,0,0,0.08)";
                ctx2.beginPath();
                ctx2.roundRect(px - LOGO_HALF, py - LOGO_HALF, LOGO_SIZE, LOGO_SIZE, 4);
                ctx2.fill();
                ctx2.fillStyle = c.isSubject ? accentColor : "#666";
                ctx2.font = "bold 11px sans-serif";
                ctx2.textAlign = "center";
                ctx2.textBaseline = "middle";
                const parts = c.name.split(/\s+/);
                const initials = (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
                ctx2.fillText(initials, px, py);
              }
              ctx2.restore();
            });
          },
        }],
      });
    }

    all.forEach(c => {
      if (!c.domain) { loaded++; if (loaded === total) buildChart(); return; }
      const img = new Image();
      img.src = `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${c.domain}&size=64`;
      logos[c.id] = img;
      img.onload = () => {
        loaded++;
        if (loaded === total) buildChart();
        else if (chartRef.current) chartRef.current.update("none");
      };
      img.onerror = () => {
        loaded++;
        if (loaded === total) buildChart();
      };
    });
    if (all.every(c => !c.domain)) buildChart();

    return () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } };
  }, [data]);

  return (
    <div className="screen">
      <div style={{marginBottom:20}}>
        <div className="mono" style={{fontSize:10, letterSpacing:"0.14em", textTransform:"uppercase", color:"var(--fg-4)", marginBottom:8}}>
          Competitive Intelligence
        </div>
        <h1 className="serif" style={{fontSize:26, fontWeight:500, letterSpacing:"-0.02em", margin:0}}>
          Positioning
        </h1>
        <p style={{color:"var(--fg-3)", fontSize:13, marginTop:6, marginBottom:0}}>
          Funding raised (log scale) vs. founded year — click any logo to open the company profile.
        </p>
      </div>

      <div className="card">
        <div className="card-h">
          <h3>Funding × Age</h3>
          <span className="meta">{all.length} companies</span>
        </div>
        <div style={{padding:"16px 16px 8px"}}>
          <canvas ref={canvasRef} />
        </div>
        {selected && (
          <div style={{
            margin:"0 16px 14px", padding:"12px 14px",
            background:"var(--bg-2)", borderRadius:6,
            border:"1px solid var(--border)",
            display:"flex", alignItems:"center", gap:14,
          }}>
            <LogoMark name={selected.name} domain={selected.domain} subject={selected.isSubject} />
            <div style={{flex:1, minWidth:0}}>
              <div style={{fontWeight:600, fontSize:13}}>{selected.name}</div>
              <div className="mono" style={{fontSize:11, color:"var(--fg-3)", marginTop:2}}>
                {selected.subCategory} · Founded {selected.founded || "—"} · {fmtMoney(selected.funding?.total || 0)} raised
              </div>
            </div>
            {!selected.isSubject && <ThreatTag level={selected.threat} />}
            <button onClick={() => setSelected(null)} style={{background:"none", border:"none", cursor:"pointer", color:"var(--fg-4)"}}>
              {Icons.x}
            </button>
          </div>
        )}
        <div style={{display:"flex", gap:16, padding:"0 16px 12px", fontSize:11, color:"var(--fg-3)"}}>
          <span>Click a logo to open company profile</span>
          <span style={{marginLeft:"auto"}}>
            <span style={{display:"inline-block", width:10, height:10, border:"2px solid #b34a1f", borderRadius:2, marginRight:4}}></span>Subject
          </span>
        </div>
      </div>
    </div>
  );
}

window.PositioningScreen = PositioningScreen;
