import { useState } from 'react'
import type { FC } from 'react'
import type { AlertItem, UserProfile } from '../types'

interface ManagerViewProps {
  alerts: AlertItem[]
  onAssignAlert: (
    alertId: string,
    technician: string,
    priority: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL',
    instructions: string
  ) => void
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
}

export const ManagerView: FC<ManagerViewProps> = ({
  alerts,
  onAssignAlert,
  currentUser,
  onOpenLogin,
}) => {
  const isManagerOrAdmin = Boolean(
    currentUser && (currentUser.role === 'Manager' || currentUser.role === 'Admin' || currentUser.clearance_level >= 3)
  )

  const [selectedAlertForAssign, setSelectedAlertForAssign] = useState<AlertItem | null>(null)
  const [selectedTechnician, setSelectedTechnician] = useState<string>('tech_dave')
  const [selectedPriority, setSelectedPriority] = useState<'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL'>('CRITICAL')
  const [instructions, setInstructions] = useState<string>(
    'Inspect motor bearing immediately. Check for axial play, loose mount bolts, and measure dynamic vibration after torque verification.'
  )
  const [filterState, setFilterState] = useState<'ALL' | 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED'>('ALL')
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const activeAlerts = alerts.filter((a) => a.state !== 'RESOLVED')
  const criticalAlerts = alerts.filter((a) => a.severity === 'CRITICAL' && a.state !== 'RESOLVED')
  const unassignedCriticalCount = criticalAlerts.filter((a) => !a.assigned_to).length

  const filteredAlerts = alerts.filter((a) => {
    if (filterState === 'ALL') return true
    return a.state === filterState
  })

  const handleOpenAssignModal = (alert: AlertItem) => {
    setSelectedAlertForAssign(alert)
    if (alert.severity === 'CRITICAL') {
      setSelectedPriority('CRITICAL')
      setInstructions(`URGENT: ${alert.message}. Technician must inspect ${alert.motor_id} on site and complete repair logging.`)
    } else {
      setSelectedPriority('HIGH')
      setInstructions(`Review warning on ${alert.motor_id}. Verify temperature & electrical connections.`)
    }
  }

  const handleConfirmAssignment = () => {
    if (!selectedAlertForAssign) return
    onAssignAlert(
      selectedAlertForAssign.alert_id,
      selectedTechnician,
      selectedPriority,
      instructions
    )
    setToastMessage(`Dispatched ${selectedAlertForAssign.alert_id} to ${selectedTechnician}`)
    setSelectedAlertForAssign(null)
    setTimeout(() => setToastMessage(null), 3500)
  }

  return (
    <div className="manager-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="manager-toast">
          <span>✓</span> {toastMessage}
        </div>
      )}

      {/* Header & Metric Bar */}
      <div className="manager-header">
        <div>
          <div className="manager-pretitle">OPERATIONS MANAGEMENT &amp; DISPATCH HUB</div>
          <h1 className="manager-title">Incident Queue &amp; Work Order Assignment</h1>
          <p className="manager-desc">
            Monitor real-time critical motor alarms and assign emergency repair work orders directly to certified technicians.
          </p>
        </div>

        <div className="manager-dispatch-status">
          <div className={`status-counter-card ${unassignedCriticalCount > 0 ? 'critical-active' : ''}`}>
            <span className="counter-num">{unassignedCriticalCount}</span>
            <span className="counter-label">Unassigned Critical Alarms</span>
          </div>
          <div className="status-counter-card">
            <span className="counter-num">{activeAlerts.length}</span>
            <span className="counter-label">Active Plant Incidents</span>
          </div>
        </div>
      </div>

      {/* RBAC Clearance Warning Banner */}
      {!isManagerOrAdmin && (
        <div className="rbac-clearance-warning-banner">
          <div className="warning-text">
            🔒 <strong>Clearance Notice:</strong> Incident Dispatching requires <strong>Level 3 (Manager)</strong> or <strong>Level 4 (Admin)</strong> clearance.
            Currently logged in as <code>{currentUser?.username}</code> (L{currentUser?.clearance_level}). Dispatch actions are view-only.
          </div>
          {onOpenLogin && (
            <button className="btn-elevate-role" onClick={onOpenLogin}>
              ⚡ Switch to Manager Alice
            </button>
          )}
        </div>
      )}

      {/* Critical Alarms Attention Banner */}
      {criticalAlerts.length > 0 && (
        <div className="critical-dispatch-banner">
          <div className="banner-icon-pulse">🚨</div>
          <div className="banner-content">
            <div className="banner-title">
              Attention Required: {criticalAlerts.length} Critical Fault(s) Detected Across Fleet
            </div>
            <div className="banner-sub">
              TinyML edge classifiers and safety rules have detected equipment damage risks.
              Assign each incident below to a maintenance technician immediately.
            </div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="manager-filter-bar">
        <div className="filter-pill-group">
          {(['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'] as const).map((st) => (
            <button
              key={st}
              className={`manager-filter-pill ${filterState === st ? 'active' : ''}`}
              onClick={() => setFilterState(st)}
            >
              {st} ({alerts.filter((a) => (st === 'ALL' ? true : a.state === st)).length})
            </button>
          ))}
        </div>
      </div>

      {/* Incidents List */}
      <div className="incidents-grid">
        {filteredAlerts.length === 0 ? (
          <div className="empty-incidents-box">
            <div className="empty-icon">✓</div>
            <h3>No Incidents in {filterState} Status</h3>
            <p>All motor telemetry thresholds and ML health classifications are currently nominal.</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isCritical = alert.severity === 'CRITICAL'
            const isResolved = alert.state === 'RESOLVED'
            const isAssigned = !!alert.assigned_to

            return (
              <div
                key={alert.alert_id}
                className={`incident-card ${isCritical ? 'critical-border' : 'warning-border'} ${
                  isResolved ? 'resolved-card' : ''
                }`}
              >
                <div className="incident-card-top">
                  <div className="incident-badge-group">
                    <span className={`badge ${alert.severity.toLowerCase()}`}>
                      {alert.severity}
                    </span>
                    <span className={`badge state-${alert.state.toLowerCase()}`}>
                      ● {alert.state}
                    </span>
                    {alert.priority && (
                      <span className="badge priority-tag">
                        PRIORITY: {alert.priority}
                      </span>
                    )}
                  </div>
                  <span className="incident-id">{alert.alert_id}</span>
                </div>

                <div className="incident-motor-title">
                  <strong>{alert.motor_id}</strong> · Device: {alert.device_id}
                </div>

                <div className="incident-message">{alert.message}</div>

                <div className="incident-metrics">
                  <div className="metric-box">
                    <span className="m-label">Triggered Reading</span>
                    <span className="m-value text-critical">
                      {alert.trigger_value.toFixed(2)} {alert.unit}
                    </span>
                  </div>
                  <div className="metric-box">
                    <span className="m-label">Safety Threshold</span>
                    <span className="m-value text-muted">
                      {alert.threshold_limit.toFixed(2)} {alert.unit}
                    </span>
                  </div>
                  <div className="metric-box">
                    <span className="m-label">Trigger Type</span>
                    <span className="m-value text-secondary" style={{ fontSize: '0.75rem' }}>
                      {alert.trigger_type}
                    </span>
                  </div>
                </div>

                {/* Assignment & Technician Status */}
                <div className="incident-assignment-tray">
                  {isAssigned ? (
                    <div className="assigned-info-box">
                      <div className="assigned-header">
                        <span className="assigned-tech-badge">
                          👤 ASSIGNED TO: <strong>{alert.assigned_to}</strong>
                        </span>
                        <span className="assigned-time">
                          {alert.assigned_at
                            ? new Date(alert.assigned_at).toLocaleTimeString()
                            : 'Pending'}
                        </span>
                      </div>
                      {alert.instructions && (
                        <div className="assigned-instructions">
                          &ldquo;{alert.instructions}&rdquo;
                        </div>
                      )}
                    </div>
                  ) : isResolved ? (
                    <div className="resolved-info-box">
                      <div className="resolved-header">
                        <span>✓ RESOLVED BY: <strong>{alert.resolved_by || 'Technician'}</strong></span>
                      </div>
                      {alert.resolution_notes && (
                        <div className="resolved-notes">
                          Notes: {alert.resolution_notes}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="unassigned-prompt">
                      <span>⚠️ Unassigned incident — no technician currently dispatched.</span>
                    </div>
                  )}
                </div>

                {/* Action Controls */}
                {!isResolved && (
                  <div className="incident-card-actions">
                    {!isAssigned ? (
                      <button
                        className={`btn-assign-tech-urgent ${!isManagerOrAdmin ? 'disabled' : ''}`}
                        onClick={() => isManagerOrAdmin ? handleOpenAssignModal(alert) : onOpenLogin?.()}
                        title={!isManagerOrAdmin ? 'Requires Level 3 Manager Clearance' : 'Assign Incident'}
                      >
                        {isManagerOrAdmin ? '⚡ Assign to Technician →' : '🔒 Requires Manager Clearance (L3)'}
                      </button>
                    ) : (
                      <button
                        className={`btn-reassign-tech ${!isManagerOrAdmin ? 'disabled' : ''}`}
                        onClick={() => isManagerOrAdmin ? handleOpenAssignModal(alert) : onOpenLogin?.()}
                        title={!isManagerOrAdmin ? 'Requires Level 3 Manager Clearance' : 'Reassign Incident'}
                      >
                        {isManagerOrAdmin ? 'Reassign Technician / Update Order' : '🔒 Read-Only Assignment'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Assignment Modal */}
      {selectedAlertForAssign && (
        <div className="modal-backdrop" onClick={() => setSelectedAlertForAssign(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Dispatch Work Order</h3>
                <div className="modal-subtitle">
                  Assign incident <strong>{selectedAlertForAssign.alert_id}</strong> on{' '}
                  <strong>{selectedAlertForAssign.motor_id}</strong>
                </div>
              </div>
              <button
                className="modal-close-btn"
                onClick={() => setSelectedAlertForAssign(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Select Certified Field Technician</label>
                <div className="tech-selection-grid">
                  <div
                    className={`tech-card ${selectedTechnician === 'tech_dave' ? 'selected' : ''}`}
                    onClick={() => setSelectedTechnician('tech_dave')}
                  >
                    <div className="tech-avatar">DM</div>
                    <div>
                      <div className="tech-name">Dave Miller (tech_dave)</div>
                      <div className="tech-spec">Mechanical &amp; Vibration Specialist</div>
                    </div>
                  </div>

                  <div
                    className={`tech-card ${selectedTechnician === 'tech_sara' ? 'selected' : ''}`}
                    onClick={() => setSelectedTechnician('tech_sara')}
                  >
                    <div className="tech-avatar">SC</div>
                    <div>
                      <div className="tech-name">Sara Connor (tech_sara)</div>
                      <div className="tech-spec">Electrical &amp; Thermal Specialist</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Work Order Priority</label>
                <div className="priority-btn-group">
                  {(['NORMAL', 'HIGH', 'URGENT', 'CRITICAL'] as const).map((pri) => (
                    <button
                      key={pri}
                      type="button"
                      className={`priority-select-btn ${pri.toLowerCase()} ${
                        selectedPriority === pri ? 'selected' : ''
                      }`}
                      onClick={() => setSelectedPriority(pri)}
                    >
                      {pri}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Dispatch Work Instructions for Technician</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Enter specific repair steps, safety protocols, and parts requirements..."
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSelectedAlertForAssign(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary-glow"
                  onClick={handleConfirmAssignment}
                >
                  Confirm &amp; Dispatch Work Order →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
