import type { FC } from 'react'
import { useMemo } from 'react'
import {
  Thermometer,
  Zap,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'
import type { ChartMetric } from '../types'

interface MetricSummaryCardProps {
  metric: ChartMetric
  title: string
  sensorLabel: string
  latestValue: number | null
  unit: string
  history: (number | null)[]
  thresholdWarn?: number
  thresholdCrit?: number
  onClick?: () => void
  isSelected?: boolean
  sensorState?: string
  connectionStatus?: string
}

export const MetricSummaryCard: FC<MetricSummaryCardProps> = ({
  metric,
  title,
  sensorLabel,
  latestValue,
  unit,
  history,
  thresholdWarn,
  thresholdCrit,
  onClick,
  isSelected = false,
  sensorState,
  connectionStatus,
}) => {
  // Extract min, max, delta from real history
  const { minVal, maxVal, delta, isDeltaPositive } = useMemo(() => {
    const valid = history.filter((v): v is number => v !== null && !isNaN(v))
    if (valid.length === 0) {
      return { minVal: null, maxVal: null, delta: 0, isDeltaPositive: false }
    }
    const min = Math.min(...valid)
    const max = Math.max(...valid)
    const current = valid[valid.length - 1]
    const prev = valid.length > 1 ? valid[valid.length - 2] : current
    const d = current - prev
    return {
      minVal: min,
      maxVal: max,
      delta: d,
      isDeltaPositive: d > 0,
    }
  }, [history])

  // Determine threshold health status (stale, offline, and disconnected are never healthy)
  const statusClass = useMemo(() => {
    if (connectionStatus === 'offline') return 'offline'
    if (connectionStatus === 'stale') return 'warning'
    if (
      sensorState === 'DISCONNECTED' ||
      sensorState === 'UNAVAILABLE' ||
      sensorState === 'OUT_OF_RANGE'
    ) {
      return 'unknown'
    }
    if (latestValue == null) return 'unknown'
    if (thresholdCrit != null && latestValue >= thresholdCrit) return 'critical'
    if (thresholdWarn != null && latestValue >= thresholdWarn) return 'warning'
    return 'healthy'
  }, [connectionStatus, sensorState, latestValue, thresholdWarn, thresholdCrit])

  const badgeLabel = useMemo(() => {
    if (connectionStatus === 'offline') return 'OFFLINE'
    if (connectionStatus === 'stale') return 'STALE'
    if (sensorState === 'DISCONNECTED') return 'DISCONNECTED'
    if (sensorState === 'UNAVAILABLE') return 'UNAVAILABLE'
    return statusClass.toUpperCase()
  }, [connectionStatus, sensorState, statusClass])

  // Icon
  const Icon = metric === 'temperature' ? Thermometer : metric === 'current' ? Zap : Activity

  // Estimated Electrical Power for 12V DC RS-775 Motor
  const estimatedPowerWatts = useMemo(() => {
    if (metric === 'current' && latestValue != null) {
      return (12.0 * latestValue).toFixed(1)
    }
    return null
  }, [metric, latestValue])

  // Render SVG Sparkline
  const sparklinePoints = useMemo(() => {
    const valid = history.filter((v): v is number => v !== null && !isNaN(v)).slice(-20)
    if (valid.length < 2) return ''
    const min = Math.min(...valid)
    const max = Math.max(...valid)
    const range = max - min || 1
    const width = 100
    const height = 24

    return valid
      .map((val, idx) => {
        const x = (idx / (valid.length - 1)) * width
        const y = height - ((val - min) / range) * (height - 4) - 2
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }, [history])

  const formattedVal =
    latestValue != null
      ? latestValue.toFixed(metric === 'vibration' ? 3 : metric === 'current' ? 2 : 1)
      : 'N/A'

  return (
    <div
      className={`measurement-card ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        borderLeft: isSelected ? '4px solid var(--brand-primary)' : undefined,
      }}
    >
      <div className="measurement-card-header">
        <div className="measurement-name-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Icon size={14} color="var(--brand-primary)" />
            <span className="measurement-title">{title}</span>
          </div>
          <span className="measurement-sensor-type">{sensorLabel}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Mini Sparkline */}
          {sparklinePoints && (
            <svg width="70" height="20" style={{ overflow: 'visible' }}>
              <polyline
                fill="none"
                stroke={
                  statusClass === 'critical'
                    ? '#C43D43'
                    : statusClass === 'warning'
                    ? '#B7791F'
                    : statusClass === 'offline' || statusClass === 'unknown'
                    ? '#6B7280'
                    : '#23845B'
                }
                strokeWidth="1.75"
                points={sparklinePoints}
              />
            </svg>
          )}

          <div
            className={`badge-status ${statusClass}`}
            style={{ fontSize: '10px', padding: '1px 6px' }}
          >
            {badgeLabel}
          </div>
        </div>
      </div>

      <div className="measurement-reading-row">
        <div>
          <span className="measurement-big-val tabular-nums">{formattedVal}</span>
          <span className="measurement-big-unit">{unit}</span>
        </div>

        {delta !== 0 && (
          <div className="measurement-delta-tag tabular-nums">
            {isDeltaPositive ? (
              <ArrowUpRight size={13} color="#B7791F" />
            ) : (
              <ArrowDownRight size={13} color="#23845B" />
            )}
            <span>
              {isDeltaPositive ? '+' : ''}
              {delta.toFixed(metric === 'vibration' ? 3 : 2)} {unit}
            </span>
          </div>
        )}
      </div>

      <div className="measurement-stats-row">
        <div className="stat-item-block">
          <span className="stat-item-label">Min (Range)</span>
          <span className="stat-item-val tabular-nums">
            {minVal != null ? `${minVal.toFixed(metric === 'vibration' ? 3 : 1)} ${unit}` : '—'}
          </span>
        </div>

        <div className="stat-item-block">
          <span className="stat-item-label">Max (Range)</span>
          <span className="stat-item-val tabular-nums">
            {maxVal != null ? `${maxVal.toFixed(metric === 'vibration' ? 3 : 1)} ${unit}` : '—'}
          </span>
        </div>

        <div className="stat-item-block">
          <span className="stat-item-label">
            {metric === 'current' ? 'Est. Power (12V)' : 'Safe Limit'}
          </span>
          <span className="stat-item-val tabular-nums">
            {estimatedPowerWatts
              ? `${estimatedPowerWatts} W`
              : thresholdWarn
              ? `< ${thresholdWarn} ${unit}`
              : 'Nominal'}
          </span>
        </div>
      </div>
    </div>
  )
}
