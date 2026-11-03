import type { FC, ReactNode } from 'react'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export const EmptyState: FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div
      className={`empty-state ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        textAlign: 'center',
        background: 'var(--bg-card)',
        border: '1px dashed var(--border-main)',
        borderRadius: 'var(--radius-md, 8px)',
        color: 'var(--text-muted)',
      }}
    >
      {icon && (
        <div style={{
          marginBottom: '14px',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {icon}
        </div>
      )}
      <h3 style={{
        fontSize: '15px',
        fontWeight: 600,
        color: 'var(--text-main)',
        margin: '0 0 6px 0',
      }}>
        {title}
      </h3>
      {description && (
        <p style={{
          fontSize: '12.5px',
          color: 'var(--text-secondary)',
          maxWidth: '420px',
          margin: '0 0 16px 0',
          lineHeight: 1.5,
        }}>
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  )
}
