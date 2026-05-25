import { useCallback, useEffect, useRef, useState } from "react";
import { LogEntry } from "../../hooks/useSseScan";
import { PhaseState } from "../../types";

interface LiveLogProps {
  lines: LogEntry[];
  maxLines?: number;
}

const PHASE_KEYS: (keyof PhaseState)[] = ["UNDERSTAND", "DISCOVER", "ENRICH"];

function isPhaseKey(phase: unknown): phase is keyof PhaseState {
  return PHASE_KEYS.includes(phase as keyof PhaseState);
}

export function LiveLog({ lines, maxLines = 200 }: LiveLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const displayLines = lines.slice(-maxLines);

  // Auto-scroll on new lines
  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [displayLines.length, autoScroll]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
    setAutoScroll(atBottom);
  }, []);

  return (
    <div className="bg-surface-panel border border-line-subtle rounded-md">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-line-subtle">
        <span className="font-mono text-xs tracking-wider text-fg-muted uppercase">
          Live Log
        </span>
        <button
          type="button"
          onClick={() => {
            setAutoScroll((v) => !v);
            if (!autoScroll && scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="font-mono text-xs text-fg-disabled hover:text-fg-muted transition-colors duration-fast"
        >
          {autoScroll ? "▼ AUTO" : "● PAUSED"}
        </button>
      </div>

      {/* Log body */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="max-h-48 overflow-y-auto px-4 py-3 flex flex-col gap-0.5"
      >
        {displayLines.length === 0 && (
          <span className="font-mono text-xs text-fg-disabled">Waiting for events…</span>
        )}
        {displayLines.map((line) => (
          <div key={line.id} className="font-mono text-xs text-fg-secondary animate-enter">
            <span className="text-fg-disabled">{line.time}</span>{" "}
            {line.phase && isPhaseKey(line.phase) && (
              <span className="text-status-active">[{line.phase}]</span>
            )}{" "}
            <span className="text-fg-secondary">{line.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
