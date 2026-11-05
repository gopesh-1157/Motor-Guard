import type { FC } from 'react'
import { useEffect, useRef, useState, useMemo } from 'react'
import * as echarts from 'echarts'
import {
  Download,
  Maximize2,
  Minimize2,
  RefreshCw,
  Eye,
  EyeOff,
  Sliders,
  FileSpreadsheet,
  FileCode,
  Image as ImageIcon,
} from 'lucide-react'
import type { ChartMetric, ChartType, TimeRangeOption } from '../types'

export interface ChartDataPoint {
  timestamp: string // ISO
  value: number | null
  status?: string
}

interface EChartPanelProps {
  title: string
  subtitle?: string
  metric: ChartMetric
  unit: string
  motorId: string
  deviceId: string
  data: ChartDataPoint[]
  thresholdWarn?: number
  thresholdCrit?: number
  timeRange: TimeRangeOption
  onTimeRangeChange?: (tr: TimeRangeOption) => void
  isPrimary?: boolean
}

export const EChartPanel: FC<EChartPanelProps> = ({
  title,
  subtitle,
  metric,
  unit,
  motorId,
  deviceId,
  data,
  thresholdWarn,
  thresholdCrit,
  timeRange,
  onTimeRangeChange,
  isPrimary = false,
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  // Chart type selection state
  const [chartType, setChartType] = useState<ChartType>('line')
  const [showThresholds, setShowThresholds] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)

  // Real-time theme detection
  const [currentTheme, setCurrentTheme] = useState<'dark' | 'light'>(() => {
    return (typeof document !== 'undefined' && (document.documentElement.getAttribute('data-theme') as 'dark' | 'light')) || 'dark'
  })

  useEffect(() => {
    if (typeof document === 'undefined') return
    const observer = new MutationObserver(() => {
      const t = (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark'
      setCurrentTheme(t)
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  // Available chart types based on measurement nature
  const availableTypes: { key: ChartType; label: string }[] = useMemo(() => {
    if (metric === 'temperature') {
      return [
        { key: 'line', label: 'Line' },
        { key: 'area', label: 'Area' },
        { key: 'step', label: 'Step' },
        { key: 'bar', label: 'Bar' },
        { key: 'scatter', label: 'Scatter' },
      ]
    }
    if (metric === 'current') {
      return [
        { key: 'line', label: 'Line' },
        { key: 'area', label: 'Area' },
        { key: 'bar', label: 'Bar' },
        { key: 'scatter', label: 'Scatter' },
        { key: 'threshold', label: 'Threshold Limits' },
      ]
    }
    // vibration
    return [
      { key: 'line', label: 'Line' },
      { key: 'area', label: 'Area' },
      { key: 'bar', label: 'Bar' },
      { key: 'scatter', label: 'Scatter' },
      { key: 'histogram', label: 'Distribution' },
    ]
  }, [metric])

  // Filter data by time range anchored deterministically to the telemetry timeline
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) return []
    if (timeRange === 'all') return data

    const latestItem = data[data.length - 1]
    const referenceTime = latestItem?.timestamp ? new Date(latestItem.timestamp).getTime() : 0
    if (!referenceTime) return data

    const windowsMs: Record<TimeRangeOption, number> = {
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      all: Infinity,
    }

    const cutoff = referenceTime - (windowsMs[timeRange] || Infinity)
    return data.filter((d) => {
      try {
        return new Date(d.timestamp).getTime() >= cutoff
      } catch {
        return true
      }
    })
  }, [data, timeRange])

  // Initialize and update ECharts
  useEffect(() => {
    if (!chartRef.current) return

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: 'svg', // Enables crisp rendering and direct SVG downloads
      })
    }

    const chart = chartInstance.current

    // Extract series data
    const timestamps = filteredData.map((d) => {
      try {
        const date = new Date(d.timestamp)
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      } catch {
        return d.timestamp
      }
    })

    const rawValues = filteredData.map((d) => d.value ?? null)
    const isDark = currentTheme !== 'light'

    // Theme-aligned series color choices
    // Dark: Cyan (#22D3EE), Amber (#F59E0B), Teal (#14B8A6)
    // Light: Deep Teal (#0F766E), Dark Orange (#C2410C), Cyan (#0891B2)
    const metricColor = isDark
      ? metric === 'temperature'
        ? '#F59E0B'
        : metric === 'current'
        ? '#22D3EE'
        : '#14B8A6'
      : metric === 'temperature'
      ? '#C2410C'
      : metric === 'current'
      ? '#0F766E'
      : '#0891B2'

    // Configure mark lines for critical/warning thresholds
    const markLineData: any[] = []
    const warnColor = isDark ? '#F59E0B' : '#B45309'
    const critColor = isDark ? '#EF4444' : '#B91C1C'

    if (showThresholds && thresholdWarn != null) {
      markLineData.push({
        yAxis: thresholdWarn,
        name: 'Warning Limit',
        lineStyle: { color: warnColor, type: 'dashed', width: 1.5 },
        label: { formatter: `Warn ${thresholdWarn} ${unit}`, position: 'end', color: warnColor, fontSize: 10 },
      })
    }
    if (showThresholds && thresholdCrit != null) {
      markLineData.push({
        yAxis: thresholdCrit,
        name: 'Critical Trip',
        lineStyle: { color: critColor, type: 'dashed', width: 1.5 },
        label: { formatter: `Trip ${thresholdCrit} ${unit}`, position: 'end', color: critColor, fontSize: 10 },
      })
    }

    let option: echarts.EChartsOption = {}

    // 1. Histogram distribution mode
    if (chartType === 'histogram') {
      const validNums = rawValues.filter((v): v is number => typeof v === 'number')
      const min = Math.min(...(validNums.length ? validNums : [0]))
      const max = Math.max(...(validNums.length ? validNums : [1]))
      const binsCount = 8
      const binWidth = (max - min) / binsCount || 0.1
      const bins = Array(binsCount).fill(0)
      const binLabels = Array(binsCount).fill('')

      for (let i = 0; i < binsCount; i++) {
        const binStart = min + i * binWidth
        const binEnd = binStart + binWidth
        binLabels[i] = `${binStart.toFixed(2)} - ${binEnd.toFixed(2)}`
      }

      validNums.forEach((val) => {
        const idx = Math.min(Math.floor((val - min) / binWidth), binsCount - 1)
        if (idx >= 0 && idx < binsCount) bins[idx]++
      })

      option = {
        grid: { top: 25, right: 25, bottom: 40, left: 45 },
        tooltip: {
          trigger: 'axis',
          backgroundColor: isDark ? '#172235' : '#FFFFFF',
          borderColor: isDark ? '#334155' : '#E2E8F0',
          textStyle: { color: isDark ? '#F1F5F9' : '#0F172A' },
          axisPointer: { type: 'shadow' },
        },
        xAxis: {
          type: 'category',
          data: binLabels,
          axisLine: { lineStyle: { color: isDark ? '#334155' : '#CBD5E1' } },
          axisLabel: { fontSize: 10, rotate: 20, color: isDark ? '#94A3B8' : '#64748B' },
        },
        yAxis: {
          type: 'value',
          name: 'Count',
          axisLabel: { color: isDark ? '#94A3B8' : '#64748B' },
          splitLine: { lineStyle: { color: isDark ? 'rgba(51, 65, 85, 0.45)' : '#E2E8F0', type: 'dashed' } },
        },
        series: [
          {
            name: `${metric} Frequency`,
            type: 'bar',
            data: bins,
            itemStyle: { color: metricColor, borderRadius: [4, 4, 0, 0] },
          },
        ],
      }
    } else {
      // Time-series modes: line, area, step, bar, scatter, threshold
      const isArea = chartType === 'area'
      const isStep = chartType === 'step'
      const isBar = chartType === 'bar'
      const isScatter = chartType === 'scatter'

      option = {
        animation: false, // Performance optimization for continuous real-time feeds
        grid: { top: 30, right: 35, bottom: 40, left: 50 },
        tooltip: {
          trigger: 'axis',
          backgroundColor: isDark ? '#172235' : '#FFFFFF',
          borderColor: isDark ? '#334155' : '#E2E8F0',
          borderWidth: 1,
          padding: [8, 12],
          textStyle: { color: isDark ? '#F1F5F9' : '#0F172A' },
          axisPointer: {
            type: 'cross',
            label: {
              backgroundColor: isDark ? '#1E293B' : '#F1F5F9',
              color: isDark ? '#F1F5F9' : '#0F172A',
            },
          },
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params[0] : params
            const val = p.value != null ? Number(p.value).toFixed(metric === 'vibration' ? 3 : metric === 'current' ? 2 : 1) : 'N/A'
            const textColor = isDark ? '#F1F5F9' : '#0F172A'
            const subColor = isDark ? '#94A3B8' : '#64748B'
            return `
              <div style="font-family: Inter, sans-serif; font-size: 12px; line-height: 1.4; color: ${textColor};">
                <div style="color: ${subColor}; margin-bottom: 4px; font-family: 'JetBrains Mono', monospace; font-size: 11px;">Time: <strong>${p.name}</strong></div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                  <span style="color:${subColor}; font-weight:500;">${p.seriesName}:</span>
                  <strong style="color:${textColor}; font-family: 'JetBrains Mono', monospace;">${val} ${unit}</strong>
                </div>
              </div>
            `
          },
        },
        xAxis: {
          type: 'category',
          data: timestamps,
          boundaryGap: isBar,
          axisLine: { lineStyle: { color: isDark ? '#334155' : '#CBD5E1' } },
          axisLabel: { color: isDark ? '#94A3B8' : '#64748B', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
          axisTick: { show: false },
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLine: { show: false },
          axisLabel: { color: isDark ? '#94A3B8' : '#64748B', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', formatter: `{value} ${unit}` },
          splitLine: { lineStyle: { color: isDark ? 'rgba(51, 65, 85, 0.45)' : '#E2E8F0', type: 'dashed' } },
        },
        dataZoom: [
          { type: 'inside', start: 0, end: 100 },
          {
            type: 'slider',
            show: isPrimary || isExpanded,
            height: 16,
            bottom: 6,
            borderColor: isDark ? '#334155' : '#CBD5E1',
            fillerColor: isDark ? 'rgba(34, 211, 238, 0.15)' : 'rgba(15, 118, 110, 0.12)',
            handleStyle: { color: isDark ? '#22D3EE' : '#0F766E', borderColor: isDark ? '#334155' : '#CBD5E1' },
            textStyle: { color: isDark ? '#94A3B8' : '#64748B', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
          },
        ],
        series: [
          {
            name: `${metric.toUpperCase()}`,
            type: isBar ? 'bar' : isScatter ? 'scatter' : 'line',
            step: isStep ? 'middle' : false,
            data: rawValues,
            smooth: !isStep && !isBar,
            showSymbol: isScatter || rawValues.length < 20,
            symbolSize: isScatter ? 7 : 5,
            itemStyle: { color: metricColor },
            lineStyle: { width: 2, color: metricColor },
            areaStyle: isArea
              ? {
                  color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `${metricColor}44` },
                    { offset: 1, color: `${metricColor}04` },
                  ]),
                }
              : undefined,
            markLine: markLineData.length > 0 ? { symbol: 'none', data: markLineData } : undefined,
          },
        ],
      }
    }

    chart.setOption(option)

    const handleResize = () => {
      chart.resize()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [
    filteredData,
    chartType,
    metric,
    unit,
    showThresholds,
    thresholdWarn,
    thresholdCrit,
    isPrimary,
    isExpanded,
    currentTheme,
  ])

  // Reset zoom
  const handleResetZoom = () => {
    if (!chartInstance.current) return
    chartInstance.current.dispatchAction({
      type: 'dataZoom',
      start: 0,
      end: 100,
    })
  }

  // PNG Export with Industrial Watermark & Details
  const handleExportPNG = () => {
    if (!chartInstance.current) return
    const url = chartInstance.current.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#FFFFFF',
    })
    const dateStr = new Date().toISOString().split('T')[0]
    const filename = `MotorGuard_${motorId}_${metric.toUpperCase()}_${dateStr}.png`
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    setIsExportMenuOpen(false)
  }

  // SVG Export
  const handleExportSVG = () => {
    if (!chartInstance.current) return
    const url = chartInstance.current.getDataURL({
      type: 'svg',
      backgroundColor: '#FFFFFF',
    })
    const dateStr = new Date().toISOString().split('T')[0]
    const filename = `MotorGuard_${motorId}_${metric.toUpperCase()}_${dateStr}.svg`
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    setIsExportMenuOpen(false)
  }

  // CSV Data Export
  const handleExportCSV = () => {
    if (!filteredData || filteredData.length === 0) return
    const headers = ['Timestamp_ISO', 'Motor_ID', 'Device_ID', 'Measurement', 'Value', 'Unit', 'Status']
    const rows = filteredData.map((d) => [
      `"${d.timestamp}"`,
      `"${motorId}"`,
      `"${deviceId}"`,
      `"${metric}"`,
      d.value != null ? d.value : '',
      `"${unit}"`,
      `"${d.status || 'OK'}"`,
    ])

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const dateStr = new Date().toISOString().split('T')[0]
    const link = document.createElement('a')
    link.href = encodedUri
    link.download = `MotorGuard_${motorId}_${metric.toUpperCase()}_Telemetry_${dateStr}.csv`
    link.click()
    setIsExportMenuOpen(false)
  }

  // JSON Data Export
  const handleExportJSON = () => {
    if (!filteredData || filteredData.length === 0) return
    const exportPayload = {
      export_metadata: {
        system: 'MotorGuard Industrial Edge Gateway',
        motor_id: motorId,
        device_id: deviceId,
        metric,
        unit,
        exported_at: new Date().toISOString(),
        time_range: timeRange,
        points_count: filteredData.length,
      },
      data: filteredData,
    }
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportPayload, null, 2))
    const dateStr = new Date().toISOString().split('T')[0]
    const link = document.createElement('a')
    link.href = dataStr
    link.download = `MotorGuard_${motorId}_${metric.toUpperCase()}_${dateStr}.json`
    link.click()
    setIsExportMenuOpen(false)
  }

  return (
    <div className={`chart-panel ${isPrimary ? 'primary' : ''} ${isExpanded ? 'expanded' : ''}`}>
      {/* Top Toolbar */}
      <div className="chart-toolbar">
        <div className="chart-toolbar-left">
          <span className="chart-title-tag">{title}</span>
          {subtitle && <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>({subtitle})</span>}

          {/* Segmented Chart Type Selector */}
          <div className="segmented-control" role="group" aria-label="Chart Type">
            {availableTypes.map((t) => (
              <button
                key={t.key}
                className={`segmented-btn ${chartType === t.key ? 'active' : ''}`}
                onClick={() => setChartType(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="chart-toolbar-right">
          {/* Time Range Selector */}
          {onTimeRangeChange && (
            <div className="segmented-control" role="group" aria-label="Time Range">
              {(['15m', '1h', '6h', '24h', 'all'] as TimeRangeOption[]).map((tr) => (
                <button
                  key={tr}
                  className={`segmented-btn ${timeRange === tr ? 'active' : ''}`}
                  onClick={() => onTimeRangeChange(tr)}
                >
                  {tr.toUpperCase()}
                </button>
              ))}
            </div>
          )}

          {/* Threshold Line Toggle */}
          {(thresholdWarn != null || thresholdCrit != null) && (
            <button
              className={`btn-icon-toolbar ${showThresholds ? 'active' : ''}`}
              onClick={() => setShowThresholds(!showThresholds)}
              title={showThresholds ? 'Hide Threshold Limits' : 'Show Threshold Limits'}
              aria-label="Toggle Thresholds"
            >
              {showThresholds ? <Eye size={14} /> : <EyeOff size={14} />}
            </button>
          )}

          {/* Reset Zoom */}
          <button
            className="btn-icon-toolbar"
            onClick={handleResetZoom}
            title="Reset Zoom & Pan"
            aria-label="Reset Zoom"
          >
            <RefreshCw size={13} />
          </button>

          {/* Fullscreen / Expand Toggle */}
          <button
            className="btn-icon-toolbar"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse Chart' : 'Maximize Chart'}
            aria-label="Expand Chart"
          >
            {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>

          {/* Genuine Export Menu */}
          <div style={{ position: 'relative' }}>
            <button
              className={`btn-icon-toolbar ${isExportMenuOpen ? 'active' : ''}`}
              onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
              title="Export Chart or Data"
              aria-label="Export Menu"
            >
              <Download size={14} />
            </button>

            {isExportMenuOpen && (
              <div className="chart-menu-dropdown">
                <button className="menu-item-btn" onClick={handleExportPNG}>
                  <ImageIcon size={14} color="#315FCE" />
                  <span>Download PNG (2x HQ)</span>
                </button>

                <button className="menu-item-btn" onClick={handleExportSVG}>
                  <Sliders size={14} color="#23845B" />
                  <span>Download SVG Vector</span>
                </button>

                <div className="menu-divider" />

                <button className="menu-item-btn" onClick={handleExportCSV}>
                  <FileSpreadsheet size={14} color="#B7791F" />
                  <span>Export CSV Dataset</span>
                </button>

                <button className="menu-item-btn" onClick={handleExportJSON}>
                  <FileCode size={14} color="#6D28D9" />
                  <span>Export JSON Schema</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="chart-canvas-container" ref={chartRef}>
        {filteredData.length === 0 && (
          <div
            style={{
              display: 'flex',
              height: '100%',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              fontSize: '13px',
            }}
          >
            Awaiting sensor telemetry stream for {metric}...
          </div>
        )}
      </div>
    </div>
  )
}
