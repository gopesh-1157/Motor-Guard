import type { FC } from 'react'
import { useMemo } from 'react'
import type { MotorState } from '../types'
import { Sparkline } from './Sparkline'

interface MotorCardProps {
  motor: MotorState
  onSelect: (motor: MotorState) => void
}

export const MotorCard: FC<MotorCardProps> = ({ motor, onSelect }) => {
  const { latest, connectionStatus, history } = motor
  const { sensors, sensor_status, inference, diagnostics } = latest

  const isSimulator = latest.source === 'simulator'

  // Extract sparkline historical arrays
  const tempHistory = history.map((h) => h.temperature)
  const currentHistory = history.map((h) => h.current)
  const vibHistory = history.map((h) => h.vibration)

  const formatGauge = (
    val: number | null | undefined,
    status: string,
    unit: string,
    decimals = 1
  ) => {
    if (status !== 'OK' || val === null || val === undefined) {
      return {
        value: status,
        isUnavailable: true,
        unit: '',
        cssClass: 'unavailable',
      }
    }
    return {
      value: val.toFixed(decimals),
      isUnavailable: false,
      unit,
      cssClass:
        inference.health_status === 'critical'
          ? 'critical'
          : inference.health_status === 'warning'
          ? 'warning'
          : 'healthy',
    }
  }

  const tempDisplay = formatGauge(sensors.temperature_c, sensor_status.temperature, '°C', 1)
  const currentDisplay = formatGauge(sensors.current_a, sensor_status.current, 'A', 2)
  const vibDisplay = formatGauge(sensors.vibration_g_rms, sensor_status.vibration, 'g', 3)

  const formatTimestamp = (iso: string) => {
    try {
      const date = new Date(iso)
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return iso
    }
  }

  const probs = inference.probabilities || {
    healthy: inference.health_status === 'healthy' ? inference.confidence : 0,
    warning: inference.health_status === 'warning' ? inference.confidence : 0,
    critical: inference.health_status === 'critical' ? inference.confidence : 0,
  }

  // Calculate ISO 10816-3 vibration severity marker percentage (0 to 100%)
  const isoMarkerPct = useMemo(() => {
    const v = sensors.vibration_g_rms
    if (v == null || isNaN(v)) return 15
    // Max scale 3.5 g for visualization
    const clamped = Math.max(0, Math.min(3.5, v))
    return Math.round((clamped / 3.5) * 100)
  }, [sensors.vibration_g_rms])

  const isoZoneLabel = useMemo(() => {
    const v = sensors.vibration_g_rms
    if (v == null) return 'N/A'
    if (v < 0.6) return 'ZONE A: GOOD'
    if (v < 1.2) return 'ZONE B: ACCEPTABLE'
    if (v < 2.0) return 'ZONE C: ALERT'
    return 'ZONE D: DAMAGE TRIP'
  }, [sensors.vibration_g_rms])

  return (
    <div
      className={`motor-card scada-panel ${connectionStatus === 'offline' ? 'offline' : inference.health_status}`}
      onClick={() => onSelect(motor)}
      style={{ cursor: 'pointer', padding: '16px 18px', gap: '12px' }}
    >
      <div className="motor-card-header" style={{ alignItems: 'center' }}>
        <div className="motor-identity">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="scada-equip-tag">{latest.motor_id}</span>
            <span style={{ fontSize: '11px', fontFamily: 'var(--scada-mono-font)', color: 'var(--text-muted)' }}>
              RS-775 DC 12V
            </span>
          </div>
          <div className="device-id" style={{ marginTop: '2px', color: 'var(--text-muted)' }}>
            NODE: {latest.device_id}
          </div>
        </div>

        <div className="motor-badges">
          {isSimulator ? (
            <span className="badge simulator" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>
              SIM NODE
            </span>
          ) : (
            <span className="badge" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px', background: 'rgba(59, 130, 246, 0.15)', borderColor: 'rgba(59, 130, 246, 0.4)', color: 'var(--accent-primary)' }}>
              ESP32 HW
            </span>
          )}

          <span className={`badge ${connectionStatus}`} style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>
            ● {connectionStatus.toUpperCase()}
          </span>

          <span className={`badge ${inference.health_status}`} style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>
            {inference.health_status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Industrial Sensor Gauges with Tolerance Limit Banners */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        <div className="scada-gauge-box">
          <div className="scada-gauge-header">
            <span>TEMP</span>
            <span className="scada-gauge-limit" title="IEC Class F Thermal Limit: 70°C">HH: 70°C</span>
          </div>
          <div className={`scada-gauge-val ${tempDisplay.cssClass}`}>
            {tempDisplay.value}
            <span className="scada-gauge-unit">{tempDisplay.unit}</span>
          </div>
        </div>

        <div className="scada-gauge-box">
          <div className="scada-gauge-header">
            <span>CURRENT</span>
            <span className="scada-gauge-limit" title="Overcurrent Trip Limit: 10.0A">HH: 10.0A</span>
          </div>
          <div className={`scada-gauge-val ${currentDisplay.cssClass}`}>
            {currentDisplay.value}
            <span className="scada-gauge-unit">{currentDisplay.unit}</span>
          </div>
        </div>

        <div className="scada-gauge-box">
          <div className="scada-gauge-header">
            <span>VIBRATION</span>
            <span className="scada-gauge-limit" title="ISO 10816 Zone D Trip: 2.0g">HH: 2.0g</span>
          </div>
          <div className={`scada-gauge-val ${vibDisplay.cssClass}`}>
            {vibDisplay.value}
            <span className="scada-gauge-unit">{vibDisplay.unit}</span>
          </div>
        </div>
      </div>

      {/* ISO 10816-3 Vibration Severity Gauge Bar */}
      <div className="iso-severity-scale" style={{ background: 'var(--bg-subtle)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '9.5px', fontFamily: 'var(--scada-mono-font)' }}>
          <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>ISO 10816-3 SEVERITY</span>
          <span style={{ fontWeight: 700, color: inference.health_status === 'critical' ? '#EF4444' : inference.health_status === 'warning' ? '#F59E0B' : '#10B981' }}>
            {isoZoneLabel}
          </span>
        </div>
        <div className="iso-severity-bar" style={{ marginTop: '3px' }}>
          <div className="iso-zone zone-a" title="Zone A: Good (New Commissioned)" />
          <div className="iso-zone zone-b" title="Zone B: Acceptable (Long-term Continuous)" />
          <div className="iso-zone zone-c" title="Zone C: Alert (Corrective Action Required)" />
          <div className="iso-zone zone-d" title="Zone D: Damage Trip (Danger)" />
          <div className="iso-marker" style={{ left: `${isoMarkerPct}%` }} />
        </div>
        <div className="iso-legend-row" style={{ marginTop: '2px' }}>
          <span>A: &lt;0.6g</span>
          <span>B: 0.6-1.2g</span>
          <span>C: 1.2-2.0g</span>
          <span>D: &gt;2.0g</span>
        </div>
      </div>

      {/* Real-time Sparklines */}
      <div className="sparkline-section">
        <div className="sparkline-container">
          <div>
            <Sparkline data={tempHistory} color="#f59e0b" label={`t-${latest.motor_id}`} />
            <div className="sparkline-label" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '9px' }}>Temp (°C)</div>
          </div>
          <div>
            <Sparkline data={currentHistory} color="#3b82f6" label={`c-${latest.motor_id}`} />
            <div className="sparkline-label" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '9px' }}>Current (A)</div>
          </div>
          <div>
            <Sparkline data={vibHistory} color="#a855f7" label={`v-${latest.motor_id}`} />
            <div className="sparkline-label" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '9px' }}>Vibration (g)</div>
          </div>
        </div>
      </div>

      {/* TinyML Edge Inference Breakdown */}
      <div className="inference-section" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <div className="inference-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
          <span className="inference-title" style={{ fontSize: '10.5px' }}>
            TinyML Classifier ({Math.round(inference.confidence * 100)}%)
          </span>
          <span className="inference-model" style={{ fontSize: '10px' }}>
            {inference.model_version || 'v1.0.0'}
            {inference.inference_time_ms ? ` · ${inference.inference_time_ms}ms` : ''}
          </span>
        </div>

        <div className="probability-bars">
          <div className="prob-row">
            <span className="prob-label healthy" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>Healthy</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill healthy"
                style={{ width: `${Math.round(probs.healthy * 100)}%` }}
              />
            </div>
            <span className="prob-value" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>{(probs.healthy * 100).toFixed(0)}%</span>
          </div>

          <div className="prob-row">
            <span className="prob-label warning" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>Warning</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill warning"
                style={{ width: `${Math.round(probs.warning * 100)}%` }}
              />
            </div>
            <span className="prob-value" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>{(probs.warning * 100).toFixed(0)}%</span>
          </div>

          <div className="prob-row">
            <span className="prob-label critical" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>Critical</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill critical"
                style={{ width: `${Math.round(probs.critical * 100)}%` }}
              />
            </div>
            <span className="prob-value" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>{(probs.critical * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div className="motor-card-footer" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>
        <div className="card-timestamp">
          ⏱ SYNC {formatTimestamp(latest.timestamp)}
        </div>
        <div className="card-seq">
          FRAME #{latest.seq}
          {diagnostics?.wifi_rssi_dbm !== undefined && diagnostics?.wifi_rssi_dbm !== null && (
            <span> · RSSI {diagnostics.wifi_rssi_dbm} dBm</span>
          )}
        </div>
      </div>
    </div>
  )
}
