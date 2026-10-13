import { useState, useMemo, useEffect, useRef } from 'react'
import type { FC } from 'react'
import {
  Play,
  Pause,
  RotateCcw,
  LayoutGrid,
  Square,
  Thermometer,
  Zap,
  Activity,
  Gauge,
  Clock,
  ExternalLink,
  ChevronRight,
} from 'lucide-react'
import type { MotorState, ChartMetric } from '../types'
import { EChartPanel } from './EChartPanel'
import { Motor3DViewer } from './Motor3DViewer'

interface LiveMonitoringViewProps {
  motors: MotorState[]
  selectedMotorId: string
  onSelectMotor: (id: string) => void
  onInspectMotorDetail: (motor: MotorState) => void
  wsConnected: boolean
}

interface TelemetryLogRow {
  id: string
  timestamp: string
  motor_id: string
  device_id: string
  source: string
  seq: number
  temp: number | null
  current: number | null
  vib: number | null
  power: number | null
  health: string
  confidence: number
}

export const LiveMonitoringView: FC<LiveMonitoringViewProps> = ({
  motors,
  selectedMotorId,
  onSelectMotor,
  onInspectMotorDetail,
  wsConnected,
}) => {
  // View mode: 'single' (focused asset deep-dive) or 'multi' (plant floor multi-gauge grid)
  const [viewMode, setViewMode] = useState<'single' | 'multi'>('single')
  const [isPaused, setIsPaused] = useState(false)
  const [show3D, setShow3D] = useState(true)
  const [activeMetric, setActiveMetric] = useState<ChartMetric>('vibration')
  const [eventLog, setEventLog] = useState<TelemetryLogRow[]>([])

  // Find currently selected motor or default to first
  const currentMotor = useMemo(() => {
    return motors.find((m) => m.motor_id === selectedMotorId) || motors[0]
  }, [motors, selectedMotorId])

  // Track incoming telemetry into streaming log table (bounded to last 50 events)
  const lastEventRef = useRef<string>('')
  useEffect(() => {
    if (isPaused || !currentMotor) return

    const latest = currentMotor.latest
    if (!latest || latest.event_id === lastEventRef.current) return
    lastEventRef.current = latest.event_id

    const curr = latest.sensors.current_a
    const pwr = curr != null ? Number((12.0 * curr).toFixed(2)) : null

    const newRow: TelemetryLogRow = {
      id: latest.event_id,
      timestamp: latest.timestamp,
      motor_id: latest.motor_id,
      device_id: latest.device_id,
      source: latest.source,
      seq: latest.seq,
      temp: latest.sensors.temperature_c ?? null,
      current: curr ?? null,
      vib: latest.sensors.vibration_g_rms ?? null,
      power: pwr,
      health: latest.inference.health_status,
      confidence: latest.inference.confidence,
    }

    setEventLog((prev) => [newRow, ...prev.slice(0, 49)])
  }, [currentMotor, isPaused])

  // Compute freshness (seconds since last update)
  const [freshnessSec, setFreshnessSec] = useState<number>(0)
  useEffect(() => {
    const interval = setInterval(() => {
      if (currentMotor?.lastSeen) {
        const diff = Math.max(0, Math.round((Date.now() - currentMotor.lastSeen) / 1000))
        setFreshnessSec(diff)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [currentMotor])

  if (!currentMotor) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No registered motors found in plant registry.</p>
      </div>
    )
  }

  const { latest, history } = currentMotor
  const { sensors, sensor_status, inference, device_id, motor_id, source } = latest

  const curr = sensors.current_a
  const powerW = curr != null ? (12.0 * curr).toFixed(2) : '—'

  // Time-series buffers for ECharts
  const tempSeries = history.map((h) => ({
    timestamp: h.timestamp,
    value: h.temperature,
    status: h.health_status,
  }))

  const currSeries = history.map((h) => ({
    timestamp: h.timestamp,
    value: h.current,
    status: h.health_status,
  }))

  const vibSeries = history.map((h) => ({
    timestamp: h.timestamp,
    value: h.vibration,
    status: h.health_status,
  }))

  const activeSeries =
    activeMetric === 'temperature' ? tempSeries : activeMetric === 'current' ? currSeries : vibSeries

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Page Header with Real-Time Stream Controls */}
      <div className="page-header" style={{ alignItems: 'flex-start' }}>
        <div className="page-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 className="page-title">Live Telemetry &amp; Stream Monitor</h2>
            <span
              className={`badge-status ${wsConnected ? 'healthy' : 'critical'}`}
              style={{ fontSize: '11px' }}
            >
              {wsConnected ? 'LIVE WS' : 'WS RECONNECTING'}
            </span>
            {isPaused && (
              <span
                className="badge-status warning"
                style={{ fontSize: '11px' }}
              >
                STREAM PAUSED
              </span>
            )}
          </div>
          <p className="page-description">
            High-frequency deterministic telemetry pipeline: ESP32 &rarr; Mosquitto MQTT &rarr; FastAPI &rarr; WebSockets.
          </p>
        </div>

        {/* Toolbar Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* View mode toggle */}
          <div
            style={{
              display: 'flex',
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-main)',
              borderRadius: 'var(--radius-sm)',
              padding: '2px',
            }}
          >
            <button
              onClick={() => setViewMode('single')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
                borderRadius: 'var(--radius-xs)',
                cursor: 'pointer',
                background: viewMode === 'single' ? '#FFFFFF' : 'transparent',
                color: viewMode === 'single' ? 'var(--brand-primary)' : 'var(--text-secondary)',
                boxShadow: viewMode === 'single' ? 'var(--shadow-xs)' : 'none',
              }}
            >
              <Square size={14} />
              <span>Single Asset</span>
            </button>

            <button
              onClick={() => setViewMode('multi')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
                borderRadius: 'var(--radius-xs)',
                cursor: 'pointer',
                background: viewMode === 'multi' ? '#FFFFFF' : 'transparent',
                color: viewMode === 'multi' ? 'var(--brand-primary)' : 'var(--text-secondary)',
                boxShadow: viewMode === 'multi' ? 'var(--shadow-xs)' : 'none',
              }}
            >
              <LayoutGrid size={14} />
              <span>Multi-Asset Grid</span>
            </button>
          </div>

          {/* Pause / Resume button */}
          <button
            className={`btn-secondary ${isPaused ? 'active' : ''}`}
            onClick={() => setIsPaused((prev) => !prev)}
            style={{
              borderColor: isPaused ? 'var(--status-warning)' : 'var(--border-main)',
              color: isPaused ? 'var(--status-warning)' : 'var(--text-main)',
            }}
          >
            {isPaused ? <Play size={14} /> : <Pause size={14} />}
            <span>{isPaused ? 'Resume Stream' : 'Pause Live'}</span>
          </button>

          {/* Clear Log Buffer */}
          <button
            className="btn-secondary"
            onClick={() => setEventLog([])}
            title="Clear event log history"
          >
            <RotateCcw size={14} />
            <span>Reset Log</span>
          </button>
        </div>
      </div>

      {/* SINGLE MOTOR DEEP-DIVE VIEW */}
      {viewMode === 'single' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Active Asset Selector Bar */}
          <div
            className="card"
            style={{
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Target Motor Asset:
              </span>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {motors.map((m) => (
                  <button
                    key={m.motor_id}
                    onClick={() => onSelectMotor(m.motor_id)}
                    style={{
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      borderRadius: 'var(--radius-sm)',
                      border: m.motor_id === motor_id ? '1px solid var(--brand-primary)' : '1px solid var(--border-main)',
                      background: m.motor_id === motor_id ? 'var(--brand-primary-light)' : 'var(--bg-card)',
                      color: m.motor_id === motor_id ? 'var(--brand-primary)' : 'var(--text-main)',
                      cursor: 'pointer',
                    }}
                  >
                    {m.motor_id}
                    <span
                      style={{
                        marginLeft: '6px',
                        display: 'inline-block',
                        width: '7px',
                        height: '7px',
                        borderRadius: '50%',
                        background:
                          m.latest.inference.health_status === 'healthy'
                            ? 'var(--status-healthy)'
                            : m.latest.inference.health_status === 'warning'
                            ? 'var(--status-warning)'
                            : 'var(--status-critical)',
                      }}
                    />
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Clock size={14} color="var(--text-muted)" />
                <span style={{ color: 'var(--text-secondary)' }}>Freshness:</span>
                <strong
                  className="tabular-nums"
                  style={{
                    color: freshnessSec > 15 ? 'var(--status-critical)' : freshnessSec > 6 ? 'var(--status-warning)' : 'var(--status-healthy)',
                  }}
                >
                  {freshnessSec}s ago
                </strong>
              </div>

              <button
                className="btn-secondary"
                onClick={() => onInspectMotorDetail(currentMotor)}
                style={{ padding: '4px 10px', fontSize: '11px' }}
              >
                <span>Full Asset Specs</span>
                <ExternalLink size={12} />
              </button>
            </div>
          </div>

          {/* Primary 4 Live Telemetry Gauges */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '16px',
            }}
          >
            {/* 1. Temperature Gauge */}
            <div
              className={`metric-card ${activeMetric === 'temperature' ? 'active' : ''}`}
              onClick={() => setActiveMetric('temperature')}
              style={{
                cursor: 'pointer',
                borderColor: activeMetric === 'temperature' ? 'var(--sensor-temp)' : undefined,
              }}
            >
              <div className="metric-header">
                <span className="metric-label">Armature / Bearing Temp</span>
                <Thermometer size={16} color="var(--sensor-temp)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ color: 'var(--sensor-temp)' }}>
                  {sensors.temperature_c != null ? sensors.temperature_c.toFixed(1) : '—'}
                </span>
                <span className="metric-unit">°C</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>Threshold: &le; 50.0 °C</span>
                <span className={`status-pill ${sensor_status.temperature.toLowerCase()}`}>
                  {sensor_status.temperature}
                </span>
              </div>
            </div>

            {/* 2. Armature Current Gauge */}
            <div
              className={`metric-card ${activeMetric === 'current' ? 'active' : ''}`}
              onClick={() => setActiveMetric('current')}
              style={{
                cursor: 'pointer',
                borderColor: activeMetric === 'current' ? 'var(--sensor-curr)' : undefined,
              }}
            >
              <div className="metric-header">
                <span className="metric-label">Armature Current</span>
                <Zap size={16} color="var(--sensor-curr)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ color: 'var(--sensor-curr)' }}>
                  {sensors.current_a != null ? sensors.current_a.toFixed(2) : '—'}
                </span>
                <span className="metric-unit">A</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>Threshold: &le; 3.00 A</span>
                <span className={`status-pill ${sensor_status.current.toLowerCase()}`}>
                  {sensor_status.current}
                </span>
              </div>
            </div>

            {/* 3. Dynamic Vibration RMS Gauge */}
            <div
              className={`metric-card ${activeMetric === 'vibration' ? 'active' : ''}`}
              onClick={() => setActiveMetric('vibration')}
              style={{
                cursor: 'pointer',
                borderColor: activeMetric === 'vibration' ? 'var(--sensor-vib)' : undefined,
              }}
            >
              <div className="metric-header">
                <span className="metric-label">3-Axis Vibration RMS</span>
                <Activity size={16} color="var(--sensor-vib)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ color: 'var(--sensor-vib)' }}>
                  {sensors.vibration_g_rms != null ? sensors.vibration_g_rms.toFixed(3) : '—'}
                </span>
                <span className="metric-unit">g RMS</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>ISO 10816: &le; 0.200 g</span>
                <span className={`status-pill ${sensor_status.vibration.toLowerCase()}`}>
                  {sensor_status.vibration}
                </span>
              </div>
            </div>

            {/* 4. Active Power Gauge */}
            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-label">Active Power (P = V &times; I)</span>
                <Gauge size={16} color="var(--sensor-power)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ color: 'var(--sensor-power)' }}>
                  {powerW}
                </span>
                <span className="metric-unit">W</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>Rated Voltage: 12.0 VDC</span>
                <span className="badge-status healthy" style={{ fontSize: '10px' }}>
                  MEASURED
                </span>
              </div>
            </div>
          </div>

          {/* Real-time High-Resolution Telemetry Chart & 3D Spatial Twin */}
          <div style={{ display: 'grid', gridTemplateColumns: show3D ? '1fr 340px' : '1fr', gap: '16px' }}>
            <div className="card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>
                    Live {activeMetric.toUpperCase()} Time Series ({motor_id})
                  </h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    Continuous bounded rolling chart • Buffer size: {history.length} samples
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn-secondary"
                    onClick={() => setShow3D((prev) => !prev)}
                    style={{ fontSize: '11px', padding: '4px 8px' }}
                  >
                    {show3D ? 'Hide 3D View' : 'Show 3D View'}
                  </button>
                </div>
              </div>

              <EChartPanel
                title={`${activeMetric.toUpperCase()} Live Stream`}
                metric={activeMetric}
                unit={activeMetric === 'temperature' ? '°C' : activeMetric === 'current' ? 'A' : 'g RMS'}
                motorId={motor_id}
                deviceId={device_id}
                data={activeSeries}
                timeRange="1h"
                thresholdWarn={activeMetric === 'temperature' ? 50 : activeMetric === 'current' ? 3.0 : 0.2}
                thresholdCrit={activeMetric === 'temperature' ? 75 : activeMetric === 'current' ? 4.0 : 0.8}
                isPrimary={true}
              />
            </div>

            {/* 3D Physical Motor Representation */}
            {show3D && (
              <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div>
                    <h3 style={{ fontSize: '13px', fontWeight: 700, margin: 0 }}>
                      Physical 3D Equipment Twin
                    </h3>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Shaft RPM &amp; Thermal Mesh
                    </span>
                  </div>
                  <span
                    className={`badge-status ${
                      inference.health_status === 'healthy'
                        ? 'healthy'
                        : inference.health_status === 'warning'
                        ? 'warning'
                        : 'critical'
                    }`}
                  >
                    {inference.health_status.toUpperCase()}
                  </span>
                </div>

                <div style={{ flex: 1, minHeight: '220px', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                  <Motor3DViewer
                    motorId={motor_id}
                    healthStatus={inference.health_status}
                    temperature={sensors.temperature_c}
                    current={sensors.current_a}
                    vibration={sensors.vibration_g_rms}
                  />
                </div>

                <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                  <span>Device: <strong>{device_id}</strong></span>
                  <span>Source: <strong>{source.toUpperCase()}</strong></span>
                </div>
              </div>
            )}
          </div>

          {/* Live Ingested Telemetry Event Stream Table */}
          <div className="card" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>
                  Incoming Event Stream Log ({eventLog.length} Frames Buffer)
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Idempotent telemetry contracts accepted via WebSocket
                </span>
              </div>
              <span className="badge-status healthy" style={{ fontSize: '11px' }}>
                QoS 1 INGESTION
              </span>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="compact-table" style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-main)' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Time (UTC)</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Seq</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Motor ID</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Device ID</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Source</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Temp (°C)</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Current (A)</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Vibration (g)</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Power (W)</th>
                    <th style={{ padding: '8px 12px', textAlign: 'center' }}>TinyML Health</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {eventLog.length === 0 ? (
                    <tr>
                      <td colSpan={11} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        Streaming telemetry log initializing...
                      </td>
                    </tr>
                  ) : (
                    eventLog.map((row) => (
                      <tr
                        key={row.id}
                        style={{
                          borderBottom: '1px solid var(--border-subtle)',
                        }}
                      >
                        <td style={{ padding: '6px 12px', fontFamily: 'var(--font-mono)' }}>
                          {row.timestamp.split('T')[1]?.slice(0, 12) || row.timestamp}
                        </td>
                        <td style={{ padding: '6px 12px', fontFamily: 'var(--font-mono)' }}>#{row.seq}</td>
                        <td style={{ padding: '6px 12px', fontWeight: 600 }}>{row.motor_id}</td>
                        <td style={{ padding: '6px 12px', color: 'var(--text-secondary)' }}>{row.device_id}</td>
                        <td style={{ padding: '6px 12px' }}>
                          <span className={`badge ${row.source === 'hardware' ? 'healthy' : 'simulator'}`}>
                            {row.source.toUpperCase()}
                          </span>
                        </td>
                        <td className="tabular-nums" style={{ padding: '6px 12px', textAlign: 'right' }}>
                          {row.temp != null ? `${row.temp.toFixed(1)}` : '—'}
                        </td>
                        <td className="tabular-nums" style={{ padding: '6px 12px', textAlign: 'right' }}>
                          {row.current != null ? `${row.current.toFixed(2)}` : '—'}
                        </td>
                        <td className="tabular-nums" style={{ padding: '6px 12px', textAlign: 'right' }}>
                          {row.vib != null ? `${row.vib.toFixed(3)}` : '—'}
                        </td>
                        <td className="tabular-nums" style={{ padding: '6px 12px', textAlign: 'right' }}>
                          {row.power != null ? `${row.power.toFixed(2)}` : '—'}
                        </td>
                        <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                          <span className={`badge-status ${row.health}`}>
                            {row.health.toUpperCase()}
                          </span>
                        </td>
                        <td className="tabular-nums" style={{ padding: '6px 12px', textAlign: 'right' }}>
                          {(row.confidence * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MULTI-ASSET GRID VIEW */}
      {viewMode === 'multi' && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '16px',
          }}
        >
          {motors.map((m) => {
            const mLatest = m.latest
            const mSensors = mLatest.sensors
            const mInf = mLatest.inference
            const mPower = mSensors.current_a != null ? (12.0 * mSensors.current_a).toFixed(2) : '—'

            return (
              <div
                key={m.motor_id}
                className="card"
                style={{
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  borderTop:
                    mInf.health_status === 'healthy'
                      ? '3px solid var(--status-healthy)'
                      : mInf.health_status === 'warning'
                      ? '3px solid var(--status-warning)'
                      : '3px solid var(--status-critical)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>{m.motor_id}</h3>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Node: {m.device_id} • {m.source.toUpperCase()}
                    </span>
                  </div>

                  <span className={`badge-status ${mInf.health_status}`}>
                    {mInf.health_status.toUpperCase()}
                  </span>
                </div>

                {/* 4 Sensor Values */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '8px',
                    background: 'var(--bg-subtle)',
                    padding: '10px',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>TEMP</span>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sensor-temp)' }} className="tabular-nums">
                      {mSensors.temperature_c != null ? `${mSensors.temperature_c.toFixed(1)} °C` : '—'}
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>CURRENT</span>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sensor-curr)' }} className="tabular-nums">
                      {mSensors.current_a != null ? `${mSensors.current_a.toFixed(2)} A` : '—'}
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>VIBRATION</span>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sensor-vib)' }} className="tabular-nums">
                      {mSensors.vibration_g_rms != null ? `${mSensors.vibration_g_rms.toFixed(3)} g` : '—'}
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>POWER</span>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sensor-power)' }} className="tabular-nums">
                      {mPower} W
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Model: {(mInf.confidence * 100).toFixed(0)}% conf
                  </span>

                  <button
                    className="btn-secondary"
                    onClick={() => {
                      onSelectMotor(m.motor_id)
                      setViewMode('single')
                    }}
                    style={{ fontSize: '11px', padding: '4px 8px' }}
                  >
                    <span>Focus Stream</span>
                    <ChevronRight size={12} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
