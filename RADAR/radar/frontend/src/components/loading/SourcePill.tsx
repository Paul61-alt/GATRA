import { useState } from "react";

interface SourcePillProps {
  domain: string;
}

export function SourcePill({ domain }: SourcePillProps) {
  const resolvedFavicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;
  const [faviconError, setFaviconError] = useState(false);

  return (
    <button
      type="button"
      onClick={() => window.open(`https://${domain}`, "_blank", "noopener,noreferrer")}
      className="inline-flex items-center gap-1.5 bg-surface-panel border border-line-subtle rounded-sm px-2 py-0.5 font-mono text-xs text-fg-muted cursor-pointer hover:bg-surface-raised hover:text-fg-secondary transition-colors duration-fast"
    >
      {!faviconError && (
        <img
          src={resolvedFavicon}
          alt=""
          width={14}
          height={14}
          className="flex-shrink-0"
          onError={() => setFaviconError(true)}
        />
      )}
      <span>{domain}</span>
    </button>
  );
}
