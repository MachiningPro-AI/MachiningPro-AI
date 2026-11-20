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
import type { DisplayMode, ToolpathLineGroup, ViewPreset, WorkspaceFile } from './WorkspaceTypes'
import { CLIENT_RENDER_FORMATS, SERVER_RENDER_FORMATS } from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// Scene constants
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
  const fovRad = (camera.fov * Math.PI) / 180
  const dist   = (maxDim / 2 / Math.tan(fovRad / 2)) * 1.6
  camera.position.set(center.x + dist * 0.25, center.y + dist * 0.5, center.z + dist)
  camera.lookAt(center)
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
  toolpaths:    ToolpathLineGroup[]
  viewPreset:   ViewPreset | null
  onViewPresetConsumed: () => void
  onFit:        (() => void) | null
  onCursorPos:  (pos: [number, number, number] | null) => void
  onMeshLoaded: (vtxCount: number, triCount: number) => void
  loadingBackend: boolean
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
  toolpaths,
  viewPreset,
  onViewPresetConsumed,
  onFit,
  onCursorPos,
  onMeshLoaded,
  loadingBackend,
}: ViewportProps) {
  const { t } = useLocale()
  const containerRef   = useRef<HTMLDivElement>(null)
  const cameraRef      = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef    = useRef<OrbitControls | null>(null)
  const fitBoxRef      = useRef<THREE.Box3 | null>(null)
  const initPosRef     = useRef(new THREE.Vector3())
  const initTgtRef     = useRef(new THREE.Vector3())
  const meshGroupRef   = useRef<THREE.Group | null>(null)
  const edgeGroupRef   = useRef<THREE.Group | null>(null)
  const tpGroupRef     = useRef<THREE.Group | null>(null)
  const gridRef        = useRef<THREE.GridHelper | null>(null)
  const wcsRef         = useRef<THREE.Group | null>(null)
  const sceneRef       = useRef<THREE.Scene | null>(null)
  const rendererRef    = useRef<THREE.WebGLRenderer | null>(null)
  const axisCanvasRef  = useRef<HTMLCanvasElement | null>(null)
  const disposeListRef = useRef<Array<THREE.BufferGeometry | THREE.Material>>([])

  const [loading,    setLoading]    = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [meshLoaded, setMeshLoaded] = useState(false)

  // Track current display mode & show flags without re-mounting the entire scene
  const displayModeRef  = useRef(displayMode)
  const showGridRef     = useRef(showGrid)
  const showWcsRef      = useRef(showWcs)
  const showToolpathRef = useRef(showToolpath)

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

      // Update axis triad mini-canvas
      if (axCtx && axisCanvasRef.current) {
        const sz = axisCanvasRef.current.width
        axCtx.clearRect(0, 0, sz, sz)
        axCtx.fillStyle = 'rgba(13,17,23,0.7)'
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
    if (wsFile && SERVER_RENDER_FORMATS.includes(wsFile.format)) return  // handled by mesh prop

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

  // ── View preset ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (!viewPreset) return
    if (!cameraRef.current || !controlsRef.current) return
    applyViewPreset(viewPreset, fitBoxRef.current, cameraRef.current, controlsRef.current)
    onViewPresetConsumed()
  }, [viewPreset, onViewPresetConsumed])

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

  return (
    <div className="relative w-full h-full overflow-hidden bg-[#0d1117]">
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
