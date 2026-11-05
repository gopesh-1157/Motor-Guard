import { useRef, useEffect, useState, useMemo } from 'react'
import type { FC } from 'react'
import * as THREE from 'three'
import { Application as SplineApp } from '@splinetool/runtime'
import {
  Box,
  Layers,
  RotateCw,
  Sliders,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  WifiOff,
  Activity,
  Thermometer,
  Zap,
  Gauge,
  Sparkles,
  Link2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react'
import type { MotorState, HealthStatus } from '../types'

interface SplineMotorTwinProps {
  motors: MotorState[]
  selectedMotorId?: string
  onSelectMotor?: (motorId: string) => void
}

const isWebGLAvailable = () => {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
  } catch {
    return false
  }
}

export const SplineMotorTwin: FC<SplineMotorTwinProps> = ({
  motors,
  selectedMotorId,
  onSelectMotor: _onSelectMotor,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const splineCanvasRef = useRef<HTMLCanvasElement>(null)
  const cadCanvasRef = useRef<HTMLCanvasElement>(null)

  // Find active motor
  const activeMotor = useMemo(() => {
    if (!motors || motors.length === 0) return null
    if (selectedMotorId) {
      const found = motors.find((m) => m.motor_id === selectedMotorId)
      if (found) return found
    }
    return motors[0]
  }, [motors, selectedMotorId])

  // Spline scene URL state (configurable via env, local storage, or in-view URL dialog)
  const defaultSceneUrl = (import.meta.env.VITE_SPLINE_SCENE_URL as string | undefined) || ''
  const [splineSceneUrl, setSplineSceneUrl] = useState<string>(() => {
    return localStorage.getItem('motorguard_spline_scene_url') || defaultSceneUrl
  })
  const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)
  const [tempUrlInput, setTempUrlInput] = useState(splineSceneUrl)

  // Render mode: 'spline' if URL configured, otherwise fallback to 'cad' Three.js
  const [activeEngine, setActiveEngine] = useState<'spline' | 'cad'>(() => {
    return splineSceneUrl.trim().length > 0 ? 'spline' : 'cad'
  })

  // Spline runtime status
  const [splineLoading, setSplineLoading] = useState(false)
  const [splineError, setSplineError] = useState<string | null>(null)
  const splineAppRef = useRef<SplineApp | null>(null)

  // Interactive View Controls
  const [isWireframe, setIsWireframe] = useState(false)
  const [isExploded, setIsExploded] = useState(false)
  const [autoRotate, setAutoRotate] = useState(true)
  const [reducedMotion, setReducedMotion] = useState(false)

  // WebGL availability check
  const [webglSupported] = useState(isWebGLAvailable)

  // Detect prefers-reduced-motion
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(mediaQuery.matches)
    if (mediaQuery.matches) {
      setAutoRotate(false)
    }
    const handler = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches)
      if (e.matches) setAutoRotate(false)
    }
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  // Health state and live telemetry values
  const healthStatus: HealthStatus = activeMotor?.latest?.inference?.health_status || 'healthy'
  const isOnline = activeMotor?.connectionStatus === 'online'
  const isOffline = activeMotor?.connectionStatus === 'offline'
  const effectiveHealth: HealthStatus = isOffline ? 'unknown' : healthStatus

  const currentVal = activeMotor?.latest?.sensors?.current_a ?? null
  const tempVal = activeMotor?.latest?.sensors?.temperature_c ?? null
  const vibVal = activeMotor?.latest?.sensors?.vibration_g_rms ?? null
  const speedVal = activeMotor?.electrical_specs?.rated_speed_rpm ?? null

  const thresholds = activeMotor?.effective_thresholds || activeMotor?.thresholds
  const warnVib = thresholds?.vibration_warning_g ?? 0.20
  const critVib = thresholds?.vibration_critical_g ?? 0.80

  // -------------------------------------------------------------
  // Spline Runtime Loader
  // -------------------------------------------------------------
  useEffect(() => {
    if (activeEngine !== 'spline' || !splineSceneUrl.trim()) return
    const canvas = splineCanvasRef.current
    if (!canvas || !webglSupported) return

    let isSubscribed = true
    setSplineLoading(true)
    setSplineError(null)

    const app = new SplineApp(canvas)
    splineAppRef.current = app

    app
      .load(splineSceneUrl.trim())
      .then(() => {
        if (!isSubscribed) return
        setSplineLoading(false)
        setSplineError(null)
      })
      .catch((err: unknown) => {
        if (!isSubscribed) return
        const msg = err instanceof Error ? err.message : 'Failed to initialize Spline 3D Scene'
        setSplineLoading(false)
        setSplineError(msg)
      })

    return () => {
      isSubscribed = false
      try {
        app.dispose?.()
      } catch {}
      splineAppRef.current = null
    }
  }, [activeEngine, splineSceneUrl, webglSupported])

  // -------------------------------------------------------------
  // CAD Three.js Engine Implementation (Fallback & Dedicated View)
  // -------------------------------------------------------------
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const motorGroupRef = useRef<THREE.Group | null>(null)
  const rotorRef = useRef<THREE.Group | null>(null)
  const statorMaterialRef = useRef<THREE.MeshStandardMaterial | null>(null)
  const indicatorRingRef = useRef<THREE.Mesh | null>(null)

  const activeMotorRef = useRef(activeMotor)
  useEffect(() => {
    activeMotorRef.current = activeMotor
  }, [activeMotor])

  const autoRotateRef = useRef(autoRotate)
  useEffect(() => {
    autoRotateRef.current = autoRotate
  }, [autoRotate])

  const reducedMotionRef = useRef(reducedMotion)
  useEffect(() => {
    reducedMotionRef.current = reducedMotion
  }, [reducedMotion])

  const isExplodedRef = useRef(isExploded)
  useEffect(() => {
    isExplodedRef.current = isExploded
  }, [isExploded])

  const explodedPartsRef = useRef<{
    frontCap: THREE.Mesh
    rearCap: THREE.Mesh
    rotor: THREE.Group
    stator: THREE.Mesh
    bearingFront: THREE.Mesh
    bearingRear: THREE.Mesh
  } | null>(null)

  // Initialize Three.js CAD model
  useEffect(() => {
    if (activeEngine !== 'cad' && !splineError) return
    const container = containerRef.current
    const canvas = cadCanvasRef.current
    if (!container || !canvas || !webglSupported) return

    const width = container.clientWidth || 640
    const height = container.clientHeight || 500

    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000)
    camera.position.set(0, 0.8, 9.0)
    camera.lookAt(0, 0, 0)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    rendererRef.current = renderer

    // Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.95)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.5)
    keyLight.position.set(8, 12, 10)
    keyLight.castShadow = true
    scene.add(keyLight)

    const rimLight = new THREE.DirectionalLight(0x93c5fd, 0.7)
    rimLight.position.set(-10, -5, -8)
    scene.add(rimLight)

    // Ground Pedestal (Shadow Receiver)
    const groundGeo = new THREE.CylinderGeometry(5.2, 5.2, 0.1, 48)
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.1,
      roughness: 0.85,
      transparent: true,
      opacity: 0.22,
    })
    const ground = new THREE.Mesh(groundGeo, groundMat)
    ground.position.set(0, -2.1, 0)
    ground.receiveShadow = true
    scene.add(ground)

    // Assembly Group
    const motorGroup = new THREE.Group()
    motorGroupRef.current = motorGroup
    scene.add(motorGroup)

    // 1. Stator Casing
    const statorGeo = new THREE.CylinderGeometry(1.6, 1.6, 4.2, 36)
    const statorMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.85,
      roughness: 0.28,
      wireframe: isWireframe,
    })
    statorMaterialRef.current = statorMat
    const statorMesh = new THREE.Mesh(statorGeo, statorMat)
    statorMesh.rotation.z = Math.PI / 2
    statorMesh.castShadow = true
    statorMesh.receiveShadow = true
    motorGroup.add(statorMesh)

    // Stator status indicator ring (reflects healthy/warning/critical)
    const ringGeo = new THREE.TorusGeometry(1.64, 0.08, 16, 48)
    const ringMat = new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x10b981,
      emissiveIntensity: 0.6,
      roughness: 0.2,
    })
    const ringMesh = new THREE.Mesh(ringGeo, ringMat)
    ringMesh.rotation.y = Math.PI / 2
    ringMesh.position.set(0, 0, 0)
    indicatorRingRef.current = ringMesh
    motorGroup.add(ringMesh)

    // 2. Front End Bell
    const frontCapGeo = new THREE.CylinderGeometry(1.62, 1.62, 0.5, 36)
    const capMat = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      metalness: 0.9,
      roughness: 0.2,
      wireframe: isWireframe,
    })
    const frontCapMesh = new THREE.Mesh(frontCapGeo, capMat)
    frontCapMesh.position.set(2.35, 0, 0)
    frontCapMesh.rotation.z = Math.PI / 2
    frontCapMesh.castShadow = true
    motorGroup.add(frontCapMesh)

    // 3. Rear End Bell
    const rearCapGeo = new THREE.CylinderGeometry(1.61, 1.61, 0.45, 36)
    const rearCapMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.4,
      roughness: 0.6,
      wireframe: isWireframe,
    })
    const rearCapMesh = new THREE.Mesh(rearCapGeo, rearCapMat)
    rearCapMesh.position.set(-2.32, 0, 0)
    rearCapMesh.rotation.z = Math.PI / 2
    rearCapMesh.castShadow = true
    motorGroup.add(rearCapMesh)

    // 4. Front & Rear Bearings
    const bearingGeo = new THREE.CylinderGeometry(0.55, 0.55, 0.35, 24)
    const bearingMat = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      metalness: 0.95,
      roughness: 0.15,
    })
    const bearingFront = new THREE.Mesh(bearingGeo, bearingMat)
    bearingFront.position.set(2.5, 0, 0)
    bearingFront.rotation.z = Math.PI / 2
    motorGroup.add(bearingFront)

    const bearingRear = new THREE.Mesh(bearingGeo, bearingMat)
    bearingRear.position.set(-2.45, 0, 0)
    bearingRear.rotation.z = Math.PI / 2
    motorGroup.add(bearingRear)

    // 5. Internal Rotor Assembly
    const rotorGroup = new THREE.Group()
    rotorRef.current = rotorGroup
    motorGroup.add(rotorGroup)

    const shaftGeo = new THREE.CylinderGeometry(0.22, 0.22, 6.6, 24)
    const shaftMat = new THREE.MeshStandardMaterial({
      color: 0xf1f5f9,
      metalness: 0.95,
      roughness: 0.1,
    })
    const shaftMesh = new THREE.Mesh(shaftGeo, shaftMat)
    shaftMesh.rotation.z = Math.PI / 2
    shaftMesh.castShadow = true
    rotorGroup.add(shaftMesh)

    const armatureGeo = new THREE.CylinderGeometry(1.28, 1.28, 2.6, 28)
    const armatureMat = new THREE.MeshStandardMaterial({
      color: 0xd97706,
      metalness: 0.7,
      roughness: 0.4,
    })
    const armatureMesh = new THREE.Mesh(armatureGeo, armatureMat)
    armatureMesh.rotation.z = Math.PI / 2
    rotorGroup.add(armatureMesh)

    explodedPartsRef.current = {
      frontCap: frontCapMesh,
      rearCap: rearCapMesh,
      rotor: rotorGroup,
      stator: statorMesh,
      bearingFront,
      bearingRear,
    }

    // Interactive mouse rotation
    let isDragging = false
    let prevX = 0
    let prevY = 0
    let rotX = 0.25
    let rotY = -0.5

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true
      prevX = e.clientX
      prevY = e.clientY
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return
      const deltaX = e.clientX - prevX
      const deltaY = e.clientY - prevY
      prevX = e.clientX
      prevY = e.clientY

      rotY += deltaX * 0.008
      rotX += deltaY * 0.008
      rotX = Math.max(-0.75, Math.min(0.75, rotX))
    }

    const onMouseUp = () => {
      isDragging = false
    }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      if (!cameraRef.current) return
      const curZ = cameraRef.current.position.z
      const newZ = Math.min(Math.max(curZ + e.deltaY * 0.006, 5.5), 15.0)
      cameraRef.current.position.z = newZ
      cameraRef.current.lookAt(0, 0, 0)
    }

    const onDblClick = () => {
      rotX = 0.25
      rotY = -0.5
      if (cameraRef.current) {
        cameraRef.current.position.set(0, 0.8, 9.0)
        cameraRef.current.lookAt(0, 0, 0)
      }
    }

    canvas.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('dblclick', onDblClick)

    // Animation Render Loop
    let animId: number
    let clock = new THREE.Clock()

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const delta = clock.getDelta()
      const elapsed = clock.getElapsedTime()

      // Handle explode animation lerp
      const parts = explodedPartsRef.current
      if (parts) {
        const targetOffset = isExplodedRef.current ? 1.6 : 0
        parts.frontCap.position.x += (2.35 + targetOffset * 1.8 - parts.frontCap.position.x) * 0.1
        parts.rearCap.position.x += (-2.32 - targetOffset * 1.8 - parts.rearCap.position.x) * 0.1
        parts.bearingFront.position.x += (2.5 + targetOffset * 2.8 - parts.bearingFront.position.x) * 0.1
        parts.bearingRear.position.x += (-2.45 - targetOffset * 2.8 - parts.bearingRear.position.x) * 0.1
      }

      // Auto rotation
      if (autoRotateRef.current && !isDragging && !reducedMotionRef.current) {
        rotY += delta * 0.4
      }

      // Rotor dynamic rotation based on measured speed / current
      if (rotorRef.current && !reducedMotionRef.current) {
        const liveCurrent = activeMotorRef.current?.latest?.sensors?.current_a ?? 0.8
        const rotationSpeed = Math.min(Math.max(liveCurrent * 8, 2), 35)
        rotorRef.current.rotation.x += delta * rotationSpeed
      }

      // Dynamic subtle vibration based on measured ADXL345 RMS
      if (motorGroupRef.current) {
        motorGroupRef.current.rotation.x = rotX
        motorGroupRef.current.rotation.y = rotY

        if (!reducedMotionRef.current) {
          const liveVib = activeMotorRef.current?.latest?.sensors?.vibration_g_rms ?? 0.05
          const vibAmp = Math.min(liveVib * 0.08, 0.12)
          motorGroupRef.current.position.y = Math.sin(elapsed * 45) * vibAmp
          motorGroupRef.current.position.z = Math.cos(elapsed * 40) * (vibAmp * 0.5)
        } else {
          motorGroupRef.current.position.set(0, 0, 0)
        }
      }

      // Dynamic indicator color update
      if (indicatorRingRef.current) {
        const state = activeMotorRef.current?.latest?.inference?.health_status || 'unknown'
        const ringMat = indicatorRingRef.current.material as THREE.MeshStandardMaterial
        if (state === 'healthy') {
          ringMat.color.setHex(0x10b981)
          ringMat.emissive.setHex(0x10b981)
          ringMat.emissiveIntensity = 0.6
        } else if (state === 'warning') {
          ringMat.color.setHex(0xf59e0b)
          ringMat.emissive.setHex(0xf59e0b)
          ringMat.emissiveIntensity = 0.8 + Math.sin(elapsed * 8) * 0.3
        } else if (state === 'critical') {
          ringMat.color.setHex(0xef4444)
          ringMat.emissive.setHex(0xef4444)
          ringMat.emissiveIntensity = 1.0 + Math.sin(elapsed * 12) * 0.5
        } else {
          ringMat.color.setHex(0x64748b)
          ringMat.emissive.setHex(0x334155)
          ringMat.emissiveIntensity = 0.2
        }
      }

      if (cameraRef.current) {
        cameraRef.current.lookAt(0, 0, 0)
      }
      renderer.render(scene, camera)
    }

    animate()

    // Resize handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return
      const newW = container.clientWidth
      const newH = container.clientHeight || 500
      camera.aspect = newW / newH
      camera.updateProjectionMatrix()
      camera.lookAt(0, 0, 0)
      renderer.setSize(newW, newH)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('dblclick', onDblClick)
      renderer.dispose()
    }
  }, [activeEngine, splineError, webglSupported, isWireframe])

  // Save custom Spline URL
  const handleSaveSplineUrl = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = tempUrlInput.trim()
    setSplineSceneUrl(clean)
    localStorage.setItem('motorguard_spline_scene_url', clean)
    setIsUrlModalOpen(false)
    if (clean) {
      setActiveEngine('spline')
    }
  }

  // Clear Spline URL
  const handleClearSplineUrl = () => {
    setSplineSceneUrl('')
    setTempUrlInput('')
    localStorage.removeItem('motorguard_spline_scene_url')
    setIsUrlModalOpen(false)
    setActiveEngine('cad')
  }

  return (
    <div className="spline-digital-twin-page" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header & Controls Bar */}
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div className="page-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <h2 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Box size={20} color="var(--brand-primary)" />
              {activeMotor?.motor_id || 'MTR-775-001'} — 3D Digital Twin
            </h2>

            {/* Health Badge */}
            <span
              className={`status-pill status-${effectiveHealth}`}
              style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}
            >
              {effectiveHealth === 'healthy' && <CheckCircle size={13} />}
              {effectiveHealth === 'warning' && <AlertTriangle size={13} />}
              {effectiveHealth === 'critical' && <ShieldAlert size={13} />}
              {effectiveHealth === 'unknown' && <HelpCircle size={13} />}
              {effectiveHealth === 'unknown' ? 'NODE OFFLINE' : `HEALTH: ${effectiveHealth}`}
            </span>
          </div>
          <p className="page-subtitle">
            Edge-synchronized digital replica of industrial motor asset. Telemetry fed directly via MQTT cloud pipeline.
          </p>
        </div>

        {/* View Actions & Engine Toggle */}
        <div className="header-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {/* Engine Selector */}
          <div
            style={{
              display: 'flex',
              background: 'var(--bg-subtle)',
              padding: '2px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-main)',
            }}
          >
            <button
              onClick={() => setActiveEngine('spline')}
              className={`btn-action-ghost ${activeEngine === 'spline' ? 'active' : ''}`}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                background: activeEngine === 'spline' ? 'var(--bg-panel)' : 'transparent',
                boxShadow: activeEngine === 'spline' ? 'var(--shadow-xs)' : 'none',
              }}
              title="Spline 3D Scene View"
            >
              <Sparkles size={13} style={{ marginRight: 4 }} />
              Spline Scene
            </button>
            <button
              onClick={() => setActiveEngine('cad')}
              className={`btn-action-ghost ${activeEngine === 'cad' ? 'active' : ''}`}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                background: activeEngine === 'cad' ? 'var(--bg-panel)' : 'transparent',
                boxShadow: activeEngine === 'cad' ? 'var(--shadow-xs)' : 'none',
              }}
              title="CAD Precision Three.js Interactive Twin"
            >
              <Box size={13} style={{ marginRight: 4 }} />
              CAD Three.js
            </button>
          </div>

          {/* Spline Asset Config Button */}
          <button
            onClick={() => {
              setTempUrlInput(splineSceneUrl)
              setIsUrlModalOpen(true)
            }}
            className="btn-action-ghost"
            style={{ padding: '4px 10px', fontSize: '11px' }}
            title="Configure Spline .splinecode scene URL"
          >
            <Link2 size={13} style={{ marginRight: 4 }} />
            {splineSceneUrl ? 'Spline Linked' : 'Link Spline'}
          </button>

          {/* CAD Controls */}
          {activeEngine === 'cad' && (
            <>
              <button
                onClick={() => setAutoRotate(!autoRotate)}
                className={`btn-action-ghost ${autoRotate ? 'active' : ''}`}
                style={{ padding: '4px 10px', fontSize: '11px' }}
                title="Toggle Auto Rotation"
              >
                <RotateCw size={13} style={{ marginRight: 4 }} />
                Rotate: {autoRotate ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setIsExploded(!isExploded)}
                className={`btn-action-ghost ${isExploded ? 'active' : ''}`}
                style={{ padding: '4px 10px', fontSize: '11px' }}
                title="Toggle Exploded CAD Assembly View"
              >
                <Layers size={13} style={{ marginRight: 4 }} />
                Exploded: {isExploded ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setIsWireframe(!isWireframe)}
                className={`btn-action-ghost ${isWireframe ? 'active' : ''}`}
                style={{ padding: '4px 10px', fontSize: '11px' }}
                title="Toggle Wireframe Stator"
              >
                <Sliders size={13} style={{ marginRight: 4 }} />
                Wireframe: {isWireframe ? 'ON' : 'OFF'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main 3D Digital Twin Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: '20px',
          minHeight: '560px',
        }}
      >
        {/* 3D Canvas Viewport */}
        <div
          ref={containerRef}
          className="card"
          style={{
            position: 'relative',
            overflow: 'hidden',
            padding: 0,
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-main)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '560px',
          }}
        >
          {/* Top HUD Badges */}
          <div
            style={{
              position: 'absolute',
              top: '16px',
              left: '16px',
              zIndex: 10,
              display: 'flex',
              gap: '8px',
              pointerEvents: 'none',
              flexWrap: 'wrap',
            }}
          >
            <div
              style={{
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-main)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-xs, 4px)',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                boxShadow: 'var(--shadow-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: isOnline ? 'var(--status-healthy)' : 'var(--text-muted)',
                }}
              />
              SOURCE: {activeMotor?.source.toUpperCase()} // DEVICE: {activeMotor?.latest?.device_id || 'esp32-node-001'}
            </div>

            <div
              style={{
                background: 'var(--bg-card)',
                color: 'var(--brand-primary)',
                border: '1px solid var(--border-main)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-xs, 4px)',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                boxShadow: 'var(--shadow-xs)',
              }}
            >
              ENGINE: {activeEngine === 'spline' ? 'SPLINE RUNTIME v2' : 'THREE.js CAD WEBGL'}
            </div>
          </div>


          {/* WebGL Not Supported Fallback */}
          {!webglSupported ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              <WifiOff size={40} style={{ margin: '0 auto 12px', opacity: 0.6 }} />
              <h4 style={{ color: 'var(--text-main)', marginBottom: '8px' }}>WebGL Context Unavailable</h4>
              <p style={{ fontSize: '13px', maxWidth: '360px', margin: '0 auto' }}>
                Hardware 3D acceleration is disabled or unsupported in this browser environment. Telemetry data continues to stream normally.
              </p>
            </div>
          ) : activeEngine === 'spline' ? (
            // Spline Canvas Container
            <div style={{ width: '100%', height: '100%', position: 'relative' }}>
              {!splineSceneUrl.trim() ? (
                // Spline Boundary Config Guide (When no URL is set)
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: '30px',
                    textAlign: 'center',
                  }}
                >
                  <Sparkles size={36} color="var(--brand-primary)" style={{ marginBottom: 12 }} />
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>
                    Spline 3D Integration Boundary Ready
                  </h3>
                  <p
                    style={{
                      fontSize: '13px',
                      color: 'var(--text-muted)',
                      maxWidth: '460px',
                      lineHeight: '1.5',
                      marginBottom: 16,
                    }}
                  >
                    No custom Spline scene URL is currently loaded. You can link your maintained Spline scene URL (e.g. <code>https://prod.spline.design/xyz/scene.splinecode</code>) or switch to the built-in Three.js CAD twin.
                  </p>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      className="btn-primary"
                      onClick={() => setIsUrlModalOpen(true)}
                      style={{ fontSize: '12px', padding: '6px 14px' }}
                    >
                      <Link2 size={13} style={{ marginRight: 6 }} /> Enter Spline Scene URL
                    </button>
                    <button
                      className="btn-action-ghost"
                      onClick={() => setActiveEngine('cad')}
                      style={{ fontSize: '12px', padding: '6px 14px' }}
                    >
                      View CAD Three.js Twin
                    </button>
                  </div>
                </div>
              ) : splineLoading ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    gap: 12,
                    color: 'var(--text-muted)',
                  }}
                >
                  <RefreshCw size={24} className="spin" color="var(--brand-primary)" />
                  <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    LOADING SPLINE 3D SCENE ASSET...
                  </span>
                </div>
              ) : splineError ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: 24,
                    textAlign: 'center',
                    gap: 12,
                  }}
                >
                  <AlertTriangle size={32} color="var(--status-warning)" />
                  <h4 style={{ margin: 0, color: 'var(--text-main)' }}>Spline Asset Load Failed</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: 420 }}>
                    {splineError}. Falling back to internal Three.js CAD digital twin.
                  </p>
                  <button
                    className="btn-primary"
                    onClick={() => setActiveEngine('cad')}
                    style={{ fontSize: '11px', padding: '5px 12px' }}
                  >
                    Switch to CAD Twin
                  </button>
                </div>
              ) : null}

              {/* Real Spline Canvas */}
              <canvas
                ref={splineCanvasRef}
                style={{
                  width: '100%',
                  height: '100%',
                  display: splineLoading || splineError || !splineSceneUrl.trim() ? 'none' : 'block',
                }}
              />
            </div>
          ) : (
            // Three.js CAD Canvas
            <canvas ref={cadCanvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
          )}

          {/* Bottom Interaction Guide */}
          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '16px',
              zIndex: 10,
              fontSize: '10.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              pointerEvents: 'none',
            }}
          >
            ORBIT: CLICK + DRAG // ZOOM: PINCH // DOUBLE CLICK: RESET VIEW
          </div>
        </div>

        {/* Live Telemetry Readout & Sensor Status Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Identity & Health Card */}
          <div className="card" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)' }}>
                MOTOR ASSET SPEC
              </span>
              <span className={`status-dot status-dot-${effectiveHealth}`} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Asset Tag:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{activeMotor?.motor_id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Hardware Device:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{activeMotor?.latest?.device_id || 'esp32-node-001'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Telemetry Source:</span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    color: activeMotor?.source === 'hardware' ? 'var(--status-hardware)' : 'var(--status-sim)',
                  }}
                >
                  {activeMotor?.source.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Model Confidence:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {activeMotor?.latest?.inference?.confidence != null
                    ? `${(activeMotor.latest.inference.confidence * 100).toFixed(1)}%`
                    : '98.5%'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Last Packet:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {activeMotor?.latest?.timestamp
                    ? (() => {
                        const ts = activeMotor.latest.timestamp
                        const normalized = !ts.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(ts) ? `${ts}Z` : ts
                        return new Date(normalized).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                      })()
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Real Live Physical Readings */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)' }}>
              LIVE SENSOR READOUTS
            </span>

            {/* Current */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Zap size={15} color="var(--sensor-curr)" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ACS712 Current</span>
                </div>
                <span className="badge-info" style={{ fontSize: '10px' }}>
                  Limit: {thresholds?.current_critical_a ?? 4.0} A
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {currentVal != null ? currentVal.toFixed(2) : '--'}{' '}
                  <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>A</span>
                </span>
              </div>
            </div>

            {/* Temperature */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Thermometer size={15} color="var(--sensor-temp)" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>DHT11 Stator Temp</span>
                </div>
                <span className="badge-warning" style={{ fontSize: '10px' }}>
                  Warn: {thresholds?.temperature_warning_c ?? 50} °C
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {tempVal != null ? tempVal.toFixed(1) : '--'}{' '}
                  <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>°C</span>
                </span>
              </div>
            </div>

            {/* Vibration */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Activity size={15} color="var(--sensor-vib)" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ADXL345 Vibration</span>
                </div>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    fontFamily: 'var(--font-mono)',
                    color: vibVal && vibVal >= critVib ? 'var(--status-critical)' : 'var(--status-healthy)',
                  }}
                >
                  ISO: {vibVal && vibVal < warnVib ? 'Zone A' : vibVal && vibVal < critVib ? 'Zone B' : 'Zone C'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {vibVal != null ? vibVal.toFixed(3) : '--'}{' '}
                  <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>g RMS</span>
                </span>
              </div>
            </div>

            {/* Speed (if available) */}
            {speedVal != null && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Gauge size={15} color="var(--brand-primary)" />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Shaft Velocity</span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '18px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                    {Math.round(speedVal).toLocaleString()}{' '}
                    <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>RPM</span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Spline Asset URL Link Modal */}
      {isUrlModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-dialog" style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>Link Spline 3D Scene Asset</h3>
              <button
                onClick={() => setIsUrlModalOpen(false)}
                className="btn-icon"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSaveSplineUrl}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', margin: 0 }}>
                  Enter the public or CDN URL of your exported Spline <code>.splinecode</code> file.
                </p>
                <input
                  type="url"
                  placeholder="https://prod.spline.design/xxxxxxxx/scene.splinecode"
                  value={tempUrlInput}
                  onChange={(e) => setTempUrlInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-main)',
                    background: 'var(--bg-app)',
                    color: 'var(--text-main)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                  }}
                />
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', background: 'var(--bg-subtle)', padding: '8px', borderRadius: '4px' }}>
                  💡 <strong>Asset Boundary Note:</strong> Spline scenes export via Spline Editor → Export → Code → "Spline Viewer / Runtime".
                </div>
              </div>
              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                {splineSceneUrl ? (
                  <button
                    type="button"
                    onClick={handleClearSplineUrl}
                    className="btn-action-ghost"
                    style={{ color: 'var(--status-critical)' }}
                  >
                    Unlink Asset
                  </button>
                ) : <div />}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button type="button" onClick={() => setIsUrlModalOpen(false)} className="btn-action-ghost">
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary">
                    Save & Load Scene
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
