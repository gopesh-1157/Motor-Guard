import type { FC, ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: string | number
  unit?: string
  subtext?: string
  status?: 'healthy' | 'warning' | 'critical' | 'offline' | 'neutral' | 'info'
  icon?: ReactNode
  sparkline?: ReactNode
  className?: string
  onClick?: () => void
}

export const StatCard: FC<StatCardProps> = ({
  label,
  value,
  unit,
  subtext,
  status = 'neutral',
  icon,
  sparkline,
  className = '',
  onClick,
}) => {
  let statusColor = 'var(--text-muted)'
  if (status === 'healthy') statusColor = 'var(--status-healthy)'
  else if (status === 'warning') statusColor = 'var(--status-warning)'
  else if (status === 'critical') statusColor = 'var(--status-critical)'
  else if (status === 'offline') statusColor = 'var(--status-offline)'
  else if (status === 'info') statusColor = 'var(--status-info)'

  return (
    <div
      className={`stat-card ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-main)',
        borderRadius: 'var(--radius-md, 8px)',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        minHeight: '92px',
        position: 'relative',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform var(--transition-fast), border-color var(--transition-fast)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--text-secondary)',
        }}>
          {label}
        </span>
        {icon && (
          <span style={{ color: statusColor, display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            {icon}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
        <span
          className="tabular-nums"
          style={{
            fontSize: '24px',
            fontWeight: 700,
            fontFamily: 'var(--scada-mono-font, monospace)',
            color: 'var(--text-main)',
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          {value}
        </span>
        {unit && (
          <span style={{
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-secondary)',
            fontFamily: 'var(--scada-mono-font, monospace)',
          }}>
            {unit}
          </span>
        )}
      </div>

      {(subtext || sparkline) && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: '8px',
          fontSize: '11px',
          color: 'var(--text-muted)',
        }}>
          {subtext && <span>{subtext}</span>}
          {sparkline && <div style={{ marginLeft: 'auto' }}>{sparkline}</div>}
        </div>
      )}
    </div>
  )
}
