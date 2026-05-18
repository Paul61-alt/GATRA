type StatusIndicatorState = "live" | "active" | "complete" | "pending" | "error";

interface StatusIndicatorProps {
  state?: StatusIndicatorState;
  label: string;
}

const dotClass: Record<StatusIndicatorState, string> = {
  live: "bg-status-active animate-pulse-slow",
  active: "bg-status-active animate-pulse",
  complete: "bg-status-complete",
  pending: "bg-status-pending",
  error: "bg-status-error",
};

export function StatusIndicator({ state = "live", label }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-1.5 h-1.5 rounded-full ${dotClass[state]}`} />
      <span className="font-mono text-xs tracking-wider text-fg-secondary uppercase">
        {label}
      </span>
    </div>
  );
}
