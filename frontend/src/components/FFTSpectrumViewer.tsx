import { useRef, useEffect, useState, useMemo } from 'react'
import type { FC } from 'react'
import * as echarts from 'echarts'
import type { MotorState } from '../types'
import { computeVibrationDiagnostics, computeRULPrognostics } from '../utils/vibrationDiagnostics'
import { Activity, Clock, ShieldAlert, Cpu, Layers } from 'lucide-react'

interface FFTSpectrumViewerProps {
  motor: MotorState
}

export const FFTSpectrumViewer: FC<FFTSpectrumViewerProps> = ({ motor }) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const trendChartRef = useRef<HTMLDivElement>(null)
  const [displayUnit, setDisplayUnit] = useState<'acceleration' | 'velocity'>('velocity')

  // Real-time theme synchronization
  const [currentTheme, setCurrentTheme] = useState<'dark' | 'light'>(() => {
    return (typeof document !== 'undefined' && (document.documentElement.getAttribute('data-theme') as 'dark' | 'light')) || 'dark'
  })

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const t = (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark'
      setCurrentTheme(t)
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  const isDark = currentTheme !== 'light'

  // Compute diagnostics
  const spectrumData = useMemo(() => computeVibrationDiagnostics(motor), [motor])
  const rulData = useMemo(() => computeRULPrognostics(motor), [motor])
  const maxFreq = spectrumData.frequencies[spectrumData.frequencies.length - 1] || 400

  // Colors aligned with industrial theme
  const axisColor = isDark ? '#334155' : '#cbd5e1'
  const textColor = isDark ? '#94a3b8' : '#64748b'
  const splitColor = isDark ? 'rgba(51, 65, 85, 0.35)' : 'rgba(226, 232, 240, 0.75)'
  const seriesColor = isDark ? '#06b6d4' : '#0284c7'

  // Initialize FFT Chart
  useEffect(() => {
    if (!chartRef.current) return
    const chart = echarts.init(chartRef.current, isDark ? 'dark' : undefined)

    const isVel = displayUnit === 'velocity'
    const amplitudes = isVel ? spectrumData.amplitudes_mms : spectrumData.amplitudes_g
    const unitLabel = isVel ? 'mm/s RMS' : 'g RMS'

    // Build mark points for significant defect peaks
    const markPoints = spectrumData.peaks
      .filter((p) => p.frequency_hz <= maxFreq)
      .map((p) => ({
        name: p.label,
        coord: [p.frequency_hz, isVel ? p.amplitude_mms : p.amplitude_g],
        value: `${isVel ? p.amplitude_mms : p.amplitude_g} ${unitLabel}`,
        itemStyle: {
          color: p.severity === 'critical' ? '#ef4444' : p.severity === 'warning' ? '#f59e0b' : seriesColor,
        },
        label: {
          formatter: p.label,
          position: 'top' as const,
          fontSize: 10,
          color: isDark ? '#f8fafc' : '#0f172a',
        },
      }))

    // Build vertical mark lines for bearing fault frequencies that lie within spectrum bounds
    const markLines: any[] = []

    if (spectrumData.running_frequency_hz <= maxFreq) {
      markLines.push({
        xAxis: spectrumData.running_frequency_hz,
        name: '1x RPM',
        lineStyle: { color: seriesColor, type: 'dashed' as const, width: 1.5 },
        label: { formatter: '1x RPM', position: 'end' as const, color: seriesColor, fontSize: 10 },
      })
    }

    const harm2x = Number((spectrumData.running_frequency_hz * 2).toFixed(1))
    if (harm2x <= maxFreq) {
      markLines.push({
        xAxis: harm2x,
        name: '2x Harm',
        lineStyle: { color: '#8b5cf6', type: 'dashed' as const, width: 1.5 },
        label: { formatter: '2x Harm', position: 'end' as const, color: '#8b5cf6', fontSize: 10 },
      })
    }

    if (spectrumData.bearing_frequencies.bpfo_hz <= maxFreq) {
      markLines.push({
        xAxis: spectrumData.bearing_frequencies.bpfo_hz,
        name: 'BPFO',
        lineStyle: { color: '#ef4444', type: 'dotted' as const, width: 1.5 },
        label: { formatter: 'BPFO', position: 'end' as const, color: '#ef4444', fontSize: 10 },
      })
    }

    if (spectrumData.bearing_frequencies.bpfi_hz <= maxFreq) {
      markLines.push({
        xAxis: spectrumData.bearing_frequencies.bpfi_hz,
        name: 'BPFI',
        lineStyle: { color: '#f59e0b', type: 'dotted' as const, width: 1.5 },
        label: { formatter: 'BPFI', position: 'end' as const, color: '#f59e0b', fontSize: 10 },
      })
    }

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: seriesColor, type: 'dashed' } },
        backgroundColor: isDark ? '#0f172a' : '#ffffff',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        textStyle: { color: isDark ? '#f8fafc' : '#0f172a' },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return ''
          const item = params[0]
          return `
            <div style="font-family: var(--font-mono, monospace); font-size: 12px; padding: 4px;">
              <span style="color: ${textColor};">Frequency:</span> <strong>${item.axisValue} Hz</strong><br/>
              <span style="color: ${seriesColor};">Amplitude:</span> <strong>${item.data} ${unitLabel}</strong>
            </div>
          `
        },
      },
      grid: {
        top: 40,
        right: 25,
        bottom: 35,
        left: 54,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: spectrumData.frequencies.map(String),
        name: 'Frequency (Hz)',
        nameLocation: 'middle',
        nameGap: 24,
        axisLine: { lineStyle: { color: axisColor } },
        axisLabel: { color: textColor, fontSize: 10, interval: Math.round(spectrumData.frequencies.length / 10) },
        splitLine: { show: true, lineStyle: { color: splitColor, type: 'dashed' } },
      },
      yAxis: {
        type: 'value',
        name: unitLabel,
        nameTextStyle: { color: textColor, fontSize: 11 },
        axisLine: { lineStyle: { color: axisColor } },
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { show: true, lineStyle: { color: splitColor, type: 'dashed' } },
      },
      series: [
        {
          name: 'Spectrum',
          type: 'line',
          showSymbol: false,
          smooth: true,
          data: amplitudes,
          lineStyle: {
            color: seriesColor,
            width: 1.8,
            shadowColor: isDark ? 'rgba(6, 182, 212, 0.4)' : 'rgba(2, 132, 199, 0.3)',
            shadowBlur: 4,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: isDark ? 'rgba(6, 182, 212, 0.28)' : 'rgba(2, 132, 199, 0.20)' },
              { offset: 1, color: isDark ? 'rgba(6, 182, 212, 0.01)' : 'rgba(2, 132, 199, 0.01)' },
            ]),
          },
          markPoint: {
            data: markPoints,
          },
          markLine: {
            silent: false,
            data: markLines,
          },
        },
      ],
    }

    chart.setOption(option)

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
    }
  }, [spectrumData, displayUnit, isDark, maxFreq, seriesColor, axisColor, textColor, splitColor])

  // Initialize RUL Trend Chart
  useEffect(() => {
    if (!trendChartRef.current) return
    const trendChart = echarts.init(trendChartRef.current, isDark ? 'dark' : undefined)

    const days = rulData.projected_trend.map((p) => `Day ${p.day}`)
    const projectedG = rulData.projected_trend.map((p) => p.projected_vibration_g)

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: isDark ? '#0f172a' : '#ffffff',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        textStyle: { color: isDark ? '#f8fafc' : '#0f172a' },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return ''
          const item = params[0]
          return `<div style="font-size: 11px;"><strong>${item.axisValue}:</strong> ${item.data} g RMS</div>`
        },
      },
      grid: {
        top: 20,
        right: 15,
        bottom: 25,
        left: 45,
      },
      xAxis: {
        type: 'category',
        data: days,
        axisLine: { lineStyle: { color: axisColor } },
        axisLabel: { color: textColor, fontSize: 9, interval: 2 },
      },
      yAxis: {
        type: 'value',
        name: 'Vib (g)',
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLine: { lineStyle: { color: axisColor } },
        axisLabel: { color: textColor, fontSize: 9 },
        splitLine: { show: true, lineStyle: { color: splitColor, type: 'dashed' } },
      },
      series: [
        {
          name: 'Wear Projection',
          type: 'line',
          data: projectedG,
          smooth: true,
          lineStyle: {
            color: rulData.failure_risk_level === 'CRITICAL' ? '#ef4444' : '#f59e0b',
            width: 2,
            type: 'dashed',
          },
          markLine: {
            data: [
              {
                yAxis: 0.80,
                name: 'Crit Limit (0.80g)',
                lineStyle: { color: '#ef4444', type: 'solid', width: 1.5 },
                label: { formatter: 'Crit Limit (0.8g)', color: '#ef4444', fontSize: 9 },
              },
            ],
          },
        },
      ],
    }

    trendChart.setOption(option)
    const handleResize = () => trendChart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      trendChart.dispose()
    }
  }, [rulData, isDark, axisColor, textColor, splitColor])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. Header Bar with ISO 10816 Severity Indicator */}
      <div
        className="card"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          padding: '14px 18px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color={seriesColor} />
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              FFT Vibration Frequency Spectrum & ISO 10816-3 Diagnostics
            </h3>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
            Nyquist Band (0–{maxFreq} Hz) • Harmonics & Bearing Fault Multipliers (BPFO / BPFI) • Shaft Speed: {spectrumData.rpm} RPM ({spectrumData.running_frequency_hz} Hz)
          </p>
        </div>

        {/* Unit Selector Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Spectral Unit:</span>
          <div className="segmented-control" role="group">
            <button
              className={`segmented-btn ${displayUnit === 'velocity' ? 'active' : ''}`}
              onClick={() => setDisplayUnit('velocity')}
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              Velocity (mm/s RMS)
            </button>
            <button
              className={`segmented-btn ${displayUnit === 'acceleration' ? 'active' : ''}`}
              onClick={() => setDisplayUnit('acceleration')}
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              Acceleration (g)
            </button>
          </div>
        </div>
      </div>

      {/* 2. ISO 10816 Severity Meter & Diagnostic Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
        }}
      >
        {/* ISO 10816-3 Velocity Classification Card */}
        <div
          className="card"
          style={{
            padding: '14px',
            borderColor:
              spectrumData.iso_rating_status === 'critical'
                ? 'var(--status-critical)'
                : spectrumData.iso_rating_status === 'warning'
                ? 'var(--status-warning)'
                : 'var(--border-main)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>
              ISO 10816-3 SEVERITY
            </span>
            <Layers size={14} color={seriesColor} />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
            {spectrumData.iso_velocity_mms_rms} <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>mm/s RMS</span>
          </div>
          <div
            style={{
              marginTop: '6px',
              fontSize: '11px',
              fontWeight: 600,
              color:
                spectrumData.iso_rating_status === 'critical'
                  ? 'var(--status-critical)'
                  : spectrumData.iso_rating_status === 'warning'
                  ? 'var(--status-warning)'
                  : 'var(--status-healthy)',
            }}
          >
            ● {spectrumData.iso_zone}
          </div>
          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Class I Electric Motors (up to 15 kW)
          </div>
        </div>

        {/* Bearing Fault Frequencies Card */}
        <div className="card" style={{ padding: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>
              BEARING FAULT FREQS
            </span>
            <Cpu size={14} color="#8b5cf6" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
            <div>
              <span style={{ color: '#ef4444', fontWeight: 600 }}>BPFO:</span> {spectrumData.bearing_frequencies.bpfo_hz} Hz
            </div>
            <div>
              <span style={{ color: '#f59e0b', fontWeight: 600 }}>BPFI:</span> {spectrumData.bearing_frequencies.bpfi_hz} Hz
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>BSF:</span> {spectrumData.bearing_frequencies.bsf_hz} Hz
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>FTF:</span> {spectrumData.bearing_frequencies.ftf_hz} Hz
            </div>
          </div>
          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '6px' }}>
            Deep-groove 608/6204 bearing geometry
          </div>
        </div>

        {/* Remaining Useful Life (RUL) Card */}
        <div
          className="card"
          style={{
            padding: '14px',
            borderColor:
              rulData.failure_risk_level === 'CRITICAL'
                ? 'var(--status-critical)'
                : rulData.failure_risk_level === 'ELEVATED'
                ? 'var(--status-warning)'
                : 'var(--border-main)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>
              PROGNOSTIC RUL
            </span>
            <Clock size={14} color="var(--status-healthy)" />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
            {rulData.estimated_rul_hours.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>Hours</span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            ~{rulData.projected_days_to_maintenance} Days to Planned Overhaul
          </div>
          <div
            style={{
              marginTop: '4px',
              fontSize: '11px',
              fontWeight: 600,
              color:
                rulData.failure_risk_level === 'CRITICAL'
                  ? 'var(--status-critical)'
                  : rulData.failure_risk_level === 'ELEVATED'
                  ? 'var(--status-warning)'
                  : 'var(--status-healthy)',
            }}
          >
            Risk Level: {rulData.failure_risk_level}
          </div>
        </div>

        {/* Degradation State & Dominant Factor */}
        <div className="card" style={{ padding: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>
              HEALTH INDEX
            </span>
            <ShieldAlert size={14} color="var(--status-warning)" />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
            {rulData.health_index} <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>/ 100</span>
          </div>
          <div style={{ marginTop: '8px' }}>
            <div style={{ height: '6px', background: 'var(--bg-subtle)', borderRadius: '3px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              <div
                style={{
                  height: '100%',
                  width: `${rulData.health_index}%`,
                  background:
                    rulData.health_index > 75
                      ? 'var(--status-healthy)'
                      : rulData.health_index > 40
                      ? 'var(--status-warning)'
                      : 'var(--status-critical)',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '6px' }}>
            Primary Driver: <strong style={{ color: 'var(--text-main)' }}>{rulData.dominant_stress_factor.replace('_', ' ')}</strong>
          </div>
        </div>
      </div>

      {/* 3. Main FFT Spectrum Chart Viewport */}
      <div className="card" style={{ padding: '16px 16px 8px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
            FFT Frequency Spectrum Breakdown (0 – {maxFreq} Hz)
          </span>
          <div style={{ display: 'flex', gap: '12px', fontSize: '11px', flexWrap: 'wrap' }}>
            <span style={{ color: seriesColor }}>● 1x RPM ({spectrumData.running_frequency_hz} Hz)</span>
            <span style={{ color: '#8b5cf6' }}>● 2x Harmonics ({(spectrumData.running_frequency_hz * 2).toFixed(1)} Hz)</span>
            {spectrumData.bearing_frequencies.bpfo_hz <= maxFreq && (
              <span style={{ color: '#ef4444' }}>● BPFO ({spectrumData.bearing_frequencies.bpfo_hz} Hz)</span>
            )}
            {spectrumData.bearing_frequencies.bpfi_hz <= maxFreq && (
              <span style={{ color: '#f59e0b' }}>● BPFI ({spectrumData.bearing_frequencies.bpfi_hz} Hz)</span>
            )}
          </div>
        </div>
        <div ref={chartRef} style={{ width: '100%', height: '280px' }} />
      </div>

      {/* 4. 30-Day Prognostic Wear Projection Chart */}
      <div className="card" style={{ padding: '16px 16px 8px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
            30-Day Prognostic Degradation Trajectory (Vibration Wear vs. Critical 0.8g Threshold)
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Confidence: {(rulData.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div ref={trendChartRef} style={{ width: '100%', height: '140px' }} />
      </div>
    </div>
  )
}
