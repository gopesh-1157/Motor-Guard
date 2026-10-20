import type { FC } from 'react'
import { useState, useMemo } from 'react'
import {
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Radio,
  WifiOff,
  Search,
  ExternalLink,
  ShieldAlert,
  Clock,
  RotateCw,
  Eye,
  Sliders,
  ChevronLeft,
  ChevronRight,
  Zap,
} from 'lucide-react'
import type { DashboardStats, MotorState, AlertItem, NavigationTab } from '../types'
import { Motor3DViewer } from './Motor3DViewer'

interface OverviewViewProps {
  stats: DashboardStats
  motors: MotorState[]
  alerts: AlertItem[]
  loadingAlerts?: boolean
  alertFetchError?: string | null
  onSelectMotorForAnalytics: (motorId: string) => void
  onInspectMotorDetail?: (motor: MotorState) => void
  onNavigate: (tab: NavigationTab) => void
  lastUpdatedIso?: string
  wsConnected?: boolean
}

export const OverviewView: FC<OverviewViewProps> = ({
  stats,
  motors,
  alerts,
  loadingAlerts = false,
  alertFetchError = null,
  onSelectMotorForAnalytics,
  onInspectMotorDetail,
  onNavigate,
  lastUpdatedIso,
  wsConnected = true,
}) => {
  const [facility, setFacility] = useState('Facility Alpha — Plant Line 1')
  const [timeRange, setTimeRange] = useState<'live' | '15m' | '1h' | '24h'>('live')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [connectionFilter, setConnectionFilter] = useState<'all' | 'online' | 'offline'>('all')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'hardware' | 'simulator'>('all')
  const [sortBy, setSortBy] = useState<'id' | 'temp' | 'current' | 'vib' | 'health'>('id')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 6

  const [selectedMotorFor3D, setSelectedMotorFor3D] = useState<string>(
    motors[0]?.motor_id || 'MTR-775-001'
  )
  const [isSimInjecting, setIsSimInjecting] = useState(false)
  const [simMessage, setSimMessage] = useState<string | null>(null)

  const activeMotor3D = useMemo(() => {
    return motors.find((m) => m.motor_id === selectedMotorFor3D) || motors[0]
  }, [motors, selectedMotorFor3D])

  // Filter and sort motors list
  const filteredMotors = useMemo(() => {
    const list = motors.filter((m) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchId = m.motor_id.toLowerCase().includes(q)
        const matchDev = m.device_id.toLowerCase().includes(q)
        if (!matchId && !matchDev) return false
      }
      // Status filter
      if (statusFilter !== 'all') {
        if (m.latest.inference.health_status !== statusFilter) return false
      }
      // Connection filter
      if (connectionFilter !== 'all') {
        if (m.connectionStatus !== connectionFilter) return false
      }
      // Source filter
      if (sourceFilter !== 'all') {
        if (m.source !== sourceFilter) return false
      }
      return true
    })

    // Sort
    return list.sort((a, b) => {
      let comparison = 0
      if (sortBy === 'id') {
        comparison = a.motor_id.localeCompare(b.motor_id)
      } else if (sortBy === 'temp') {
        const tA = a.latest.sensors.temperature_c ?? -999
        const tB = b.latest.sensors.temperature_c ?? -999
        comparison = tA - tB
      } else if (sortBy === 'current') {
        const cA = a.latest.sensors.current_a ?? -999
        const cB = b.latest.sensors.current_a ?? -999
        comparison = cA - cB
      } else if (sortBy === 'vib') {
        const vA = a.latest.sensors.vibration_g_rms ?? -999
        const vB = b.latest.sensors.vibration_g_rms ?? -999
        comparison = vA - vB
      } else if (sortBy === 'health') {
        const score = (s: string) => (s === 'critical' ? 3 : s === 'warning' ? 2 : 1)
        comparison = score(a.latest.inference.health_status) - score(b.latest.inference.health_status)
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })
  }, [motors, searchQuery, statusFilter, connectionFilter, sourceFilter, sortBy, sortOrder])

  // Pagination
  const totalPages = Math.ceil(filteredMotors.length / pageSize) || 1
  const paginatedMotors = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredMotors.slice(start, start + pageSize)
  }, [filteredMotors, currentPage, pageSize])

  // Active unacknowledged alerts
  const activeAlerts = useMemo(() => {
    return alerts.filter((a) => a.state !== 'RESOLVED').slice(0, 6)
  }, [alerts])

  // Fleet aggregate metrics
  const aggregateAverages = useMemo(() => {
    if (motors.length === 0) return { avgTemp: 0, avgCurrent: 0, avgVib: 0, healthPct: 0 }
    let sumT = 0, countT = 0
    let sumC = 0, countC = 0
    let sumV = 0, countV = 0
    let healthyCount = 0

    motors.forEach((m) => {
      if (m.latest.sensors.temperature_c != null) {
        sumT += m.latest.sensors.temperature_c
        countT++
      }
      if (m.latest.sensors.current_a != null) {
        sumC += m.latest.sensors.current_a
        countC++
      }
      if (m.latest.sensors.vibration_g_rms != null) {
        sumV += m.latest.sensors.vibration_g_rms
        countV++
      }
      if (m.latest.inference.health_status === 'healthy') {
        healthyCount++
      }
    })

    return {
      avgTemp: countT > 0 ? (sumT / countT).toFixed(1) : '—',
      avgCurrent: countC > 0 ? (sumC / countC).toFixed(2) : '—',
      avgVib: countV > 0 ? (sumV / countV).toFixed(3) : '—',
      healthPct: Math.round((healthyCount / motors.length) * 100),
    }
  }, [motors])

  const handleSimInject = async (condition: string, motorId = 'MTR-775-002') => {
    setIsSimInjecting(true)
    setSimMessage(null)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/simulator/inject', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          motor_id: motorId,
          device_id: motorId === 'MTR-775-002' ? 'sim-node-002' : 'sim-node-003',
          condition,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setSimMessage(`Injected '${condition}' on ${motorId} -> Status: ${data.health_status.toUpperCase()}`)
      } else if (res.status === 401 || res.status === 403) {
        setSimMessage('Fault simulation requires Manager or Admin security clearance.')
      } else {
        setSimMessage(`Injection returned status ${res.status}`)
      }
    } catch {
      setSimMessage('Simulator API not reachable')
    } finally {

      setIsSimInjecting(false)
      setTimeout(() => setSimMessage(null), 4000)
    }
  }

  const formatTimestamp = (iso?: string) => {
    if (!iso) return 'Just now'
    try {
      const d = new Date(iso)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return iso
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Page Header */}
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div className="page-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 className="page-title">Plant Overview</h2>
            <div
              className={`connection-pill ${wsConnected ? 'online' : 'offline'}`}
              style={{ fontSize: '11px', padding: '3px 8px' }}
            >
              <span className={`connection-dot ${wsConnected ? 'pulse' : ''}`} />
              <span>{wsConnected ? 'LIVE TELEMETRY' : 'HISTORICAL / OFFLINE'}</span>
            </div>
          </div>
          <p className="page-description">
            Continuous condition monitoring, Edge Impulse anomaly classification, and fleet health telemetry.
          </p>
        </div>

        <div className="page-actions-group" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Facility Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SITE:</span>
            <select
              value={facility}
              onChange={(e) => setFacility(e.target.value)}
              style={{
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-main)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <option value="Facility Alpha — Plant Line 1">Facility Alpha — Line 1 (Packaging)</option>
              <option value="Facility Beta — Plant Line 2">Facility Beta — Line 2 (Extrusion)</option>
              <option value="Lab A — Engineering Testbench">Lab A — Engineering Testbench</option>
            </select>
          </div>

          {/* Time Range Selector */}
          <div className="segmented-control">
            {(['live', '15m', '1h', '24h'] as const).map((r) => (
              <button
                key={r}
                className={`segmented-btn ${timeRange === r ? 'active' : ''}`}
                onClick={() => setTimeRange(r)}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Timestamp and Refresh */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              color: 'var(--text-muted)',
              padding: '4px 8px',
              background: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Clock size={12} />
            <span className="tabular-nums">Updated: {formatTimestamp(lastUpdatedIso)}</span>
            <button
              onClick={() => window.location.reload()}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                display: 'inline-flex',
                padding: '2px',
              }}
              title="Refresh telemetry"
            >
              <RotateCw size={11} />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Top Fleet Summary KPI Row (All 6 Required Metrics) */}
      <div className="kpi-summary-row" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        {/* Metric 1: Total Registered Motors */}
        <div
          className={`kpi-summary-card scada-panel ${statusFilter === 'all' && connectionFilter === 'all' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('all')
            setConnectionFilter('all')
          }}
          title="Filter all registered drive motors"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>TOTAL ASSETS</span>
            <Activity size={13} color="var(--brand-primary)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.totalMotors}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>DRIVES</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>LINE 1 + 2 ASSETS</span>
        </div>

        {/* Metric 2: Healthy Motors */}
        <div
          className={`kpi-summary-card healthy scada-panel ${statusFilter === 'healthy' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('healthy')
            setConnectionFilter('all')
          }}
          title="Filter healthy state motors"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>NOMINAL RUN</span>
            <CheckCircle size={13} color="var(--status-healthy)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.healthyCount}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>OPTIMAL</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>ISO ZONE A/B OK</span>
        </div>

        {/* Metric 3: Warning Motors */}
        <div
          className={`kpi-summary-card warning scada-panel ${statusFilter === 'warning' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('warning')
            setConnectionFilter('all')
          }}
          title="Filter warning state motors"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>ADVISORY</span>
            <AlertTriangle size={13} color="var(--status-warning)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.warningCount}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>FLAGGED</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>THERMAL / LOAD TRIP</span>
        </div>

        {/* Metric 4: Critical Motors */}
        <div
          className={`kpi-summary-card critical scada-panel ${statusFilter === 'critical' ? 'active' : ''}`}
          onClick={() => {
            setStatusFilter('critical')
            setConnectionFilter('all')
          }}
          title="Filter critical fault motors"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>CRITICAL TRIP</span>
            <XCircle size={13} color="var(--status-critical)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.criticalCount}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>ALARMS</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>SAFETY INTERLOCK</span>
        </div>

        {/* Metric 5: Offline Motors */}
        <div
          className={`kpi-summary-card scada-panel ${connectionFilter === 'offline' ? 'active' : ''}`}
          onClick={() => {
            setConnectionFilter('offline')
            setStatusFilter('all')
          }}
          title="Filter offline motors"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>COMM OFFLINE</span>
            <WifiOff size={13} color="var(--status-offline)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.offlineCount}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>NODES</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>HEARTBEAT TIMEOUT</span>
        </div>

        {/* Metric 6: Connected ESP32 Devices */}
        <div
          className={`kpi-summary-card hardware scada-panel ${sourceFilter === 'hardware' ? 'active' : ''}`}
          onClick={() => {
            setSourceFilter(sourceFilter === 'hardware' ? 'all' : 'hardware')
          }}
          title="Filter physical hardware ESP32 nodes"
        >
          <div className="kpi-header" style={{ fontFamily: 'var(--scada-mono-font)' }}>
            <span>ESP32 OT NODES</span>
            <Radio size={13} color="var(--status-hardware)" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.hardwareCount ?? 0}</span>
            <span className="kpi-unit" style={{ fontFamily: 'var(--scada-mono-font)' }}>{stats.esp32ApConnected ? 'HW ONLINE' : 'ACTIVE'}</span>
          </div>
          <span className="kpi-subtext" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>DHT11 + ACS712 + ADXL</span>
        </div>
      </div>

      {/* Simulator Test Controls Bar */}
      <div
        className="measurement-card scada-panel"
        style={{
          padding: '10px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          borderLeft: '4px solid var(--brand-primary)',
          background: 'var(--bg-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sliders size={15} color="var(--brand-primary)" />
          <span style={{ fontSize: '11px', fontFamily: 'var(--scada-mono-font)', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.03em' }}>
            SCADA TESTBENCH OVERRIDE INTERLOCK:
          </span>
          {simMessage && (
            <span style={{ fontSize: '11px', fontFamily: 'var(--scada-mono-font)', color: 'var(--brand-primary)', fontWeight: 600 }}>
              {simMessage}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--scada-mono-font)' }}>
          <button
            className="btn-secondary"
            style={{ fontSize: '10.5px', padding: '4px 8px' }}
            disabled={isSimInjecting}
            onClick={() => handleSimInject('healthy', 'MTR-775-002')}
          >
            NORMALIZE [HEALTHY]
          </button>
          <button
            className="btn-secondary"
            style={{ fontSize: '10.5px', padding: '4px 8px', borderColor: 'var(--status-warning)', color: 'var(--status-warning)' }}
            disabled={isSimInjecting}
            onClick={() => handleSimInject('warning_temp', 'MTR-775-002')}
          >
            INJECT WARN TEMP (55.4°C)
          </button>
          <button
            className="btn-secondary"
            style={{ fontSize: '10.5px', padding: '4px 8px', borderColor: 'var(--status-critical)', color: 'var(--status-critical)' }}
            disabled={isSimInjecting}
            onClick={() => handleSimInject('critical_vib', 'MTR-775-003')}
          >
            INJECT CRIT VIB (0.89g)
          </button>
          <button
            className="btn-secondary"
            style={{ fontSize: '10.5px', padding: '4px 8px', borderColor: 'var(--status-critical)', color: 'var(--status-critical)' }}
            disabled={isSimInjecting}
            onClick={() => handleSimInject('overload_current', 'MTR-775-002')}
          >
            INJECT HIGH LOAD (4.65A)
          </button>
          <button
            className="btn-secondary"
            style={{ fontSize: '10.5px', padding: '4px 8px' }}
            disabled={isSimInjecting}
            onClick={() => handleSimInject('sensor_disconnected', 'MTR-775-002')}
          >
            FAULT DISCONNECT
          </button>
        </div>
      </div>

      {/* Main Grid: Fleet Status Table (Left 65%) + Restrained 3D Twin & Recent Alerts (Right 35%) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 1fr)', gap: '20px' }}>
        {/* Left Column: Fleet Asset Table */}
        <div className="data-table-container scada-panel">
          <div className="table-toolbar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px', fontFamily: 'var(--scada-mono-font)', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.04em' }}>
                PLANT FLOOR DRIVE ROSTER
              </span>
              <span style={{ fontSize: '11px', fontFamily: 'var(--scada-mono-font)', color: 'var(--text-muted)' }}>
                [{filteredMotors.length} ASSETS ONLINE]
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              {/* Search */}
              <div className="search-input-wrapper">
                <Search size={14} className="search-icon-inside" />
                <input
                  type="text"
                  className="search-input-field"
                  placeholder="Search Tag / Node ID..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value)
                    setCurrentPage(1)
                  }}
                  style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '11px' }}
                />
              </div>

              {/* Status filter pill group */}
              <div className="segmented-control" style={{ fontFamily: 'var(--scada-mono-font)' }}>
                {['all', 'healthy', 'warning', 'critical'].map((st) => (
                  <button
                    key={st}
                    className={`segmented-btn ${statusFilter === st ? 'active' : ''}`}
                    onClick={() => {
                      setStatusFilter(st)
                      setCurrentPage(1)
                    }}
                    style={{ fontSize: '10px' }}
                  >
                    {st.toUpperCase()}
                  </button>
                ))}
              </div>

              {/* Sort selector */}
              <select
                value={`${sortBy}-${sortOrder}`}
                onChange={(e) => {
                  const [field, order] = e.target.value.split('-') as [any, 'asc' | 'desc']
                  setSortBy(field)
                  setSortOrder(order)
                }}
                style={{
                  padding: '4px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-main)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: '11px',
                  fontFamily: 'var(--scada-mono-font)',
                  cursor: 'pointer',
                }}
              >
                <option value="id-asc">Sort: Asset Tag (A-Z)</option>
                <option value="temp-desc">Sort: Temp (High-Low)</option>
                <option value="current-desc">Sort: Current (High-Low)</option>
                <option value="vib-desc">Sort: Vib RMS (High-Low)</option>
                <option value="health-desc">Sort: Alarm Severity</option>
              </select>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="industrial-table">
              <thead>
                <tr style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10.5px' }}>
                  <th>ASSET TAG</th>
                  <th>NODE &amp; BUS</th>
                  <th>STATUS [IEC 60034]</th>
                  <th>TEMP [°C]</th>
                  <th>CURRENT [A RMS]</th>
                  <th>VIB [g RMS]</th>
                  <th>POWER [W]</th>
                  <th>SCADA SYNC</th>
                  <th style={{ textAlign: 'center' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {paginatedMotors.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                      No motor assets found matching the selected filters.
                    </td>
                  </tr>
                ) : (
                  paginatedMotors.map((m) => {
                    const s = m.latest.sensors
                    const inf = m.latest.inference
                    const isSelectedFor3D = m.motor_id === selectedMotorFor3D
                    // Calculate power if current is valid (assume 12.0 VDC rated supply)
                    const powerCalc = s.current_a != null ? (s.current_a * 12.0).toFixed(1) : '—'

                    return (
                      <tr
                        key={m.motor_id}
                        onClick={() => setSelectedMotorFor3D(m.motor_id)}
                        style={{
                          cursor: 'pointer',
                          background: isSelectedFor3D ? 'var(--brand-primary-light)' : undefined,
                        }}
                      >
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span className="scada-equip-tag" style={{ width: 'fit-content' }}>
                              {m.motor_id}
                            </span>
                            <span style={{ color: 'var(--text-muted)', fontSize: '10px', fontFamily: 'var(--scada-mono-font)' }}>
                              LINE 1 DRIVE
                            </span>
                          </div>
                        </td>

                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{ color: 'var(--text-main)', fontSize: '12px', fontWeight: 500 }}>
                              {m.device_id}
                            </span>
                            <div style={{ display: 'flex', gap: '4px' }}>
                              <span className={`badge-status ${m.source === 'hardware' ? 'hardware' : 'simulator'}`}>
                                {m.source.toUpperCase()}
                              </span>
                              <span className={`badge-status ${m.connectionStatus}`}>
                                {m.connectionStatus.toUpperCase()}
                              </span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className={`badge-status ${inf.health_status}`}>
                              {inf.health_status.toUpperCase()}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }} className="tabular-nums">
                              {(inf.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>

                        <td className="tabular-nums" style={{ fontWeight: 600 }}>
                          {s.temperature_c != null ? (
                            <span style={{ color: s.temperature_c > 50 ? 'var(--status-critical)' : undefined }}>
                              {s.temperature_c.toFixed(1)}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>N/A</span>
                          )}
                        </td>

                        <td className="tabular-nums" style={{ fontWeight: 600 }}>
                          {s.current_a != null ? (
                            <span style={{ color: s.current_a > 4.0 ? 'var(--status-critical)' : undefined }}>
                              {s.current_a.toFixed(2)}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>N/A</span>
                          )}
                        </td>

                        <td className="tabular-nums" style={{ fontWeight: 600 }}>
                          {s.vibration_g_rms != null ? (
                            <span style={{ color: s.vibration_g_rms > 0.5 ? 'var(--status-critical)' : undefined }}>
                              {s.vibration_g_rms.toFixed(3)}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>N/A</span>
                          )}
                        </td>

                        <td className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                          {powerCalc}
                        </td>

                        <td className="tabular-nums" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {formatTimestamp(m.latest.timestamp)}
                        </td>

                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}>
                            <button
                              className="btn-primary"
                              style={{ padding: '3px 8px', fontSize: '11px' }}
                              onClick={(e) => {
                                e.stopPropagation()
                                onInspectMotorDetail?.(m)
                              }}
                              title="Open full asset inspection modal"
                            >
                              <Eye size={11} />
                              <span>Inspect</span>
                            </button>
                            <button
                              className="btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '11px' }}
                              onClick={(e) => {
                                e.stopPropagation()
                                onSelectMotorForAnalytics(m.motor_id)
                              }}
                              title="Open telemetry analytics"
                            >
                              <ExternalLink size={11} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 16px',
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '12px',
                color: 'var(--text-muted)',
              }}
            >
              <span>
                Page {currentPage} of {totalPages} ({filteredMotors.length} motors total)
              </span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  className="btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '11px' }}
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={13} />
                  <span>Previous</span>
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '11px' }}
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                >
                  <span>Next</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Fleet Aggregates + Three.js Equipment Viewer + Recent Alarms */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Fleet Aggregate Trends Panel */}
          <div className="measurement-card scada-panel" style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Zap size={14} color="var(--brand-primary)" />
                <span style={{ fontSize: '12px', fontFamily: 'var(--scada-mono-font)', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.04em' }}>
                  FLEET AGGREGATE OT HEALTH
                </span>
              </div>
              <span style={{ fontSize: '11px', fontFamily: 'var(--scada-mono-font)', color: 'var(--status-healthy)', fontWeight: 700 }}>
                {aggregateAverages.healthPct}% AVAILABILITY
              </span>
            </div>

            {/* Health Distribution Progress Bar */}
            <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', marginBottom: '12px', background: 'var(--border-subtle)' }}>
              <div
                style={{
                  width: `${(stats.healthyCount / (stats.totalMotors || 1)) * 100}%`,
                  background: 'var(--status-healthy)',
                }}
                title={`Healthy: ${stats.healthyCount}`}
              />
              <div
                style={{
                  width: `${(stats.warningCount / (stats.totalMotors || 1)) * 100}%`,
                  background: 'var(--status-warning)',
                }}
                title={`Warning: ${stats.warningCount}`}
              />
              <div
                style={{
                  width: `${(stats.criticalCount / (stats.totalMotors || 1)) * 100}%`,
                  background: 'var(--status-critical)',
                }}
                title={`Critical: ${stats.criticalCount}`}
              />
              <div
                style={{
                  width: `${(stats.offlineCount / (stats.totalMotors || 1)) * 100}%`,
                  background: 'var(--status-offline)',
                }}
                title={`Offline: ${stats.offlineCount}`}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', textAlign: 'center' }}>
              <div className="scada-gauge-box">
                <div className="scada-gauge-header">Avg Temp</div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--sensor-temp)', fontFamily: 'var(--scada-mono-font)' }} className="tabular-nums">
                  {aggregateAverages.avgTemp} °C
                </div>
              </div>
              <div className="scada-gauge-box">
                <div className="scada-gauge-header">Avg Curr</div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--sensor-current)', fontFamily: 'var(--scada-mono-font)' }} className="tabular-nums">
                  {aggregateAverages.avgCurrent} A
                </div>
              </div>
              <div className="scada-gauge-box">
                <div className="scada-gauge-header">Avg Vib</div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--sensor-vibration)', fontFamily: 'var(--scada-mono-font)' }} className="tabular-nums">
                  {aggregateAverages.avgVib} g
                </div>
              </div>
            </div>
          </div>

          {/* Three.js Motor Model Viewer */}
          {activeMotor3D && (
            <div className="scada-panel">
              <Motor3DViewer
                motorId={activeMotor3D.motor_id}
                healthStatus={activeMotor3D.latest.inference.health_status}
                temperature={activeMotor3D.latest.sensors.temperature_c}
                current={activeMotor3D.latest.sensors.current_a}
                vibration={activeMotor3D.latest.sensors.vibration_g_rms}
              />
            </div>
          )}

          {/* Recent Active Alerts Card */}
          <div className="data-table-container scada-panel">
            <div className="table-toolbar">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldAlert size={15} color="var(--status-critical)" />
                <span style={{ fontSize: '12px', fontFamily: 'var(--scada-mono-font)', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.04em' }}>
                  ACTIVE TRIPS &amp; INTERLOCKS
                </span>
              </div>
              <button
                className="btn-secondary"
                style={{ padding: '2px 8px', fontSize: '10px', fontFamily: 'var(--scada-mono-font)' }}
                onClick={() => onNavigate('alerts')}
              >
                VIEW LOG
              </button>
            </div>

            {loadingAlerts ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                <Clock size={20} style={{ margin: '0 auto 6px', display: 'block' }} />
                Synchronizing alarms with gateway...
              </div>
            ) : alertFetchError ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#ef4444', fontSize: '12px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: '6px', margin: '8px' }}>
                <AlertTriangle size={20} style={{ margin: '0 auto 6px', display: 'block', color: '#ef4444' }} />
                <strong>Alerts Gateway Unavailable:</strong>
                <div style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>{alertFetchError}</div>
              </div>
            ) : activeAlerts.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--status-healthy)', fontSize: '12px' }}>
                <CheckCircle size={20} style={{ margin: '0 auto 6px', display: 'block' }} />
                No active alarm conditions detected in plant line.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {activeAlerts.map((a) => {
                  const targetMotor = motors.find((m) => m.motor_id === a.motor_id)
                  return (
                    <div
                      key={a.alert_id}
                      style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className={`badge-status ${a.severity.toLowerCase()}`}>
                            {a.severity}
                          </span>
                          <strong style={{ fontSize: '12px', color: 'var(--text-main)' }}>
                            {a.motor_id}
                          </strong>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }} className="tabular-nums">
                            {formatTimestamp(a.triggered_at)}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {a.message}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }} className="tabular-nums">
                          Value: <strong>{a.trigger_value} {a.unit}</strong> (Limit: {a.threshold_limit} {a.unit})
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                        <span className={`badge-status ${a.state.toLowerCase()}`} style={{ fontSize: '10px' }}>
                          {a.state}
                        </span>
                        {targetMotor && (
                          <button
                            className="btn-secondary"
                            style={{ padding: '2px 6px', fontSize: '10px' }}
                            onClick={() => onInspectMotorDetail?.(targetMotor)}
                          >
                            Inspect
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
