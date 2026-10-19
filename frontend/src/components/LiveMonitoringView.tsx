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
  AlertTriangle,
} from 'lucide-react'
import type { MotorState, ChartMetric, AlertItem } from '../types'
import { EChartPanel } from './EChartPanel'
import { Motor3DViewer } from './Motor3DViewer'

interface MotorAlertEvaluation {
  severity: 'critical' | 'warning' | 'healthy' | 'stale' | 'offline'
  label: 'CRITICAL' | 'WARNING' | 'HEALTHY' | 'STALE' | 'OFFLINE'
  activeReason?: string
}

function getLiveMotorAlertStatus(
  motor: MotorState,
  alerts?: AlertItem[],
  freshnessSec: number = 0
): MotorAlertEvaluation {
  // 1. Check Stale / Offline timeout status
  const isOffline = motor.connectionStatus === 'offline' || (motor.lastSeen > 0 && freshnessSec > 35)
  const isStale = motor.connectionStatus === 'stale' || (motor.lastSeen > 0 && freshnessSec > 15)

  // 2. Active backend alerts for this specific motor
  const motorActiveAlerts = alerts
    ? alerts.filter((a) => a.motor_id === motor.motor_id && a.state === 'ACTIVE')
    : []

  const criticalBackendAlert = motorActiveAlerts.find((a) => a.severity === 'CRITICAL')
  const warningBackendAlert = motorActiveAlerts.find((a) => a.severity === 'WARNING')

  // 3. Independent rule-based safety evaluation in latest telemetry
  const safetyStatus = motor.latest?.safety?.status
  const safetyReasons = motor.latest?.safety?.active_reasons || []

  // Rule: Critical alerts take absolute precedence over Warning alerts
  if (criticalBackendAlert) {
    return {
      severity: 'critical',
      label: 'CRITICAL',
      activeReason: criticalBackendAlert.message,
    }
  }

  if (safetyStatus === 'CRITICAL') {
    return {
      severity: 'critical',
      label: 'CRITICAL',
      activeReason: safetyReasons[0] || 'Critical safety threshold trip',
    }
  }

  // 4. Warning alerts (only when no critical is active)
  if (warningBackendAlert) {
    return {
      severity: 'warning',
      label: 'WARNING',
      activeReason: warningBackendAlert.message,
    }
  }

  if (safetyStatus === 'WARNING') {
    return {
      severity: 'warning',
      label: 'WARNING',
      activeReason: safetyReasons[0] || 'Safety warning threshold exceeded',
    }
  }

  // 5. ML prediction fallback (ML healthy can never suppress safety trips)
  const mlStatus = motor.latest?.inference?.health_status
  if (mlStatus === 'critical') {
    return {
      severity: 'critical',
      label: 'CRITICAL',
      activeReason: 'TinyML model diagnosed critical condition',
    }
  }
  if (mlStatus === 'warning') {
    return {
      severity: 'warning',
      label: 'WARNING',
      activeReason: 'TinyML model flagged operating anomaly',
    }
  }

  // 6. Offline / Stale state when no active safety violation
  if (isOffline) {
    return { severity: 'offline', label: 'OFFLINE' }
  }
  if (isStale) {
    return { severity: 'stale', label: 'STALE' }
  }

  // 7. Normal steady healthy baseline
  return {
    severity: 'healthy',
    label: 'HEALTHY',
  }
}

interface LiveMonitoringViewProps {
  motors: MotorState[]
  selectedMotorId: string
  onSelectMotor: (id: string) => void
  onInspectMotorDetail: (motor: MotorState) => void
  wsConnected: boolean
  alerts?: AlertItem[]
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
  alerts,
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
  const [nowTs, setNowTs] = useState<number>(() => Date.now())
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      setNowTs(now)
      if (currentMotor?.lastSeen) {
        const diff = Math.max(0, Math.round((now - currentMotor.lastSeen) / 1000))
        setFreshnessSec(diff)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [currentMotor])

  // Unified alert status evaluation for currently selected motor
  const currentStatus = useMemo(() => {
    if (!currentMotor) return { severity: 'offline', label: 'OFFLINE' } as MotorAlertEvaluation
    return getLiveMotorAlertStatus(currentMotor, alerts, freshnessSec)
  }, [currentMotor, alerts, freshnessSec])

  if (!currentMotor) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No registered motors found in plant registry.</p>
      </div>
    )
  }

  const { latest, history } = currentMotor
  const { sensors, sensor_status, device_id, motor_id, source } = latest

  const curr = sensors.current_a
  const powerW = curr != null ? (12.0 * curr).toFixed(2) : '—'

  // Effective thresholds resolved from motor-specific overrides or gateway defaults
  const effectiveWarnTemp = currentMotor.effective_thresholds?.temperature_warning_c ?? currentMotor.thresholds?.temperature_warning_c ?? 50.0
  const effectiveCritTemp = currentMotor.effective_thresholds?.temperature_critical_c ?? currentMotor.thresholds?.temperature_critical_c ?? 75.0
  const effectiveWarnCurr = currentMotor.effective_thresholds?.current_warning_a ?? currentMotor.thresholds?.current_warning_a ?? 3.0
  const effectiveCritCurr = currentMotor.effective_thresholds?.current_critical_a ?? currentMotor.thresholds?.current_critical_a ?? 4.0
  const effectiveWarnVib = currentMotor.effective_thresholds?.vibration_warning_g ?? currentMotor.thresholds?.vibration_warning_g ?? 0.20
  const effectiveCritVib = currentMotor.effective_thresholds?.vibration_critical_g ?? currentMotor.thresholds?.vibration_critical_g ?? 0.80

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
                {motors.map((m) => {
                  const mFresh = m.lastSeen ? Math.max(0, Math.round((nowTs - m.lastSeen) / 1000)) : 0
                  const mStatus = getLiveMotorAlertStatus(m, alerts, mFresh)
                  const isSelected = m.motor_id === motor_id
                  return (
                    <button
                      key={m.motor_id}
                      onClick={() => onSelectMotor(m.motor_id)}
                      className={`live-monitor-selector-btn ${
                        mStatus.severity === 'critical'
                          ? 'critical'
                          : mStatus.severity === 'warning'
                          ? 'warning'
                          : ''
                      }`}
                      style={{
                        padding: '6px 12px',
                        fontSize: '12px',
                        fontWeight: 600,
                        borderRadius: 'var(--radius-sm)',
                        border: isSelected ? '1px solid var(--brand-primary)' : '1px solid var(--border-main)',
                        background: isSelected ? 'var(--brand-primary-light)' : 'var(--bg-card)',
                        color: isSelected ? 'var(--brand-primary)' : 'var(--text-main)',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {m.motor_id}
                      <span className={`live-monitor-dot ${mStatus.severity}`} />
                    </button>
                  )
                })}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Status:</span>
                <span
                  className={`live-monitor-badge ${
                    currentStatus.severity === 'critical'
                      ? 'live-blink-critical'
                      : currentStatus.severity === 'warning'
                      ? 'live-blink-warning'
                      : currentStatus.severity
                  }`}
                >
                  {(currentStatus.severity === 'critical' || currentStatus.severity === 'warning') && (
                    <AlertTriangle size={12} />
                  )}
                  {currentStatus.label}
                </span>
              </div>

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

          {/* Active Alert Banner for Focused Asset */}
          {currentStatus.activeReason && (currentStatus.severity === 'critical' || currentStatus.severity === 'warning') && (
            <div className={`live-monitor-alert-banner ${currentStatus.severity}`}>
              <AlertTriangle size={16} style={{ flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{ fontWeight: 700, letterSpacing: '0.02em' }}>
                  {currentStatus.label} ALERT ACTIVE FOR {motor_id}
                </span>
                <span style={{ fontSize: '12px', opacity: 0.95 }}>
                  {currentStatus.activeReason}
                </span>
              </div>
            </div>
          )}

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
                <span className="metric-label">Chassis / Ambient Temp (DHT11)</span>
                <Thermometer size={16} color="var(--sensor-temp)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ color: 'var(--sensor-temp)' }}>
                  {sensors.temperature_c != null ? sensors.temperature_c.toFixed(1) : '—'}
                </span>
                <span className="metric-unit">°C</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>Threshold: &le; {effectiveWarnTemp.toFixed(1)} °C</span>
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
                <span>Threshold: &le; {effectiveWarnCurr.toFixed(2)} A</span>
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
                <span>ISO 10816: &le; {effectiveWarnVib.toFixed(3)} g RMS</span>
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
                thresholdWarn={activeMetric === 'temperature' ? effectiveWarnTemp : activeMetric === 'current' ? effectiveWarnCurr : effectiveWarnVib}
                thresholdCrit={activeMetric === 'temperature' ? effectiveCritTemp : activeMetric === 'current' ? effectiveCritCurr : effectiveCritVib}
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
                    className={`live-monitor-badge ${
                      currentStatus.severity === 'critical'
                        ? 'live-blink-critical'
                        : currentStatus.severity === 'warning'
                        ? 'live-blink-warning'
                        : currentStatus.severity
                    }`}
                  >
                    {(currentStatus.severity === 'critical' || currentStatus.severity === 'warning') && (
                      <AlertTriangle size={12} />
                    )}
                    {currentStatus.label}
                  </span>
                </div>

                <div style={{ flex: 1, minHeight: '220px', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                  <Motor3DViewer
                    motorId={motor_id}
                    healthStatus={
                      currentStatus.severity === 'critical'
                        ? 'critical'
                        : currentStatus.severity === 'warning'
                        ? 'warning'
                        : 'healthy'
                    }
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
            const mFresh = m.lastSeen ? Math.max(0, Math.round((nowTs - m.lastSeen) / 1000)) : 0
            const mStatus = getLiveMotorAlertStatus(m, alerts, mFresh)

            return (
              <div
                key={m.motor_id}
                className={`card live-monitor-grid-card ${
                  mStatus.severity === 'critical'
                    ? 'critical'
                    : mStatus.severity === 'warning'
                    ? 'warning'
                    : ''
                }`}
                style={{
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  borderTop:
                    mStatus.severity === 'critical'
                      ? '3px solid var(--status-critical)'
                      : mStatus.severity === 'warning'
                      ? '3px solid var(--status-warning)'
                      : mStatus.severity === 'healthy'
                      ? '3px solid var(--status-healthy)'
                      : '3px solid var(--status-neutral)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {m.motor_id}
                      <span className={`live-monitor-dot ${mStatus.severity}`} />
                    </h3>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Node: {m.device_id} • {m.source.toUpperCase()}
                    </span>
                  </div>

                  <span
                    className={`live-monitor-badge ${
                      mStatus.severity === 'critical'
                        ? 'live-blink-critical'
                        : mStatus.severity === 'warning'
                        ? 'live-blink-warning'
                        : mStatus.severity
                    }`}
                  >
                    {(mStatus.severity === 'critical' || mStatus.severity === 'warning') && (
                      <AlertTriangle size={12} />
                    )}
                    {mStatus.label}
                  </span>
                </div>

                {/* Active Alert Banner inside Multi-Asset Card */}
                {mStatus.activeReason && (mStatus.severity === 'critical' || mStatus.severity === 'warning') && (
                  <div className={`live-monitor-alert-banner ${mStatus.severity}`}>
                    <AlertTriangle size={12} style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {mStatus.activeReason}
                    </span>
                  </div>
                )}

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
