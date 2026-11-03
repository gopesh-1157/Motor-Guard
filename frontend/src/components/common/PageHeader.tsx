import type { FC, ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  badge?: ReactNode
  actions?: ReactNode
  className?: string
}

export const PageHeader: FC<PageHeaderProps> = ({
  title,
  subtitle,
  badge,
  actions,
  className = '',
}) => {
  return (
    <header className={`page-header ${className}`} style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '12px',
      marginBottom: '16px',
      paddingBottom: '12px',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
        <h1 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: 'var(--text-main)',
          letterSpacing: '-0.01em',
          margin: 0,
        }}>
          {title}
        </h1>
        {badge}
      </div>

      {subtitle && (
        <p style={{
          width: '100%',
          fontSize: '12px',
          color: 'var(--text-secondary)',
          margin: '-4px 0 0 0',
          lineHeight: 1.4,
        }}>
          {subtitle}
        </p>
      )}

      {actions && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {actions}
        </div>
      )}
    </header>
  )
}
