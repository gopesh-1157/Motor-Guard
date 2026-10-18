import { useState, useMemo } from 'react'
import type { FC } from 'react'
import {
  Thermometer,
  Zap,
  Activity,
  Gauge,
  Copy,
  Check,
  FileSpreadsheet,
} from 'lucide-react'
import type { MotorState, ChartMetric } from '../types'
import { Motor3DViewer } from './Motor3DViewer'
import { EChartPanel } from './EChartPanel'

interface MotorDetailModalProps {
  motor: MotorState | null
  onClose: () => void
}

export const MotorDetailModal: FC<MotorDetailModalProps> = ({
  motor,
  onClose,
}) => {
  const [copied, setCopied] = useState(false)
  const [activeChartMetric, setActiveChartMetric] = useState<ChartMetric>('vibration')
  const [timeRange, setTimeRange] = useState<'15m' | '1h' | '24h'>('1h')

  const history = useMemo(() => motor?.history || [], [motor?.history])

  // Time-series points for charts
  const tempSeries = useMemo(() => {
    return history.map((h) => ({
      timestamp: h.timestamp,
      value: h.temperature,
      status: h.health_status,
    }))
  }, [history])

  const currSeries = useMemo(() => {
    return history.map((h) => ({
      timestamp: h.timestamp,
      value: h.current,
      status: h.health_status,
    }))
  }, [history])

  const vibSeries = useMemo(() => {
    return history.map((h) => ({
      timestamp: h.timestamp,
      value: h.vibration,
      status: h.health_status,
    }))
  }, [history])

  if (!motor) return null

  const { latest, connectionStatus } = motor
  const { sensors, sensor_status, inference, device_id, motor_id, source } = latest

  const curr = sensors.current_a
  const powerW = curr != null ? Number((12.0 * curr).toFixed(2)) : null

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(latest, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Export CSV for this motor
  const handleExportCSV = () => {
    const headers = [
      'Timestamp_ISO',
      'Motor_ID',
      'Device_ID',
      'Source',
      'Sequence',
      'Temp_C',
      'Current_A',
      'Vibration_g_RMS',
      'Power_W',
      'Health_Status',
      'Model_Confidence',
    ]
    const rows = history.map((h, i) => {
      const p = h.current != null ? (12.0 * h.current).toFixed(2) : ''
      return [
        `"${h.timestamp}"`,
        `"${motor_id}"`,
        `"${device_id}"`,
        `"${source}"`,
        i + 1,
        h.temperature != null ? h.temperature : '',
        h.current != null ? h.current : '',
        h.vibration != null ? h.vibration : '',
        p,
        `"${h.health_status}"`,
        inference.confidence != null ? inference.confidence : '',
      ]
    })

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute(
      'download',
      `MotorGuard_${motor_id}_telemetry_${new Date().toISOString().split('T')[0]}.csv`
    )
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const activeSeries =
    activeChartMetric === 'temperature'
      ? tempSeries
      : activeChartMetric === 'current'
      ? currSeries
      : vibSeries

  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 100 }}>
      <div
        className="modal-container"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1080px', width: '95%', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* Modal Header */}
        <div
          className="modal-header"
          style={{
            borderBottom: '1px solid var(--border-main)',
            padding: '16px 24px',
            background: 'var(--bg-card)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                {motor_id}
              </h2>
              <span className={`badge ${source === 'hardware' ? 'healthy' : 'simulator'}`}>
                {source.toUpperCase()}
              </span>
              <span
                className={`badge-status ${
                  connectionStatus === 'online'
                    ? 'healthy'
                    : connectionStatus === 'stale'
                    ? 'warning'
                    : 'critical'
                }`}
              >
                ● {connectionStatus.toUpperCase()}
              </span>
              <span className={`badge-status ${inference.health_status}`}>
                DIAGNOSIS: {inference.health_status.toUpperCase()}
              </span>
            </div>

            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <span>Assigned Node: <strong>{device_id}</strong></span>
              <span>•</span>
              <span>Facility: <strong>Plant Alpha • Line 1</strong></span>
              <span>•</span>
              <span>Last Event: <strong className="tabular-nums">{latest.timestamp}</strong></span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              className="btn-secondary"
              onClick={handleExportCSV}
              style={{ fontSize: '11px', padding: '6px 10px' }}
              title="Download full historical telemetry buffer as CSV"
            >
              <FileSpreadsheet size={13} />
              <span>Export CSV</span>
            </button>

            <button
              className="modal-close-btn"
              onClick={onClose}
              aria-label="Close modal"
              style={{ width: '32px', height: '32px' }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div
          className="modal-body"
          style={{ padding: '20px 24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}
        >
          {/* Primary 4 Metric Cards with Plain-English Interpretations */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
            {/* 1. Temp */}
            <div
              className={`metric-card ${activeChartMetric === 'temperature' ? 'active' : ''}`}
              onClick={() => setActiveChartMetric('temperature')}
              style={{ cursor: 'pointer', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}
            >
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '11px' }}>Temperature</span>
                <Thermometer size={14} color="var(--sensor-temp)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ fontSize: '22px', color: 'var(--sensor-temp)' }}>
                  {sensors.temperature_c != null ? sensors.temperature_c.toFixed(1) : '—'}
                </span>
                <span className="metric-unit">°C</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Warn: 50.0°C • Crit: 75.0°C</span>
                <span className={`status-pill ${sensor_status.temperature.toLowerCase()}`}>{sensor_status.temperature}</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-main)', background: 'var(--bg-subtle)', padding: '6px', borderRadius: '4px', lineHeight: 1.3 }}>
                {sensors.temperature_c != null ? (
                  sensors.temperature_c > 75.0 ? (
                    <span style={{ color: 'var(--status-critical)' }}>Critical: {sensors.temperature_c.toFixed(1)}°C exceeds the 75.0°C emergency shutdown limit.</span>
                  ) : sensors.temperature_c > 50.0 ? (
                    <span style={{ color: 'var(--status-warning)' }}>Warning: {sensors.temperature_c.toFixed(1)}°C exceeds the configured 50.0°C warning threshold.</span>
                  ) : (
                    <span>Temperature: {sensors.temperature_c.toFixed(1)}°C. This is below the configured 50.0°C warning threshold.</span>
                  )
                ) : 'Sensor disconnected.'}
              </div>
            </div>

            {/* 2. Current */}
            <div
              className={`metric-card ${activeChartMetric === 'current' ? 'active' : ''}`}
              onClick={() => setActiveChartMetric('current')}
              style={{ cursor: 'pointer', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}
            >
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '11px' }}>Armature Current</span>
                <Zap size={14} color="var(--sensor-curr)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ fontSize: '22px', color: 'var(--sensor-curr)' }}>
                  {sensors.current_a != null ? sensors.current_a.toFixed(2) : '—'}
                </span>
                <span className="metric-unit">A</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Trip Limit: 4.00 A</span>
                <span className={`status-pill ${sensor_status.current.toLowerCase()}`}>{sensor_status.current}</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-main)', background: 'var(--bg-subtle)', padding: '6px', borderRadius: '4px', lineHeight: 1.3 }}>
                {sensors.current_a != null ? (
                  sensors.current_a > 4.00 ? (
                    <span style={{ color: 'var(--status-critical)' }}>Overload: {sensors.current_a.toFixed(2)} A exceeds the configured 4.00 A trip limit.</span>
                  ) : sensors.current_a > 3.00 ? (
                    <span style={{ color: 'var(--status-warning)' }}>Current: {sensors.current_a.toFixed(2)} A is elevated near full-load capacity.</span>
                  ) : (
                    <span>Current: {sensors.current_a.toFixed(2)} A. This is below the configured 4.00 A warning threshold.</span>
                  )
                ) : 'Sensor disconnected.'}
              </div>
            </div>

            {/* 3. Vibration */}
            <div
              className={`metric-card ${activeChartMetric === 'vibration' ? 'active' : ''}`}
              onClick={() => setActiveChartMetric('vibration')}
              style={{ cursor: 'pointer', padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}
            >
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '11px' }}>3-Axis Dynamic Vibration</span>
                <Activity size={14} color="var(--sensor-vib)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ fontSize: '22px', color: 'var(--sensor-vib)' }}>
                  {sensors.vibration_g_rms != null ? sensors.vibration_g_rms.toFixed(3) : '—'}
                </span>
                <span className="metric-unit">g RMS</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>ISO 10816: 0.200 g RMS</span>
                <span className={`status-pill ${sensor_status.vibration.toLowerCase()}`}>{sensor_status.vibration}</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-main)', background: 'var(--bg-subtle)', padding: '6px', borderRadius: '4px', lineHeight: 1.3 }}>
                {sensors.vibration_g_rms != null ? (
                  sensors.vibration_g_rms > 0.400 ? (
                    <span style={{ color: 'var(--status-critical)' }}>Critical: {sensors.vibration_g_rms.toFixed(3)} g RMS indicates severe bearing or coupling distress.</span>
                  ) : sensors.vibration_g_rms > 0.200 ? (
                    <span style={{ color: 'var(--status-warning)' }}>Warning: {sensors.vibration_g_rms.toFixed(3)} g RMS exceeds ISO 10816 (0.200 g).</span>
                  ) : (
                    <span>Vibration: {sensors.vibration_g_rms.toFixed(3)} g RMS. This is below the configured 0.200 g warning threshold.</span>
                  )
                ) : 'Sensor disconnected.'}
              </div>
            </div>

            {/* 4. Power */}
            <div className="metric-card" style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div className="metric-header">
                <span className="metric-label" style={{ fontSize: '11px' }}>Power (12V Nominal)</span>
                <Gauge size={14} color="var(--sensor-power)" />
              </div>
              <div className="metric-value-row">
                <span className="metric-value tabular-nums" style={{ fontSize: '22px', color: 'var(--sensor-power)' }}>
                  {powerW != null ? powerW : '—'}
                </span>
                <span className="metric-unit">W</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                <span>Calculated: P = V &times; I</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-main)', background: 'var(--bg-subtle)', padding: '6px', borderRadius: '4px', lineHeight: 1.3 }}>
                {powerW != null ? `Active electrical draw: ${powerW} W across 12V DC bus.` : 'Awaiting current reading.'}
              </div>
            </div>
          </div>

          {/* Plain-English Condition Explanation & Operator Guidance (Non-Technical Readable) */}
          <div
            className="card"
            style={{
              padding: '16px',
              borderLeft: `4px solid ${
                connectionStatus === 'offline'
                  ? 'var(--text-muted)'
                  : inference.health_status === 'critical'
                  ? 'var(--status-critical)'
                  : inference.health_status === 'warning'
                  ? 'var(--status-warning)'
                  : 'var(--status-healthy)'
              }`,
              background: 'var(--bg-subtle)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)' }}>
                Plain-English Condition Explanation &amp; Operator Guidance
              </span>
              <span
                className={`badge-status ${
                  connectionStatus === 'offline'
                    ? 'warning'
                    : inference.health_status === 'critical'
                    ? 'critical'
                    : inference.health_status === 'warning'
                    ? 'warning'
                    : 'healthy'
                }`}
              >
                {connectionStatus === 'offline'
                  ? 'OFFLINE'
                  : inference.health_status.toUpperCase()}
              </span>
            </div>

            <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', margin: '0 0 10px 0' }}>
              {connectionStatus === 'offline'
                ? 'Offline: No recent readings have arrived. Check the ESP32, power supply, network, and sensor connections.'
                : inference.health_status === 'healthy'
                ? 'Healthy: The motor is operating within its configured monitoring limits.'
                : inference.health_status === 'warning'
                ? 'Warning: The motor has readings that need attention. Arrange an inspection.'
                : inference.health_status === 'critical'
                ? 'Critical: A serious fault condition has been detected. Inspect the motor promptly and follow the site\'s safety procedures.'
                : 'Unknown: There is not enough reliable data to determine the motor\'s condition.'}
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', fontSize: '12px' }}>
              <div>
                <strong style={{ color: 'var(--text-muted)' }}>What was detected:</strong>
                <div style={{ color: 'var(--text-main)', marginTop: '2px' }}>
                  {inference.health_status === 'critical'
                    ? `Critical fault: ${sensors.vibration_g_rms && sensors.vibration_g_rms > 0.4 ? 'Excessive bearing vibration' : sensors.temperature_c && sensors.temperature_c > 75 ? 'Overtemperature spike' : 'Multi-sensor anomaly'} flagged by TinyML with ${(inference.confidence * 100).toFixed(0)}% confidence.`
                    : inference.health_status === 'warning'
                    ? `Warning threshold exceeded on ${sensors.temperature_c && sensors.temperature_c > 50 ? 'thermal sensor (DHT11)' : 'vibration sensor (ADXL345)'}.`
                    : 'All physical sensor parameters (Temperature, Current, Vibration RMS) within baseline.'}
                </div>
              </div>

              <div>
                <strong style={{ color: 'var(--text-muted)' }}>Why it matters:</strong>
                <div style={{ color: 'var(--text-main)', marginTop: '2px' }}>
                  {inference.health_status === 'critical'
                    ? 'Unaddressed critical vibration or thermal runaway leads to catastrophic bearing seizure and production stoppage.'
                    : inference.health_status === 'warning'
                    ? 'Early detection of thermal/vibration drift allows planned lubrication or re-tensioning before mechanical damage occurs.'
                    : 'Motor is running efficiently with optimal magnetic flux and balanced mechanical bearings.'}
                </div>
              </div>

              <div>
                <strong style={{ color: 'var(--text-muted)' }}>Recommended operator action:</strong>
                <div style={{ color: 'var(--text-main)', marginTop: '2px' }}>
                  {inference.health_status === 'critical'
                    ? 'Escalate immediately to maintenance dispatch. Prepare for controlled line halt if vibration persists.'
                    : inference.health_status === 'warning'
                    ? 'Schedule a field technician inspection during the next routine maintenance window.'
                    : 'No corrective action needed. Continue routine plant monitoring.'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '10px', padding: '6px 10px', background: 'var(--bg-card)', borderRadius: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
              ⚠️ <em>Safety Notice: Sensor readings and ML predictions are indicators, not guarantees of mechanical safety. Follow plant Lockout/Tagout (LOTO) protocols before servicing.</em>
            </div>
          </div>

          {/* Interactive 3D Equipment Twin & Health Panel */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px' }}>
            {/* Interactive Telemetry Time-Series Chart */}
            <div className="card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '13px', fontWeight: 700, margin: 0 }}>
                    {activeChartMetric.toUpperCase()} Time Series &amp; Threshold Tracking
                  </h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {history.length} buffered points
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  {(['15m', '1h', '24h'] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => setTimeRange(r)}
                      style={{
                        padding: '3px 8px',
                        fontSize: '11px',
                        fontWeight: 600,
                        border: '1px solid var(--border-main)',
                        borderRadius: 'var(--radius-xs)',
                        background: timeRange === r ? 'var(--brand-primary-light)' : 'transparent',
                        color: timeRange === r ? 'var(--brand-primary)' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              <EChartPanel
                title={`${activeChartMetric.toUpperCase()} Telemetry`}
                metric={activeChartMetric}
                unit={activeChartMetric === 'temperature' ? '°C' : activeChartMetric === 'current' ? 'A' : 'g RMS'}
                motorId={motor_id}
                deviceId={device_id}
                data={activeSeries}
                timeRange={timeRange === '15m' ? '15m' : timeRange === '24h' ? '24h' : '1h'}
                thresholdWarn={activeChartMetric === 'temperature' ? 50 : activeChartMetric === 'current' ? 3.0 : 0.2}
                thresholdCrit={activeChartMetric === 'temperature' ? 75 : activeChartMetric === 'current' ? 4.0 : 0.8}
                isPrimary={true}
              />
            </div>

            {/* 3D Motor Shaft & Equipment Representation */}
            <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', fontWeight: 700 }}>3D Equipment Digital Twin</span>
                <span className={`badge-status ${inference.health_status}`} style={{ fontSize: '10px' }}>
                  {inference.health_status.toUpperCase()}
                </span>
              </div>

              <div style={{ flex: 1, minHeight: '180px', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                <Motor3DViewer
                  motorId={motor_id}
                  healthStatus={inference.health_status}
                  temperature={sensors.temperature_c}
                  current={sensors.current_a}
                  vibration={sensors.vibration_g_rms}
                />
              </div>

              <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Shaft Spin: <strong>{curr && curr > 0.1 ? 'ACTIVE' : 'IDLE'}</strong></span>
                <span>Thermal: <strong>{sensors.temperature_c ? `${sensors.temperature_c.toFixed(1)}°C` : 'N/A'}</strong></span>
              </div>
            </div>
          </div>

          {/* TinyML Edge Impulse Diagnosis Specification */}
          <div className="card" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '13px', fontWeight: 700, margin: 0 }}>
                  Edge Impulse TinyML Model Validation
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  On-device inference pipeline (Project #1133176 • MotoGuard Motor Health)
                </span>
              </div>

              <span className={`badge-status ${inference.status === 'PREDICTED' ? 'healthy' : 'warning'}`}>
                {inference.status === 'PREDICTED' ? 'INFERENCE ACTIVE' : 'INFERENCE UNAVAILABLE'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div style={{ background: 'var(--bg-subtle)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>MODEL DEPLOYMENT</span>
                <div style={{ fontSize: '12px', fontWeight: 600, marginTop: '2px' }}>
                  {inference.model_version || 'ei-motoguard-v1.0.1 (EON Compiled)'}
                </div>
              </div>

              <div style={{ background: 'var(--bg-subtle)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>INPUT FEATURES (TABULAR)</span>
                <div style={{ fontSize: '12px', fontWeight: 600, marginTop: '2px' }}>
                  temp_C + vib_g + current_A (3 Axes)
                </div>
              </div>

              <div style={{ background: 'var(--bg-subtle)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>CONFIDENCE SCORE</span>
                <div style={{ fontSize: '12px', fontWeight: 600, marginTop: '2px' }} className="tabular-nums">
                  {(inference.confidence * 100).toFixed(1)}% deterministic
                </div>
              </div>

              <div style={{ background: 'var(--bg-subtle)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>INFERENCE LATENCY</span>
                <div style={{ fontSize: '12px', fontWeight: 600, marginTop: '2px' }} className="tabular-nums">
                  {inference.inference_time_ms ? `${inference.inference_time_ms} ms` : '5 ms'}
                </div>
              </div>
            </div>

            {/* Class Probabilities Bar */}
            {inference.probabilities && (
              <div style={{ marginTop: '14px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Model Class Probabilities Breakdown:
                </span>
                <div style={{ display: 'flex', gap: '12px', marginTop: '6px' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                      <span style={{ color: 'var(--status-healthy)', fontWeight: 600 }}>Healthy</span>
                      <strong className="tabular-nums">{(inference.probabilities.healthy * 100).toFixed(1)}%</strong>
                    </div>
                    <div style={{ height: '6px', background: 'var(--border-subtle)', borderRadius: '3px', overflow: 'hidden', marginTop: '2px' }}>
                      <div
                        style={{
                          width: `${inference.probabilities.healthy * 100}%`,
                          height: '100%',
                          background: 'var(--status-healthy)',
                        }}
                      />
                    </div>
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                      <span style={{ color: 'var(--status-warning)', fontWeight: 600 }}>Warning</span>
                      <strong className="tabular-nums">{(inference.probabilities.warning * 100).toFixed(1)}%</strong>
                    </div>
                    <div style={{ height: '6px', background: 'var(--border-subtle)', borderRadius: '3px', overflow: 'hidden', marginTop: '2px' }}>
                      <div
                        style={{
                          width: `${inference.probabilities.warning * 100}%`,
                          height: '100%',
                          background: 'var(--status-warning)',
                        }}
                      />
                    </div>
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                      <span style={{ color: 'var(--status-critical)', fontWeight: 600 }}>Critical</span>
                      <strong className="tabular-nums">{(inference.probabilities.critical * 100).toFixed(1)}%</strong>
                    </div>
                    <div style={{ height: '6px', background: 'var(--border-subtle)', borderRadius: '3px', overflow: 'hidden', marginTop: '2px' }}>
                      <div
                        style={{
                          width: `${inference.probabilities.critical * 100}%`,
                          height: '100%',
                          background: 'var(--status-critical)',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Diagnostics and Raw Telemetry JSON */}
          <div className="card" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700 }}>Telemetry Contract Payload (JSON)</span>
              <button
                className="btn-secondary"
                onClick={handleCopyJson}
                style={{ padding: '4px 8px', fontSize: '11px' }}
              >
                {copied ? <Check size={12} color="var(--status-healthy)" /> : <Copy size={12} />}
                <span>{copied ? 'Copied' : 'Copy Payload'}</span>
              </button>
            </div>
            <pre
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-main)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                overflowX: 'auto',
                margin: 0,
                maxHeight: '160px',
              }}
            >
              {JSON.stringify(latest, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
