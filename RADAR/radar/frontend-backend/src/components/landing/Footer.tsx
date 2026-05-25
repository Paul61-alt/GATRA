const CAPABILITIES = [
  "Company profile",
  "Competitor map",
  "Funding signals",
  "Pricing intel",
];

export function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 z-elevated flex flex-col items-center gap-3 px-4 py-4 border-t border-line-subtle bg-surface-base">
      <p className="font-mono text-xs text-fg-disabled">
        Powered by Linkup · Claude Sonnet 4
        <span className="mx-2 text-fg-disabled">·</span>
        <span className="text-fg-muted">View methodology →</span>
      </p>
      <div className="hidden md:flex flex-wrap justify-center gap-2">
        {CAPABILITIES.map((cap) => (
          <span
            key={cap}
            className="font-mono text-xs border border-line-subtle rounded-sm px-2 py-0.5 text-fg-disabled"
          >
            {cap}
          </span>
        ))}
      </div>
    </footer>
  );
}
