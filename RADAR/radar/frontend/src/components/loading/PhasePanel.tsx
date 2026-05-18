import { PhaseStatus } from "../../types";
import { StatusIndicator } from "../ui/StatusIndicator";
import { SourcePill } from "./SourcePill";

interface PhasePanelProps {
  phase: "UNDERSTAND" | "DISCOVER" | "ENRICH";
  status: PhaseStatus;
  elapsedMs: number;
  dataPoints: { label: string; value?: string }[];
  sources: { domain: string }[];
}

const PHASE_LABELS: Record<string, string> = {
  UNDERSTAND: "Understand",
  DISCOVER: "Discover",
  ENRICH: "Enrich",
};

const STATUS_LABELS: Record<PhaseStatus, string> = {
  idle: "Pending",
  running: "In progress",
  done: "Complete",
  error: "Error",
};

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function PhasePanel({ phase, status, elapsedMs, dataPoints, sources }: PhasePanelProps) {
  const containerClass = [
    "bg-surface-panel border border-line-subtle rounded-md p-6 flex flex-col gap-4",
    status === "running" ? "border-l-2 border-l-status-active" : "",
    status === "done" ? "border-l-2 border-l-status-complete" : "",
    status === "error" ? "border-l-2 border-l-status-error" : "",
    status === "idle" ? "opacity-50" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const indicatorState =
    status === "running"
      ? "active"
      : status === "done"
      ? "complete"
      : status === "error"
      ? "live" // live state uses red in StatusIndicator via CSS? — error state: reuse pending with manual dot
      : "pending";

  return (
    <div className={containerClass}>
      {/* Header */}
      <div className="flex items-center gap-3">
        {status === "error" ? (
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-status-error" />
            <span className="font-mono text-xs tracking-wider text-fg-secondary uppercase">
              ERROR
            </span>
          </div>
        ) : (
          <StatusIndicator state={indicatorState} label={PHASE_LABELS[phase]} />
        )}

        <span className="font-mono text-xs text-fg-muted">{STATUS_LABELS[status]}</span>

        {/* Elapsed right-aligned */}
        <div className="flex-1" />
        {elapsedMs > 0 && (
          <span className="font-mono text-xs text-fg-muted tabular-nums">
            {formatElapsed(elapsedMs)}
          </span>
        )}
      </div>

      {/* Data points */}
      {dataPoints.length > 0 && (
        <ul className="flex flex-col gap-1">
          {dataPoints.map((dp, i) => (
            <li key={`${dp.label}-${i}`} className="font-mono text-sm text-fg-secondary animate-enter">
              <span className="text-fg-disabled">•</span>{" "}
              {dp.value != null ? (
                <>
                  <span>{dp.label}:</span>{" "}
                  <span className="text-fg-primary">{dp.value}</span>
                </>
              ) : (
                <span>{dp.label}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-fg-disabled">Sources:</span>
          {sources.map((s) => (
            <SourcePill key={s.domain} domain={s.domain} />
          ))}
        </div>
      )}
    </div>
  );
}
