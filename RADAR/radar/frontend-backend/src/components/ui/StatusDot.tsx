type DotState = "active" | "complete" | "pending" | "error" | "live";
type DotSize = "xs" | "sm" | "md";

interface StatusDotProps {
  state: DotState;
  size?: DotSize;
}

const sizeClass: Record<DotSize, string> = {
  xs: "w-1.5 h-1.5",
  sm: "w-2 h-2",
  md: "w-2.5 h-2.5",
};

const colorClass: Record<DotState, string> = {
  active: "bg-status-active",
  complete: "bg-status-complete",
  pending: "bg-status-pending",
  error: "bg-status-error",
  live: "bg-status-active",
};

const animationClass: Record<DotState, string> = {
  active: "animate-pulse",
  complete: "",
  pending: "",
  error: "",
  live: "animate-pulse-slow",
};

export function StatusDot({ state, size = "sm" }: StatusDotProps) {
  return (
    <div
      className={[
        "rounded-full flex-shrink-0",
        sizeClass[size],
        colorClass[state],
        animationClass[state],
      ]
        .filter(Boolean)
        .join(" ")}
    />
  );
}
