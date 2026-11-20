/**
 * CadCamWorkspacePage — Professional CAD/CAM Engineering Workspace.
 *
 * Layout: menu bar → ribbon → 3-panel (model tree | 3D viewport | properties)
 *         → CAM panel → status bar.
 *
 * Safety contract (enforced at all layers):
 *   NO_FABRICATED_GEOMETRY=YES      — 3D viewer only renders real loaded mesh
 *   NO_FABRICATED_TOOLPATHS=YES     — toolpath lines only from real API data
 *   NO_FAKE_SIMULATION=YES          — simulation calls /api/verification/simulate only
 *   NO_MACHINE_WRITE=YES            — no machine dispatch controls
 *   NO_AUTO_APPROVAL=YES            — no auto-approval or auto-confirm
 *   IS_DISPATCHABLE=false           — invariant, never changed
 *   PRODUCTION_RELEASED=false       — invariant, never changed
 *   VIEWER_ENGINEERING_STATE_CHANGED=NO — animation/sim do not alter engineering state
 *   SIMULATION_ENGINEERING_STATE_CHANGED=NO — simulation is offline, offline only
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { ChevronDown, AlertTriangle, X } from 'lucide-react'
import { useLocale } from '../i18n'
import { useAuth } from '../hooks/useAuth'
import WorkspaceViewport from '../components/workspace/WorkspaceViewport'
import WorkspaceModelTree from '../components/workspace/WorkspaceModelTree'
import WorkspacePropertiesPanel from '../components/workspace/WorkspacePropertiesPanel'
import WorkspaceRibbon from '../components/workspace/WorkspaceRibbon'
import WorkspaceCamPanel from '../components/workspace/WorkspaceCamPanel'
import WorkspaceStatusBar from '../components/workspace/WorkspaceStatusBar'
import { detectFormat } from '../components/workspace/WorkspaceTypes'
import { DEFAULT_SIMULATION_STATE } from '../components/workspace/WorkspaceTypes'
import type {
  DisplayMode,
  ViewPreset,
  WorkspaceFile,
  ConnectedWorkflow,
  OperationSummary,
  ToolpathLineGroup,
  ToolPose,
  StockBbox,
  SimulationState,
  AnimSpeed,
} from '../components/workspace/WorkspaceTypes'
import type { PreviewMesh } from '../services/engineeringImport'
import { detectAndImport } from '../services/engineeringImport'
import { getStoredAuth } from '../services/apiClient'
import {
  toolpathGroupsToSegments,
  toolpathGroupsToAnimFrames,
  runSimulation,
  SimulationApiError,
} from '../services/simulationService'
import type { SimulationResultFE } from '../services/simulationService'

// ---------------------------------------------------------------------------
// Menu bar
// ---------------------------------------------------------------------------

interface MenuBarProps {
  onOpenFile: () => void
  onConnectWorkflow: () => void
  onCloseFile: () => void
  hasFile: boolean
}

function MenuBar({ onOpenFile, onConnectWorkflow, onCloseFile, hasFile }: MenuBarProps) {
  const { t } = useLocale()
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  const menus: Array<{ id: string; labelKey: Parameters<typeof t>[0] }> = [
    { id: 'file',     labelKey: 'ws_fileMenu' },
    { id: 'edit',     labelKey: 'ws_editMenu' },
    { id: 'view',     labelKey: 'ws_viewMenu' },
    { id: 'cam',      labelKey: 'ws_camMenu' },
    { id: 'simulate', labelKey: 'ws_simulateMenu' },
    { id: 'help',     labelKey: 'ws_helpMenu' },
  ]

  return (
    <div
      className="shrink-0 h-8 flex items-center px-2 gap-0
                 bg-tp-surface-2 border-b border-tp-border text-[11px]"
      onMouseLeave={() => setOpenMenu(null)}
    >
      <span className="text-[10px] font-semibold text-tp-accent-light mr-3 select-none shrink-0">
        {t('ws_title')}
      </span>

      {menus.map(menu => (
        <div key={menu.id} className="relative shrink-0">
          <button
            type="button"
            onMouseEnter={() => openMenu && setOpenMenu(menu.id)}
            onClick={() => setOpenMenu(openMenu === menu.id ? null : menu.id)}
            className={`h-8 px-2.5 text-[11px] flex items-center gap-0.5 transition-colors
                       ${openMenu === menu.id
                         ? 'bg-tp-accent/15 text-tp-accent-light'
                         : 'text-tp-text-2 hover:bg-tp-surface hover:text-tp-text'
                       }`}
          >
            {t(menu.labelKey)}
          </button>

          {openMenu === 'file' && menu.id === 'file' && (
            <div className="absolute left-0 top-8 z-50 w-52 rounded border border-tp-border
                            bg-tp-surface shadow-lg shadow-black/40 py-1">
              <DropdownItem label={t('ws_openFile')}      onClick={() => { setOpenMenu(null); onOpenFile() }} />
              <DropdownItem label={t('ws_loadWorkflow')}  onClick={() => { setOpenMenu(null); onConnectWorkflow() }} />
              <div className="h-px bg-tp-border my-1" />
              <DropdownItem label={t('ws_closeFile')}     onClick={() => { setOpenMenu(null); onCloseFile() }} disabled={!hasFile} />
            </div>
          )}

          {openMenu === menu.id && menu.id !== 'file' && (
            <div className="absolute left-0 top-8 z-50 w-44 rounded border border-tp-border
                            bg-tp-surface shadow-lg shadow-black/40 p-2">
              <div className="text-[10px] text-tp-text-3 italic">Available via ribbon</div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function DropdownItem({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`w-full text-left px-3 py-1.5 text-[11px] transition-colors
                 ${disabled
                   ? 'text-tp-text-3 opacity-50 cursor-not-allowed'
                   : 'text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text'
                 }`}
    >
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Connect workflow dialog
// ---------------------------------------------------------------------------

function ConnectWorkflowDialog({ onClose, onConnect, loading, error }: {
  onClose:   () => void
  onConnect: (workflowId: string) => void
  loading:   boolean
  error:     string | null
}) {
  const { t } = useLocale()
  const [wfId, setWfId] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-tp-surface border border-tp-border rounded-lg p-5 w-80 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-tp-text">{t('ws_connectWorkflow')}</h3>
          <button type="button" onClick={onClose} className="text-tp-text-3 hover:text-tp-text" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <label className="block text-[11px] text-tp-text-2 mb-1">{t('ws_workflowId')}</label>
        <input
          type="text"
          value={wfId}
          onChange={e => setWfId(e.target.value.trim())}
          placeholder="WF_..."
          className="w-full px-3 py-2 rounded border border-tp-border bg-tp-surface-2
                     text-[12px] text-tp-text placeholder:text-tp-text-3
                     focus:outline-none focus:border-tp-accent"
          onKeyDown={e => e.key === 'Enter' && wfId && onConnect(wfId)}
          autoFocus
        />
        {error && <p className="mt-2 text-[11px] text-tp-error">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose}
            className="px-3 py-1.5 rounded text-[11px] text-tp-text-2 border border-tp-border hover:bg-tp-surface-2">
            Cancel
          </button>
          <button type="button" onClick={() => wfId && onConnect(wfId)}
            disabled={!wfId || loading}
            className="px-3 py-1.5 rounded text-[11px] bg-tp-accent text-white
                       hover:bg-tp-accent/80 disabled:opacity-50 disabled:cursor-not-allowed">
            {loading ? t('ws_loadingWorkflow') : 'Connect'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Parse workflow API response
// ---------------------------------------------------------------------------

function parseWorkflowOperations(data: Record<string, unknown>): OperationSummary[] {
  try {
    const plan = data['manufacturing_plan'] as Record<string, unknown> | null
    if (!plan) return []
    const ops = plan['operations'] as Array<Record<string, unknown>> | undefined
    if (!Array.isArray(ops)) return []
    return ops.map((op, i) => ({
      operationId:    String(op['operation_id'] ?? op['id'] ?? `op-${i}`),
      name:           String(op['name'] ?? op['operation_name'] ?? op['type'] ?? `Operation ${i + 1}`),
      type:           String(op['operation_type'] ?? op['type'] ?? 'UNKNOWN'),
      setupRef:       op['setup_id'] ? String(op['setup_id']) : null,
      toolRef:        op['tool_id'] ? String(op['tool_id']) : null,
      sequenceNumber: Number(op['sequence_number'] ?? i + 1),
      status:         String(op['status'] ?? 'UNKNOWN'),
    }))
  } catch {
    return []
  }
}

function parseWorkflowToolpaths(data: Record<string, unknown>): ToolpathLineGroup[] {
  try {
    const stages = data['stages'] as Array<Record<string, unknown>> | undefined
    if (!Array.isArray(stages)) return []
    const groups: ToolpathLineGroup[] = []
    for (const stage of stages) {
      const result = stage['result'] as Record<string, unknown> | null
      if (!result) continue
      const viz = result['visualization'] as Record<string, unknown> | null
      if (!viz) continue
      const pts = viz['polyline_points'] as Array<[number, number, number]> | null
      if (!Array.isArray(pts) || pts.length === 0) continue
      const motionTypes = viz['motion_types'] as string[] | null
      const flat = pts.flat()
      const motionType = motionTypes?.[0] ?? 'FEED'
      groups.push({
        motionType:   motionType as ToolpathLineGroup['motionType'],
        points:       flat,
        operationRef: String(stage['stage'] ?? 'unknown'),
      })
    }
    return groups
  } catch {
    return []
  }
}

function simResultToState(result: SimulationResultFE): SimulationState {
  const checks: SimulationState['checks'] = {}
  for (const [key, chk] of Object.entries(result.checks)) {
    checks[key] = { status: chk.status, severity: chk.severity, warnings: chk.warnings }
  }
  const viz = result.visualization
  return {
    runStatus:               result.simulation_status === 'COMPLETED' ? 'COMPLETED' : 'FAILED',
    toolpathId:              result.toolpath_id,
    verificationState:       result.verification_state,
    checks,
    initialStockVolumeMm3:   result.initial_stock_volume_mm3,
    remainingStockVolumeMm3: result.remaining_stock_volume_mm3,
    removedVolumeMm3:        result.removed_volume_mm3,
    stockRemovalFidelity:    result.stock_removal_fidelity,
    collisionPoints:         (viz?.collision_points ?? []) as Array<[number, number, number]>,
    gougePoints:             (viz?.gouge_points     ?? []) as Array<[number, number, number]>,
    errorMessage:            null,
  }
}

// ---------------------------------------------------------------------------
// CadCamWorkspacePage
// ---------------------------------------------------------------------------

export default function CadCamWorkspacePage() {
  const { t } = useLocale()
  const { token } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── File state ────────────────────────────────────────────────────────────
  const [wsFile,         setWsFile]         = useState<WorkspaceFile | null>(null)
  const [mesh,           setMesh]           = useState<PreviewMesh | null>(null)
  const [loadingBackend, setLoadingBackend] = useState(false)
  const [backendError,   setBackendError]   = useState<string | null>(null)
  const [vtxCount,       setVtxCount]       = useState(0)
  const [triCount,       setTriCount]       = useState(0)

  // ── Viewport state ────────────────────────────────────────────────────────
  const [displayMode,  setDisplayMode]  = useState<DisplayMode>('shaded')
  const [showGrid,     setShowGrid]     = useState(true)
  const [showWcs,      setShowWcs]      = useState(true)
  const [showStock,    setShowStock]    = useState(true)
  const [showToolpath, setShowToolpath] = useState(true)
  const [viewPreset,   setViewPreset]   = useState<ViewPreset | null>(null)
  const [cursorPos,    setCursorPos]    = useState<[number, number, number] | null>(null)
  const [units,        setUnits]        = useState<'mm' | 'inch'>('mm')
  const [selectedId,   setSelectedId]   = useState<string | null>(null)

  // ── Workflow ─────────────────────────────────────────────────────────────
  const [workflow,          setWorkflow]         = useState<ConnectedWorkflow | null>(null)
  const [showConnectDialog, setShowConnectDialog] = useState(false)
  const [connectLoading,    setConnectLoading]    = useState(false)
  const [connectError,      setConnectError]      = useState<string | null>(null)

  // ── Stock bbox ─────────────────────────────────────────────────────────────
  const [stockBbox, setStockBbox] = useState<StockBbox | null>(null)

  // ── Animation state ────────────────────────────────────────────────────────
  const [animFrames,  setAnimFrames]  = useState<Array<[number, number, number]>>([])
  const [animFrame,   setAnimFrame]   = useState(0)
  const [animPlaying, setAnimPlaying] = useState(false)
  const [animSpeed,   setAnimSpeed]   = useState<AnimSpeed>(1)
  const animIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Simulation state ───────────────────────────────────────────────────────
  const [simState,   setSimState]   = useState<SimulationState>(DEFAULT_SIMULATION_STATE)
  const [simRunning, setSimRunning] = useState(false)

  // ── File open ─────────────────────────────────────────────────────────────

  const handleOpenFile = useCallback(() => fileInputRef.current?.click(), [])

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    const format = detectFormat(file.name)
    const wsf: WorkspaceFile = { file, name: file.name, format, sizeBytes: file.size, loadedAt: new Date() }
    setWsFile(wsf)
    setMesh(null)
    setBackendError(null)
    setVtxCount(0)
    setTriCount(0)

    if (format === 'STEP' || format === 'IGES') {
      setLoadingBackend(true)
      try {
        const result = await detectAndImport(file)
        if (result.preview_mesh) {
          setMesh(result.preview_mesh)
          setVtxCount(result.preview_mesh.vertex_count)
          setTriCount(result.preview_mesh.triangle_count)
        } else {
          setBackendError(t('ws_geometryError'))
        }
      } catch {
        setBackendError(t('ws_geometryError'))
      } finally {
        setLoadingBackend(false)
      }
    }
  }, [t])

  const handleCloseFile = useCallback(() => {
    setWsFile(null)
    setMesh(null)
    setLoadingBackend(false)
    setBackendError(null)
    setVtxCount(0)
    setTriCount(0)
  }, [])

  // ── Workflow connect ──────────────────────────────────────────────────────

  const handleConnectWorkflow = useCallback(async (workflowId: string) => {
    const auth = getStoredAuth()
    const tok = auth.token ?? token
    if (!tok) { setConnectError('Authentication required'); return }

    setConnectLoading(true)
    setConnectError(null)
    try {
      const resp = await fetch(`/api/workflow/${workflowId}`, {
        headers: { Authorization: `Bearer ${tok}` },
      })
      if (!resp.ok) { setConnectError(t('ws_workflowError')); return }

      const data = await resp.json() as Record<string, unknown>
      const ops   = parseWorkflowOperations(data)
      const tps   = parseWorkflowToolpaths(data)
      const meta  = data['workflow'] as Record<string, unknown> | null

      const wf: ConnectedWorkflow = {
        workflowId,
        partName:       meta ? String(meta['part_name'] ?? meta['drawing_number'] ?? workflowId) : workflowId,
        drawingNumber:  meta ? (meta['drawing_number'] as string | null) : null,
        operations:     ops,
        toolpathGroups: tps,
        planStatus:     data['status'] ? String(data['status']) : null,
      }
      setWorkflow(wf)
      setShowConnectDialog(false)

      // Build animation frames from toolpath groups
      const frames = toolpathGroupsToAnimFrames(tps)
      setAnimFrames(frames)
      setAnimFrame(0)
      setAnimPlaying(false)

      // Extract stock bbox from viz data if available
      const stages = data['stages'] as Array<Record<string, unknown>> | undefined
      if (Array.isArray(stages)) {
        for (const stage of stages) {
          const result = stage['result'] as Record<string, unknown> | null
          if (!result) continue
          const viz = result['visualization'] as Record<string, unknown> | null
          const bbox = viz?.['stock_bbox'] as Record<string, number> | null
          if (bbox && typeof bbox['min_x'] === 'number') {
            setStockBbox({
              minX: bbox['min_x'], minY: bbox['min_y'] ?? 0, minZ: bbox['min_z'] ?? 0,
              maxX: bbox['max_x'] ?? 0, maxY: bbox['max_y'] ?? 0, maxZ: bbox['max_z'] ?? 0,
              confirmed: false,  // from API, not USER_CONFIRMED
            })
            break
          }
        }
      }
    } catch {
      setConnectError(t('ws_workflowError'))
    } finally {
      setConnectLoading(false)
    }
  }, [t, token])

  // ── Animation loop ────────────────────────────────────────────────────────

  useEffect(() => {
    if (animIntervalRef.current) {
      clearInterval(animIntervalRef.current)
      animIntervalRef.current = null
    }
    if (!animPlaying || animFrames.length === 0) return

    const fps = 30 * animSpeed
    animIntervalRef.current = setInterval(() => {
      setAnimFrame(f => {
        if (f >= animFrames.length - 1) {
          setAnimPlaying(false)
          return animFrames.length - 1
        }
        return f + 1
      })
    }, 1000 / fps)

    return () => {
      if (animIntervalRef.current) clearInterval(animIntervalRef.current)
    }
  }, [animPlaying, animSpeed, animFrames.length])

  // ── Simulation ────────────────────────────────────────────────────────────

  const handleRunSimulation = useCallback(async () => {
    if (!workflow || workflow.toolpathGroups.length === 0) return
    const auth = getStoredAuth()
    const tok = auth.token ?? token
    if (!tok) return

    setSimRunning(true)
    setSimState(prev => ({ ...prev, runStatus: 'RUNNING', errorMessage: null }))
    try {
      const segments = toolpathGroupsToSegments(workflow.toolpathGroups)
      const req = {
        toolpath_id: workflow.workflowId,
        segments,
        stock: stockBbox ? {
          shape: 'BOX' as const,
          fidelity: (stockBbox.confirmed ? 'USER_CONFIRMED' : 'SUGGESTED') as 'USER_CONFIRMED' | 'SUGGESTED',
          min_x_mm: stockBbox.minX, min_y_mm: stockBbox.minY, min_z_mm: stockBbox.minZ,
          max_x_mm: stockBbox.maxX, max_y_mm: stockBbox.maxY, max_z_mm: stockBbox.maxZ,
        } : undefined,
        part_bbox_min: mesh ? mesh.bounding_box.min : undefined,
        part_bbox_max: mesh ? mesh.bounding_box.max : undefined,
      }
      const result = await runSimulation(req, tok)
      const newState = simResultToState(result)
      setSimState(newState)

      // Update stock bbox from simulation visualization if newly available
      const bbox = result.visualization?.stock_bbox
      if (bbox && typeof bbox['min_x'] === 'number' && !stockBbox) {
        setStockBbox({
          minX: bbox['min_x'], minY: bbox['min_y'] ?? 0, minZ: bbox['min_z'] ?? 0,
          maxX: bbox['max_x'] ?? 0, maxY: bbox['max_y'] ?? 0, maxZ: bbox['max_z'] ?? 0,
          confirmed: false,
        })
      }
    } catch (err) {
      const msg = err instanceof SimulationApiError ? err.message : 'Simulation failed'
      setSimState(prev => ({ ...prev, runStatus: 'FAILED', errorMessage: msg }))
    } finally {
      setSimRunning(false)
    }
  }, [workflow, stockBbox, mesh, token])

  // ── Animation controls ─────────────────────────────────────────────────────

  const handleAnimPlay  = useCallback(() => setAnimPlaying(true),  [])
  const handleAnimPause = useCallback(() => setAnimPlaying(false), [])
  const handleAnimStop  = useCallback(() => { setAnimPlaying(false); setAnimFrame(0) }, [])
  const handleAnimStepFwd  = useCallback(() => setAnimFrame(f => Math.min(f + 1, animFrames.length - 1)), [animFrames.length])
  const handleAnimStepBack = useCallback(() => setAnimFrame(f => Math.max(f - 1, 0)), [])
  const handleAnimSeek  = useCallback((frame: number) => setAnimFrame(frame), [])
  const handleAnimSpeed = useCallback((s: AnimSpeed) => setAnimSpeed(s), [])

  // ── Derived state ─────────────────────────────────────────────────────────

  const hasFile      = !!wsFile || !!mesh
  const hasToolpaths = (workflow?.toolpathGroups.length ?? 0) > 0
  const hasStock     = !!stockBbox
  const toolpaths    = workflow?.toolpathGroups ?? []
  const opCount      = workflow?.operations.length ?? 0
  const tpSegCount   = toolpaths.reduce((s, g) => s + Math.floor(g.points.length / 3), 0)

  const toolPose: ToolPose | null = (animFrames.length > 0 && animFrame < animFrames.length)
    ? { x: animFrames[animFrame]![0], y: animFrames[animFrame]![1], z: animFrames[animFrame]![2] }
    : null

  return (
    <div className="h-full overflow-hidden flex flex-col bg-tp-surface-3">

      {/* Menu bar */}
      <MenuBar
        onOpenFile={handleOpenFile}
        onConnectWorkflow={() => setShowConnectDialog(true)}
        onCloseFile={handleCloseFile}
        hasFile={hasFile}
      />

      {/* Ribbon */}
      <WorkspaceRibbon
        hasFile={hasFile}
        hasToolpaths={hasToolpaths}
        hasStock={hasStock}
        displayMode={displayMode}
        showGrid={showGrid}
        showWcs={showWcs}
        showStock={showStock}
        showToolpath={showToolpath}
        animPlaying={animPlaying}
        animFrames={animFrames.length}
        animSpeed={animSpeed}
        onOpenFile={handleOpenFile}
        onFitAll={() => setViewPreset('iso')}
        onViewPreset={setViewPreset}
        onDisplayMode={setDisplayMode}
        onToggleGrid={() => setShowGrid(v => !v)}
        onToggleWcs={() => setShowWcs(v => !v)}
        onToggleStock={() => setShowStock(v => !v)}
        onToggleToolpath={() => setShowToolpath(v => !v)}
        onConnectWorkflow={() => setShowConnectDialog(true)}
        onAnimPlay={handleAnimPlay}
        onAnimPause={handleAnimPause}
        onAnimStop={handleAnimStop}
        onAnimSpeed={handleAnimSpeed}
      />

      {/* Three-panel area */}
      <div className="flex-1 overflow-hidden flex">

        {/* Left: Model tree */}
        <WorkspaceModelTree
          wsFile={wsFile}
          workflow={workflow}
          selectedId={selectedId}
          onSelect={setSelectedId}
          vtxCount={vtxCount}
          triCount={triCount}
        />

        {/* Center: 3D viewport */}
        <div className="flex-1 overflow-hidden relative">
          {backendError && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10
                            bg-tp-error/15 border border-tp-error text-tp-error
                            text-[11px] px-3 py-1.5 rounded flex items-center gap-2">
              <AlertTriangle size={12} aria-hidden="true" />
              {backendError}
            </div>
          )}
          <WorkspaceViewport
            wsFile={wsFile}
            mesh={mesh}
            displayMode={displayMode}
            showGrid={showGrid}
            showWcs={showWcs}
            showToolpath={showToolpath}
            showStock={showStock}
            toolpaths={toolpaths}
            toolPose={toolPose}
            stockBbox={stockBbox}
            collisionPoints={simState.collisionPoints}
            gougePoints={simState.gougePoints}
            viewPreset={viewPreset}
            onViewPresetConsumed={() => setViewPreset(null)}
            onFit={null}
            onCursorPos={setCursorPos}
            onMeshLoaded={(vtx, tri) => { setVtxCount(vtx); setTriCount(tri) }}
            loadingBackend={loadingBackend}
          />
        </div>

        {/* Right: Properties */}
        <WorkspacePropertiesPanel
          wsFile={wsFile}
          mesh={mesh}
          workflow={workflow}
          selectedId={selectedId}
        />
      </div>

      {/* CAM operations panel */}
      <WorkspaceCamPanel
        workflow={workflow}
        selectedId={selectedId}
        onSelect={setSelectedId}
        animFrames={animFrames.length}
        animFrame={animFrame}
        animPlaying={animPlaying}
        animSpeed={animSpeed}
        simState={simState}
        simRunning={simRunning}
        onPlay={handleAnimPlay}
        onPause={handleAnimPause}
        onStop={handleAnimStop}
        onStepFwd={handleAnimStepFwd}
        onStepBack={handleAnimStepBack}
        onSeek={handleAnimSeek}
        onSpeed={handleAnimSpeed}
        onRunSim={handleRunSimulation}
      />

      {/* Status bar */}
      <WorkspaceStatusBar
        wsFile={wsFile}
        cursorPos={cursorPos}
        units={units}
        onToggleUnits={() => setUnits(u => u === 'mm' ? 'inch' : 'mm')}
        operationCount={opCount}
        toolpathCount={tpSegCount}
      />

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".stl,.obj,.3mf,.step,.stp,.iges,.igs,.dxf,.pdf,.png,.jpg,.jpeg"
        className="hidden"
        aria-hidden="true"
        onChange={handleFileChange}
      />

      {/* Connect workflow dialog */}
      {showConnectDialog && (
        <ConnectWorkflowDialog
          onClose={() => { setShowConnectDialog(false); setConnectError(null) }}
          onConnect={handleConnectWorkflow}
          loading={connectLoading}
          error={connectError}
        />
      )}
    </div>
  )
}
