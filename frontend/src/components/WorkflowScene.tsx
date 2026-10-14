import { useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Html } from '@react-three/drei/web/Html.js'
import { Stars } from '@react-three/drei/core/Stars.js'
import { CatmullRomCurve3, Vector3 } from 'three'
import type { Group } from 'three'
import type { WorkflowNode, WorkflowNodeId } from '../types'

interface WorkflowSceneProps {
  nodes: WorkflowNode[]
  selectedNode: WorkflowNodeId | null
  onSelect: (id: WorkflowNodeId) => void
  reducedMotion: boolean
}

const NODE_POSITIONS: [number, number, number][] = [
  [-2.65, 1.25, 0], [0, 1.95, -0.2], [2.65, 1.25, 0],
  [-2.65, -1.25, 0], [0, -1.95, -0.2], [2.65, -1.25, 0],
]

function ResponsiveCamera() {
  const { camera, size, invalidate } = useThree()

  useEffect(() => {
    const aspect = size.width / Math.max(size.height, 1)
    // Nodes are positioned at x = ±2.65. With labels and screen margins,
    // we require a visible horizontal span at z = 0 of ~8.4 units.
    const targetSpan = 8.4
    const vFovRad = (39 * Math.PI) / 180
    const neededZ = targetSpan / (2 * Math.tan(vFovRad / 2) * Math.max(aspect, 0.45))
    // On wide desktop (aspect > 1.4), position.z stays at default 9.2.
    // On narrow viewports (e.g. 375px), position.z increases to ~11.5–12.5,
    // framing the core and all 6 nodes within the visible canvas without clipping.
    camera.position.z = Math.max(9.2, neededZ)
    camera.updateProjectionMatrix()
    invalidate()
  }, [camera, size.width, size.height, invalidate])

  return null
}

function IntelligenceCore({ reducedMotion }: { reducedMotion: boolean }) {
  const group = useRef<Group>(null)
  useFrame(({ clock }) => {
    if (!reducedMotion && group.current) {
      group.current.rotation.y = clock.elapsedTime * 0.12
      group.current.rotation.x = Math.sin(clock.elapsedTime * 0.16) * 0.08
    }
  })
  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[0.78, 2]} />
        <meshPhysicalMaterial color="#112b4b" emissive="#063b67" emissiveIntensity={0.8} roughness={0.24} metalness={0.72} clearcoat={0.8} />
      </mesh>
      <mesh>
        <icosahedronGeometry args={[0.52, 2]} />
        <meshBasicMaterial color="#42ddff" wireframe transparent opacity={0.58} />
      </mesh>
      <mesh rotation={[0.7, 0.2, 0.35]}>
        <torusGeometry args={[1.12, 0.012, 8, 72]} />
        <meshBasicMaterial color="#8b73ff" transparent opacity={0.75} />
      </mesh>
      <mesh rotation={[-0.45, 0.15, -0.55]}>
        <torusGeometry args={[1.28, 0.008, 8, 72]} />
        <meshBasicMaterial color="#40dfff" transparent opacity={0.48} />
      </mesh>
      <pointLight color="#21cfff" intensity={2.2} distance={5} />
    </group>
  )
}

function WorkflowOrb({ node, position, selected, onSelect, reducedMotion }: {
  node: WorkflowNode
  position: [number, number, number]
  selected: boolean
  onSelect: () => void
  reducedMotion: boolean
}) {
  const ref = useRef<Group>(null)
  useFrame(({ clock }) => {
    if (!reducedMotion && ref.current) ref.current.position.y = position[1] + Math.sin(clock.elapsedTime * 0.65 + position[0]) * 0.045
  })
  const color = node.status === 'running' ? '#41dcff'
    : node.status === 'success' ? '#31d69a'
      : node.status === 'failed' ? '#ff6484'
        : node.status === 'awaiting' ? '#ffbd59' : node.color
  return (
    <group ref={ref} position={position} onClick={(event) => { event.stopPropagation(); onSelect() }} onPointerOver={() => { document.body.style.cursor = 'pointer' }} onPointerOut={() => { document.body.style.cursor = 'auto' }}>
      <mesh>
        <sphereGeometry args={[selected ? 0.25 : 0.2, 18, 18]} />
        <meshStandardMaterial color="#101b32" emissive={color} emissiveIntensity={node.status === 'idle' ? 0.28 : 0.85} metalness={0.66} roughness={0.28} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[selected ? 0.39 : 0.33, 0.012, 8, 48]} />
        <meshBasicMaterial color={color} transparent opacity={selected ? 0.95 : 0.62} />
      </mesh>
      <mesh position={[0, 0, -0.045]}>
        <sphereGeometry args={[0.47, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={selected ? 0.1 : 0.045} depthWrite={false} />
      </mesh>
      <Html position={[0, -0.58, 0]} center distanceFactor={8}>
        <button className={`scene-label ${selected ? 'is-selected' : ''}`} onClick={(event) => { event.stopPropagation(); onSelect() }} aria-label={`${node.label}: ${node.statusLabel}, ${node.value}`}>
          <span className="scene-label-title">{node.label}</span>
          <span className={`scene-label-state scene-label-state--${node.status}`}>{node.value}</span>
        </button>
      </Html>
    </group>
  )
}

function SceneContents({ nodes, selectedNode, onSelect, reducedMotion }: WorkflowSceneProps) {
  const { camera } = useThree()
  const camZ = camera.position.z

  return <>
    <ResponsiveCamera />
    <color attach="background" args={['#070b17']} />
    <fog attach="fog" args={['#070b17', Math.max(10, camZ - 1), Math.max(22, camZ * 2.2)]} />
    <ambientLight intensity={0.48} />
    <pointLight position={[0, 0, 3]} color="#22d3ee" intensity={1.4} distance={8} />
    <pointLight position={[0, 0, -2]} color="#845cff" intensity={1.3} distance={7} />
    <Stars radius={24} depth={20} count={reducedMotion ? 160 : 300} factor={1.15} saturation={0} fade speed={reducedMotion ? 0 : 0.18} />
    <IntelligenceCore reducedMotion={reducedMotion} />
    {nodes.map((node, index) => <WorkflowOrb key={node.id} node={node} position={NODE_POSITIONS[index]} selected={selectedNode === node.id} onSelect={() => onSelect(node.id)} reducedMotion={reducedMotion} />)}
    {nodes.map((node, index) => {
      const next = NODE_POSITIONS[(index + 1) % NODE_POSITIONS.length]
      const here = NODE_POSITIONS[index]
      const points = [new Vector3(...here), new Vector3((here[0] + next[0]) / 2, (here[1] + next[1]) / 2, -0.08), new Vector3(...next)]
      const curve = new CatmullRomCurve3(points)
      return <mesh key={`link-${node.id}`}><tubeGeometry args={[curve, 20, 0.008, 4, false]} /><meshBasicMaterial color="#315273" transparent opacity={0.42} /></mesh>
    })}
  </>
}

export default function WorkflowScene(props: WorkflowSceneProps) {
  const [webglAvailable, setWebglAvailable] = useState(true)
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      setWebglAvailable(Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl')))
    } catch {
      setWebglAvailable(false)
    }
  }, [])

  if (!webglAvailable) return <div className="scene-fallback" role="status">3D rendering is unavailable in this browser. Use the workflow controls below.</div>
  return <Canvas className="workflow-canvas" frameloop={props.reducedMotion ? 'demand' : 'always'} camera={{ position: [0, 0, 9.2], fov: 39 }} dpr={[1, 1.5]} gl={{ antialias: false, alpha: false, powerPreference: 'low-power' }} fallback={<div className="scene-fallback">3D rendering is unavailable. Use the workflow controls below.</div>}>
    <SceneContents {...props} />
  </Canvas>
}
