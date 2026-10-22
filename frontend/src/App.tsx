import { useState, useMemo, useEffect, useCallback, useRef, lazy, Suspense } from 'react'
import { AppShell } from './components/AppShell'
import { OverviewView } from './components/OverviewView'
import { LandingView } from './components/LandingView'
import { ErrorBoundary } from './components/ErrorBoundary'
import { RBACLoginModal } from './components/RBACLoginModal'
import { MotorDetailModal } from './components/MotorDetailModal'
import { useTelemetry } from './hooks/useTelemetry'
import type { MotorState, AlertItem, NavigationTab, UserProfile } from './types'

// Dynamic lazy-loaded view chunks to cut initial bundle size from 2.2 MB
const AnalyticsView = lazy(() => import('./components/AnalyticsView').then((m) => ({ default: m.AnalyticsView })))
const MotorDigitalTwin3D = lazy(() => import('./components/MotorDigitalTwin3D').then((m) => ({ default: m.MotorDigitalTwin3D })))
const MotorManagementView = lazy(() => import('./components/MotorManagementView').then((m) => ({ default: m.MotorManagementView })))
const LiveMonitoringView = lazy(() => import('./components/LiveMonitoringView').then((m) => ({ default: m.LiveMonitoringView })))
const AlertsView = lazy(() => import('./components/AlertsView').then((m) => ({ default: m.AlertsView })))
const ManagerView = lazy(() => import('./components/ManagerView').then((m) => ({ default: m.ManagerView })))
const TechnicianView = lazy(() => import('./components/TechnicianView').then((m) => ({ default: m.TechnicianView })))
const DeviceNodesView = lazy(() => import('./components/DeviceNodesView').then((m) => ({ default: m.DeviceNodesView })))
const ReportsView = lazy(() => import('./components/ReportsView').then((m) => ({ default: m.ReportsView })))
const SettingsView = lazy(() => import('./components/SettingsView').then((m) => ({ default: m.SettingsView })))
const UserManagementView = lazy(() => import('./components/UserManagementView').then((m) => ({ default: m.UserManagementView })))

const ViewLoadingFallback = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '360px', color: 'var(--text-muted)' }}>
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
      <div style={{ width: '28px', height: '28px', border: '2px solid rgba(6, 182, 212, 0.2)', borderTopColor: '#06b6d4', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <span style={{ fontSize: '11px', letterSpacing: '0.08em', fontWeight: 600 }}>LOADING MOTORGUARD MODULE...</span>
    </div>
  </div>
)

export default function App() {
  // RBAC User Session state (strictly defaults to null unless authenticated)
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    try {
      const savedUser = localStorage.getItem('motorguard_auth_user')
      const savedToken = localStorage.getItem('motorguard_auth_token')
      if (savedUser && savedToken) return JSON.parse(savedUser)
    } catch {}
    return null
  })

  const {
    motorList,
    stats,
    wsConnected,
    totalMessages,
    refreshMotors,
    clearTelemetry,
  } = useTelemetry(currentUser)

  // Navigation tab state (defaulting to overview)
  const [currentTab, setCurrentTab] = useState<NavigationTab>('overview')

  // Selected motor ID for analytics & 3D inspection
  const [selectedMotorId, setSelectedMotorId] = useState<string>('MTR-775-001')
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false)

  // Selected motor for detail inspection modal
  const [selectedModalMotor, setSelectedModalMotor] = useState<MotorState | null>(null)

  // Alerts state for Manager & Technician workflows
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(false)
  const [alertFetchError, setAlertFetchError] = useState<string | null>(null)

  // Helper: get auth headers for API calls
  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = localStorage.getItem('motorguard_auth_token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }, [])

  // Handle incoming alert from WebSocket broadcast
  const handleIncomingAlert = useCallback((alertData: AlertItem) => {
    setAlerts((prev) => {
      // De-duplicate by alert_id
      const exists = prev.find((a) => a.alert_id === alertData.alert_id)
      if (exists) {
        // Update existing alert in-place
        return prev.map((a) => (a.alert_id === alertData.alert_id ? { ...a, ...alertData } : a))
      }
      // Prepend new alert to the list
      return [alertData, ...prev]
    })
  }, [])

  // Expose the alert handler to the WebSocket hook via a stable ref
  const alertHandlerRef = useRef(handleIncomingAlert)
  useEffect(() => {
    alertHandlerRef.current = handleIncomingAlert
  }, [handleIncomingAlert])

  // Patch the WebSocket message handler to also process 'alert' type messages
  useEffect(() => {
    // Listen for custom alert events dispatched from the WebSocket
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (detail && detail.alert_id) {
        alertHandlerRef.current(detail as AlertItem)
      }
    }
    window.addEventListener('motorguard:alert', handler)
    return () => window.removeEventListener('motorguard:alert', handler)
  }, [])

  // Fetch real alerts from backend API on mount or auth update
  const fetchAlerts = useCallback(async () => {
    if (!currentUser) {
      setAlerts([])
      setAlertFetchError(null)
      setLoadingAlerts(false)
      return
    }

    setLoadingAlerts(true)
    setAlertFetchError(null)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch('/api/v1/alerts', { headers })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) {
          setAlerts(data)
          setAlertFetchError(null)
        } else {
          setAlertFetchError('Malformed alert response from gateway API')
        }
      } else {
        setAlertFetchError(`Alerts service unavailable (HTTP ${res.status})`)
      }
    } catch {
      setAlertFetchError('Network failure connecting to gateway alerts service')
    } finally {
      setLoadingAlerts(false)
    }
  }, [currentUser])

  useEffect(() => {
    fetchAlerts()
    refreshMotors()
  }, [currentUser, fetchAlerts, refreshMotors])

  // Count active critical alerts and assigned tickets
  const criticalAlertsCount = useMemo(() => {
    return alerts.filter((a) => a.severity === 'CRITICAL' && a.state !== 'RESOLVED').length
  }, [alerts])

  const assignedCount = useMemo(() => {
    return alerts.filter((a) => !!a.assigned_to && a.state !== 'RESOLVED').length
  }, [alerts])

  // Last telemetry timestamp across fleet
  const latestTelemetryIso = useMemo(() => {
    if (motorList.length === 0) return undefined
    return motorList[0]?.latest.timestamp
  }, [motorList])

  // Real Logout action: clear storage and set user to null
  const handleLogout = () => {
    localStorage.removeItem('motorguard_auth_user')
    localStorage.removeItem('motorguard_auth_token')
    setCurrentUser(null)
    setAlerts([])
    clearTelemetry()
    setCurrentTab('overview')
  }

  // Manager action: Assign alert to technician and persist work order
  const handleAssignAlert = (
    alertId: string,
    technician: string,
    priority: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL',
    instructions: string
  ) => {
    const nowIso = new Date().toISOString()
    const actor = currentUser?.username || 'admin'

    setAlerts((prev) =>
      prev.map((a) => {
        if (a.alert_id === alertId) {
          return {
            ...a,
            assigned_to: technician,
            assigned_by: actor,
            assigned_at: nowIso,
            priority,
            instructions,
            state: 'ACKNOWLEDGED',
            acknowledged_at: nowIso,
            acknowledged_by: actor,
          }
        }
        return a
      })
    )

    fetch(`/api/v1/alerts/${alertId}/assign`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        technician_username: technician,
        priority,
        instructions,
      }),
    }).catch(() => {})

    // Persist into MongoDB work_orders collection
    const targetAlert = alerts.find((a) => a.alert_id === alertId)
    const motorId = targetAlert ? targetAlert.motor_id : 'MTR-775-001'
    const woPriority = priority === 'NORMAL' ? 'MEDIUM' : priority
    fetch('/api/v1/work-orders', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        motor_id: motorId,
        alert_id: alertId,
        assigned_to_user_id: technician,
        priority: woPriority,
        title: `Maintenance on ${motorId}: ${targetAlert?.message || 'High Severity Fault'}`,
        description: instructions || 'Inspect motor bearing, measure dynamic vibration RMS and verify thermals.',
      }),
    }).catch(() => {})
  }

  // Technician action: Resolve alert
  const handleResolveAlert = (
    alertId: string,
    motorId: string,
    resolutionNotes: string,
    serviceType: string,
    partsReplaced: string[],
    downtimeMinutes: number
  ) => {
    const nowIso = new Date().toISOString()
    const actor = currentUser?.username || 'technician'

    setAlerts((prev) =>
      prev.map((a) => {
        if (a.alert_id === alertId) {
          return {
            ...a,
            state: 'RESOLVED',
            resolved_at: nowIso,
            resolved_by: actor,
            resolution_notes: resolutionNotes,
          }
        }
        return a
      })
    )

    fetch(`/api/v1/alerts/${alertId}/resolve`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ resolution_notes: resolutionNotes }),
    }).catch(() => {})

    fetch(`/api/v1/maintenance/motors/${motorId}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        motor_id: motorId,
        service_type: serviceType,
        summary: `Work order completed for ${alertId}`,
        details: resolutionNotes,
        parts_replaced: partsReplaced,
        downtime_minutes: downtimeMinutes,
      }),
    }).catch(() => {})
  }

  // Drilldown to analytics
  const handleSelectMotorForAnalytics = (motorId: string) => {
    setSelectedMotorId(motorId)
    setCurrentTab('analytics')
  }

  return (
    <AppShell
      currentTab={currentTab}
      onTabChange={setCurrentTab}
      wsConnected={wsConnected}
      esp32HwConnected={stats.esp32ApConnected}
      totalMessages={totalMessages}
      lastUpdatedIso={latestTelemetryIso}
      currentUser={currentUser}
      onOpenLogin={() => setIsLoginModalOpen(true)}
      onLogout={handleLogout}
      motors={motorList}
      selectedMotorId={selectedMotorId}
      onSelectMotor={setSelectedMotorId}
      criticalAlertCount={criticalAlertsCount}
      activeWorkOrderCount={assignedCount}
    >
      {/* 1. PUBLIC MARKETING LANDING PAGE OR AUTHENTICATED OVERVIEW DASHBOARD */}
      {(currentTab === 'overview' || currentTab === 'landing') && (
        !currentUser || currentTab === 'landing' ? (
          <LandingView
            stats={stats}
            criticalAlertsCount={criticalAlertsCount}
            onNavigate={(tab) => {
              // Marketing may describe workspaces, but every operational view
              // requires an authenticated session.
              if (!currentUser && tab !== 'landing') {
                setIsLoginModalOpen(true)
              } else {
                setCurrentTab(tab)
              }
            }}
            onOpenLogin={() => setIsLoginModalOpen(true)}
          />
        ) : (
          <OverviewView
            stats={stats}
            motors={motorList}
            alerts={alerts}
            loadingAlerts={loadingAlerts}
            alertFetchError={alertFetchError}
            onSelectMotorForAnalytics={handleSelectMotorForAnalytics}
            onInspectMotorDetail={(m) => setSelectedModalMotor(m)}
            onNavigate={setCurrentTab}
            lastUpdatedIso={latestTelemetryIso}
            wsConnected={wsConnected}
          />
        )
      )}

      {/* 2. MOTOR FLEET MANAGEMENT */}
      {(currentTab === 'fleet' || currentTab === 'motors') && (
        <ErrorBoundary fallbackTitle="Fleet Management Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <MotorManagementView
              motors={motorList}
              currentUser={currentUser}
              onMotorRegistered={(newMotorId) => {
                refreshMotors?.()
                setSelectedMotorId(newMotorId)
              }}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 3. LIVE MONITORING STREAM */}
      {currentTab === 'live' && (
        <ErrorBoundary fallbackTitle="Live Telemetry View Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <LiveMonitoringView
              motors={motorList}
              selectedMotorId={selectedMotorId}
              onSelectMotor={setSelectedMotorId}
              onInspectMotorDetail={(m) => setSelectedModalMotor(m)}
              wsConnected={wsConnected}
              alerts={alerts}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 4. MOTOR ANALYTICS WORKSPACE */}
      {currentTab === 'analytics' && (
        <ErrorBoundary fallbackTitle="Analytics View Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <AnalyticsView
              motors={motorList}
              selectedMotorId={selectedMotorId}
              onSelectMotor={setSelectedMotorId}
              alerts={alerts}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 4.5. 3D SPATIAL DIGITAL TWIN */}
      {currentTab === 'twin' && (
        <ErrorBoundary fallbackTitle="3D Digital Twin Unavailable" fallbackMessage="WebGL 3D Context could not be rendered or was lost.">
          <Suspense fallback={<ViewLoadingFallback />}>
            <MotorDigitalTwin3D
              motors={motorList}
              selectedMotorId={selectedMotorId}
              onSelectMotor={setSelectedMotorId}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 5. ALERTS & EVENTS MANAGEMENT */}
      {currentTab === 'alerts' && (
        <ErrorBoundary fallbackTitle="Alerts Center Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <AlertsView
              alerts={alerts}
              motors={motorList}
              loadingAlerts={loadingAlerts}
              alertFetchError={alertFetchError}
              onRetryFetchAlerts={fetchAlerts}
              onAssignAlert={handleAssignAlert}
              onResolveAlert={handleResolveAlert}
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
              onNavigateToMotor={(motorId) => {
                setSelectedMotorId(motorId)
                setCurrentTab('analytics')
              }}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 5b. Legacy Manager Dispatch View */}
      {currentTab === 'manager' && (
        <ErrorBoundary fallbackTitle="Manager Workbench Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <ManagerView
              alerts={alerts}
              onAssignAlert={handleAssignAlert}
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 6. MAINTENANCE WORKBENCH */}
      {(currentTab === 'maintenance' || currentTab === 'technician') && (
        <ErrorBoundary fallbackTitle="Maintenance Workbench Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <TechnicianView
              alerts={alerts}
              onResolveAlert={handleResolveAlert}
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 7. ESP32 DEVICE NODES */}
      {currentTab === 'devices' && (
        <ErrorBoundary fallbackTitle="Device Nodes Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <DeviceNodesView
              motors={motorList}
              esp32HwConnected={stats.esp32ApConnected}
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 8. REPORTS */}
      {currentTab === 'reports' && (
        <ErrorBoundary fallbackTitle="Reports View Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <ReportsView
              motors={motorList}
              alerts={alerts}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 9. SETTINGS */}
      {currentTab === 'settings' && (
        <ErrorBoundary fallbackTitle="Settings View Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <SettingsView
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* 10. USER MANAGEMENT (Admin-Only) */}
      {currentTab === 'users' && (
        <ErrorBoundary fallbackTitle="User Management Unavailable">
          <Suspense fallback={<ViewLoadingFallback />}>
            <UserManagementView
              currentUser={currentUser}
              onOpenLogin={() => setIsLoginModalOpen(true)}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* Motor Detail Modal */}
      <MotorDetailModal
        motor={selectedModalMotor}
        onClose={() => setSelectedModalMotor(null)}
      />

      {/* RBAC Login Modal */}
      <RBACLoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        currentUser={currentUser}
        onLoginSuccess={(u) => {
          setCurrentUser(u)
          setIsLoginModalOpen(false)
        }}
        onLogout={handleLogout}
      />
    </AppShell>
  )
}
