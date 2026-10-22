import type { FC } from 'react'
import {
  LayoutDashboard,
  Activity,
  LineChart,
  AlertTriangle,
  Wrench,
  Cpu,
  FileText,
  Settings,
  Users,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Sliders,
  Globe,
} from 'lucide-react'
import type { NavigationTab, UserProfile } from '../types'

interface SidebarProps {
  currentTab: NavigationTab
  onTabChange: (tab: NavigationTab) => void
  collapsed: boolean
  onToggleCollapse: () => void
  criticalAlertCount: number
  activeWorkOrderCount: number
  currentUser?: UserProfile | null
}

interface NavItem {
  key: NavigationTab
  label: string
  icon: typeof LayoutDashboard
  badge?: number
}

export const Sidebar: FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  collapsed,
  onToggleCollapse,
  criticalAlertCount,
  activeWorkOrderCount,
  currentUser,
}) => {
  const navItems: NavItem[] = [
    { key: 'overview', label: 'Overview', icon: LayoutDashboard },
    { key: 'landing', label: '3D Motor Tour', icon: Globe },
    { key: 'fleet', label: 'Motor Fleet', icon: Sliders },
    { key: 'live', label: 'Live Monitoring', icon: Activity },
    { key: 'analytics', label: 'Analytics', icon: LineChart },
    { key: 'alerts', label: 'Alerts & Events', icon: AlertTriangle, badge: criticalAlertCount },
    { key: 'maintenance', label: 'Work Orders', icon: Wrench, badge: activeWorkOrderCount },
    { key: 'devices', label: 'ESP32 Devices', icon: Cpu },
    { key: 'users', label: 'User Management', icon: Users },
    { key: 'reports', label: 'Reports', icon: FileText },
    { key: 'settings', label: 'Settings', icon: Settings },
  ]

  // Role-based visibility filtering (strictly exactly 3 roles)
  const visibleNavItems = navItems.filter((item) => {
    if (item.key === 'landing') return true
    if (!currentUser) return item.key === 'overview'
    const role = currentUser.role
    if (role === 'Admin') return true
    if (role === 'Manager') {
      return ['overview', 'landing', 'fleet', 'devices', 'alerts', 'maintenance', 'live', 'analytics', 'reports'].includes(item.key)
    }
    if (role === 'Technician') {
      return ['overview', 'landing', 'fleet', 'maintenance', 'live', 'analytics'].includes(item.key)
    }
    return item.key === 'overview'
  })

  // Map legacy/alias tabs to standard keys for active highlight
  const normalizedTab = (tab: NavigationTab): NavigationTab => {
    if (tab === 'landing') return 'landing'
    if (tab === 'motors') return 'fleet'
    if (tab === 'manager') return 'alerts'
    if (tab === 'technician') return 'maintenance'
    return tab
  }

  const activeKey = normalizedTab(currentTab)

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`} aria-label="Main Navigation">
      <div className="sidebar-header">
        <div
          className="sidebar-brand"
          onClick={() => onTabChange('overview')}
          title="MotorGuard Edge Gateway DCS"
        >
          <div className="brand-icon-box" style={{ background: 'linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%)', border: '1px solid #3B82F6', fontWeight: 800 }}>MG</div>
          {!collapsed && (
            <div className="brand-text-block">
              <span className="brand-name" style={{ letterSpacing: '0.04em' }}>MotorGuard</span>
              <span className="brand-tagline" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '9px', color: '#93C5FD' }}>
                DCS // SCADA OT v2.4
              </span>
            </div>
          )}
        </div>

        <button
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          aria-label={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="sidebar-nav-list">
        {visibleNavItems.map((item) => {
          const Icon = item.icon
          const isActive = activeKey === item.key

          return (
            <button
              key={item.key}
              className={`sidebar-item-btn ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(item.key)}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="sidebar-icon" size={18} />
              {!collapsed && <span style={{ fontSize: '12.5px' }}>{item.label}</span>}
              {!collapsed && item.badge && item.badge > 0 ? (
                <span className="sidebar-badge-count">{item.badge}</span>
              ) : null}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-info" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '10px' }}>
          <ShieldCheck size={15} color="var(--status-healthy)" />
          {!collapsed && <span>IEC 61508 / ISO 10816</span>}
        </div>
      </div>
    </aside>
  )
}
