import { useReducer, useRef, useCallback } from "react";
import { PhaseState, PhaseStatus, RadarOutput } from "../types";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LogEntry {
  id: string;
  time: string; // "HH:MM"
  phase: keyof PhaseState | null;
  message: string;
}

export interface SseScanState {
  phaseStatus: PhaseState;
  elapsedMs: Record<string, number>;
  dataPoints: Record<string, { label: string; value?: string }[]>;
  sources: Record<string, { domain: string }[]>;
  logLines: LogEntry[];
  result: RadarOutput | null;
  error: string | null;
  isLoading: boolean;
  fromCache: boolean;
}

// ─── Action types ─────────────────────────────────────────────────────────────

type Action =
  | { type: "RESET" }
  | { type: "START_LOADING" }
  | { type: "SET_PHASE"; phase: keyof PhaseState; status: PhaseStatus }
  | { type: "TICK_ELAPSED"; phase: keyof PhaseState; ms: number }
  | { type: "ADD_SOURCE"; phase: keyof PhaseState; domain: string }
  | { type: "ADD_DATA_POINT"; phase: keyof PhaseState; label: string; value?: string }
  | { type: "UPDATE_DATA_POINT"; phase: keyof PhaseState; label: string; value: string }
  | { type: "SET_RESULT"; result: RadarOutput; fromCache: boolean }
  | { type: "SET_ERROR"; error: string }
  | { type: "ADD_LOG"; entry: LogEntry };

// ─── Constants ────────────────────────────────────────────────────────────────

const PHASES: (keyof PhaseState)[] = ["UNDERSTAND", "DISCOVER", "ENRICH"];
const IDLE_PHASE_STATE: PhaseState = { UNDERSTAND: "idle", DISCOVER: "idle", ENRICH: "idle" };
const IDLE_ELAPSED: Record<string, number> = { UNDERSTAND: 0, DISCOVER: 0, ENRICH: 0 };
const MAX_LOG_LINES = 200;

// ─── Initial state ────────────────────────────────────────────────────────────

const initialState: SseScanState = {
  phaseStatus: IDLE_PHASE_STATE,
  elapsedMs: { ...IDLE_ELAPSED },
  dataPoints: { UNDERSTAND: [], DISCOVER: [], ENRICH: [] },
  sources: { UNDERSTAND: [], DISCOVER: [], ENRICH: [] },
  logLines: [],
  result: null,
  error: null,
  isLoading: false,
  fromCache: false,
};

// ─── Reducer ──────────────────────────────────────────────────────────────────

function reducer(state: SseScanState, action: Action): SseScanState {
  switch (action.type) {
    case "RESET":
      return { ...initialState };

    case "START_LOADING":
      return {
        ...initialState,
        isLoading: true,
        phaseStatus: { ...IDLE_PHASE_STATE },
        elapsedMs: { ...IDLE_ELAPSED },
        dataPoints: { UNDERSTAND: [], DISCOVER: [], ENRICH: [] },
        sources: { UNDERSTAND: [], DISCOVER: [], ENRICH: [] },
        logLines: [],
      };

    case "SET_PHASE":
      return {
        ...state,
        phaseStatus: { ...state.phaseStatus, [action.phase]: action.status },
      };

    case "TICK_ELAPSED":
      return {
        ...state,
        elapsedMs: { ...state.elapsedMs, [action.phase]: action.ms },
      };

    case "ADD_SOURCE": {
      const existing = state.sources[action.phase] ?? [];
      // deduplicate by domain
      if (existing.some((s) => s.domain === action.domain)) return state;
      return {
        ...state,
        sources: {
          ...state.sources,
          [action.phase]: [...existing, { domain: action.domain }],
        },
      };
    }

    case "ADD_DATA_POINT": {
      const existing = state.dataPoints[action.phase] ?? [];
      return {
        ...state,
        dataPoints: {
          ...state.dataPoints,
          [action.phase]: [...existing, { label: action.label, value: action.value }],
        },
      };
    }

    case "UPDATE_DATA_POINT": {
      const existing = state.dataPoints[action.phase] ?? [];
      const idx = existing.findIndex((p) => p.label === action.label);
      if (idx === -1) {
        return {
          ...state,
          dataPoints: {
            ...state.dataPoints,
            [action.phase]: [...existing, { label: action.label, value: action.value }],
          },
        };
      }
      const updated = [...existing];
      updated[idx] = { ...updated[idx], value: action.value };
      return {
        ...state,
        dataPoints: { ...state.dataPoints, [action.phase]: updated },
      };
    }

    case "SET_RESULT":
      return {
        ...state,
        result: action.result,
        isLoading: false,
        fromCache: action.fromCache,
        phaseStatus: { UNDERSTAND: "done", DISCOVER: "done", ENRICH: "done" },
      };

    case "SET_ERROR":
      return {
        ...state,
        error: action.error,
        isLoading: false,
      };

    case "ADD_LOG": {
      const lines = [...state.logLines, action.entry];
      return {
        ...state,
        logLines: lines.length > MAX_LOG_LINES ? lines.slice(-MAX_LOG_LINES) : lines,
      };
    }

    default:
      return state;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function nowTime(): string {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function isValidPhase(phase: unknown): phase is keyof PhaseState {
  return PHASES.includes(phase as keyof PhaseState);
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useSseScan(apiUrl: string) {
  const logIdCounterRef = useRef(0);
  const [state, dispatch] = useReducer(reducer, initialState);

  const phaseStartRef = useRef<Record<string, number>>({});
  const timerRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  const abortRef = useRef<AbortController | null>(null);

  const clearPhaseTimer = useCallback((phase: string) => {
    if (timerRefs.current[phase]) {
      clearInterval(timerRefs.current[phase]);
      delete timerRefs.current[phase];
    }
  }, []);

  const startPhaseTimer = useCallback(
    (phase: keyof PhaseState) => {
      clearPhaseTimer(phase);
      const start = Date.now();
      phaseStartRef.current[phase] = start;
      timerRefs.current[phase] = setInterval(() => {
        const elapsed = Date.now() - start;
        dispatch({ type: "TICK_ELAPSED", phase, ms: elapsed });
      }, 100);
    },
    [clearPhaseTimer]
  );

  const stopPhaseTimer = useCallback(
    (phase: keyof PhaseState) => {
      clearPhaseTimer(phase);
      // Snap to final elapsed
      const start = phaseStartRef.current[phase];
      if (start) {
        dispatch({ type: "TICK_ELAPSED", phase, ms: Date.now() - start });
      }
    },
    [clearPhaseTimer]
  );

  const addLog = useCallback(
    (phase: keyof PhaseState | null, message: string) => {
      const id = `log-${Date.now()}-${++logIdCounterRef.current}`;
      dispatch({
        type: "ADD_LOG",
        entry: { id, time: nowTime(), phase, message },
      });
    },
    []
  );

  const run = useCallback(
    async (query: string) => {
      if (!query.trim()) return;

      // Cancel any in-flight request
      if (abortRef.current) {
        abortRef.current.abort();
      }
      abortRef.current = new AbortController();

      // Clear all timers
      PHASES.forEach(clearPhaseTimer);

      dispatch({ type: "START_LOADING" });
      addLog(null, `Initiating scan for ${query}`);

      try {
        const response = await fetch(`${apiUrl}/scan/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: query }),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `HTTP ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const STREAM_IDLE_TIMEOUT_MS = 20_000;

        while (true) {
          const readPromise = reader.read();
          const timeoutPromise = new Promise<never>((_, reject) =>
            setTimeout(
              () => reject(new Error("Stream idle — no event from backend in 20s")),
              STREAM_IDLE_TIMEOUT_MS
            )
          );
          const { done, value } = (await Promise.race([readPromise, timeoutPromise])) as ReadableStreamReadResult<Uint8Array>;
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data:")) continue;

            let event: Record<string, unknown>;
            try {
              event = JSON.parse(line.slice("data:".length).trim());
            } catch {
              continue;
            }

            // ── Error event ────────────────────────────────────────────────
            if (event.error) {
              throw new Error(event.error as string);
            }

            // ── Phase transition ───────────────────────────────────────────
            if (event.phase && isValidPhase(event.phase)) {
              const phase = event.phase as keyof PhaseState;
              const status = event.status as string;

              if (status === "start") {
                dispatch({ type: "SET_PHASE", phase, status: "running" });
                startPhaseTimer(phase);
                addLog(phase, `[${phase}] IN PROGRESS`);
              } else if (status === "ok") {
                dispatch({ type: "SET_PHASE", phase, status: "done" });
                stopPhaseTimer(phase);
                const elapsedSec = ((Date.now() - (phaseStartRef.current[phase] ?? Date.now())) / 1000).toFixed(1);
                addLog(phase, `[${phase}] Complete (${elapsedSec}s)`);
              } else if (status === "error") {
                dispatch({ type: "SET_PHASE", phase, status: "error" });
                stopPhaseTimer(phase);
                addLog(phase, `[${phase}] Error`);
              }

              // ── Progress events ──────────────────────────────────────────
              if (status === "progress") {
                const kind = event.kind as string | undefined;
                const payload = (event.payload ?? {}) as Record<string, unknown>;

                if (kind === "source_consulted") {
                  const domain = (payload.domain ?? payload.url ?? "") as string;
                  if (domain) {
                    dispatch({ type: "ADD_SOURCE", phase, domain });
                    addLog(phase, `[${phase}] Consulted: ${domain}`);
                  }
                } else if (kind === "field_extracted") {
                  const field = (payload.field ?? "") as string;
                  const val = payload.value != null ? String(payload.value) : undefined;
                  if (field) {
                    dispatch({ type: "ADD_DATA_POINT", phase, label: field, value: val });
                    addLog(
                      phase,
                      `[${phase}] Extracted: ${field}${val ? ` (${val})` : ""}`
                    );
                  }
                } else if (kind === "candidate_found") {
                  const name = (payload.name ?? "") as string;
                  const website = payload.website as string | undefined;
                  if (name) {
                    dispatch({
                      type: "ADD_DATA_POINT",
                      phase: "DISCOVER",
                      label: name,
                      value: website,
                    });
                    addLog("DISCOVER", `[DISCOVER] Candidate: ${name}${website ? ` (${website})` : ""}`);
                  }
                } else if (kind === "task_polled") {
                  const completed = payload.completed as number | undefined;
                  const total = payload.total as number | undefined;
                  if (completed != null && total != null) {
                    dispatch({
                      type: "UPDATE_DATA_POINT",
                      phase: "ENRICH",
                      label: "Tasks",
                      value: `${completed}/${total}`,
                    });
                    addLog("ENRICH", `[ENRICH] Tasks: ${completed}/${total}`);
                  }
                } else if (kind === "competitor_enriched") {
                  const name = (payload.name ?? "") as string;
                  if (name) {
                    dispatch({ type: "ADD_DATA_POINT", phase: "ENRICH", label: name });
                    addLog("ENRICH", `[ENRICH] Enriched: ${name}`);
                  }
                }
              }
            }

            // ── Final result ───────────────────────────────────────────────
            if (event.result) {
              const fromCache = (event.from_cache as boolean | undefined) === true;
              PHASES.forEach(stopPhaseTimer);
              dispatch({
                type: "SET_RESULT",
                result: event.result as RadarOutput,
                fromCache,
              });
              addLog(null, `Scan complete${fromCache ? " (cached)" : ""}`);
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        const message = err instanceof Error ? err.message : "Unknown error";
        PHASES.forEach(stopPhaseTimer);
        dispatch({ type: "SET_ERROR", error: message });
        addLog(null, `Error: ${message}`);
      }
    },
    [apiUrl, addLog, startPhaseTimer, stopPhaseTimer, clearPhaseTimer]
  );

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    PHASES.forEach(clearPhaseTimer);
    dispatch({ type: "RESET" });
  }, [clearPhaseTimer]);

  return { state, run, reset };
}
