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

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-breadcrumbs">
          <span className="breadcrumb-root">Plant Floor</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">{getTabLabel(currentTab)}</span>
        </div>

        {/* Global Motor Selector (Visible in Analytics & 3D Twin) */}
        {(currentTab === 'analytics' || currentTab === 'twin') && motors.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '12px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Asset:
            </span>
            <select
              value={selectedMotorId || motors[0].motor_id}
              onChange={(e) => onSelectMotor?.(e.target.value)}
              style={{
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-main)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                fontSize: '12px',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  {m.motor_id} ({m.source.toUpperCase()} - {m.latest.inference.health_status.toUpperCase()})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="topbar-right">
        {/* Last Data Received Time */}
        <div className="topbar-timestamp" title="Timestamp of latest accepted telemetry event">
          <Clock size={13} />
          <span className="tabular-nums">Last: {formatTime(lastUpdatedIso)}</span>
        </div>

        {/* Ingested Messages Count */}
        <div
          style={{
            fontSize: '12px',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
          title="Total validated telemetry frames processed since launch"
        >
          <Layers size={13} color="var(--text-muted)" />
          <span>Ingested:</span>
          <strong className="tabular-nums" style={{ color: 'var(--text-main)' }}>
            {totalMessages.toLocaleString()}
          </strong>
        </div>

        {/* ESP32 Hardware Status Badge */}
        <div
          className={`connection-pill ${esp32HwConnected ? 'online' : ''}`}
          style={{
            background: esp32HwConnected ? 'var(--status-hardware-bg)' : undefined,
            color: esp32HwConnected ? 'var(--status-hardware)' : undefined,
            borderColor: esp32HwConnected ? 'var(--status-hardware-border)' : undefined,
          }}
          title={
            esp32HwConnected
              ? 'ESP32 Physical Hardware node actively streaming'
              : 'Waiting for ESP32 hardware connection'
          }
        >
          <span className={`connection-dot ${esp32HwConnected ? 'pulse' : ''}`} />
          <span>{esp32HwConnected ? 'ESP32 HW: ONLINE' : 'ESP32 HW: STANDBY'}</span>
        </div>

        {/* WebSocket Gateway Status Badge */}
        <div
          className={`connection-pill ${wsConnected ? 'online' : 'offline'}`}
          title={wsConnected ? 'WebSocket live feed active' : 'Gateway feed disconnected'}
        >
          <span className={`connection-dot ${wsConnected ? 'pulse' : ''}`} />
          <span>{wsConnected ? 'GATEWAY CONNECTED' : 'OFFLINE'}</span>
        </div>

        {/* Theme Toggle Button */}
        <button
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
          aria-label="Toggle theme"
        >
          {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
        </button>

        {/* User Profile / Auth Button */}
        {!currentUser ? (
          <button
            className="btn-primary-glow"
            style={{ padding: '6px 14px', fontSize: '12px' }}
            onClick={onOpenLogin}
          >
            🔑 Sign In
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              className="user-profile-pill"
              title={`Logged in as ${currentUser.username} (${currentUser.role})`}
              onClick={onOpenLogin}
            >
              <div className="user-avatar">
                {currentUser.username.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="user-meta-name">{currentUser.username}</div>
              </div>
              <span className="user-role-badge">
                {currentUser.role}
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
                <LogOut size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
