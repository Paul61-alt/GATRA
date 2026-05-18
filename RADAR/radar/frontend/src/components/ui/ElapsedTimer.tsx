import { useState, useEffect } from "react";

interface ElapsedTimerProps {
  startedAt: number | null;
  running: boolean;
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function ElapsedTimer({ startedAt, running }: ElapsedTimerProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);

  if (startedAt === null) {
    return (
      <span className="font-mono text-sm text-fg-muted tabular-nums">
        00:00
      </span>
    );
  }

  const elapsed = running ? now - startedAt : 0;

  return (
    <span className="font-mono text-sm text-fg-muted tabular-nums">
      {formatElapsed(elapsed)}
    </span>
  );
}
