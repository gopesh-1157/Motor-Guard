/**
 * MotorGuard — AlertsView: Real-Time Alert Command Center
 *
 * Premium industrial-grade alert dashboard providing:
 * - Live real-time alert feed via WebSocket
 * - Severity/state filtering with animated pill tabs
 * - Alert statistics summary cards with live counters
 * - Alert timeline with severity-coded indicators
 * - Acknowledge, Assign, and Resolve workflow modals
 * - RBAC-enforced action controls
 * - Toast notification system for alert events
 */

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import type { FC } from 'react'
import type { AlertItem, UserProfile, MotorState, TechnicianUser } from '../types'

interface AlertsViewProps {
  alerts: AlertItem[]
  motors: MotorState[]
  loadingAlerts?: boolean
  alertFetchError?: string | null
  onRetryFetchAlerts?: () => void
  onAssignAlert: (
    alertId: string,
    technician: string,
    priority: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL',
    instructions: string
  ) => void
  onResolveAlert: (
    alertId: string,
    motorId: string,
    resolutionNotes: string,
    serviceType: string,
    partsReplaced: string[],
    downtimeMinutes: number
  ) => void
  onAcknowledgeAlert?: (alertId: string) => void
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
  onNavigateToMotor?: (motorId: string) => void
}

type FilterTab = 'ALL' | 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED'
type SeverityFilter = 'ALL' | 'CRITICAL' | 'WARNING' | 'INFO'

interface ToastNotification {
  id: string
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
  timestamp: number
}

const SEVERITY_ICONS: Record<string, string> = {
  CRITICAL: '🔴',
  WARNING: '🟡',
  INFO: '🔵',
}

const TRIGGER_TYPE_LABELS: Record<string, string> = {
  THRESHOLD_OVERCURRENT: 'Overcurrent Trip',
  THRESHOLD_OVERTEMPERATURE: 'Thermal Exceedance',
  THRESHOLD_HIGH_VIBRATION: 'Vibration Anomaly (Legacy)',
  THRESHOLD_HIGH_VIBRATION_RMS: 'Vibration RMS Anomaly',
  THRESHOLD_HIGH_VIBRATION_PEAK: 'Peak-Shock Anomaly',
  SENSOR_DISCONNECTED: 'Sensor Fault (Legacy - Review Required)',
  SENSOR_TEMPERATURE_DISCONNECTED: 'Temperature Sensor Fault',
  SENSOR_CURRENT_DISCONNECTED: 'Current Sensor Fault',
  SENSOR_VIBRATION_DISCONNECTED: 'Vibration Sensor Fault',
  CRITICAL_INFERENCE_FAULT: 'TinyML Critical Diagnosis',
  DEVICE_OFFLINE: 'Device Connection Lost',
}

const TRIGGER_TYPE_ICONS: Record<string, string> = {
  THRESHOLD_OVERCURRENT: '⚡',
  THRESHOLD_OVERTEMPERATURE: '🌡️',
  THRESHOLD_HIGH_VIBRATION: '📳',
  THRESHOLD_HIGH_VIBRATION_RMS: '📳',
  THRESHOLD_HIGH_VIBRATION_PEAK: '⚡',
  SENSOR_DISCONNECTED: '🔌',
  SENSOR_TEMPERATURE_DISCONNECTED: '🌡️',
  SENSOR_CURRENT_DISCONNECTED: '🔌',
  SENSOR_VIBRATION_DISCONNECTED: '📳',
  CRITICAL_INFERENCE_FAULT: '🧠',
  DEVICE_OFFLINE: '📡',
}

const CATEGORY_CONFIG: Record<string, { label: string; icon: string; className: string }> = {
  SAFETY_THRESHOLD: { label: 'Safety Rule', icon: '🛡️', className: 'alerts-category--safety' },
  ML_INFERENCE: { label: 'TinyML Inference', icon: '🧠', className: 'alerts-category--ml' },
  SENSOR_DIAGNOSTIC: { label: 'Sensor Diagnostic', icon: '🔌', className: 'alerts-category--sensor' },
  CONNECTIVITY: { label: 'Connectivity', icon: '📡', className: 'alerts-category--conn' },
}

const TRIGGER_TYPE_TO_CATEGORY: Record<string, string> = {
  THRESHOLD_OVERCURRENT: 'SAFETY_THRESHOLD',
  HARD_OVERCURRENT_TRIP: 'SAFETY_THRESHOLD',
  THRESHOLD_OVERTEMPERATURE: 'SAFETY_THRESHOLD',
  THRESHOLD_HIGH_VIBRATION: 'SAFETY_THRESHOLD',
  THRESHOLD_HIGH_VIBRATION_RMS: 'SAFETY_THRESHOLD',
  THRESHOLD_HIGH_VIBRATION_PEAK: 'SAFETY_THRESHOLD',
  CRITICAL_INFERENCE_FAULT: 'ML_INFERENCE',
  WARNING_INFERENCE_ANOMALY: 'ML_INFERENCE',
  SENSOR_DISCONNECTED: 'SENSOR_DIAGNOSTIC',
  SENSOR_TEMPERATURE_DISCONNECTED: 'SENSOR_DIAGNOSTIC',
  SENSOR_CURRENT_DISCONNECTED: 'SENSOR_DIAGNOSTIC',
  SENSOR_VIBRATION_DISCONNECTED: 'SENSOR_DIAGNOSTIC',
  SENSOR_UNCALIBRATED: 'SENSOR_DIAGNOSTIC',
  INFERENCE_DIAGNOSTIC_FAILURE: 'SENSOR_DIAGNOSTIC',
  DEVICE_OFFLINE: 'CONNECTIVITY',
}

export const AlertsView: FC<AlertsViewProps> = ({
  alerts,
  motors,
  loadingAlerts = false,
  alertFetchError = null,
  onRetryFetchAlerts,
  onAssignAlert,
  onResolveAlert,
  onAcknowledgeAlert,
  currentUser,
  onOpenLogin,
  onNavigateToMotor,
}) => {
  const isManagerOrAdmin = Boolean(
    currentUser && (currentUser.role === 'Manager' || currentUser.role === 'Admin' || currentUser.clearance_level >= 3)
  )
  const isTechOrAbove = Boolean(
    currentUser && (currentUser.role === 'Technician' || currentUser.role === 'Manager' || currentUser.role === 'Admin' || currentUser.clearance_level >= 2)
  )

  // State
  const [filterTab, setFilterTab] = useState<FilterTab>('ALL')
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastNotification[]>([])
  const [liveAlertCount, setLiveAlertCount] = useState(0)
  const [showTimeline, setShowTimeline] = useState(false)

  // Dynamic Technicians (authenticated endpoint /api/v1/auth/technicians)
  const [technicians, setTechnicians] = useState<TechnicianUser[]>([])
  const [loadingTechnicians, setLoadingTechnicians] = useState<boolean>(false)
  const [technicianFetchError, setTechnicianFetchError] = useState<string | null>(null)

  // Assign Modal
  const [assignModalAlert, setAssignModalAlert] = useState<AlertItem | null>(null)
  const [selectedTechnician, setSelectedTechnician] = useState<string>('')
  const [assignPriority, setAssignPriority] = useState<'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL'>('CRITICAL')
  const [assignInstructions, setAssignInstructions] = useState('')

  const fetchTechnicians = useCallback(async () => {
    if (!currentUser || (currentUser.role !== 'Admin' && currentUser.role !== 'Manager')) {
      return
    }
    setLoadingTechnicians(true)
    setTechnicianFetchError(null)
    try {
      const token = localStorage.getItem('motorguard_auth_token') || currentUser.token
      const res = await fetch('/api/v1/auth/technicians', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.status === 401) {
        setTechnicianFetchError('Session expired. Please log in again.')
        return
      }
      if (!res.ok) {
        throw new Error(`Failed to load technicians (${res.status})`)
      }
      const data: TechnicianUser[] = await res.json()
      setTechnicians(data)
      if (data.length > 0) {
        setSelectedTechnician((prev) => prev || data[0].username)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error fetching technicians'
      setTechnicianFetchError(msg)
    } finally {
      setLoadingTechnicians(false)
    }
  }, [currentUser])

  useEffect(() => {
    if (currentUser?.role === 'Admin' || currentUser?.role === 'Manager') {
      fetchTechnicians()
    }
  }, [currentUser, fetchTechnicians])

  const getInitials = (username: string) => (username || 'TC').slice(0, 2).toUpperCase()
  const getAvatarColor = (idx: number) => {
    const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4']
    return colors[idx % colors.length]
  }

  // Resolve Modal
  const [resolveModalAlert, setResolveModalAlert] = useState<AlertItem | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')
  const [resolveServiceType, setResolveServiceType] = useState('CORRECTIVE')
  const [resolveParts, setResolveParts] = useState('')
  const [resolveDowntime, setResolveDowntime] = useState(0)

  const alertListRef = useRef<HTMLDivElement>(null)
  const prevAlertCountRef = useRef(alerts.length)

  const [currentTime, setCurrentTime] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  // Toast helpers
  const addToast = useCallback((message: string, type: ToastNotification['type'] = 'info') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`
    setToasts((prev) => [...prev, { id, message, type, timestamp: Date.now() }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  // Live alert count tracking for "new alerts" badge
  useEffect(() => {
    if (alerts.length > prevAlertCountRef.current) {
      const newCount = alerts.length - prevAlertCountRef.current
      setLiveAlertCount((c) => c + newCount)
      addToast(`${newCount} new alert${newCount > 1 ? 's' : ''} triggered`, 'warning')
    }
    prevAlertCountRef.current = alerts.length
  }, [alerts.length, addToast])

  // Statistics
  const stats = useMemo(() => {
    const active = alerts.filter((a) => a.state === 'ACTIVE')
    const acked = alerts.filter((a) => a.state === 'ACKNOWLEDGED')
    const resolved = alerts.filter((a) => a.state === 'RESOLVED')
    const critActive = active.filter((a) => a.severity === 'CRITICAL')
    const unassigned = active.filter((a) => !a.assigned_to)
    const avgResponseMs = acked
      .filter((a) => a.acknowledged_at && a.triggered_at)
      .map((a) => new Date(a.acknowledged_at!).getTime() - new Date(a.triggered_at).getTime())
      .reduce((sum, val, _, arr) => sum + val / arr.length, 0)

    return {
      total: alerts.length,
      active: active.length,
      acknowledged: acked.length,
      resolved: resolved.length,
      criticalActive: critActive.length,
      unassigned: unassigned.length,
      avgResponseMs,
    }
  }, [alerts])

  // Filtered alerts
  const filteredAlerts = useMemo(() => {
    let result = [...alerts]

    // State filter
    if (filterTab !== 'ALL') {
      result = result.filter((a) => a.state === filterTab)
    }

    // Severity filter
    if (severityFilter !== 'ALL') {
      result = result.filter((a) => a.severity === severityFilter)
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (a) =>
          a.alert_id.toLowerCase().includes(q) ||
          a.motor_id.toLowerCase().includes(q) ||
          a.device_id.toLowerCase().includes(q) ||
          a.message.toLowerCase().includes(q) ||
          a.trigger_type.toLowerCase().includes(q)
      )
    }

    // Sort: ACTIVE first, then by triggered_at descending
    result.sort((a, b) => {
      const stateOrder: Record<string, number> = { ACTIVE: 0, ACKNOWLEDGED: 1, RESOLVED: 2 }
      const stateDiff = (stateOrder[a.state] ?? 3) - (stateOrder[b.state] ?? 3)
      if (stateDiff !== 0) return stateDiff
      return new Date(b.triggered_at).getTime() - new Date(a.triggered_at).getTime()
    })

    return result
  }, [alerts, filterTab, severityFilter, searchQuery])

  // Handlers
  const handleOpenAssignModal = (alert: AlertItem) => {
    setAssignModalAlert(alert)
    setSelectedTechnician((prev) => prev || technicians[0]?.username || '')
    setAssignPriority(alert.severity === 'CRITICAL' ? 'CRITICAL' : 'HIGH')
    setAssignInstructions(
      `${alert.severity === 'CRITICAL' ? 'URGENT: ' : ''}${alert.message}. Inspect ${alert.motor_id} on site and complete repair logging.`
    )
  }

  const handleConfirmAssign = () => {
    if (!assignModalAlert || !selectedTechnician) return
    onAssignAlert(assignModalAlert.alert_id, selectedTechnician, assignPriority, assignInstructions)
    addToast(`Dispatched ${assignModalAlert.alert_id} → ${selectedTechnician}`, 'success')
    setAssignModalAlert(null)
  }

  const handleOpenResolveModal = (alert: AlertItem) => {
    setResolveModalAlert(alert)
    setResolveNotes('')
    setResolveParts('')
    setResolveDowntime(0)
    setResolveServiceType('CORRECTIVE')
  }

  const handleConfirmResolve = () => {
    if (!resolveModalAlert || resolveNotes.trim().length < 3) return
    const parts = resolveParts
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
    onResolveAlert(
      resolveModalAlert.alert_id,
      resolveModalAlert.motor_id,
      resolveNotes,
      resolveServiceType,
      parts,
      resolveDowntime
    )
    addToast(`Resolved ${resolveModalAlert.alert_id}`, 'success')
    setResolveModalAlert(null)
  }

  const handleAcknowledge = async (alert: AlertItem) => {
    if (onAcknowledgeAlert) {
      onAcknowledgeAlert(alert.alert_id)
    } else {
      try {
        const token = localStorage.getItem('motorguard_auth_token')
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        if (token) headers['Authorization'] = `Bearer ${token}`
        await fetch(`/api/v1/alerts/${alert.alert_id}/acknowledge`, {
          method: 'POST',
          headers,
          body: JSON.stringify({}),
        })
        addToast(`Acknowledged ${alert.alert_id}`, 'info')
      } catch {
        addToast('Failed to acknowledge alert', 'error')
      }
    }
  }

  const formatTimeAgo = (iso: string) => {
    const diff = currentTime - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ${mins % 60}m ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  }

  const formatDuration = (ms: number) => {
    if (ms <= 0) return '—'
    const mins = Math.floor(ms / 60000)
    if (mins < 60) return `${mins}m`
    const hrs = Math.floor(mins / 60)
    return `${hrs}h ${mins % 60}m`
  }

  return (
    <div className="alerts-command-center">
      {/* Toast Stack */}
      <div className="alerts-toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`alerts-toast alerts-toast--${t.type}`}>
            <span className="alerts-toast__icon">
              {t.type === 'success' ? '✓' : t.type === 'warning' ? '⚠' : t.type === 'error' ? '✕' : 'ℹ'}
            </span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      {/* ── HEADER ── */}
      <header className="alerts-header">
        <div className="alerts-header__left">
          <div className="alerts-header__pretitle">
            <span className="alerts-header__pulse" />
            REAL-TIME ALERT COMMAND CENTER
          </div>
          <h1 className="alerts-header__title">Alert Monitor & Dispatch</h1>
          <p className="alerts-header__desc">
            Live threshold violations, TinyML fault detections, and device health alerts across the entire motor fleet.
          </p>
        </div>
        <div className="alerts-header__actions">
          <button
            className={`alerts-btn alerts-btn--outline ${showTimeline ? 'active' : ''}`}
            onClick={() => setShowTimeline(!showTimeline)}
          >
            📊 {showTimeline ? 'Hide' : 'Show'} Timeline
          </button>
          {liveAlertCount > 0 && (
            <button
              className="alerts-btn alerts-btn--glow"
              onClick={() => { setLiveAlertCount(0); setFilterTab('ACTIVE') }}
            >
              🔔 {liveAlertCount} New
            </button>
          )}
        </div>
      </header>

      {/* ── STATISTICS CARDS ── */}
      <div className="alerts-stats-grid">
        <div className={`alerts-stat-card ${stats.criticalActive > 0 ? 'alerts-stat-card--critical' : ''}`}>
          <div className="alerts-stat-card__icon">🚨</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{stats.criticalActive}</span>
            <span className="alerts-stat-card__label">Critical Active</span>
          </div>
          {stats.criticalActive > 0 && <div className="alerts-stat-card__pulse-ring" />}
        </div>
        <div className="alerts-stat-card alerts-stat-card--active">
          <div className="alerts-stat-card__icon">🔥</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{stats.active}</span>
            <span className="alerts-stat-card__label">Active Alerts</span>
          </div>
        </div>
        <div className="alerts-stat-card alerts-stat-card--pending">
          <div className="alerts-stat-card__icon">⏳</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{stats.unassigned}</span>
            <span className="alerts-stat-card__label">Unassigned</span>
          </div>
        </div>
        <div className="alerts-stat-card alerts-stat-card--ack">
          <div className="alerts-stat-card__icon">👁️</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{stats.acknowledged}</span>
            <span className="alerts-stat-card__label">Acknowledged</span>
          </div>
        </div>
        <div className="alerts-stat-card alerts-stat-card--resolved">
          <div className="alerts-stat-card__icon">✅</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{stats.resolved}</span>
            <span className="alerts-stat-card__label">Resolved</span>
          </div>
        </div>
        <div className="alerts-stat-card alerts-stat-card--response">
          <div className="alerts-stat-card__icon">⏱️</div>
          <div className="alerts-stat-card__content">
            <span className="alerts-stat-card__value">{formatDuration(stats.avgResponseMs)}</span>
            <span className="alerts-stat-card__label">Avg Response</span>
          </div>
        </div>
      </div>

      {/* ── RBAC Warning ── */}
      {!isTechOrAbove && (
        <div className="alerts-rbac-banner">
          <span>
            🔒 <strong>Clearance Notice:</strong> Alert actions require{' '}
            <strong>Level 2 (Technician)</strong> or higher.
            Logged in as <code>{currentUser?.username}</code> (L{currentUser?.clearance_level}).
          </span>
          {onOpenLogin && (
            <button className="alerts-btn alerts-btn--sm" onClick={onOpenLogin}>
              ⚡ Elevate Access
            </button>
          )}
        </div>
      )}

      {/* ── FILTER BAR ── */}
      <div className="alerts-filter-bar">
        <div className="alerts-filter-bar__left">
          {/* State Tabs */}
          <div className="alerts-pill-group">
            {(['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'] as FilterTab[]).map((tab) => {
              const count =
                tab === 'ALL' ? alerts.length : alerts.filter((a) => a.state === tab).length
              return (
                <button
                  key={tab}
                  className={`alerts-pill ${filterTab === tab ? 'alerts-pill--active' : ''} ${
                    tab === 'ACTIVE' && stats.active > 0 ? 'alerts-pill--has-active' : ''
                  }`}
                  onClick={() => setFilterTab(tab)}
                >
                  {tab}
                  <span className="alerts-pill__count">{count}</span>
                </button>
              )
            })}
          </div>

          {/* Severity Chips */}
          <div className="alerts-severity-chips">
            {(['ALL', 'CRITICAL', 'WARNING', 'INFO'] as SeverityFilter[]).map((sev) => (
              <button
                key={sev}
                className={`alerts-severity-chip alerts-severity-chip--${sev.toLowerCase()} ${
                  severityFilter === sev ? 'alerts-severity-chip--selected' : ''
                }`}
                onClick={() => setSeverityFilter(sev)}
              >
                {sev !== 'ALL' && <span>{SEVERITY_ICONS[sev]}</span>}
                {sev}
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="alerts-search-box">
          <span className="alerts-search-box__icon">🔍</span>
          <input
            className="alerts-search-box__input"
            type="text"
            placeholder="Search alerts by ID, motor, device, trigger..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="alerts-search-box__clear" onClick={() => setSearchQuery('')}>
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ── TIMELINE VIEW ── */}
      {showTimeline && (
        <div className="alerts-timeline">
          <div className="alerts-timeline__header">
            <h3>Alert Timeline</h3>
            <span className="alerts-timeline__count">{filteredAlerts.length} events</span>
          </div>
          <div className="alerts-timeline__track">
            {filteredAlerts.slice(0, 20).map((alert) => (
              <div
                key={alert.alert_id}
                className={`alerts-timeline__node alerts-timeline__node--${alert.severity.toLowerCase()}`}
                onClick={() => setExpandedAlertId(expandedAlertId === alert.alert_id ? null : alert.alert_id)}
              >
                <div className="alerts-timeline__dot" />
                <div className="alerts-timeline__connector" />
                <div className="alerts-timeline__content">
                  <div className="alerts-timeline__time">{formatTimeAgo(alert.triggered_at)}</div>
                  <div className="alerts-timeline__label">
                    {TRIGGER_TYPE_ICONS[alert.trigger_type] || '⚠️'}{' '}
                    {TRIGGER_TYPE_LABELS[alert.trigger_type] || alert.trigger_type}
                  </div>
                  <div className="alerts-timeline__motor">{alert.motor_id}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── ALERT CARDS ── */}
      <div className="alerts-list" ref={alertListRef}>
        {loadingAlerts ? (
          <div className="alerts-loading" style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-secondary, #94a3b8)' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem', animation: 'spin 1.5s linear infinite' }}>⏳</div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary, #f8fafc)', marginBottom: '0.5rem' }}>
              Loading Active Alerts...
            </h3>
            <p style={{ fontSize: '0.9rem', maxWidth: '420px', margin: '0 auto' }}>
              Synchronizing active alarm conditions with the industrial gateway API.
            </p>
          </div>
        ) : alertFetchError ? (
          <div
            className="alerts-error-banner"
            style={{
              padding: '2.5rem 1.5rem',
              borderRadius: '12px',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              textAlign: 'center',
              margin: '1rem 0',
            }}
          >
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚠️</div>
            <h3 style={{ color: '#ef4444', fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Alerts Gateway Unavailable
            </h3>
            <p style={{ color: 'var(--text-secondary, #cbd5e1)', fontSize: '0.92rem', maxWidth: '520px', margin: '0 auto 1.5rem' }}>
              {alertFetchError}. Safety and threshold exceedance status cannot be verified. Do not assume equipment is safe.
            </p>
            {onRetryFetchAlerts && (
              <button
                className="alerts-btn alerts-btn--primary"
                onClick={onRetryFetchAlerts}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.6rem 1.5rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                <span>🔄</span> Retry Connection
              </button>
            )}
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="alerts-empty">
            <div className="alerts-empty__icon">✓</div>
            <h3>{filterTab === 'ALL' && severityFilter === 'ALL' && !searchQuery ? 'No active alerts' : 'No Alerts Match Current Filters'}</h3>
            <p>
              {filterTab === 'ALL' && severityFilter === 'ALL' && !searchQuery
                ? 'All motor telemetry and ML health classifications are currently within safe operational limits.'
                : 'Try adjusting your filters or search query to find alerts.'}
            </p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isExpanded = expandedAlertId === alert.alert_id
            const isCritical = alert.severity === 'CRITICAL'
            const isResolved = alert.state === 'RESOLVED'
            const isAssigned = !!alert.assigned_to
            const isAcknowledged = alert.state === 'ACKNOWLEDGED'
            const motor = motors.find((m) => m.motor_id === alert.motor_id)

            return (
              <div
                key={alert.alert_id}
                className={`alerts-card ${
                  isCritical ? 'alerts-card--critical' : alert.severity === 'WARNING' ? 'alerts-card--warning' : 'alerts-card--info'
                } ${isResolved ? 'alerts-card--resolved' : ''} ${isExpanded ? 'alerts-card--expanded' : ''}`}
                onClick={() => setExpandedAlertId(isExpanded ? null : alert.alert_id)}
              >
                {/* Card Header */}
                <div className="alerts-card__header">
                  <div className="alerts-card__badges">
                    <span className={`alerts-badge alerts-badge--${alert.severity.toLowerCase()}`}>
                      {SEVERITY_ICONS[alert.severity]} {alert.severity}
                    </span>
                    {(() => {
                      const cat = alert.category || TRIGGER_TYPE_TO_CATEGORY[alert.trigger_type] || 'SAFETY_THRESHOLD'
                      const conf = CATEGORY_CONFIG[cat]
                      return conf ? (
                        <span className={`alerts-category-badge ${conf.className}`}>
                          {conf.icon} {conf.label}
                        </span>
                      ) : null
                    })()}
                    {(() => {
                      const isML = alert.category === 'ML_INFERENCE' || alert.trigger_type.includes('INFERENCE')
                      if (!isML && !alert.ml_health_status) return null
                      const mlLabel = alert.ml_health_status || (alert.severity === 'CRITICAL' ? 'critical' : 'warning')
                      return (
                        <span className="alerts-ml-badge">
                          🧠 ML: {mlLabel.toUpperCase()}
                          {alert.ml_confidence !== undefined && alert.ml_confidence !== null
                            ? ` (${(alert.ml_confidence * 100).toFixed(0)}%)`
                            : alert.trigger_value > 0
                            ? ` (${(alert.trigger_value * 100).toFixed(0)}%)`
                            : ''}
                        </span>
                      )
                    })()}
                    <span className={`alerts-badge alerts-badge--state-${alert.state.toLowerCase()}`}>
                      ● {alert.state}
                    </span>
                    {alert.priority && (
                      <span className={`alerts-badge alerts-badge--priority-${alert.priority.toLowerCase()}`}>
                        P: {alert.priority}
                      </span>
                    )}
                    {motor && motor.source === 'hardware' && (
                      <span className="alerts-badge alerts-badge--hw">HW</span>
                    )}
                  </div>
                  <div className="alerts-card__meta">
                    <span className="alerts-card__id">{alert.alert_id}</span>
                    <span className="alerts-card__time">{formatTimeAgo(alert.triggered_at)}</span>
                  </div>
                </div>

                {/* Card Body */}
                <div className="alerts-card__body">
                  <div className="alerts-card__trigger-icon">
                    {TRIGGER_TYPE_ICONS[alert.trigger_type] || '⚠️'}
                  </div>
                  <div className="alerts-card__info">
                    <div className="alerts-card__motor-line">
                      <strong
                        className="alerts-card__motor-id"
                        onClick={(e) => {
                          e.stopPropagation()
                          onNavigateToMotor?.(alert.motor_id)
                        }}
                      >
                        {alert.motor_id}
                      </strong>
                      {alert.site_id && (
                        <span className="alerts-badge" style={{ fontSize: '10px', background: 'rgba(255,255,255,0.06)' }}>
                          📍 {alert.site_id}
                        </span>
                      )}
                      <span className="alerts-card__device">Device: {alert.device_id}</span>
                    </div>
                    <div className="alerts-card__message">{alert.message}</div>
                    <div className="alerts-card__trigger-label">
                      {TRIGGER_TYPE_LABELS[alert.trigger_type] || alert.trigger_type}
                    </div>
                  </div>
                </div>

                {/* Metrics Row */}
                <div className="alerts-card__metrics">
                  <div className="alerts-metric">
                    <span className="alerts-metric__label">Triggered Reading</span>
                    <span className="alerts-metric__value alerts-metric__value--danger">
                      {alert.trigger_value.toFixed(2)} {alert.unit}
                    </span>
                  </div>
                  <div className="alerts-metric">
                    <span className="alerts-metric__label">Safety Threshold</span>
                    <span className="alerts-metric__value alerts-metric__value--muted">
                      {alert.threshold_limit.toFixed(2)} {alert.unit}
                    </span>
                  </div>
                  <div className="alerts-metric">
                    <span className="alerts-metric__label">Overshoot</span>
                    <span className="alerts-metric__value alerts-metric__value--danger">
                      +{((alert.trigger_value / alert.threshold_limit - 1) * 100).toFixed(0)}%
                    </span>
                  </div>
                  {motor && motor.connectionStatus && (
                    <div className="alerts-metric">
                      <span className="alerts-metric__label">Motor Status</span>
                      <span className={`alerts-metric__value alerts-metric__value--${motor.connectionStatus}`}>
                        {motor.connectionStatus.toUpperCase()}
                      </span>
                    </div>
                  )}
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="alerts-card__expanded" onClick={(e) => e.stopPropagation()}>
                    {/* Assignment Status */}
                    <div className="alerts-card__assignment">
                      {isAssigned ? (
                        <div className="alerts-assignment-box alerts-assignment-box--assigned">
                          <div className="alerts-assignment-box__header">
                            <span className="alerts-assignment-box__badge">
                              👤 ASSIGNED TO: <strong>{alert.assigned_to}</strong>
                            </span>
                            <span className="alerts-assignment-box__time">
                              {alert.assigned_at ? new Date(alert.assigned_at).toLocaleString() : '—'}
                            </span>
                          </div>
                          {alert.instructions && (
                            <div className="alerts-assignment-box__instructions">
                              "{alert.instructions}"
                            </div>
                          )}
                          {alert.assigned_by && (
                            <div className="alerts-assignment-box__by">
                              Dispatched by: {alert.assigned_by}
                            </div>
                          )}
                        </div>
                      ) : isResolved ? (
                        <div className="alerts-assignment-box alerts-assignment-box--resolved">
                          <div className="alerts-assignment-box__header">
                            <span>✓ RESOLVED BY: <strong>{alert.resolved_by || '—'}</strong></span>
                            <span>{alert.resolved_at ? new Date(alert.resolved_at).toLocaleString() : ''}</span>
                          </div>
                          {alert.resolution_notes && (
                            <div className="alerts-assignment-box__notes">
                              Resolution: {alert.resolution_notes}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="alerts-assignment-box alerts-assignment-box--unassigned">
                          ⚠️ No technician currently dispatched to this incident.
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    {!isResolved && (
                      <div className="alerts-card__actions">
                        {alert.state === 'ACTIVE' && !isAssigned && (
                          <button
                            className="alerts-action-btn alerts-action-btn--ack"
                            onClick={() => isTechOrAbove ? handleAcknowledge(alert) : onOpenLogin?.()}
                            disabled={!isTechOrAbove}
                          >
                            {isTechOrAbove ? '👁️ Acknowledge' : '🔒 Requires L2+'}
                          </button>
                        )}
                        <button
                          className="alerts-action-btn alerts-action-btn--assign"
                          onClick={() => isManagerOrAdmin ? handleOpenAssignModal(alert) : onOpenLogin?.()}
                          disabled={!isManagerOrAdmin}
                        >
                          {isManagerOrAdmin
                            ? isAssigned
                              ? '🔄 Reassign Technician'
                              : '⚡ Assign to Technician'
                            : '🔒 Requires L3+ Manager'}
                        </button>
                        {(isAcknowledged || isAssigned) && (
                          <button
                            className="alerts-action-btn alerts-action-btn--resolve"
                            onClick={() => isTechOrAbove ? handleOpenResolveModal(alert) : onOpenLogin?.()}
                            disabled={!isTechOrAbove}
                          >
                            {isTechOrAbove ? '✓ Resolve & Close' : '🔒 Requires L2+'}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* ── ASSIGN MODAL ── */}
      {assignModalAlert && (
        <div className="modal-backdrop" onClick={() => setAssignModalAlert(null)}>
          <div className="modal-container alerts-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Dispatch Work Order</h3>
                <div className="modal-subtitle">
                  Assign <strong>{assignModalAlert.alert_id}</strong> on{' '}
                  <strong>{assignModalAlert.motor_id}</strong>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setAssignModalAlert(null)}>✕</button>
            </div>

            <div className="modal-body">
              {/* Alert Summary */}
              <div className="alerts-modal__summary">
                <span className={`alerts-badge alerts-badge--${assignModalAlert.severity.toLowerCase()}`}>
                  {SEVERITY_ICONS[assignModalAlert.severity]} {assignModalAlert.severity}
                </span>
                <span className="alerts-modal__summary-text">{assignModalAlert.message}</span>
              </div>

              {/* Technician Selection */}
              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label className="form-label" style={{ margin: 0 }}>Select Certified Field Technician</label>
                  {currentUser?.role === 'Manager' && currentUser.assigned_sites && currentUser.assigned_sites.length > 0 && (
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Scope: {currentUser.assigned_sites.join(', ')}
                    </span>
                  )}
                </div>

                {loadingTechnicians ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)', background: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
                    🔄 Querying verified technicians for authorized scope...
                  </div>
                ) : technicianFetchError ? (
                  <div style={{ padding: '0.75rem 1rem', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 'var(--radius-sm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>⚠️ {technicianFetchError}</span>
                    <button type="button" className="alerts-btn alerts-btn--sm alerts-btn--outline" onClick={fetchTechnicians}>
                      Retry
                    </button>
                  </div>
                ) : technicians.length === 0 ? (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)', background: 'var(--bg-app)', borderRadius: 'var(--radius-sm)' }}>
                    No active certified technicians found in your assigned scope.
                  </div>
                ) : (
                  <div className="tech-selection-grid">
                    {technicians.map((tech, idx) => (
                      <div
                        key={tech.id || tech.username}
                        className={`tech-card ${selectedTechnician === tech.username ? 'selected' : ''}`}
                        onClick={() => setSelectedTechnician(tech.username)}
                      >
                        <div className="tech-avatar" style={{ background: getAvatarColor(idx) }}>
                          {getInitials(tech.username)}
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                          <div className="tech-name">
                            <strong>{tech.username}</strong>
                            {tech.assigned_sites && tech.assigned_sites.length > 0 && (
                              <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: '6px' }}>
                                [{tech.assigned_sites.join(', ')}]
                              </span>
                            )}
                          </div>
                          <div className="tech-spec">{tech.email || 'Certified Field Technician'}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Priority */}
              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Work Order Priority</label>
                <div className="priority-btn-group">
                  {(['NORMAL', 'HIGH', 'URGENT', 'CRITICAL'] as const).map((pri) => (
                    <button
                      key={pri}
                      type="button"
                      className={`priority-select-btn ${pri.toLowerCase()} ${assignPriority === pri ? 'selected' : ''}`}
                      onClick={() => setAssignPriority(pri)}
                    >
                      {pri}
                    </button>
                  ))}
                </div>
              </div>

              {/* Instructions */}
              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Dispatch Work Instructions</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={assignInstructions}
                  onChange={(e) => setAssignInstructions(e.target.value)}
                  placeholder="Enter specific repair steps, safety protocols, and parts requirements..."
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setAssignModalAlert(null)}>
                  Cancel
                </button>
                <button type="button" className="btn-primary-glow" onClick={handleConfirmAssign}>
                  Confirm &amp; Dispatch →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── RESOLVE MODAL ── */}
      {resolveModalAlert && (
        <div className="modal-backdrop" onClick={() => setResolveModalAlert(null)}>
          <div className="modal-container alerts-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Resolve Alert</h3>
                <div className="modal-subtitle">
                  Close <strong>{resolveModalAlert.alert_id}</strong> on{' '}
                  <strong>{resolveModalAlert.motor_id}</strong>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setResolveModalAlert(null)}>✕</button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Service Type</label>
                <select
                  className="form-select"
                  value={resolveServiceType}
                  onChange={(e) => setResolveServiceType(e.target.value)}
                >
                  <option value="CORRECTIVE">Corrective Maintenance</option>
                  <option value="INSPECTION">Inspection & Verification</option>
                  <option value="PREVENTIVE">Preventive Maintenance</option>
                  <option value="EMERGENCY">Emergency Repair</option>
                  <option value="LUBRICATION">Lubrication Service</option>
                </select>
              </div>

              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Resolution Notes (required)</label>
                <textarea
                  className="form-textarea"
                  rows={4}
                  value={resolveNotes}
                  onChange={(e) => setResolveNotes(e.target.value)}
                  placeholder="Describe what was found, repaired, and verified..."
                />
              </div>

              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Parts Replaced (comma-separated)</label>
                <input
                  className="form-input"
                  value={resolveParts}
                  onChange={(e) => setResolveParts(e.target.value)}
                  placeholder="e.g. bearing-6203, drive-belt-v2"
                />
              </div>

              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Downtime (minutes)</label>
                <input
                  className="form-input"
                  type="number"
                  min={0}
                  value={resolveDowntime}
                  onChange={(e) => setResolveDowntime(parseInt(e.target.value) || 0)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setResolveModalAlert(null)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary-glow"
                  onClick={handleConfirmResolve}
                  disabled={resolveNotes.trim().length < 3}
                >
                  ✓ Resolve &amp; Log Maintenance →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
