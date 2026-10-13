import type { FC, ReactNode } from 'react'
import { useState, useEffect } from 'react'
import type { NavigationTab, UserProfile, MotorState } from '../types'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useAnimePageTransition } from '../hooks/useAnimeMotion'

interface AppShellProps {
  currentTab: NavigationTab
  onTabChange: (tab: NavigationTab) => void
  wsConnected: boolean
  esp32HwConnected?: boolean
  totalMessages: number
  lastUpdatedIso?: string
  currentUser: UserProfile | null
  onOpenLogin: () => void
  motors: MotorState[]
  selectedMotorId: string
  onSelectMotor: (id: string) => void
  criticalAlertCount: number
  activeWorkOrderCount: number
  children: ReactNode
}

export const AppShell: FC<AppShellProps> = ({
  currentTab,
  onTabChange,
  wsConnected,
  esp32HwConnected,
  totalMessages,
  lastUpdatedIso,
  currentUser,
  onOpenLogin,
  motors,
  selectedMotorId,
  onSelectMotor,
  criticalAlertCount,
  activeWorkOrderCount,
  children,
}) => {
  // Collapsible sidebar state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('motorguard_sidebar_collapsed') === 'true'
  })

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('motorguard_sidebar_collapsed', String(next))
      return next
    })
  }

  // Theme state: default is industrial light (#F5F6F7), supports dark
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('motorguard_theme') as 'light' | 'dark') || 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('motorguard_theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  // Restrained Anime.js page transition
  const contentRef = useAnimePageTransition(currentTab)

  return (
    <div className="app-shell">
      {/* Persistent Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={onTabChange}
        collapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        criticalAlertCount={criticalAlertCount}
        activeWorkOrderCount={activeWorkOrderCount}
      />

      {/* Main Right Column */}
      <div className="app-main-column">
        {/* Compact Industrial Top Bar */}
        <TopBar
          currentTab={currentTab}
          wsConnected={wsConnected}
          esp32HwConnected={esp32HwConnected}
          totalMessages={totalMessages}
          lastUpdatedIso={lastUpdatedIso}
          currentUser={currentUser}
          onOpenLogin={onOpenLogin}
          theme={theme}
          onToggleTheme={toggleTheme}
          motors={motors}
          selectedMotorId={selectedMotorId}
          onSelectMotor={onSelectMotor}
        />

        {/* Content Area with smooth transition */}
        <main className="app-content-area" ref={contentRef}>
          {children}
        </main>
      </div>
    </div>
  )
}
