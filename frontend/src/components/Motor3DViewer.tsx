import type { FC } from 'react'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Box, Pause, Play } from 'lucide-react'
import type { HealthStatus } from '../types'

interface Motor3DViewerProps {
  motorId: string
  healthStatus?: HealthStatus
  temperature?: number | null
  current?: number | null
  vibration?: number | null
}

const isWebGLAvailable = () => {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
  } catch {
    return false
  }
}

export const Motor3DViewer: FC<Motor3DViewerProps> = ({
  motorId,
  healthStatus = 'healthy',
  temperature,
  current,
  vibration,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoRotate, setAutoRotate] = useState(true)
  const [webglSupported] = useState(isWebGLAvailable)

  useEffect(() => {
    const container = containerRef.current
    if (!container || !webglSupported) return

    const width = container.clientWidth || 320
    const height = container.clientHeight || 240

    // Scene setup
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xF9FAFB) // Light clean background matching theme

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100)
    camera.position.set(5.5, 3.8, 6.5)
    camera.lookAt(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    container.appendChild(renderer.domElement)

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xFFFFFF, 0.75)
    scene.add(ambientLight)

    const dirLight = new THREE.DirectionalLight(0xFFFFFF, 1.2)
    dirLight.position.set(8, 12, 6)
    dirLight.castShadow = true
    scene.add(dirLight)

    const fillLight = new THREE.DirectionalLight(0xB0C4DE, 0.4)
    fillLight.position.set(-6, -4, -6)
    scene.add(fillLight)

    // RS-775 Motor Model Group
    const motorGroup = new THREE.Group()

    // 1. Cylindrical Casing (Steel Stator Can)
    const statorGeo = new THREE.CylinderGeometry(1.3, 1.3, 3.4, 32)
    const statorMat = new THREE.MeshStandardMaterial({
      color: 0x94A3B8, // Industrial steel
      metalness: 0.85,
      roughness: 0.35,
    })
    const stator = new THREE.Mesh(statorGeo, statorMat)
    stator.rotation.z = Math.PI / 2
    stator.castShadow = true
    motorGroup.add(stator)

    // 2. Front End Bell (Aluminum cap)
    const frontCapGeo = new THREE.CylinderGeometry(1.32, 1.32, 0.4, 32)
    const frontCapMat = new THREE.MeshStandardMaterial({
      color: 0xCBD5E1,
      metalness: 0.9,
      roughness: 0.2,
    })
    const frontCap = new THREE.Mesh(frontCapGeo, frontCapMat)
    frontCap.position.set(1.85, 0, 0)
    frontCap.rotation.z = Math.PI / 2
    motorGroup.add(frontCap)

    // 3. Rear End Bell (Polymer terminal housing)
    const rearCapGeo = new THREE.CylinderGeometry(1.31, 1.31, 0.35, 32)
    const rearCapMat = new THREE.MeshStandardMaterial({
      color: 0x334155, // Matte black industrial phenolic
      roughness: 0.7,
      metalness: 0.1,
    })
    const rearCap = new THREE.Mesh(rearCapGeo, rearCapMat)
    rearCap.position.set(-1.85, 0, 0)
    rearCap.rotation.z = Math.PI / 2
    motorGroup.add(rearCap)

    // 4. Output Shaft (5mm Ground Steel D-shaft)
    const shaftGeo = new THREE.CylinderGeometry(0.18, 0.18, 1.4, 24)
    const shaftMat = new THREE.MeshStandardMaterial({
      color: 0xE2E8F0,
      metalness: 0.95,
      roughness: 0.15,
    })
    const shaft = new THREE.Mesh(shaftGeo, shaftMat)
    shaft.position.set(2.65, 0, 0)
    shaft.rotation.z = Math.PI / 2
    motorGroup.add(shaft)

    // 5. Motor Mounting Bracket Base
    const bracketGeo = new THREE.BoxGeometry(0.3, 2.2, 2.4)
    const bracketMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      metalness: 0.6,
      roughness: 0.5,
    })
    const bracket = new THREE.Mesh(bracketGeo, bracketMat)
    bracket.position.set(1.65, -0.6, 0)
    motorGroup.add(bracket)

    // 6. Restrained Status Glow Ring
    const ringColor =
      healthStatus === 'critical'
        ? 0xC43D43
        : healthStatus === 'warning'
        ? 0xB7791F
        : 0x23845B

    const ringGeo = new THREE.TorusGeometry(1.33, 0.04, 16, 64)
    const ringMat = new THREE.MeshStandardMaterial({
      color: ringColor,
      emissive: ringColor,
      emissiveIntensity: 0.7,
    })
    const statusRing = new THREE.Mesh(ringGeo, ringMat)
    statusRing.rotation.y = Math.PI / 2
    statusRing.position.set(0, 0, 0)
    motorGroup.add(statusRing)

    scene.add(motorGroup)

    // Subtle Ground Shadow Plate
    const floorGeo = new THREE.PlaneGeometry(12, 12)
    const floorMat = new THREE.ShadowMaterial({ opacity: 0.12 })
    const floor = new THREE.Mesh(floorGeo, floorMat)
    floor.rotation.x = -Math.PI / 2
    floor.position.y = -1.7
    floor.receiveShadow = true
    scene.add(floor)

    // Animation Loop
    let animId: number
    const animate = () => {
      animId = requestAnimationFrame(animate)

      if (autoRotate) {
        motorGroup.rotation.y += 0.005
      }

      renderer.render(scene, camera)
    }

    animate()

    // Resize Handler
    const handleResize = () => {
      if (!container) return
      const w = container.clientWidth
      const h = container.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }

    window.addEventListener('resize', handleResize)

    // Cleanup & WebGL Disposal
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }

      // Dispose resources
      statorGeo.dispose()
      statorMat.dispose()
      frontCapGeo.dispose()
      frontCapMat.dispose()
      rearCapGeo.dispose()
      rearCapMat.dispose()
      shaftGeo.dispose()
      shaftMat.dispose()
      bracketGeo.dispose()
      bracketMat.dispose()
      ringGeo.dispose()
      ringMat.dispose()
      floorGeo.dispose()
      floorMat.dispose()
      renderer.dispose()
    }
  }, [autoRotate, healthStatus, webglSupported])

  return (
    <div className="motor-3d-card">
      <div className="motor-3d-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Box size={16} color="var(--brand-primary)" />
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
            Physical Twin Model: {motorId}
          </span>
        </div>

        <button
          className="btn-icon-toolbar"
          onClick={() => setAutoRotate(!autoRotate)}
          title={autoRotate ? 'Pause Rotation' : 'Resume Rotation'}
          aria-label="Toggle Rotation"
        >
          {autoRotate ? <Pause size={13} /> : <Play size={13} />}
        </button>
      </div>

      <div className="motor-3d-canvas-wrap" ref={containerRef}>
        {!webglSupported && (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
            WebGL context not available. Displaying static schematic mode.
          </div>
        )}
        <div className="motor-3d-overlay tabular-nums">
          RS-775 DC Drive • T: {temperature != null ? `${temperature.toFixed(1)}°C` : '—'} • I: {current != null ? `${current.toFixed(2)}A` : '—'} • Vib: {vibration != null ? `${vibration.toFixed(3)}g` : '—'}
        </div>
      </div>
    </div>
  )
}
