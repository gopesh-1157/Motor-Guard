import { useRef, useEffect } from 'react'
import type { FC } from 'react'
import * as THREE from 'three'

export const CyberBackground3D: FC = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const width = container.clientWidth
    const height = container.clientHeight

    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x020617, 0.04)

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100)
    camera.position.set(0, 2, 9)

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))

    // Ambient & Point lights
    const ambientLight = new THREE.AmbientLight(0x0284c7, 1.5)
    scene.add(ambientLight)

    const cyanLight = new THREE.PointLight(0x06b6d4, 3, 20)
    cyanLight.position.set(-4, 3, 2)
    scene.add(cyanLight)

    const amberLight = new THREE.PointLight(0xf59e0b, 2.5, 20)
    amberLight.position.set(4, -2, -1)
    scene.add(amberLight)

    // Cyber Grid Floor
    const grid = new THREE.GridHelper(30, 30, 0x0284c7, 0x0f172a)
    grid.position.y = -2.5
    scene.add(grid)

    // Central Wireframe Motor Assembly (Geometric Rings & Cylinders)
    const motorWireGroup = new THREE.Group()
    scene.add(motorWireGroup)

    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.18,
    })

    const statorWire = new THREE.Mesh(new THREE.CylinderGeometry(1.8, 1.8, 4.2, 16, 4, true), wireMat)
    statorWire.rotation.z = Math.PI / 2
    motorWireGroup.add(statorWire)

    const rotorWireMat = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      wireframe: true,
      transparent: true,
      opacity: 0.22,
    })
    const rotorShaft = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 7.0, 12, 1), rotorWireMat)
    rotorShaft.rotation.z = Math.PI / 2
    motorWireGroup.add(rotorShaft)

    // Torus Rings
    for (let i = -1.6; i <= 1.6; i += 0.8) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.85, 0.05, 8, 24), wireMat)
      ring.position.x = i
      ring.rotation.y = Math.PI / 2
      motorWireGroup.add(ring)
    }

    // Floating Data Particles
    const particleCount = 150
    const particleGeo = new THREE.BufferGeometry()
    const positions = new Float32Array(particleCount * 3)

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 16
      positions[i * 3 + 1] = (Math.random() - 0.5) * 10
      positions[i * 3 + 2] = (Math.random() - 0.5) * 10
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const particleMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.08,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
    })
    const particles = new THREE.Points(particleGeo, particleMat)
    scene.add(particles)

    // Mouse Parallax
    let targetX = 0
    let targetY = 0
    const onMouseMove = (e: MouseEvent) => {
      targetX = (e.clientX / window.innerWidth - 0.5) * 0.8
      targetY = (e.clientY / window.innerHeight - 0.5) * 0.8
    }
    window.addEventListener('mousemove', onMouseMove)

    // Resize
    const onResize = () => {
      if (!container) return
      const w = container.clientWidth
      const h = container.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    // Animation Loop
    let animId: number
    const clock = new THREE.Clock()

    const animate = () => {
      const delta = clock.getDelta()
      const time = clock.getElapsedTime()

      motorWireGroup.rotation.y += delta * 0.25
      motorWireGroup.rotation.x = Math.sin(time * 0.4) * 0.15
      rotorShaft.rotation.x += delta * 2.0

      particles.rotation.y += delta * 0.08

      // Camera parallax interpolation
      camera.position.x += (targetX * 2 - camera.position.x) * 0.05
      camera.position.y += ((2 - targetY * 1.5) - camera.position.y) * 0.05
      camera.lookAt(0, 0, 0)

      renderer.render(scene, camera)
      animId = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
    }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
    </div>
  )
}
