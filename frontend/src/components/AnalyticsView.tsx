import type { FC } from 'react'
import { useState, useMemo } from 'react'
import { Download, Table, AlertTriangle } from 'lucide-react'
import type { MotorState, ChartMetric, TimeRangeOption, AlertItem } from '../types'
import { MetricSummaryCard } from './MetricSummaryCard'
import { EChartPanel } from './EChartPanel'

interface AnalyticsViewProps {
  motors: MotorState[]
  selectedMotorId: string
  onSelectMotor: (id: string) => void
  alerts: AlertItem[]
}

export const AnalyticsView: FC<AnalyticsViewProps> = ({
  motors,
  selectedMotorId,
  onSelectMotor,
  alerts,
}) => {
  // Find current motor
  const currentMotor = useMemo(() => {
    return motors.find((m) => m.motor_id === selectedMotorId) || motors[0]
  }, [motors, selectedMotorId])

  // Focused primary metric
  const [primaryMetric, setPrimaryMetric] = useState<ChartMetric>('vibration')
  const [timeRange, setTimeRange] = useState<TimeRangeOption>('1h')
  const [tableSearch, setTableSearch] = useState('')

  const history = useMemo(() => currentMotor?.history || [], [currentMotor])
  const motor_id = currentMotor?.latest.motor_id || ''

  // Prepare chart series from motor history
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

  // Contextual alerts for this specific motor
  const motorAlerts = useMemo(() => {
    return alerts.filter((a) => a.motor_id === motor_id)
  }, [alerts, motor_id])

  // Historical table items filtered by search
  const filteredTableHistory = useMemo(() => {
    const list = [...history].reverse()
    if (!tableSearch.trim()) return list
    const q = tableSearch.toLowerCase().trim()
    return list.filter(
      (h) =>
        h.timestamp.toLowerCase().includes(q) ||
        h.health_status.toLowerCase().includes(q)
    )
  }, [history, tableSearch])

  if (!currentMotor) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No monitored motor assets available.
      </div>
    )
  }

  const { latest, connectionStatus } = currentMotor
  const { sensors, inference, device_id, source } = latest

  // Full dataset export handler
  const handleExportFullCSV = () => {
    const headers = ['Timestamp_ISO', 'Motor_ID', 'Device_ID', 'Source', 'Temp_C', 'Current_A', 'Vibration_g_RMS', 'Health_Status']
    const rows = history.map((h) => [
      `"${h.timestamp}"`,
      `"${motor_id}"`,
      `"${device_id}"`,
      `"${source}"`,
      h.temperature != null ? h.temperature : '',
      h.current != null ? h.current : '',
      h.vibration != null ? h.vibration : '',
      `"${h.health_status}"`,
    ])

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const dateStr = new Date().toISOString().split('T')[0]
    const link = document.createElement('a')
    link.href = encodedUri
    link.download = `MotorGuard_${motor_id}_Complete_Telemetry_${dateStr}.csv`
    link.click()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header & Asset Meta Bar */}
      <div className="page-header">
        <div className="page-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 className="page-title">{motor_id} — Detailed Analytics</h2>

            {/* Asset Switcher Dropdown */}
            <select
              value={selectedMotorId}
              onChange={(e) => onSelectMotor(e.target.value)}
              style={{
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-main)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  Switch to {m.motor_id} ({m.source.toUpperCase()})
                </option>
              ))}
            </select>

            {/* Source Distinction Badge */}
            <span
              className={`badge-status ${source === 'hardware' ? 'hardware' : 'simulator'}`}
            >
              {source === 'hardware' ? 'LIVE HARDWARE' : 'DEMO SIMULATION'}
            </span>

            {/* Connection Status Badge */}
            <span className={`badge-status ${connectionStatus}`}>
              ● {connectionStatus.toUpperCase()}
            </span>

            {/* AI Health Classification Badge */}
            <span className={`badge-status ${inference.health_status}`}>
              AI: {inference.health_status.toUpperCase()} ({(inference.confidence * 100).toFixed(0)}%)
            </span>

            {/* Active Alerts for this Motor */}
            {motorAlerts.length > 0 && (
              <span className="badge-status critical" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <AlertTriangle size={12} />
                {motorAlerts.length} Active Alarms
              </span>
            )}
          </div>

          <p className="page-description">
            Asset Node: <strong style={{ color: 'var(--text-main)' }}>{device_id}</strong> • Specification: RS-775 12V High-Torque Brushed Motor • Edge Impulse TinyML EON Model v1.0.1
          </p>
        </div>

        <div className="page-actions-group">
          {/* Shared Time Range Picker */}
          <div className="segmented-control" role="group" aria-label="Global Time Range">
            {(['15m', '1h', '6h', '24h', '7d', 'all'] as TimeRangeOption[]).map((tr) => (
              <button
                key={tr}
                className={`segmented-btn ${timeRange === tr ? 'active' : ''}`}
                onClick={() => setTimeRange(tr)}
              >
                {tr.toUpperCase()}
              </button>
            ))}
          </div>

          <button className="btn-secondary" onClick={handleExportFullCSV}>
            <Download size={14} />
            <span>Export Full Telemetry CSV</span>
          </button>
        </div>
      </div>

      {/* 3 Primary Metric Summary Cards */}
      <div className="measurement-grid">
        <MetricSummaryCard
          metric="temperature"
          title="Chassis Temperature"
          sensorLabel="DHT11 Sensor • GPIO 4"
          latestValue={sensors.temperature_c ?? null}
          unit="°C"
          history={history.map((h) => h.temperature)}
          thresholdWarn={50.0}
          thresholdCrit={65.0}
          isSelected={primaryMetric === 'temperature'}
          onClick={() => setPrimaryMetric('temperature')}
        />

        <MetricSummaryCard
          metric="current"
          title="Armature Current"
          sensorLabel="ACS712 20A Hall-Effect • GPIO 34"
          latestValue={sensors.current_a ?? null}
          unit="A"
          history={history.map((h) => h.current)}
          thresholdWarn={3.5}
          thresholdCrit={4.0}
          isSelected={primaryMetric === 'current'}
          onClick={() => setPrimaryMetric('current')}
        />

        <MetricSummaryCard
          metric="vibration"
          title="Dynamic Vibration RMS"
          sensorLabel="ADXL345 3-Axis • I2C Bus 0 (100 Hz)"
          latestValue={sensors.vibration_g_rms ?? null}
          unit="g"
          history={history.map((h) => h.vibration)}
          thresholdWarn={0.20}
          thresholdCrit={0.80}
          isSelected={primaryMetric === 'vibration'}
          onClick={() => setPrimaryMetric('vibration')}
        />
      </div>

      {/* Primary Chart Viewport (Focused Metric) */}
      {primaryMetric === 'temperature' && (
        <EChartPanel
          title="Chassis Thermal Trajectory"
          subtitle="DHT11 Temperature Over Time"
          metric="temperature"
          unit="°C"
          motorId={motor_id}
          deviceId={device_id}
          data={tempSeries}
          thresholdWarn={50.0}
          thresholdCrit={65.0}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          isPrimary
        />
      )}

      {primaryMetric === 'current' && (
        <EChartPanel
          title="Armature Current Load"
          subtitle="ACS712 20A True RMS Load"
          metric="current"
          unit="A"
          motorId={motor_id}
          deviceId={device_id}
          data={currSeries}
          thresholdWarn={3.5}
          thresholdCrit={4.0}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          isPrimary
        />
      )}

      {primaryMetric === 'vibration' && (
        <EChartPanel
          title="Mechanical Dynamic Vibration RMS"
          subtitle="ADXL345 High-Speed 100 Hz Synchronized RMS"
          metric="vibration"
          unit="g"
          motorId={motor_id}
          deviceId={device_id}
          data={vibSeries}
          thresholdWarn={0.20}
          thresholdCrit={0.80}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
          isPrimary
        />
      )}

      {/* Secondary Charts Grid (Remaining Metrics) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '16px' }}>
        {primaryMetric !== 'temperature' && (
          <EChartPanel
            title="Temperature Profile"
            metric="temperature"
            unit="°C"
            motorId={motor_id}
            deviceId={device_id}
            data={tempSeries}
            thresholdWarn={50.0}
            thresholdCrit={65.0}
            timeRange={timeRange}
          />
        )}

        {primaryMetric !== 'current' && (
          <EChartPanel
            title="Current Draw"
            metric="current"
            unit="A"
            motorId={motor_id}
            deviceId={device_id}
            data={currSeries}
            thresholdWarn={3.5}
            thresholdCrit={4.0}
            timeRange={timeRange}
          />
        )}

        {primaryMetric !== 'vibration' && (
          <EChartPanel
            title="Dynamic Vibration"
            metric="vibration"
            unit="g"
            motorId={motor_id}
            deviceId={device_id}
            data={vibSeries}
            thresholdWarn={0.20}
            thresholdCrit={0.80}
            timeRange={timeRange}
          />
        )}
      </div>

      {/* Historical Telemetry Data Table */}
      <div className="data-table-container">
        <div className="table-toolbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Table size={16} color="var(--text-secondary)" />
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
              Historical Sensor Readings Log ({history.length} samples buffer)
            </span>
          </div>

          <div className="search-input-wrapper">
            <input
              type="text"
              className="search-input-field"
              placeholder="Filter by timestamp or health status..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
            />
          </div>
        </div>

        <div style={{ overflowX: 'auto', maxHeight: '340px' }}>
          <table className="industrial-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Temperature (°C)</th>
                <th>Current (A)</th>
                <th>Vibration (g RMS)</th>
                <th>AI Classification</th>
              </tr>
            </thead>
            <tbody>
              {filteredTableHistory.slice(0, 50).map((pt, idx) => (
                <tr key={`${pt.timestamp}-${idx}`}>
                  <td className="tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    {pt.timestamp}
                  </td>
                  <td className="tabular-nums">
                    {pt.temperature != null ? `${pt.temperature.toFixed(1)} °C` : 'DISCONNECTED'}
                  </td>
                  <td className="tabular-nums">
                    {pt.current != null ? `${pt.current.toFixed(2)} A` : 'DISCONNECTED'}
                  </td>
                  <td className="tabular-nums">
                    {pt.vibration != null ? `${pt.vibration.toFixed(3)} g` : 'DISCONNECTED'}
                  </td>
                  <td>
                    <span className={`badge-status ${pt.health_status}`}>
                      {pt.health_status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
              {filteredTableHistory.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                    No telemetry records match the search filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
