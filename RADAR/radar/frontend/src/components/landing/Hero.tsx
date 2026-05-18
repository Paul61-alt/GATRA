import { FormEvent } from "react";
import { SampleChips } from "./SampleChips";

interface HeroProps {
  url: string;
  setUrl: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onRunQuery: (query: string) => void;
  disabled: boolean;
}

export function Hero({ url, setUrl, onSubmit, onRunQuery, disabled }: HeroProps) {
  function handleFill(domain: string) {
    setUrl(domain);
    onRunQuery(domain);
  }

  return (
    <main className="relative z-base flex flex-col items-center justify-center min-h-screen px-4 md:px-0 pb-16 pt-10">
      <div className="w-full max-w-2xl space-y-6">
        {/* Eyebrow */}
        <p className="font-mono text-xs tracking-wider text-fg-muted uppercase text-center">
          Competitive Intelligence
        </p>

        {/* Headline */}
        <h1 className="font-sans text-2xl md:text-3xl font-bold leading-tight tracking-tight text-fg-primary text-center">
          Find every competitor of any company.
        </h1>

        {/* Subhead */}
        <p className="text-sm md:text-base text-fg-secondary text-center leading-normal">
          Live intelligence pulled from primary sources. No black box.
        </p>

        {/* Search input */}
        <form onSubmit={onSubmit} className="mt-8">
          <div className="flex items-center h-14 md:h-16 bg-surface-inset border border-line-subtle rounded-md focus-within:border-line-strong focus-within:shadow-focus transition-colors duration-fast">
            <span className="pl-4 pr-2 font-mono text-fg-muted select-none" aria-hidden>▸</span>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Enter company domain — e.g., doctolib.fr"
              aria-label="Company domain"
              disabled={disabled}
              className="flex-1 h-full bg-transparent font-mono text-base text-fg-primary placeholder-fg-muted focus:outline-none disabled:opacity-50"
              autoFocus
            />
            <button
              type="submit"
              disabled={disabled || !url.trim()}
              className="mr-2 h-12 px-4 bg-accent-500 hover:bg-accent-600 active:bg-accent-700 text-fg-primary font-mono font-medium text-sm tracking-wide rounded-sm disabled:opacity-40 transition-colors duration-fast whitespace-nowrap"
            >
              {disabled ? "Analyzing" : "RUN ANALYSIS →"}
            </button>
          </div>
        </form>

        {/* Metadata line */}
        <div className="flex flex-col items-center gap-3">
          <p className="font-mono text-sm text-fg-muted">
            5 recent reports cached · ~95s avg time to result
          </p>
          <SampleChips onFill={handleFill} />
        </div>
      </div>
    </main>
  );
}
