import { useState, useEffect, useId, useCallback } from 'react'
import type { FC, FormEvent } from 'react'
import {
  Plus,
  Cpu,
  CheckCircle,
  History,
  Edit,
  PowerOff,
} from 'lucide-react'
import type {
  RegisteredMotor,
  EnrolledDevice,
  AuditEvent,
  UserProfile,
  MotorState,
} from '../types'

interface MotorManagementViewProps {
  motors?: MotorState[]
  currentUser: UserProfile | null
  onMotorRegistered?: (motorId: string) => void
  onOpenLogin?: () => void
}

export const MotorManagementView: FC<MotorManagementViewProps> = ({
  currentUser,
  onMotorRegistered,
  onOpenLogin,
}) => {
  const isManagerOrAdmin = Boolean(
    currentUser && (currentUser.role === 'Manager' || currentUser.role === 'Admin' || currentUser.clearance_level >= 3)
  )

  // Core Data
  const [registeredMotors, setRegisteredMotors] = useState<RegisteredMotor[]>([])
  const [devices, setDevices] = useState<EnrolledDevice[]>([])
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  // Filtering
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'active' | 'inactive'>('ALL')
  const [siteFilter, setSiteFilter] = useState('ALL')

  // Modals
  const [isWizardOpen, setIsWizardOpen] = useState(false)
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false)
  const [isEnrollDeviceModalOpen, setIsEnrollDeviceModalOpen] = useState(false)
  const [editingMotor, setEditingMotor] = useState<RegisteredMotor | null>(null)
  const [disablingMotor, setDisablingMotor] = useState<RegisteredMotor | null>(null)

  // Wizard Step State
  const [step, setStep] = useState(1)
  const [wizardError, setWizardError] = useState<string | null>(null)

  // Wizard Form Fields
  const [wMotorId, setWMotorId] = useState('')
  const [wName, setWName] = useState('')
  const [wType, setWType] = useState('RS-775 Brushed DC')
  const [wManufacturer, setWManufacturer] = useState('Johnson Electric')
  const [wModelNumber, setWModelNumber] = useState('RS-775-12V-150W')
  const [wSerialNumber, setWSerialNumber] = useState('')
  const [wSiteId, setWSiteId] = useState('SITE-PLANT-A')
  const [wInstallationDate, setWInstallationDate] = useState('2026-10-11')
  const [wDescription, setWDescription] = useState('')

  // Specs
  const [wVoltage, setWVoltage] = useState(12.0)
  const [wRatedCurrent, setWRatedCurrent] = useState(2.5)
  const [wNoLoadCurrent, setWNoLoadCurrent] = useState(0.45)
  const [wRatedSpeed, setWRatedSpeed] = useState(12000)
  const [wMaxSpeed, setWMaxSpeed] = useState(18000)
  const [wRatedPower, setWRatedPower] = useState(30.0)
  const [wSupplyType, setWSupplyType] = useState('External DC supply')
  const [wLoad, setWLoad] = useState('Feed Conveyor Drive')

  // Device assignment
  const [wAssignMode, setWAssignMode] = useState<'existing' | 'new'>('existing')
  const [wSelectedDeviceId, setWSelectedDeviceId] = useState('')
  const [wNewDeviceId, setWNewDeviceId] = useState('')
  const [wNewDeviceVariant, setWNewDeviceVariant] = useState('ESP32-D0WD-V3')
  const [wNewDeviceFw, setWNewDeviceFw] = useState('1.0.1-AP')

  // Sensors & Pins
  const [wDhtPin, setWDhtPin] = useState(4)
  const [wDhtInterval, setWDhtInterval] = useState(1500)
  const [wDhtOffset, setWDhtOffset] = useState(0.0)

  const [wAdxlSda, setWAdxlSda] = useState(21)
  const [wAdxlScl, setWAdxlScl] = useState(22)
  const [wAdxlRange, setWAdxlRange] = useState<'2g' | '4g' | '8g' | '16g'>('16g')
  const [wAdxlRate, setWAdxlRate] = useState(100)

  const [wAcsPin, setWAcsPin] = useState(34)
  const [wAcsSensitivity, setWAcsSensitivity] = useState(100.0)
  const [wAcsZeroV, setWAcsZeroV] = useState(2.50)

  const [wOledEnabled, setWOledEnabled] = useState(true)
  const [wOledSda, setWOledSda] = useState(32)
  const [wOledScl, setWOledScl] = useState(33)

  // Thresholds
  const [wTempWarn, setWTempWarn] = useState(45.0)
  const [wTempCrit, setWTempCrit] = useState(50.0)
  const [wCurrWarn, setWCurrWarn] = useState(3.0)
  const [wCurrCrit, setWCurrCrit] = useState(4.0)
  const [wVibWarn, setWVibWarn] = useState(0.50)
  const [wVibCrit, setWVibCrit] = useState(1.00)

  // Edge Impulse AI
  const [wAiEnabled, setWAiEnabled] = useState(true)
  const [wModelName, setWModelName] = useState('MotoGuard_Motor_Health_inferencing')
  const [wModelVersion, setWModelVersion] = useState('v1.0.1')

  // Quick enroll device modal
  const [quickDevId, setQuickDevId] = useState('')
  const [quickDevType, setQuickDevType] = useState('ESP32')
  const [quickDevVariant, setQuickDevVariant] = useState('ESP32-D0WD-V3')

  // Edit config modal fields
  const [editTempWarn, setEditTempWarn] = useState(45.0)
  const [editTempCrit, setEditTempCrit] = useState(50.0)
  const [editCurrWarn, setEditCurrWarn] = useState(3.0)
  const [editCurrCrit, setEditCurrCrit] = useState(4.0)
  const [editVibWarn, setEditVibWarn] = useState(0.50)
  const [editVibCrit, setEditVibCrit] = useState(1.00)
  const [editAssignedDevice, setEditAssignedDevice] = useState('')

  // Unique IDs for form inputs
  const motorIdInputId = useId()
  const motorNameInputId = useId()
  const motorTypeInputId = useId()
  const mfrInputId = useId()
  const modelNoInputId = useId()
  const serialNoInputId = useId()
  const siteSelectId = useId()
  const installDateInputId = useId()
  const descInputId = useId()
  const voltageInputId = useId()
  const ratedCurrInputId = useId()
  const noLoadCurrInputId = useId()
  const ratedSpeedInputId = useId()
  const maxSpeedInputId = useId()
  const ratedPowerInputId = useId()
  const appLoadInputId = useId()
  const supplyTypeInputId = useId()
  const devSelectId = useId()
  const newDevIdInputId = useId()
  const newDevVariantInputId = useId()
  const newDevFwInputId = useId()
  const dhtPinInputId = useId()
  const dhtIntervalInputId = useId()
  const dhtOffsetInputId = useId()
  const adxlRangeSelectId = useId()
  const adxlRateInputId = useId()
  const adxlSdaInputId = useId()
  const adxlSclInputId = useId()
  const acsPinInputId = useId()
  const acsSensInputId = useId()
  const acsZeroVInputId = useId()
  const oledSdaInputId = useId()
  const oledSclInputId = useId()
  const tempWarnInputId = useId()
  const tempCritInputId = useId()
  const currWarnInputId = useId()
  const currCritInputId = useId()
  const vibWarnInputId = useId()
  const vibCritInputId = useId()
  const modelNameInputId = useId()
  const modelVerInputId = useId()
  const quickDevIdInputId = useId()
  const quickDevTypeSelectId = useId()
  const quickDevVariantInputId = useId()
  const editTempWarnInputId = useId()
  const editTempCritInputId = useId()
  const editCurrWarnInputId = useId()
  const editCurrCritInputId = useId()
  const editVibWarnInputId = useId()
  const editVibCritInputId = useId()
  const editDevSelectId = useId()

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3500)
  }

  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = currentUser?.token || localStorage.getItem('motorguard_auth_token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return headers
  }, [currentUser?.token])

  // Load motors and devices from backend API
  const loadData = useCallback(async () => {
    try {
      const [motorsRes, devicesRes] = await Promise.all([
        fetch('/api/v1/motors', { headers: getAuthHeaders() }),
        fetch('/api/v1/devices', { headers: getAuthHeaders() }),
      ])

      if (motorsRes.ok) {
        const motorsData = await motorsRes.json()
        setRegisteredMotors(motorsData)
      }
      if (devicesRes.ok) {
        const devicesData = await devicesRes.json()
        setDevices(devicesData)
      }
    } catch {
      setErrorMsg('Failed to connect to MotorGuard backend API. Ensure FastAPI is running on port 8000.')
    } finally {
      setIsLoading(false)
    }
  }, [getAuthHeaders])

  const loadAudit = async () => {
    try {
      const res = await fetch('/api/v1/motors/audit?limit=30', {
        headers: getAuthHeaders(),
      })
      if (res.ok) {
        const data = await res.json()
        setAuditEvents(data)
      }
    } catch {
      // audit endpoint error handling
    }
  }

  useEffect(() => {
    let isMounted = true
    const init = async () => {
      try {
        const [motorsRes, devicesRes] = await Promise.all([
          fetch('/api/v1/motors', { headers: getAuthHeaders() }),
          fetch('/api/v1/devices', { headers: getAuthHeaders() }),
        ])

        if (motorsRes.ok && isMounted) {
          const motorsData = await motorsRes.json()
          setRegisteredMotors(motorsData)
        }
        if (devicesRes.ok && isMounted) {
          const devicesData = await devicesRes.json()
          setDevices(devicesData)
        }
      } catch {
        if (isMounted) setErrorMsg('Failed to connect to MotorGuard backend API. Ensure FastAPI is running on port 8000.')
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    init()
    return () => {
      isMounted = false
    }
  }, [getAuthHeaders])

  // Pin conflict detection engine
  const detectPinConflicts = (): string[] => {
    const pinUsage: Record<number, string> = {}
    const conflicts: string[] = []

    const addPin = (pin: number, label: string) => {
      if (pinUsage[pin]) {
        conflicts.push(`GPIO ${pin} collision between ${label} and ${pinUsage[pin]}`)
      } else {
        pinUsage[pin] = label
      }
    }

    addPin(wDhtPin, 'DHT11 Data')
    addPin(wAcsPin, 'ACS712 Analog')
    addPin(wAdxlSda, 'ADXL345 SDA')
    addPin(wAdxlScl, 'ADXL345 SCL')
    if (wOledEnabled) {
      addPin(wOledSda, 'SH1106 OLED SDA')
      addPin(wOledScl, 'SH1106 OLED SCL')
    }

    return conflicts
  }

  const pinConflicts = detectPinConflicts()

  // Open Wizard
  const handleOpenWizard = () => {
    // Generate next motor ID recommendation
    const nextNum = registeredMotors.length + 1
    const pad = String(nextNum).padStart(3, '0')
    setWMotorId(`MTR-775-${pad}`)
    setWName(`Line ${nextNum} Feed Actuator`)
    setWSerialNumber(`SN-775-2026-${pad}`)
    setWizardError(null)
    setStep(1)
    setIsWizardOpen(true)
  }

  // Submit Wizard
  const handleCommitMotorRegistration = async (e?: FormEvent) => {
    if (e) e.preventDefault()
    setWizardError(null)

    if (!isManagerOrAdmin) {
      onOpenLogin?.()
      return
    }

    if (pinConflicts.length > 0) {
      setWizardError(`Cannot register motor: Please resolve pin conflicts:\n${pinConflicts.join('\n')}`)
      return
    }

    if (wTempWarn >= wTempCrit) {
      setWizardError('Temperature warning threshold must be strictly less than critical limit!')
      return
    }
    if (wCurrWarn >= wCurrCrit) {
      setWizardError('Current warning threshold must be strictly less than critical limit!')
      return
    }
    if (wVibWarn >= wVibCrit) {
      setWizardError('Vibration warning threshold must be strictly less than critical limit!')
      return
    }

    try {
      let finalAssignedDeviceId = wAssignMode === 'existing' ? wSelectedDeviceId : wNewDeviceId

      // If enrolling a new device on the fly, call device enrollment first
      if (wAssignMode === 'new' && wNewDeviceId) {
        const enrollRes = await fetch('/api/v1/devices/enroll', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            device_id: wNewDeviceId.trim(),
            device_type: 'ESP32',
            board_variant: wNewDeviceVariant,
            firmware_version: wNewDeviceFw,
            site_id: wSiteId,
          }),
        })
        if (!enrollRes.ok) {
          const errData = await enrollRes.json()
          if (errData.detail && errData.detail.toLowerCase().includes('already enrolled')) {
            console.warn(`Device ${wNewDeviceId} is already enrolled; associating directly.`)
          } else {
            setWizardError(`Failed to enroll ESP32 device: ${errData.detail || 'Unknown error'}`)
            return
          }
        }
      }

      // Payload for Motor Creation
      const motorPayload = {
        motor_id: wMotorId.trim(),
        name: wName.trim(),
        motor_type: wType,
        manufacturer: wManufacturer || null,
        model_number: wModelNumber || null,
        serial_number: wSerialNumber || null,
        site_id: wSiteId,
        installation_date: wInstallationDate || null,
        description: wDescription || null,
        status: 'active',
        electrical_specs: {
          motor_type: wType,
          rated_voltage_v: Number(wVoltage),
          rated_current_a: Number(wRatedCurrent),
          no_load_current_a: Number(wNoLoadCurrent) || null,
          rated_speed_rpm: Number(wRatedSpeed) || null,
          max_speed_rpm: Number(wMaxSpeed) || null,
          rated_power_w: Number(wRatedPower) || null,
          motor_supply_type: wSupplyType,
          application_load: wLoad || null,
        },
        sensors_config: {
          dht11: {
            sensor_type: 'DHT11',
            gpio_pin: Number(wDhtPin),
            unit: '°C',
            sampling_interval_ms: Number(wDhtInterval),
            enabled: true,
            calibration_offset_c: Number(wDhtOffset),
          },
          adxl345: {
            sensor_type: 'ADXL345',
            i2c_bus: 0,
            sda_pin: Number(wAdxlSda),
            scl_pin: Number(wAdxlScl),
            measurement_range_g: wAdxlRange,
            sample_frequency_hz: Number(wAdxlRate),
            axes: ['X', 'Y', 'Z'],
            output_feature: 'dynamic_rms_acceleration',
            measurement_unit: 'g RMS',
            calibration_offset_g: 0.0,
            enabled: true,
          },
          acs712: {
            sensor_type: 'ACS712-20A',
            analog_gpio_pin: Number(wAcsPin),
            module_supply_v: 5.0,
            sensitivity_mv_per_a: Number(wAcsSensitivity),
            zero_current_voltage_v: Number(wAcsZeroV),
            voltage_divider_ratio: 0.6667,
            output_unit: 'A',
            enabled: true,
          },
          sh1106: {
            display_type: 'SH1106',
            i2c_bus: 1,
            sda_pin: Number(wOledSda),
            scl_pin: Number(wOledScl),
            i2c_address: '0x3C',
            enabled: wOledEnabled,
          },
        },
        thresholds: {
          temperature_warning_c: Number(wTempWarn),
          temperature_critical_c: Number(wTempCrit),
          current_warning_a: Number(wCurrWarn),
          current_critical_a: Number(wCurrCrit),
          vibration_warning_g: Number(wVibWarn),
          vibration_critical_g: Number(wVibCrit),
          device_offline_timeout_sec: 35,
          alert_persistence_sec: 10,
          alert_cooldown_sec: 60,
          hysteresis_percentage: 5.0,
        },
        edge_impulse_config: {
          enabled: wAiEnabled,
          model_name: wModelName,
          model_version: wModelVersion,
          deployment_type: 'ESP32 embedded inference',
          expected_input_format: 'ADXL345 dynamic RMS (100 Hz, 50 samples) + ACS712 + DHT11',
          sample_frequency_hz: 100,
          window_length_ms: 500,
          class_mapping: ['healthy', 'warning', 'critical'],
        },
        assigned_device_id: finalAssignedDeviceId || null,
      }

      const res = await fetch('/api/v1/motors', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(motorPayload),
      })

      if (!res.ok) {
        const errData = await res.json()
        setWizardError(`Failed to register motor: ${errData.detail || 'Validation error'}`)
        return
      }

      const newMotor = await res.json()
      showToast(`Successfully registered ${newMotor.motor_id} in plant fleet!`)
      setIsWizardOpen(false)
      loadData()
      onMotorRegistered?.(newMotor.motor_id)
    } catch (err: any) {
      setWizardError(`Error registering motor: ${err.message}`)
    }
  }

  // Quick enroll ESP32 device
  const handleQuickEnrollDevice = async (e: FormEvent) => {
    e.preventDefault()
    if (!quickDevId.trim()) return

    try {
      const res = await fetch('/api/v1/devices/enroll', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          device_id: quickDevId.trim(),
          device_type: quickDevType,
          board_variant: quickDevVariant,
          firmware_version: '1.0.1-AP',
          site_id: 'SITE-PLANT-A',
        }),
      })

      if (!res.ok) {
        const errData = await res.json()
        alert(`Error: ${errData.detail || 'Enrollment failed'}`)
        return
      }

      showToast(`ESP32 node '${quickDevId}' enrolled successfully!`)
      setQuickDevId('')
      setIsEnrollDeviceModalOpen(false)
      loadData()
    } catch (err: any) {
      alert(`Enrollment failed: ${err.message}`)
    }
  }

  // Open Edit Motor Configuration Modal
  const handleOpenEdit = (motor: RegisteredMotor) => {
    setEditingMotor(motor)
    setEditTempWarn(motor.thresholds.temperature_warning_c)
    setEditTempCrit(motor.thresholds.temperature_critical_c)
    setEditCurrWarn(motor.thresholds.current_warning_a)
    setEditCurrCrit(motor.thresholds.current_critical_a)
    setEditVibWarn(motor.thresholds.vibration_warning_g)
    setEditVibCrit(motor.thresholds.vibration_critical_g)
    setEditAssignedDevice(motor.assigned_device_id || '')
  }

  // Save Edit Configuration
  const handleSaveEditConfig = async (e: FormEvent) => {
    e.preventDefault()
    if (!editingMotor) return

    if (editTempWarn >= editTempCrit || editCurrWarn >= editCurrCrit || editVibWarn >= editVibCrit) {
      alert('Validation error: Warning thresholds must be strictly less than critical thresholds!')
      return
    }

    try {
      const res = await fetch(`/api/v1/motors/${editingMotor.motor_id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          thresholds: {
            temperature_warning_c: Number(editTempWarn),
            temperature_critical_c: Number(editTempCrit),
            current_warning_a: Number(editCurrWarn),
            current_critical_a: Number(editCurrCrit),
            vibration_warning_g: Number(editVibWarn),
            vibration_critical_g: Number(editVibCrit),
            device_offline_timeout_sec: 35,
            alert_persistence_sec: 10,
            alert_cooldown_sec: 60,
            hysteresis_percentage: 5.0,
            calibration_status: editingMotor.thresholds.calibration_status || 'provisional',
            provenance: editingMotor.thresholds.provenance || 'Motor management console configured',
          },
          assigned_device_id: editAssignedDevice || null,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        alert(`Failed to update motor: ${err.detail || 'Unknown error'}`)
        return
      }

      showToast(`Updated configuration for ${editingMotor.motor_id} (Config v${editingMotor.configuration_version + 1})`)
      setEditingMotor(null)
      loadData()
    } catch (err: any) {
      alert(`Error updating motor: ${err.message}`)
    }
  }

  // Disable Motor
  const handleConfirmDisable = async () => {
    if (!disablingMotor) return

    try {
      const res = await fetch(`/api/v1/motors/${disablingMotor.motor_id}/disable`, {
        method: 'POST',
        headers: getAuthHeaders(),
      })
      if (!res.ok) {
        const err = await res.json()
        alert(`Failed: ${err.detail || 'Could not disable motor'}`)
        return
      }
      showToast(`Motor ${disablingMotor.motor_id} marked as inactive`)
      setDisablingMotor(null)
      loadData()
    } catch (err: any) {
      alert(`Error: ${err.message}`)
    }
  }

  // Filtered Motors List
  const filteredMotors = registeredMotors.filter((m) => {
    if (statusFilter !== 'ALL' && m.status !== statusFilter) return false
    if (siteFilter !== 'ALL' && m.site_id !== siteFilter) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const matchId = m.motor_id.toLowerCase().includes(q)
      const matchName = m.name.toLowerCase().includes(q)
      const matchDevice = (m.assigned_device_id || '').toLowerCase().includes(q)
      if (!matchId && !matchName && !matchDevice) return false
    }
    return true
  })

  return (
    <div className="manager-container">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="manager-toast">
          <span>✓</span> {toastMsg}
        </div>
      )}

      {/* Page Header */}
      <div className="manager-header">
        <div>
          <div className="manager-pretitle">FLEET ENGINEERING &amp; HARDWARE PROVISIONING</div>
          <h1 className="manager-title">Motor Management &amp; ESP32 Registry</h1>
          <p className="manager-desc">
            Register physical motors, configure multi-sensor calibration profiles, link edge telemetry nodes, and enforce deterministic safety trip limits.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            className="btn-secondary"
            onClick={() => {
              loadAudit()
              setIsAuditModalOpen(true)
            }}
          >
            <History size={15} /> Audit Trail
          </button>

          <button
            className="btn-secondary"
            onClick={() => setIsEnrollDeviceModalOpen(true)}
          >
            <Cpu size={15} /> Enroll ESP32
          </button>

          <button
            className="btn-primary"
            onClick={handleOpenWizard}
            title={!isManagerOrAdmin ? 'Requires Level 3 Manager or Admin Clearance' : 'Register Motor'}
          >
            <Plus size={16} /> Register Physical Motor
          </button>
        </div>
      </div>

      {/* RBAC Notice if unauthorized */}
      {!isManagerOrAdmin && (
        <div className="rbac-clearance-warning-banner">
          <div className="warning-text">
            🔒 <strong>Clearance Notice:</strong> Motor Provisioning and ESP32 enrollment require <strong>Level 3 (Manager)</strong> or <strong>Level 4 (Admin)</strong> clearance.
            Currently logged in as <code>{currentUser?.username || 'Guest'}</code>. Hardware mutations are in view-only mode.
          </div>
          {onOpenLogin && (
            <button className="btn-elevate-role" onClick={onOpenLogin}>
              ⚡ Switch to Manager Alice
            </button>
          )}
        </div>
      )}

      {/* Error Notice */}
      {errorMsg && (
        <div className="critical-dispatch-banner">
          <div className="banner-icon-pulse">⚠️</div>
          <div className="banner-content">
            <div className="banner-title">API Connection Alert</div>
            <div className="banner-sub">{errorMsg}</div>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="filter-controls-container">
        <div className="filter-search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="search-input"
            placeholder="Search by Motor ID, Name, or Device ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>✕</button>
          )}
        </div>

        <div className="filter-pills-row">
          <div className="filter-group">
            <span className="filter-label">Status:</span>
            <div className="pill-group">
              {(['ALL', 'active', 'inactive'] as const).map((st) => (
                <button
                  key={st}
                  className={`filter-pill ${statusFilter === st ? 'active' : ''}`}
                  onClick={() => setStatusFilter(st)}
                >
                  {st.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <span className="filter-label">Site:</span>
            <div className="pill-group">
              {['ALL', 'SITE-PLANT-A'].map((site) => (
                <button
                  key={site}
                  className={`filter-pill ${siteFilter === site ? 'active' : ''}`}
                  onClick={() => setSiteFilter(site)}
                >
                  {site}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Fleet Inventory Table */}
      <div className="chart-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-main)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)' }}>
              Registered Motor Fleet ({filteredMotors.length} Assets)
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '10px' }}>
              Persistent MongoDB Asset Records with ESP32 Hardware Associations
            </span>
          </div>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--brand-primary)' }}>
            {devices.filter((d) => d.availability === 'online').length} Nodes Online
          </span>
        </div>

        {isLoading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading motor registry...
          </div>
        ) : filteredMotors.length === 0 ? (
          <div className="empty-incidents-box" style={{ margin: '20px' }}>
            <div className="empty-icon">⚙</div>
            <h3>No Motors Found</h3>
            <p>No motors match your query or site filter. Click &ldquo;Register Physical Motor&rdquo; to add a new motor.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="telemetry-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>MOTOR ID</th>
                  <th>NAME &amp; LOAD</th>
                  <th>ASSIGNED ESP32</th>
                  <th>ELECTRICAL SPECS</th>
                  <th>HEALTH STATE</th>
                  <th>OP STATUS</th>
                  <th>VER</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {filteredMotors.map((m) => {
                  const assignedDevice = devices.find((d) => d.device_id === m.assigned_device_id)
                  const isOnline = assignedDevice?.availability === 'online'

                  return (
                    <tr key={m.motor_id}>
                      <td>
                        <strong style={{ fontFamily: 'monospace', fontSize: '13px', color: 'var(--text-main)' }}>
                          {m.motor_id}
                        </strong>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{m.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {m.motor_type} • {m.electrical_specs?.application_load || 'General Drive'}
                        </div>
                      </td>
                      <td>
                        {m.assigned_device_id ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: 600 }}>
                              {m.assigned_device_id}
                            </span>
                            <span className={`badge ${isOnline ? 'online' : 'offline'}`} style={{ padding: '2px 5px', fontSize: '9px' }}>
                              {isOnline ? 'ONLINE' : 'OFFLINE'}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>— Unassigned —</span>
                        )}
                      </td>
                      <td>
                        <div style={{ fontSize: '12px', fontFeatureSettings: 'tnum', fontWeight: 600 }}>
                          {m.electrical_specs?.rated_voltage_v}V • {m.electrical_specs?.rated_current_a}A
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {m.electrical_specs?.rated_power_w ? `${m.electrical_specs.rated_power_w}W` : 'DC Supply'}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${m.health_status.toLowerCase()}`}>
                          {m.health_status.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${m.status === 'active' ? 'online' : 'offline'}`}>
                          {m.status.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-muted)' }}>
                          v{m.configuration_version}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            className="btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            onClick={() => handleOpenEdit(m)}
                            title="Edit Configuration & Thresholds"
                          >
                            <Edit size={12} /> Config
                          </button>
                          {m.status === 'active' ? (
                            <button
                              className="btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '11px', color: 'var(--status-critical)' }}
                              onClick={() => setDisablingMotor(m)}
                              title="Deactivate motor"
                            >
                              <PowerOff size={12} />
                            </button>
                          ) : (
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Inactive</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ==============================================================================
          7-STEP ADD MOTOR MULTI-STEP REGISTRATION WIZARD MODAL
          ============================================================================== */}
      {isWizardOpen && (
        <div className="modal-backdrop" onClick={() => setIsWizardOpen(false)}>
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '780px', maxHeight: '92vh' }}
          >
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Register Physical Motor Asset</h3>
                <div className="modal-subtitle">
                  Step {step} of 7: {
                    step === 1 ? 'Motor Identity & Plant Association' :
                    step === 2 ? 'Electrical & Mechanical Specifications' :
                    step === 3 ? 'ESP32 Device Node Assignment' :
                    step === 4 ? 'Sensor Subsystems & GPIO Mapping' :
                    step === 5 ? 'Deterministic Health Safety Thresholds' :
                    step === 6 ? 'Edge Impulse TinyML Model Profile' :
                    'Configuration Review & Final Commitment'
                  }
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsWizardOpen(false)}>✕</button>
            </div>

            {/* Stepper Progress Bar */}
            <div style={{ display: 'flex', background: 'var(--bg-app)', borderBottom: '1px solid var(--border-main)', padding: '10px 16px', gap: '4px' }}>
              {[1, 2, 3, 4, 5, 6, 7].map((s) => (
                <div
                  key={s}
                  onClick={() => setStep(s)}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    padding: '6px 2px',
                    fontSize: '11px',
                    fontWeight: 600,
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: step === s ? 'var(--brand-primary)' : step > s ? 'rgba(49, 95, 206, 0.15)' : 'transparent',
                    color: step === s ? '#FFFFFF' : step > s ? 'var(--brand-primary)' : 'var(--text-muted)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {s}. {
                    s === 1 ? 'Identity' :
                    s === 2 ? 'Specs' :
                    s === 3 ? 'Device' :
                    s === 4 ? 'Sensors' :
                    s === 5 ? 'Limits' :
                    s === 6 ? 'AI ML' : 'Review'
                  }
                </div>
              ))}
            </div>

            <form onSubmit={handleCommitMotorRegistration}>
              <div className="modal-body" style={{ maxHeight: 'calc(92vh - 180px)', overflowY: 'auto' }}>
                {wizardError && (
                  <div className="critical-dispatch-banner" style={{ margin: '0 0 14px 0' }}>
                    <div className="banner-icon-pulse">⚠️</div>
                    <div className="banner-content">
                      <div className="banner-title">Registration Notice</div>
                      <div className="banner-sub">{wizardError}</div>
                    </div>
                  </div>
                )}

                {/* STEP 1: MOTOR IDENTITY */}
                {step === 1 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div className="form-group">
                      <label htmlFor={motorIdInputId} className="form-label">Motor ID (Unique Identifier) *</label>
                      <input
                        id={motorIdInputId}
                        type="text"
                        className="form-textarea"
                        style={{ height: '38px', fontFamily: 'monospace' }}
                        value={wMotorId}
                        onChange={(e) => setWMotorId(e.target.value)}
                        placeholder="e.g. MTR-775-004"
                        required
                      />
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Permanent stable asset ID. Do not use volatile IP or MAC addresses.
                      </span>
                    </div>

                    <div className="form-group">
                      <label htmlFor={motorNameInputId} className="form-label">Motor Name / Functional Role *</label>
                      <input
                        id={motorNameInputId}
                        type="text"
                        className="form-textarea"
                        style={{ height: '38px' }}
                        value={wName}
                        onChange={(e) => setWName(e.target.value)}
                        placeholder="e.g. Line 4 Conveyor Feed Actuator"
                        required
                      />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={motorTypeInputId} className="form-label">Motor Construction Type *</label>
                        <select
                          id={motorTypeInputId}
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wType}
                          onChange={(e) => setWType(e.target.value)}
                        >
                          <option value="RS-775 Brushed DC">RS-775 Brushed DC</option>
                          <option value="Brushed DC">Standard Brushed DC</option>
                          <option value="Brushless DC (BLDC)">Brushless DC (BLDC)</option>
                          <option value="AC Induction">AC Induction Motor</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor={mfrInputId} className="form-label">Manufacturer</label>
                        <input
                          id={mfrInputId}
                          type="text"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wManufacturer}
                          onChange={(e) => setWManufacturer(e.target.value)}
                          placeholder="e.g. Johnson Electric / Mabuchi"
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={modelNoInputId} className="form-label">Model Number</label>
                        <input
                          id={modelNoInputId}
                          type="text"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wModelNumber}
                          onChange={(e) => setWModelNumber(e.target.value)}
                          placeholder="e.g. RS-775-12V-150W"
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor={serialNoInputId} className="form-label">Serial Number</label>
                        <input
                          id={serialNoInputId}
                          type="text"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wSerialNumber}
                          onChange={(e) => setWSerialNumber(e.target.value)}
                          placeholder="e.g. SN-775-2026-004D"
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={siteSelectId} className="form-label">Plant Site Association *</label>
                        <select
                          id={siteSelectId}
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wSiteId}
                          onChange={(e) => setWSiteId(e.target.value)}
                        >
                          <option value="SITE-PLANT-A">SITE-PLANT-A (Line 3 Main Assembly)</option>
                          <option value="SITE-PLANT-B">SITE-PLANT-B (Packaging Hall)</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor={installDateInputId} className="form-label">Installation Date</label>
                        <input
                          id={installDateInputId}
                          type="date"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wInstallationDate}
                          onChange={(e) => setWInstallationDate(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label htmlFor={descInputId} className="form-label">Operational Notes / Machine Context</label>
                      <textarea
                        id={descInputId}
                        className="form-textarea"
                        rows={2}
                        value={wDescription}
                        onChange={(e) => setWDescription(e.target.value)}
                        placeholder="Enter mounting details, vibration dampening setup, or operating environment..."
                      />
                    </div>
                  </div>
                )}

                {/* STEP 2: ELECTRICAL & MECHANICAL SPECS */}
                {step === 2 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ background: 'rgba(49, 95, 206, 0.05)', border: '1px solid var(--border-main)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      ℹ️ <strong>Datasheet Notice:</strong> Electrical parameters vary significantly across RS-775 manufacturers. Populate values matching your actual motor specification.
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={voltageInputId} className="form-label">Rated Operating Voltage (V DC) *</label>
                        <input
                          id={voltageInputId}
                          type="number"
                          step="0.1"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wVoltage}
                          onChange={(e) => setWVoltage(Number(e.target.value))}
                          required
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor={ratedCurrInputId} className="form-label">Rated Continuous Current (A) *</label>
                        <input
                          id={ratedCurrInputId}
                          type="number"
                          step="0.05"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wRatedCurrent}
                          onChange={(e) => setWRatedCurrent(Number(e.target.value))}
                          required
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={noLoadCurrInputId} className="form-label">No-Load Current (A)</label>
                        <input
                          id={noLoadCurrInputId}
                          type="number"
                          step="0.01"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wNoLoadCurrent}
                          onChange={(e) => setWNoLoadCurrent(Number(e.target.value))}
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor={ratedSpeedInputId} className="form-label">Rated Speed Under Load (RPM)</label>
                        <input
                          id={ratedSpeedInputId}
                          type="number"
                          step="100"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wRatedSpeed}
                          onChange={(e) => setWRatedSpeed(Number(e.target.value))}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={maxSpeedInputId} className="form-label">Maximum No-Load Speed (RPM)</label>
                        <input
                          id={maxSpeedInputId}
                          type="number"
                          step="100"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wMaxSpeed}
                          onChange={(e) => setWMaxSpeed(Number(e.target.value))}
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor={ratedPowerInputId} className="form-label">Rated Mechanical Power (Watts)</label>
                        <input
                          id={ratedPowerInputId}
                          type="number"
                          step="1"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wRatedPower}
                          onChange={(e) => setWRatedPower(Number(e.target.value))}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={supplyTypeInputId} className="form-label">Motor Supply Type *</label>
                        <input
                          id={supplyTypeInputId}
                          type="text"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wSupplyType}
                          onChange={(e) => setWSupplyType(e.target.value)}
                          placeholder="External DC supply"
                          required
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor={appLoadInputId} className="form-label">Application / Machine Load Context</label>
                        <input
                          id={appLoadInputId}
                          type="text"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wLoad}
                          onChange={(e) => setWLoad(e.target.value)}
                          placeholder="e.g. Line Feed Conveyor, Spindle Cooler, Test Bench"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* STEP 3: ESP32 DEVICE ASSIGNMENT */}
                {step === 3 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-app)', padding: '4px', borderRadius: 'var(--radius-sm)' }}>
                      <button
                        type="button"
                        className={`filter-pill ${wAssignMode === 'existing' ? 'active' : ''}`}
                        onClick={() => setWAssignMode('existing')}
                        style={{ flex: 1, padding: '8px' }}
                      >
                        Select Existing Enrolled ESP32
                      </button>
                      <button
                        type="button"
                        className={`filter-pill ${wAssignMode === 'new' ? 'active' : ''}`}
                        onClick={() => setWAssignMode('new')}
                        style={{ flex: 1, padding: '8px' }}
                      >
                        + Enroll New Physical ESP32 Node
                      </button>
                    </div>

                    {wAssignMode === 'existing' ? (
                      <div className="form-group">
                        <label htmlFor={devSelectId} className="form-label">Select Registered ESP32 Sensor Node</label>
                        <select
                          id={devSelectId}
                          className="form-textarea"
                          style={{ height: '42px', fontFamily: 'monospace' }}
                          value={wSelectedDeviceId}
                          onChange={(e) => setWSelectedDeviceId(e.target.value)}
                        >
                          <option value="">— Leave Unassigned (Assign Later) —</option>
                          {devices.map((d) => (
                            <option key={d.device_id} value={d.device_id}>
                              {d.device_id} ({d.board_variant} • {d.availability.toUpperCase()}
                              {d.assigned_motor_id ? ` • Currently: ${d.assigned_motor_id}` : ' • Available'})
                            </option>
                          ))}
                        </select>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          1-to-1 Association: An ESP32 cannot be actively assigned to two motors simultaneously.
                        </span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div className="form-group">
                          <label htmlFor={newDevIdInputId} className="form-label">New Device ID *</label>
                          <input
                            id={newDevIdInputId}
                            type="text"
                            className="form-textarea"
                            style={{ height: '38px', fontFamily: 'monospace' }}
                            value={wNewDeviceId}
                            onChange={(e) => setWNewDeviceId(e.target.value)}
                            placeholder="e.g. esp32-node-004"
                            required={wAssignMode === 'new'}
                          />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                          <div className="form-group">
                            <label htmlFor={newDevVariantInputId} className="form-label">Board Variant</label>
                            <input
                              id={newDevVariantInputId}
                              type="text"
                              className="form-textarea"
                              style={{ height: '38px' }}
                              value={wNewDeviceVariant}
                              onChange={(e) => setWNewDeviceVariant(e.target.value)}
                            />
                          </div>
                          <div className="form-group">
                            <label htmlFor={newDevFwInputId} className="form-label">Firmware Version</label>
                            <input
                              id={newDevFwInputId}
                              type="text"
                              className="form-textarea"
                              style={{ height: '38px' }}
                              value={wNewDeviceFw}
                              onChange={(e) => setWNewDeviceFw(e.target.value)}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* STEP 4: SENSORS & GPIO CONFLICT DETECTOR */}
                {step === 4 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {/* Conflict Warning */}
                    {pinConflicts.length > 0 && (
                      <div className="critical-dispatch-banner">
                        <div className="banner-icon-pulse">⚠️</div>
                        <div className="banner-content">
                          <div className="banner-title">Hardware GPIO Conflict Detected!</div>
                          <div className="banner-sub">
                            {pinConflicts.map((c, i) => (
                              <div key={i}>• {c}</div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Sensor 1: DHT11 */}
                    <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px 16px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                          🌡️ Chassis Temperature Sensor — DHT11
                        </span>
                        <span className="badge healthy">GPIO 4</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                        <div className="form-group">
                          <label htmlFor={dhtPinInputId} className="form-label">Data GPIO Pin</label>
                          <input
                            id={dhtPinInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wDhtPin}
                            onChange={(e) => setWDhtPin(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={dhtIntervalInputId} className="form-label">Sample Interval (ms)</label>
                          <input
                            id={dhtIntervalInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wDhtInterval}
                            onChange={(e) => setWDhtInterval(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={dhtOffsetInputId} className="form-label">Calib Offset (°C)</label>
                          <input
                            id={dhtOffsetInputId}
                            type="number"
                            step="0.1"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wDhtOffset}
                            onChange={(e) => setWDhtOffset(Number(e.target.value))}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Sensor 2: ADXL345 */}
                    <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px 16px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                          〰️ Dynamic Vibration Sensor — ADXL345 (I2C Bus 0)
                        </span>
                        <span className="badge healthy">SDA 21 • SCL 22</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '10px' }}>
                        <div className="form-group">
                          <label htmlFor={adxlRangeSelectId} className="form-label">Range</label>
                          <select
                            id={adxlRangeSelectId}
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAdxlRange}
                            onChange={(e) => setWAdxlRange(e.target.value as any)}
                          >
                            <option value="2g">±2g</option>
                            <option value="4g">±4g</option>
                            <option value="8g">±8g</option>
                            <option value="16g">±16g</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label htmlFor={adxlRateInputId} className="form-label">Rate (Hz)</label>
                          <input
                            id={adxlRateInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAdxlRate}
                            onChange={(e) => setWAdxlRate(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={adxlSdaInputId} className="form-label">SDA Pin</label>
                          <input
                            id={adxlSdaInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAdxlSda}
                            onChange={(e) => setWAdxlSda(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={adxlSclInputId} className="form-label">SCL Pin</label>
                          <input
                            id={adxlSclInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAdxlScl}
                            onChange={(e) => setWAdxlScl(Number(e.target.value))}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Sensor 3: ACS712 */}
                    <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px 16px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                          ⚡ Armature Current Sensor — ACS712 20A Hall Effect
                        </span>
                        <span className="badge healthy">Analog GPIO 34</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                        <div className="form-group">
                          <label htmlFor={acsPinInputId} className="form-label">Analog ADC Pin</label>
                          <input
                            id={acsPinInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAcsPin}
                            onChange={(e) => setWAcsPin(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={acsSensInputId} className="form-label">Sensitivity (mV/A)</label>
                          <input
                            id={acsSensInputId}
                            type="number"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAcsSensitivity}
                            onChange={(e) => setWAcsSensitivity(Number(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label htmlFor={acsZeroVInputId} className="form-label">Zero-Current V (V)</label>
                          <input
                            id={acsZeroVInputId}
                            type="number"
                            step="0.01"
                            className="form-textarea"
                            style={{ height: '34px' }}
                            value={wAcsZeroV}
                            onChange={(e) => setWAcsZeroV(Number(e.target.value))}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Sensor 4: SH1106 OLED Display */}
                    <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px 16px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>
                          🖥️ Local Status Display — SH1106 128x64 OLED (I2C Bus 1)
                        </span>
                        <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={wOledEnabled}
                            onChange={(e) => setWOledEnabled(e.target.checked)}
                          />
                          Enabled
                        </label>
                      </div>
                      {wOledEnabled && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                          <div className="form-group">
                            <label htmlFor={oledSdaInputId} className="form-label">OLED SDA Pin</label>
                            <input
                              id={oledSdaInputId}
                              type="number"
                              className="form-textarea"
                              style={{ height: '34px' }}
                              value={wOledSda}
                              onChange={(e) => setWOledSda(Number(e.target.value))}
                            />
                          </div>
                          <div className="form-group">
                            <label htmlFor={oledSclInputId} className="form-label">OLED SCL Pin</label>
                            <input
                              id={oledSclInputId}
                              type="number"
                              className="form-textarea"
                              style={{ height: '34px' }}
                              value={wOledScl}
                              onChange={(e) => setWOledScl(Number(e.target.value))}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* STEP 5: HEALTH THRESHOLDS */}
                {step === 5 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ background: 'rgba(183, 121, 31, 0.08)', border: '1px solid rgba(183, 121, 31, 0.3)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: '12px', color: '#8A5B15' }}>
                      ⚠️ <strong>Provisional Profile:</strong> The initial thresholds below must be verified against actual machine operating conditions before operational use. Warning limits must strictly precede Critical limits.
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={tempWarnInputId} className="form-label">Temperature Warning (°C) *</label>
                        <input
                          id={tempWarnInputId}
                          type="number"
                          step="0.5"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wTempWarn}
                          onChange={(e) => setWTempWarn(Number(e.target.value))}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor={tempCritInputId} className="form-label">Temperature Critical Trip (°C) *</label>
                        <input
                          id={tempCritInputId}
                          type="number"
                          step="0.5"
                          className="form-textarea"
                          style={{ height: '38px', borderColor: wTempWarn >= wTempCrit ? 'var(--status-critical)' : undefined }}
                          value={wTempCrit}
                          onChange={(e) => setWTempCrit(Number(e.target.value))}
                          required
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={currWarnInputId} className="form-label">Armature Current Warning (A) *</label>
                        <input
                          id={currWarnInputId}
                          type="number"
                          step="0.1"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wCurrWarn}
                          onChange={(e) => setWCurrWarn(Number(e.target.value))}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor={currCritInputId} className="form-label">Overcurrent Critical Trip (A) *</label>
                        <input
                          id={currCritInputId}
                          type="number"
                          step="0.1"
                          className="form-textarea"
                          style={{ height: '38px', borderColor: wCurrWarn >= wCurrCrit ? 'var(--status-critical)' : undefined }}
                          value={wCurrCrit}
                          onChange={(e) => setWCurrCrit(Number(e.target.value))}
                          required
                        />
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor={vibWarnInputId} className="form-label">Vibration Warning (g RMS) *</label>
                        <input
                          id={vibWarnInputId}
                          type="number"
                          step="0.05"
                          className="form-textarea"
                          style={{ height: '38px' }}
                          value={wVibWarn}
                          onChange={(e) => setWVibWarn(Number(e.target.value))}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor={vibCritInputId} className="form-label">Vibration Critical Trip (g RMS) *</label>
                        <input
                          id={vibCritInputId}
                          type="number"
                          step="0.05"
                          className="form-textarea"
                          style={{ height: '38px', borderColor: wVibWarn >= wVibCrit ? 'var(--status-critical)' : undefined }}
                          value={wVibCrit}
                          onChange={(e) => setWVibCrit(Number(e.target.value))}
                          required
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* STEP 6: EDGE IMPULSE AI */}
                {step === 6 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)' }}>
                        Embedded TinyML Health Classification Engine
                      </span>
                      <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={wAiEnabled}
                          onChange={(e) => setWAiEnabled(e.target.checked)}
                        />
                        Enable TinyML Inference
                      </label>
                    </div>

                    <div className="form-group">
                      <label htmlFor={modelNameInputId} className="form-label">Exported Model Header Name</label>
                      <input
                        id={modelNameInputId}
                        type="text"
                        className="form-textarea"
                        style={{ height: '38px', fontFamily: 'monospace' }}
                        value={wModelName}
                        onChange={(e) => setWModelName(e.target.value)}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor={modelVerInputId} className="form-label">Model Version</label>
                      <input
                        id={modelVerInputId}
                        type="text"
                        className="form-textarea"
                        style={{ height: '38px', fontFamily: 'monospace' }}
                        value={wModelVersion}
                        onChange={(e) => setWModelVersion(e.target.value)}
                      />
                    </div>

                    <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                        Compiled Output Classes:
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <span className="badge healthy">healthy</span>
                        <span className="badge warning">warning</span>
                        <span className="badge critical">critical</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* STEP 7: REVIEW & REGISTER */}
                {step === 7 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ background: 'rgba(35, 132, 91, 0.08)', border: '1px solid rgba(35, 132, 91, 0.3)', padding: '12px 16px', borderRadius: 'var(--radius-sm)' }}>
                      <strong style={{ color: 'var(--status-healthy)' }}>Ready for Fleet Registration:</strong>
                      <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Confirming will store the configuration in MongoDB, enroll or bind the ESP32 node, generate an audit record, and integrate the motor into real-time monitoring.
                      </p>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                        <div style={{ fontWeight: 700, marginBottom: '6px', color: 'var(--text-main)' }}>Motor Identity</div>
                        <div>ID: <strong>{wMotorId}</strong></div>
                        <div>Name: {wName}</div>
                        <div>Type: {wType}</div>
                        <div>Site: {wSiteId}</div>
                      </div>

                      <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                        <div style={{ fontWeight: 700, marginBottom: '6px', color: 'var(--text-main)' }}>Electrical Specs</div>
                        <div>Voltage: <strong>{wVoltage} V</strong></div>
                        <div>Current: <strong>{wRatedCurrent} A</strong></div>
                        <div>Power: {wRatedPower} W</div>
                        <div>Load: {wLoad}</div>
                      </div>

                      <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                        <div style={{ fontWeight: 700, marginBottom: '6px', color: 'var(--text-main)' }}>Assigned ESP32</div>
                        <div>
                          Device: <strong>{wAssignMode === 'existing' ? (wSelectedDeviceId || 'None') : wNewDeviceId}</strong>
                        </div>
                        <div>Mode: {wAssignMode === 'existing' ? 'Pre-Enrolled' : 'New Enrollment'}</div>
                      </div>

                      <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-main)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                        <div style={{ fontWeight: 700, marginBottom: '6px', color: 'var(--text-main)' }}>Trip Thresholds</div>
                        <div>Temp: {wTempWarn}°C / <strong>{wTempCrit}°C</strong></div>
                        <div>Current: {wCurrWarn}A / <strong>{wCurrCrit}A</strong></div>
                        <div>Vib: {wVibWarn}g / <strong>{wVibCrit}g</strong></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer Controls */}
              <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-main)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => (step > 1 ? setStep(step - 1) : setIsWizardOpen(false))}
                >
                  {step === 1 ? 'Cancel' : '← Previous Step'}
                </button>

                <div style={{ display: 'flex', gap: '8px' }}>
                  {step < 7 ? (
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        setWizardError(null)
                        setStep(step + 1)
                      }}
                    >
                      Next Step →
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ background: 'var(--status-healthy)', borderColor: 'var(--status-healthy)' }}
                      onClick={() => handleCommitMotorRegistration()}
                    >
                      <CheckCircle size={16} /> Confirm &amp; Commit Motor Registration
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==============================================================================
          QUICK ENROLL ESP32 DEVICE MODAL
          ============================================================================== */}
      {isEnrollDeviceModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsEnrollDeviceModalOpen(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '520px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Enroll ESP32 Telemetry Node</h3>
                <div className="modal-subtitle">Add a physical or virtual edge node to the plant hardware registry.</div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsEnrollDeviceModalOpen(false)}>✕</button>
            </div>

            <form onSubmit={handleQuickEnrollDevice}>
              <div className="modal-body">
                <div className="form-group">
                  <label htmlFor={quickDevIdInputId} className="form-label">Device ID *</label>
                  <input
                    id={quickDevIdInputId}
                    type="text"
                    className="form-textarea"
                    style={{ height: '38px', fontFamily: 'monospace' }}
                    value={quickDevId}
                    onChange={(e) => setQuickDevId(e.target.value)}
                    placeholder="e.g. esp32-node-004"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor={quickDevTypeSelectId} className="form-label">Device Type</label>
                  <select
                    id={quickDevTypeSelectId}
                    className="form-textarea"
                    style={{ height: '38px' }}
                    value={quickDevType}
                    onChange={(e) => setQuickDevType(e.target.value)}
                  >
                    <option value="ESP32">ESP32 (Standard)</option>
                    <option value="ESP32-S3">ESP32-S3</option>
                    <option value="Virtual-ESP32">Virtual-ESP32 (Simulator)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor={quickDevVariantInputId} className="form-label">Board Variant</label>
                  <input
                    id={quickDevVariantInputId}
                    type="text"
                    className="form-textarea"
                    style={{ height: '38px' }}
                    value={quickDevVariant}
                    onChange={(e) => setQuickDevVariant(e.target.value)}
                    placeholder="e.g. ESP32-D0WD-V3"
                  />
                </div>
              </div>

              <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-main)', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" className="btn-secondary" onClick={() => setIsEnrollDeviceModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Enroll Device →
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==============================================================================
          EDIT MOTOR CONFIGURATION & THRESHOLDS MODAL
          ============================================================================== */}
      {editingMotor && (
        <div className="modal-backdrop" onClick={() => setEditingMotor(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Edit Configuration — {editingMotor.motor_id}</h3>
                <div className="modal-subtitle">Currently Configuration v{editingMotor.configuration_version}</div>
              </div>
              <button className="modal-close-btn" onClick={() => setEditingMotor(null)}>✕</button>
            </div>

            <form onSubmit={handleSaveEditConfig}>
              <div className="modal-body">
                <div className="form-group">
                  <label htmlFor={editDevSelectId} className="form-label">Assigned ESP32 Device</label>
                  <select
                    id={editDevSelectId}
                    className="form-textarea"
                    style={{ height: '38px', fontFamily: 'monospace' }}
                    value={editAssignedDevice}
                    onChange={(e) => setEditAssignedDevice(e.target.value)}
                  >
                    <option value="">— Unassigned —</option>
                    {devices.map((d) => (
                      <option key={d.device_id} value={d.device_id}>
                        {d.device_id} ({d.availability.toUpperCase()})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)', marginTop: '8px' }}>
                  Safety Trip Thresholds
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label htmlFor={editTempWarnInputId} className="form-label">Temp Warning (°C)</label>
                    <input
                      id={editTempWarnInputId}
                      type="number"
                      step="0.5"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editTempWarn}
                      onChange={(e) => setEditTempWarn(Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor={editTempCritInputId} className="form-label">Temp Critical (°C)</label>
                    <input
                      id={editTempCritInputId}
                      type="number"
                      step="0.5"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editTempCrit}
                      onChange={(e) => setEditTempCrit(Number(e.target.value))}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label htmlFor={editCurrWarnInputId} className="form-label">Current Warning (A)</label>
                    <input
                      id={editCurrWarnInputId}
                      type="number"
                      step="0.1"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editCurrWarn}
                      onChange={(e) => setEditCurrWarn(Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor={editCurrCritInputId} className="form-label">Current Critical (A)</label>
                    <input
                      id={editCurrCritInputId}
                      type="number"
                      step="0.1"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editCurrCrit}
                      onChange={(e) => setEditCurrCrit(Number(e.target.value))}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label htmlFor={editVibWarnInputId} className="form-label">Vibration Warning (g)</label>
                    <input
                      id={editVibWarnInputId}
                      type="number"
                      step="0.05"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editVibWarn}
                      onChange={(e) => setEditVibWarn(Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor={editVibCritInputId} className="form-label">Vibration Critical (g)</label>
                    <input
                      id={editVibCritInputId}
                      type="number"
                      step="0.05"
                      className="form-textarea"
                      style={{ height: '36px' }}
                      value={editVibCrit}
                      onChange={(e) => setEditVibCrit(Number(e.target.value))}
                    />
                  </div>
                </div>
              </div>

              <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-main)', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" className="btn-secondary" onClick={() => setEditingMotor(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Changes (v{editingMotor.configuration_version + 1}) →
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==============================================================================
          AUDIT TRAIL MODAL
          ============================================================================== */}
      {isAuditModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsAuditModalOpen(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">Hardware Configuration Audit Trail</h3>
                <div className="modal-subtitle">Immutable log of motor registrations, updates, and device bindings.</div>
              </div>
              <button className="modal-close-btn" onClick={() => setIsAuditModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              {auditEvents.length === 0 ? (
                <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No audit records logged yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {auditEvents.map((evt) => (
                    <div
                      key={evt.event_id}
                      style={{
                        background: 'var(--bg-app)',
                        border: '1px solid var(--border-main)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '10px 14px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ fontWeight: 700, color: 'var(--brand-primary)' }}>
                          {evt.action} • {evt.target_id}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : ''}
                        </span>
                      </div>
                      <div style={{ color: 'var(--text-secondary)' }}>
                        User: <strong>{evt.user}</strong>
                      </div>
                      <div style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {JSON.stringify(evt.details)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border-main)', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setIsAuditModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==============================================================================
          CONFIRM DISABLE MOTOR MODAL
          ============================================================================== */}
      {disablingMotor && (
        <div className="modal-backdrop" onClick={() => setDisablingMotor(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Deactivate Motor {disablingMotor.motor_id}?</h3>
              <button className="modal-close-btn" onClick={() => setDisablingMotor(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)' }}>
                Are you sure you want to disable <strong>{disablingMotor.name}</strong> ({disablingMotor.motor_id})?
                This asset will be marked inactive and taken offline from active SCADA dispatch.
              </p>
            </div>
            <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-main)', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button className="btn-secondary" onClick={() => setDisablingMotor(null)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                style={{ background: 'var(--status-critical)', borderColor: 'var(--status-critical)' }}
                onClick={handleConfirmDisable}
              >
                Confirm Deactivation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
