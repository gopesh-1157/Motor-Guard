import { useState, type FC } from 'react'
import { Save, Check, Sliders, Radio, Cpu, RefreshCw, AlertTriangle, ShieldCheck } from 'lucide-react'

export const SettingsView: FC = () => {
  // Threshold values
  const [tempWarn, setTempWarn] = useState(50.0)
  const [tempCrit, setTempCrit] = useState(65.0)
  const [currWarn, setCurrWarn] = useState(3.5)
  const [currCrit, setCurrCrit] = useState(4.0)
  const [vibWarn, setVibWarn] = useState(0.20)
  const [vibCrit, setVibCrit] = useState(0.80)
  const [staleTimeoutSec, setStaleTimeoutSec] = useState(15)
  const [offlineTimeoutSec, setOfflineTimeoutSec] = useState(35)
  const [saved, setSaved] = useState(false)

  // Gateway parameters
  const [mqttHost, setMqttHost] = useState('127.0.0.1')
  const [mqttPort, setMqttPort] = useState(1883)
  const [softApIp, setSoftApIp] = useState('192.168.4.1')
  const [gatewaySaved, setGatewaySaved] = useState(false)

  // Simulator controls
  const [simMotor, setSimMotor] = useState('MTR-775-002')
  const [simCondition, setSimCondition] = useState('healthy')
  const [simInjecting, setSimInjecting] = useState(false)
  const [simFeedback, setSimFeedback] = useState<string | null>(null)

  const handleSaveThresholds = (e: React.FormEvent) => {
    e.preventDefault()
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const handleSaveGateway = (e: React.FormEvent) => {
    e.preventDefault()
    setGatewaySaved(true)
    setTimeout(() => setGatewaySaved(false), 2500)
  }

  const handleInjectSimFault = async () => {
    setSimInjecting(true)
    setSimFeedback(null)
    try {
      const token = localStorage.getItem('motorguard_auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch('/api/v1/simulator/inject', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          motor_id: simMotor,
          device_id: simMotor === 'MTR-775-002' ? 'sim-node-002' : 'sim-node-003',
          condition: simCondition,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setSimFeedback(`Condition '${simCondition}' applied to ${simMotor} -> Status: ${data.health_status.toUpperCase()}`)
      } else if (res.status === 401 || res.status === 403) {
        setSimFeedback('Simulator injection requires Manager or Admin security clearance.')
      } else {
        setSimFeedback(`Simulator error (HTTP ${res.status})`)
      }
    } catch {
      setSimFeedback('Failed to reach backend simulator endpoint.')
    } finally {
      setSimInjecting(false)
      setTimeout(() => setSimFeedback(null), 4000)
    }
  }


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div className="page-title-group">
          <h2 className="page-title">Edge Gateway Configuration &amp; Safety Thresholds</h2>
          <p className="page-description">
            Configure safety trips, deterministic alarm thresholds, broker connectivity, and edge testing simulator.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px' }}>
        {/* Panel 1: Industrial Safety Thresholds */}
        <form onSubmit={handleSaveThresholds} className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <ShieldCheck size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Operational Safety Thresholds &amp; Automatic Trips
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Temperature */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Temperature Safety Limits (°C) — DHT11
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Warning Alert Threshold</label>
                  <input
                    type="number"
                    step="0.5"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={tempWarn}
                    onChange={(e) => setTempWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Critical Emergency Trip</label>
                  <input
                    type="number"
                    step="0.5"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={tempCrit}
                    onChange={(e) => setTempCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Current */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Current Load Limits (Amps) — ACS712 20A
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Warning Alert Limit</label>
                  <input
                    type="number"
                    step="0.1"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={currWarn}
                    onChange={(e) => setCurrWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Overcurrent Cutoff</label>
                  <input
                    type="number"
                    step="0.1"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={currCrit}
                    onChange={(e) => setCurrCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Vibration */}
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Vibration RMS Limits (g) — ADXL345
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Mechanical Warning Limit</label>
                  <input
                    type="number"
                    step="0.05"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={vibWarn}
                    onChange={(e) => setVibWarn(parseFloat(e.target.value))}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Severe Breakdown Trip</label>
                  <input
                    type="number"
                    step="0.05"
                    className="search-input-field"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={vibCrit}
                    onChange={(e) => setVibCrit(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Telemetry timeouts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Stale Warning Timeout (seconds)
                </label>
                <input
                  type="number"
                  step="1"
                  min="5"
                  max="120"
                  className="search-input-field"
                  style={{ width: '100%', marginTop: '4px' }}
                  value={staleTimeoutSec}
                  onChange={(e) => setStaleTimeoutSec(parseInt(e.target.value, 10))}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Offline Disconnection Timeout (seconds)
                </label>
                <input
                  type="number"
                  step="1"
                  min="10"
                  max="300"
                  className="search-input-field"
                  style={{ width: '100%', marginTop: '4px' }}
                  value={offlineTimeoutSec}
                  onChange={(e) => setOfflineTimeoutSec(parseInt(e.target.value, 10))}
                />
              </div>
            </div>

            <div style={{ paddingTop: '8px' }}>
              <button type="submit" className="btn-primary">
                {saved ? <Check size={14} /> : <Save size={14} />}
                <span>{saved ? 'Safety Rules Updated' : 'Save Safety Limits'}</span>
              </button>
            </div>
          </div>
        </form>

        {/* Panel 2: Edge Gateway & MQTT Infrastructure */}
        <form onSubmit={handleSaveGateway} className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Radio size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Connectivity &amp; Broker Topology
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                MQTT Broker Hostname / IP (Local Mosquitto)
              </label>
              <input
                type="text"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={mqttHost}
                onChange={(e) => setMqttHost(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                MQTT Broker TCP Port
              </label>
              <input
                type="number"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={mqttPort}
                onChange={(e) => setMqttPort(parseInt(e.target.value, 10))}
              />
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                ESP32 Hardware SoftAP Bridge IP (COM7 USB / Direct Wi-Fi)
              </label>
              <input
                type="text"
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
                value={softApIp}
                onChange={(e) => setSoftApIp(e.target.value)}
              />
            </div>

            <div
              style={{
                padding: '12px',
                background: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '11px',
                color: 'var(--text-muted)',
                lineHeight: 1.5,
              }}
            >
              <strong style={{ color: 'var(--text-main)' }}>Telemetry Contract v1.0.0:</strong>
              <br />
              • Topic: <code style={{ color: 'var(--brand-primary)' }}>motorguard/v1/&#123;device_id&#125;/telemetry</code>
              <br />
              • QoS: 1 (At least once with broker acknowledgment)
              <br />
              • LWT: <code style={{ color: 'var(--status-critical)' }}>motorguard/v1/&#123;device_id&#125;/status</code> (offline)
            </div>

            <div style={{ paddingTop: '8px' }}>
              <button type="submit" className="btn-primary">
                {gatewaySaved ? <Check size={14} /> : <Save size={14} />}
                <span>{gatewaySaved ? 'Gateway Topology Saved' : 'Apply Gateway Settings'}</span>
              </button>
            </div>
          </div>
        </form>

        {/* Panel 3: Edge Impulse TinyML Specification */}
        <div className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Cpu size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Impulse TinyML Model Metadata
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Edge Impulse Project ID:</span>
              <strong style={{ color: 'var(--text-main)' }}>#1133176 ("MotoGuard Motor Health")</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Architecture:</span>
              <strong style={{ color: 'var(--text-main)' }}>Sensor Fusion EON Neural Network</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Input Features (Order-Strict):</span>
              <strong style={{ color: 'var(--text-main)' }}>[0] temp_C, [1] vib_g, [2] current_A</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)' }}>Model Class Labels:</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <span className="badge-status healthy">HEALTHY</span>
                <span className="badge-status warning">WARNING</span>
                <span className="badge-status critical">CRITICAL</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: 'var(--text-muted)' }}>DSP &amp; Quantization:</span>
              <strong style={{ color: 'var(--text-main)' }}>int8 Quantized / ~180KB RAM Free</strong>
            </div>
          </div>
        </div>

        {/* Panel 4: Edge Virtual Fleet Simulator Controls */}
        <div className="measurement-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sliders size={18} color="var(--brand-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-main)' }}>
              Edge Telemetry Simulator Suite (Testing &amp; Verification)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Target Virtual Drive Asset</label>
              <select
                value={simMotor}
                onChange={(e) => setSimMotor(e.target.value)}
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
              >
                <option value="MTR-775-001">MTR-775-001 (Physical / Simulated Twin)</option>
                <option value="MTR-775-002">MTR-775-002 (sim-node-002)</option>
                <option value="MTR-775-003">MTR-775-003 (sim-node-003)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Fault Injection Profile</label>
              <select
                value={simCondition}
                onChange={(e) => setSimCondition(e.target.value)}
                className="search-input-field"
                style={{ width: '100%', marginTop: '4px' }}
              >
                <option value="healthy">Healthy Baseline (38.5°C, 2.15A, 0.082g)</option>
                <option value="warning_temp">Warning Overtemperature (55.4°C)</option>
                <option value="critical_vib">Critical Mechanical Bearing Fault (0.895g)</option>
                <option value="overload_current">Electrical Overload (4.65A, 62°C)</option>
                <option value="sensor_disconnected">Sensor Disconnection (temp=NULL)</option>
              </select>
            </div>

            {simFeedback && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--brand-primary)',
                  fontSize: '11px',
                  color: 'var(--text-main)',
                  fontWeight: 600,
                }}
              >
                {simFeedback}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', paddingTop: '4px' }}>
              <button
                type="button"
                className="btn-primary"
                disabled={simInjecting}
                onClick={handleInjectSimFault}
              >
                {simInjecting ? <RefreshCw size={14} className="spin" /> : <AlertTriangle size={14} />}
                <span>{simInjecting ? 'Injecting Frame...' : 'Inject Test Condition'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
