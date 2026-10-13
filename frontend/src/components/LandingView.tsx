import type { FC } from 'react'
import type { DashboardStats, NavigationTab } from '../types'

interface LandingViewProps {
  stats: DashboardStats
  criticalAlertsCount: number
  onNavigate: (tab: NavigationTab) => void
  onOpenLogin?: () => void
}

export const LandingView: FC<LandingViewProps> = ({
  stats,
  criticalAlertsCount,
  onNavigate,
  onOpenLogin,
}) => {
  return (
    <div className="landing-container">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-badge">
          <span className="landing-badge-dot" />
          INDUSTRIAL EDGE GATEWAY &amp; THREE.JS DIGITAL TWIN
        </div>
        <h1 className="landing-title">
          Autonomous Condition Monitoring <br />
          <span>For Critical Electric Drive Motors</span>
        </h1>
        <p className="landing-subtitle">
          MotorGuard couples on-device TinyML vibration inference, 3D Three.js digital-twin spatial telemetry,
          and closed-loop RBAC incident dispatching for zero unplanned motor downtime.
        </p>

        <div className="landing-actions">
          <button
            className="btn-primary-glow"
            onClick={() => onNavigate('fleet')}
          >
            Launch Fleet SCADA →
          </button>
          <button
            className="btn-secondary"
            onClick={() => onNavigate('twin')}
          >
            🌐 3D Digital Twin (Three.js)
          </button>
          <button
            className="btn-secondary"
            onClick={() => onNavigate('manager')}
          >
            Manager Hub
            {criticalAlertsCount > 0 && (
              <span className="badge-critical-counter">{criticalAlertsCount} CRITICAL</span>
            )}
          </button>
          <button
            className="btn-secondary"
            onClick={() => onNavigate('technician')}
          >
            Technician Workbench
          </button>
          {onOpenLogin && (
            <button
              className="btn-secondary btn-rbac-gate"
              onClick={onOpenLogin}
            >
              🔒 RBAC Security Gate
            </button>
          )}
        </div>
      </section>

      {/* Live Plant Telemetry Bar */}
      <section className="landing-kpi-bar">
        <div className="kpi-item">
          <span className="kpi-label">Fleet Asset Pool</span>
          <span className="kpi-value">{stats.totalMotors} Motors</span>
          <span className="kpi-sub">Continuous Ingestion</span>
        </div>
        <div className="kpi-divider" />
        <div className="kpi-item">
          <span className="kpi-label">Operational Health</span>
          <span className="kpi-value text-healthy">{stats.healthyCount} Optimal</span>
          <span className="kpi-sub">{stats.warningCount} Warnings Flagged</span>
        </div>
        <div className="kpi-divider" />
        <div className="kpi-item">
          <span className="kpi-label">Active Critical Alarms</span>
          <span className={`kpi-value ${criticalAlertsCount > 0 ? 'text-critical' : 'text-healthy'}`}>
            {criticalAlertsCount} Unresolved
          </span>
          <span className="kpi-sub">Immediate Action Required</span>
        </div>
        <div className="kpi-divider" />
        <div className="kpi-item">
          <span className="kpi-label">Telemetry Bus Throughput</span>
          <span className="kpi-value text-cyan">{stats.totalMessages} Events</span>
          <span className="kpi-sub">QoS 1 Wire Protocol</span>
        </div>
      </section>

      {/* Industrial Architecture Blueprint */}
      <section className="landing-section">
        <div className="section-header-centered">
          <h2 className="section-headline">Deterministic 5-Tier Industrial Architecture</h2>
          <p className="section-subtext">
            Engineered for zero-loss factory local operation with edge-first resilience and strict hardware isolation.
          </p>
        </div>

        <div className="blueprint-grid">
          <div className="blueprint-card">
            <div className="blueprint-step">01</div>
            <h3 className="blueprint-title">Physical Sensor Layer</h3>
            <p className="blueprint-desc">
              ADXL345 dynamic 3-axis vibration RMS, ACS712 20A armature current with boot zero-calibration,
              and DHT11 temperature with disconnect fail-safes.
            </p>
            <div className="blueprint-tag">ESP32 DevKit · I2C / ADC</div>
          </div>

          <div className="blueprint-card">
            <div className="blueprint-step">02</div>
            <h3 className="blueprint-title">On-Device TinyML</h3>
            <p className="blueprint-desc">
              Edge Impulse EON-compiled neural classifier running on-chip in &lt;10ms. Real-time probability
              distribution across Healthy, Warning, and Critical classes.
            </p>
            <div className="blueprint-tag">TensorFlow Lite Micro</div>
          </div>

          <div className="blueprint-card">
            <div className="blueprint-step">03</div>
            <h3 className="blueprint-title">MQTT Edge Bus</h3>
            <p className="blueprint-desc">
              Local Eclipse Mosquitto message bus running QoS 1 telemetry streaming, Last Will and Testament (LWT)
              disconnect notification, and strict topic namespaces.
            </p>
            <div className="blueprint-tag">MQTT 3.1.1 / 5.0 · LWT</div>
          </div>

          <div className="blueprint-card">
            <div className="blueprint-step">04</div>
            <h3 className="blueprint-title">Gateway Persistence</h3>
            <p className="blueprint-desc">
              Local MongoDB 7.0 document store with compound unique indexes for idempotent event deduplication,
              preventing corrupt replays during network hiccups.
            </p>
            <div className="blueprint-tag">MongoDB · Deduplication</div>
          </div>

          <div className="blueprint-card highlight-card">
            <div className="blueprint-step">05</div>
            <h3 className="blueprint-title">Closed-Loop Work Orders</h3>
            <p className="blueprint-desc">
              When a critical fault triggers, Operations Managers immediately assign the incident to specific
              technicians with work instructions and repair audit tracking.
            </p>
            <div className="blueprint-tag">Dispatch &amp; Maintenance</div>
          </div>
        </div>
      </section>

      {/* Interactive Role Portals */}
      <section className="landing-section">
        <div className="section-header-centered">
          <h2 className="section-headline">Role-Based Operational Workspaces</h2>
          <p className="section-subtext">
            Tailored interfaces designed for plant operators, operations managers, and maintenance technicians.
          </p>
        </div>

        <div className="roles-grid">
          <div className="role-portal-card" onClick={() => onNavigate('fleet')}>
            <div className="role-portal-icon">📊</div>
            <div className="role-portal-badge">OPERATOR VIEW</div>
            <h3 className="role-portal-title">Live SCADA Fleet Monitor</h3>
            <p className="role-portal-desc">
              Real-time telemetry gauges, dynamic micro-sparklines, TinyML inference confidence percentages,
              and connection heartbeat states.
            </p>
            <div className="role-portal-cta">Open Fleet Monitor →</div>
          </div>

          <div className="role-portal-card featured" onClick={() => onNavigate('manager')}>
            <div className="role-portal-icon">🛡️</div>
            <div className="role-portal-badge featured">OPERATIONS MANAGER</div>
            <h3 className="role-portal-title">Critical Incident Dispatch Hub</h3>
            <p className="role-portal-desc">
              Triage active thermal and vibration alarms. Assign critical motor breakdowns to certified
              technicians with priority instructions.
            </p>
            <div className="role-portal-cta">Launch Incident Dispatch →</div>
          </div>

          <div className="role-portal-card" onClick={() => onNavigate('technician')}>
            <div className="role-portal-icon">🔧</div>
            <div className="role-portal-badge">TECHNICIAN VIEW</div>
            <h3 className="role-portal-title">Field Technician Workbench</h3>
            <p className="role-portal-desc">
              View dispatched repair work orders, inspect pre-failure telemetry snapshots, log replaced parts,
              and resolve motor alarms.
            </p>
            <div className="role-portal-cta">Open Technician Portal →</div>
          </div>
        </div>
      </section>
    </div>
  )
}
