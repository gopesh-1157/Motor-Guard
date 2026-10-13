import { useState, useMemo, useEffect, useCallback, useRef } from 'react'
import { AppShell } from './components/AppShell'
import { OverviewView } from './components/OverviewView'
import { AnalyticsView } from './components/AnalyticsView'
import { ManagerView } from './components/ManagerView'
import { AlertsView } from './components/AlertsView'
import { TechnicianView } from './components/TechnicianView'
import { MotorDigitalTwin3D } from './components/MotorDigitalTwin3D'
import { DeviceNodesView } from './components/DeviceNodesView'
import { ReportsView } from './components/ReportsView'
import { SettingsView } from './components/SettingsView'
import { RBACLoginModal } from './components/RBACLoginModal'
import { MotorDetailModal } from './components/MotorDetailModal'
import { MotorManagementView } from './components/MotorManagementView'
import { LiveMonitoringView } from './components/LiveMonitoringView'
import { useTelemetry } from './hooks/useTelemetry'
import type { MotorState, AlertItem, NavigationTab, UserProfile } from './types'

const INITIAL_ALERTS: AlertItem[] = [
  {
    alert_id: 'ALT-20261010-CRIT01',
    motor_id: 'MTR-775-003',
    device_id: 'sim-node-003',
    severity: 'CRITICAL',
    trigger_type: 'THRESHOLD_HIGH_VIBRATION',
    trigger_value: 0.865,
    threshold_limit: 0.200,
    unit: 'g',
    message: 'CRITICAL bearing harmonic vibration on MTR-775-003: measured 0.865 g (limit 0.200 g)',
    state: 'ACTIVE',
    triggered_at: '2026-10-10T04:30:00.000Z',
    priority: 'CRITICAL',
  },
  {
    alert_id: 'ALT-20261010-WARN01',
    motor_id: 'MTR-775-002',
    device_id: 'sim-node-002',
    severity: 'WARNING',
    trigger_type: 'THRESHOLD_OVERTEMPERATURE',
    trigger_value: 54.8,
    threshold_limit: 50.0,
    unit: '°C',
    message: 'Thermal threshold warning on MTR-775-002: measured 54.8 °C (limit 50.0 °C)',
    state: 'ACTIVE',
    triggered_at: '2026-10-10T04:15:00.000Z',
    priority: 'HIGH',
  },
]

export default function App() {
  const {
    motorList,
    stats,
    wsConnected,
    totalMessages,
    injectSyntheticTelemetry,
    refreshMotors,
  } = useTelemetry()

  // Navigation tab state (defaulting to overview)
  const [currentTab, setCurrentTab] = useState<NavigationTab>('overview')

  // Selected motor ID for analytics & 3D inspection
  const [selectedMotorId, setSelectedMotorId] = useState<string>('MTR-775-001')

  // RBAC User Session state
  const [currentUser, setCurrentUser] = useState<UserProfile>(() => {
    try {
      const saved = localStorage.getItem('motorguard_auth_user')
      if (saved) return JSON.parse(saved)
    } catch {}
    return {
      username: 'manager_alice',
      role: 'Manager',
      email: 'alice.manager@factory.local',
      title: 'Operations Plant Manager',
      clearance_level: 3,
    }
  })
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false)

  // Selected motor for detail inspection modal
  const [selectedModalMotor, setSelectedModalMotor] = useState<MotorState | null>(null)

  // Alerts state for Manager & Technician workflows
  const [alerts, setAlerts] = useState<AlertItem[]>(INITIAL_ALERTS)

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
  alertHandlerRef.current = handleIncomingAlert

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

  // Fetch real alerts from backend API on mount
  useEffect(() => {
    async function ensureToken() {
      if (!localStorage.getItem('motorguard_auth_token')) {
        try {
          const res = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: 'manager_alice',
              password: 'managerpassword123',
            }),
          })
          if (res.ok) {
            const data = await res.json()
            localStorage.setItem('motorguard_auth_token', data.access_token)
          }
        } catch {}
      }
    }
    ensureToken()

    async function fetchAlerts() {
      try {
        const token = localStorage.getItem('motorguard_auth_token')
        const headers: Record<string, string> = {}
        if (token) headers['Authorization'] = `Bearer ${token}`
        const res = await fetch('/api/v1/alerts', { headers })
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data) && data.length > 0) {
            setAlerts(data)
          }
        }
      } catch {
        // Fallback to initial seeded alerts
      }
    }
    fetchAlerts()
  }, [])

  // Auto-seed initial 3 motors into fleet if empty so dashboard is immediately rich
  useEffect(() => {
    if (motorList.length === 0) {
      injectSyntheticTelemetry({
        motor_id: 'MTR-775-001',
        device_id: 'esp32-node-001',
        source: 'hardware',
        sensors: { temperature_c: 31.5, current_a: 0.15, vibration_g_rms: 0.015 },
        inference: {
          status: 'PREDICTED',
          health_status: 'healthy',
          confidence: 0.99,
          probabilities: { healthy: 0.99, warning: 0.01, critical: 0.0 },
          model_version: 'ei-motoguard-v1.0.1',
          inference_time_ms: 6,
        },
      })
      injectSyntheticTelemetry({
        motor_id: 'MTR-775-002',
        device_id: 'sim-node-002',
        source: 'simulator',
        sensors: { temperature_c: 54.8, current_a: 3.25, vibration_g_rms: 0.125 },
        inference: {
          status: 'PREDICTED',
          health_status: 'warning',
          confidence: 0.88,
          probabilities: { healthy: 0.08, warning: 0.88, critical: 0.04 },
          model_version: 'ei-motoguard-v1.0.1',
          inference_time_ms: 7,
        },
      })
      injectSyntheticTelemetry({
        motor_id: 'MTR-775-003',
        device_id: 'sim-node-003',
        source: 'simulator',
        sensors: { temperature_c: 44.2, current_a: 4.45, vibration_g_rms: 0.865 },
        inference: {
          status: 'PREDICTED',
          health_status: 'critical',
          confidence: 0.93,
          probabilities: { healthy: 0.01, warning: 0.06, critical: 0.93 },
          model_version: 'ei-motoguard-v1.0.1',
          inference_time_ms: 8,
        },
      })
    }
  }, [motorList.length, injectSyntheticTelemetry])

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

  // Logout action
  const handleLogout = () => {
    localStorage.removeItem('motorguard_auth_user')
    localStorage.removeItem('motorguard_auth_token')
    setCurrentUser({
      username: 'operator_bob',
      role: 'Operator',
      email: 'bob.operator@factory.local',
      title: 'Line Floor SCADA Operator',
      clearance_level: 1,
    })
  }

  // Manager action: Assign alert to technician
  const handleAssignAlert = (
    alertId: string,
    technician: string,
    priority: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL',
    instructions: string
  ) => {
    const nowIso = new Date().toISOString()
    setAlerts((prev) =>
      prev.map((a) => {
        if (a.alert_id === alertId) {
          return {
            ...a,
            assigned_to: technician,
            assigned_by: currentUser.username,
            assigned_at: nowIso,
            priority,
            instructions,
            state: 'ACKNOWLEDGED',
            acknowledged_at: nowIso,
            acknowledged_by: currentUser.username,
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

    setAlerts((prev) =>
      prev.map((a) => {
        if (a.alert_id === alertId) {
          return {
            ...a,
            state: 'RESOLVED',
            resolved_at: nowIso,
            resolved_by: currentUser.username,
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
      motors={motorList}
      selectedMotorId={selectedMotorId}
      onSelectMotor={setSelectedMotorId}
      criticalAlertCount={criticalAlertsCount}
      activeWorkOrderCount={assignedCount}
    >
      {/* 1. OVERVIEW DASHBOARD */}
      {(currentTab === 'overview' || currentTab === 'landing') && (
        <OverviewView
          stats={stats}
          motors={motorList}
          alerts={alerts}
          onSelectMotorForAnalytics={handleSelectMotorForAnalytics}
          onInspectMotorDetail={(m) => setSelectedModalMotor(m)}
          onNavigate={setCurrentTab}
          lastUpdatedIso={latestTelemetryIso}
          wsConnected={wsConnected}
        />
      )}

      {/* 2. MOTOR FLEET MANAGEMENT */}
      {(currentTab === 'fleet' || currentTab === 'motors') && (
        <MotorManagementView
          motors={motorList}
          currentUser={currentUser}
          onMotorRegistered={(newMotorId) => {
            refreshMotors?.()
            setSelectedMotorId(newMotorId)
          }}
          onOpenLogin={() => setIsLoginModalOpen(true)}
        />
      )}

      {/* 3. LIVE MONITORING STREAM */}
      {currentTab === 'live' && (
        <LiveMonitoringView
          motors={motorList}
          selectedMotorId={selectedMotorId}
          onSelectMotor={setSelectedMotorId}
          onInspectMotorDetail={(m) => setSelectedModalMotor(m)}
          wsConnected={wsConnected}
        />
      )}

      {/* 4. MOTOR ANALYTICS WORKSPACE */}
      {currentTab === 'analytics' && (
        <AnalyticsView
          motors={motorList}
          selectedMotorId={selectedMotorId}
          onSelectMotor={setSelectedMotorId}
          alerts={alerts}
        />
      )}

      {/* 4.5. 3D SPATIAL DIGITAL TWIN */}
      {currentTab === 'twin' && (
        <MotorDigitalTwin3D
          motors={motorList}
          selectedMotorId={selectedMotorId}
          onSelectMotor={setSelectedMotorId}
        />
      )}

      {/* 5. ALERTS & EVENTS MANAGEMENT — New Command Center */}
      {currentTab === 'alerts' && (
        <AlertsView
          alerts={alerts}
          motors={motorList}
          onAssignAlert={handleAssignAlert}
          onResolveAlert={handleResolveAlert}
          currentUser={currentUser}
          onOpenLogin={() => setIsLoginModalOpen(true)}
          onNavigateToMotor={(motorId) => {
            setSelectedMotorId(motorId)
            setCurrentTab('analytics')
          }}
        />
      )}

      {/* 5b. Legacy Manager Dispatch View */}
      {currentTab === 'manager' && (
        <ManagerView
          alerts={alerts}
          onAssignAlert={handleAssignAlert}
          currentUser={currentUser}
          onOpenLogin={() => setIsLoginModalOpen(true)}
        />
      )}

      {/* 6. MAINTENANCE WORKBENCH */}
      {(currentTab === 'maintenance' || currentTab === 'technician') && (
        <TechnicianView
          alerts={alerts}
          onResolveAlert={handleResolveAlert}
          currentUser={currentUser}
          onOpenLogin={() => setIsLoginModalOpen(true)}
        />
      )}

      {/* 7. ESP32 DEVICE NODES */}
      {currentTab === 'devices' && (
        <DeviceNodesView
          motors={motorList}
          esp32HwConnected={stats.esp32ApConnected}
          currentUser={currentUser}
          onOpenLogin={() => setIsLoginModalOpen(true)}
        />
      )}

      {/* 8. REPORTS */}
      {currentTab === 'reports' && (
        <ReportsView
          motors={motorList}
          alerts={alerts}
        />
      )}

      {/* 9. SETTINGS */}
      {currentTab === 'settings' && <SettingsView />}

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
