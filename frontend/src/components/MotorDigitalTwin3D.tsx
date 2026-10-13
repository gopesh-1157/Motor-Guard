import { useRef, useEffect, useState, useMemo } from 'react'
import type { FC } from 'react'
import * as THREE from 'three'
import type { MotorState } from '../types'

interface MotorDigitalTwin3DProps {
  motors: MotorState[]
  selectedMotorId?: string
  onSelectMotor?: (motorId: string) => void
}

export const MotorDigitalTwin3D: FC<MotorDigitalTwin3DProps> = ({
  motors,
  selectedMotorId,
  onSelectMotor,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Find active motor
  const activeMotor = useMemo(() => {
    if (!motors || motors.length === 0) return null
    if (selectedMotorId) {
      const found = motors.find((m) => m.motor_id === selectedMotorId)
      if (found) return found
    }
    return motors[0]
  }, [motors, selectedMotorId])

  // Interactive View Controls
  const [isWireframe, setIsWireframe] = useState(false)
  const [isExploded, setIsExploded] = useState(false)
  const [autoRotate, setAutoRotate] = useState(true)
  const [showSensors, setShowSensors] = useState(true)
  const [hoveredSensor, setHoveredSensor] = useState<string | null>(null)

  // Sensor screen projections for overlay pins
  const [sensorCoords, setSensorCoords] = useState<{
    adxl: { x: number; y: number; visible: boolean }
    acs: { x: number; y: number; visible: boolean }
    temp: { x: number; y: number; visible: boolean }
    esp32: { x: number; y: number; visible: boolean }
  }>({
    adxl: { x: 0, y: 0, visible: false },
    acs: { x: 0, y: 0, visible: false },
    temp: { x: 0, y: 0, visible: false },
    esp32: { x: 0, y: 0, visible: false },
  })

  // Stable refs for animation loop
  const activeMotorRef = useRef(activeMotor)
  useEffect(() => {
    activeMotorRef.current = activeMotor
  }, [activeMotor])

  const isExplodedRef = useRef(isExploded)
  useEffect(() => {
    isExplodedRef.current = isExploded
  }, [isExploded])

  const autoRotateRef = useRef(autoRotate)
  useEffect(() => {
    autoRotateRef.current = autoRotate
  }, [autoRotate])

  // Three.js object references for animation loop
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const rotorRef = useRef<THREE.Group | null>(null)
  const motorGroupRef = useRef<THREE.Group | null>(null)
  const statorMaterialRef = useRef<THREE.MeshStandardMaterial | null>(null)
  const explodedPartsRef = useRef<{
    frontCap: THREE.Mesh
    rearCap: THREE.Mesh
    rotor: THREE.Group
    stator: THREE.Mesh
    bearingFront: THREE.Mesh
    bearingRear: THREE.Mesh
  } | null>(null)

  // Mouse interaction state for manual orbit
  const mouseState = useRef({
    isDragging: false,
    prevX: 0,
    prevY: 0,
    rotX: 0.35,
    rotY: -0.65,
    distance: 12,
  })

  // Setup Three.js Scene
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const width = container.clientWidth
    const height = container.clientHeight || 550

    // 1. Scene & Camera
    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000)
    camera.position.set(0, 3, 12)
    cameraRef.current = camera

    // 2. WebGL Renderer
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

    // 3. Lighting (Industrial High-Contrast Dark SCADA Studio)
    const ambientLight = new THREE.AmbientLight(0x0f172a, 2.5)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight(0x38bdf8, 3.2)
    keyLight.position.set(8, 12, 10)
    keyLight.castShadow = true
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight(0x818cf8, 1.8)
    fillLight.position.set(-10, -4, -6)
    scene.add(fillLight)

    const rimLight = new THREE.PointLight(0x06b6d4, 3.5, 30)
    rimLight.position.set(0, 6, -8)
    scene.add(rimLight)

    const underGlow = new THREE.PointLight(0x22d3ee, 2.0, 20)
    underGlow.position.set(0, -5, 0)
    scene.add(underGlow)

    // 4. Ground Grid / Measurement Plane
    const gridHelper = new THREE.GridHelper(16, 16, 0x0ea5e9, 0x1e293b)
    gridHelper.position.y = -3.2
    scene.add(gridHelper)

    // 5. Construct Motor 3D Model Assembly (RS-775 Form Factor)
    const motorGroup = new THREE.Group()
    motorGroupRef.current = motorGroup
    scene.add(motorGroup)

    // Materials
    const statorMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.85,
      roughness: 0.28,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.25,
    })
    statorMaterialRef.current = statorMaterial

    const chromeMaterial = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      metalness: 0.95,
      roughness: 0.12,
    })

    const copperMaterial = new THREE.MeshStandardMaterial({
      color: 0xc27803,
      metalness: 0.7,
      roughness: 0.35,
    })

    const darkAlloyMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.6,
      roughness: 0.5,
    })

    const brassMaterial = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      metalness: 0.85,
      roughness: 0.25,
    })

    // A. Stator Housing Cylinder
    const statorGeo = new THREE.CylinderGeometry(2.1, 2.1, 5.2, 32, 1, true)
    const stator = new THREE.Mesh(statorGeo, statorMaterial)
    stator.rotation.z = Math.PI / 2
    stator.castShadow = true
    motorGroup.add(stator)

    // B. Stator Cooling Fins (Exterior heat dissipation rings)
    const finGroup = new THREE.Group()
    for (let i = -2; i <= 2; i += 0.5) {
      if (Math.abs(i) < 0.2) continue // center badge clearance
      const finGeo = new THREE.TorusGeometry(2.18, 0.06, 8, 32)
      const finMesh = new THREE.Mesh(finGeo, darkAlloyMaterial)
      finMesh.position.x = i
      finMesh.rotation.y = Math.PI / 2
      finGroup.add(finMesh)
    }
    motorGroup.add(finGroup)

    // C. Internal Armature / Copper Windings (Visible in exploded/wireframe view)
    const copperCoils = new THREE.Group()
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3
      const coilGeo = new THREE.BoxGeometry(3.6, 0.45, 0.65)
      const coilMesh = new THREE.Mesh(coilGeo, copperMaterial)
      coilMesh.position.set(0, Math.cos(angle) * 1.25, Math.sin(angle) * 1.25)
      coilMesh.rotation.x = angle
      copperCoils.add(coilMesh)
    }
    motorGroup.add(copperCoils)

    // D. Rotor & Shaft Assembly (Spins during runtime)
    const rotorGroup = new THREE.Group()
    rotorRef.current = rotorGroup

    // Center Steel Shaft
    const shaftGeo = new THREE.CylinderGeometry(0.35, 0.35, 9.4, 24)
    const shaft = new THREE.Mesh(shaftGeo, chromeMaterial)
    shaft.rotation.z = Math.PI / 2
    rotorGroup.add(shaft)

    // Shaft Keyway D-cut flat
    const keyGeo = new THREE.BoxGeometry(1.6, 0.12, 0.38)
    const keyMesh = new THREE.Mesh(keyGeo, darkAlloyMaterial)
    keyMesh.position.set(3.8, 0.28, 0)
    rotorGroup.add(keyMesh)

    // Internal Rotor Core laminations
    const coreGeo = new THREE.CylinderGeometry(1.7, 1.7, 3.8, 24)
    const coreMesh = new THREE.Mesh(coreGeo, darkAlloyMaterial)
    coreMesh.rotation.z = Math.PI / 2
    rotorGroup.add(coreMesh)

    motorGroup.add(rotorGroup)

    // E. Front Drive-End Cap (Front Bearing Housing & Mounting Holes)
    const frontCapGeo = new THREE.CylinderGeometry(2.15, 2.15, 0.6, 32)
    const frontCap = new THREE.Mesh(frontCapGeo, darkAlloyMaterial)
    frontCap.rotation.z = Math.PI / 2
    frontCap.position.x = 2.85
    motorGroup.add(frontCap)

    // Front Bearing
    const bearingGeo = new THREE.CylinderGeometry(0.75, 0.75, 0.4, 24)
    const bearingFront = new THREE.Mesh(bearingGeo, chromeMaterial)
    bearingFront.rotation.z = Math.PI / 2
    bearingFront.position.x = 3.2
    motorGroup.add(bearingFront)

    // F. Rear Commutator Cap (With ventilation vents)
    const rearCapGeo = new THREE.CylinderGeometry(2.15, 2.15, 0.6, 32)
    const rearCap = new THREE.Mesh(rearCapGeo, darkAlloyMaterial)
    rearCap.rotation.z = Math.PI / 2
    rearCap.position.x = -2.85
    motorGroup.add(rearCap)

    // Rear Bearing
    const bearingRear = new THREE.Mesh(bearingGeo, chromeMaterial)
    bearingRear.rotation.z = Math.PI / 2
    bearingRear.position.x = -3.2
    motorGroup.add(bearingRear)

    // G. Terminal Blocks (+ and - Power Connectors on Rear Cap)
    const termPosGeo = new THREE.BoxGeometry(0.3, 0.6, 0.25)
    const termPos = new THREE.Mesh(termPosGeo, brassMaterial)
    termPos.position.set(-2.85, 1.4, 0.9)
    motorGroup.add(termPos)

    const termNeg = new THREE.Mesh(termPosGeo, brassMaterial)
    termNeg.position.set(-2.85, 1.4, -0.9)
    motorGroup.add(termNeg)

    // H. Heavy Mounting Cradle Bracket Base
    const mountBaseGeo = new THREE.BoxGeometry(5.4, 0.45, 4.2)
    const mountBase = new THREE.Mesh(mountBaseGeo, darkAlloyMaterial)
    mountBase.position.set(0, -2.4, 0)
    motorGroup.add(mountBase)

    // Vibration Dampener Pads under mount
    for (const dx of [-2.2, 2.2]) {
      for (const dz of [-1.6, 1.6]) {
        const padGeo = new THREE.CylinderGeometry(0.35, 0.35, 0.25, 16)
        const pad = new THREE.Mesh(padGeo, new THREE.MeshStandardMaterial({ color: 0x0284c7 }))
        pad.position.set(dx, -2.7, dz)
        motorGroup.add(pad)
      }
    }

    // Save parts for Exploded View interpolation
    explodedPartsRef.current = {
      frontCap,
      rearCap,
      rotor: rotorGroup,
      stator,
      bearingFront,
      bearingRear,
    }

    // 6. Magnetic Flux Particle Ring
    const particleCount = 200
    const particlePositions = new Float32Array(particleCount * 3)
    for (let i = 0; i < particleCount; i++) {
      const radius = 2.4 + Math.random() * 0.8
      const theta = Math.random() * Math.PI * 2
      const x = (Math.random() - 0.5) * 5.0
      particlePositions[i * 3] = x
      particlePositions[i * 3 + 1] = Math.cos(theta) * radius
      particlePositions[i * 3 + 2] = Math.sin(theta) * radius
    }
    const particleGeo = new THREE.BufferGeometry()
    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3))
    const particleMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.08,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
    })
    const particleSystem = new THREE.Points(particleGeo, particleMat)
    motorGroup.add(particleSystem)

    // 7. Interactive Mouse Controls (Orbit, Zoom)
    let isMouseDown = false
    let startX = 0
    let startY = 0

    const onPointerDown = (e: PointerEvent) => {
      isMouseDown = true
      startX = e.clientX
      startY = e.clientY
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!isMouseDown) return
      const deltaX = e.clientX - startX
      const deltaY = e.clientY - startY
      startX = e.clientX
      startY = e.clientY

      mouseState.current.rotY += deltaX * 0.008
      mouseState.current.rotX += deltaY * 0.008
      mouseState.current.rotX = Math.max(-1.2, Math.min(1.2, mouseState.current.rotX))
    }

    const onPointerUp = () => {
      isMouseDown = false
    }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      mouseState.current.distance += e.deltaY * 0.008
      mouseState.current.distance = Math.max(6, Math.min(22, mouseState.current.distance))
    }

    canvas.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })

    // 8. Resize Handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return
      const w = container.clientWidth
      const h = container.clientHeight || 550
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', handleResize)

    // 9. Animation Loop
    let animationFrameId: number
    let clock = new THREE.Clock()

    // 3D sensor coordinates in world space for screen projection
    const adxlPos = new THREE.Vector3(3.2, 0.8, 0) // Front bearing
    const acsPos = new THREE.Vector3(-2.85, 2.0, 0.9) // Terminals
    const tempPos = new THREE.Vector3(0, 2.4, 0) // Stator chassis
    const esp32Pos = new THREE.Vector3(0, -2.4, 2.4) // Gateway bracket

    const renderLoop = () => {
      const delta = clock.getDelta()
      const time = clock.getElapsedTime()

      // A. Camera Orbit Positioning
      if (autoRotateRef.current && !isMouseDown) {
        mouseState.current.rotY += 0.004
      }

      const dist = mouseState.current.distance
      const rx = mouseState.current.rotX
      const ry = mouseState.current.rotY

      camera.position.x = dist * Math.sin(ry) * Math.cos(rx)
      camera.position.y = dist * Math.sin(rx) + 0.5
      camera.position.z = dist * Math.cos(ry) * Math.cos(rx)
      camera.lookAt(0, 0, 0)

      // B. Dynamic Motor Vibration Jitter & Rotor RPM
      if (motorGroupRef.current && rotorRef.current) {
        const curMotor = activeMotorRef.current
        const vibration = curMotor?.latest.sensors.temperature_c ? (curMotor?.latest.sensors.vibration_g_rms ?? 0.05) : 0.05
        const health = curMotor?.latest.inference.health_status ?? 'healthy'

        // Dynamic vibration shake based on real vibration_g_rms
        const shakeIntensity = vibration * 0.08
        motorGroupRef.current.position.y = Math.sin(time * 65) * shakeIntensity
        motorGroupRef.current.position.z = Math.cos(time * 50) * (shakeIntensity * 0.7)

        // Rotor Spin Speed: healthy spins fast, critical stutters
        const baseSpeed = health === 'critical' ? 24 : health === 'warning' ? 16 : 30
        rotorRef.current.rotation.x += delta * baseSpeed

        // Particle swirl
        particleSystem.rotation.x += delta * 1.5
      }

      // C. Exploded View Smooth Interpolation
      if (explodedPartsRef.current) {
        const targetExplode = isExplodedRef.current ? 2.5 : 0
        const { frontCap, rearCap, bearingFront, bearingRear } = explodedPartsRef.current

        frontCap.position.x += ((2.85 + targetExplode) - frontCap.position.x) * 0.1
        bearingFront.position.x += ((3.2 + targetExplode * 1.4) - bearingFront.position.x) * 0.1
        rearCap.position.x += ((-2.85 - targetExplode) - rearCap.position.x) * 0.1
        bearingRear.position.x += ((-3.2 - targetExplode * 1.4) - bearingRear.position.x) * 0.1
      }

      // D. Project Sensor 3D Pins to 2D Screen
      if (container && camera) {
        const project = (pos: THREE.Vector3) => {
          const p = pos.clone()
          motorGroup.localToWorld(p)
          p.project(camera)
          const halfW = container.clientWidth / 2
          const halfH = (container.clientHeight || 550) / 2
          const x = p.x * halfW + halfW
          const y = -(p.y * halfH) + halfH
          return { x, y, visible: p.z < 1 }
        }

        setSensorCoords({
          adxl: project(adxlPos),
          acs: project(acsPos),
          temp: project(tempPos),
          esp32: project(esp32Pos),
        })
      }

      renderer.render(scene, camera)
      animationFrameId = requestAnimationFrame(renderLoop)
    }

    renderLoop()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', handleResize)
      canvas.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('wheel', onWheel)
      renderer.dispose()
    }
  }, [])

  // Update Dynamic Stator Thermal Emissive Glow based on activeMotor temperature
  useEffect(() => {
    if (!statorMaterialRef.current) return
    const temp = activeMotor?.latest.sensors.temperature_c ?? 35
    const health = activeMotor?.latest.inference.health_status ?? 'healthy'

    if (health === 'critical' || temp >= 55) {
      statorMaterialRef.current.emissive.setHex(0xef4444) // Intense infrared crimson
      statorMaterialRef.current.emissiveIntensity = 0.85
    } else if (health === 'warning' || temp >= 45) {
      statorMaterialRef.current.emissive.setHex(0xf59e0b) // Warning warm amber
      statorMaterialRef.current.emissiveIntensity = 0.55
    } else {
      statorMaterialRef.current.emissive.setHex(0x06b6d4) // Nominal cyber cyan
      statorMaterialRef.current.emissiveIntensity = 0.25
    }

    statorMaterialRef.current.wireframe = isWireframe
  }, [activeMotor, isWireframe])

  return (
    <div className="digital-twin-container">
      {/* 3D Viewport Header & Controls */}
      <div className="twin-control-bar">
        <div className="twin-header-info">
          <div className="twin-title-row">
            <span className="twin-badge">THREE.JS DIGITAL TWIN</span>
            <h3 className="twin-title">
              {activeMotor ? `${activeMotor.motor_id} — Real-Time 3D Spatial Twin` : '3D Motor Twin'}
            </h3>
          </div>
          <p className="twin-desc">
            Direct spatial mapping of ADXL345 dynamic vibration displacement, ACS712 current, and thermal heat emissions.
          </p>
        </div>

        {/* Motor Asset Selector */}
        <div className="twin-actions">
          <div className="twin-selector-group">
            <label className="twin-label">Asset:</label>
            <select
              className="twin-select"
              value={activeMotor?.motor_id || ''}
              onChange={(e) => onSelectMotor?.(e.target.value)}
            >
              {motors.map((m) => (
                <option key={m.motor_id} value={m.motor_id}>
                  {m.motor_id} ({m.latest.inference.health_status.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          {/* Interactive Mode Toggles */}
          <div className="twin-btn-group">
            <button
              className={`twin-toggle-btn ${isWireframe ? 'active' : ''}`}
              onClick={() => setIsWireframe(!isWireframe)}
              title="Toggle Wireframe Structural Mode"
            >
              🕸️ Wireframe
            </button>

            <button
              className={`twin-toggle-btn ${isExploded ? 'active' : ''}`}
              onClick={() => setIsExploded(!isExploded)}
              title="Toggle Exploded Mechanical Assembly"
            >
              💥 Exploded View
            </button>

            <button
              className={`twin-toggle-btn ${showSensors ? 'active' : ''}`}
              onClick={() => setShowSensors(!showSensors)}
              title="Toggle Sensor Annotation Pins"
            >
              📍 Sensor Pins
            </button>

            <button
              className={`twin-toggle-btn ${autoRotate ? 'active' : ''}`}
              onClick={() => setAutoRotate(!autoRotate)}
              title="Toggle Auto Orbit"
            >
              {autoRotate ? '⏸️ Pause Orbit' : '▶️ Auto Orbit'}
            </button>
          </div>
        </div>
      </div>

      {/* 3D WebGL Canvas Viewport */}
      <div className="twin-viewport" ref={containerRef}>
        <canvas ref={canvasRef} className="twin-canvas" />

        {/* Orbit Helper Watermark */}
        <div className="twin-hint">
          🖱️ Click &amp; Drag to Orbit • Scroll to Zoom • Physical RS-775 Form Factor
        </div>

        {/* Live Telemetry HUD Overlay in Top-Left */}
        {activeMotor && (
          <div className="twin-hud-card">
            <div className="twin-hud-header">
              <span className={`status-pill ${activeMotor.latest.inference.health_status}`}>
                {activeMotor.latest.inference.health_status.toUpperCase()}
              </span>
              <span className="twin-hud-source">
                {activeMotor.source.toUpperCase()}
              </span>
            </div>

            <div className="twin-hud-metrics">
              <div className="twin-hud-row">
                <span className="hud-metric-label">Temperature:</span>
                <span className="hud-metric-val">
                  {activeMotor.latest.sensors.temperature_c != null
                    ? `${activeMotor.latest.sensors.temperature_c.toFixed(1)} °C`
                    : 'N/A'}
                </span>
              </div>

              <div className="twin-hud-row">
                <span className="hud-metric-label">Dynamic Vibration:</span>
                <span className="hud-metric-val">
                  {activeMotor.latest.sensors.vibration_g_rms != null
                    ? `${activeMotor.latest.sensors.vibration_g_rms.toFixed(3)} g`
                    : 'N/A'}
                </span>
              </div>

              <div className="twin-hud-row">
                <span className="hud-metric-label">Current Draw:</span>
                <span className="hud-metric-val">
                  {activeMotor.latest.sensors.current_a != null
                    ? `${activeMotor.latest.sensors.current_a.toFixed(2)} A`
                    : 'N/A'}
                </span>
              </div>

              <div className="twin-hud-row">
                <span className="hud-metric-label">TinyML Confidence:</span>
                <span className="hud-metric-val">
                  {(activeMotor.latest.inference.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Sensor 3D Annotation Pins (Screen Space Projected) */}
        {showSensors && sensorCoords.adxl.visible && (
          <div
            className={`sensor-pin ${hoveredSensor === 'adxl' ? 'hovered' : ''}`}
            style={{ left: `${sensorCoords.adxl.x}px`, top: `${sensorCoords.adxl.y}px` }}
            onMouseEnter={() => setHoveredSensor('adxl')}
            onMouseLeave={() => setHoveredSensor(null)}
          >
            <div className="pin-pulse" />
            <div className="pin-label">
              <strong>ADXL345</strong>
              <span>
                {activeMotor?.latest.sensors.vibration_g_rms != null
                  ? `${activeMotor.latest.sensors.vibration_g_rms.toFixed(3)}g`
                  : 'Vibration'}
              </span>
            </div>
          </div>
        )}

        {showSensors && sensorCoords.acs.visible && (
          <div
            className={`sensor-pin ${hoveredSensor === 'acs' ? 'hovered' : ''}`}
            style={{ left: `${sensorCoords.acs.x}px`, top: `${sensorCoords.acs.y}px` }}
            onMouseEnter={() => setHoveredSensor('acs')}
            onMouseLeave={() => setHoveredSensor(null)}
          >
            <div className="pin-pulse" />
            <div className="pin-label">
              <strong>ACS712-20A</strong>
              <span>
                {activeMotor?.latest.sensors.current_a != null
                  ? `${activeMotor.latest.sensors.current_a.toFixed(2)}A`
                  : 'Current'}
              </span>
            </div>
          </div>
        )}

        {showSensors && sensorCoords.temp.visible && (
          <div
            className={`sensor-pin ${hoveredSensor === 'temp' ? 'hovered' : ''}`}
            style={{ left: `${sensorCoords.temp.x}px`, top: `${sensorCoords.temp.y}px` }}
            onMouseEnter={() => setHoveredSensor('temp')}
            onMouseLeave={() => setHoveredSensor(null)}
          >
            <div className="pin-pulse" />
            <div className="pin-label">
              <strong>DHT11 / Temp</strong>
              <span>
                {activeMotor?.latest.sensors.temperature_c != null
                  ? `${activeMotor.latest.sensors.temperature_c.toFixed(1)}°C`
                  : 'Thermal'}
              </span>
            </div>
          </div>
        )}

        {showSensors && sensorCoords.esp32.visible && (
          <div
            className={`sensor-pin ${hoveredSensor === 'esp32' ? 'hovered' : ''}`}
            style={{ left: `${sensorCoords.esp32.x}px`, top: `${sensorCoords.esp32.y}px` }}
            onMouseEnter={() => setHoveredSensor('esp32')}
            onMouseLeave={() => setHoveredSensor(null)}
          >
            <div className="pin-pulse" />
            <div className="pin-label">
              <strong>ESP32 TinyML</strong>
              <span>EON Model #1133176</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
