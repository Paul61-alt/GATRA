import { useEffect } from "react";

interface CacheHitBannerProps {
  domain: string;
  onDismiss: () => void;
}

export function CacheHitBanner({ domain, onDismiss }: CacheHitBannerProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 800);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="fixed inset-0 z-modal flex items-center justify-center bg-surface-base/90 animate-enter">
      <div className="bg-surface-panel border border-line-subtle rounded-md px-8 py-6 text-center space-y-2">
        <p className="font-mono text-base text-fg-muted select-none" aria-hidden>
          &gt;&gt;
        </p>
        <p className="font-mono text-xs tracking-wider text-fg-muted uppercase">
          Cached
        </p>
        <p className="font-mono text-lg font-semibold text-fg-primary">
          {domain}
        </p>
        <p className="text-sm text-fg-secondary">
          Dossier loaded from cache
        </p>
      </div>
    </div>
  );
}
