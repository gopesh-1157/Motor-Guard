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
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Sliders,
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
    { key: 'fleet', label: 'Motor Fleet', icon: Sliders },
    { key: 'live', label: 'Live Monitoring', icon: Activity },
    { key: 'analytics', label: 'Analytics', icon: LineChart },
    { key: 'alerts', label: 'Alerts & Events', icon: AlertTriangle, badge: criticalAlertCount },
    { key: 'maintenance', label: 'Maintenance', icon: Wrench, badge: activeWorkOrderCount },
    { key: 'devices', label: 'ESP32 Devices', icon: Cpu },
    { key: 'reports', label: 'Reports', icon: FileText },
    { key: 'settings', label: 'Settings', icon: Settings },
  ]

  // Role-based visibility filtering
  const visibleNavItems = navItems.filter((item) => {
    if (!currentUser) return item.key === 'overview'
    const role = currentUser.role
    if (role === 'Admin') return true
    if (role === 'Manager') {
      return ['overview', 'fleet', 'live', 'analytics', 'alerts', 'reports'].includes(item.key)
    }
    if (role === 'Technician') {
      return ['overview', 'maintenance', 'live', 'analytics'].includes(item.key)
    }
    if (role === 'Operator') {
      return ['overview', 'live'].includes(item.key)
    }
    return item.key === 'overview'
  })

  // Map legacy/alias tabs to standard keys for active highlight
  const normalizedTab = (tab: NavigationTab): NavigationTab => {
    if (tab === 'landing') return 'overview'
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
          title="MotorGuard Edge Gateway"
        >
          <div className="brand-icon-box">MG</div>
          {!collapsed && (
            <div className="brand-text-block">
              <span className="brand-name">MotorGuard</span>
              <span className="brand-tagline">Industrial Analytics</span>
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
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && item.badge && item.badge > 0 ? (
                <span className="sidebar-badge-count">{item.badge}</span>
              ) : null}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-info">
          <ShieldCheck size={16} color="var(--status-healthy)" />
          {!collapsed && <span>Edge Firmware v1.0.1</span>}
        </div>
      </div>
    </aside>
  )
}
