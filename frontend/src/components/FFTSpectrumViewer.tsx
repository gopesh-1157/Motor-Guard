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

  // Compute diagnostics
  const spectrumData = useMemo(() => computeVibrationDiagnostics(motor), [motor])
  const rulData = useMemo(() => computeRULPrognostics(motor), [motor])

  // Initialize FFT Chart
  useEffect(() => {
    if (!chartRef.current) return
    const chart = echarts.init(chartRef.current, 'dark')

    const isVel = displayUnit === 'velocity'
    const amplitudes = isVel ? spectrumData.amplitudes_mms : spectrumData.amplitudes_g
    const unitLabel = isVel ? 'mm/s RMS' : 'g'

    // Build mark points for significant defect peaks
    const markPoints = spectrumData.peaks.map((p) => ({
      name: p.label,
      coord: [p.frequency_hz, isVel ? p.amplitude_mms : p.amplitude_g],
      value: `${isVel ? p.amplitude_mms : p.amplitude_g} ${unitLabel}`,
      itemStyle: {
        color: p.severity === 'critical' ? '#ef4444' : p.severity === 'warning' ? '#f59e0b' : '#06b6d4',
      },
      label: {
        formatter: p.label,
        position: 'top' as const,
        fontSize: 10,
        color: '#f8fafc',
      },
    }))

    // Build vertical mark lines for bearing fault frequencies
    const markLines = [
      {
        xAxis: spectrumData.running_frequency_hz,
        name: '1x RPM',
        lineStyle: { color: '#06b6d4', type: 'dashed' as const, width: 1.5 },
        label: { formatter: '1x RPM', position: 'end' as const, color: '#06b6d4', fontSize: 10 },
      },
      {
        xAxis: Number((spectrumData.running_frequency_hz * 2).toFixed(1)),
        name: '2x Harm',
        lineStyle: { color: '#8b5cf6', type: 'dashed' as const, width: 1.5 },
        label: { formatter: '2x Misalign', position: 'end' as const, color: '#8b5cf6', fontSize: 10 },
      },
      {
        xAxis: spectrumData.bearing_frequencies.bpfo_hz,
        name: 'BPFO',
        lineStyle: { color: '#ef4444', type: 'dotted' as const, width: 1.5 },
        label: { formatter: 'BPFO', position: 'end' as const, color: '#ef4444', fontSize: 10 },
      },
      {
        xAxis: spectrumData.bearing_frequencies.bpfi_hz,
        name: 'BPFI',
        lineStyle: { color: '#f59e0b', type: 'dotted' as const, width: 1.5 },
        label: { formatter: 'BPFI', position: 'end' as const, color: '#f59e0b', fontSize: 10 },
      },
    ]

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: '#06b6d4', type: 'dashed' } },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return ''
          const item = params[0]
          return `
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 4px;">
              <strong style="color: #94a3b8;">Frequency:</strong> ${item.axisValue} Hz<br/>
              <strong style="color: #06b6d4;">Amplitude:</strong> ${item.data} ${unitLabel}
            </div>
          `
        },
      },
      grid: {
        top: 45,
        right: 25,
        bottom: 35,
        left: 48,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: spectrumData.frequencies.map(String),
        name: 'Frequency (Hz)',
        nameLocation: 'middle',
        nameGap: 24,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 10, interval: 39 }, // Label every ~40 Hz
        splitLine: { show: true, lineStyle: { color: 'rgba(51, 65, 85, 0.3)', type: 'dashed' } },
      },
      yAxis: {
        type: 'value',
        name: unitLabel,
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        splitLine: { show: true, lineStyle: { color: 'rgba(51, 65, 85, 0.3)', type: 'dashed' } },
      },
      series: [
        {
          name: 'Spectrum',
          type: 'line',
          showSymbol: false,
          smooth: true,
          data: amplitudes,
          lineStyle: {
            color: '#06b6d4',
            width: 1.8,
            shadowColor: 'rgba(6, 182, 212, 0.4)',
            shadowBlur: 6,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(6, 182, 212, 0.28)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0.01)' },
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
  }, [spectrumData, displayUnit])

  // Initialize RUL Trend Chart
  useEffect(() => {
    if (!trendChartRef.current) return
    const trendChart = echarts.init(trendChartRef.current, 'dark')

    const days = rulData.projected_trend.map((p) => `Day ${p.day}`)
    const projectedG = rulData.projected_trend.map((p) => p.projected_vibration_g)

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return ''
          const item = params[0]
          return `<div style="font-size: 11px;"><strong>${item.axisValue}:</strong> ${item.data} g RMS</div>`
        },
      },
      grid: {
        top: 25,
        right: 15,
        bottom: 25,
        left: 40,
      },
      xAxis: {
        type: 'category',
        data: days,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 9, interval: 2 },
      },
      yAxis: {
        type: 'value',
        name: 'Vib (g)',
        nameTextStyle: { color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 9 },
        splitLine: { show: true, lineStyle: { color: 'rgba(51, 65, 85, 0.25)', type: 'dashed' } },
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
  }, [rulData])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. Header Bar with ISO 10816 Severity Indicator */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
          padding: '14px 18px',
          borderRadius: 'var(--radius-md, 10px)',
          border: '1px solid var(--border-main, rgba(148, 163, 184, 0.15))',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="#06b6d4" />
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text-main, #f8fafc)' }}>
              FFT Vibration Frequency Spectrum & ISO 10816-3 Diagnostics
            </h3>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-muted, #94a3b8)' }}>
            800 Hz Nyquist Band (0–400 Hz) • Harmonics & Bearing Fault Multipliers (BPFO / BPFI) • Shaft Speed: {spectrumData.rpm} RPM ({spectrumData.running_frequency_hz} Hz)
          </p>
        </div>

        {/* Unit Selector Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted, #94a3b8)' }}>Spectral Unit:</span>
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
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '12px',
        }}
      >
        {/* ISO 10816-3 Velocity Classification Card */}
        <div
          style={{
            background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
            padding: '14px',
            borderRadius: 'var(--radius-sm, 8px)',
            border: `1px solid ${
              spectrumData.iso_rating_status === 'critical'
                ? 'rgba(239, 68, 68, 0.4)'
                : spectrumData.iso_rating_status === 'warning'
                ? 'rgba(245, 158, 11, 0.4)'
                : 'rgba(6, 182, 212, 0.3)'
            }`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted, #94a3b8)' }}>
              ISO 10816-3 SEVERITY
            </span>
            <Layers size={14} color="#06b6d4" />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-main, #f8fafc)', fontFamily: 'JetBrains Mono' }}>
            {spectrumData.iso_velocity_mms_rms} <span style={{ fontSize: '12px', fontWeight: 400 }}>mm/s RMS</span>
          </div>
          <div
            style={{
              marginTop: '6px',
              fontSize: '11px',
              fontWeight: 600,
              color:
                spectrumData.iso_rating_status === 'critical'
                  ? '#ef4444'
                  : spectrumData.iso_rating_status === 'warning'
                  ? '#f59e0b'
                  : '#10b981',
            }}
          >
            ● {spectrumData.iso_zone}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', marginTop: '4px' }}>
            Standard Class I Electric Motor (up to 15 kW)
          </div>
        </div>

        {/* Bearing Fault Frequencies Card */}
        <div
          style={{
            background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
            padding: '14px',
            borderRadius: 'var(--radius-sm, 8px)',
            border: '1px solid var(--border-main, rgba(148, 163, 184, 0.15))',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted, #94a3b8)' }}>
              BEARING FAULT FREQS
            </span>
            <Cpu size={14} color="#8b5cf6" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', fontSize: '11px' }}>
            <div>
              <span style={{ color: '#ef4444', fontWeight: 600 }}>BPFO:</span> {spectrumData.bearing_frequencies.bpfo_hz} Hz
            </div>
            <div>
              <span style={{ color: '#f59e0b', fontWeight: 600 }}>BPFI:</span> {spectrumData.bearing_frequencies.bpfi_hz} Hz
            </div>
            <div>
              <span style={{ color: '#94a3b8' }}>BSF:</span> {spectrumData.bearing_frequencies.bsf_hz} Hz
            </div>
            <div>
              <span style={{ color: '#94a3b8' }}>FTF:</span> {spectrumData.bearing_frequencies.ftf_hz} Hz
            </div>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', marginTop: '6px' }}>
            Deep-groove 608/6204 bearing geometry
          </div>
        </div>

        {/* Remaining Useful Life (RUL) Card */}
        <div
          style={{
            background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
            padding: '14px',
            borderRadius: 'var(--radius-sm, 8px)',
            border: `1px solid ${
              rulData.failure_risk_level === 'CRITICAL'
                ? 'rgba(239, 68, 68, 0.4)'
                : rulData.failure_risk_level === 'ELEVATED'
                ? 'rgba(245, 158, 11, 0.4)'
                : 'rgba(16, 185, 129, 0.3)'
            }`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted, #94a3b8)' }}>
              PROGNOSTIC RUL
            </span>
            <Clock size={14} color="#10b981" />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-main, #f8fafc)', fontFamily: 'JetBrains Mono' }}>
            {rulData.estimated_rul_hours.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 400 }}>Hours</span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', marginTop: '4px' }}>
            ~{rulData.projected_days_to_maintenance} Days to Planned Overhaul
          </div>
          <div
            style={{
              marginTop: '4px',
              fontSize: '10px',
              fontWeight: 600,
              color:
                rulData.failure_risk_level === 'CRITICAL'
                  ? '#ef4444'
                  : rulData.failure_risk_level === 'ELEVATED'
                  ? '#f59e0b'
                  : '#10b981',
            }}
          >
            Risk Level: {rulData.failure_risk_level}
          </div>
        </div>

        {/* Degradation State & Dominant Factor */}
        <div
          style={{
            background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
            padding: '14px',
            borderRadius: 'var(--radius-sm, 8px)',
            border: '1px solid var(--border-main, rgba(148, 163, 184, 0.15))',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted, #94a3b8)' }}>
              HEALTH INDEX
            </span>
            <ShieldAlert size={14} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-main, #f8fafc)', fontFamily: 'JetBrains Mono' }}>
            {rulData.health_index} <span style={{ fontSize: '12px', fontWeight: 400 }}>/ 100</span>
          </div>
          <div style={{ marginTop: '6px' }}>
            <div style={{ height: '4px', background: 'rgba(51, 65, 85, 0.5)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${rulData.health_index}%`,
                  background:
                    rulData.health_index > 75
                      ? '#10b981'
                      : rulData.health_index > 40
                      ? '#f59e0b'
                      : '#ef4444',
                }}
              />
            </div>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', marginTop: '6px' }}>
            Primary Driver: <strong style={{ color: '#f8fafc' }}>{rulData.dominant_stress_factor.replace('_', ' ')}</strong>
          </div>
        </div>
      </div>

      {/* 3. Main FFT Spectrum Chart Viewport */}
      <div
        style={{
          background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
          borderRadius: 'var(--radius-md, 10px)',
          border: '1px solid var(--border-main, rgba(148, 163, 184, 0.15))',
          padding: '16px 16px 8px 16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main, #f8fafc)' }}>
            FFT Frequency Spectrum Breakdown (0 – 400 Hz)
          </span>
          <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
            <span style={{ color: '#06b6d4' }}>● 1x RPM ({spectrumData.running_frequency_hz} Hz)</span>
            <span style={{ color: '#8b5cf6' }}>● 2x Harmonics ({(spectrumData.running_frequency_hz * 2).toFixed(1)} Hz)</span>
            <span style={{ color: '#ef4444' }}>● BPFO ({spectrumData.bearing_frequencies.bpfo_hz} Hz)</span>
            <span style={{ color: '#f59e0b' }}>● BPFI ({spectrumData.bearing_frequencies.bpfi_hz} Hz)</span>
          </div>
        </div>
        <div ref={chartRef} style={{ width: '100%', height: '280px' }} />
      </div>

      {/* 4. 30-Day Prognostic Wear Projection Chart */}
      <div
        style={{
          background: 'var(--bg-card, rgba(15, 23, 42, 0.6))',
          borderRadius: 'var(--radius-md, 10px)',
          border: '1px solid var(--border-main, rgba(148, 163, 184, 0.15))',
          padding: '16px 16px 8px 16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main, #f8fafc)' }}>
            30-Day Prognostic Degradation Trajectory (Vibration Wear vs. Critical 0.8g Threshold)
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
            Confidence: {(rulData.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div ref={trendChartRef} style={{ width: '100%', height: '140px' }} />
      </div>
    </div>
  )
}
