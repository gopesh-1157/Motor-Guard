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
  Box,
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
  interface NavSection {
    id: string
    title: string
    items: NavItem[]
  }

  const sections: NavSection[] = [
    {
      id: 'monitor',
      title: 'Monitor',
      items: [
        { key: 'overview', label: 'Overview', icon: LayoutDashboard },
        { key: 'twin', label: '3D Digital Twin', icon: Box },
        { key: 'live', label: 'Live Monitoring', icon: Activity },
        { key: 'analytics', label: 'Analytics & Diag', icon: LineChart },
      ],
    },
    {
      id: 'maintain',
      title: 'Maintain',
      items: [
        { key: 'alerts', label: 'Alerts & Events', icon: AlertTriangle, badge: criticalAlertCount },
        { key: 'maintenance', label: 'Work Orders', icon: Wrench, badge: activeWorkOrderCount },
        { key: 'landing', label: '3D Motor Tour', icon: Globe },
      ],
    },
    {
      id: 'manage',
      title: 'Manage',
      items: [
        { key: 'fleet', label: 'Motor Fleet', icon: Sliders },
        { key: 'devices', label: 'ESP32 Devices', icon: Cpu },
        { key: 'users', label: 'User Management', icon: Users },
      ],
    },
    {
      id: 'system',
      title: 'System',
      items: [
        { key: 'reports', label: 'Reports', icon: FileText },
        { key: 'settings', label: 'Settings', icon: Settings },
      ],
    },
  ]

  // Role-based item visibility check (strictly exactly 3 roles)
  const isItemVisible = (key: NavigationTab): boolean => {
    if (key === 'landing' || key === 'twin') return true
    if (!currentUser) return key === 'overview'
    const role = currentUser.role
    if (role === 'Admin') return true
    if (role === 'Manager') {
      return ['overview', 'twin', 'landing', 'fleet', 'devices', 'alerts', 'maintenance', 'live', 'analytics', 'users', 'reports'].includes(key)
    }
    if (role === 'Technician') {
      return ['overview', 'twin', 'landing', 'fleet', 'maintenance', 'live', 'analytics'].includes(key)
    }
    return key === 'overview'
  }

  const visibleSections = sections
    .map((sec) => ({
      ...sec,
      items: sec.items.filter((item) => isItemVisible(item.key)),
    }))
    .filter((sec) => sec.items.length > 0)

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
          <div className="brand-icon-box" style={{ background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-secondary) 100%)', color: '#0F172A', fontWeight: 800, border: 'none' }}>MG</div>
          {!collapsed && (
            <div className="brand-text-block">
              <span className="brand-name" style={{ letterSpacing: '0.04em' }}>MotorGuard</span>
              <span className="brand-tagline" style={{ fontFamily: 'var(--scada-mono-font)', fontSize: '9px', color: 'var(--brand-primary)' }}>
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

      <nav className="sidebar-nav-list" aria-label="Navigation Sections">
        {visibleSections.map((sec) => (
          <div key={sec.id} className="sidebar-section">
            <span className="sidebar-section-title">{sec.title}</span>
            {sec.items.map((item) => {
              const Icon = item.icon
              const isActive = activeKey === item.key

              return (
                <button
                  key={item.key}
                  className={`sidebar-item-btn ${isActive ? 'active' : ''}`}
                  onClick={() => onTabChange(item.key)}
                  title={collapsed ? item.label : undefined}
                  aria-label={item.label}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="sidebar-icon" size={18} />
                  {!collapsed && <span style={{ fontSize: '12.5px' }}>{item.label}</span>}
                  {!collapsed && item.badge && item.badge > 0 ? (
                    <span className="sidebar-badge-count">{item.badge}</span>
                  ) : null}
                </button>
              )
            })}
          </div>
        ))}
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
