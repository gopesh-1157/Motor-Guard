import { useState, useEffect, useRef } from 'react'
import type { FC } from 'react'
import {
  Cpu,
  Shield,
  Wrench,
  Sliders,
  ChevronDown,
  Layers,
  Zap,
  Radio,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react'
import { ScrollMotorCanvas } from './ScrollMotorCanvas'
import type { DashboardStats, NavigationTab } from '../types'

interface LandingViewProps {
  stats: DashboardStats
  criticalAlertsCount: number
  onNavigate: (tab: NavigationTab) => void
  onOpenLogin?: () => void
}

export const LandingView: FC<LandingViewProps> = ({
  onNavigate,
  onOpenLogin,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [scrollProgress, setScrollProgress] = useState(0)

  // Track window or container scroll to animate the 3D motor model
  useEffect(() => {
    const handleScroll = () => {
      const el = scrollContainerRef.current
      if (!el) {
        const winScroll = window.scrollY
        const height = document.documentElement.scrollHeight - window.innerHeight
        if (height > 0) {
          setScrollProgress(Math.max(0, Math.min(1, winScroll / height)))
        }
        return
      }

      const rect = el.getBoundingClientRect()
      const totalScroll = el.scrollHeight - el.clientHeight
      if (totalScroll > 0) {
        const progress = Math.max(0, Math.min(1, el.scrollTop / totalScroll))
        setScrollProgress(progress)
      } else {
        // Fallback to window scroll relative to section
        const windowHeight = window.innerHeight
        const topOffset = rect.top
        const totalHeight = rect.height - windowHeight
        if (totalHeight > 0) {
          const progress = Math.max(0, Math.min(1, -topOffset / totalHeight))
          setScrollProgress(progress)
        }
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    const container = scrollContainerRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true })
    }

    return () => {
      window.removeEventListener('scroll', handleScroll)
      if (container) {
        container.removeEventListener('scroll', handleScroll)
      }
    }
  }, [])

  return (
    <div
      ref={scrollContainerRef}
      className="landing-container"
      style={{
        maxWidth: '1440px',
        margin: '0 auto',
        padding: '0 16px 64px 16px',
        position: 'relative',
      }}
    >
      {/* 1. HERO SECTION WITH EMBEDDED 3D SCROLL MOTOR VIEWPORT */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(320px, 1.15fr) minmax(360px, 1fr)',
          gap: '24px',
          alignItems: 'center',
          minHeight: '80vh',
          padding: '48px 32px',
          background: 'linear-gradient(135deg, var(--bg-card) 0%, var(--bg-subtle) 100%)',
          borderRadius: '24px',
          border: '1px solid var(--border-strong)',
          boxShadow: '0 12px 32px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(20px)',
          position: 'relative',
          overflow: 'hidden',
          marginBottom: '32px',
        }}
      >
        {/* Left Hero Narrative */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', zIndex: 2 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 14px',
              borderRadius: '9999px',
              background: 'var(--brand-primary-light)',
              border: '1px solid var(--brand-primary)',
              color: 'var(--brand-primary)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              width: 'fit-content',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: 'var(--brand-primary)',
                boxShadow: '0 0 10px rgba(2, 132, 199, 0.6)',
                animation: 'pulse 2s infinite',
              }}
            />
            NEXT-GEN INDUSTRIAL DRIVE TWIN &amp; TINYML SCADA
          </div>

          <h1
            style={{
              fontSize: 'clamp(32px, 4.5vw, 54px)',
              fontWeight: 800,
              lineHeight: 1.12,
              letterSpacing: '-0.03em',
              color: 'var(--text-main)',
              margin: 0,
            }}
          >
            Autonomous Motor Health.{' '}
            <span
              style={{
                background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #4338ca 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Zero Downtime.
            </span>
          </h1>

          <p
            style={{
              fontSize: '16px',
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              maxWidth: '560px',
              margin: 0,
            }}
          >
            MotorGuard delivers closed-loop electric drive protection: sub-10ms on-chip TinyML vibration
            inference, real-time 3D spatial digital-twin inspection, and automated dispatch for plant floor reliability.
          </p>

          {/* Public entry point: operational screens remain behind authentication. */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '8px' }}>
            {onOpenLogin && (
              <button
                type="button"
                onClick={onOpenLogin}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '13px 18px',
                  borderRadius: '10px',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-main)',
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                <Shield size={15} />
                <span>Secure sign in</span>
              </button>
            )}
          </div>

          {/* Product claims only: no plant-specific status is exposed publicly. */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '12px',
              paddingTop: '20px',
              borderTop: '1px solid var(--border-main)',
              marginTop: '12px',
            }}
          >
            <div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)' }}>
                Private
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Fleet data after sign-in
              </div>
            </div>

            <div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--brand-primary)' }}>
                Edge
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                On-device diagnostics
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: '22px',
                  fontWeight: 800,
                  color: '#059669',
                }}
              >
                Role-based
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Operational access
              </div>
            </div>
          </div>
        </div>

        {/* Right Sticky 3D Interactive Canvas */}
        <div
          style={{
            position: 'relative',
            height: '520px',
            borderRadius: '20px',
            background: 'radial-gradient(circle at center, var(--brand-primary-light) 0%, var(--bg-subtle) 70%)',
            border: '1px solid var(--border-strong)',
            boxShadow: 'inset 0 0 30px rgba(15, 23, 42, 0.04)',
            overflow: 'hidden',
          }}
        >
          <ScrollMotorCanvas scrollProgress={scrollProgress} />

          {/* Scroll Prompt Pill */}
          <div
            style={{
              position: 'absolute',
              bottom: '16px',
              right: '16px',
              padding: '6px 12px',
              borderRadius: '9999px',
              background: 'var(--bg-panel)',
              border: '1px solid var(--border-strong)',
              color: 'var(--brand-primary)',
              fontSize: '11px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <span>Scroll page to inspect internals</span>
            <ChevronDown size={14} />
          </div>
        </div>
      </section>

      {/* 2. SCROLL SHOWCASE CHAPTERS (Synchronized with 3D Exploded Engine) */}
      <section
        className="scada-panel"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          margin: '32px 0',
          padding: '36px 28px',
          background: 'var(--bg-card)',
          borderRadius: '16px',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '680px', margin: '0 auto 12px auto' }}>
          <div
            style={{
              fontSize: '11px',
              fontFamily: 'var(--scada-mono-font)',
              fontWeight: 700,
              color: '#0EA5E9',
              letterSpacing: '1.2px',
              textTransform: 'uppercase',
              marginBottom: '8px',
            }}
          >
            DEEP-DIVE HARDWARE ANATOMY
          </div>
          <h2
            style={{
              fontSize: '30px',
              fontWeight: 800,
              color: 'var(--text-main)',
              letterSpacing: '-0.02em',
              margin: '0 0 10px 0',
            }}
          >
            Precision Physical-Digital Twin
          </h2>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            Scroll through each operational layer to observe internal mechanical stresses, sensor mounting points,
            and neural inference processing in real time.
          </p>
        </div>

        {/* 4 Interactive Feature Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px',
          }}
        >
          {/* Card 1: Mechanical Anatomy */}
          <div
            style={{
              padding: '24px',
              borderRadius: '16px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-main)',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              transition: 'transform 0.2s, border-color 0.2s',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'rgba(2, 132, 199, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--brand-primary)',
              }}
            >
              <Layers size={20} />
            </div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)', letterSpacing: '0.8px' }}>
              01 • EXPLODED ANATOMY
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Heavy-Duty RS-775 Core
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
              High-torque copper wound armature, dual ISO 10816 shielded bearing races, and precision commutator
              assemblies mapped in 3D Three.js space.
            </p>
          </div>

          {/* Card 2: Tri-Sensor Matrix */}
          <div
            style={{
              padding: '24px',
              borderRadius: '16px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-main)',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'rgba(5, 150, 105, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#059669',
              }}
            >
              <Zap size={20} />
            </div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#059669', letterSpacing: '0.8px' }}>
              02 • SENSORY MATRIX
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Tri-Axis Dynamic Sensors
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
              ADXL345 dynamic 800 Hz vibration RMS, ACS712 zero-calibrated armature current, and DHT11 thermal
              casing probes with wire-break fail-safes.
            </p>
          </div>

          {/* Card 3: TinyML Intelligence */}
          <div
            style={{
              padding: '24px',
              borderRadius: '16px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-main)',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'rgba(124, 58, 237, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#7c3aed',
              }}
            >
              <Cpu size={20} />
            </div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#7c3aed', letterSpacing: '0.8px' }}>
              03 • ON-DEVICE TINYML
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Sub-10ms Edge Neural Net
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
              Edge Impulse EON-compiled classifier executing directly on ESP32 cores. Detects bearing spalling,
              eccentricity, and winding overload before mechanical failure.
            </p>
          </div>

          {/* Card 4: SCADA & Closed Loop */}
          <div
            style={{
              padding: '24px',
              borderRadius: '16px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-main)',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'rgba(217, 119, 6, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#d97706',
              }}
            >
              <Radio size={20} />
            </div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#d97706', letterSpacing: '0.8px' }}>
              04 • CLOSED-LOOP SCADA
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Deterministic Fleet Dispatch
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
              Automatic alert filing, technician work order dispatching, and ISO 10816 printable compliance
              reports ready for plant audits.
            </p>
          </div>
        </div>
      </section>

      {/* 3. DETERMINISTIC 5-TIER BLUEPRINT */}
      <section
        className="scada-panel"
        style={{
          padding: '36px 28px',
          borderRadius: '16px',
          background: 'var(--bg-card)',
          margin: '32px 0',
        }}
      >
        <div style={{ marginBottom: '24px' }}>
          <div
            style={{
              fontSize: '11px',
              fontFamily: 'var(--scada-mono-font)',
              fontWeight: 700,
              color: '#0EA5E9',
              letterSpacing: '1.2px',
              textTransform: 'uppercase',
              marginBottom: '6px',
            }}
          >
            DCS &amp; IIOT ARCHITECTURE TOPOLOGY
          </div>
          <h2 style={{ fontSize: '26px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 8px 0' }}>
            5-Tier Resilient Architecture
          </h2>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0 }}>
            Guaranteed zero telemetry data loss during factory network outages via edge ring buffers and QoS 1 wire protocols.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '14px',
          }}
        >
          {[
            { step: '01', title: 'Sensors', desc: 'ADXL345 + ACS712 + DHT11', tech: 'I2C Bus 0 & ADC' },
            { step: '02', title: 'TinyML Edge', desc: 'Sub-10ms Neural Classifier', tech: 'ESP32 Dual-Core' },
            { step: '03', title: 'MQTT Broker', desc: 'QoS 1 Telemetry Stream', tech: 'Mosquitto 1883' },
            { step: '04', title: 'FastAPI Core', desc: 'Rules Engine & WebSockets', tech: 'Python 3.12 Asynchronous' },
            { step: '05', title: 'MongoDB 7', desc: 'Idempotent Deduplication', tech: 'Time-Series TTL' },
          ].map((tier) => (
            <div
              key={tier.step}
              className="scada-gauge-box"
              style={{
                padding: '16px',
                borderRadius: '10px',
              }}
            >
              <div style={{ fontSize: '11.5px', fontFamily: 'var(--scada-mono-font)', fontWeight: 800, color: '#38bdf8', marginBottom: '4px' }}>
                STAGE {tier.step}
              </div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                {tier.title}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                {tier.desc}
              </div>
              <div
                style={{
                  fontSize: '10px',
                  fontFamily: 'var(--scada-mono-font)',
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-subtle)',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  width: 'fit-content',
                }}
              >
                {tier.tech}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. ROLE WORKSPACES PORTALS */}
      <section
        className="scada-panel"
        style={{
          padding: '36px 28px',
          borderRadius: '16px',
          background: 'var(--bg-card)',
          margin: '32px 0',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div
            style={{
              fontSize: '11px',
              fontFamily: 'var(--scada-mono-font)',
              fontWeight: 700,
              color: '#0EA5E9',
              letterSpacing: '1.2px',
              textTransform: 'uppercase',
              marginBottom: '6px',
            }}
          >
            ACCESS WORKSPACES // RBAC CLEARANCE
          </div>
          <h2 style={{ fontSize: '26px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 8px 0' }}>
            Role-Based Industrial Workspaces
          </h2>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0 }}>
            Dedicated portals engineered for plant operators, operations managers, and maintenance technicians.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          {/* Operator Portal */}
          <div
            onClick={() => onNavigate('fleet')}
            className="scada-panel"
            style={{
              padding: '24px',
              borderRadius: '12px',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              transition: 'transform 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: 'rgba(2, 132, 199, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--brand-primary)',
                }}
              >
                <Sliders size={18} />
              </div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)', letterSpacing: '0.5px' }}>
                OPERATOR VIEW
              </span>
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Live Fleet SCADA Monitor
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Inspect live telemetry sparklines, real-time current draw, and vibration RMS gauges across all motors.
            </p>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--brand-primary)', marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Launch Fleet Console</span>
              <ArrowRight size={13} />
            </div>
          </div>

          {/* Operations Manager Portal */}
          <div
            onClick={() => onNavigate('alerts')}
            className="scada-panel"
            style={{
              padding: '24px',
              borderRadius: '12px',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              transition: 'transform 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: 'rgba(217, 119, 6, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#d97706',
                }}
              >
                <AlertTriangle size={18} />
              </div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#d97706', letterSpacing: '0.5px' }}>
                MANAGER HUB
              </span>
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Alarm Triage &amp; Work Orders
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Review active thermal trips and vibration anomalies. Dispatch maintenance technicians with instructions.
            </p>
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#d97706', marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Open Alarms Console</span>
              <ArrowRight size={13} />
            </div>
          </div>

          {/* Technician Workbench */}
          <div
            onClick={() => onNavigate('maintenance')}
            className="scada-panel"
            style={{
              padding: '24px',
              borderRadius: '12px',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              transition: 'transform 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: 'rgba(5, 150, 105, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#059669',
                }}
              >
                <Wrench size={18} />
              </div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#059669', letterSpacing: '0.5px' }}>
                TECHNICIAN WORKBENCH
              </span>
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Maintenance Dispatch
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
              Inspect pre-failure vibration snapshots, log repaired motor parts, and resolve physical safety trips.
            </p>
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#059669', marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Open Work Orders</span>
              <ArrowRight size={13} />
            </div>
          </div>
        </div>
      </section>

      {/* 5. FOOTER */}
      <footer
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '24px 0',
          borderTop: '1px solid var(--border-main)',
          fontSize: '12px',
          color: 'var(--text-muted)',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={16} color="#059669" />
          <span>MotorGuard Industrial Edge Gateway • ISO 10816 Mechanical Standard</span>
        </div>
        <div>
          Deterministic SCADA Core • NIST SP 800-82 OT Cybersecurity
        </div>
      </footer>
    </div>
  )
}
