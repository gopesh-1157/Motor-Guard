export type HealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown'
export type ConnectionStatus = 'online' | 'stale' | 'offline'
export type TelemetrySource = 'hardware' | 'simulator'
export type SensorState = 'OK' | 'UNAVAILABLE' | 'DISCONNECTED' | 'OUT_OF_RANGE' | 'STALE'
export type NavigationTab =
  | 'overview'
  | 'fleet'
  | 'live'
  | 'analytics'
  | 'alerts'
  | 'maintenance'
  | 'devices'
  | 'reports'
  | 'settings'
  | 'motors' // alias for fleet
  | 'twin' // 3D digital twin
  | 'landing' // legacy alias for overview
  | 'manager' // legacy alias for alerts
  | 'technician' // legacy alias for maintenance

export type UserRole = 'Admin' | 'Manager' | 'Technician' | 'Operator'

export type ChartMetric = 'temperature' | 'current' | 'vibration'
export type ChartType = 'line' | 'area' | 'step' | 'bar' | 'scatter' | 'histogram' | 'threshold'
export type TimeRangeOption = '15m' | '1h' | '6h' | '24h' | '7d' | 'all'

export interface ElectricalSpecs {
  motor_type: string
  rated_voltage_v: number
  rated_current_a: number
  no_load_current_a?: number | null
  rated_speed_rpm?: number | null
  max_speed_rpm?: number | null
  rated_power_w?: number | null
  motor_supply_type: string
  application_load?: string | null
}

export interface MechanicalSpecs {
  shaft_diameter_mm?: number | null
  weight_grams?: number | null
  mounting_type?: string | null
  cooling_type?: string | null
}

export interface SensorDHT11Config {
  sensor_type: 'DHT11'
  gpio_pin: number
  unit: string
  sampling_interval_ms: number
  enabled: boolean
  calibration_offset_c: number
}

export interface SensorADXL345Config {
  sensor_type: 'ADXL345'
  i2c_bus: number
  sda_pin: number
  scl_pin: number
  measurement_range_g: '2g' | '4g' | '8g' | '16g'
  sample_frequency_hz: number
  axes: string[]
  output_feature: string
  measurement_unit: string
  calibration_offset_g: number
  enabled: boolean
}

export interface SensorACS712Config {
  sensor_type: 'ACS712-20A' | 'ACS712-5A' | 'ACS712-30A'
  analog_gpio_pin: number
  module_supply_v: number
  sensitivity_mv_per_a: number
  zero_current_voltage_v: number
  voltage_divider_ratio: number
  output_unit: string
  enabled: boolean
}

export interface SensorSH1106Config {
  display_type: 'SH1106'
  i2c_bus: number
  sda_pin: number
  scl_pin: number
  i2c_address: string
  enabled: boolean
}

export interface SensorsConfig {
  dht11: SensorDHT11Config
  adxl345: SensorADXL345Config
  acs712: SensorACS712Config
  sh1106: SensorSH1106Config
}

export interface HealthThresholds {
  temperature_warning_c: number
  temperature_critical_c: number
  current_warning_a: number
  current_critical_a: number
  vibration_warning_g: number
  vibration_critical_g: number
  device_offline_timeout_sec: number
  alert_persistence_sec: number
  alert_cooldown_sec: number
  hysteresis_percentage: number
}

export interface EdgeImpulseConfig {
  enabled: boolean
  model_name: string
  model_version: string
  deployment_type: string
  expected_input_format: string
  sample_frequency_hz: number
  window_length_ms: number
  class_mapping: string[]
  last_inference_timestamp?: string | null
}

export interface RegisteredMotor {
  motor_id: string
  name: string
  motor_type: string
  manufacturer?: string | null
  model_number?: string | null
  serial_number?: string | null
  site_id: string
  installation_date?: string | null
  description?: string | null
  status: 'active' | 'inactive'
  electrical_specs: ElectricalSpecs
  mechanical_specs?: MechanicalSpecs | null
  sensors_config: SensorsConfig
  thresholds: HealthThresholds
  edge_impulse_config: EdgeImpulseConfig
  assigned_device_id?: string | null
  configuration_version: number
  health_status: HealthStatus
  operational_state: 'RUNNING' | 'IDLE' | 'ALARM' | 'OFFLINE'
  created_at: string
  updated_at: string
  created_by?: string | null
}

export interface EnrolledDevice {
  device_id: string
  device_type: string
  board_variant: string
  firmware_version: string
  site_id: string
  assigned_motor_id?: string | null
  enrollment_status: 'enrolled' | 'pending' | 'revoked'
  availability: 'online' | 'offline' | 'unknown'
  last_seen?: string | null
  configuration_version: number
  created_at: string
  updated_at: string
}

export interface AuditEvent {
  event_id: string
  action: string
  user: string
  target_type: string
  target_id: string
  details: Record<string, any>
  timestamp: string
}


export interface SensorsPayload {
  temperature_c?: number | null
  current_a?: number | null
  vibration_g_rms?: number | null
}

export interface SensorStatusPayload {
  temperature: SensorState
  current: SensorState
  vibration: SensorState
}

export interface InferenceProbabilities {
  healthy: number
  warning: number
  critical: number
}

export interface InferencePayload {
  status: 'PREDICTED' | 'MODEL_UNAVAILABLE' | 'INPUT_INVALID' | 'SKIPPED' | 'MODEL_ERROR'
  health_status: HealthStatus
  confidence: number
  probabilities?: InferenceProbabilities | null
  model_version?: string | null
  inference_time_ms?: number | null
}

export interface DiagnosticsPayload {
  wifi_rssi_dbm?: number | null
  free_heap_bytes?: number | null
  uptime_seconds?: number | null
}

export interface TelemetryMessage {
  schema_version: '1.0.0'
  event_id: string
  device_id: string
  motor_id: string
  source: TelemetrySource
  seq: number
  timestamp: string
  sensors: SensorsPayload
  sensor_status: SensorStatusPayload
  inference: InferencePayload
  diagnostics?: DiagnosticsPayload | null
}

export interface MotorHistoryPoint {
  timestamp: string
  temperature: number | null
  current: number | null
  vibration: number | null
  health_status: HealthStatus
}

export interface MotorState {
  motor_id: string
  device_id: string
  source: TelemetrySource
  latest: TelemetryMessage
  history: MotorHistoryPoint[]
  lastSeen: number // unix epoch ms
  connectionStatus: ConnectionStatus
}

export interface DashboardStats {
  totalMotors: number
  healthyCount: number
  warningCount: number
  criticalCount: number
  offlineCount: number
  simulatorCount: number
  hardwareCount?: number
  esp32ApConnected?: boolean
  totalMessages: number
  wsConnected: boolean
}

export interface AlertItem {
  id?: string
  alert_id: string
  motor_id: string
  device_id: string
  severity: 'INFO' | 'WARNING' | 'CRITICAL'
  trigger_type: string
  trigger_value: number
  threshold_limit: number
  unit: string
  message: string
  state: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED'
  triggered_at: string
  acknowledged_at?: string | null
  acknowledged_by?: string | null
  assigned_to?: string | null
  assigned_by?: string | null
  assigned_at?: string | null
  priority?: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL' | null
  instructions?: string | null
  resolved_at?: string | null
  resolved_by?: string | null
  resolution_notes?: string | null
}

export interface UserProfile {
  username: string
  role: UserRole
  email: string
  clearance_level: number // 1: Operator, 2: Tech, 3: Manager, 4: Admin
  title?: string
  avatar?: string
  token?: string
}

export type WorkOrderStatus = 'Assigned' | 'Accepted' | 'In Progress' | 'Resolved' | 'Rejected'
export type WorkOrderPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT' | 'CRITICAL'

export interface WorkOrderItem {
  id?: string
  work_order_id: string
  motor_id: string
  alert_id?: string | null
  assigned_to_user_id: string
  assigned_by_user_id: string
  priority: WorkOrderPriority
  title: string
  description: string
  status: WorkOrderStatus
  created_at: string
  assigned_at?: string | null
  accepted_at?: string | null
  started_at?: string | null
  resolved_at?: string | null
  rejected_at?: string | null
  diagnosis?: string | null
  actions_taken?: string | null
  parts_replaced: string[]
  downtime_minutes: number
  resolution_notes?: string | null
  rejection_reason?: string | null
  updated_at: string
}

