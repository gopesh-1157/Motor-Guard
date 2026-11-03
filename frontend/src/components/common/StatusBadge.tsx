import type { FC } from 'react'

export type StatusVariant = 'healthy' | 'warning' | 'critical' | 'offline' | 'info' | 'hardware' | 'sim'

interface StatusBadgeProps {
  status: StatusVariant | string
  label?: string
  pulse?: boolean
  size?: 'sm' | 'md'
}

export const StatusBadge: FC<StatusBadgeProps> = ({
  status,
  label,
  pulse = true,
  size = 'sm',
}) => {
  const norm = status.toLowerCase()
  let colorVar = 'var(--status-healthy)'
  let bgVar = 'var(--status-healthy-bg)'
  let borderVar = 'var(--status-healthy-border)'
  let displayLabel = label || status.toUpperCase()

  if (norm.includes('crit') || norm === 'danger') {
    colorVar = 'var(--status-critical)'
    bgVar = 'var(--status-critical-bg)'
    borderVar = 'var(--status-critical-border)'
    displayLabel = label || 'CRITICAL'
  } else if (norm.includes('warn') || norm.includes('deg')) {
    colorVar = 'var(--status-warning)'
    bgVar = 'var(--status-warning-bg)'
    borderVar = 'var(--status-warning-border)'
    displayLabel = label || 'WARNING'
  } else if (norm.includes('off') || norm.includes('stale') || norm.includes('disc')) {
    colorVar = 'var(--status-offline)'
    bgVar = 'var(--status-offline-bg)'
    borderVar = 'var(--status-offline-border)'
    displayLabel = label || 'OFFLINE'
  } else if (norm.includes('hard') || norm.includes('hw')) {
    colorVar = 'var(--status-hardware)'
    bgVar = 'var(--status-hardware-bg)'
    borderVar = 'var(--status-hardware-border)'
    displayLabel = label || 'HARDWARE'
  } else if (norm.includes('sim')) {
    colorVar = 'var(--status-sim)'
    bgVar = 'var(--status-sim-bg)'
    borderVar = 'var(--status-sim-border)'
    displayLabel = label || 'SIMULATOR'
  } else if (norm.includes('info') || norm.includes('ack')) {
    colorVar = 'var(--status-info)'
    bgVar = 'var(--status-info-bg)'
    borderVar = 'var(--status-info-border)'
    displayLabel = label || 'INFO'
  }

  const isSmall = size === 'sm'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: isSmall ? '5px' : '7px',
        padding: isSmall ? '2px 8px' : '4px 10px',
        borderRadius: '999px',
        backgroundColor: bgVar,
        border: `1px solid ${borderVar}`,
        color: colorVar,
        fontSize: isSmall ? '10.5px' : '11.5px',
        fontWeight: 600,
        fontFamily: 'var(--scada-mono-font, monospace)',
        letterSpacing: '0.04em',
        lineHeight: 1,
        userSelect: 'none',
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          width: isSmall ? '6px' : '8px',
          height: isSmall ? '6px' : '8px',
          borderRadius: '50%',
          backgroundColor: colorVar,
          boxShadow: pulse ? `0 0 6px ${colorVar}` : 'none',
          flexShrink: 0,
        }}
      />
      {displayLabel}
    </span>
  )
}
