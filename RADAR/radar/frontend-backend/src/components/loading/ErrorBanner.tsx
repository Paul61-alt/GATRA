interface ErrorBannerProps {
  message: string;
  onRetry: () => void;
  onReset: () => void;
}

export function ErrorBanner({ message, onRetry, onReset }: ErrorBannerProps) {
  return (
    <div className="fixed top-10 left-0 right-0 z-dropdown animate-enter bg-tint-error border-b border-status-error/30 px-4 py-3 flex items-center gap-4">
      {/* Left: dot + message */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <div className="w-1.5 h-1.5 rounded-full bg-status-error flex-shrink-0" />
        <span className="font-mono text-sm text-status-error truncate">{message}</span>
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          type="button"
          onClick={onRetry}
          className="font-mono text-xs px-3 py-1.5 rounded-sm border border-line-default bg-surface-panel text-fg-primary hover:bg-surface-raised transition-colors duration-fast"
        >
          Retry
        </button>
        <button
          type="button"
          onClick={onReset}
          className="font-mono text-xs px-3 py-1.5 text-fg-muted hover:text-fg-primary transition-colors duration-fast"
        >
          New analysis
        </button>
      </div>
    </div>
  );
}
