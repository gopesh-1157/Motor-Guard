import { useState, useMemo } from 'react'
import type { FC } from 'react'
import {
  Printer,
  Filter,
  FileSpreadsheet,
} from 'lucide-react'
import type { MotorState, AlertItem } from '../types'

interface ReportsViewProps {
  motors: MotorState[]
  alerts: AlertItem[]
}

type ReportType =
  | 'fleet_health'
  | 'telemetry_history'
  | 'sensor_trends'
  | 'alert_history'
  | 'device_connectivity'
  | 'maintenance_audit'

export const ReportsView: FC<ReportsViewProps> = ({ motors, alerts }) => {
  const [reportType, setReportType] = useState<ReportType>('fleet_health')
  const [selectedMotorId, setSelectedMotorId] = useState<string>('ALL')
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')
  const [timePeriod, setTimePeriod] = useState<string>('7d')

  // Filtered alerts for reports
  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (selectedMotorId !== 'ALL' && a.motor_id !== selectedMotorId) return false
      if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false
      return true
    })
  }, [alerts, selectedMotorId, severityFilter])

  // Filtered motors for reports
  const filteredMotors = useMemo(() => {
    if (selectedMotorId === 'ALL') return motors
    return motors.filter((m) => m.motor_id === selectedMotorId)
  }, [motors, selectedMotorId])

  // Aggregate calculations
  const totalSamples = useMemo(() => {
    return filteredMotors.reduce((acc, m) => acc + m.history.length, 0)
  }, [filteredMotors])

  const avgTemp = useMemo(() => {
    const validTemps = filteredMotors
      .flatMap((m) => m.history.map((h) => h.temperature))
      .filter((t): t is number => t != null)
    if (validTemps.length === 0) return '—'
    return (validTemps.reduce((a, b) => a + b, 0) / validTemps.length).toFixed(1)
  }, [filteredMotors])

  const maxVib = useMemo(() => {
    const validVibs = filteredMotors
      .flatMap((m) => m.history.map((h) => h.vibration))
      .filter((v): v is number => v != null)
    if (validVibs.length === 0) return '—'
    return Math.max(...validVibs).toFixed(3)
  }, [filteredMotors])

  // CSV Export
  const handleExportCSV = () => {
    let headers: string[] = []
    let rows: (string | number)[][] = []
    const nowIso = new Date().toISOString().split('T')[0]

    if (reportType === 'alert_history') {
      headers = [
        'Alert_ID',
        'Motor_ID',
        'Device_ID',
        'Severity',
        'Trigger_Type',
        'Trigger_Value',
        'Limit',
        'Unit',
        'State',
        'Triggered_At',
        'Assigned_To',
        'Resolved_By',
      ]
      rows = filteredAlerts.map((a) => [
        `"${a.alert_id}"`,
        `"${a.motor_id}"`,
        `"${a.device_id}"`,
        `"${a.severity}"`,
        `"${a.trigger_type}"`,
        a.trigger_value,
        a.threshold_limit,
        `"${a.unit}"`,
        `"${a.state}"`,
        `"${a.triggered_at}"`,
        `"${a.assigned_to || ''}"`,
        `"${a.resolved_by || ''}"`,
      ])
    } else {
      headers = [
        'Timestamp_UTC',
        'Motor_ID',
        'Device_ID',
        'Source',
        'Temp_C',
        'Current_A',
        'Vib_g_RMS',
        'Health_Status',
      ]
      rows = filteredMotors.flatMap((m) =>
        m.history.map((h) => [
          `"${h.timestamp}"`,
          `"${m.motor_id}"`,
          `"${m.device_id}"`,
          `"${m.source}"`,
          h.temperature ?? '',
          h.current ?? '',
          h.vibration ?? '',
          `"${h.health_status}"`,
        ])
      )
    }

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.href = encodedUri
    link.download = `MotorGuard_${reportType}_Report_${nowIso}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // PDF / Printable Report Export
  const handlePrintReport = () => {
    window.print()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Page Header */}
      <div className="page-header">
        <div className="page-title-group">
          <h2 className="page-title">Industrial Operations &amp; Compliance Reports</h2>
          <p className="page-description">
            Audit-grade plant reports, ISO 10816 vibration compliance logs, shift transitions, and alarm histories.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn-secondary" onClick={handlePrintReport}>
            <Printer size={14} />
            <span>Print / Save PDF</span>
          </button>

          <button className="btn-primary" onClick={handleExportCSV}>
            <FileSpreadsheet size={14} />
            <span>Export CSV Dataset</span>
          </button>
        </div>
      </div>

      {/* Report Template Selector & Filter Controls */}
      <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} color="var(--brand-primary)" />
          <span style={{ fontSize: '13px', fontWeight: 700 }}>Report Configuration &amp; Filter Workspace</span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px',
          }}
        >
          {/* Report Type */}
          <div>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              Report Template
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as ReportType)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)', fontSize: '12px', fontWeight: 600 }}
            >
              <option value="fleet_health">Fleet Asset Health Summary</option>
              <option value="telemetry_history">Continuous Telemetry Audit</option>
              <option value="sensor_trends">Sensor Trend &amp; Stability</option>
              <option value="alert_history">Alarm &amp; Incident Log</option>
              <option value="device_connectivity">ESP32 Device Node SLA</option>
              <option value="maintenance_audit">Maintenance &amp; Work Orders</option>
            </select>
          </div>

          {/* Motor Selector */}
          <div>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              Motor Asset
            </label>
            <select
              value={selectedMotorId}
              onChange={(e) => setSelectedMotorId(e.target.value)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)', fontSize: '12px', fontWeight: 600 }}
            >
              <option value="ALL">All Motors (Entire Fleet)</option>
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  {m.motor_id}
                </option>
              ))}
            </select>
          </div>

          {/* Severity Filter */}
          <div>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              Severity Level
            </label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)', fontSize: '12px', fontWeight: 600 }}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Alarms Only</option>
              <option value="WARNING">Warnings &amp; Criticals</option>
              <option value="INFO">Informational</option>
            </select>
          </div>

          {/* Time Period */}
          <div>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              Reporting Time Window
            </label>
            <select
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)', fontSize: '12px', fontWeight: 600 }}
            >
              <option value="shift">Current Operational Shift (8h)</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days (Weekly Audit)</option>
              <option value="30d">Last 30 Days (Monthly Compliance)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Aggregate Report KPI Summary */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '14px',
        }}
      >
        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>
            AUDITED MOTOR ASSETS
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }} className="tabular-nums">
            {filteredMotors.length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{totalSamples} telemetry intervals</span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--sensor-temp)', fontWeight: 600 }}>
            MEAN FLEET TEMP
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--sensor-temp)' }} className="tabular-nums">
            {avgTemp} °C
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Nominal baseline: 35.0 °C</span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--sensor-vib)', fontWeight: 600 }}>
            PEAK DYNAMIC VIBRATION
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--sensor-vib)' }} className="tabular-nums">
            {maxVib} g
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ISO 10816 limit: 0.200 g</span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--status-critical)', fontWeight: 600 }}>
            FILTERED ALARM EVENTS
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--status-critical)' }} className="tabular-nums">
            {filteredAlerts.length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Incidents recorded</span>
        </div>
      </div>

      {/* Report Document Preview (Styled for Printable & On-Screen Review) */}
      <div
        className="card"
        style={{
          padding: '28px',
          background: '#FFFFFF',
          border: '1px solid var(--border-main)',
        }}
      >
        <div style={{ borderBottom: '2px solid var(--border-main)', paddingBottom: '16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="brand-icon-box" style={{ width: '26px', height: '26px', fontSize: '11px' }}>
                  MG
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 800, margin: 0 }}>
                  MotorGuard Plant Operations Report
                </h3>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                Report Type: <strong>{reportType.replace('_', ' ').toUpperCase()}</strong> • Facility: <strong>Plant Alpha Line 1</strong>
              </p>
            </div>

            <div style={{ textAlign: 'right', fontSize: '11px', color: 'var(--text-muted)' }}>
              <div>Generated: <strong className="tabular-nums">{new Date().toLocaleString()}</strong></div>
              <div>Classification: <strong>ENGINEERING SENSITIVE</strong></div>
            </div>
          </div>
        </div>

        {/* Section 1: Executive Fleet Status */}
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', margin: '0 0 10px 0' }}>
            1. Fleet Asset Health Summary
          </h4>
          <table className="compact-table" style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-main)' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Motor Asset ID</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Assigned Node</th>
                <th style={{ padding: '8px 12px', textAlign: 'left' }}>Telemetry Source</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Temp (°C)</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Current (A)</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Vibration (g)</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>TinyML Health</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>SLA Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredMotors.map((m) => (
                <tr key={m.motor_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 600 }}>{m.motor_id}</td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{m.device_id}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <span className={`badge ${m.source === 'hardware' ? 'healthy' : 'simulator'}`}>
                      {m.source.toUpperCase()}
                    </span>
                  </td>
                  <td className="tabular-nums" style={{ padding: '8px 12px', textAlign: 'right' }}>
                    {m.latest.sensors.temperature_c != null ? `${m.latest.sensors.temperature_c.toFixed(1)}` : '—'}
                  </td>
                  <td className="tabular-nums" style={{ padding: '8px 12px', textAlign: 'right' }}>
                    {m.latest.sensors.current_a != null ? `${m.latest.sensors.current_a.toFixed(2)}` : '—'}
                  </td>
                  <td className="tabular-nums" style={{ padding: '8px 12px', textAlign: 'right' }}>
                    {m.latest.sensors.vibration_g_rms != null ? `${m.latest.sensors.vibration_g_rms.toFixed(3)}` : '—'}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    <span className={`badge-status ${m.latest.inference.health_status}`}>
                      {m.latest.inference.health_status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    <span className={`badge-status ${m.connectionStatus === 'online' ? 'healthy' : 'warning'}`}>
                      {m.connectionStatus.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Section 2: Incidents & Alerts Log */}
        <div>
          <h4 style={{ fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', margin: '0 0 10px 0' }}>
            2. Safety Incidents &amp; Alarm Dispatches
          </h4>
          {filteredAlerts.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)', fontSize: '12px' }}>
              ✓ No active or unacknowledged alarm violations recorded for the selected filter criteria.
            </div>
          ) : (
            <table className="compact-table" style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-main)' }}>
                  <th style={{ padding: '8px 12px', textAlign: 'left' }}>Alert ID</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left' }}>Motor</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left' }}>Severity</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left' }}>Trigger Rule</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right' }}>Trigger Value</th>
                  <th style={{ padding: '8px 12px', textAlign: 'center' }}>Lifecycle State</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left' }}>Assigned Tech</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.slice(0, 15).map((a) => (
                  <tr key={a.alert_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)' }}>{a.alert_id}</td>
                    <td style={{ padding: '8px 12px', fontWeight: 600 }}>{a.motor_id}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <span className={`badge-status ${a.severity.toLowerCase()}`}>
                        {a.severity}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{a.trigger_type}</td>
                    <td className="tabular-nums" style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                      {a.trigger_value} {a.unit}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                      <span className={`badge-status ${a.state === 'RESOLVED' ? 'healthy' : a.state === 'ACKNOWLEDGED' ? 'warning' : 'critical'}`}>
                        {a.state}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      {a.assigned_to || 'Unassigned'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
