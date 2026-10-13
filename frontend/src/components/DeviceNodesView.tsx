import { useState, useEffect } from 'react'
import type { FC, FormEvent } from 'react'
import {
  Cpu,
  HardDrive,
  Plus,
  RefreshCw,
  Link,
  Unlink,
} from 'lucide-react'
import type { MotorState, EnrolledDevice, UserProfile } from '../types'

interface DeviceNodesViewProps {
  motors: MotorState[]
  esp32HwConnected?: boolean
  currentUser?: UserProfile | null
  onOpenLogin?: () => void
}

const FALLBACK_DEVICES: EnrolledDevice[] = [
  {
    device_id: 'esp32-node-001',
    device_type: 'ESP32 DevKit V1',
    board_variant: 'ESP32-D0WD-V3',
    firmware_version: '1.0.1-AP',
    site_id: 'SITE-PLANT-A',
    assigned_motor_id: 'MTR-775-001',
    enrollment_status: 'enrolled',
    availability: 'online',
    last_seen: new Date().toISOString(),
    configuration_version: 1,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
  },
  {
    device_id: 'sim-node-002',
    device_type: 'Virtual Simulated Node',
    board_variant: 'Python Async Engine',
    firmware_version: '1.0.0-SIM',
    site_id: 'SITE-PLANT-A',
    assigned_motor_id: 'MTR-775-002',
    enrollment_status: 'enrolled',
    availability: 'online',
    last_seen: new Date().toISOString(),
    configuration_version: 1,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
  },
  {
    device_id: 'sim-node-003',
    device_type: 'Virtual Simulated Node',
    board_variant: 'Python Async Engine',
    firmware_version: '1.0.0-SIM',
    site_id: 'SITE-PLANT-A',
    assigned_motor_id: 'MTR-775-003',
    enrollment_status: 'enrolled',
    availability: 'online',
    last_seen: new Date().toISOString(),
    configuration_version: 1,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
  },
]

export const DeviceNodesView: FC<DeviceNodesViewProps> = ({
  motors,
  esp32HwConnected,
  currentUser,
  onOpenLogin,
}) => {
  const [devices, setDevices] = useState<EnrolledDevice[]>(FALLBACK_DEVICES)
  const [isLoading, setIsLoading] = useState(false)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Enrollment Modal state
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false)
  const [newDeviceId, setNewDeviceId] = useState('')
  const [newDeviceType, setNewDeviceType] = useState('ESP32 DevKit V1')
  const [newBoardVariant, setNewBoardVariant] = useState('ESP32-D0WD-V3')
  const [newFirmwareVer, setNewFirmwareVer] = useState('1.0.1-AP')
  const [newSiteId, setNewSiteId] = useState('SITE-PLANT-A')

  // Assignment Modal state
  const [assigningDevice, setAssigningDevice] = useState<EnrolledDevice | null>(null)
  const [targetMotorId, setTargetMotorId] = useState('')

  const isAuthorized = !currentUser || currentUser.clearance_level >= 3

  // Load devices from backend API
  const fetchDevices = async () => {
    setIsLoading(true)
    setErrorMsg(null)
    try {
      const res = await fetch('/api/v1/devices')
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          setDevices(data)
          return
        }
      }
    } catch {
      // Fallback to local devices
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDevices()
  }, [])

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3500)
  }

  // Handle Enrollment submit
  const handleEnrollDevice = async (e: FormEvent) => {
    e.preventDefault()
    if (!isAuthorized) {
      onOpenLogin?.()
      return
    }

    if (!newDeviceId.trim()) {
      setErrorMsg('Device ID is required.')
      return
    }

    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const payload = {
        device_id: newDeviceId.trim(),
        device_type: newDeviceType,
        board_variant: newBoardVariant,
        firmware_version: newFirmwareVer,
        site_id: newSiteId,
      }

      const res = await fetch('/api/v1/devices/enroll', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        const created: EnrolledDevice = await res.json()
        setDevices((prev) => [created, ...prev.filter((d) => d.device_id !== created.device_id)])
        setIsEnrollModalOpen(false)
        setNewDeviceId('')
        showToast(`Device node '${created.device_id}' enrolled successfully.`)
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to enroll device node.')
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Network error enrolling device.')
    }
  }

  // Handle Device Assignment
  const handleAssignSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!assigningDevice || !targetMotorId) return

    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`/api/v1/devices/${assigningDevice.device_id}/assign`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ motor_id: targetMotorId }),
      })

      if (res.ok) {
        const updated: EnrolledDevice = await res.json()
        setDevices((prev) =>
          prev.map((d) => (d.device_id === updated.device_id ? updated : d))
        )
        setAssigningDevice(null)
        showToast(`Device '${updated.device_id}' assigned to ${targetMotorId}.`)
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to assign device.')
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating device assignment.')
    }
  }

  // Handle Device Unassignment
  const handleUnassignDevice = async (deviceId: string) => {
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(`/api/v1/devices/${deviceId}/unassign`, {
        method: 'POST',
        headers,
      })

      if (res.ok) {
        const updated: EnrolledDevice = await res.json()
        setDevices((prev) =>
          prev.map((d) => (d.device_id === updated.device_id ? updated : d))
        )
        showToast(`Device '${deviceId}' unassigned.`)
      }
    } catch {}
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast Notification */}
      {toastMsg && (
        <div
          style={{
            background: 'var(--status-healthy-bg)',
            border: '1px solid var(--status-healthy-border)',
            color: 'var(--status-healthy)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          ✓ {toastMsg}
        </div>
      )}

      {/* Page Header */}
      <div className="page-header">
        <div className="page-title-group">
          <h2 className="page-title">ESP32 Device Node Management</h2>
          <p className="page-description">
            Physical edge microcontrollers, MQTT client credentials, firmware versions, and motor asset mapping.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn-secondary" onClick={fetchDevices} disabled={isLoading}>
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          <button
            className="btn-primary"
            onClick={() => {
              if (!isAuthorized) {
                onOpenLogin?.()
              } else {
                setIsEnrollModalOpen(true)
              }
            }}
          >
            <Plus size={14} />
            <span>Enroll New ESP32 Node</span>
          </button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '14px',
        }}
      >
        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>
            ENROLLED NODES
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }} className="tabular-nums">
            {devices.length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Registered in gateway DB</span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--status-hardware)', fontWeight: 600 }}>
            PHYSICAL ESP32 NODES
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--status-hardware)' }} className="tabular-nums">
            {devices.filter((d) => d.device_id.startsWith('esp32')).length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Status: {esp32HwConnected ? 'Active SoftAP' : 'Standby Link'}
          </span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--status-sim)', fontWeight: 600 }}>
            SIMULATOR NODES
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--status-sim)' }} className="tabular-nums">
            {devices.filter((d) => d.device_id.startsWith('sim')).length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Virtual degradation daemon</span>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--status-healthy)', fontWeight: 600 }}>
            ACTIVE ASSIGNMENTS
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px', color: 'var(--status-healthy)' }} className="tabular-nums">
            {devices.filter((d) => !!d.assigned_motor_id).length} / {devices.length}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>1-to-1 asset association</span>
        </div>
      </div>

      {/* Enrolled Devices Table */}
      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 14px 0' }}>
          Registered Edge Hardware Nodes
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table className="compact-table" style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-main)' }}>
                <th style={{ padding: '10px 14px', textAlign: 'left' }}>Device Node ID</th>
                <th style={{ padding: '10px 14px', textAlign: 'left' }}>Hardware Model</th>
                <th style={{ padding: '10px 14px', textAlign: 'left' }}>Firmware</th>
                <th style={{ padding: '10px 14px', textAlign: 'left' }}>Assigned Motor</th>
                <th style={{ padding: '10px 14px', textAlign: 'left' }}>Site / Location</th>
                <th style={{ padding: '10px 14px', textAlign: 'center' }}>Connection</th>
                <th style={{ padding: '10px 14px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((dev) => {
                const isHw = dev.device_id.startsWith('esp32')
                const isOnline = isHw ? !!esp32HwConnected : true

                return (
                  <tr key={dev.device_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {isHw ? <Cpu size={16} color="var(--brand-primary)" /> : <HardDrive size={16} color="var(--status-sim)" />}
                        <span>{dev.device_id}</span>
                      </div>
                    </td>

                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>
                      {dev.device_type} ({dev.board_variant})
                    </td>

                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      v{dev.firmware_version}
                    </td>

                    <td style={{ padding: '10px 14px' }}>
                      {dev.assigned_motor_id ? (
                        <span style={{ fontWeight: 600, color: 'var(--brand-primary)' }}>
                          {dev.assigned_motor_id}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                          Unassigned (Spare)
                        </span>
                      )}
                    </td>

                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>
                      {dev.site_id}
                    </td>

                    <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                      <span className={`badge-status ${isOnline ? 'healthy' : 'warning'}`}>
                        {isOnline ? 'ONLINE' : 'STANDBY'}
                      </span>
                    </td>

                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        {dev.assigned_motor_id ? (
                          <button
                            className="btn-secondary"
                            onClick={() => handleUnassignDevice(dev.device_id)}
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Unassign device from motor"
                          >
                            <Unlink size={12} />
                            <span>Unassign</span>
                          </button>
                        ) : (
                          <button
                            className="btn-secondary"
                            onClick={() => {
                              setAssigningDevice(dev)
                              setTargetMotorId(motors[0]?.motor_id || '')
                            }}
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Assign to a motor"
                          >
                            <Link size={12} />
                            <span>Assign</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sensor Subsystems & Wiring Contract */}
      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 12px 0' }}>
          Physical Sensor Hardware Architecture &amp; Pinouts
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '0 0 16px 0' }}>
          Standardized sensor bus configurations deployed on physical ESP32 edge nodes.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          <div style={{ background: 'var(--bg-subtle)', padding: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '13px', color: 'var(--sensor-temp)' }}>DHT11 Temperature</strong>
              <span className="badge-status healthy" style={{ fontSize: '10px' }}>GPIO 4</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '6px 0' }}>
              1-Wire digital temperature interface. Sampled periodically with 1500 ms cooldown to prevent self-heating.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Range: 0–50 °C (&plusmn;2 °C) • Unit: Celsius
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '13px', color: 'var(--sensor-curr)' }}>ACS712 20A Current</strong>
              <span className="badge-status healthy" style={{ fontSize: '10px' }}>GPIO 34 (ADC1)</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '6px 0' }}>
              Hall-effect armature current sensor via 20k/10k voltage divider to protect 3.3V ESP32 ADC.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Sensitivity: 100 mV/A • Zero-point: 2.50V (divider: 1.67V)
            </div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '13px', color: 'var(--sensor-vib)' }}>ADXL345 Vibration</strong>
              <span className="badge-status healthy" style={{ fontSize: '10px' }}>I2C Bus 0 (21/22)</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '6px 0' }}>
              100 Hz synchronized 3-axis accelerometer. Dynamic RMS calculation with Earth gravity subtracted.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Range: &plusmn;16g • Output: dynamic g RMS
            </div>
          </div>
        </div>
      </div>

      {/* Device Enrollment Modal */}
      {isEnrollModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsEnrollModalOpen(false)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '520px', width: '90%' }}
          >
            <div className="modal-header">
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>Enroll New ESP32 Edge Node</h3>
              <button className="modal-close-btn" onClick={() => setIsEnrollModalOpen(false)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleEnrollDevice} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {errorMsg && (
                <div style={{ color: 'var(--status-critical)', fontSize: '12px', background: 'var(--status-critical-bg)', padding: '8px', borderRadius: '4px' }}>
                  {errorMsg}
                </div>
              )}

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Device Node ID *
                </label>
                <input
                  type="text"
                  placeholder="e.g. esp32-node-002"
                  value={newDeviceId}
                  onChange={(e) => setNewDeviceId(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                    Hardware Type
                  </label>
                  <input
                    type="text"
                    value={newDeviceType}
                    onChange={(e) => setNewDeviceType(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                    Board Variant
                  </label>
                  <input
                    type="text"
                    value={newBoardVariant}
                    onChange={(e) => setNewBoardVariant(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                    Firmware Version
                  </label>
                  <input
                    type="text"
                    value={newFirmwareVer}
                    onChange={(e) => setNewFirmwareVer(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                    Plant Site
                  </label>
                  <input
                    type="text"
                    value={newSiteId}
                    onChange={(e) => setNewSiteId(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="btn-secondary" onClick={() => setIsEnrollModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Enroll Device
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assignment Modal */}
      {assigningDevice && (
        <div className="modal-backdrop" onClick={() => setAssigningDevice(null)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '440px', width: '90%' }}
          >
            <div className="modal-header">
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>
                Assign Node: {assigningDevice.device_id}
              </h3>
              <button className="modal-close-btn" onClick={() => setAssigningDevice(null)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleAssignSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Select Motor Asset
                </label>
                <select
                  value={targetMotorId}
                  onChange={(e) => setTargetMotorId(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-main)' }}
                >
                  {motors.map((m) => (
                    <option key={m.motor_id} value={m.motor_id}>
                      {m.motor_id} (Currently: {m.device_id})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" className="btn-secondary" onClick={() => setAssigningDevice(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Confirm Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
