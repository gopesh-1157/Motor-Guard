import { useState, useEffect, useCallback, useMemo } from 'react'
import type { FC } from 'react'
import {
  Wrench,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  RotateCcw,
  Plus,
  Search,
  Check,
  X,
  UserCheck,
  ArrowRight,
} from 'lucide-react'
import type { UserProfile, WorkOrderItem, AlertItem, WorkOrderPriority } from '../types'
import { PageHeader } from './common/PageHeader'
import { StatCard } from './common/StatCard'
import { StatusBadge } from './common/StatusBadge'
import { EmptyState } from './common/EmptyState'
import { LoadingSkeleton } from './common/LoadingSkeleton'
import { ErrorBanner } from './common/ErrorBanner'

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

interface ManagedTechUser {
  username: string
  role: string
  assigned_sites?: string[]
}

export const TechnicianView: FC<TechnicianViewProps> = ({
  currentUser,
  onOpenLogin,
  onRefreshData,
  alerts: _alerts,
  onResolveAlert,
}) => {
  const isAuthorized =
    currentUser && (currentUser.role === 'Technician' || currentUser.role === 'Admin' || currentUser.role === 'Manager')

  const [workOrders, setWorkOrders] = useState<WorkOrderItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedWoForRepair, setSelectedWoForRepair] = useState<WorkOrderItem | null>(null)
  const [selectedWoForReject, setSelectedWoForReject] = useState<WorkOrderItem | null>(null)
  const [selectedWoForReassign, setSelectedWoForReassign] = useState<WorkOrderItem | null>(null)

  // Filters state
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [technicianFilter, setTechnicianFilter] = useState('ALL')

  // Reassignment state
  const [availableTechnicians, setAvailableTechnicians] = useState<ManagedTechUser[]>([])
  const [targetTechUsername, setTargetTechUsername] = useState('')
  const [reassignNotes, setReassignNotes] = useState('')
  const [isReassigning, setIsReassigning] = useState(false)

  // Create Work Order modal state (Admin / Manager)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newMotorId, setNewMotorId] = useState('MTR-775-001')
  const [newAssignedTech, setNewAssignedTech] = useState('')
  const [newPriority, setNewPriority] = useState<WorkOrderPriority>('HIGH')
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false)

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

  // Fetch work orders for active role
  const fetchWorkOrders = useCallback(async () => {
    if (!isAuthorized) return
    setIsLoading(true)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      let url = '/api/v1/work-orders'
      // Admins and Managers can optionally filter by technician on the server
      if (technicianFilter !== 'ALL' && currentUser?.role !== 'Technician') {
        url += `?assigned_to=${encodeURIComponent(technicianFilter)}`
      }

      const res = await fetch(url, { headers })
      if (res.ok) {
        const data = await res.json()
        setWorkOrders(Array.isArray(data) ? data : [])
      }
    } catch {
      // Offline or network error
    } finally {
      setIsLoading(false)
    }
  }, [isAuthorized, technicianFilter, currentUser?.role])

  // Fetch technician list for Admin/Manager
  const fetchTechnicians = useCallback(async () => {
    if (!currentUser || currentUser.role === 'Technician') return
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/auth/users', { headers })
      if (res.ok) {
        const users: ManagedTechUser[] = await res.json()
        const techs = users.filter((u) => u.role === 'Technician')
        setAvailableTechnicians(techs)
        if (techs.length > 0 && !newAssignedTech) {
          setNewAssignedTech(techs[0].username)
        }
      }
    } catch {
      // Fallback default technicians
      setAvailableTechnicians([
        { username: 'tech_tom', role: 'Technician', assigned_sites: ['SITE-NORTH'] },
        { username: 'tech_other', role: 'Technician', assigned_sites: ['SITE-NORTH'] },
        { username: 'tech_dave', role: 'Technician', assigned_sites: ['SITE-01'] },
        { username: 'tech_sara', role: 'Technician', assigned_sites: ['SITE-01'] },
      ])
    }
  }, [currentUser, newAssignedTech])

  useEffect(() => {
    fetchWorkOrders()
    fetchTechnicians()
  }, [fetchWorkOrders, fetchTechnicians])

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
        body: JSON.stringify({ notes: `Accepted by ${currentUser?.username || 'user'}` }),
      })
      if (res.ok) {
        showToast(`Work Order ${woId} accepted. You may now begin work.`)
        await fetchWorkOrders()
        onRefreshData?.()
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to accept work order')
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
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to start work order')
      }
    } catch {
      showToast('Failed to start work order')
    }
  }

  // Confirm Reassign
  const handleConfirmReassign = async () => {
    if (!selectedWoForReassign || !targetTechUsername.trim()) return
    setIsReassigning(true)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch(`/api/v1/work-orders/${selectedWoForReassign.work_order_id}/reassign`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          assigned_to_user_id: targetTechUsername.trim(),
          notes: reassignNotes.trim() || undefined,
        }),
      })
      if (res.ok) {
        showToast(`Work Order ${selectedWoForReassign.work_order_id} reassigned to ${targetTechUsername}.`)
        setSelectedWoForReassign(null)
        setTargetTechUsername('')
        setReassignNotes('')
        await fetchWorkOrders()
        onRefreshData?.()
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to reassign work order')
      }
    } catch {
      showToast('Failed to reassign work order')
    } finally {
      setIsReassigning(false)
    }
  }

  // Create Work Order (Admin / Manager)
  const handleCreateWorkOrder = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMotorId.trim() || !newAssignedTech.trim() || !newTitle.trim()) return
    setIsSubmittingOrder(true)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const res = await fetch('/api/v1/work-orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          motor_id: newMotorId.trim(),
          assigned_to_user_id: newAssignedTech.trim(),
          priority: newPriority,
          title: newTitle.trim(),
          description: newDescription.trim() || 'Scheduled maintenance inspection and diagnostics.',
        }),
      })
      if (res.ok) {
        showToast(`Work order successfully created and assigned to ${newAssignedTech}.`)
        setIsCreateModalOpen(false)
        setNewTitle('')
        setNewDescription('')
        await fetchWorkOrders()
        onRefreshData?.()
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to create work order')
      }
    } catch {
      showToast('Failed to create work order')
    } finally {
      setIsSubmittingOrder(false)
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
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to reject work order')
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
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.detail || 'Failed to resolve work order')
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

  // Filtered work orders in UI
  const filteredWorkOrders = useMemo(() => {
    return workOrders.filter((wo) => {
      // Status filter
      if (statusFilter !== 'ALL' && wo.status !== statusFilter) return false
      // Priority filter
      if (priorityFilter !== 'ALL' && wo.priority !== priorityFilter) return false
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchId = wo.work_order_id.toLowerCase().includes(q)
        const matchMotor = wo.motor_id.toLowerCase().includes(q)
        const matchTitle = wo.title.toLowerCase().includes(q)
        const matchTech = (wo.assigned_to_user_id || '').toLowerCase().includes(q)
        if (!matchId && !matchMotor && !matchTitle && !matchTech) return false
      }
      return true
    })
  }, [workOrders, statusFilter, priorityFilter, searchQuery])

  if (!currentUser || !isAuthorized) {
    return (
      <div className="technician-container" style={{ padding: 'var(--space-6, 24px)' }}>
        <ErrorBanner
          message={
            currentUser
              ? `Access to the Work Order Workbench is restricted to authorized Technicians, Managers, and Administrators. You are currently logged in as ${currentUser.username} (${currentUser.role}).`
              : 'Authentication Required: Access to the Work Order Workbench is restricted to authorized Technicians, Managers, and Administrators.'
          }
          onRetry={onOpenLogin}
        />
      </div>
    )
  }

  const pendingOrders = filteredWorkOrders.filter((wo) => wo.status === 'Assigned')
  const activeOrders = filteredWorkOrders.filter(
    (wo) => wo.status === 'Accepted' || wo.status === 'In Progress'
  )
  const completedOrders = filteredWorkOrders.filter(
    (wo) => wo.status === 'Resolved' || wo.status === 'Rejected'
  )

  const isManagerOrAdmin = currentUser.role === 'Admin' || currentUser.role === 'Manager'

  const formatCleanTitle = (wo: WorkOrderItem) => {
    let t = wo.title || ''
    const p1 = `Maintenance on ${wo.motor_id}:`
    const p2 = `Maintenance on ${wo.motor_id}`
    if (t.startsWith(p1)) {
      t = t.substring(p1.length).trim()
    } else if (t.startsWith(p2)) {
      t = t.substring(p2.length).trim()
    }
    return t || 'Maintenance Required'
  }

  return (
    <div className="technician-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="manager-toast" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={15} color="var(--status-healthy)" /> {toastMessage}
        </div>
      )}

      {/* Header */}
      <PageHeader
        title={
          currentUser.role === 'Admin'
            ? 'Fleet Work Order Command Hub'
            : currentUser.role === 'Manager'
            ? 'Site Work Orders Queue'
            : `My Assigned Work Orders (${currentUser.username})`
        }
        subtitle={
          currentUser.role === 'Admin'
            ? 'Full fleet oversight: Monitor all technicians, dispatch work orders, reassign tickets, and track repair lifecycles across all plant facilities.'
            : currentUser.role === 'Manager'
            ? `Managing work orders for authorized sites (${currentUser.assigned_sites?.length ? currentUser.assigned_sites.join(', ') : 'All authorized sites'}). Reassign technicians and monitor maintenance.`
            : 'Personal maintenance inbox. Accept dispatched work orders, conduct physical repairs, and record replacement components.'
        }
        badge={
          <StatusBadge
            status="info"
            label={
              currentUser.role === 'Admin'
                ? 'FLEET DISPATCH'
                : currentUser.role === 'Manager'
                ? 'FACILITY QUEUE'
                : 'TECHNICIAN'
            }
            size="sm"
          />
        }
        actions={
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {isManagerOrAdmin && (
              <button
                className="btn-primary-glow"
                onClick={() => setIsCreateModalOpen(true)}
                style={{ fontSize: '12px', padding: '6px 14px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Plus size={13} /> Create Work Order
              </button>
            )}
            <button
              className="btn-secondary"
              onClick={fetchWorkOrders}
              disabled={isLoading}
              style={{ fontSize: '12px', padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <RotateCcw size={13} /> {isLoading ? 'Refreshing...' : 'Refresh Orders'}
            </button>
          </div>
        }
      />

      {/* KPI Metrics Cards */}
      <div className="work-orders-stats-grid" style={{ margin: '1rem 0 1.25rem' }}>
        <StatCard
          label="Total Orders"
          value={filteredWorkOrders.length}
          status="neutral"
          icon={<Wrench size={16} />}
          subtext="Fleet tickets in active scope"
        />
        <StatCard
          label="Pending Acceptance"
          value={pendingOrders.length}
          status={pendingOrders.length > 0 ? 'warning' : 'neutral'}
          icon={<Clock size={16} />}
          subtext="Dispatched to technicians"
        />
        <StatCard
          label="In Progress"
          value={activeOrders.length}
          status={activeOrders.length > 0 ? 'critical' : 'neutral'}
          icon={<Play size={16} />}
          subtext="Active physical interventions"
        />
        <StatCard
          label="Resolved / Closed"
          value={completedOrders.length}
          status="healthy"
          icon={<CheckCircle2 size={16} />}
          subtext="Sign-off verified repairs"
        />
      </div>

      {/* Filters and Controls Bar */}
      <div
        className="filter-controls-bar"
        style={{
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: 'var(--bg-card)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-main)',
        }}
      >
        <div style={{ flex: '1 1 200px', position: 'relative' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Search Work Order, Motor, Title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%', fontSize: '12px', paddingLeft: '28px' }}
          />
          <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        </div>

        <div>
          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ fontSize: '12px', padding: '6px 10px' }}
          >
            <option value="ALL">All Statuses</option>
            <option value="Assigned">Assigned (Awaiting Acceptance)</option>
            <option value="Accepted">Accepted</option>
            <option value="In Progress">In Progress</option>
            <option value="Resolved">Resolved</option>
            <option value="Rejected">Rejected</option>
          </select>
        </div>

        <div>
          <select
            className="form-select"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            style={{ fontSize: '12px', padding: '6px 10px' }}
          >
            <option value="ALL">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="URGENT">Urgent</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>

        {isManagerOrAdmin && availableTechnicians.length > 0 && (
          <div>
            <select
              className="form-select"
              value={technicianFilter}
              onChange={(e) => setTechnicianFilter(e.target.value)}
              style={{ fontSize: '12px', padding: '6px 10px' }}
            >
              <option value="ALL">All Technicians</option>
              {availableTechnicians.map((t) => (
                <option key={t.username} value={t.username}>
                  Tech: {t.username}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ── 1. ACTIVE / IN-PROGRESS ORDERS ── */}
      <div className="workbench-section-title">
        <span>
          {isManagerOrAdmin
            ? `Active In-Progress Repairs (${activeOrders.length})`
            : `My Active Repairs in Progress (${activeOrders.length})`}
        </span>
        <span className="badge priority-tag">{activeOrders.length} ACTIVE</span>
      </div>

      <div className="incidents-grid">
        {isLoading && workOrders.length === 0 ? (
          <LoadingSkeleton lines={3} height="120px" />
        ) : activeOrders.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 size={36} color="var(--status-healthy)" />}
            title={isManagerOrAdmin ? 'No Active Repairs In Progress' : 'No Active Interventions'}
            description={
              currentUser.role === 'Technician'
                ? 'Accept a pending dispatched work order below to begin physical repair.'
                : 'No technicians currently have active repairs in progress for the selected scope.'
            }
          />
        ) : (
          activeOrders.map((wo) => {
            const isAssignedToCurrent =
              wo.assigned_to_user_id === currentUser.username || (currentUser.id && wo.assigned_to === currentUser.id)

            return (
              <div
                key={wo.work_order_id}
                className={`incident-card ${wo.priority === 'CRITICAL' ? 'critical-border' : 'warning-border'}`}
              >
                <div className="incident-card-top">
                  <div className="incident-badge-group">
                    <StatusBadge
                      status={wo.status === 'In Progress' ? 'critical' : 'info'}
                      label={wo.status.toUpperCase()}
                      size="sm"
                    />
                    <span className="badge priority-tag">{wo.priority}</span>
                    {wo.site_id && (
                      <span className="badge" style={{ background: 'rgba(255,255,255,0.06)' }}>
                        {wo.site_id}
                      </span>
                    )}
                  </div>
                  <span className="incident-id">{wo.work_order_id}</span>
                </div>

                <div className="incident-motor-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span className="scada-equip-tag" style={{ fontSize: '11px', fontWeight: 600 }}>{wo.motor_id}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '13px' }}>{formatCleanTitle(wo)}</span>
                </div>

                {wo.description && wo.description !== wo.title && (
                  <div className="incident-message" style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {wo.description}
                  </div>
                )}

                <div className="tech-instructions-callout" style={{ padding: '8px 12px', fontSize: '11.5px', marginTop: '8px' }}>
                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', color: 'var(--text-secondary)' }}>
                    <span>Tech: <strong style={{ color: 'var(--text-main)' }}>{wo.assigned_to_user_id}</strong></span>
                    <span>By: <strong style={{ color: 'var(--text-main)' }}>{wo.assigned_by_user_id}</strong></span>
                    {wo.accepted_by && (
                      <span style={{ color: 'var(--status-healthy)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Check size={12} /> Accepted {wo.accepted_at ? `(${new Date(wo.accepted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})` : ''}
                      </span>
                    )}
                    {wo.reassigned_from_user_id && (
                      <span>Prior: <em>{wo.reassigned_from_user_id}</em></span>
                    )}
                  </div>
                </div>

                <div className="incident-card-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Technician Repair Actions (Only for assigned technician) */}
                  {isAssignedToCurrent && wo.status === 'Accepted' && (
                    <button
                      className="btn-primary-glow"
                      style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      onClick={() => handleStart(wo.work_order_id)}
                    >
                      <Play size={12} /> Begin Maintenance Work <ArrowRight size={12} />
                    </button>
                  )}
                  {isAssignedToCurrent && wo.status === 'In Progress' && (
                    <button
                      className="btn-complete-repair"
                      style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      onClick={() => setSelectedWoForRepair(wo)}
                    >
                      <Wrench size={12} /> Complete &amp; Sign Off Work Order <ArrowRight size={12} />
                    </button>
                  )}

                  {/* Admin / Manager Oversight & Reassign */}
                  {isManagerOrAdmin && (
                    <button
                      className="btn-secondary"
                      onClick={() => {
                        setSelectedWoForReassign(wo)
                        setTargetTechUsername('')
                      }}
                      title="Reassign to another technician"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                    >
                      <UserCheck size={13} /> Reassign Technician
                    </button>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* ── 2. NEW ASSIGNMENTS QUEUE ── */}
      <div className="workbench-section-title" style={{ marginTop: '2.5rem' }}>
        <span>
          {isManagerOrAdmin
            ? `Dispatched Orders Awaiting Technician Acceptance (${pendingOrders.length})`
            : `New Dispatched Work Orders Awaiting My Acceptance (${pendingOrders.length})`}
        </span>
        <span className="badge priority-tag">{pendingOrders.length} DISPATCHED</span>
      </div>

      <div className="incidents-grid">
        {isLoading && workOrders.length === 0 ? (
          <LoadingSkeleton lines={3} height="120px" />
        ) : pendingOrders.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 size={36} color="var(--status-healthy)" />}
            title={isManagerOrAdmin ? 'No Orders Awaiting Acceptance' : 'No Pending Work Orders'}
            description={
              isManagerOrAdmin
                ? 'All dispatched assignments have been acknowledged and accepted by technicians.'
                : 'You have acknowledged all work orders dispatched to your account.'
            }
          />
        ) : (
          pendingOrders.map((wo) => {
            const isAssignedToCurrent =
              wo.assigned_to_user_id === currentUser.username || (currentUser.id && wo.assigned_to === currentUser.id)

            return (
              <div
                key={wo.work_order_id}
                className={`incident-card ${wo.priority === 'CRITICAL' ? 'critical-border' : 'warning-border'}`}
              >
                <div className="incident-card-top">
                  <div className="incident-badge-group">
                    <StatusBadge
                      status="warning"
                      label="ASSIGNED"
                      size="sm"
                    />
                    <span className="badge priority-tag">{wo.priority}</span>
                    {wo.site_id && (
                      <span className="badge" style={{ background: 'rgba(255,255,255,0.06)' }}>
                        {wo.site_id}
                      </span>
                    )}
                  </div>
                  <span className="incident-id">{wo.work_order_id}</span>
                </div>

                <div className="incident-motor-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span className="scada-equip-tag" style={{ fontSize: '11px', fontWeight: 600 }}>{wo.motor_id}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '13px' }}>{formatCleanTitle(wo)}</span>
                </div>

                {wo.description && wo.description !== wo.title && (
                  <div className="incident-message" style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {wo.description}
                  </div>
                )}

                <div className="tech-instructions-callout" style={{ padding: '8px 12px', fontSize: '11.5px', marginTop: '8px' }}>
                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', color: 'var(--text-secondary)' }}>
                    <span>Assigned to: <strong style={{ color: 'var(--text-main)' }}>{wo.assigned_to_user_id}</strong></span>
                    <span>By: <strong style={{ color: 'var(--text-main)' }}>{wo.assigned_by_user_id}</strong></span>
                    {wo.reassigned_from_user_id && (
                      <span>Prior: <em>{wo.reassigned_from_user_id}</em></span>
                    )}
                  </div>
                </div>

                <div className="incident-card-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Technician Accept / Reject Buttons */}
                  {isAssignedToCurrent ? (
                    <>
                      <button
                        className="btn-primary-glow"
                        style={{ flex: 2, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        onClick={() => handleAccept(wo.work_order_id)}
                      >
                        <Check size={13} /> Accept Work Order
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ flex: 1, borderColor: 'var(--status-critical-border)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        onClick={() => setSelectedWoForReject(wo)}
                      >
                        <X size={13} /> Reject
                      </button>
                    </>
                  ) : (
                    /* Admin / Manager Oversight Indicator */
                    <div style={{ flex: 1, fontSize: '12px', color: 'var(--status-warning)', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <Clock size={13} /> Awaiting acceptance by: <strong>{wo.assigned_to_user_id}</strong>
                    </div>
                  )}

                  {/* Admin / Manager Reassign Action */}
                  {isManagerOrAdmin && (
                    <button
                      className="btn-secondary"
                      onClick={() => {
                        setSelectedWoForReassign(wo)
                        setTargetTechUsername('')
                      }}
                      title="Reassign to another technician"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                    >
                      <UserCheck size={13} /> Reassign Technician
                    </button>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* ── 3. COMPLETED MAINTENANCE AUDIT LOG ── */}
      {completedOrders.length > 0 && (
        <div style={{ marginTop: '2.5rem' }}>
          <div className="workbench-section-title">
            <span>
              {isManagerOrAdmin
                ? `Completed & Resolved Fleet Orders (${completedOrders.length})`
                : `My Completed Maintenance Log (${completedOrders.length})`}
            </span>
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
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {wo.status === 'Resolved' ? <Check size={14} /> : <X size={14} />}
                  </span>
                  <div>
                    <div className="log-title" style={{ fontSize: '12.5px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span className="scada-equip-tag" style={{ fontSize: '10.5px' }}>{wo.motor_id}</span>
                      <strong>{formatCleanTitle(wo)}</strong>
                      <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>({wo.work_order_id})</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>&bull; Tech: {wo.assigned_to_user_id}</span>
                    </div>
                    {wo.status === 'Resolved' ? (
                      <div className="log-notes" style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginTop: '3px' }}>
                        <span><strong>Diagnosis:</strong> {wo.diagnosis}</span> &bull;{' '}
                        <span><strong>Action:</strong> {wo.actions_taken}</span>
                        {wo.parts_replaced.length > 0 && (
                          <span> &bull; <strong>Parts:</strong> {wo.parts_replaced.join(', ')}</span>
                        )}
                        {wo.downtime_minutes ? (
                          <span> &bull; <strong>Downtime:</strong> {wo.downtime_minutes} min</span>
                        ) : null}
                      </div>
                    ) : (
                      <div className="log-notes text-critical" style={{ fontSize: '11.5px', marginTop: '3px' }}>
                        <strong>Rejection Reason:</strong> {wo.rejection_reason}
                      </div>
                    )}
                  </div>
                </div>
                <div className="log-time">
                  {wo.resolved_at
                    ? new Date(wo.resolved_at).toLocaleDateString()
                    : new Date(wo.updated_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── REASSIGN WORK ORDER MODAL ── */}
      {selectedWoForReassign && (
        <div className="modal-backdrop" onClick={() => setSelectedWoForReassign(null)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '500px' }}
          >
            <div className="modal-header">
              <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <UserCheck size={16} color="var(--brand-primary)" /> Reassign Work Order
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedWoForReassign(null)}
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '13px' }}>
                Reassign <strong>{selectedWoForReassign.work_order_id}</strong> on{' '}
                <code>{selectedWoForReassign.motor_id}</code> to another technician.
                The previous technician will no longer see this ticket.
              </p>

              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Current Assigned Technician</label>
                <input
                  type="text"
                  className="form-input"
                  value={selectedWoForReassign.assigned_to_user_id}
                  disabled
                  style={{ opacity: 0.7 }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">New Technician *</label>
                {availableTechnicians.length > 0 ? (
                  <select
                    className="form-select"
                    value={targetTechUsername}
                    onChange={(e) => setTargetTechUsername(e.target.value)}
                    style={{ width: '100%' }}
                  >
                    <option value="">-- Select Eligible Technician --</option>
                    {availableTechnicians
                      .filter((t) => t.username !== selectedWoForReassign.assigned_to_user_id)
                      .map((t) => (
                        <option key={t.username} value={t.username}>
                          {t.username} {t.assigned_sites?.length ? `(${t.assigned_sites.join(', ')})` : ''}
                        </option>
                      ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Enter technician username"
                    value={targetTechUsername}
                    onChange={(e) => setTargetTechUsername(e.target.value)}
                  />
                )}
              </div>

              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Reassignment Notes / Instructions</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  placeholder="e.g. Work shifted to morning crew; requires mechanical bearing overhaul"
                  value={reassignNotes}
                  onChange={(e) => setReassignNotes(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSelectedWoForReassign(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary-glow"
                  disabled={!targetTechUsername.trim() || isReassigning}
                  onClick={handleConfirmReassign}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {isReassigning ? 'Reassigning...' : 'Confirm Reassignment'}
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── CREATE WORK ORDER MODAL (Admin / Manager) ── */}
      {isCreateModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsCreateModalOpen(false)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '550px' }}
          >
            <div className="modal-header">
              <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Plus size={16} color="var(--brand-primary)" /> Create Maintenance Work Order
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setIsCreateModalOpen(false)}
              >
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateWorkOrder}>
              <div className="modal-body">
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Target Motor ID *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={newMotorId}
                    onChange={(e) => setNewMotorId(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Assign Technician *</label>
                  {availableTechnicians.length > 0 ? (
                    <select
                      className="form-select"
                      value={newAssignedTech}
                      onChange={(e) => setNewAssignedTech(e.target.value)}
                      required
                    >
                      <option value="">-- Select Technician --</option>
                      {availableTechnicians.map((t) => (
                        <option key={t.username} value={t.username}>
                          {t.username} {t.assigned_sites?.length ? `(${t.assigned_sites.join(', ')})` : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Technician username"
                      value={newAssignedTech}
                      onChange={(e) => setNewAssignedTech(e.target.value)}
                      required
                    />
                  )}
                </div>

                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Priority</label>
                  <select
                    className="form-select"
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as WorkOrderPriority)}
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="URGENT">Urgent</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Work Order Title *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Inspect bearing vibration on drive shaft"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Task Instructions / Description</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="Detailed inspection or repair steps for technician..."
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setIsCreateModalOpen(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-primary-glow"
                    disabled={isSubmittingOrder || !newTitle.trim() || !newAssignedTech.trim()}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    {isSubmittingOrder ? 'Dispatching...' : 'Dispatch Work Order'}
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── RESOLVE / SIGN-OFF MODAL ── */}
      {selectedWoForRepair && (
        <div className="modal-backdrop" onClick={() => setSelectedWoForRepair(null)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '640px' }}
          >
            <div className="modal-header">
              <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={16} color="var(--status-healthy)" /> Complete Work Order &amp; Sign Off
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedWoForRepair(null)}
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="alert-meta-card" style={{ marginBottom: '1rem' }}>
                <div>
                  <strong>Work Order:</strong> {selectedWoForRepair.work_order_id} &bull;{' '}
                  <strong>Motor:</strong> {selectedWoForRepair.motor_id}
                </div>
                <div style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {selectedWoForRepair.title}
                </div>
              </div>

              {/* Diagnosis */}
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Root Cause Diagnosis *</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="Identify root mechanical or electrical cause of anomaly..."
                />
              </div>

              {/* Actions Taken */}
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Corrective Actions Performed *</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={actionsTaken}
                  onChange={(e) => setActionsTaken(e.target.value)}
                  placeholder="Detail physical repair, torque specs, calibration steps..."
                />
              </div>

              {/* Spare Parts Checklist */}
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Components Replaced from Field Pool</label>
                <div className="parts-checklist-grid">
                  {COMMON_SPARE_PARTS.map((part) => (
                    <label key={part} className="part-checkbox-label">
                      <input
                        type="checkbox"
                        checked={partsSelected.includes(part)}
                        onChange={() => togglePart(part)}
                      />
                      <span>{part}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Downtime */}
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Total Equipment Downtime (minutes) *</label>
                <input
                  type="number"
                  className="form-input"
                  min={0}
                  value={downtimeMinutes}
                  onChange={(e) => setDowntimeMinutes(Number(e.target.value))}
                />
              </div>

              {/* Notes */}
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Post-Maintenance Verification Notes *</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Bench test results, sensor calibration verification..."
                />
              </div>

              {/* Actions */}
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
                  className="btn-complete-repair"
                  onClick={handleConfirmResolve}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  <Check size={13} /> Sign Off &amp; Close Work Order
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
              <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} color="var(--status-critical)" /> Reject Work Order
              </h3>
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
                  style={{ background: 'var(--status-critical)', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  onClick={handleConfirmReject}
                >
                  <X size={13} /> Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
