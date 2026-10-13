import type { FC } from 'react'
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

  return (
    <div
      className={`motor-card ${connectionStatus === 'offline' ? 'offline' : inference.health_status}`}
      onClick={() => onSelect(motor)}
      style={{ cursor: 'pointer' }}
    >
      <div className="motor-card-header">
        <div className="motor-identity">
          <div className="motor-id">{latest.motor_id}</div>
          <div className="device-id">{latest.device_id}</div>
        </div>

        <div className="motor-badges">
          {isSimulator ? (
            <span className="badge simulator">SIMULATOR</span>
          ) : (
            <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.15)', borderColor: 'rgba(59, 130, 246, 0.4)', color: 'var(--accent-primary)' }}>
              HARDWARE
            </span>
          )}

          <span className={`badge ${connectionStatus}`}>
            ● {connectionStatus.toUpperCase()}
          </span>

          <span className={`badge ${inference.health_status}`}>
            {inference.health_status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Sensor Gauges */}
      <div className="sensor-gauges">
        <div className="gauge">
          <div className="gauge-label">Temp</div>
          <div className={`gauge-value ${tempDisplay.cssClass}`}>{tempDisplay.value}</div>
          <div className="gauge-unit">{tempDisplay.unit}</div>
        </div>

        <div className="gauge">
          <div className="gauge-label">Current</div>
          <div className={`gauge-value ${currentDisplay.cssClass}`}>{currentDisplay.value}</div>
          <div className="gauge-unit">{currentDisplay.unit}</div>
        </div>

        <div className="gauge">
          <div className="gauge-label">Vibration</div>
          <div className={`gauge-value ${vibDisplay.cssClass}`}>{vibDisplay.value}</div>
          <div className="gauge-unit">{vibDisplay.unit}</div>
        </div>
      </div>

      {/* Real-time Sparklines */}
      <div className="sparkline-section">
        <div className="sparkline-container">
          <div>
            <Sparkline data={tempHistory} color="#f59e0b" label={`t-${latest.motor_id}`} />
            <div className="sparkline-label">Temp (°C)</div>
          </div>
          <div>
            <Sparkline data={currentHistory} color="#3b82f6" label={`c-${latest.motor_id}`} />
            <div className="sparkline-label">Current (A)</div>
          </div>
          <div>
            <Sparkline data={vibHistory} color="#a855f7" label={`v-${latest.motor_id}`} />
            <div className="sparkline-label">Vibration (g)</div>
          </div>
        </div>
      </div>

      {/* TinyML Edge Inference Breakdown */}
      <div className="inference-section">
        <div className="inference-header">
          <span className="inference-title">
            TinyML Inference ({Math.round(inference.confidence * 100)}%)
          </span>
          <span className="inference-model">
            {inference.model_version || 'v1.0.0'}
            {inference.inference_time_ms ? ` · ${inference.inference_time_ms}ms` : ''}
          </span>
        </div>

        <div className="probability-bars">
          <div className="prob-row">
            <span className="prob-label healthy">Healthy</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill healthy"
                style={{ width: `${Math.round(probs.healthy * 100)}%` }}
              />
            </div>
            <span className="prob-value">{(probs.healthy * 100).toFixed(0)}%</span>
          </div>

          <div className="prob-row">
            <span className="prob-label warning">Warning</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill warning"
                style={{ width: `${Math.round(probs.warning * 100)}%` }}
              />
            </div>
            <span className="prob-value">{(probs.warning * 100).toFixed(0)}%</span>
          </div>

          <div className="prob-row">
            <span className="prob-label critical">Critical</span>
            <div className="prob-bar-bg">
              <div
                className="prob-bar-fill critical"
                style={{ width: `${Math.round(probs.critical * 100)}%` }}
              />
            </div>
            <span className="prob-value">{(probs.critical * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div className="motor-card-footer">
        <div className="card-timestamp">
          ⏱ {formatTimestamp(latest.timestamp)}
        </div>
        <div className="card-seq">
          Seq #{latest.seq}
          {diagnostics?.wifi_rssi_dbm !== undefined && diagnostics?.wifi_rssi_dbm !== null && (
            <span> · {diagnostics.wifi_rssi_dbm} dBm</span>
          )}
        </div>
      </div>
    </div>
  )
}
