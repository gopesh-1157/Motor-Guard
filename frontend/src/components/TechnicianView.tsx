import { useState, useEffect, useCallback } from 'react'
import type { FC } from 'react'
import type { UserProfile, WorkOrderItem, AlertItem } from '../types'

interface TechnicianViewProps {
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
  onRefreshData?: () => void
  alerts?: AlertItem[]
  onResolveAlert?: (
    alertId: string,
    motorId: string,
    resolutionNotes: string,
    serviceType: string,
    partsReplaced: string[],
    downtimeMinutes: number
  ) => void
}

const COMMON_SPARE_PARTS = [
  'SKF 608-2RS Deep-Groove Ball Bearing',
  'M4 High-Tensile Mounting Hardware Set',
  'Silicone Thermal Conductive Paste',
  'Centrifugal Fan Shroud Air Filter',
  'Carbon Brush Assembly Set (RS-775)',
  'Vibration Damping Neoprene Mounts',
  'ACS712 Terminal Header Block',
]

export const TechnicianView: FC<TechnicianViewProps> = ({
  currentUser,
  onOpenLogin,
  onRefreshData,
  alerts: _alerts,
  onResolveAlert,
}) => {
  const isAuthorized =
    currentUser && (currentUser.role === 'Technician' || currentUser.role === 'Admin')

  const [workOrders, setWorkOrders] = useState<WorkOrderItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedWoForRepair, setSelectedWoForRepair] = useState<WorkOrderItem | null>(null)
  const [selectedWoForReject, setSelectedWoForReject] = useState<WorkOrderItem | null>(null)

  // Repair Modal Form State
  const [diagnosis, setDiagnosis] = useState(
    'Excessive bearing raceway clearance and harmonic vibration under rotational load.'
  )
  const [actionsTaken, setActionsTaken] = useState(
    'Disassembled motor casing, pressed out worn ball bearing, cleaned drive shaft, seated new bearing, torqued mounting hardware to 12 Nm.'
  )
  const [partsSelected, setPartsSelected] = useState<string[]>([
    'SKF 608-2RS Deep-Groove Ball Bearing',
    'M4 High-Tensile Mounting Hardware Set',
  ])
  const [downtimeMinutes, setDowntimeMinutes] = useState(35)
  const [resolutionNotes, setResolutionNotes] = useState(
    'Bench-tested with 12V DC power supply; vibration normalized to 0.058 g RMS baseline. Motor returned to operating pool.'
  )
  const [rejectionReason, setRejectionReason] = useState('')
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 4000)
  }

  // Fetch work orders for active technician
  const fetchWorkOrders = useCallback(async () => {
    if (!isAuthorized) return
    setIsLoading(true)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/work-orders', { headers })
      if (res.ok) {
        const data = await res.json()
        setWorkOrders(Array.isArray(data) ? data : [])
      }
    } catch {
      // Offline or network error
    } finally {
      setIsLoading(false)
    }
  }, [isAuthorized])

  useEffect(() => {
    fetchWorkOrders()
  }, [fetchWorkOrders])

  // Accept assignment
  const handleAccept = async (woId: string) => {
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch(`/api/v1/work-orders/${woId}/accept`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ notes: 'Accepted by field technician' }),
      })
      if (res.ok) {
        showToast(`Work Order ${woId} accepted. You may now begin work.`)
        await fetchWorkOrders()
        onRefreshData?.()
      }
    } catch {
      showToast('Failed to accept work order')
    }
  }

  // Start work
  const handleStart = async (woId: string) => {
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch(`/api/v1/work-orders/${woId}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ notes: 'Maintenance intervention started' }),
      })
      if (res.ok) {
        showToast(`Work Order ${woId} marked In Progress.`)
        await fetchWorkOrders()
        onRefreshData?.()
      }
    } catch {
      showToast('Failed to start work order')
    }
  }

  // Confirm Reject
  const handleConfirmReject = async () => {
    if (!selectedWoForReject || !rejectionReason.trim()) return
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch(`/api/v1/work-orders/${selectedWoForReject.work_order_id}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ rejection_reason: rejectionReason }),
      })
      if (res.ok) {
        showToast(`Work Order ${selectedWoForReject.work_order_id} rejected.`)
        setSelectedWoForReject(null)
        setRejectionReason('')
        await fetchWorkOrders()
        onRefreshData?.()
      }
    } catch {
      showToast('Failed to reject work order')
    }
  }

  // Confirm Resolve
  const handleConfirmResolve = async () => {
    if (!selectedWoForRepair) return
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch(`/api/v1/work-orders/${selectedWoForRepair.work_order_id}/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          diagnosis,
          actions_taken: actionsTaken,
          parts_replaced: partsSelected,
          downtime_minutes: downtimeMinutes,
          resolution_notes: resolutionNotes,
        }),
      })
      if (res.ok) {
        showToast(`Work Order ${selectedWoForRepair.work_order_id} resolved & signed off!`)
        if (selectedWoForRepair.alert_id && onResolveAlert) {
          onResolveAlert(
            selectedWoForRepair.alert_id,
            selectedWoForRepair.motor_id,
            resolutionNotes || diagnosis,
            'CORRECTIVE',
            partsSelected,
            downtimeMinutes
          )
        }
        setSelectedWoForRepair(null)
        await fetchWorkOrders()
        onRefreshData?.()
      }
    } catch {
      showToast('Failed to resolve work order')
    }
  }

  const togglePart = (part: string) => {
    setPartsSelected((prev) =>
      prev.includes(part) ? prev.filter((p) => p !== part) : [...prev, part]
    )
  }

  if (!currentUser || !isAuthorized) {
    return (
      <div className="technician-container">
        <div className="rbac-clearance-warning-banner" style={{ margin: '2rem 0' }}>
          <div className="warning-text">
            🔒 <strong>Authentication Required:</strong> Access to the Field Maintenance Workbench
            is restricted to certified <strong>Technicians</strong> and <strong>Administrators</strong>.
            You are currently {currentUser ? `logged in as ${currentUser.username} (${currentUser.role})` : 'unauthenticated'}.
          </div>
          {onOpenLogin && (
            <button className="btn-elevate-role" onClick={onOpenLogin} style={{ marginTop: '0.75rem' }}>
              🔑 Sign In as Technician
            </button>
          )}
        </div>
      </div>
    )
  }

  const pendingOrders = workOrders.filter((wo) => wo.status === 'Assigned')
  const activeOrders = workOrders.filter(
    (wo) => wo.status === 'Accepted' || wo.status === 'In Progress'
  )
  const completedOrders = workOrders.filter(
    (wo) => wo.status === 'Resolved' || wo.status === 'Rejected'
  )

  return (
    <div className="technician-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="manager-toast">
          <span>✓</span> {toastMessage}
        </div>
      )}

      {/* Header */}
      <div className="tech-workbench-header">
        <div>
          <div className="manager-pretitle">FIELD MAINTENANCE WORKBENCH</div>
          <h1 className="manager-title">
            Assigned Work Orders for {currentUser.username}
          </h1>
          <p className="manager-desc">
            Complete dispatched motor repairs, record replaced components, and sign off verified maintenance records.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            className="btn-secondary"
            onClick={fetchWorkOrders}
            disabled={isLoading}
            style={{ fontSize: '12px', padding: '6px 12px' }}
          >
            🔄 {isLoading ? 'Refreshing...' : 'Refresh Orders'}
          </button>
        </div>
      </div>

      {/* ── 1. ACTIVE / IN-PROGRESS ORDERS ── */}
      <div className="workbench-section-title">
        <span>Active Interventions in Progress ({activeOrders.length})</span>
        <span className="badge priority-tag">{activeOrders.length} ACTIVE</span>
      </div>

      <div className="incidents-grid">
        {activeOrders.length === 0 ? (
          <div className="empty-incidents-box">
            <div className="empty-icon">✓</div>
            <h3>No Active Interventions</h3>
            <p>Accept a pending dispatched work order below to begin physical repair.</p>
          </div>
        ) : (
          activeOrders.map((wo) => (
            <div
              key={wo.work_order_id}
              className={`incident-card ${wo.priority === 'CRITICAL' ? 'critical-border' : 'warning-border'}`}
            >
              <div className="incident-card-top">
                <div className="incident-badge-group">
                  <span className={`badge ${wo.status === 'In Progress' ? 'critical' : 'warning'}`}>
                    {wo.status.toUpperCase()}
                  </span>
                  <span className="badge priority-tag">{wo.priority}</span>
                </div>
                <span className="incident-id">{wo.work_order_id}</span>
              </div>

              <div className="incident-motor-title">
                <strong>{wo.motor_id}</strong> &mdash; {wo.title}
              </div>

              <div className="incident-message">{wo.description}</div>

              <div className="tech-instructions-callout">
                <span className="callout-label">DISPATCH DETAILS:</span>
                <p className="callout-text">
                  Assigned by: <strong>{wo.assigned_by_user_id}</strong> &middot;{' '}
                  {wo.alert_id ? `Linked Alert: ${wo.alert_id}` : 'Direct dispatch'}
                </p>
              </div>

              <div className="incident-card-actions" style={{ display: 'flex', gap: '8px' }}>
                {wo.status === 'Accepted' && (
                  <button
                    className="btn-primary-glow"
                    style={{ flex: 1 }}
                    onClick={() => handleStart(wo.work_order_id)}
                  >
                    ▶ Begin Maintenance Work &rarr;
                  </button>
                )}
                {wo.status === 'In Progress' && (
                  <button
                    className="btn-complete-repair"
                    style={{ flex: 1 }}
                    onClick={() => setSelectedWoForRepair(wo)}
                  >
                    🔧 Complete &amp; Sign Off Work Order &rarr;
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── 2. NEW ASSIGNMENTS QUEUE ── */}
      <div className="workbench-section-title" style={{ marginTop: '2.5rem' }}>
        <span>New Dispatched Work Orders Awaiting Acceptance ({pendingOrders.length})</span>
        <span className="badge priority-tag">{pendingOrders.length} DISPATCHED</span>
      </div>

      <div className="incidents-grid">
        {pendingOrders.length === 0 ? (
          <div className="empty-incidents-box">
            <div className="empty-icon">✓</div>
            <h3>No Unaccepted Work Orders</h3>
            <p>All dispatched assignments have been acknowledged.</p>
          </div>
        ) : (
          pendingOrders.map((wo) => (
            <div
              key={wo.work_order_id}
              className={`incident-card ${wo.priority === 'CRITICAL' ? 'critical-border' : 'warning-border'}`}
            >
              <div className="incident-card-top">
                <div className="incident-badge-group">
                  <span className="badge state-active">ASSIGNED</span>
                  <span className="badge priority-tag">{wo.priority}</span>
                </div>
                <span className="incident-id">{wo.work_order_id}</span>
              </div>

              <div className="incident-motor-title">
                <strong>{wo.motor_id}</strong> &mdash; {wo.title}
              </div>

              <div className="incident-message">{wo.description}</div>

              <div className="tech-instructions-callout">
                <span className="callout-label">ASSIGNED BY {wo.assigned_by_user_id.toUpperCase()}:</span>
                <p className="callout-text">
                  Dispatched at {new Date(wo.created_at).toLocaleTimeString()}
                </p>
              </div>

              <div className="incident-card-actions" style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn-primary-glow"
                  style={{ flex: 2 }}
                  onClick={() => handleAccept(wo.work_order_id)}
                >
                  ✓ Accept Work Order
                </button>
                <button
                  className="btn-secondary"
                  style={{ flex: 1, borderColor: 'var(--status-critical-border)' }}
                  onClick={() => setSelectedWoForReject(wo)}
                >
                  ✕ Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── 3. COMPLETED MAINTENANCE AUDIT LOG ── */}
      {completedOrders.length > 0 && (
        <div style={{ marginTop: '2.5rem' }}>
          <div className="workbench-section-title">
            <span>Completed &amp; Resolved Work Orders ({completedOrders.length})</span>
          </div>

          <div className="completed-log-list">
            {completedOrders.map((wo) => (
              <div key={wo.work_order_id} className="completed-log-item">
                <div className="log-item-left">
                  <span
                    className="log-check"
                    style={{
                      background:
                        wo.status === 'Resolved'
                          ? 'var(--status-healthy-bg)'
                          : 'var(--status-critical-bg)',
                      color:
                        wo.status === 'Resolved'
                          ? 'var(--status-healthy)'
                          : 'var(--status-critical)',
                    }}
                  >
                    {wo.status === 'Resolved' ? '✓' : '✕'}
                  </span>
                  <div>
                    <div className="log-title">
                      <strong>{wo.motor_id}</strong> &mdash; {wo.title} (
                      <code>{wo.work_order_id}</code>)
                    </div>
                    {wo.status === 'Resolved' ? (
                      <div className="log-notes">
                        <strong>Diagnosis:</strong> {wo.diagnosis} &bull;{' '}
                        <strong>Actions:</strong> {wo.actions_taken} &bull;{' '}
                        <strong>Parts:</strong> {wo.parts_replaced.join(', ') || 'None'}
                      </div>
                    ) : (
                      <div className="log-notes text-critical">
                        <strong>Rejection Reason:</strong> {wo.rejection_reason}
                      </div>
                    )}
                  </div>
                </div>
                <div className="log-meta">
                  <span
                    className={`badge ${wo.status === 'Resolved' ? 'state-resolved' : 'state-rejected'}`}
                  >
                    {wo.status.toUpperCase()}
                  </span>
                  <span className="log-date">
                    {wo.resolved_at
                      ? new Date(wo.resolved_at).toLocaleTimeString()
                      : wo.rejected_at
                      ? new Date(wo.rejected_at).toLocaleTimeString()
                      : 'Completed'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── REPAIR & RESOLUTION MODAL ── */}
      {selectedWoForRepair && (
        <div className="modal-backdrop" onClick={() => setSelectedWoForRepair(null)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '680px' }}
          >
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Complete Work Order &amp; Sign Off</h3>
                <div className="modal-subtitle">
                  Logging maintenance intervention for{' '}
                  <strong>{selectedWoForRepair.motor_id}</strong> (
                  <code>{selectedWoForRepair.work_order_id}</code>)
                </div>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedWoForRepair(null)}
              >
                &times;
              </button>
            </div>

            <div className="modal-body">
              {/* Root Cause Diagnosis */}
              <div className="form-group">
                <label className="form-label">Root Cause Diagnosis</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="Explain the mechanical, thermal, or electrical defect identified..."
                />
              </div>

              {/* Corrective Actions Taken */}
              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Corrective Actions Performed</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={actionsTaken}
                  onChange={(e) => setActionsTaken(e.target.value)}
                  placeholder="Detail the repair, replacement, or calibration procedures executed..."
                />
              </div>

              {/* Parts Replaced */}
              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Replaced Spare Parts &amp; Hardware</label>
                <div className="parts-tag-grid">
                  {COMMON_SPARE_PARTS.map((part) => (
                    <button
                      key={part}
                      type="button"
                      className={`part-pill-btn ${partsSelected.includes(part) ? 'selected' : ''}`}
                      onClick={() => togglePart(part)}
                    >
                      {partsSelected.includes(part) ? '✓ ' : '+ '}
                      {part}
                    </button>
                  ))}
                </div>
              </div>

              {/* Measured Downtime */}
              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Total Intervention Downtime (Minutes)</label>
                <input
                  type="number"
                  min="0"
                  max="1440"
                  className="form-input"
                  value={downtimeMinutes}
                  onChange={(e) => setDowntimeMinutes(Number(e.target.value))}
                />
              </div>

              {/* Resolution & Re-testing Notes */}
              <div className="form-group" style={{ marginTop: '1rem' }}>
                <label className="form-label">Final Sign-off &amp; Re-testing Notes</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Post-repair telemetry observations, vibration re-test results, safety verification..."
                />
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.75rem',
                  marginTop: '1.5rem',
                }}
              >
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSelectedWoForRepair(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary-glow"
                  onClick={handleConfirmResolve}
                >
                  ✓ Sign Off &amp; Close Work Order
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── REJECT WORK ORDER MODAL ── */}
      {selectedWoForReject && (
        <div className="modal-backdrop" onClick={() => setSelectedWoForReject(null)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '480px' }}
          >
            <div className="modal-header">
              <h3 className="modal-title">Reject Work Order</h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedWoForReject(null)}
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Provide a reason for rejecting work order{' '}
                <code>{selectedWoForReject.work_order_id}</code>. The operations manager will be
                notified to reassign.
              </p>
              <div className="form-group">
                <label className="form-label">Rejection Reason</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Requires electrical specialist, out of shift, missing spare part..."
                />
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.75rem',
                  marginTop: '1.5rem',
                }}
              >
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSelectedWoForReject(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary-glow"
                  style={{ background: 'var(--status-critical)' }}
                  onClick={handleConfirmReject}
                >
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
