import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertOctagon, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
  fallbackMessage?: string
  onReset?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '32px 24px',
            background: 'var(--bg-card, rgba(15, 23, 42, 0.75))',
            border: '1px solid var(--border-danger, rgba(239, 68, 68, 0.3))',
            borderRadius: 'var(--radius-md, 12px)',
            color: 'var(--text-main, #f8fafc)',
            textAlign: 'center',
            minHeight: '220px',
            gap: '14px',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ef4444',
            }}
          >
            <AlertOctagon size={24} />
          </div>
          <div>
            <h4 style={{ margin: '0 0 6px 0', fontSize: '16px', fontWeight: 600 }}>
              {this.props.fallbackTitle || 'Component Render Interrupted'}
            </h4>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted, #94a3b8)', maxWidth: '420px' }}>
              {this.props.fallbackMessage ||
                this.state.error?.message ||
                'A rendering fault or WebGL context error occurred in this view module.'}
            </p>
          </div>
          <button
            onClick={this.handleReset}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm, 6px)',
              background: 'var(--bg-subtle, rgba(30, 41, 59, 0.8))',
              border: '1px solid var(--border-main, rgba(148, 163, 184, 0.2))',
              color: 'var(--text-main, #f8fafc)',
              fontSize: '13px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            <RefreshCw size={13} />
            <span>Reset View</span>
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
