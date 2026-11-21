/**
 * WorkspaceViewport — Professional Three.js 3D viewport for the CAD/CAM workspace.
 *
 * Safety contract:
 *   NO_FABRICATED_GEOMETRY=YES   — only renders real loaded mesh or PreviewMesh from backend
 *   NO_FABRICATED_TOOLPATHS=YES  — only renders toolpath lines from real API data
 *   NO_SIMULATION_RESULTS=YES    — no simulated stock removal, no fake collision markers
 *   DISPLAY_MODES=REAL_MESH_ONLY — shaded/wireframe/edges applied to real mesh only
 *
 * Supported:
 *   - File formats: STL (ASCII + binary), OBJ, 3MF (client-side)
 *   - Mesh payload: PreviewMesh from backend tessellation (STEP, IGES)
 *   - Toolpath overlay: THREE.LineSegments from real VisualizationData
 *   - Display modes: shaded, wireframe, shaded+edges, points
 *   - Grid plane, axis triad, view presets, fit all
 *   - Cursor 3D position (raycasting against grid plane)
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { LoaderCircle, Maximize2, RotateCcw } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { PreviewMesh } from '../../services/engineeringImport'
import type { BackgroundPreset, DisplayMode, ToolPose, StockBbox, ToolpathLineGroup, ViewPreset, WorkspaceFile } from './WorkspaceTypes'
import { CLIENT_RENDER_FORMATS, DEFAULT_BG_PRESET, SERVER_RENDER_FORMATS } from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// Scene constants (defaults — overridable via bgPreset prop)
// ---------------------------------------------------------------------------

const BG        = 0x0d1117
const MESH_COL  = 0x7a8fa8
const SPEC_COL  = 0x223344
const EDGE_COL  = 0x1a2a3a
const GRID_COL1 = 0x1e2a38
const GRID_COL2 = 0x2a3a4a

// Motion type colors
const MOTION_COLORS: Record<string, number> = {
  RAPID:   0xffb300,
  FEED:    0x00e5ff,
  PLUNGE:  0xff5722,
  RETRACT: 0xff9800,
  LINK:    0x607d8b,
  DEFAULT: 0x90a4ae,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fitToBox(
  box: THREE.Box3,
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
): void {
  const center = new THREE.Vector3()
  const size   = new THREE.Vector3()
  box.getCenter(center)
  box.getSize(size)
  const maxDim = Math.max(size.x, size.y, size.z)
  if (maxDim <= 0) return
  const fovRad = (camera.fov * Math.PI) / 180
  const dist   = (maxDim / 2 / Math.tan(fovRad / 2)) * 1.6
  camera.position.set(center.x + dist * 0.25, center.y + dist * 0.5, center.z + dist)
  camera.lookAt(center)
  // Update near/far so the entire model is inside the frustum regardless of offset from origin
  camera.near = Math.max(dist * 0.001, 0.001)
  camera.far  = dist * 100
  camera.updateProjectionMatrix()
  controls.target.copy(center)
  controls.update()
}

function applyViewPreset(
  preset: ViewPreset,
  box: THREE.Box3 | null,
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
): void {
  const center = box ? (() => { const v = new THREE.Vector3(); box.getCenter(v); return v })() : new THREE.Vector3()
  const size   = box ? (() => { const v = new THREE.Vector3(); box.getSize(v); return v })() : new THREE.Vector3(1, 1, 1)
  const dist   = Math.max(size.x, size.y, size.z) * 1.6

  const positions: Record<ViewPreset, THREE.Vector3> = {
    iso:    new THREE.Vector3(center.x + dist * 0.6, center.y + dist * 0.6, center.z + dist * 0.6),
    top:    new THREE.Vector3(center.x, center.y + dist, center.z),
    front:  new THREE.Vector3(center.x, center.y, center.z + dist),
    right:  new THREE.Vector3(center.x + dist, center.y, center.z),
    left:   new THREE.Vector3(center.x - dist, center.y, center.z),
    back:   new THREE.Vector3(center.x, center.y, center.z - dist),
    bottom: new THREE.Vector3(center.x, center.y - dist, center.z),
  }

  const ups: Partial<Record<ViewPreset, THREE.Vector3>> = {
    top:    new THREE.Vector3(0, 0, -1),
    bottom: new THREE.Vector3(0, 0, 1),
  }

  camera.position.copy(positions[preset])
  camera.up.copy(ups[preset] ?? new THREE.Vector3(0, 1, 0))
  camera.lookAt(center)
  controls.target.copy(center)
  controls.update()
}

function buildMeshMaterial(mode: DisplayMode): THREE.Material {
  if (mode === 'wireframe') {
    return new THREE.MeshBasicMaterial({ color: MESH_COL, wireframe: true })
  }
  if (mode === 'points') {
    return new THREE.PointsMaterial({ color: MESH_COL, size: 0.5 })
  }
  if (mode === 'hidden_line') {
    return new THREE.MeshBasicMaterial({ color: 0x1a2a3a, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 })
  }
  // shaded or shaded_edges
  return new THREE.MeshPhongMaterial({
    color:    MESH_COL,
    specular: SPEC_COL,
    shininess: 40,
    side: THREE.DoubleSide,
  })
}

function buildEdgeMaterial(): THREE.LineBasicMaterial {
  return new THREE.LineBasicMaterial({ color: EDGE_COL })
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ViewportProps {
  wsFile:       WorkspaceFile | null
  mesh:         PreviewMesh | null
  displayMode:  DisplayMode
  showGrid:     boolean
  showWcs:      boolean
  showToolpath: boolean
  showStock:    boolean
  toolpaths:    ToolpathLineGroup[]
  toolPose:     ToolPose | null
  stockBbox:    StockBbox | null
  collisionPoints: Array<[number, number, number]>
  gougePoints:     Array<[number, number, number]>
  viewPreset:   ViewPreset | null
  onViewPresetConsumed: () => void
  onFit:        (() => void) | null
  onCursorPos:  (pos: [number, number, number] | null) => void
  onMeshLoaded: (vtxCount: number, triCount: number) => void
  loadingBackend: boolean
  // Appearance — MUST 15, 17, 18, 20 — never alter engineering data
  bgPreset?:    BackgroundPreset
  partOpacity?: number
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function WorkspaceViewport({
  wsFile,
  mesh,
  displayMode,
  showGrid,
  showWcs,
  showToolpath,
  showStock,
  toolpaths,
  toolPose,
  stockBbox,
  collisionPoints,
  gougePoints,
  viewPreset,
  onViewPresetConsumed,
  onFit,
  onCursorPos,
  onMeshLoaded,
  loadingBackend,
  bgPreset,
  partOpacity,
}: ViewportProps) {
  const { t } = useLocale()
  const containerRef   = useRef<HTMLDivElement>(null)
  const cameraRef      = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef    = useRef<OrbitControls | null>(null)
  const fitBoxRef      = useRef<THREE.Box3 | null>(null)
  const initPosRef     = useRef(new THREE.Vector3())
  const initTgtRef     = useRef(new THREE.Vector3())
  const meshGroupRef      = useRef<THREE.Group | null>(null)
  const edgeGroupRef      = useRef<THREE.Group | null>(null)
  const tpGroupRef        = useRef<THREE.Group | null>(null)
  const gridRef           = useRef<THREE.GridHelper | null>(null)
  const wcsRef            = useRef<THREE.Group | null>(null)
  const toolMarkerRef     = useRef<THREE.Mesh | null>(null)
  const stockBoxRef       = useRef<THREE.Group | null>(null)
  const collisionGroupRef = useRef<THREE.Points | null>(null)
  const gougeGroupRef     = useRef<THREE.Points | null>(null)
  const sceneRef          = useRef<THREE.Scene | null>(null)
  const rendererRef       = useRef<THREE.WebGLRenderer | null>(null)
  const axisCanvasRef     = useRef<HTMLCanvasElement | null>(null)
  const disposeListRef    = useRef<Array<THREE.BufferGeometry | THREE.Material>>([])

  const [loading,    setLoading]    = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [meshLoaded, setMeshLoaded] = useState(false)

  // Track current display mode & show flags without re-mounting the entire scene
  const displayModeRef  = useRef(displayMode)
  const showGridRef     = useRef(showGrid)
  const showWcsRef      = useRef(showWcs)
  const showToolpathRef = useRef(showToolpath)
  const showStockRef    = useRef(showStock)
  // Track appearance props for use in render loop — MUST 15, 18
  const bgPresetRef     = useRef<BackgroundPreset>(bgPreset ?? DEFAULT_BG_PRESET)

  // ── Scene setup ──────────────────────────────────────────────────────────

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Scene
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(BG)
    sceneRef.current = scene

    // Camera
    const w = container.clientWidth  || 800
    const h = container.clientHeight || 600
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.0001, 1e6)
    camera.position.set(100, 80, 150)
    cameraRef.current = camera

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(w, h)
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const key = new THREE.DirectionalLight(0xffffff, 0.85)
    key.position.set(1.5, 2, 2.5)
    scene.add(key)
    const fill = new THREE.DirectionalLight(0x8899bb, 0.3)
    fill.position.set(-2, -1, -1)
    scene.add(fill)

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.06
    controlsRef.current = controls

    // Grid
    const grid = new THREE.GridHelper(2000, 100, GRID_COL1, GRID_COL2)
    grid.visible = showGridRef.current
    scene.add(grid)
    gridRef.current = grid

    // WCS marker (X=red, Y=green, Z=blue)
    const wcsGroup = new THREE.Group()
    const axisLen = 30
    const axes: Array<[number, number, number, number]> = [
      [axisLen, 0, 0, 0xff2222],
      [0, axisLen, 0, 0x22ff22],
      [0, 0, axisLen, 0x2222ff],
    ]
    for (const [x, y, z, col] of axes) {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(x, y, z),
      ])
      const mat = new THREE.LineBasicMaterial({ color: col })
      wcsGroup.add(new THREE.Line(geo, mat))
      disposeListRef.current.push(geo, mat)
    }
    wcsGroup.visible = showWcsRef.current
    scene.add(wcsGroup)
    wcsRef.current = wcsGroup

    // Toolpath group (populated by toolpath effect)
    const tpGroup = new THREE.Group()
    tpGroup.visible = showToolpathRef.current
    scene.add(tpGroup)
    tpGroupRef.current = tpGroup

    // Mesh group (populated by file/mesh effect)
    const meshGroup = new THREE.Group()
    scene.add(meshGroup)
    meshGroupRef.current = meshGroup

    const edgeGroup = new THREE.Group()
    scene.add(edgeGroup)
    edgeGroupRef.current = edgeGroup

    // Tool pose marker — small yellow sphere, hidden until pose set
    const toolGeo = new THREE.SphereGeometry(0.5, 10, 10)
    const toolMat = new THREE.MeshBasicMaterial({ color: 0xffff00, transparent: true, opacity: 0.85 })
    const toolMarker = new THREE.Mesh(toolGeo, toolMat)
    toolMarker.visible = false
    scene.add(toolMarker)
    toolMarkerRef.current = toolMarker
    disposeListRef.current.push(toolGeo, toolMat)

    // Stock bounding box group — transparent surface + wireframe edges
    const stockBoxGroup = new THREE.Group()
    stockBoxGroup.visible = false
    scene.add(stockBoxGroup)
    stockBoxRef.current = stockBoxGroup

    // Collision / gouge point clouds (empty initially)
    const colGeo  = new THREE.BufferGeometry()
    const colMat  = new THREE.PointsMaterial({ color: 0xff1744, size: 2.5, sizeAttenuation: false })
    const colPts  = new THREE.Points(colGeo, colMat)
    colPts.visible = false
    scene.add(colPts)
    collisionGroupRef.current = colPts
    disposeListRef.current.push(colGeo, colMat)

    const gougeGeo = new THREE.BufferGeometry()
    const gougeMat = new THREE.PointsMaterial({ color: 0xff6d00, size: 2.5, sizeAttenuation: false })
    const gougePts = new THREE.Points(gougeGeo, gougeMat)
    gougePts.visible = false
    scene.add(gougePts)
    gougeGroupRef.current = gougePts
    disposeListRef.current.push(gougeGeo, gougeMat)

    // Ground raycasting plane for cursor position
    const groundGeo  = new THREE.PlaneGeometry(1e6, 1e6)
    const groundMat  = new THREE.MeshBasicMaterial({ visible: false, side: THREE.DoubleSide })
    const groundMesh = new THREE.Mesh(groundGeo, groundMat)
    groundMesh.rotation.x = -Math.PI / 2
    groundMesh.name = 'ground'
    scene.add(groundMesh)
    disposeListRef.current.push(groundGeo, groundMat)

    // Raycaster for cursor
    const raycaster = new THREE.Raycaster()
    const mouse     = new THREE.Vector2()
    const onMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      mouse.x =  ((e.clientX - rect.left)  / rect.width)  * 2 - 1
      mouse.y = -((e.clientY - rect.top)   / rect.height) * 2 + 1
      raycaster.setFromCamera(mouse, camera)
      const hits = raycaster.intersectObject(groundMesh)
      if (hits.length > 0) {
        const p = hits[0].point
        onCursorPos([p.x, p.y, p.z])
      }
    }
    container.addEventListener('mousemove', onMouseMove)
    const onMouseLeave = () => onCursorPos(null)
    container.addEventListener('mouseleave', onMouseLeave)

    // Render loop
    let animId = 0
    const axCtx = axisCanvasRef.current?.getContext('2d')

    const loop = () => {
      animId = requestAnimationFrame(loop)
      controls.update()
      renderer.render(scene, camera)

      // Update axis triad mini-canvas — MUST 18: contrast adapts to bgPreset
      if (axCtx && axisCanvasRef.current) {
        const sz = axisCanvasRef.current.width
        axCtx.clearRect(0, 0, sz, sz)
        axCtx.fillStyle = bgPresetRef.current.axisCanvasBg
        axCtx.fillRect(0, 0, sz, sz)

        const origin = new THREE.Vector3(0, 0, 0)
        const axes3: Array<[THREE.Vector3, string, string]> = [
          [new THREE.Vector3(1, 0, 0), '#ff4444', 'X'],
          [new THREE.Vector3(0, 1, 0), '#44ff44', 'Y'],
          [new THREE.Vector3(0, 0, 1), '#4488ff', 'Z'],
        ]
        const half = sz / 2
        const radius = half * 0.72

        // Project using camera matrices
        const mvp = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
        const project = (v: THREE.Vector3) => {
          const c = v.clone().applyMatrix4(mvp)
          return { x: half + c.x * half, y: half - c.y * half }
        }
        const o2d = project(origin)

        for (const [axis, color, label] of axes3) {
          const tip = project(axis)
          const dx  = tip.x - o2d.x
          const dy  = tip.y - o2d.y
          const len = Math.sqrt(dx * dx + dy * dy)
          const nx  = len > 0 ? dx / len : 0
          const ny  = len > 0 ? dy / len : 0
          const ex  = half + nx * radius
          const ey  = half + ny * radius

          axCtx.beginPath()
          axCtx.moveTo(half, half)
          axCtx.lineTo(ex, ey)
          axCtx.strokeStyle = color
          axCtx.lineWidth = 2
          axCtx.stroke()

          axCtx.font = `bold ${Math.round(sz * 0.18)}px monospace`
          axCtx.fillStyle = color
          axCtx.fillText(label, ex + nx * 4, ey + ny * 4)
        }
      }
    }
    loop()

    // ResizeObserver
    const ro = new ResizeObserver(() => {
      const nw = container.clientWidth
      const nh = container.clientHeight
      if (nw === 0 || nh === 0) return
      camera.aspect = nw / nh
      camera.updateProjectionMatrix()
      renderer.setSize(nw, nh)
    })
    ro.observe(container)

    return () => {
      cancelAnimationFrame(animId)
      ro.disconnect()
      container.removeEventListener('mousemove', onMouseMove)
      container.removeEventListener('mouseleave', onMouseLeave)
      controls.dispose()
      for (const d of disposeListRef.current) d.dispose()
      disposeListRef.current = []
      renderer.dispose()
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement)
      cameraRef.current = controlsRef.current = sceneRef.current = rendererRef.current = null
      meshGroupRef.current = edgeGroupRef.current = tpGroupRef.current = null
      gridRef.current = wcsRef.current = null
      toolMarkerRef.current = stockBoxRef.current = null
      collisionGroupRef.current = gougeGroupRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // scene mounts once

  // ── Load mesh from file ──────────────────────────────────────────────────

  useEffect(() => {
    const meshGroup = meshGroupRef.current
    const edgeGroup = edgeGroupRef.current
    if (!meshGroup || !edgeGroup) return

    // Clear previous mesh
    meshGroup.clear()
    edgeGroup.clear()
    setMeshLoaded(false)
    setParseError(null)

    if (!wsFile && !mesh) return
    if (wsFile && !mesh && SERVER_RENDER_FORMATS.includes(wsFile.format)) return  // mesh not yet arrived; wait for it

    setLoading(true)
    let alive = true

    const addMeshToScene = (geo: THREE.BufferGeometry) => {
      if (!alive) return
      geo.computeVertexNormals()
      disposeListRef.current.push(geo)

      const mat = buildMeshMaterial(displayModeRef.current)
      disposeListRef.current.push(mat)
      const obj = displayModeRef.current === 'points'
        ? new THREE.Points(geo, mat as THREE.PointsMaterial)
        : new THREE.Mesh(geo, mat as THREE.Material)
      meshGroup.add(obj)

      if (displayModeRef.current === 'shaded_edges') {
        const edgeGeo = new THREE.EdgesGeometry(geo, 25)
        const edgeMat = buildEdgeMaterial()
        disposeListRef.current.push(edgeGeo, edgeMat)
        const edges = new THREE.LineSegments(edgeGeo, edgeMat)
        edgeGroup.add(edges)
      }

      const box = new THREE.Box3().setFromObject(meshGroup)
      fitBoxRef.current = box
      fitToBox(box, cameraRef.current!, controlsRef.current!)
      initPosRef.current.copy(cameraRef.current!.position)
      initTgtRef.current.copy(controlsRef.current!.target)

      const vtx = geo.attributes['position']?.count ?? 0
      const tri = vtx > 0 ? Math.floor(vtx / 3) : 0
      onMeshLoaded(vtx, tri)
      setMeshLoaded(true)
      setLoading(false)
    }

    if (mesh) {
      // Backend PreviewMesh
      try {
        const geo = new THREE.BufferGeometry()
        geo.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3))
        geo.setIndex(mesh.indices)
        addMeshToScene(geo)
      } catch {
        if (!alive) return
        setParseError(t('ws_geometryError'))
        setLoading(false)
      }
      return () => { alive = false }
    }

    if (!wsFile || !CLIENT_RENDER_FORMATS.includes(wsFile.format)) {
      setLoading(false)
      return () => { alive = false }
    }

    const objectUrl = URL.createObjectURL(wsFile.file)
    const ext = wsFile.format.toLowerCase()

    void (async () => {
      try {
        if (ext === 'stl') {
          const geo = await new STLLoader().loadAsync(objectUrl)
          addMeshToScene(geo)
        } else if (ext === 'obj') {
          const group = (await new OBJLoader().loadAsync(objectUrl)) as THREE.Group
          group.traverse(child => {
            if (child instanceof THREE.Mesh) {
              const geo = child.geometry as THREE.BufferGeometry
              addMeshToScene(geo)
            }
          })
        } else {
          // 3MF
          const group = (await new ThreeMFLoader().loadAsync(objectUrl)) as THREE.Group
          group.traverse(child => {
            if (child instanceof THREE.Mesh) {
              const geo = child.geometry as THREE.BufferGeometry
              addMeshToScene(geo)
            }
          })
        }
      } catch {
        if (!alive) return
        setParseError(t('ws_geometryError'))
        setLoading(false)
      } finally {
        URL.revokeObjectURL(objectUrl)
      }
    })()

    return () => { alive = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsFile, mesh])

  // ── Display mode changes ─────────────────────────────────────────────────

  useEffect(() => {
    displayModeRef.current = displayMode
    const meshGroup = meshGroupRef.current
    const edgeGroup = edgeGroupRef.current
    if (!meshGroup || !edgeGroup || meshGroup.children.length === 0) return

    meshGroup.children.forEach(obj => {
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Points) {
        obj.material = buildMeshMaterial(displayMode)
        disposeListRef.current.push(obj.material as THREE.Material)
      }
    })
    edgeGroup.clear()
    if (displayMode === 'shaded_edges') {
      meshGroup.children.forEach(obj => {
        if (obj instanceof THREE.Mesh) {
          const edgeGeo = new THREE.EdgesGeometry(obj.geometry, 25)
          const edgeMat = buildEdgeMaterial()
          disposeListRef.current.push(edgeGeo, edgeMat)
          edgeGroup.add(new THREE.LineSegments(edgeGeo, edgeMat))
        }
      })
    }
  }, [displayMode])

  // ── Grid visibility ──────────────────────────────────────────────────────

  useEffect(() => {
    showGridRef.current = showGrid
    if (gridRef.current) gridRef.current.visible = showGrid
  }, [showGrid])

  // ── WCS visibility ───────────────────────────────────────────────────────

  useEffect(() => {
    showWcsRef.current = showWcs
    if (wcsRef.current) wcsRef.current.visible = showWcs
  }, [showWcs])

  // ── Toolpath lines ───────────────────────────────────────────────────────

  useEffect(() => {
    const tpGroup = tpGroupRef.current
    if (!tpGroup) return

    // Clear old lines
    while (tpGroup.children.length > 0) {
      const child = tpGroup.children[0]
      if (child instanceof THREE.LineSegments) {
        child.geometry.dispose()
        ;(child.material as THREE.Material).dispose()
      }
      tpGroup.remove(child)
    }

    // No fabricated toolpaths — only render if real data exists
    for (const group of toolpaths) {
      if (group.points.length < 6) continue  // need at least 2 points
      const pts = group.points
      // Convert from polyline to line segments: 0→1, 1→2, 2→3, ...
      const segPts: number[] = []
      for (let i = 0; i + 3 < pts.length; i += 3) {
        segPts.push(pts[i], pts[i+1], pts[i+2])
        segPts.push(pts[i+3], pts[i+4], pts[i+5])
      }
      const geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.Float32BufferAttribute(segPts, 3))
      const color = MOTION_COLORS[group.motionType] ?? MOTION_COLORS['DEFAULT']!
      const mat = new THREE.LineBasicMaterial({ color })
      tpGroup.add(new THREE.LineSegments(geo, mat))
    }
    tpGroup.visible = showToolpathRef.current
  }, [toolpaths])

  // ── Toolpath visibility ──────────────────────────────────────────────────

  useEffect(() => {
    showToolpathRef.current = showToolpath
    if (tpGroupRef.current) tpGroupRef.current.visible = showToolpath
  }, [showToolpath])

  // ── Tool pose (animation marker) ────────────────────────────────────────

  useEffect(() => {
    const marker = toolMarkerRef.current
    if (!marker) return
    if (toolPose) {
      marker.position.set(toolPose.x, toolPose.y, toolPose.z)
      marker.visible = true
    } else {
      marker.visible = false
    }
  }, [toolPose])

  // ── Stock bounding box ───────────────────────────────────────────────────

  useEffect(() => {
    const group = stockBoxRef.current
    if (!group) return

    // Clear previous stock meshes
    while (group.children.length > 0) {
      const child = group.children[0]!
      if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments) {
        (child as THREE.Mesh).geometry.dispose()
        const mat = (child as THREE.Mesh).material as THREE.Material
        mat.dispose()
      }
      group.remove(child)
    }

    if (!stockBbox) {
      group.visible = false
      return
    }

    const { minX, minY, minZ, maxX, maxY, maxZ } = stockBbox
    const w = maxX - minX, h = maxY - minY, d = maxZ - minZ
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2

    const boxGeo = new THREE.BoxGeometry(w, h, d)
    const boxMat = new THREE.MeshBasicMaterial({
      color: stockBbox.confirmed ? 0x1a4fa0 : 0x2a7a4a,
      transparent: true,
      opacity: 0.08,
      side: THREE.DoubleSide,
    })
    const boxMesh = new THREE.Mesh(boxGeo, boxMat)
    boxMesh.position.set(cx, cy, cz)
    group.add(boxMesh)

    const edgeGeo = new THREE.EdgesGeometry(boxGeo)
    const edgeMat = new THREE.LineBasicMaterial({
      color: stockBbox.confirmed ? 0x4488ff : 0x44cc88,
      transparent: true, opacity: 0.6,
    })
    const edgeMesh = new THREE.LineSegments(edgeGeo, edgeMat)
    edgeMesh.position.set(cx, cy, cz)
    group.add(edgeMesh)
    disposeListRef.current.push(boxGeo, boxMat, edgeGeo, edgeMat)

    group.visible = showStockRef.current
  }, [stockBbox])

  // ── Stock visibility ──────────────────────────────────────────────────────

  useEffect(() => {
    showStockRef.current = showStock
    if (stockBoxRef.current) {
      stockBoxRef.current.visible = showStock && !!stockBbox
    }
  }, [showStock, stockBbox])

  // ── Collision / gouge point markers ──────────────────────────────────────

  useEffect(() => {
    const pts = collisionGroupRef.current
    if (!pts) return
    if (collisionPoints.length === 0) {
      pts.visible = false
      return
    }
    const flat = collisionPoints.flat()
    pts.geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3))
    pts.visible = true
  }, [collisionPoints])

  useEffect(() => {
    const pts = gougeGroupRef.current
    if (!pts) return
    if (gougePoints.length === 0) {
      pts.visible = false
      return
    }
    const flat = gougePoints.flat()
    pts.geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3))
    pts.visible = true
  }, [gougePoints])

  // ── View preset ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!viewPreset) return
    if (!cameraRef.current || !controlsRef.current) return
    applyViewPreset(viewPreset, fitBoxRef.current, cameraRef.current, controlsRef.current)
    onViewPresetConsumed()
  }, [viewPreset, onViewPresetConsumed])

  // ── Background preset — MUST 15, 18 ─────────────────────────────────────

  useEffect(() => {
    const preset = bgPreset ?? DEFAULT_BG_PRESET
    bgPresetRef.current = preset

    const scene = sceneRef.current
    if (!scene) return

    // Update scene background — MUST 15
    scene.background = new THREE.Color(preset.color)

    // Recreate grid with contrasting colors — MUST 18
    const oldGrid = gridRef.current
    if (oldGrid) {
      scene.remove(oldGrid)
      if (Array.isArray(oldGrid.material)) oldGrid.material.forEach(m => m.dispose())
      else (oldGrid.material as THREE.Material).dispose()
      oldGrid.geometry.dispose()
    }
    const newGrid = new THREE.GridHelper(2000, 100, preset.gridColor1, preset.gridColor2)
    newGrid.visible = showGridRef.current
    scene.add(newGrid)
    gridRef.current = newGrid
  }, [bgPreset])

  // ── Part opacity — MUST 20 ───────────────────────────────────────────────

  useEffect(() => {
    if (!meshGroupRef.current) return
    const opacity = partOpacity ?? 1
    meshGroupRef.current.traverse(obj => {
      if (obj instanceof THREE.Mesh) {
        const mat = obj.material as THREE.Material | THREE.Material[]
        const mats = Array.isArray(mat) ? mat : [mat]
        for (const m of mats) {
          m.transparent = opacity < 1
          ;(m as THREE.MeshPhongMaterial).opacity = opacity
          m.needsUpdate = true
        }
      }
    })
  }, [partOpacity])

  // ── Fit all callback ─────────────────────────────────────────────────────

  const handleFit = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current || !fitBoxRef.current) return
    fitToBox(fitBoxRef.current, cameraRef.current, controlsRef.current)
  }, [])

  const handleReset = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return
    cameraRef.current.position.copy(initPosRef.current)
    controlsRef.current.target.copy(initTgtRef.current)
    controlsRef.current.update()
  }, [])

  useEffect(() => {
    if (onFit) {
      // expose fit handler via parent setter
    }
  }, [onFit, handleFit])

  const isLoading   = loading || loadingBackend
  const showEmpty   = !wsFile && !mesh && !isLoading
  const showError   = !!parseError

  const bgCss = bgPreset
    ? `#${bgPreset.color.toString(16).padStart(6, '0')}`
    : '#0d1117'

  return (
    <div className="relative w-full h-full overflow-hidden" style={{ backgroundColor: bgCss }}>
      {/* Three.js canvas container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Axis triad mini canvas — bottom left */}
      <canvas
        ref={axisCanvasRef}
        width={80}
        height={80}
        className="absolute bottom-10 left-2 pointer-events-none opacity-80"
        aria-hidden="true"
      />

      {/* Loading overlay */}
      {isLoading && !showError && (
        <div className="absolute inset-0 flex items-center justify-center bg-tp-surface/70">
          <LoaderCircle size={22} className="animate-spin text-tp-accent-light" aria-hidden="true" />
          <span className="ml-2 text-sm text-tp-text-2">{t('ws_loadingGeometry')}</span>
        </div>
      )}

      {/* Error overlay */}
      {showError && (
        <div className="absolute inset-0 flex items-center justify-center bg-tp-surface">
          <p className="text-sm text-tp-error">{parseError}</p>
        </div>
      )}

      {/* Empty state */}
      {showEmpty && !showError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 pointer-events-none">
          <div className="text-tp-text-3 text-xs font-mono uppercase tracking-widest">{t('ws_noFileLoaded')}</div>
          <div className="text-tp-text-3 text-[11px]">{t('ws_dropFileHere')}</div>
        </div>
      )}

      {/* Viewport controls — top right */}
      {meshLoaded && !showError && (
        <div className="absolute right-2 top-2 flex gap-1">
          <button
            type="button"
            onClick={handleFit}
            aria-label={t('ws_fitAll')}
            title={t('ws_fitAll')}
            className="rounded border border-tp-border bg-tp-surface/80 p-1.5 text-tp-text-2
                       hover:bg-tp-surface hover:text-tp-text"
          >
            <Maximize2 size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={handleReset}
            aria-label={t('ciViewerReset')}
            title={t('ciViewerReset')}
            className="rounded border border-tp-border bg-tp-surface/80 p-1.5 text-tp-text-2
                       hover:bg-tp-surface hover:text-tp-text"
          >
            <RotateCcw size={13} aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Verification badge — always NOT_PERFORMED */}
      <div className="absolute bottom-1 right-2 text-[9px] font-mono text-tp-text-3 pointer-events-none">
        SIM_REQ=YES · VERIFIED=NO
      </div>
    </div>
  )
}
