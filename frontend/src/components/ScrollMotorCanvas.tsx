import { useRef, useEffect, useState } from 'react'
import type { FC } from 'react'
import * as THREE from 'three'

interface ScrollMotorCanvasProps {
  scrollProgress: number // 0.0 (hero assembled) to 1.0 (final stage)
  activeStage?: number   // 0: Assembled Hero, 1: Exploded View, 2: Sensors, 3: TinyML Pulse
  onStageChange?: (stage: number) => void
}

export const ScrollMotorCanvas: FC<ScrollMotorCanvasProps> = ({
  scrollProgress,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Interactive controls
  const [isWireframe, setIsWireframe] = useState(false)

  // Three.js object references
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const motorGroupRef = useRef<THREE.Group | null>(null)
  const rotorRef = useRef<THREE.Group | null>(null)
  const pulseRingsRef = useRef<THREE.Mesh[]>([])
  
  // Exploded parts references
  const partsRef = useRef<{
    stator: THREE.Mesh
    fins: THREE.Group
    coils: THREE.Group
    rotor: THREE.Group
    frontCap: THREE.Mesh
    bearingFront: THREE.Mesh
    rearCap: THREE.Mesh
    bearingRear: THREE.Mesh
    adxlSensor: THREE.Group
    acsSensor: THREE.Group
    dhtSensor: THREE.Group
  } | null>(null)

  // Current smooth scroll lerp
  const currentScrollRef = useRef(0)
  const targetScrollRef = useRef(0)

  useEffect(() => {
    targetScrollRef.current = Math.max(0, Math.min(1, scrollProgress))
  }, [scrollProgress])

  // Mouse orbit state
  const mouseState = useRef({
    isDragging: false,
    prevX: 0,
    prevY: 0,
    rotX: 0.25,
    rotY: -0.55,
  })

  // Setup Three.js Scene
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const width = container.clientWidth || 600
    const height = container.clientHeight || 550

    // 1. Scene
    const scene = new THREE.Scene()
    sceneRef.current = scene

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100)
    camera.position.set(0, 1.5, 13)
    cameraRef.current = camera

    // 3. Renderer with antialiasing
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    rendererRef.current = renderer

    // 4. Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight(0x38bdf8, 3.2)
    keyLight.position.set(8, 12, 10)
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight(0x818cf8, 2.0)
    fillLight.position.set(-10, -4, -6)
    scene.add(fillLight)

    const cyanRim = new THREE.PointLight(0x00f0ff, 4.0, 35)
    cyanRim.position.set(0, 6, -8)
    scene.add(cyanRim)

    const amberGlow = new THREE.PointLight(0xf59e0b, 2.5, 25)
    amberGlow.position.set(6, -4, 4)
    scene.add(amberGlow)

    // 5. Holographic Floor Grid
    const gridHelper = new THREE.GridHelper(18, 18, 0x0ea5e9, 0x1e293b)
    gridHelper.position.y = -3.2
    scene.add(gridHelper)

    // 6. Construct High-Fidelity RS-775 Motor Model
    const motorGroup = new THREE.Group()
    motorGroupRef.current = motorGroup
    scene.add(motorGroup)

    // Materials
    const statorMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.88,
      roughness: 0.26,
      emissive: 0x0284c7,
      emissiveIntensity: 0.18,
    })

    const chromeMat = new THREE.MeshStandardMaterial({
      color: 0xf1f5f9,
      metalness: 0.96,
      roughness: 0.10,
    })

    const copperMat = new THREE.MeshStandardMaterial({
      color: 0xd97706,
      metalness: 0.75,
      roughness: 0.32,
    })

    const darkAlloyMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.65,
      roughness: 0.45,
    })

    const sensorHousingMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      metalness: 0.5,
      roughness: 0.2,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.4,
    })

    // A. Stator Housing Cylinder
    const statorGeo = new THREE.CylinderGeometry(2.1, 2.1, 5.2, 36, 1, true)
    const stator = new THREE.Mesh(statorGeo, statorMat)
    stator.rotation.z = Math.PI / 2
    motorGroup.add(stator)

    // B. Stator Cooling Fins
    const finsGroup = new THREE.Group()
    for (let i = -2.1; i <= 2.1; i += 0.45) {
      if (Math.abs(i) < 0.25) continue
      const finGeo = new THREE.TorusGeometry(2.18, 0.05, 8, 36)
      const finMesh = new THREE.Mesh(finGeo, darkAlloyMat)
      finMesh.position.x = i
      finMesh.rotation.y = Math.PI / 2
      finsGroup.add(finMesh)
    }
    motorGroup.add(finsGroup)

    // C. Internal Armature Copper Windings
    const coilsGroup = new THREE.Group()
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3
      const coilGeo = new THREE.BoxGeometry(3.6, 0.48, 0.68)
      const coilMesh = new THREE.Mesh(coilGeo, copperMat)
      coilMesh.position.set(0, Math.cos(angle) * 1.25, Math.sin(angle) * 1.25)
      coilMesh.rotation.x = angle
      coilsGroup.add(coilMesh)
    }
    motorGroup.add(coilsGroup)

    // D. Rotor & Shaft Assembly
    const rotorGroup = new THREE.Group()
    rotorRef.current = rotorGroup

    const shaftGeo = new THREE.CylinderGeometry(0.35, 0.35, 9.6, 24)
    const shaft = new THREE.Mesh(shaftGeo, chromeMat)
    shaft.rotation.z = Math.PI / 2
    rotorGroup.add(shaft)

    const coreGeo = new THREE.CylinderGeometry(1.7, 1.7, 3.8, 24)
    const coreMesh = new THREE.Mesh(coreGeo, darkAlloyMat)
    coreMesh.rotation.z = Math.PI / 2
    rotorGroup.add(coreMesh)

    motorGroup.add(rotorGroup)

    // E. Front Drive-End Cap & Bearing
    const frontCapGeo = new THREE.CylinderGeometry(2.15, 2.15, 0.6, 36)
    const frontCap = new THREE.Mesh(frontCapGeo, darkAlloyMat)
    frontCap.rotation.z = Math.PI / 2
    frontCap.position.x = 2.85
    motorGroup.add(frontCap)

    const bearingGeo = new THREE.CylinderGeometry(0.75, 0.75, 0.4, 24)
    const bearingFront = new THREE.Mesh(bearingGeo, chromeMat)
    bearingFront.rotation.z = Math.PI / 2
    bearingFront.position.x = 3.2
    motorGroup.add(bearingFront)

    // F. Rear Cap & Bearing
    const rearCapGeo = new THREE.CylinderGeometry(2.15, 2.15, 0.6, 36)
    const rearCap = new THREE.Mesh(rearCapGeo, darkAlloyMat)
    rearCap.rotation.z = Math.PI / 2
    rearCap.position.x = -2.85
    motorGroup.add(rearCap)

    const bearingRear = new THREE.Mesh(bearingGeo, chromeMat)
    bearingRear.rotation.z = Math.PI / 2
    bearingRear.position.x = -3.2
    motorGroup.add(bearingRear)

    // G. Sensor 3D Callout Badges attached to motor
    // 1. ADXL345 on front bearing mount
    const adxlGroup = new THREE.Group()
    const adxlBox = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.25, 0.5), sensorHousingMat)
    const adxlPin = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.8), chromeMat)
    adxlPin.position.y = 0.4
    adxlGroup.add(adxlBox)
    adxlGroup.add(adxlPin)
    adxlGroup.position.set(2.8, 2.3, 0)
    motorGroup.add(adxlGroup)

    // 2. ACS712 on electrical terminals (rear)
    const acsGroup = new THREE.Group()
    const acsBox = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.3, 0.45), new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x059669,
      emissiveIntensity: 0.5,
    }))
    acsGroup.add(acsBox)
    acsGroup.position.set(-2.8, 1.8, 1.2)
    motorGroup.add(acsGroup)

    // 3. DHT11 on stator cylinder
    const dhtGroup = new THREE.Group()
    const dhtBox = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.6, 0.3), new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      emissive: 0xd97706,
      emissiveIntensity: 0.4,
    }))
    dhtGroup.add(dhtBox)
    dhtGroup.position.set(0, 2.3, -0.6)
    motorGroup.add(dhtGroup)

    // H. TinyML Neural Pulse Rings
    const pulseRings: THREE.Mesh[] = []
    for (let i = 0; i < 3; i++) {
      const ringGeo = new THREE.TorusGeometry(2.4 + i * 0.4, 0.03, 8, 36)
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0x00f0ff,
        transparent: true,
        opacity: 0,
      })
      const ring = new THREE.Mesh(ringGeo, ringMat)
      ring.rotation.y = Math.PI / 2
      motorGroup.add(ring)
      pulseRings.push(ring)
    }
    pulseRingsRef.current = pulseRings

    // Save parts references
    partsRef.current = {
      stator,
      fins: finsGroup,
      coils: coilsGroup,
      rotor: rotorGroup,
      frontCap,
      bearingFront,
      rearCap,
      bearingRear,
      adxlSensor: adxlGroup,
      acsSensor: acsGroup,
      dhtSensor: dhtGroup,
    }

    // 7. Render Loop
    let animId: number
    const clock = new THREE.Clock()

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const delta = clock.getDelta()
      const time = clock.getElapsedTime()

      // Smooth scroll lerp (0.0 -> 1.0)
      currentScrollRef.current += (targetScrollRef.current - currentScrollRef.current) * 0.08
      const p = currentScrollRef.current

      // Continuous rotor spin
      if (rotorRef.current) {
        rotorRef.current.rotation.x += delta * 4.0
      }

      // Dynamic Transformation based on scroll progress:
      if (motorGroupRef.current && partsRef.current) {
        const {
          stator: st,
          fins: fn,
          coils: cl,
          frontCap: fc,
          bearingFront: bf,
          rearCap: rc,
          bearingRear: br,
          adxlSensor: adxl,
          acsSensor: acs,
          dhtSensor: dht,
        } = partsRef.current

        // STAGE 0 to STAGE 1: Explosion & Rotation (p: 0.0 -> 0.4)
        const explodeFactor = Math.max(0, Math.min(1, (p - 0.15) / 0.35))
        
        // Front assembly slides forward (+X)
        fc.position.x = 2.85 + explodeFactor * 3.2
        bf.position.x = 3.2 + explodeFactor * 4.4
        
        // Rear assembly slides backward (-X)
        rc.position.x = -2.85 - explodeFactor * 3.2
        br.position.x = -3.2 - explodeFactor * 4.4
        
        // Stator lifts slightly up and becomes semi-transparent in exploded view
        st.position.y = explodeFactor * 1.6
        fn.position.y = explodeFactor * 1.6
        ;(st.material as THREE.MeshStandardMaterial).opacity = 1.0 - explodeFactor * 0.45
        ;(st.material as THREE.MeshStandardMaterial).transparent = explodeFactor > 0.01

        // Coils expand radially
        cl.scale.set(1 + explodeFactor * 0.3, 1 + explodeFactor * 0.3, 1 + explodeFactor * 0.3)

        // STAGE 2: Sensor Pulse (p: 0.4 -> 0.75)
        const sensorPhase = Math.max(0, Math.min(1, (p - 0.45) / 0.3))
        adxl.scale.setScalar(1 + Math.sin(time * 4) * 0.15 * sensorPhase)
        acs.scale.setScalar(1 + Math.cos(time * 4) * 0.15 * sensorPhase)
        dht.scale.setScalar(1 + Math.sin(time * 3 + 1) * 0.15 * sensorPhase)

        // STAGE 3: TinyML Neural Pulse Wave (p: 0.7 -> 1.0)
        const mlPhase = Math.max(0, Math.min(1, (p - 0.70) / 0.3))
        pulseRingsRef.current.forEach((ring, idx) => {
          const ringMat = ring.material as THREE.MeshBasicMaterial
          const wave = (time * 2 + idx * 0.8) % 3
          ringMat.opacity = Math.max(0, (1 - wave / 3) * mlPhase * 0.85)
          ring.scale.setScalar(1 + wave * 0.35)
        })

        // Motor Base Rotation driven by scroll + mouse
        if (!mouseState.current.isDragging) {
          // Autonomous scroll rotation path
          const targetRotY = -0.55 + p * Math.PI * 1.6
          const targetRotX = 0.25 + Math.sin(p * Math.PI) * 0.35
          motorGroupRef.current.rotation.y += (targetRotY - motorGroupRef.current.rotation.y) * 0.05
          motorGroupRef.current.rotation.x += (targetRotX - motorGroupRef.current.rotation.x) * 0.05
        } else {
          motorGroupRef.current.rotation.y = mouseState.current.rotY
          motorGroupRef.current.rotation.x = mouseState.current.rotX
        }

        // Idle floating levitation
        motorGroupRef.current.position.y = Math.sin(time * 1.8) * 0.15
      }

      renderer.render(scene, camera)
    }
    animate()

    // 8. Resize Handler
    const handleResize = () => {
      if (!container || !camera || !renderer) return
      const w = container.clientWidth
      const h = container.clientHeight || 550
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', handleResize)

    // Cleanup
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      renderer.dispose()
    }
  }, [])

  // Mouse drag interaction
  const handleMouseDown = (e: React.MouseEvent) => {
    mouseState.current.isDragging = true
    mouseState.current.prevX = e.clientX
    mouseState.current.prevY = e.clientY
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!mouseState.current.isDragging) return
    const dx = e.clientX - mouseState.current.prevX
    const dy = e.clientY - mouseState.current.prevY
    mouseState.current.prevX = e.clientX
    mouseState.current.prevY = e.clientY
    mouseState.current.rotY += dx * 0.008
    mouseState.current.rotX += dy * 0.008
    mouseState.current.rotX = Math.max(-1.2, Math.min(1.2, mouseState.current.rotX))
  }

  const handleMouseUp = () => {
    mouseState.current.isDragging = false
  }

  // Toggle wireframe mode
  const handleToggleWireframe = () => {
    setIsWireframe(!isWireframe)
    if (sceneRef.current) {
      sceneRef.current.traverse((child) => {
        if (child instanceof THREE.Mesh && child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach((m) => { m.wireframe = !isWireframe })
          } else {
            child.material.wireframe = !isWireframe
          }
        }
      })
    }
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: '480px',
        overflow: 'hidden',
        cursor: mouseState.current.isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      />

      {/* Floating HUD Controls */}
      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          display: 'flex',
          gap: '8px',
          zIndex: 10,
        }}
      >
        <button
          type="button"
          onClick={handleToggleWireframe}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: isWireframe ? '1px solid var(--brand-primary)' : '1px solid var(--border-strong)',
            background: isWireframe ? 'var(--brand-primary-light)' : 'var(--bg-panel)',
            boxShadow: 'var(--shadow-xs)',
            color: 'var(--brand-primary)',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          {isWireframe ? 'Solid Model' : 'Wireframe X-Ray'}
        </button>

        <span
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-main)',
            boxShadow: 'var(--shadow-xs)',
            color: 'var(--text-muted)',
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: 'var(--brand-primary)',
              boxShadow: '0 0 6px var(--brand-primary)',
            }}
          />
          Interactive 3D • Drag to Orbit
        </span>
      </div>

      {/* Scroll Milestone Indicators */}
      <div
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 10,
        }}
      >
        {[
          { label: '01 Assembled Hero', range: [0, 0.3] },
          { label: '02 Exploded Anatomy', range: [0.3, 0.6] },
          { label: '03 Sensor Triad', range: [0.6, 0.85] },
          { label: '04 TinyML Core', range: [0.85, 1.0] },
        ].map((item) => {
          const isActive = scrollProgress >= item.range[0] && scrollProgress <= item.range[1]
          return (
            <div
              key={item.label}
              style={{
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.6px',
                padding: '4px 10px',
                borderRadius: '4px',
                background: isActive ? 'var(--brand-primary-light)' : 'var(--bg-panel)',
                border: isActive ? '1px solid var(--brand-primary)' : '1px solid var(--border-main)',
                color: isActive ? 'var(--brand-primary)' : 'var(--text-muted)',
                boxShadow: 'var(--shadow-xs)',
                transition: 'all 0.3s ease',
              }}
            >
              {item.label}
            </div>
          )
        })}
      </div>
    </div>
  )
}
