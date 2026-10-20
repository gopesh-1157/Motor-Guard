import type { FC } from 'react'
import {
  Sun,
  Moon,
  Clock,
  Layers,
  LogOut,
} from 'lucide-react'
import type { NavigationTab, UserProfile, MotorState } from '../types'

interface TopBarProps {
  currentTab: NavigationTab
  wsConnected: boolean
  esp32HwConnected?: boolean
  totalMessages: number
  lastUpdatedIso?: string
  currentUser: UserProfile | null
  onOpenLogin: () => void
  onLogout?: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  motors: MotorState[]
  selectedMotorId?: string
  onSelectMotor?: (motorId: string) => void
}

export const TopBar: FC<TopBarProps> = ({
  currentTab,
  wsConnected,
  esp32HwConnected,
  totalMessages,
  lastUpdatedIso,
  currentUser,
  onOpenLogin,
  onLogout,
  theme,
  onToggleTheme,
  motors,
  selectedMotorId,
  onSelectMotor,
}) => {
  const getTabLabel = (tab: NavigationTab) => {
    switch (tab) {
      case 'overview':
      case 'landing':
        return 'Overview'
      case 'fleet':
        return 'Live Motors'
      case 'analytics':
        return 'Analytics'
      case 'motors':
        return 'Motor Management & Provisioning'
      case 'alerts':
      case 'manager':
        return 'Alerts & Faults'
      case 'maintenance':
      case 'technician':
        return 'Maintenance Workbench'
      case 'twin':
        return '3D Spatial Twin'
      case 'landing':
        return '3D Motor Tour & Industrial Showcase'
      case 'devices':
        return 'Device Nodes'
      case 'reports':
        return 'Operational Reports'
      case 'settings':
        return 'Gateway Settings'
      default:
        return 'Dashboard'
    }
  }

  const formatTime = (iso?: string) => {
    if (!iso) return 'Waiting...'
    try {
      const d = new Date(iso)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return iso
    }
  }

  const critCount = motors.filter((m) => m.latest.inference.health_status === 'critical').length
  const warnCount = motors.filter((m) => m.latest.inference.health_status === 'warning').length
  const healthyCount = motors.filter((m) => m.latest.inference.health_status === 'healthy').length

  return (
    <header className="topbar" style={{ borderBottom: '1px solid var(--border-main)' }}>
      <div className="topbar-left">
        {/* SCADA Plant Cell Tag & Navigation Path */}
        <div className="topbar-breadcrumbs" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '12px' }}>
          <span className="scada-equip-tag" style={{ fontSize: '10px', padding: '2px 6px' }}>PLANT-01 // CELL-A</span>
          <span className="breadcrumb-separator" style={{ color: 'var(--text-muted)' }}>::</span>
          <span className="breadcrumb-current" style={{ fontWeight: 700, letterSpacing: '0.02em' }}>
            {getTabLabel(currentTab).toUpperCase()}
          </span>
        </div>

        {/* Global Motor Selector (Visible in Analytics & 3D Twin) */}
        {(currentTab === 'analytics' || currentTab === 'twin') && motors.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
            <span style={{ fontSize: '10px', fontFamily: 'var(--scada-mono-font)', color: 'var(--text-muted)', fontWeight: 700 }}>
              ASSET TAG:
            </span>
            <select
              value={selectedMotorId || motors[0].motor_id}
              onChange={(e) => onSelectMotor?.(e.target.value)}
              style={{
                padding: '4px 8px',
                borderRadius: '3px',
                border: '1px solid var(--border-main)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                fontSize: '11px',
                fontFamily: 'var(--scada-mono-font)',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  {m.motor_id} [{m.source.toUpperCase()}] — {m.latest.inference.health_status.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="topbar-right">
        {/* Real-time SCADA Annunciator Matrix */}
        <div className="scada-annunciator-strip" title="SCADA Fleet Health Annunciator Matrix">
          <div className={`scada-annunciator-tile ${critCount > 0 ? 'crit' : 'norm'}`}>
            <span className={critCount > 0 ? 'scada-heartbeat-dot' : ''} style={{ background: critCount > 0 ? '#EF4444' : '#10B981', width: 6, height: 6 }} />
            ALARM: {critCount}
          </div>
          <div className={`scada-annunciator-tile ${warnCount > 0 ? 'warn' : 'norm'}`}>
            WARN: {warnCount}
          </div>
          <div className="scada-annunciator-tile norm">
            NORM: {healthyCount}
          </div>
        </div>

        {/* SCADA Sync Heartbeat & Timestamp */}
        <div className="topbar-timestamp" title="Live SCADA Telemetry Stream Pacing (100 Hz / Edge Impulse Sync)" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '11px' }}>
          <span className="scada-heartbeat-dot" />
          <Clock size={12} />
          <span className="tabular-nums">SYNC: {formatTime(lastUpdatedIso)}</span>
        </div>

        {/* Ingested Frames */}
        <div
          style={{
            fontSize: '11px',
            fontFamily: 'var(--scada-mono-font)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}
          title="Total validated telemetry frames processed since gateway launch"
        >
          <Layers size={12} color="var(--text-muted)" />
          <span>FRAMES:</span>
          <strong className="tabular-nums" style={{ color: 'var(--text-main)' }}>
            {totalMessages.toLocaleString()}
          </strong>
        </div>

        {/* ESP32 Hardware Status Badge */}
        <div
          className={`connection-pill ${esp32HwConnected ? 'online' : ''}`}
          style={{
            fontFamily: 'var(--scada-mono-font)',
            fontSize: '10.5px',
            background: esp32HwConnected ? 'rgba(59, 130, 246, 0.12)' : undefined,
            color: esp32HwConnected ? '#60A5FA' : undefined,
            borderColor: esp32HwConnected ? 'rgba(59, 130, 246, 0.35)' : undefined,
          }}
          title={
            esp32HwConnected
              ? 'ESP32 Physical Hardware node actively streaming via SoftAP/WiFi'
              : 'Waiting for ESP32 hardware connection'
          }
        >
          <span className={`connection-dot ${esp32HwConnected ? 'pulse' : ''}`} />
          <span>{esp32HwConnected ? 'ESP32 HW: ONLINE' : 'ESP32 HW: STANDBY'}</span>
        </div>

        {/* Gateway WebSocket Connection */}
        <div
          className={`connection-pill ${wsConnected ? 'online' : (!currentUser ? 'reconnecting' : 'offline')}`}
          style={{
            fontFamily: 'var(--scada-mono-font)',
            fontSize: '10.5px',
            background: !wsConnected && !currentUser ? 'rgba(245, 158, 11, 0.12)' : undefined,
            color: !wsConnected && !currentUser ? '#F59E0B' : undefined,
            borderColor: !wsConnected && !currentUser ? 'rgba(245, 158, 11, 0.35)' : undefined,
          }}
          title={
            wsConnected
              ? 'WebSocket OT telemetry feed active (Authenticated Live Bus)'
              : !currentUser
              ? 'Gateway secured — Sign In as Operator or Manager to stream live bus'
              : 'Gateway feed disconnected'
          }
        >
          <span className={`connection-dot ${wsConnected ? 'pulse' : ''}`} />
          <span>
            {wsConnected
              ? 'OT GW: SYNCED'
              : !currentUser
              ? 'OT GW: SECURED'
              : 'OT GW: OFFLINE'}
          </span>
        </div>

        {/* Theme Toggle Button */}
        <button
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
          aria-label="Toggle theme"
        >
          {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
        </button>

        {/* User Profile / Auth Button */}
        {!currentUser ? (
          <button
            className="btn-primary-glow"
            style={{ padding: '5px 12px', fontSize: '11px', fontFamily: 'var(--scada-mono-font)' }}
            onClick={onOpenLogin}
          >
            🔒 OPERATOR SIGN IN
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              className="user-profile-pill"
              title={`Logged in as ${currentUser.username} (${currentUser.role})`}
              onClick={onOpenLogin}
              style={{ fontFamily: 'var(--scada-mono-font)' }}
            >
              <div className="user-avatar" style={{ fontSize: '10px' }}>
                {currentUser.username.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="user-meta-name" style={{ fontSize: '11px' }}>{currentUser.username}</div>
              </div>
              <span className="user-role-badge" style={{ fontSize: '9px', letterSpacing: '0.04em' }}>
                {currentUser.role.toUpperCase()}
              </span>
            </div>
            {onLogout && (
              <button
                className="theme-toggle-btn"
                onClick={onLogout}
                title="Sign Out"
                aria-label="Sign Out"
                style={{ color: 'var(--status-critical)' }}
              >
                <LogOut size={13} />
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
