import { useState, useEffect, useCallback, useMemo, type FC } from 'react'
import {
  Users,
  UserPlus,
  Search,
  Filter,
  RefreshCw,
  Edit2,
  Power,
  Lock,
  CheckCircle,
  AlertCircle,
  X,
  Eye,
  EyeOff,
} from 'lucide-react'
import type { UserProfile, ManagedUser } from '../types'

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

  // Edit User Modal state
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null)
  const [editEmail, setEditEmail] = useState('')
  const [editRole, setEditRole] = useState<'Admin' | 'Manager' | 'Technician'>('Technician')
  const [editActive, setEditActive] = useState(true)
  const [editSites, setEditSites] = useState('')
  const [editMotors, setEditMotors] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const isAdmin = currentUser?.role === 'Admin'

  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [currentUser])

  // Fetch users from API
  const fetchUsers = useCallback(async () => {
    if (!isAdmin) return
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
  }, [isAdmin, getAuthHeaders])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  // Toggle user activation status
  const handleToggleStatus = async (user: ManagedUser) => {
    try {
      const newStatus = !user.is_active
      const res = await fetch(`/api/v1/auth/users/${user.id}/status`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ is_active: newStatus }),
      })
      if (res.ok) {
        setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, is_active: newStatus } : u)))
      } else {
        const err = await res.json().catch(() => ({}))
        alert(err.detail || 'Failed to update user status')
      }
    } catch {
      alert('Network error while toggling user status')
    }
  }

  // Create user submit
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
        setCreateSites('SITE-PLANT-A')
        setCreateMotors('')
        setTimeout(() => {
          setIsCreateOpen(false)
          setCreateSuccess(null)
          fetchUsers()
        }, 1200)
      } else {
        const err = await res.json().catch(() => ({}))
        const detail = Array.isArray(err.detail)
          ? err.detail.map((d: { msg?: string }) => d.msg).join(', ')
          : err.detail
        setCreateError(detail || `Failed to create user (HTTP ${res.status})`)
      }
    } catch {
      setCreateError('Network error: Unable to reach user registration endpoint')
    } finally {
      setCreatingUser(false)
    }
  }

  // Open edit modal
  const openEditModal = (user: ManagedUser) => {
    setEditingUser(user)
    setEditEmail(user.email)
    setEditRole(user.role)
    setEditActive(user.is_active)
    setEditSites((user.assigned_sites || []).join(', '))
    setEditMotors((user.assigned_motors || []).join(', '))
    setEditError(null)
  }

  // Save edit submit
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return
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

  // Authorization Guard
  if (!isAdmin) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-main)' }}>
        <div
          style={{
            maxWidth: '480px',
            margin: '0 auto',
            background: 'var(--bg-card, #0f172a)',
            padding: '32px',
            borderRadius: '12px',
            border: '1px solid rgba(239, 68, 68, 0.3)',
          }}
        >
          <Lock size={44} color="#ef4444" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 8px' }}>Admin Clearance Required</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, margin: '0 0 20px' }}>
            User identity management, role provisioning, and account lifecycle governance are strictly restricted to
            Administrator personnel.
          </p>
          {onOpenLogin && (
            <button
              onClick={onOpenLogin}
              style={{
                padding: '10px 20px',
                borderRadius: '8px',
                border: 'none',
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Sign In as Administrator
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="view-container" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
                background: 'linear-gradient(135deg, #3b82f6 0%, #1e40af 100%)',
                padding: '8px',
                borderRadius: '8px',
                display: 'flex',
              }}
            >
              <Users size={20} color="#fff" />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
              Workforce Identity &amp; RBAC Registry
            </h1>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 0 42px' }}>
            Admin-governed user creation, least-privilege scoping, and session lifecycle controls.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={fetchUsers}
            disabled={loading}
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid var(--border-main)',
              background: 'var(--bg-card, rgba(255,255,255,0.03))',
              color: 'var(--text-main)',
              fontSize: '12px',
              fontWeight: 500,
              cursor: loading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setIsCreateOpen(true)}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 4px 12px rgba(37,99,235,0.3)',
            }}
          >
            <UserPlus size={14} />
            <span>+ Provision User</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '16px',
        }}
      >
        <div className="measurement-card" style={{ padding: '16px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Registered Users
          </span>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
            {stats.total}
          </div>
          <span style={{ fontSize: '11px', color: '#38bdf8' }}>Active Plant Personnel</span>
        </div>

        <div className="measurement-card" style={{ padding: '16px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Active Managers
          </span>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
            {stats.managers}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Site-Scoped Operations</span>
        </div>

        <div className="measurement-card" style={{ padding: '16px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Active Technicians
          </span>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#f59e0b', marginTop: '4px' }}>
            {stats.technicians}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Field Service Specialists</span>
        </div>

        <div className="measurement-card" style={{ padding: '16px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Deactivated Accounts
          </span>
          <div style={{ fontSize: '24px', fontWeight: 800, color: stats.inactive > 0 ? '#ef4444' : 'var(--text-muted)', marginTop: '4px' }}>
            {stats.inactive}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Sessions Terminated</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="measurement-card"
        style={{
          padding: '14px 18px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1', minWidth: '260px' }}>
          <Search size={16} color="var(--text-muted)" />
          <input
            type="text"
            className="search-input-field"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search username, email, or site..."
            style={{ width: '100%', border: 'none', background: 'transparent', outline: 'none' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={13} color="var(--text-muted)" />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="search-input-field"
              style={{ padding: '6px 10px', fontSize: '12px' }}
            >
              <option value="ALL">All Roles</option>
              <option value="Admin">Admin</option>
              <option value="Manager">Manager</option>
              <option value="Technician">Technician</option>
            </select>
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="search-input-field"
            style={{ padding: '6px 10px', fontSize: '12px' }}
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active Only</option>
            <option value="INACTIVE">Deactivated Only</option>
          </select>
        </div>
      </div>

      {/* Error Message */}
      {errorMsg && (
        <div
          style={{
            padding: '12px 16px',
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: '#ef4444',
            borderRadius: '8px',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Users Table */}
      <div className="measurement-card" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-main)', background: 'rgba(255,255,255,0.02)' }}>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>USER</th>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>ROLE</th>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>STATUS</th>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>ASSIGNED SCOPE</th>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>REGISTERED</th>
                <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'right' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    {loading ? 'Loading user directory...' : 'No users match the search criteria.'}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const roleBadgeClass =
                    u.role === 'Admin'
                      ? 'badge-status healthy'
                      : u.role === 'Manager'
                      ? 'badge-status'
                      : 'badge-status warning'

                  return (
                    <tr
                      key={u.id}
                      style={{
                        borderBottom: '1px solid var(--border-main)',
                        opacity: u.is_active ? 1 : 0.6,
                        transition: 'background 0.15s',
                      }}
                    >
                      {/* User Info */}
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div
                            style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '50%',
                              background: u.is_active ? 'rgba(56, 189, 248, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                              color: u.is_active ? '#38bdf8' : '#94a3b8',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '12px',
                            }}
                          >
                            {u.username.substring(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{u.username}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{u.email}</div>
                          </div>
                        </div>
                      </td>

                      {/* Role */}
                      <td style={{ padding: '12px 16px' }}>
                        <span className={roleBadgeClass} style={{ fontSize: '11px', padding: '3px 8px' }}>
                          {u.role === 'Admin' && '👑 Admin'}
                          {u.role === 'Manager' && '👔 Manager'}
                          {u.role === 'Technician' && '🔧 Technician'}
                        </span>
                      </td>

                      {/* Status */}
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            fontWeight: 600,
                            background: u.is_active ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            color: u.is_active ? '#22c55e' : '#ef4444',
                            border: `1px solid ${u.is_active ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                          }}
                        >
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>

                      {/* Scope */}
                      <td style={{ padding: '12px 16px' }}>
                        {u.role === 'Admin' ? (
                          <span style={{ fontSize: '11px', color: '#a855f7', fontWeight: 600 }}>Unrestricted Global Fleet</span>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                            {u.assigned_sites && u.assigned_sites.length > 0 ? (
                              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                                <strong>Sites:</strong> {u.assigned_sites.join(', ')}
                              </div>
                            ) : (
                              <span style={{ fontSize: '11px', color: '#ef4444' }}>No sites assigned</span>
                            )}
                            {u.role === 'Technician' && u.assigned_motors && u.assigned_motors.length > 0 && (
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                <strong>Motors:</strong> {u.assigned_motors.join(', ')}
                              </div>
                            )}
                          </div>
                        )}
                      </td>

                      {/* Registration Date */}
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '12px' }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                      </td>

                      {/* Actions */}
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                          <button
                            onClick={() => openEditModal(u)}
                            style={{
                              padding: '5px 10px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-main)',
                              background: 'var(--bg-input, rgba(255,255,255,0.03))',
                              color: 'var(--text-main)',
                              fontSize: '11px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title="Edit User Role & Scope"
                          >
                            <Edit2 size={12} />
                            <span>Edit</span>
                          </button>

                          <button
                            onClick={() => handleToggleStatus(u)}
                            style={{
                              padding: '5px 10px',
                              borderRadius: '6px',
                              border: `1px solid ${u.is_active ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
                              background: u.is_active ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
                              color: u.is_active ? '#ef4444' : '#22c55e',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title={u.is_active ? 'Deactivate user session' : 'Activate user session'}
                          >
                            <Power size={12} />
                            <span>{u.is_active ? 'Deactivate' : 'Activate'}</span>
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
      </div>

      {/* CREATE USER MODAL */}
      {isCreateOpen && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setIsCreateOpen(false)}>
          <div
            className="rbac-login-modal"
            style={{ maxWidth: '520px', background: 'var(--bg-card, #0f172a)', borderRadius: '12px', padding: '24px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ background: '#2563eb', padding: '8px', borderRadius: '8px', display: 'flex' }}>
                  <UserPlus size={18} color="#fff" />
                </div>
                <div>
                  <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                    Provision New Plant Account
                  </h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Only Manager and Technician accounts can be provisioned.
                  </span>
                </div>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {createSuccess && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'rgba(34,197,94,0.1)',
                  border: '1px solid rgba(34,197,94,0.3)',
                  color: '#22c55e',
                  borderRadius: '8px',
                  fontSize: '13px',
                  marginBottom: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <CheckCircle size={16} />
                <span>{createSuccess}</span>
              </div>
            )}

            {createError && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                  borderRadius: '8px',
                  fontSize: '13px',
                  marginBottom: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={16} />
                <span>{createError}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Username
                </label>
                <input
                  type="text"
                  className="search-input-field"
                  value={createUsername}
                  onChange={(e) => setCreateUsername(e.target.value)}
                  placeholder="e.g. tech_davis or mgr_roberts"
                  minLength={3}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Work Email
                </label>
                <input
                  type="email"
                  className="search-input-field"
                  value={createEmail}
                  onChange={(e) => setCreateEmail(e.target.value)}
                  placeholder="e.g. user@plant.local"
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Temporary Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={createShowPassword ? 'text' : 'password'}
                    className="search-input-field"
                    value={createPassword}
                    onChange={(e) => setCreatePassword(e.target.value)}
                    placeholder="Min 8 chars, 1 uppercase, 1 digit"
                    minLength={8}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setCreateShowPassword(!createShowPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                    }}
                  >
                    {createShowPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Role Assignment
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setCreateRole('Technician')}
                    style={{
                      padding: '10px',
                      borderRadius: '8px',
                      border: `1px solid ${createRole === 'Technician' ? '#f59e0b' : 'var(--border-main)'}`,
                      background: createRole === 'Technician' ? 'rgba(245,158,11,0.1)' : 'transparent',
                      color: createRole === 'Technician' ? '#f59e0b' : 'var(--text-muted)',
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    🔧 Technician
                  </button>

                  <button
                    type="button"
                    onClick={() => setCreateRole('Manager')}
                    style={{
                      padding: '10px',
                      borderRadius: '8px',
                      border: `1px solid ${createRole === 'Manager' ? '#38bdf8' : 'var(--border-main)'}`,
                      background: createRole === 'Manager' ? 'rgba(56,189,248,0.1)' : 'transparent',
                      color: createRole === 'Manager' ? '#38bdf8' : 'var(--text-muted)',
                      fontWeight: 600,
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    👔 Manager
                  </button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Assigned Plant Sites (comma-separated)
                </label>
                <input
                  type="text"
                  className="search-input-field"
                  value={createSites}
                  onChange={(e) => setCreateSites(e.target.value)}
                  placeholder="e.g. SITE-PLANT-A, SITE-NORTH"
                  required={createRole === 'Manager'}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', display: 'block' }}>
                  {createRole === 'Manager'
                    ? 'Managers require explicit site assignments for fleet access in production.'
                    : 'Technicians can be scoped to specific sites or whole plant.'}
                </span>
              </div>

              {createRole === 'Technician' && (
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                    Assigned Motor IDs (optional, comma-separated)
                  </label>
                  <input
                    type="text"
                    className="search-input-field"
                    value={createMotors}
                    onChange={(e) => setCreateMotors(e.target.value)}
                    placeholder="e.g. MTR-775-001, MTR-775-002"
                  />
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  style={{
                    flex: '1',
                    padding: '10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-main)',
                    background: 'transparent',
                    color: 'var(--text-main)',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={creatingUser}
                  style={{
                    flex: '2',
                    padding: '10px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                    color: '#fff',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: creatingUser ? 'wait' : 'pointer',
                  }}
                >
                  {creatingUser ? 'Registering Account...' : 'Provision Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT USER MODAL */}
      {editingUser && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setEditingUser(null)}>
          <div
            className="rbac-login-modal"
            style={{ maxWidth: '480px', background: 'var(--bg-card, #0f172a)', borderRadius: '12px', padding: '24px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ background: '#3b82f6', padding: '8px', borderRadius: '8px', display: 'flex' }}>
                  <Edit2 size={16} color="#fff" />
                </div>
                <div>
                  <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                    Edit User: {editingUser.username}
                  </h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Modify contact email, active state, and plant site authorization.
                  </span>
                </div>
              </div>
              <button
                onClick={() => setEditingUser(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {editError && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                  borderRadius: '8px',
                  fontSize: '13px',
                  marginBottom: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={16} />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSaveEdit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Email Address
                </label>
                <input
                  type="email"
                  className="search-input-field"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Assigned Role
                </label>
                <select
                  className="search-input-field"
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value as 'Admin' | 'Manager' | 'Technician')}
                  disabled={editingUser.role === 'Admin'}
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
                {editingUser.role === 'Admin' && (
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', display: 'block' }}>
                    Admin accounts cannot be demoted through user management.
                  </span>
                )}
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Account Status
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-main)' }}>
                  <input
                    type="checkbox"
                    checked={editActive}
                    onChange={(e) => setEditActive(e.target.checked)}
                    style={{ accentColor: '#2563eb' }}
                  />
                  <span>User account is active</span>
                </label>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                  Assigned Sites (comma-separated)
                </label>
                <input
                  type="text"
                  className="search-input-field"
                  value={editSites}
                  onChange={(e) => setEditSites(e.target.value)}
                  placeholder="e.g. SITE-PLANT-A, SITE-NORTH"
                />
              </div>

              {editRole === 'Technician' && (
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', display: 'block', marginBottom: '6px' }}>
                    Assigned Motors (comma-separated)
                  </label>
                  <input
                    type="text"
                    className="search-input-field"
                    value={editMotors}
                    onChange={(e) => setEditMotors(e.target.value)}
                    placeholder="e.g. MTR-775-001, MTR-775-002"
                  />
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  style={{
                    flex: '1',
                    padding: '10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-main)',
                    background: 'transparent',
                    color: 'var(--text-main)',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={savingEdit}
                  style={{
                    flex: '2',
                    padding: '10px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                    color: '#fff',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: savingEdit ? 'wait' : 'pointer',
                  }}
                >
                  {savingEdit ? 'Saving Changes...' : 'Save Profile Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
