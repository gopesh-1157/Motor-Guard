import type { FC } from 'react'
import type { DashboardStats } from '../types'

interface StatsBarProps {
  stats: DashboardStats
  activeFilter: string
  onFilterChange: (filter: string) => void
}

export const StatsBar: FC<StatsBarProps> = ({ stats, activeFilter, onFilterChange }) => {
  return (
    <div className="stats-bar">
      <div
        className={`stat-card blue ${activeFilter === 'all' ? 'active' : ''}`}
        onClick={() => onFilterChange('all')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon blue">⚡</div>
        <div className="stat-info">
          <div className="stat-value">{stats.totalMotors}</div>
          <div className="stat-label">Total Assets</div>
        </div>
      </div>

      <div
        className={`stat-card green ${activeFilter === 'healthy' ? 'active' : ''}`}
        onClick={() => onFilterChange('healthy')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon green">✓</div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--status-healthy)' }}>
            {stats.healthyCount}
          </div>
          <div className="stat-label">Normal / Healthy</div>
        </div>
      </div>

      <div
        className={`stat-card yellow ${activeFilter === 'warning' ? 'active' : ''}`}
        onClick={() => onFilterChange('warning')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon yellow">⚠</div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--status-warning)' }}>
            {stats.warningCount}
          </div>
          <div className="stat-label">Warning State</div>
        </div>
      </div>

      <div
        className={`stat-card red ${activeFilter === 'critical' ? 'active' : ''}`}
        onClick={() => onFilterChange('critical')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon red">✕</div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--status-critical)' }}>
            {stats.criticalCount}
          </div>
          <div className="stat-label">Critical Faults</div>
        </div>
      </div>

      <div
        className={`stat-card purple ${activeFilter === 'offline' ? 'active' : ''}`}
        onClick={() => onFilterChange('offline')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--status-stale)' }}>
          ⏱
        </div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--status-stale)' }}>
            {stats.offlineCount}
          </div>
          <div className="stat-label">Stale / Offline</div>
        </div>
      </div>

      <div
        className={`stat-card green ${activeFilter === 'hardware' ? 'active' : ''}`}
        onClick={() => onFilterChange('hardware')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--status-healthy)' }}>
          📡
        </div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--status-healthy)' }}>
            {stats.hardwareCount ?? 0}
          </div>
          <div className="stat-label">Hardware Nodes</div>
        </div>
      </div>

      <div
        className={`stat-card cyan ${activeFilter === 'simulator' ? 'active' : ''}`}
        onClick={() => onFilterChange('simulator')}
        style={{ cursor: 'pointer' }}
      >
        <div className="stat-icon cyan">⚙</div>
        <div className="stat-info">
          <div className="stat-value" style={{ color: 'var(--accent-cyan)' }}>
            {stats.simulatorCount}
          </div>
          <div className="stat-label">Simulators Active</div>
        </div>
      </div>
    </div>
  )
}
