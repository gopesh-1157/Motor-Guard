import { useState, useEffect, useRef } from 'react'
import type { FC } from 'react'
import { animate, stagger } from 'animejs'
import type { UserProfile, UserRole } from '../types'

interface RBACLoginModalProps {
  isOpen: boolean
  onClose: () => void
  onLoginSuccess: (user: UserProfile) => void
  currentUser: UserProfile | null
  onLogout?: () => void
}

interface PersonaInfo {
  username: string
  password: string
  role: UserRole
  title: string
  clearanceLevel: number
  badgeColor: string
  icon: string
  permissions: string[]
}

const DEMO_PERSONAS: PersonaInfo[] = [
  {
    username: 'admin',
    password: 'admin123',
    role: 'Admin',
    title: 'System Administrator',
    clearanceLevel: 4,
    badgeColor: '#a855f7',
    icon: '👑',
    permissions: ['Full SCADA Oversight', 'Dispatch Critical Alarms', 'Execute & Sign-Off Repairs', 'User Provisioning & Audit'],
  },
  {
    username: 'manager_alice',
    password: 'manager123',
    role: 'Manager',
    title: 'Operations Plant Manager',
    clearanceLevel: 3,
    badgeColor: '#3b82f6',
    icon: '👔',
    permissions: ['Fleet SCADA Oversight', 'Incident Dispatch Hub', 'Assign Technicians & Priority', 'Review Service Logs'],
  },
  {
    username: 'tech_dave',
    password: 'tech123',
    role: 'Technician',
    title: 'Senior Field Technician',
    clearanceLevel: 2,
    badgeColor: '#10b981',
    icon: '🔧',
    permissions: ['Technician Workbench', 'Inspect Pre-Failure Telemetry', 'Log Replaced Spare Parts', 'Sign-Off & Resolve Alarms'],
  },
  {
    username: 'tech_sara',
    password: 'tech123',
    role: 'Technician',
    title: 'TinyML Diagnostics Specialist',
    clearanceLevel: 2,
    badgeColor: '#06b6d4',
    icon: '🔬',
    permissions: ['Technician Workbench', 'Edge Impulse Inference Review', 'Vibration Spectrum Analysis', 'Sign-Off & Resolve Alarms'],
  },
  {
    username: 'operator_bob',
    password: 'operator123',
    role: 'Operator',
    title: 'Line Floor SCADA Operator',
    clearanceLevel: 1,
    badgeColor: '#f59e0b',
    icon: '🏭',
    permissions: ['Plant Floor SCADA Telemetry', 'Live SVG Sparkline Monitoring', '3D Digital Twin Viewer', 'Read-Only Alarm Ticker'],
  },
]

export const RBACLoginModal: FC<RBACLoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
  currentUser,
  onLogout,
}) => {
  const [selectedPersona, setSelectedPersona] = useState<PersonaInfo>(DEMO_PERSONAS[1]) // Default to Manager Alice
  const [username, setUsername] = useState(DEMO_PERSONAS[1].username)
  const [password, setPassword] = useState(DEMO_PERSONAS[1].password)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const modalRef = useRef<HTMLDivElement>(null)
  const formBoxRef = useRef<HTMLFormElement>(null)

  // Trigger Anime.js animations upon modal opening
  useEffect(() => {
    if (!isOpen) return

    // Animate modal backdrop & content entrance
    if (modalRef.current) {
      animate(modalRef.current, {
        opacity: [0, 1],
        scale: [0.96, 1],
        duration: 350,
        ease: 'outCubic',
      })
    }

    // Stagger persona cards entrance
    animate('.role-persona-card', {
      translateY: [20, 0],
      opacity: [0, 1],
      delay: stagger(60, { start: 100 }),
      duration: 400,
      ease: 'outQuad',
    })
  }, [isOpen])

  if (!isOpen) return null

  // Fast Persona selection handler
  const handleSelectPersona = (p: PersonaInfo) => {
    setSelectedPersona(p)
    setUsername(p.username)
    setPassword(p.password)
    setErrorMsg(null)

    // Anime.js subtle pulse effect on selection
    animate(`.persona-${p.username}`, {
      scale: [0.96, 1.02, 1],
      duration: 300,
      ease: 'outBack',
    })
  }

  // Submit Authentication
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMsg(null)

    // Anime scan animation on authorization bar
    animate('.auth-scan-indicator', {
      width: ['0%', '100%'],
      duration: 600,
      ease: 'inOutQuad',
    })

    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      if (response.ok) {
        const data = await response.json()
        const userObj: UserProfile = {
          username: data.user.username,
          role: data.user.role,
          email: data.user.email,
          title: selectedPersona.username === data.user.username ? selectedPersona.title : `${data.user.role} Officer`,
          clearance_level:
            data.user.role === 'Admin'
              ? 4
              : data.user.role === 'Manager'
              ? 3
              : data.user.role === 'Technician'
              ? 2
              : 1,
          token: data.access_token,
        }

        localStorage.setItem('motorguard_auth_user', JSON.stringify(userObj))
        localStorage.setItem('motorguard_auth_token', data.access_token)
        onLoginSuccess(userObj)
        onClose()
        return
      } else {
        const errData = await response.json().catch(() => ({}))
        setErrorMsg(errData.detail || 'Invalid username or password. Please verify credentials.')
      }
    } catch {
      setErrorMsg('Cannot reach gateway authentication service. Ensure FastAPI backend is running.')
    } finally {
      setIsLoading(false)
    }

    // Trigger error shake animation
    if (formBoxRef.current) {
      animate(formBoxRef.current, {
        translateX: [-12, 12, -9, 9, -5, 5, 0],
        duration: 400,
        ease: 'inOutQuad',
      })
    }
  }

  return (
    <div className="modal-overlay">
      <div className="rbac-login-modal" ref={modalRef}>
        {/* Modal Content Wrapper */}
        <div className="rbac-modal-content">
          {/* Header */}
          <div className="rbac-modal-header">
            <div className="rbac-header-brand">
              <div className="rbac-logo-box">MG</div>
              <div>
                <h2 className="rbac-title">MotorGuard Security Gate</h2>
                <div className="rbac-subtitle">
                  Role-Based Access Control (RBAC) • Level 1-4 Clearance
                </div>
              </div>
            </div>

            <button className="btn-modal-close" onClick={onClose} title="Close Portal">
              ✕
            </button>
          </div>

          {/* Active Session Status if already logged in */}
          {currentUser && (
            <div className="rbac-active-session-banner">
              <div className="active-session-info">
                <span className="active-user-icon">👤</span>
                <div>
                  <div className="active-user-title">
                    Active Session: <strong>{currentUser.username}</strong> ({currentUser.role})
                  </div>
                  <div className="active-user-clearance">
                    Clearance: Level {currentUser.clearance_level} • {currentUser.email}
                  </div>
                </div>
              </div>

              {onLogout && (
                <button
                  className="btn-logout-banner"
                  onClick={() => {
                    onLogout()
                    setUsername(DEMO_PERSONAS[0].username)
                    setPassword(DEMO_PERSONAS[0].password)
                  }}
                >
                  🚪 End Session / Sign Out
                </button>
              )}
            </div>
          )}

          {/* Step 1: 1-Click Fast Persona Switcher */}
          <div className="rbac-section-title">
            <span>SELECT INDUSTRIAL PERSONA (1-CLICK QUICK FILL)</span>
          </div>

          <div className="persona-grid">
            {DEMO_PERSONAS.map((p) => {
              const isSelected = selectedPersona.username === p.username
              return (
                <div
                  key={p.username}
                  className={`role-persona-card persona-${p.username} ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSelectPersona(p)}
                >
                  <div className="persona-top">
                    <span className="persona-icon">{p.icon}</span>
                    <span
                      className="persona-clearance-pill"
                      style={{ backgroundColor: `${p.badgeColor}22`, color: p.badgeColor, borderColor: `${p.badgeColor}55` }}
                    >
                      CLEARANCE L{p.clearanceLevel}
                    </span>
                  </div>

                  <div className="persona-name">{p.username}</div>
                  <div className="persona-role-label">{p.title}</div>

                  <div className="persona-permissions-preview">
                    {p.permissions.slice(0, 2).map((perm, idx) => (
                      <span key={idx} className="persona-perm-tag">
                        ✓ {perm}
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Selected Role Permissions Breakdown */}
          <div className="selected-role-detail-card">
            <div className="detail-header">
              <div className="detail-title-group">
                <span className="detail-icon">{selectedPersona.icon}</span>
                <div>
                  <strong>{selectedPersona.title}</strong>
                  <span className="detail-clearance">
                    (Security Level {selectedPersona.clearanceLevel})
                  </span>
                </div>
              </div>
              <span className="credential-hint">
                Auto-filled: <code>{selectedPersona.username}</code> / <code>{selectedPersona.password}</code>
              </span>
            </div>

            <div className="detail-perms-list">
              {selectedPersona.permissions.map((perm, i) => (
                <div key={i} className="detail-perm-item">
                  <span className="perm-check">✔</span>
                  <span>{perm}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Step 2: Credentials Form */}
          <form className="rbac-login-form" ref={formBoxRef} onSubmit={handleSubmit}>
            <div className="auth-scan-bar">
              <div className="auth-scan-indicator" />
            </div>

            {errorMsg && <div className="rbac-error-box">⚠️ {errorMsg}</div>}

            <div className="rbac-inputs-row">
              <div className="rbac-input-group">
                <label className="rbac-label">Username / Operator ID</label>
                <input
                  type="text"
                  className="rbac-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. manager_alice"
                  required
                />
              </div>

              <div className="rbac-input-group">
                <label className="rbac-label">Password</label>
                <div className="password-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="rbac-input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter security key"
                    required
                  />
                  <button
                    type="button"
                    className="btn-toggle-pw"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                  >
                    {showPassword ? '👁️' : '🔒'}
                  </button>
                </div>
              </div>
            </div>

            <div className="rbac-form-actions">
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={onClose}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn-rbac-authenticate"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span>Scanning Credentials...</span>
                ) : (
                  <span>Authorize &amp; Launch Session ({selectedPersona.role})</span>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
