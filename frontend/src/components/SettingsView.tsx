import { useState, useEffect, useCallback, type FC } from 'react'
import { Save, Check, Sliders, Radio, Cpu, RefreshCw, AlertTriangle, ShieldCheck, Loader2, Lock, Info, UserPlus } from 'lucide-react'
import type { UserProfile } from '../types'

interface SettingsViewProps {
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
}

export const SettingsView: FC<SettingsViewProps> = ({ currentUser, onOpenLogin }) => {
  // Threshold values
  const [tempWarn, setTempWarn] = useState(50.0)
  const [tempCrit, setTempCrit] = useState(65.0)
  const [currWarn, setCurrWarn] = useState(3.5)
  const [currCrit, setCurrCrit] = useState(4.0)
  const [vibWarn, setVibWarn] = useState(0.20)
  const [vibCrit, setVibCrit] = useState(0.80)
  const [staleTimeoutSec, setStaleTimeoutSec] = useState(15)
  const [offlineTimeoutSec, setOfflineTimeoutSec] = useState(35)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loadingThresholds, setLoadingThresholds] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [persistedLoaded, setPersistedLoaded] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null)
  const [updatedBy, setUpdatedBy] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  // Gateway parameters
  const [mqttHost, setMqttHost] = useState('127.0.0.1')
  const [mqttPort, setMqttPort] = useState(1883)
  const [softApIp, setSoftApIp] = useState('192.168.4.1')
  const [gatewaySaved, setGatewaySaved] = useState(false)

  // Admin-only personnel account provisioning
  const [operatorUsername, setOperatorUsername] = useState('')
  const [operatorEmail, setOperatorEmail] = useState('')
  const [operatorPassword, setOperatorPassword] = useState('')
  const [operatorRole, setOperatorRole] = useState<'Technician' | 'Manager'>('Technician')
  const [operatorSaving, setOperatorSaving] = useState(false)
  const [operatorFeedback, setOperatorFeedback] = useState<string | null>(null)

  // Simulator controls
  const [simMotor, setSimMotor] = useState('MTR-775-002')
  const [simCondition, setSimCondition] = useState('healthy')
  const [simInjecting, setSimInjecting] = useState(false)
  const [simFeedback, setSimFeedback] = useState<string | null>(null)

  const isAuthorized = Boolean(
    currentUser && (currentUser.role === 'Admin' || currentUser.role === 'Manager' || currentUser.clearance_level >= 3)
  )
  const isAdmin = currentUser?.role === 'Admin'

  const handleCreateOperator = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isAdmin) {
      setOperatorFeedback('Only an Administrator can create personnel accounts.')
      return
    }

    setOperatorSaving(true)
    setOperatorFeedback(null)
    try {
      const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          username: operatorUsername.trim(),
          email: operatorEmail.trim(),
          password: operatorPassword,
          role: operatorRole,
        }),
      })
      if (res.ok) {
        setOperatorFeedback(`${operatorRole} account '${operatorUsername.trim()}' created successfully.`)
        setOperatorUsername('')
        setOperatorEmail('')
        setOperatorPassword('')
      } else {
        const error = await res.json().catch(() => ({}))
        const detail = Array.isArray(error.detail)
          ? error.detail.map((item: { msg?: string }) => item.msg ?? 'Invalid field').join(', ')
          : error.detail
        setOperatorFeedback(detail || `Unable to create account (HTTP ${res.status}).`)
      }
    } catch {
      setOperatorFeedback('Network error: Unable to reach authentication service.')
    } finally {
      setOperatorSaving(false)
    }
  }

  // Load persisted thresholds from MongoDB via authenticated API
  const fetchThresholds = useCallback(async () => {
    setLoadingThresholds(true)
    setFetchError(null)
    try {
      const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
      if (!token) {
        setFetchError('Sign in as Manager or Admin to view and edit Gateway Default Thresholds.')
        setLoadingThresholds(false)
        return
      }

      const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
      const res = await fetch('/api/v1/settings/thresholds', { headers })
      if (res.ok) {
        const data = await res.json()
        if (data.temperature_warning_c !== undefined) setTempWarn(data.temperature_warning_c)
        if (data.temperature_critical_c !== undefined) setTempCrit(data.temperature_critical_c)
        if (data.current_warning_a !== undefined) setCurrWarn(data.current_warning_a)
        if (data.current_critical_a !== undefined) setCurrCrit(data.current_critical_a)
        if (data.vibration_warning_g !== undefined) setVibWarn(data.vibration_warning_g)
        if (data.vibration_critical_g !== undefined) setVibCrit(data.vibration_critical_g)
        if (data.stale_timeout_sec !== undefined) setStaleTimeoutSec(data.stale_timeout_sec)
        if (data.offline_timeout_sec !== undefined) setOfflineTimeoutSec(data.offline_timeout_sec)
        if (data.updated_by) setUpdatedBy(data.updated_by)
        if (data.updated_at) setUpdatedAt(new Date(data.updated_at).toLocaleString())
        setPersistedLoaded(true)
      } else if (res.status === 401) {
        setFetchError('Session expired or unauthorized. Sign in with Manager or Admin credentials.')
      } else {
        setFetchError(`Server error loading gateway thresholds (HTTP ${res.status}).`)
      }
    } catch {
      setFetchError('Network error: Unable to reach gateway settings API.')
    } finally {
      setLoadingThresholds(false)
    }
  }, [currentUser])

  useEffect(() => {
    fetchThresholds()
  }, [fetchThresholds])

  const handleSaveThresholds = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isAuthorized) {
      setSaveError('Modifying operational thresholds requires Manager or Admin security clearance.')
      return
    }

    setSaving(true)
    setSaveError(null)
    setSaveSuccess(null)

    // Immediate client-side validation
    if (tempWarn >= tempCrit) {
      setSaveError(`Temperature warning (${tempWarn}°C) must be less than critical trip (${tempCrit}°C).`)
      setSaving(false)
      return
    }
    if (currWarn >= currCrit) {
      setSaveError(`Current warning (${currWarn}A) must be less than critical trip (${currCrit}A).`)
      setSaving(false)
      return
    }
    if (vibWarn >= vibCrit) {
      setSaveError(`Vibration warning (${vibWarn}g) must be less than critical trip (${vibCrit}g).`)
      setSaving(false)
      return
    }
    if (staleTimeoutSec >= offlineTimeoutSec) {
      setSaveError(`Stale timeout (${staleTimeoutSec}s) must be less than offline timeout (${offlineTimeoutSec}s).`)
      setSaving(false)
      return
    }

    try {
      const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/settings/thresholds', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          temperature_warning_c: tempWarn,
          temperature_critical_c: tempCrit,
          current_warning_a: currWarn,
          current_critical_a: currCrit,
          vibration_warning_g: vibWarn,
          vibration_critical_g: vibCrit,
          stale_timeout_sec: staleTimeoutSec,
          offline_timeout_sec: offlineTimeoutSec,
        }),
      })

      if (res.ok) {
        const data = await res.json()
        setSaved(true)
        setSaveSuccess('Gateway default limits persisted to MongoDB successfully. Motors with asset-specific thresholds retain their custom limits.')
        if (data.updated_by) setUpdatedBy(data.updated_by)
        if (data.updated_at) setUpdatedAt(new Date(data.updated_at).toLocaleString())
        setPersistedLoaded(true)
        setTimeout(() => {
          setSaved(false)
          setSaveSuccess(null)
        }, 4000)
      } else if (res.status === 401 || res.status === 403) {
        setSaveError('Modifying operational thresholds requires Manager or Admin security clearance.')
      } else if (res.status === 422) {
        const errData = await res.json().catch(() => ({}))
        const msg = errData?.detail?.[0]?.msg || errData?.detail || 'Threshold validation rejected by server.'
        setSaveError(`Validation Error: ${msg}`)
      } else {
        setSaveError(`Server error saving operational limits (HTTP ${res.status}).`)
      }
    } catch {
      setSaveError('Network error: Unable to reach gateway settings API.')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveGateway = (e: React.FormEvent) => {
    e.preventDefault()
    setGatewaySaved(true)
    setTimeout(() => setGatewaySaved(false), 2500)
  }

  const handleInjectSimFault = async () => {
    setSimInjecting(true)
    setSimFeedback(null)
    try {
      const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/simulator/inject', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          motor_id: simMotor,
          device_id: simMotor === 'MTR-775-002' ? 'sim-node-002' : 'sim-node-003',
          condition: simCondition,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setSimFeedback(`Condition '${simCondition}' applied to ${simMotor} -> Status: ${data.health_status.toUpperCase()}`)
      } else if (res.status === 401 || res.status === 403) {
        setSimFeedback('Simulator injection requires Manager or Admin security clearance.')
      } else {
        setSimFeedback(`Simulator error (HTTP ${res.status})`)
      }
    } catch {
      setSimFeedback('Failed to reach backend simulator endpoint.')
    } finally {
      setSimInjecting(false)
      setTimeout(() => setSimFeedback(null), 4000)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div className="page-title-group">
          <h2 className="page-title">Edge Gateway Configuration &amp; Safety Thresholds</h2>
          <p className="page-description">
            Configure gateway default safety trips, deterministic alarm thresholds, broker connectivity, and edge testing simulator.
          </p>
        </div>

        <button
          className="btn-secondary"
          onClick={fetchThresholds}
          disabled={loadingThresholds}
          title="Reload persisted thresholds from MongoDB"
        >
          <RefreshCw size={14} className={loadingThresholds ? 'animate-spin' : ''} />
          <span>Reload Gateway Settings</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px' }}>
        {/* Admin-only account creation keeps personnel records out of public views. */}
        {isAdmin && (
          <form onSubmit={handleCreateOperator} className="measurement-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <UserPlus size={18} color="var(--brand-primary)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>Add Personnel Account</h3>
            </div>
            <p style={{ margin: '0 0 14px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Administrators can provision Manager and Technician accounts with scoped permissions and site access.
            </p>
            <div style={{ display: 'grid', gap: '10px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <input className="search-input-field" value={operatorUsername} onChange={(e) => setOperatorUsername(e.target.value)} placeholder="Username" minLength={3} required />
                <select
                  className="search-input-field"
                  value={operatorRole}
                  onChange={(e) => setOperatorRole(e.target.value as 'Technician' | 'Manager')}
                  style={{ background: 'var(--bg-input, rgba(255,255,255,0.05))', color: 'var(--text-main)' }}
                >
                  <option value="Technician" style={{ background: '#1e293b' }}>Technician</option>
                  <option value="Manager" style={{ background: '#1e293b' }}>Manager</option>
                </select>
              </div>
              <input className="search-input-field" type="email" value={operatorEmail} onChange={(e) => setOperatorEmail(e.target.value)} placeholder="Work email" required />
              <input className="search-input-field" type="password" value={operatorPassword} onChange={(e) => setOperatorPassword(e.target.value)} placeholder="Temporary password (8+ characters)" minLength={8} required />
              {operatorFeedback && <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{operatorFeedback}</div>}
              <button type="submit" className="btn-primary" disabled={operatorSaving}>
                <UserPlus size={14} /> <span>{operatorSaving ? 'Creating account...' : `Create ${operatorRole}`}</span>
              </button>
            </div>
          </form>
        )}
        {/* Panel 1: Industrial Safety Thresholds */}
        <form onSubmit={handleSaveThresholds} className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color="var(--brand-primary)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
                Gateway Default Operational Thresholds
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {loadingThresholds ? (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Loader2 size={12} className="animate-spin" /> Fetching DB...
                </span>
              ) : persistedLoaded ? (
                <span className="badge-status healthy" style={{ fontSize: '10px' }}>
                  PERSISTED IN GATEWAY DB
                </span>
              ) : null}
            </div>
          </div>

          {/* Context Notice: Gateway Defaults Precedence */}
          <div style={{
            padding: '10px 12px',
            background: 'var(--bg-subtle)',
            border: '1px solid var(--border-main)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '16px',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            display: 'flex',
            gap: '8px',
            lineHeight: 1.45,
          }}>
            <Info size={16} color="var(--brand-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Gateway Baseline Scope:</strong> These thresholds govern unconfigured motors and newly provisioned edge nodes across the site. Individual motor assets with custom limits configured in Fleet Management (e.g. <code>MTR-775-001</code>) override these gateway defaults.
            </div>
          </div>

          {/* Unauthenticated / Error Banner */}
          {fetchError && (
            <div style={{
              padding: '10px 12px',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '16px',
              fontSize: '12px',
              color: '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={14} />
                <span>{fetchError}</span>
              </div>
              {onOpenLogin && !currentUser && (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={onOpenLogin}
                  style={{ fontSize: '11px', padding: '4px 10px', flexShrink: 0 }}
                >
                  Sign In
                </button>
              )}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', opacity: (!isAuthorized || loadingThresholds) ? 0.65 : 1 }}>
            {/* Temperature */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Temperature Safety Limits (°C) — Ambient Air (DHT11)
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Warning Limit</label>
                  <input
                    type="number"
                    step="0.5"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={tempWarn}
                    onChange={(e) => setTempWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Critical Limit</label>
                  <input
                    type="number"
                    step="0.5"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={tempCrit}
                    onChange={(e) => setTempCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>
            {/* Current */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Current Load Limits (Amps) — ACS712 20A
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Warning Limit</label>
                  <input
                    type="number"
                    step="0.1"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={currWarn}
                    onChange={(e) => setCurrWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Critical Cutoff</label>
                  <input
                    type="number"
                    step="0.1"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={currCrit}
                    onChange={(e) => setCurrCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Vibration */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Vibration RMS Limits (g RMS) — ADXL345
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Warning Limit</label>
                  <input
                    type="number"
                    step="0.05"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={vibWarn}
                    onChange={(e) => setVibWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Gateway Critical Trip</label>
                  <input
                    type="number"
                    step="0.05"
                    disabled={!isAuthorized || loadingThresholds}
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={vibCrit}
                    onChange={(e) => setVibCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Telemetry timeouts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Stale Warning Timeout (seconds)
                </label>
                <input
                  type="number"
                  step="1"
                  min="5"
                  max="120"
                  disabled={!isAuthorized || loadingThresholds}
                  className="search-input-field"
                  style={{ width: '100%', marginTop: '4px' }}
                  value={staleTimeoutSec}
                  onChange={(e) => setStaleTimeoutSec(parseInt(e.target.value, 10))}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Offline Disconnection Timeout (seconds)
                </label>
                <input
                  type="number"
                  step="1"
                  min="10"
                  max="300"
                  disabled={!isAuthorized || loadingThresholds}
                  className="search-input-field"
                  style={{ width: '100%', marginTop: '4px' }}
                  value={offlineTimeoutSec}
                  onChange={(e) => setOfflineTimeoutSec(parseInt(e.target.value, 10))}
                />
              </div>
            </div>

            {saveError && (
              <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={14} />
                <span>{saveError}</span>
              </div>
            )}

            {saveSuccess && (
              <div style={{ padding: '8px 12px', background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)', borderRadius: '6px', color: '#22c55e', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Check size={14} />
                <span>{saveSuccess}</span>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px' }}>
              <button
                type="submit"
                className="btn-primary"
                disabled={saving || !isAuthorized || loadingThresholds}
              >
                {saving ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : saved ? (
                  <Check size={14} />
                ) : (
                  <Save size={14} />
                )}
                <span>{saving ? 'Persisting to DB...' : saved ? 'Gateway Limits Saved' : 'Save Gateway Limits'}</span>
              </button>

              {updatedBy && (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Persisted by <strong style={{ color: 'var(--text-main)' }}>{updatedBy}</strong>
                  {updatedAt ? ` (${updatedAt})` : ''}
                </span>
              )}
            </div>
          </div>
        </form>

        {/* Panel 2: Edge Gateway & MQTT Infrastructure */}
        <form onSubmit={handleSaveGateway} className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Radio size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Connectivity &amp; Broker Topology
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                MQTT Broker Hostname / IP (Local Mosquitto)
              </label>
              <input
                type="text"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={mqttHost}
                onChange={(e) => setMqttHost(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                MQTT Broker TCP Port
              </label>
              <input
                type="number"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={mqttPort}
                onChange={(e) => setMqttPort(parseInt(e.target.value, 10))}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                ESP32 Hardware SoftAP Bridge IP (COM7 USB / Direct Wi-Fi)
              </label>
              <input
                type="text"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={softApIp}
                onChange={(e) => setSoftApIp(e.target.value)}
              />
            </div>

            <div
              style={{
                padding: '12px',
                background: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '11px',
                color: 'var(--text-muted)',
                lineHeight: 1.5,
              }}
            >
              <strong style={{ color: 'var(--text-main)' }}>Telemetry Contract v1.0.0:</strong>
              <br />
              • Topic: <code style={{ color: 'var(--brand-primary)' }}>motorguard/v1/&#123;device_id&#125;/telemetry</code>
              <br />
              • QoS: 1 (At least once with broker acknowledgment)
              <br />
              • LWT: <code style={{ color: 'var(--status-critical)' }}>motorguard/v1/&#123;device_id&#125;/status</code> (offline)
            </div>

            <div style={{ paddingTop: '8px' }}>
              <button type="submit" className="btn-primary">
                {gatewaySaved ? <Check size={14} /> : <Save size={14} />}
                <span>{gatewaySaved ? 'Gateway Topology Saved' : 'Apply Gateway Settings'}</span>
              </button>
            </div>
          </div>
        </form>

        {/* Panel 3: Edge Impulse TinyML Specification */}
        <div className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Cpu size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Impulse TinyML Model Metadata
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Edge Impulse Project ID:</span>
              <strong style={{ color: 'var(--text-main)' }}>#1133176 ("MotoGuard Motor Health")</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Architecture:</span>
              <strong style={{ color: 'var(--text-main)' }}>Sensor Fusion EON Neural Network</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Input Features (Order-Strict):</span>
              <strong style={{ color: 'var(--text-main)' }}>[0] temp_C, [1] vib_g, [2] current_A</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Model Class Labels:</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <span className="badge-status healthy">HEALTHY</span>
                <span className="badge-status warning">WARNING</span>
                <span className="badge-status critical">CRITICAL</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: 'var(--text-muted)' }}>DSP &amp; Quantization:</span>
              <strong style={{ color: 'var(--text-main)' }}>int8 Quantized / ~180KB RAM Free</strong>
            </div>
          </div>
        </div>

        {/* Panel 4: Edge Virtual Fleet Simulator Controls */}
        <div className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sliders size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Telemetry Simulator Suite (Testing &amp; Verification)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Target Virtual Drive Asset</label>
              <select
                value={simMotor}
                onChange={(e) => setSimMotor(e.target.value)}
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
              >
                <option value="MTR-775-001">MTR-775-001 (Physical / Simulated Twin)</option>
                <option value="MTR-775-002">MTR-775-002 (sim-node-002)</option>
                <option value="MTR-775-003">MTR-775-003 (sim-node-003)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Fault Injection Profile</label>
              <select
                value={simCondition}
                onChange={(e) => setSimCondition(e.target.value)}
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
              >
                <option value="healthy">Healthy Baseline (38.5°C, 2.15A, 0.082g)</option>
                <option value="warning_temp">Warning Overtemperature (55.4°C)</option>
                <option value="critical_vib">Critical Mechanical Bearing Fault (0.895g)</option>
                <option value="overload_current">Electrical Overload (4.65A, 62°C)</option>
                <option value="sensor_disconnected">Sensor Disconnection (temp=NULL)</option>
              </select>
            </div>

            {simFeedback && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--brand-primary)',
                  fontSize: '11px',
                  color: 'var(--text-main)',
                  fontWeight: 600,
                }}
              >
                {simFeedback}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', paddingTop: '4px' }}>
              <button
                type="button"
                className="btn-primary"
                disabled={simInjecting}
                onClick={handleInjectSimFault}
              >
                {simInjecting ? <RefreshCw size={14} className="spin" /> : <AlertTriangle size={14} />}
                <span>{simInjecting ? 'Injecting Frame...' : 'Inject Test Condition'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
