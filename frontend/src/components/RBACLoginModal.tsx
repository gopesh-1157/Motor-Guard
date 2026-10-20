import { useState, useEffect, useRef } from 'react'
import type { FC, FormEvent } from 'react'
import { animate } from 'animejs'
import { ShieldCheck, Lock, User, Eye, EyeOff, AlertCircle, LogOut, KeyRound } from 'lucide-react'
import type { UserProfile } from '../types'

interface RBACLoginModalProps {
  isOpen: boolean
  onClose: () => void
  onLoginSuccess: (user: UserProfile) => void
  currentUser: UserProfile | null
  onLogout?: () => void
}



export const RBACLoginModal: FC<RBACLoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
  currentUser,
  onLogout,
}) => {
  // Start with clean, unpopulated inputs for public security
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const modalRef = useRef<HTMLDivElement>(null)
  const formBoxRef = useRef<HTMLFormElement>(null)

  // Trigger Anime.js animations upon modal opening
  useEffect(() => {
    if (!isOpen) return

    if (modalRef.current) {
      animate(modalRef.current, {
        opacity: [0, 1],
        scale: [0.96, 1],
        translateY: [15, 0],
        duration: 300,
        ease: 'outCubic',
      })
    }
  }, [isOpen])

  if (!isOpen) return null



  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMsg(null)

    // Scan progress bar animation
    animate('.auth-scan-indicator', {
      width: ['0%', '100%'],
      duration: 500,
      ease: 'inOutQuad',
    })

    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })

      if (response.ok) {
        const data = await response.json()
        const userObj: UserProfile = {
          username: data.user.username,
          role: data.user.role,
          email: data.user.email,
          title: `${data.user.role} Clearance`,
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
        if (rememberMe) {
          localStorage.setItem('motorguard_remember_user', username.trim())
        }

        onLoginSuccess(userObj)
        onClose()
        return
      } else {
        const errData = await response.json().catch(() => ({}))
        setErrorMsg(errData.detail || 'Invalid username or password. Please verify credentials.')
      }
    } catch {
      setErrorMsg('Cannot connect to gateway authentication service. Verify backend is active.')
    } finally {
      setIsLoading(false)
    }

    // Trigger error shake animation
    if (formBoxRef.current) {
      animate(formBoxRef.current, {
        translateX: [-10, 10, -7, 7, -3, 3, 0],
        duration: 350,
        ease: 'inOutQuad',
      })
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="rbac-login-modal secure-enterprise-modal" ref={modalRef} style={{ maxWidth: '480px' }}>
        <div className="rbac-modal-content" style={{ padding: '28px' }}>
          {/* Header */}
          <div className="rbac-modal-header" style={{ borderBottom: 'none', paddingBottom: '0' }}>
            <div className="rbac-header-brand" style={{ gap: '14px' }}>
              <div
                className="rbac-logo-box"
                style={{
                  width: '44px',
                  height: '44px',
                  background: 'linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%)',
                  borderRadius: '12px',
                  boxShadow: '0 6px 18px rgba(29, 78, 216, 0.35)',
                }}
              >
                <ShieldCheck size={24} color="#ffffff" />
              </div>
              <div>
                <h2 className="rbac-title" style={{ fontSize: '20px', letterSpacing: '-0.3px' }}>
                  MotorGuard Security Gate
                </h2>
                <div className="rbac-subtitle" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Enterprise SCADA Authentication &amp; Access Clearance
                </div>
              </div>
            </div>

            <button
              className="btn-modal-close"
              onClick={onClose}
              title="Close Portal"
              aria-label="Close"
              style={{ alignSelf: 'flex-start' }}
            >
              ✕
            </button>
          </div>

          {/* Active Session Status if already logged in */}
          {currentUser && (
            <div className="rbac-active-session-banner" style={{ marginTop: '12px' }}>
              <div className="active-session-info">
                <span className="active-user-icon">👤</span>
                <div>
                  <div className="active-user-title">
                    Active Station: <strong>{currentUser.username}</strong> ({currentUser.role})
                  </div>
                  <div className="active-user-clearance">
                    Clearance Level {currentUser.clearance_level} • {currentUser.email}
                  </div>
                </div>
              </div>

              {onLogout && (
                <button
                  type="button"
                  className="btn-logout-banner"
                  onClick={() => {
                    onLogout()
                    setUsername('')
                    setPassword('')
                  }}
                >
                  <LogOut size={13} />
                  <span>Sign Out</span>
                </button>
              )}
            </div>
          )}

          {/* Security Notice Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 12px',
              background: 'rgba(14, 165, 233, 0.08)',
              border: '1px solid rgba(14, 165, 233, 0.2)',
              borderRadius: '8px',
              fontSize: '11px',
              color: 'var(--text-secondary)',
              marginTop: '4px',
            }}
          >
            <Lock size={13} style={{ color: '#0ea5e9', flexShrink: 0 }} />
            <span>Authorized personnel only. Sessions are monitored and logged to the plant audit trail.</span>
          </div>

          {/* Primary Enterprise Authentication Form */}
          <form className="rbac-login-form" ref={formBoxRef} onSubmit={handleSubmit} style={{ marginTop: '8px' }}>
            <div className="auth-scan-bar" style={{ height: '3px', background: 'rgba(56, 189, 248, 0.15)', borderRadius: '2px', overflow: 'hidden', marginBottom: '16px' }}>
              <div className="auth-scan-indicator" style={{ height: '100%', width: '0%', background: 'linear-gradient(90deg, #38bdf8, #2563eb)' }} />
            </div>

            {errorMsg && (
              <div className="rbac-error-box" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', fontSize: '13px', marginBottom: '14px' }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{errorMsg}</span>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Username Input */}
              <div className="rbac-input-group">
                <label className="rbac-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                  <User size={14} style={{ color: 'var(--text-muted)' }} />
                  <span>Username / Station ID</span>
                </label>
                <input
                  type="text"
                  className="rbac-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter assigned username or operator ID"
                  autoComplete="username"
                  autoFocus
                  required
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-main)',
                    background: 'var(--bg-input, rgba(255, 255, 255, 0.04))',
                    color: 'var(--text-main)',
                    fontSize: '14px',
                    outline: 'none',
                    transition: 'border-color 0.2s',
                  }}
                />
              </div>

              {/* Password Input */}
              <div className="rbac-input-group">
                <label className="rbac-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                  <Lock size={14} style={{ color: 'var(--text-muted)' }} />
                  <span>Security Password</span>
                </label>
                <div className="password-wrapper" style={{ position: 'relative', width: '100%' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="rbac-input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    autoComplete="current-password"
                    required
                    style={{
                      width: '100%',
                      padding: '11px 42px 11px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-main)',
                      background: 'var(--bg-input, rgba(255, 255, 255, 0.04))',
                      color: 'var(--text-main)',
                      fontSize: '14px',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    className="btn-toggle-pw"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      padding: '4px',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Remember station checkbox */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    style={{ accentColor: '#2563eb', cursor: 'pointer' }}
                  />
                  <span>Remember this terminal</span>
                </label>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>TLS 256-Bit Encrypted</span>
              </div>
            </div>

            {/* Form Actions */}
            <div className="rbac-form-actions" style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={onClose}
                style={{
                  flex: '1',
                  padding: '11px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-main)',
                  background: 'var(--bg-card)',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn-rbac-authenticate"
                disabled={isLoading}
                style={{
                  flex: '2',
                  padding: '11px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: isLoading ? 'wait' : 'pointer',
                  boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {isLoading ? (
                  <span>Verifying Credentials...</span>
                ) : (
                  <>
                    <KeyRound size={15} />
                    <span>Authorize &amp; Launch Session</span>
                  </>
                )}
              </button>
            </div>
          </form>



          {/* Security Compliance Footnote */}
          <div
            style={{
              marginTop: '16px',
              paddingTop: '12px',
              borderTop: '1px solid var(--border-main)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '10px',
              color: 'var(--text-muted)',
            }}
          >
            <span>NIST SP 800-82 OT Cybersecurity</span>
            <span>Zero-Trust SCADA Access Gate</span>
          </div>
        </div>
      </div>
    </div>
  )
}
