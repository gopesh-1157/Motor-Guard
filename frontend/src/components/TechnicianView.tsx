import { useState } from 'react'
import type { FC } from 'react'
import type { AlertItem, UserProfile } from '../types'

interface TechnicianViewProps {
  alerts: AlertItem[]
  onResolveAlert: (
    alertId: string,
    motorId: string,
    resolutionNotes: string,
    serviceType: string,
    partsReplaced: string[],
    downtimeMinutes: number
  ) => void
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
}

export const TechnicianView: FC<TechnicianViewProps> = ({
  alerts,
  onResolveAlert,
  currentUser,
  onOpenLogin,
}) => {
  const isTechOrAdmin = !currentUser || currentUser.clearance_level >= 2
  const [selectedTechOverride, setSelectedTechOverride] = useState<string | null>(null)
  const activeTechnician =
    selectedTechOverride ?? (currentUser?.role === 'Technician' ? currentUser.username : 'tech_dave')

  const [selectedAlertForRepair, setSelectedAlertForRepair] = useState<AlertItem | null>(null)

  // Repair form state
  const [serviceType, setServiceType] = useState<string>('REPAIR')
  const [resolutionNotes, setResolutionNotes] = useState<string>(
    'Dismantled motor end bell, extracted worn ball bearing, pressed in new SKF 608-2RS bearing, re-torqued mounting hardware to 12 Nm. Vibration normalized to baseline.'
  )
  const [partsSelected, setPartsSelected] = useState<string[]>([
    'SKF 608-2RS Deep-Groove Ball Bearing',
    'M4 Mounting Bolt Hardware Set',
  ])
  const [downtimeMinutes, setDowntimeMinutes] = useState<number>(35)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  // Filter alerts assigned to this technician
  const assignedAlerts = alerts.filter(
    (a) => a.assigned_to === activeTechnician && a.state !== 'RESOLVED'
  )
  const completedAlerts = alerts.filter(
    (a) => a.resolved_by === activeTechnician || (a.assigned_to === activeTechnician && a.state === 'RESOLVED')
  )

  const handleTogglePart = (part: string) => {
    setPartsSelected((prev) =>
      prev.includes(part) ? prev.filter((p) => p !== part) : [...prev, part]
    )
  }

  const handleOpenRepairModal = (alert: AlertItem) => {
    setSelectedAlertForRepair(alert)
    if (alert.trigger_type.includes('VIBRATION')) {
      setServiceType('REPAIR')
      setResolutionNotes(
        `Disassembled bearing housing on ${alert.motor_id}. Replaced damaged bearing, tightened mount bolts. Re-tested idle vibration at 0.065 g RMS.`
      )
      setPartsSelected(['SKF 608-2RS Deep-Groove Ball Bearing'])
      setDowntimeMinutes(35)
    } else if (alert.trigger_type.includes('TEMPERATURE')) {
      setServiceType('INSPECTION')
      setResolutionNotes(
        `Cleaned cooling air intake shroud on ${alert.motor_id}. Tested thermal dissipation under full DC load; chassis temp stabilized at 38.2 °C.`
      )
      setPartsSelected([])
      setDowntimeMinutes(20)
    } else {
      setServiceType('CALIBRATION')
      setResolutionNotes(`Inspected electrical terminals, verified ACS712 zero offset, normalized circuit load.`)
      setPartsSelected([])
      setDowntimeMinutes(15)
    }
  }

  const handleConfirmRepair = () => {
    if (!selectedAlertForRepair) return
    onResolveAlert(
      selectedAlertForRepair.alert_id,
      selectedAlertForRepair.motor_id,
      resolutionNotes,
      serviceType,
      partsSelected,
      downtimeMinutes
    )
    setToastMessage(`Work Order for ${selectedAlertForRepair.motor_id} completed & signed off!`)
    setSelectedAlertForRepair(null)
    setTimeout(() => setToastMessage(null), 3500)
  }

  return (
    <div className="technician-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="manager-toast">
          <span>✓</span> {toastMessage}
        </div>
      )}

      {/* RBAC Clearance Warning Banner */}
      {!isTechOrAdmin && (
        <div className="rbac-clearance-warning-banner">
          <div className="warning-text">
            🔒 <strong>Clearance Notice:</strong> Field Repair execution requires <strong>Level 2 (Technician)</strong> or <strong>Level 4 (Admin)</strong> clearance.
            Currently logged in as <code>{currentUser?.username}</code> (L{currentUser?.clearance_level}). Repair interventions are view-only.
          </div>
          {onOpenLogin && (
            <button className="btn-elevate-role" onClick={onOpenLogin}>
              ⚡ Switch to Technician Dave
            </button>
          )}
        </div>
      )}

      {/* Header & Technician Switcher */}
      <div className="tech-workbench-header">
        <div>
          <div className="manager-pretitle">FIELD MAINTENANCE WORKBENCH</div>
          <h1 className="manager-title">Assigned Work Orders &amp; Repair Actions</h1>
          <p className="manager-desc">
            Complete dispatched emergency interventions, record replaced components, and sign off resolved motor alarms.
          </p>
        </div>

        {/* Technician Profile Selector */}
        <div className="technician-switcher-box">
          <span className="switcher-label">Active Technician Profile:</span>
          <div className="switcher-buttons">
            <button
              className={`switcher-btn ${activeTechnician === 'tech_dave' ? 'active' : ''}`}
              onClick={() => setSelectedTechOverride('tech_dave')}
            >
              <span className="tech-initials">DM</span>
              <span>Dave Miller (Mechanical)</span>
            </button>
            <button
              className={`switcher-btn ${activeTechnician === 'tech_sara' ? 'active' : ''}`}
              onClick={() => setSelectedTechOverride('tech_sara')}
            >
              <span className="tech-initials">SC</span>
              <span>Sara Connor (Electrical)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Dispatched Tickets Queue */}
      <div className="workbench-section-title">
        <span>Active Dispatched Work Orders for {activeTechnician}</span>
        <span className="badge priority-tag">{assignedAlerts.length} PENDING</span>
      </div>

      <div className="incidents-grid">
        {assignedAlerts.length === 0 ? (
          <div className="empty-incidents-box">
            <div className="empty-icon">✓</div>
            <h3>No Pending Work Orders for {activeTechnician}</h3>
            <p>
              All dispatched repair tickets for this technician have been completed and verified.
              Switch technician profile above or assign new incidents from the Operations Manager Hub.
            </p>
          </div>
        ) : (
          assignedAlerts.map((alert) => (
            <div
              key={alert.alert_id}
              className={`incident-card ${alert.severity === 'CRITICAL' ? 'critical-border' : 'warning-border'}`}
            >
              <div className="incident-card-top">
                <div className="incident-badge-group">
                  <span className={`badge ${alert.severity.toLowerCase()}`}>
                    {alert.severity}
                  </span>
                  <span className="badge priority-tag">
                    {alert.priority || 'URGENT'}
                  </span>
                </div>
                <span className="incident-id">{alert.alert_id}</span>
              </div>

              <div className="incident-motor-title">
                <strong>{alert.motor_id}</strong> · Device: {alert.device_id}
              </div>

              <div className="incident-message">{alert.message}</div>

              {/* Manager Dispatch Instructions */}
              {alert.instructions && (
                <div className="tech-instructions-callout">
                  <span className="callout-label">MANAGER INSTRUCTIONS:</span>
                  <p className="callout-text">&ldquo;{alert.instructions}&rdquo;</p>
                </div>
              )}

              {/* Measured Metrics */}
              <div className="incident-metrics">
                <div className="metric-box">
                  <span className="m-label">Telemetry Reading</span>
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
                  <span className="m-label">Dispatched By</span>
                  <span className="m-value text-cyan" style={{ fontSize: '0.8rem' }}>
                    {alert.assigned_by || 'Operations Manager'}
                  </span>
                </div>
              </div>

              {/* Technician Completion Action */}
              <div className="incident-card-actions">
                <button
                  className={`btn-complete-repair ${!isTechOrAdmin ? 'disabled' : ''}`}
                  onClick={() => isTechOrAdmin ? handleOpenRepairModal(alert) : onOpenLogin?.()}
                  title={!isTechOrAdmin ? 'Requires Level 2 Technician Clearance' : 'Perform repair'}
                >
                  {isTechOrAdmin
                    ? '🔧 Perform Repair & Sign Off Work Order →'
                    : '🔒 Requires Technician Clearance (L2)'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Completed Service History */}
      {completedAlerts.length > 0 && (
        <div style={{ marginTop: '2.5rem' }}>
          <div className="workbench-section-title">
            <span>Completed Maintenance Audit Log ({completedAlerts.length})</span>
          </div>

          <div className="completed-log-list">
            {completedAlerts.map((ca) => (
              <div key={ca.alert_id} className="completed-log-item">
                <div className="log-item-left">
                  <span className="log-check">✓</span>
                  <div>
                    <div className="log-title">
                      <strong>{ca.motor_id}</strong> — {ca.trigger_type}
                    </div>
                    <div className="log-notes">{ca.resolution_notes || 'Intervention resolved and verified.'}</div>
                  </div>
                </div>
                <div className="log-meta">
                  <span className="badge state-resolved">RESOLVED</span>
                  <span className="log-date">
                    {ca.resolved_at ? new Date(ca.resolved_at).toLocaleTimeString() : 'Completed'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Repair Modal */}
      {selectedAlertForRepair && (
        <div className="modal-backdrop" onClick={() => setSelectedAlertForRepair(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Complete Work Order &amp; Sign Off</h3>
                <div className="modal-subtitle">
                  Logging maintenance intervention for <strong>{selectedAlertForRepair.motor_id}</strong>
                </div>
              </div>
              <button
                className="modal-close-btn"
                onClick={() => setSelectedAlertForRepair(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Intervention Service Type</label>
                <div className="priority-btn-group">
                  {(['REPAIR', 'REPLACEMENT', 'LUBRICATION', 'CALIBRATION', 'INSPECTION'] as const).map(
                    (st) => (
                      <button
                        key={st}
                        type="button"
                        className={`priority-select-btn ${serviceType === st ? 'selected' : ''}`}
                        onClick={() => setServiceType(st)}
                      >
                        {st}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Technician Work Details &amp; Diagnosis</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Detail mechanical observations, root cause, and post-repair baseline readings..."
                />
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Parts / Materials Replaced</label>
                <div className="parts-checklist">
                  {[
                    'SKF 608-2RS Deep-Groove Ball Bearing',
                    'M4 Mounting Bolt Hardware Set',
                    'Rubber Anti-Vibration Isolator Mount',
                    'High-Temperature Synthetic Grease (5g)',
                    'Air Intake Filter Screen',
                  ].map((part) => (
                    <label key={part} className="part-checkbox-label">
                      <input
                        type="checkbox"
                        checked={partsSelected.includes(part)}
                        onChange={() => handleTogglePart(part)}
                      />
                      <span>{part}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label className="form-label">Total Equipment Downtime (Minutes)</label>
                <input
                  type="number"
                  className="search-input"
                  style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid var(--border-subtle)',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    maxWidth: '160px',
                  }}
                  value={downtimeMinutes}
                  min={0}
                  max={480}
                  onChange={(e) => setDowntimeMinutes(parseInt(e.target.value) || 0)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSelectedAlertForRepair(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-complete-repair"
                  onClick={handleConfirmRepair}
                >
                  ✓ Sign Off &amp; Return Asset to Healthy →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
