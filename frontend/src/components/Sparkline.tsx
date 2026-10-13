import type { FC } from 'react'

interface SparklineProps {
  data: (number | null)[]
  color?: string
  height?: number
  label?: string
}

export const Sparkline: FC<SparklineProps> = ({
  data,
  color = '#3b82f6',
  height = 42,
  label,
}) => {
  const validData = data.filter((v): v is number => typeof v === 'number' && !isNaN(v))

  if (validData.length < 2) {
    return (
      <div className="sparkline-chart" style={{ height: `${height}px`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Accumulating data...</span>
      </div>
    )
  }

  const min = Math.min(...validData)
  const max = Math.max(...validData)
  const range = max - min === 0 ? 1 : max - min

  const width = 120
  const paddingY = 4

  const points = validData.map((val, idx) => {
    const x = (idx / (validData.length - 1)) * width
    const normalized = (val - min) / range
    const y = height - paddingY - normalized * (height - paddingY * 2)
    return { x, y }
  })

  const pathD = points.reduce((acc, pt, idx) => {
    return idx === 0 ? `M ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}` : `${acc} L ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`
  }, '')

  const lastPoint = points[points.length - 1]
  const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${height} L ${points[0].x.toFixed(1)} ${height} Z`

  const gradId = `spark-grad-${label || 'plot'}-${color.replace(/[^a-zA-Z0-9]/g, '')}`

  return (
    <div className="sparkline-chart" style={{ height: `${height}px` }}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <stop offset="100%" stopColor={color} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill={`url(#${gradId})`} />
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx={lastPoint.x}
          cy={lastPoint.y}
          r="2.5"
          fill={color}
          stroke="var(--bg-card)"
          strokeWidth="1"
        />
      </svg>
    </div>
  )
}
