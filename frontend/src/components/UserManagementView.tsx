import { useState, useEffect, useCallback, useMemo, type FC } from 'react'
import {
  Users,
  UserPlus,
  Search,
  RefreshCw,
  Edit2,
  Power,
  Lock,
  CheckCircle,
  AlertCircle,
  X,
  Eye,
  EyeOff,
  Shield,
  KeyRound,
} from 'lucide-react'
import type { UserProfile, ManagedUser, WorkOrderItem } from '../types'

interface UserManagementViewProps {
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
}

export const UserManagementView: FC<UserManagementViewProps> = ({ currentUser, onOpenLogin }) => {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')

  // Navigation tab inside User Management: 'directory' | 'profile'
  const [activeSubTab, setActiveSubTab] = useState<'directory' | 'profile'>('directory')

  // Detailed User Inspection Modal
  const [inspectingUser, setInspectingUser] = useState<ManagedUser | null>(null)
  const [inspectingWorkOrders, setInspectingWorkOrders] = useState<WorkOrderItem[]>([])
  const [loadingUserWorkOrders, setLoadingUserWorkOrders] = useState(false)

  // Create User Modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [createUsername, setCreateUsername] = useState('')
  const [createEmail, setCreateEmail] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createShowPassword, setCreateShowPassword] = useState(false)
  const [createRole, setCreateRole] = useState<'Manager' | 'Technician'>('Technician')
  const [createSites, setCreateSites] = useState('SITE-PLANT-A')
  const [createMotors, setCreateMotors] = useState('')
  const [creatingUser, setCreatingUser] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)

  // Edit User Modal state (Admin only)
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null)
  const [editEmail, setEditEmail] = useState('')
  const [editRole, setEditRole] = useState<'Admin' | 'Manager' | 'Technician'>('Technician')
  const [editActive, setEditActive] = useState(true)
  const [editSites, setEditSites] = useState('')
  const [editMotors, setEditMotors] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  // Self-Profile Editing state (available to all roles)
  const [selfEmail, setSelfEmail] = useState(currentUser?.email || '')
  const [selfCurrentPassword, setSelfCurrentPassword] = useState('')
  const [selfShowCurrentPassword, setSelfShowCurrentPassword] = useState(false)
  const [selfNewPassword, setSelfNewPassword] = useState('')
  const [selfShowPassword, setSelfShowPassword] = useState(false)
  const [savingSelfProfile, setSavingSelfProfile] = useState(false)
  const [selfProfileSuccess, setSelfProfileSuccess] = useState<string | null>(null)
  const [selfProfileError, setSelfProfileError] = useState<string | null>(null)

  const isAdmin = currentUser?.role === 'Admin'
  const isManager = currentUser?.role === 'Manager'
  const isTechnician = currentUser?.role === 'Technician'
  const canViewDirectory = isAdmin || isManager

  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [currentUser])

  // Fetch users from API (Admin sees all, Manager sees site-scoped users)
  const fetchUsers = useCallback(async () => {
    if (!canViewDirectory) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await fetch('/api/v1/auth/users', { credentials: 'include', headers: getAuthHeaders() })
      if (res.ok) {
        const data = await res.json()
        setUsers(data)
      } else {
        const err = await res.json().catch(() => ({}))
        setErrorMsg(err.detail || `Failed to fetch users (HTTP ${res.status})`)
      }
    } catch {
      setErrorMsg('Network error: Unable to contact user management service')
    } finally {
      setLoading(false)
    }
  }, [canViewDirectory, getAuthHeaders])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  // Sync self profile state when currentUser changes
  useEffect(() => {
    if (currentUser?.email) {
      setSelfEmail(currentUser.email)
    }
  }, [currentUser])

  // Fetch user work orders when inspecting
  useEffect(() => {
    if (!inspectingUser) {
      setInspectingWorkOrders([])
      return
    }
    let isSubscribed = true
    setLoadingUserWorkOrders(true)
    fetch(`/api/v1/work-orders?assigned_to=${encodeURIComponent(inspectingUser.username)}`, {
      headers: getAuthHeaders(),
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (isSubscribed && Array.isArray(data)) {
          setInspectingWorkOrders(data)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isSubscribed) setLoadingUserWorkOrders(false)
      })

    return () => {
      isSubscribed = false
    }
  }, [inspectingUser, getAuthHeaders])

  // Toggle user activation status (Admin only)
  const handleToggleStatus = async (user: ManagedUser) => {
    if (!isAdmin) return
    try {
      const newStatus = !user.is_active
      const res = await fetch(`/api/v1/auth/users/${user.id}/status`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ is_active: newStatus }),
      })
      if (res.ok) {
        setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, is_active: newStatus } : u)))
        if (inspectingUser && inspectingUser.id === user.id) {
          setInspectingUser({ ...inspectingUser, is_active: newStatus })
        }
      } else {
        const err = await res.json().catch(() => ({}))
        alert(err.detail || 'Failed to update user status')
      }
    } catch {
      alert('Network error while toggling user status')
    }
  }

  // Create user submit (Admin only)
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isAdmin) return
    setCreatingUser(true)
    setCreateError(null)
    setCreateSuccess(null)

    const sites = createSites
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const motors = createMotors
      .split(',')
      .map((m) => m.trim())
      .filter(Boolean)

    try {
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          username: createUsername.trim(),
          email: createEmail.trim(),
          password: createPassword,
          role: createRole,
          assigned_sites: sites,
          assigned_motors: motors,
        }),
      })

      if (res.ok) {
        setCreateSuccess(`Account '${createUsername.trim()}' successfully registered as ${createRole}!`)
        setCreateUsername('')
        setCreateEmail('')
        setCreatePassword('')
        setCreateMotors('')
        fetchUsers()
        setTimeout(() => setIsCreateOpen(false), 1200)
      } else {
        const err = await res.json().catch(() => ({}))
        setCreateError(err.detail || 'Failed to register account')
      }
    } catch {
      setCreateError('Network error while communicating with auth gateway')
    } finally {
      setCreatingUser(false)
    }
  }

  // Open edit modal for user
  const handleStartEdit = (user: ManagedUser) => {
    setEditingUser(user)
    setEditEmail(user.email)
    setEditRole(user.role)
    setEditActive(user.is_active)
    setEditSites((user.assigned_sites || []).join(', '))
    setEditMotors((user.assigned_motors || []).join(', '))
    setEditError(null)
  }

  // Save edit user (Admin only)
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser || !isAdmin) return
    setSavingEdit(true)
    setEditError(null)

    const sites = editSites
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const motors = editMotors
      .split(',')
      .map((m) => m.trim())
      .filter(Boolean)

    try {
      const res = await fetch(`/api/v1/auth/users/${editingUser.id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          email: editEmail.trim(),
          role: editRole,
          is_active: editActive,
          assigned_sites: sites,
          assigned_motors: motors,
        }),
      })

      if (res.ok) {
        const updated = await res.json()
        setUsers((prev) => prev.map((u) => (u.id === editingUser.id ? updated : u)))
        if (inspectingUser && inspectingUser.id === editingUser.id) {
          setInspectingUser(updated)
        }
        setEditingUser(null)
      } else {
        const err = await res.json().catch(() => ({}))
        setEditError(err.detail || 'Failed to update user')
      }
    } catch {
      setEditError('Network error while saving user profile')
    } finally {
      setSavingEdit(false)
    }
  }

  // Self-profile update (All authenticated roles)
  const handleSaveSelfProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSavingSelfProfile(true)
    setSelfProfileError(null)
    setSelfProfileSuccess(null)

    const payload: { email?: string; current_password?: string; password?: string } = {}
    if (selfEmail.trim()) payload.email = selfEmail.trim()
    if (selfNewPassword.trim()) {
      payload.password = selfNewPassword.trim()
      payload.current_password = selfCurrentPassword
    }

    try {
      const res = await fetch('/api/v1/auth/me', {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        const updated = await res.json()
        setSelfProfileSuccess('Profile successfully updated! New credentials are now active.')
        setSelfNewPassword('')
        setSelfCurrentPassword('')
        // Update local session info
        try {
          const stored = localStorage.getItem('motorguard_auth_user')
          if (stored) {
            const parsed = JSON.parse(stored)
            parsed.email = updated.email
            localStorage.setItem('motorguard_auth_user', JSON.stringify(parsed))
          }
        } catch {}
      } else {
        const err = await res.json().catch(() => ({}))
        setSelfProfileError(err.detail || 'Failed to update profile')
      }
    } catch {
      setSelfProfileError('Network error updating self profile')
    } finally {
      setSavingSelfProfile(false)
    }
  }

  // Filtered users
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const q = searchQuery.toLowerCase()
      const matchesSearch =
        u.username.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        (u.assigned_sites || []).some((s) => s.toLowerCase().includes(q))

      const matchesRole = roleFilter === 'ALL' || u.role === roleFilter
      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'ACTIVE' && u.is_active) ||
        (statusFilter === 'INACTIVE' && !u.is_active)

      return matchesSearch && matchesRole && matchesStatus
    })
  }, [users, searchQuery, roleFilter, statusFilter])

  // Aggregate stats
  const stats = useMemo(() => {
    const total = users.length
    const managers = users.filter((u) => u.role === 'Manager' && u.is_active).length
    const technicians = users.filter((u) => u.role === 'Technician' && u.is_active).length
    const inactive = users.filter((u) => !u.is_active).length
    return { total, managers, technicians, inactive }
  }, [users])

  // Not logged in guard
  if (!currentUser) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-main)' }}>
        <div
          style={{
            maxWidth: '480px',
            margin: '0 auto',
            background: 'var(--bg-card)',
            padding: '32px',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-main)',
            boxShadow: 'var(--shadow-md)',
          }}
        >
          <Lock size={44} color="var(--brand-primary)" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 8px' }}>Authentication Required</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, margin: '0 0 20px' }}>
            Workforce directory and user management requires an authenticated session.
          </p>
          {onOpenLogin && (
            <button onClick={onOpenLogin} className="btn-primary" style={{ padding: '8px 18px', fontSize: '13px' }}>
              Sign In to MotorGuard
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="view-container" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                background: 'var(--brand-primary)',
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                color: '#fff',
              }}
            >
              <Users size={18} />
            </div>
            <div>
              <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                {isAdmin ? 'Workforce Identity & RBAC Registry' : isManager ? 'Plant Personnel Directory' : 'User Account & Profile'}
              </h1>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                {isAdmin
                  ? 'Admin-governed user creation, least-privilege scoping, and session lifecycle controls.'
                  : isManager
                  ? `Authorized site personnel management for sites: ${(currentUser?.assigned_sites || []).join(', ') || 'Assigned Plants'}`
                  : 'Manage personal credentials, review role permissions, and view assigned plant assets.'}
              </p>
            </div>
          </div>
        </div>

        {/* Tab switch & Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {canViewDirectory && (
            <div
              style={{
                display: 'flex',
                background: 'var(--bg-subtle)',
                padding: '2px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-main)',
              }}
            >
              <button
                onClick={() => setActiveSubTab('directory')}
                className={`btn-action-ghost ${activeSubTab === 'directory' ? 'active' : ''}`}
                style={{
                  padding: '5px 12px',
                  fontSize: '11px',
                  fontWeight: 600,
                  background: activeSubTab === 'directory' ? 'var(--bg-panel)' : 'transparent',
                }}
              >
                <Users size={13} style={{ marginRight: 4 }} />
                Team Directory
              </button>
              <button
                onClick={() => setActiveSubTab('profile')}
                className={`btn-action-ghost ${activeSubTab === 'profile' ? 'active' : ''}`}
                style={{
                  padding: '5px 12px',
                  fontSize: '11px',
                  fontWeight: 600,
                  background: activeSubTab === 'profile' ? 'var(--bg-panel)' : 'transparent',
                }}
              >
                <KeyRound size={13} style={{ marginRight: 4 }} />
                My Account Settings
              </button>
            </div>
          )}

          {canViewDirectory && (
            <button
              onClick={fetchUsers}
              disabled={loading}
              className="btn-action-ghost"
              style={{ padding: '6px 12px', fontSize: '11.5px' }}
            >
              <RefreshCw size={13} className={loading ? 'spin' : ''} style={{ marginRight: 4 }} />
              Refresh
            </button>
          )}

          {isAdmin && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="btn-primary"
              style={{ padding: '6px 14px', fontSize: '11.5px' }}
            >
              <UserPlus size={13} style={{ marginRight: 6 }} />
              Provision User
            </button>
          )}
        </div>
      </div>

      {/* Technician / Non-Directory View (Direct Self Profile View) */}
      {(!canViewDirectory || activeSubTab === 'profile') && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px' }}>
          {/* Self Profile Form */}
          <div className="card" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px', color: 'var(--text-main)' }}>
              My Profile & Credentials
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '0 0 20px' }}>
              Update your verified email address or rotate your account login password.
            </p>

            {selfProfileSuccess && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'var(--status-healthy-bg)',
                  border: '1px solid var(--status-healthy-border)',
                  color: 'var(--status-healthy)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <CheckCircle size={15} />
                <span>{selfProfileSuccess}</span>
              </div>
            )}

            {selfProfileError && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'var(--status-critical-bg)',
                  border: '1px solid var(--status-critical-border)',
                  color: 'var(--status-critical)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={15} />
                <span>{selfProfileError}</span>
              </div>
            )}

            <form onSubmit={handleSaveSelfProfile} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Account Username (Immutable)
                </label>
                <input
                  type="text"
                  value={currentUser.username}
                  disabled
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-main)',
                    background: 'var(--bg-subtle)',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12.5px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Contact Email Address
                </label>
                <input
                  type="email"
                  value={selfEmail}
                  onChange={(e) => setSelfEmail(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-main)',
                    background: 'var(--bg-panel)',
                    color: 'var(--text-main)',
                    fontSize: '12.5px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Current Password (Required to change password)
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={selfShowCurrentPassword ? 'text' : 'password'}
                    value={selfCurrentPassword}
                    onChange={(e) => setSelfCurrentPassword(e.target.value)}
                    placeholder="Enter current password"
                    style={{
                      width: '100%',
                      padding: '8px 36px 8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-main)',
                      background: 'var(--bg-panel)',
                      color: 'var(--text-main)',
                      fontSize: '12.5px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setSelfShowCurrentPassword(!selfShowCurrentPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {selfShowCurrentPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Change Password (Leave blank to keep existing)
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={selfShowPassword ? 'text' : 'password'}
                    value={selfNewPassword}
                    onChange={(e) => setSelfNewPassword(e.target.value)}
                    placeholder="Min 8 characters, uppercase, digit & special"
                    style={{
                      width: '100%',
                      padding: '8px 36px 8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-main)',
                      background: 'var(--bg-panel)',
                      color: 'var(--text-main)',
                      fontSize: '12.5px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setSelfShowPassword(!selfShowPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {selfShowPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
                <button type="submit" disabled={savingSelfProfile} className="btn-primary" style={{ padding: '8px 20px' }}>
                  {savingSelfProfile ? 'Updating Credentials...' : 'Save Profile Changes'}
                </button>
              </div>
            </form>
          </div>

          {/* Account Metadata & Privileges Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                <Shield size={18} color="var(--brand-primary)" />
                <h4 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>RBAC Clearance Profile</h4>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Security Role:</span>
                  <span className="badge-info" style={{ fontWeight: 700 }}>{currentUser.role.toUpperCase()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Account Status:</span>
                  <span style={{ color: 'var(--status-healthy)', fontWeight: 600 }}>Active // Authenticated</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Assigned Sites:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {(currentUser.assigned_sites || []).join(', ') || 'Global'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Assigned Motors:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {(currentUser.assigned_motors || []).join(', ') || 'All Fleet'}
                  </span>
                </div>
              </div>
            </div>

            {isTechnician && (
              <div className="card" style={{ padding: '16px', background: 'var(--bg-subtle)' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <AlertCircle size={16} color="var(--brand-primary)" style={{ flexShrink: 0, marginTop: 2 }} />
                  <p style={{ fontSize: '11.5px', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
                    <strong>Technician Notice:</strong> Workforce provisioning and administrative roster modifications are governed by Site Managers and Systems Administrators.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Team Directory (Admin & Manager) */}
      {canViewDirectory && activeSubTab === 'directory' && (
        <>
          {/* Quick Metrics Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
            <div className="card" style={{ padding: '14px 18px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>TOTAL PERSONNEL</div>
              <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '4px' }}>{stats.total}</div>
            </div>
            <div className="card" style={{ padding: '14px 18px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>OPERATIONAL MANAGERS</div>
              <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '4px', color: 'var(--brand-primary)' }}>{stats.managers}</div>
            </div>
            <div className="card" style={{ padding: '14px 18px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>FIELD TECHNICIANS</div>
              <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '4px', color: 'var(--status-healthy)' }}>{stats.technicians}</div>
            </div>
            <div className="card" style={{ padding: '14px 18px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>SUSPENDED / INACTIVE</div>
              <div style={{ fontSize: '20px', fontWeight: 800, marginTop: '4px', color: stats.inactive > 0 ? 'var(--status-critical)' : 'var(--text-muted)' }}>
                {stats.inactive}
              </div>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="card" style={{ padding: '12px 16px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1', minWidth: '220px' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search by username, email, or site..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 10px 6px 32px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-main)',
                  background: 'var(--bg-app)',
                  color: 'var(--text-main)',
                  fontSize: '12px',
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>ROLE:</span>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                style={{
                  padding: '5px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-main)',
                  background: 'var(--bg-panel)',
                  fontSize: '11.5px',
                  color: 'var(--text-main)',
                  cursor: 'pointer',
                }}
              >
                <option value="ALL">All Roles</option>
                <option value="Admin">Admin</option>
                <option value="Manager">Manager</option>
                <option value="Technician">Technician</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>STATUS:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: '5px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-main)',
                  background: 'var(--bg-panel)',
                  fontSize: '11.5px',
                  color: 'var(--text-main)',
                  cursor: 'pointer',
                }}
              >
                <option value="ALL">All Status</option>
                <option value="ACTIVE">Active Only</option>
                <option value="INACTIVE">Inactive Only</option>
              </select>
            </div>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div
              style={{
                padding: '12px 16px',
                background: 'var(--status-critical-bg)',
                border: '1px solid var(--status-critical-border)',
                color: 'var(--status-critical)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '12.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* User Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-main)' }}>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px' }}>USER</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px' }}>ROLE</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px' }}>ASSIGNED SITES</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px' }}>STATUS</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px' }}>CREATED</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px', textAlign: 'right' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <RefreshCw size={18} className="spin" style={{ margin: '0 auto 8px' }} />
                      <div>Loading personnel roster...</div>
                    </td>
                  </tr>
                ) : filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No personnel match the selected criteria.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((u) => (
                    <tr
                      key={u.id}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        transition: 'background 0.15s ease',
                      }}
                      className="hover-row"
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '50%',
                              background: 'var(--bg-subtle)',
                              border: '1px solid var(--border-main)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '11px',
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--text-main)',
                            }}
                          >
                            {u.username.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{u.username}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{u.email}</div>
                          </div>
                        </div>
                      </td>

                      <td style={{ padding: '12px 16px' }}>
                        <span
                          className={`status-pill ${
                            u.role === 'Admin' ? 'badge-primary' : u.role === 'Manager' ? 'badge-info' : 'badge-neutral'
                          }`}
                          style={{ fontSize: '10.5px', fontWeight: 600 }}
                        >
                          {u.role}
                        </span>
                      </td>

                      <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        {(u.assigned_sites || []).length > 0 ? (
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                            {u.assigned_sites.map((s) => (
                              <span
                                key={s}
                                style={{
                                  background: 'var(--bg-subtle)',
                                  padding: '2px 6px',
                                  borderRadius: '3px',
                                  border: '1px solid var(--border-main)',
                                }}
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>None / Unscoped</span>
                        )}
                      </td>

                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            fontSize: '11.5px',
                            fontWeight: 600,
                            color: u.is_active ? 'var(--status-healthy)' : 'var(--status-critical)',
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: u.is_active ? 'var(--status-healthy)' : 'var(--status-critical)',
                            }}
                          />
                          {u.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </td>

                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '11.5px' }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}
                      </td>

                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          <button
                            onClick={() => setInspectingUser(u)}
                            className="btn-action-ghost"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Inspect User Details & Activity"
                          >
                            Details
                          </button>

                          {isAdmin && (
                            <>
                              <button
                                onClick={() => handleStartEdit(u)}
                                className="btn-action-ghost"
                                style={{ padding: '4px 8px', fontSize: '11px' }}
                                title="Edit Role & Scopes"
                              >
                                <Edit2 size={12} />
                              </button>

                              <button
                                onClick={() => handleToggleStatus(u)}
                                className="btn-action-ghost"
                                style={{
                                  padding: '4px 8px',
                                  fontSize: '11px',
                                  color: u.is_active ? 'var(--status-critical)' : 'var(--status-healthy)',
                                }}
                                title={u.is_active ? 'Suspend Account' : 'Activate Account'}
                              >
                                <Power size={12} />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* USER DETAIL INSPECTION MODAL */}
      {inspectingUser && (
        <div className="modal-backdrop">
          <div className="modal-dialog" style={{ maxWidth: '620px' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'var(--brand-primary)',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {inspectingUser.username.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                    {inspectingUser.username}
                  </h3>
                  <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                    {inspectingUser.email} // ID: {inspectingUser.id}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setInspectingUser(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Identity & Scope Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  background: 'var(--bg-subtle)',
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12px',
                }}
              >
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>ROLE CLEARANCE</div>
                  <div style={{ fontWeight: 700, marginTop: 2 }}>{inspectingUser.role.toUpperCase()}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>ACCOUNT STATE</div>
                  <div style={{ fontWeight: 700, marginTop: 2, color: inspectingUser.is_active ? 'var(--status-healthy)' : 'var(--status-critical)' }}>
                    {inspectingUser.is_active ? 'ACTIVE // IN GOOD STANDING' : 'SUSPENDED // ACCESS REVOKED'}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>ASSIGNED SITES</div>
                  <div style={{ fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {(inspectingUser.assigned_sites || []).join(', ') || 'Global'}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>ASSIGNED MOTORS</div>
                  <div style={{ fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {(inspectingUser.assigned_motors || []).join(', ') || 'All Fleet'}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>REGISTERED DATE</div>
                  <div style={{ marginTop: 2 }}>
                    {inspectingUser.created_at ? new Date(inspectingUser.created_at).toLocaleString() : 'N/A'}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '10.5px' }}>LAST LOGIN SESSION</div>
                  <div style={{ marginTop: 2 }}>
                    {inspectingUser.last_login_at ? new Date(inspectingUser.last_login_at).toLocaleString() : 'Never logged in'}
                  </div>
                </div>
              </div>

              {/* Assigned Work Orders Section */}
              <div>
                <h4 style={{ fontSize: '13px', fontWeight: 700, margin: '0 0 8px', color: 'var(--text-main)' }}>
                  Assigned Maintenance Work Orders
                </h4>
                {loadingUserWorkOrders ? (
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>Loading assigned tickets...</div>
                ) : inspectingWorkOrders.length === 0 ? (
                  <div
                    style={{
                      padding: '12px',
                      background: 'var(--bg-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '11.5px',
                      color: 'var(--text-muted)',
                      textAlign: 'center',
                    }}
                  >
                    No open or active work orders assigned to this personnel.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
                    {inspectingWorkOrders.map((wo) => (
                      <div
                        key={wo.work_order_id}
                        style={{
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border-main)',
                          background: 'var(--bg-panel)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          fontSize: '11.5px',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600 }}>{wo.title}</div>
                          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {wo.work_order_id} // MOTOR: {wo.motor_id}
                          </div>
                        </div>
                        <span
                          className={`status-pill ${
                            wo.status === 'Resolved' ? 'badge-primary' : wo.status === 'In Progress' ? 'badge-info' : 'badge-warning'
                          }`}
                          style={{ fontSize: '10px' }}
                        >
                          {wo.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between' }}>
              {isAdmin && (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => {
                      handleStartEdit(inspectingUser)
                      setInspectingUser(null)
                    }}
                    className="btn-action-ghost"
                    style={{ fontSize: '11.5px' }}
                  >
                    <Edit2 size={13} style={{ marginRight: 4 }} /> Edit Scopes
                  </button>
                  <button
                    onClick={() => handleToggleStatus(inspectingUser)}
                    className="btn-action-ghost"
                    style={{
                      fontSize: '11.5px',
                      color: inspectingUser.is_active ? 'var(--status-critical)' : 'var(--status-healthy)',
                    }}
                  >
                    <Power size={13} style={{ marginRight: 4 }} />
                    {inspectingUser.is_active ? 'Suspend Account' : 'Activate Account'}
                  </button>
                </div>
              )}
              <button onClick={() => setInspectingUser(null)} className="btn-primary" style={{ fontSize: '11.5px' }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE USER MODAL (Admin Only) */}
      {isCreateOpen && (
        <div className="modal-backdrop">
          <div className="modal-dialog" style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>Provision New Workforce Account</h3>
              <button
                onClick={() => setIsCreateOpen(false)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {createSuccess && (
                  <div style={{ padding: '8px 12px', background: 'var(--status-healthy-bg)', color: 'var(--status-healthy)', borderRadius: '4px', fontSize: '12px' }}>
                    {createSuccess}
                  </div>
                )}
                {createError && (
                  <div style={{ padding: '8px 12px', background: 'var(--status-critical-bg)', color: 'var(--status-critical)', borderRadius: '4px', fontSize: '12px' }}>
                    {createError}
                  </div>
                )}

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Username</label>
                  <input
                    type="text"
                    required
                    value={createUsername}
                    onChange={(e) => setCreateUsername(e.target.value)}
                    placeholder="e.g. tech_davis"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Email</label>
                  <input
                    type="email"
                    required
                    value={createEmail}
                    onChange={(e) => setCreateEmail(e.target.value)}
                    placeholder="davis@plant.local"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Initial Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={createShowPassword ? 'text' : 'password'}
                      required
                      value={createPassword}
                      onChange={(e) => setCreatePassword(e.target.value)}
                      placeholder="Min 8 chars, 1 digit, 1 special"
                      style={{ width: '100%', padding: '7px 32px 7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setCreateShowPassword(!createShowPassword)}
                      style={{
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        border: 'none',
                        background: 'transparent',
                        cursor: 'pointer',
                        color: 'var(--text-muted)',
                      }}
                    >
                      {createShowPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Role</label>
                  <select
                    value={createRole}
                    onChange={(e) => setCreateRole(e.target.value as 'Manager' | 'Technician')}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  >
                    <option value="Technician">Technician</option>
                    <option value="Manager">Manager</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Assigned Sites</label>
                  <input
                    type="text"
                    value={createSites}
                    onChange={(e) => setCreateSites(e.target.value)}
                    placeholder="e.g. SITE-PLANT-A, SITE-NORTH"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  />
                </div>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" onClick={() => setIsCreateOpen(false)} className="btn-action-ghost" style={{ fontSize: '12px' }}>
                  Cancel
                </button>
                <button type="submit" disabled={creatingUser} className="btn-primary" style={{ fontSize: '12px' }}>
                  {creatingUser ? 'Provisioning...' : 'Provision Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT USER MODAL (Admin Only) */}
      {editingUser && (
        <div className="modal-backdrop">
          <div className="modal-dialog" style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>Edit User: {editingUser.username}</h3>
              <button
                onClick={() => setEditingUser(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveEdit}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {editError && (
                  <div style={{ padding: '8px 12px', background: 'var(--status-critical-bg)', color: 'var(--status-critical)', borderRadius: '4px', fontSize: '12px' }}>
                    {editError}
                  </div>
                )}

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Email</label>
                  <input
                    type="email"
                    required
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Role</label>
                  <select
                    value={editRole}
                    onChange={(e) => setEditRole(e.target.value as 'Admin' | 'Manager' | 'Technician')}
                    disabled={editingUser.role === 'Admin'}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  >
                    {editingUser.role === 'Admin' ? (
                      <option value="Admin">Admin</option>
                    ) : (
                      <>
                        <option value="Manager">Manager</option>
                        <option value="Technician">Technician</option>
                      </>
                    )}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Assigned Sites</label>
                  <input
                    type="text"
                    value={editSites}
                    onChange={(e) => setEditSites(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '4px', border: '1px solid var(--border-main)', background: 'var(--bg-app)', fontSize: '12px' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px' }}>
                    <input
                      type="checkbox"
                      checked={editActive}
                      onChange={(e) => setEditActive(e.target.checked)}
                      style={{ accentColor: 'var(--brand-primary)' }}
                    />
                    <span>Account is Active</span>
                  </label>
                </div>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" onClick={() => setEditingUser(null)} className="btn-action-ghost" style={{ fontSize: '12px' }}>
                  Cancel
                </button>
                <button type="submit" disabled={savingEdit} className="btn-primary" style={{ fontSize: '12px' }}>
                  {savingEdit ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
