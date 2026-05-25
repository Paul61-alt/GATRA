const SAMPLES = ["doctolib.fr", "notion.so", "linear.app", "pennylane.com", "alan.com"];

interface SampleChipsProps {
  onFill: (domain: string) => void;
}

export function SampleChips({ onFill }: SampleChipsProps) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto scrollbar-none pb-0.5">
      <span className="font-mono text-xs text-fg-disabled flex-shrink-0">Try:</span>
      {SAMPLES.map((domain) => (
        <button
          key={domain}
          type="button"
          onClick={() => onFill(domain)}
          className="font-mono text-xs border border-line-subtle bg-surface-panel rounded-sm px-2 py-1 text-fg-secondary hover:bg-surface-raised hover:border-line-default hover:text-fg-primary transition-colors duration-fast cursor-pointer whitespace-nowrap flex-shrink-0"
        >
          {domain}
        </button>
      ))}
    </div>
  );
}
