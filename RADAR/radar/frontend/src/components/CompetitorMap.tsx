import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { CompetitorProfile } from "../types";

const STAGE_COLORS: Record<string, string> = {
  seed: "#4ade80",
  "series a": "#60a5fa",
  "series b": "#c084fc",
  "series c+": "#fb923c",
  public: "#fbbf24",
  bootstrapped: "#94a3b8",
};

function stageColor(stage: string | null): string {
  if (!stage) return "#94a3b8";
  const key = stage.toLowerCase();
  return (
    Object.entries(STAGE_COLORS).find(([k]) => key.includes(k))?.[1] ?? "#94a3b8"
  );
}

interface Props {
  competitors: CompetitorProfile[];
}

export function CompetitorMap({ competitors }: Props) {
  const mapped = competitors.filter((c) => c.hq?.lat && c.hq?.lng);

  if (!mapped.length) return null;

  const avgLat = mapped.reduce((s, c) => s + c.hq!.lat!, 0) / mapped.length;
  const avgLng = mapped.reduce((s, c) => s + c.hq!.lng!, 0) / mapped.length;

  return (
    <div className="h-80 rounded-lg overflow-hidden border border-[#222]">
      <MapContainer
        center={[avgLat, avgLng]}
        zoom={3}
        style={{ height: "100%", width: "100%", background: "#0a0a0f" }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com">CARTO</a>'
        />
        {mapped.map((c) => (
          <CircleMarker
            key={c.website}
            center={[c.hq!.lat!, c.hq!.lng!]}
            radius={8}
            pathOptions={{
              color: stageColor(c.funding_stage?.value as string | null),
              fillColor: stageColor(c.funding_stage?.value as string | null),
              fillOpacity: 0.8,
              weight: 1,
            }}
          >
            <Tooltip>
              <span className="font-semibold">{c.name}</span>
              <br />
              {c.hq?.city}, {c.hq?.country}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
