import type { FC } from 'react'
import { AlertCircle, RefreshCw, X } from 'lucide-react'

interface ErrorBannerProps {
  message: string
  onRetry?: () => void
  onDismiss?: () => void
  className?: string
}

export const ErrorBanner: FC<ErrorBannerProps> = ({
  message,
  onRetry,
  onDismiss,
  className = '',
}) => {
  return (
    <div
      className={`error-banner ${className}`}
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        padding: '10px 14px',
        background: 'var(--status-critical-bg)',
        border: '1px solid var(--status-critical-border)',
        borderRadius: 'var(--radius-sm, 6px)',
        color: 'var(--status-critical)',
        fontSize: '12.5px',
        marginBottom: '16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <AlertCircle size={16} style={{ flexShrink: 0 }} />
        <span style={{ fontWeight: 500 }}>{message}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--status-critical)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11.5px',
              fontWeight: 600,
              textDecoration: 'underline',
              padding: '2px 4px',
            }}
          >
            <RefreshCw size={12} />
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            aria-label="Dismiss error"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--status-critical)',
              display: 'flex',
              alignItems: 'center',
              padding: '2px',
            }}
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
