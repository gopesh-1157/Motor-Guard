import { useState, useEffect, useRef, useCallback } from 'react'
import type {
  TelemetryMessage,
  MotorState,
  DashboardStats,
  ConnectionStatus,
  MotorHistoryPoint,
  UserProfile,
} from '../types'

const MAX_HISTORY_POINTS = 30
const STALE_TIMEOUT_MS = 15000 // 15s without heartbeat -> STALE (aligned with backend DEVICE_STALE_TIMEOUT_SEC=15)
const OFFLINE_TIMEOUT_MS = 35000 // 35s without heartbeat -> OFFLINE (aligned with backend DEVICE_OFFLINE_TIMEOUT_SEC=35)

export function useTelemetry(currentUser?: UserProfile | null) {
  const [motors, setMotors] = useState<Record<string, MotorState>>({})
  const [totalMessages, setTotalMessages] = useState<number>(0)
  const [wsConnected, setWsConnected] = useState<boolean>(false)
  const [esp32ApConnected, setEsp32ApConnected] = useState<boolean>(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const staleTimeoutRef = useRef<number>(STALE_TIMEOUT_MS)
  const offlineTimeoutRef = useRef<number>(OFFLINE_TIMEOUT_MS)

  // Update motor state with a new telemetry message
  const handleIncomingTelemetry = useCallback((msg: TelemetryMessage) => {
    setTotalMessages((prev) => prev + 1)
    const now = Date.now()

    setMotors((prev) => {
      const existing = prev[msg.motor_id]

      // HARDWARE PRIORITY:
      // If we are actively receiving live physical readings from ESP32 hardware,
      // prevent virtual simulator packets from overwriting this motor.
      if (existing && existing.source === 'hardware' && msg.source === 'simulator') {
        const timeSinceHardware = now - existing.lastSeen
        if (timeSinceHardware < 15000) {
          return prev
        }
      }

      const newHistoryPoint: MotorHistoryPoint = {
        timestamp: msg.timestamp,
        temperature: msg.sensors.temperature_c ?? null,
        current: msg.sensors.current_a ?? null,
        vibration: msg.sensors.vibration_g_rms ?? null,
        health_status: msg.inference.health_status,
      }

      const existingHistory = existing?.history || []
      const updatedHistory = [...existingHistory, newHistoryPoint].slice(-MAX_HISTORY_POINTS)

      const updatedMotor: MotorState = {
        ...existing,
        motor_id: msg.motor_id,
        device_id: msg.device_id,
        source: msg.source,
        latest: msg,
        history: updatedHistory,
        lastSeen: now,
        connectionStatus: 'online',
        thresholds: existing?.thresholds,
        effective_thresholds: existing?.effective_thresholds,
        electrical_specs: existing?.electrical_specs,
        mechanical_specs: existing?.mechanical_specs,
      }

      return {
        ...prev,
        [msg.motor_id]: updatedMotor,
      }
    })
  }, [])

  // Helper to extract bearer token for authenticated requests
  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = localStorage.getItem('motorguard_auth_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  // Fetch registered motors from backend registry
  const refreshMotors = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/motors', { headers: getAuthHeaders() })
      if (!res.ok) return
      const registeredList = await res.json()
      if (Array.isArray(registeredList)) {
        setMotors((prev) => {
          const next = { ...prev }
          for (const rm of registeredList) {
            if (next[rm.motor_id]) {
              next[rm.motor_id] = {
                ...next[rm.motor_id],
                thresholds: rm.thresholds,
                effective_thresholds: rm.effective_thresholds,
                electrical_specs: rm.electrical_specs,
                mechanical_specs: rm.mechanical_specs,
              }
            } else {
              next[rm.motor_id] = {
                motor_id: rm.motor_id,
                device_id: rm.assigned_device_id || 'unassigned',
                source: 'hardware',
                thresholds: rm.thresholds,
                effective_thresholds: rm.effective_thresholds,
                electrical_specs: rm.electrical_specs,
                mechanical_specs: rm.mechanical_specs,
                latest: {
                  schema_version: '1.0.0',
                  event_id: 'pending-registration',
                  device_id: rm.assigned_device_id || 'unassigned',
                  motor_id: rm.motor_id,
                  source: 'hardware',
                  seq: 0,
                  timestamp: new Date().toISOString(),
                  sensors: { temperature_c: null, current_a: null, vibration_g_rms: null },
                  sensor_status: { temperature: 'UNAVAILABLE', current: 'UNAVAILABLE', vibration: 'UNAVAILABLE' },
                  inference: {
                    status: 'SKIPPED',
                    health_status: rm.health_status || 'unknown',
                    confidence: 0,
                  },
                },
                history: [],
                lastSeen: 0,
                connectionStatus: rm.operational_state === 'OFFLINE'
                  ? 'offline'
                  : rm.operational_state === 'STALE'
                    ? 'stale'
                    : 'online',
              }
            }
          }
          return next
        })
      }
    } catch {
      // Backend not reached or offline
    }
  }, [getAuthHeaders])

  // Fetch recent telemetry points from MongoDB to populate live readings
  const fetchRecentTelemetry = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/telemetry/recent?limit=100', { headers: getAuthHeaders() })
      if (!res.ok) return
      const data = await res.json()
      const items = Array.isArray(data) ? data : (Array.isArray(data?.telemetry) ? data.telemetry : [])
      if (items.length > 0) {
        const sorted = [...items].reverse()
        for (const item of sorted) {
          handleIncomingTelemetry(item)
        }
      }
    } catch (err) {
      console.warn('[MotorGuard] Recent telemetry fetch skipped/unavailable:', err)
    }
  }, [getAuthHeaders, handleIncomingTelemetry])

  // WebSocket Connection Management
  const connectRef = useRef<() => void>(() => {})

  const connectWebSocket = useCallback(() => {
    const token = localStorage.getItem('motorguard_auth_token')
    if (!token) {
      setWsConnected(false)
      return
    }

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    // Resolve WebSocket endpoint (prefers VITE_WS_URL in production, otherwise relative to current host)
    const envWsUrl = (import.meta.env.VITE_WS_URL || '').trim()
    let wsEndpoint = ''
    if (envWsUrl) {
      const cleanUrl = envWsUrl.replace(/\/+$/, '')
      wsEndpoint = cleanUrl.endsWith('/ws/telemetry') ? cleanUrl : `${cleanUrl}/ws/telemetry`
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsEndpoint = `${protocol}//${window.location.host}/ws/telemetry`
    }

    try {
      // Primary: Subprotocol authentication (Sec-WebSocket-Protocol: access_token, <token>)
      // Prevents JWT credential leakage in HTTP reverse proxy logs & browser history
      let ws: WebSocket
      try {
        ws = new WebSocket(wsEndpoint, ['access_token', token])
      } catch {
        // Fallback to query parameter only if client runtime rejects subprotocols
        ws = new WebSocket(`${wsEndpoint}?token=${encodeURIComponent(token)}`)
      }
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
        reconnectAttemptsRef.current = 0
        console.log('[MotorGuard] WebSocket live bus connected (subprotocol authenticated)')
      }

      ws.onmessage = (event) => {
        try {
          const raw = JSON.parse(event.data)

          // Handle real-time alert broadcasts from the rules engine
          if (raw && raw.type === 'alert' && raw.data) {
            window.dispatchEvent(
              new CustomEvent('motorguard:alert', { detail: raw.data })
            )
            return
          }

          const parsed = (raw && raw.type === 'telemetry' && raw.data) ? raw.data : raw
          if (parsed && parsed.motor_id) {
            handleIncomingTelemetry(parsed as TelemetryMessage)
          }
        } catch (e) {
          console.error('[MotorGuard] Failed to parse WebSocket message:', e)
        }
      }

      ws.onclose = (event: CloseEvent) => {
        setWsConnected(false)
        wsRef.current = null

        const activeToken = localStorage.getItem('motorguard_auth_token')
        // Halt reconnection if token removed or server rejected auth (1008 Policy Violation, 4001, 4003)
        if (!activeToken || event.code === 1008 || event.code === 4001 || event.code === 4003) {
          console.warn('[MotorGuard] WebSocket closed due to auth rejection (code:', event.code, ')')
          return
        }

        // Bounded retry with exponential backoff for transient network disconnects
        const attempts = reconnectAttemptsRef.current
        if (attempts >= 8) {
          return
        }

        reconnectAttemptsRef.current += 1
        const backoffDelay = Math.min(1000 * Math.pow(1.5, attempts), 10000)

        if (!reconnectTimeoutRef.current) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectTimeoutRef.current = null
            connectRef.current()
          }, backoffDelay)
        }
      }

      ws.onerror = (err) => {
        console.warn('[MotorGuard] WebSocket warning:', err)
        ws.close()
      }
    } catch (e) {
      console.warn('[MotorGuard] WebSocket connection exception:', e)
    }
  }, [handleIncomingTelemetry])

  useEffect(() => {
    connectRef.current = connectWebSocket
  }, [connectWebSocket])

  // Initial and reactive data fetching on mount or currentUser change
  useEffect(() => {
    let isMounted = true

    async function initData() {
      // Do not request plant inventory, configuration, or telemetry until a
      // signed-in user has an authenticated session.
      if (!currentUser) {
        return
      }

      await refreshMotors()

      try {
        const sRes = await fetch('/api/v1/settings/thresholds', { headers: getAuthHeaders() })
        if (sRes.ok) {
          const sData = await sRes.json()
          if (sData.stale_timeout_sec) staleTimeoutRef.current = sData.stale_timeout_sec * 1000
          if (sData.offline_timeout_sec) offlineTimeoutRef.current = sData.offline_timeout_sec * 1000
        }
      } catch {
        // Keep defaults
      }

      if (isMounted) {
        await fetchRecentTelemetry()
        reconnectAttemptsRef.current = 0
        connectWebSocket()
      }
    }

    initData()

    return () => {
      isMounted = false
    }
  }, [currentUser, getAuthHeaders, refreshMotors, fetchRecentTelemetry, connectWebSocket])

  // Resilient Industrial Polling Fallback:
  // If WebSocket is disconnected or hasn't received frames, poll recent telemetry every 3s
  // so telemetry gauges and tables NEVER show empty/frozen N/A values.
  useEffect(() => {
    const pollTimer = window.setInterval(async () => {
      const token = localStorage.getItem('motorguard_auth_token')
      if (!token) return

      // If WebSocket is not in OPEN state, fetch latest readings via REST and attempt connect
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        await fetchRecentTelemetry()
        if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          connectRef.current()
        }
      }
    }, 3000)

    return () => clearInterval(pollTimer)
  }, [currentUser, fetchRecentTelemetry])

  // Periodic heartbeat / stale / offline evaluation timer
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now()
      setMotors((prev) => {
        let changed = false
        const updated: Record<string, MotorState> = {}

        for (const [id, motor] of Object.entries(prev)) {
          const elapsed = now - motor.lastSeen
          let newStatus: ConnectionStatus = 'online'

          if (elapsed > offlineTimeoutRef.current) {
            newStatus = 'offline'
          } else if (elapsed > staleTimeoutRef.current) {
            newStatus = 'stale'
          }

          if (newStatus !== motor.connectionStatus) {
            changed = true
            updated[id] = { ...motor, connectionStatus: newStatus }
          } else {
            updated[id] = motor
          }
        }

        return changed ? updated : prev
      })
    }, 2000)

    return () => clearInterval(timer)
  }, [])

  // Direct ESP32 SoftAP Auto-Bridge (http://192.168.4.1/api/telemetry)
  useEffect(() => {
    let active = true
    const pollESP32 = async () => {
      if (!currentUser) return

      try {
        const res = await fetch('http://192.168.4.1/api/telemetry', {
          mode: 'cors',
          cache: 'no-store',
        })
        if (res.ok && active) {
          const telemetryData = await res.json()
          if (telemetryData && telemetryData.motor_id) {
            setEsp32ApConnected(true)
            handleIncomingTelemetry(telemetryData as TelemetryMessage)

            // Forward to FastAPI backend for MongoDB persistence with authorization
            fetch('/api/v1/telemetry/ingest', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
              },
              body: JSON.stringify(telemetryData),
            }).catch(() => {})
          }
        }
      } catch {
        if (active) setEsp32ApConnected(false)
      }
    }

    const interval = setInterval(pollESP32, 1000)
    pollESP32()

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [currentUser, getAuthHeaders, handleIncomingTelemetry])

  // Calculate dashboard summary statistics
  const motorList = Object.values(motors)

  const clearTelemetry = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User logged out')
      wsRef.current = null
    }
    reconnectAttemptsRef.current = 0
    setMotors({})
    setTotalMessages(0)
    setEsp32ApConnected(false)
    setWsConnected(false)
  }, [])
  const stats: DashboardStats = {
    totalMotors: motorList.length,
    healthyCount: motorList.filter((m) => m.latest.inference.health_status === 'healthy' && m.connectionStatus !== 'offline').length,
    warningCount: motorList.filter((m) => m.latest.inference.health_status === 'warning' && m.connectionStatus !== 'offline').length,
    criticalCount: motorList.filter((m) => m.latest.inference.health_status === 'critical' && m.connectionStatus !== 'offline').length,
    offlineCount: motorList.filter((m) => m.connectionStatus === 'offline' || m.connectionStatus === 'stale').length,
    simulatorCount: motorList.filter((m) => m.source === 'simulator').length,
    hardwareCount: motorList.filter((m) => m.source === 'hardware').length,
    esp32ApConnected: esp32ApConnected || motorList.some((m) => m.source === 'hardware' && m.connectionStatus === 'online'),
    totalMessages,
    wsConnected,
  }

  // Inject a synthetic test motor telemetry event (useful for verification or sandbox testing)
  const injectSyntheticTelemetry = useCallback(
    (overrides?: Partial<TelemetryMessage>) => {
      const motorId = overrides?.motor_id || `MTR-${Math.floor(Math.random() * 3) + 1}`
      const baseTemp = 48 + Math.random() * 25
      const baseCurrent = 4.2 + Math.random() * 3.5
      const baseVib = 0.25 + Math.random() * 0.9

      const isWarning = baseTemp > 65 || baseVib > 0.8
      const isCritical = baseTemp > 75 || baseVib > 1.0

      const health = isCritical ? 'critical' : isWarning ? 'warning' : 'healthy'

      const synthetic: TelemetryMessage = {
        schema_version: '1.0.0',
        event_id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        device_id: `esp32-${motorId.toLowerCase()}`,
        motor_id: motorId,
        source: 'simulator',
        seq: totalMessages + 1,
        timestamp: new Date().toISOString(),
        sensors: {
          temperature_c: parseFloat(baseTemp.toFixed(1)),
          current_a: parseFloat(baseCurrent.toFixed(2)),
          vibration_g_rms: parseFloat(baseVib.toFixed(3)),
        },
        sensor_status: {
          temperature: 'OK',
          current: 'OK',
          vibration: 'OK',
        },
        inference: {
          status: 'PREDICTED',
          health_status: health,
          confidence: parseFloat((0.85 + Math.random() * 0.14).toFixed(3)),
          probabilities: {
            healthy: health === 'healthy' ? 0.92 : 0.05,
            warning: health === 'warning' ? 0.85 : 0.08,
            critical: health === 'critical' ? 0.88 : 0.03,
          },
          model_version: 'tflite-micro-v1.0.0',
          inference_time_ms: Math.floor(12 + Math.random() * 8),
        },
        diagnostics: {
          wifi_rssi_dbm: -58 - Math.floor(Math.random() * 15),
          free_heap_bytes: 142000 - Math.floor(Math.random() * 10000),
          uptime_seconds: 3600 + totalMessages * 2,
        },
        ...overrides,
      }

      handleIncomingTelemetry(synthetic)
    },
    [totalMessages, handleIncomingTelemetry]
  )

  return {
    motors,
    motorList,
    stats,
    wsConnected,
    totalMessages,
    connectWebSocket,
    injectSyntheticTelemetry,
    refreshMotors,
    clearTelemetry,
  }
}
