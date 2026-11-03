import type { FC } from 'react'
import {
  Sun,
  Moon,
  Clock,
  LogOut,
  Lock,
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
        return 'Overview'
      case 'fleet':
      case 'motors':
        return 'Motor Fleet'
      case 'live':
        return 'Live Monitoring'
      case 'analytics':
        return 'Analytics & Diagnostics'
      case 'alerts':
      case 'manager':
        return 'Alerts & Events'
      case 'maintenance':
      case 'technician':
        return 'Work Orders'
      case 'twin':
        return '3D Digital Twin'
      case 'landing':
        return '3D Motor Tour'
      case 'devices':
        return 'ESP32 Devices'
      case 'users':
        return 'User Management'
      case 'reports':
        return 'Reports'
      case 'settings':
        return 'Settings'
      default:
        return 'Overview'
    }
  }

  const formatTime = (iso?: string) => {
    if (!iso) return 'Waiting...'
    try {
      const normalized = !iso.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(iso) ? `${iso}Z` : iso
      const d = new Date(normalized)
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
        {/* Plant Breadcrumb */}
        <div className="topbar-breadcrumbs" style={{ fontSize: '12px' }}>
          <span className="scada-equip-tag" style={{ fontSize: '11px', fontWeight: 600, padding: '2px 8px' }}>
            PLANT-01
          </span>
          <span className="breadcrumb-separator" style={{ color: 'var(--text-muted)' }}>/</span>
          <span className="breadcrumb-current" style={{ fontWeight: 600, color: 'var(--text-main)' }}>
            {getTabLabel(currentTab)}
          </span>
        </div>

        {/* Global Motor Selector (Visible in Analytics & 3D Twin) */}
        {(currentTab === 'analytics' || currentTab === 'twin') && motors.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '12px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
              Asset:
            </span>
            <select
              value={selectedMotorId || motors[0].motor_id}
              onChange={(e) => onSelectMotor?.(e.target.value)}
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-main)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                fontSize: '11.5px',
                fontWeight: 500,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  {m.motor_id} [{m.source.toUpperCase()}] &mdash; {m.latest.inference.health_status}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="topbar-right">
        {/* Fleet Health Indicator */}
        <div className="topbar-status-wrapper">
          {critCount > 0 ? (
            <div
              className="scada-annunciator-tile crit"
              title={`${critCount} motor(s) currently in critical alarm`}
              style={{ cursor: 'default' }}
            >
              <span className="scada-heartbeat-dot" style={{ background: '#EF4444', width: 6, height: 6 }} />
              {critCount} CRITICAL ALARM{critCount > 1 ? 'S' : ''}
            </div>
          ) : warnCount > 0 ? (
            <div
              className="scada-annunciator-tile warn"
              title={`${warnCount} motor(s) in warning condition`}
              style={{ cursor: 'default' }}
            >
              <span>▲</span> {warnCount} WARNING{warnCount > 1 ? 'S' : ''}
            </div>
          ) : (
            <div
              className="scada-annunciator-tile norm"
              title={`All ${healthyCount} monitored motors operating within nominal parameters`}
              style={{ cursor: 'default' }}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
              FLEET NOMINAL ({healthyCount})
            </div>
          )}
        </div>

        {/* Consolidated Gateway & Node Telemetry Pill */}
        <div
          className={`connection-pill ${wsConnected ? 'online' : (!currentUser ? 'reconnecting' : 'offline')}`}
          style={{ fontSize: '11px', padding: '4px 9px', display: 'flex', alignItems: 'center', gap: '6px' }}
          title={
            wsConnected
              ? 'Telemetry bus live (100 Hz pacing)'
              : !currentUser
              ? 'Gateway secured — sign in to activate telemetry bus'
              : 'Gateway feed offline'
          }
        >
          <span className={`connection-dot ${wsConnected ? 'pulse' : ''}`} />
          <span style={{ fontWeight: 600 }}>
            {wsConnected ? 'LIVE BUS' : (!currentUser ? 'SECURED' : 'OFFLINE')}
          </span>
          {esp32HwConnected && (
            <span
              style={{
                fontSize: '9.5px',
                padding: '1px 5px',
                borderRadius: '2px',
                background: 'var(--brand-primary)',
                color: '#fff',
                fontWeight: 700,
                letterSpacing: '0.04em',
              }}
              title="ESP32 Physical Hardware node connected and streaming"
            >
              ESP32
            </span>
          )}
        </div>

        {/* Pacing, Time & Telemetry Frames */}
        <div
          title={`Last frame: ${formatTime(lastUpdatedIso)} · ${totalMessages.toLocaleString()} frames received`}
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '0 4px',
          }}
        >
          <Clock size={11} style={{ opacity: 0.7 }} />
          <span className="tabular-nums">{formatTime(lastUpdatedIso)}</span>
          <span style={{ opacity: 0.35 }}>•</span>
          <span className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
            {totalMessages > 9999 ? `${(totalMessages / 1000).toFixed(1)}k` : totalMessages.toLocaleString()} frames
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
            style={{
              padding: '6px 14px',
              fontSize: '11px',
              fontFamily: 'var(--scada-mono-font)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              letterSpacing: '0.04em',
            }}
            onClick={onOpenLogin}
          >
            <Lock size={12} /> AUTHORIZED SIGN IN
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
