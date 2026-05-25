import { StatusIndicator } from "../ui/StatusIndicator";

export function TopBar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-elevated h-10 flex items-center justify-between px-4 border-b border-line-subtle bg-surface-base">
      <span className="font-mono font-semibold tracking-tight text-fg-primary">
        RADAR
      </span>
      <div className="flex items-center gap-4">
        <StatusIndicator state="live" label="OPERATIONAL" />
        <span className="hidden md:inline font-mono text-xs text-fg-disabled">v0.3</span>
      </div>
    </header>
  );
}
