import { StatusIndicator } from "../ui/StatusIndicator";

interface CommandBarProps {
  domain: string;
  phase: "analyzing" | "complete" | "error";
  elapsedMs: number;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function CommandBar({ domain, phase, elapsedMs }: CommandBarProps) {
  const indicatorState =
    phase === "analyzing" ? "active" : phase === "complete" ? "complete" : "error";

  const indicatorLabel =
    phase === "analyzing" ? "ANALYZING" : phase === "complete" ? "COMPLETE" : "FAILED";

  return (
    <div className="fixed top-0 left-0 right-0 z-elevated h-12 bg-surface-panel border-b border-line-subtle flex items-center px-6 gap-3">
      {/* Wordmark */}
      <span className="font-mono font-semibold tracking-tight text-fg-primary">RADAR</span>

      <span className="text-fg-disabled">·</span>

      {/* Domain */}
      <span className="font-mono text-fg-secondary text-sm">{domain}</span>

      <span className="text-fg-disabled">·</span>

      {/* Status */}
      <StatusIndicator state={indicatorState} label={indicatorLabel} />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Elapsed timer */}
      <span className="font-mono text-fg-muted text-xs tabular-nums">{formatElapsed(elapsedMs)}</span>
    </div>
  );
}
