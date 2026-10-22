import type { FC } from 'react'
import type { NavigationTab, UserProfile } from '../types'

interface HeaderProps {
  currentTab: NavigationTab
  onTabChange: (tab: NavigationTab) => void
  wsConnected: boolean
  esp32ApConnected?: boolean
  totalMessages: number
  criticalCount: number
  assignedCount: number
  onReconnect: () => void
  currentUser: UserProfile | null
  onOpenLogin: () => void
}

export const Header: FC<HeaderProps> = ({
  currentTab,
  onTabChange,
  wsConnected,
  esp32ApConnected,
  totalMessages,
  criticalCount,
  assignedCount,
  onReconnect,
  currentUser,
  onOpenLogin,
}) => {
  const getRoleBadgeClass = (role?: string) => {
    switch (role) {
      case 'Admin':
        return 'role-badge-admin'
      case 'Manager':
        return 'role-badge-manager'
      case 'Technician':
        return 'role-badge-tech'
      default:
        return 'role-badge-guest'
    }
  }

  const getRoleIcon = (role?: string) => {
    switch (role) {
      case 'Admin':
        return '👑'
      case 'Manager':
        return '👔'
      case 'Technician':
        return '🔧'
      default:
        return '🔒'
    }
  }

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo" onClick={() => onTabChange('landing')} style={{ cursor: 'pointer' }}>
          <div className="header-logo-icon">MG</div>
          <div>
            <h1 className="header-title">MotorGuard</h1>
            <div className="header-subtitle">Industrial Edge Gateway</div>
          </div>
        </div>

        {/* Primary Navigation Tabs */}
        <nav className="header-nav">
          <button
            className={`nav-tab-btn ${currentTab === 'landing' ? 'active' : ''}`}
            onClick={() => onTabChange('landing')}
          >
            Overview
          </button>

          <button
            className={`nav-tab-btn ${currentTab === 'fleet' ? 'active' : ''}`}
            onClick={() => onTabChange('fleet')}
          >
            Fleet SCADA
          </button>

          <button
            className={`nav-tab-btn ${currentTab === 'twin' ? 'active' : ''}`}
            onClick={() => onTabChange('twin')}
          >
            🌐 3D Digital Twin
          </button>

          <button
            className={`nav-tab-btn ${currentTab === 'manager' ? 'active' : ''}`}
            onClick={() => onTabChange('manager')}
          >
            Manager Hub
            {currentUser && currentUser.clearance_level < 3 && (
              <span className="tab-clearance-lock" title="Requires Level 3 Manager Clearance">
                🔒 L3+
              </span>
            )}
            {criticalCount > 0 && (
              <span className="nav-badge-critical">{criticalCount}</span>
            )}
          </button>

          <button
            className={`nav-tab-btn ${currentTab === 'technician' ? 'active' : ''}`}
            onClick={() => onTabChange('technician')}
          >
            Technician Workbench
            {currentUser && currentUser.clearance_level < 2 && (
              <span className="tab-clearance-lock" title="Requires Level 2 Technician Clearance">
                🔒 L2+
              </span>
            )}
            {assignedCount > 0 && (
              <span className="nav-badge-assigned">{assignedCount}</span>
            )}
          </button>
        </nav>
      </div>

      <div className="header-right">
        {/* Ingested Telemetry Counter */}
        <div className="header-stat-item">
          <span className="stat-muted">Ingested:</span>
          <strong className="stat-accent">{totalMessages.toLocaleString()}</strong>
        </div>

        {/* Gateway WebSocket Status Badge */}
        <div
          className={`connection-badge ${wsConnected ? 'connected' : 'disconnected'}`}
          onClick={!wsConnected ? onReconnect : undefined}
          style={{ cursor: !wsConnected ? 'pointer' : 'default' }}
          title={!wsConnected ? 'Click to reconnect' : 'Live WebSocket feed connected'}
        >
          <span className={`connection-dot ${wsConnected ? 'connected' : 'disconnected'}`} />
          {wsConnected ? 'GATEWAY ONLINE' : 'OFFLINE'}
        </div>

        {/* Physical ESP32 Hardware Link Badge */}
        <div
          className={`connection-badge ${esp32ApConnected ? 'connected' : ''}`}
          style={{
            borderColor: esp32ApConnected ? 'rgba(16, 185, 129, 0.45)' : 'rgba(255, 255, 255, 0.12)',
            background: esp32ApConnected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.03)',
            color: esp32ApConnected ? '#34d399' : '#94a3b8',
            cursor: 'default',
          }}
          title={
            esp32ApConnected
              ? 'Physical ESP32 Node streaming at http://192.168.4.1'
              : 'Waiting for ESP32 AP (Connect WiFi to MotorGuard-ESP32-AP)'
          }
        >
          <span className={`connection-dot ${esp32ApConnected ? 'connected' : 'disconnected'}`} />
          {esp32ApConnected ? 'ESP32 HW: ONLINE' : 'ESP32 HW: STANDBY'}
        </div>

        {/* RBAC Active User Profile Pill */}
        <div className="header-rbac-pill" onClick={onOpenLogin} title="Click to Switch Role or Sign Out">
          {currentUser ? (
            <>
              <span className="rbac-user-icon">{getRoleIcon(currentUser.role)}</span>
              <div className="rbac-user-meta">
                <div className="rbac-username">{currentUser.username}</div>
                <div className="rbac-role-row">
                  <span className={`rbac-role-badge ${getRoleBadgeClass(currentUser.role)}`}>
                    {currentUser.role}
                  </span>
                  <span className="rbac-clearance-tag">L{currentUser.clearance_level}</span>
                </div>
              </div>
              <span className="rbac-switch-arrow">⇄</span>
            </>
          ) : (
            <button className="btn-header-login">
              🔒 RBAC Login / Clearance
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
