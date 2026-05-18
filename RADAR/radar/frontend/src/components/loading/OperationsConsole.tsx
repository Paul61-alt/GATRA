import { useEffect, useRef } from "react";
import { RadarOutput } from "../../types";
import { useSseScan } from "../../hooks/useSseScan";
import { CommandBar } from "./CommandBar";
import { PhasePanel } from "./PhasePanel";
import { LiveLog } from "./LiveLog";

interface OperationsConsoleProps {
  query: string;
  apiUrl: string;
  onResult: (result: RadarOutput) => void;
  onError: (err: string) => void;
}

export function OperationsConsole({
  query,
  apiUrl,
  onResult,
  onError,
}: OperationsConsoleProps) {
  const { state, run } = useSseScan(apiUrl);

  // Start scan on mount
  const hasStarted = useRef(false);
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;
    run(query);
  }, [query, run]);

  // Notify parent when result arrives — after 400ms so user sees COMPLETE briefly
  const resultHandled = useRef(false);
  useEffect(() => {
    if (state.result && !resultHandled.current) {
      resultHandled.current = true;
      const timer = setTimeout(() => {
        onResult(state.result!);
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [state.result, onResult]);

  // Notify parent on error
  const errorHandled = useRef(false);
  useEffect(() => {
    if (state.error && !errorHandled.current) {
      errorHandled.current = true;
      onError(state.error);
    }
  }, [state.error, onError]);

  const { phaseStatus, elapsedMs, dataPoints, sources, logLines, result, error } = state;

  const totalElapsed =
    (elapsedMs["UNDERSTAND"] ?? 0) +
    (elapsedMs["DISCOVER"] ?? 0) +
    (elapsedMs["ENRICH"] ?? 0);

  const commandBarPhase: "analyzing" | "complete" | "error" = error
    ? "error"
    : result
    ? "complete"
    : "analyzing";

  return (
    <div className="min-h-screen bg-surface-base text-fg-primary">
      <CommandBar
        domain={query}
        phase={commandBarPhase}
        elapsedMs={totalElapsed}
      />

      <main className="pt-12 max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <PhasePanel
            phase="UNDERSTAND"
            status={phaseStatus.UNDERSTAND}
            elapsedMs={elapsedMs["UNDERSTAND"] ?? 0}
            dataPoints={dataPoints["UNDERSTAND"] ?? []}
            sources={sources["UNDERSTAND"] ?? []}
          />
          <PhasePanel
            phase="DISCOVER"
            status={phaseStatus.DISCOVER}
            elapsedMs={elapsedMs["DISCOVER"] ?? 0}
            dataPoints={dataPoints["DISCOVER"] ?? []}
            sources={sources["DISCOVER"] ?? []}
          />
          <PhasePanel
            phase="ENRICH"
            status={phaseStatus.ENRICH}
            elapsedMs={elapsedMs["ENRICH"] ?? 0}
            dataPoints={dataPoints["ENRICH"] ?? []}
            sources={sources["ENRICH"] ?? []}
          />
        </div>

        <LiveLog lines={logLines} />
      </main>
    </div>
  );
}
