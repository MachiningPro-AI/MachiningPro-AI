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
import { AlertTriangle, X, ChevronDown, Check } from 'lucide-react'
import { useLocale } from '../i18n'
import { useAuth } from '../hooks/useAuth'
import WorkspaceViewport from '../components/workspace/WorkspaceViewport'
import WorkspaceModelTree from '../components/workspace/WorkspaceModelTree'
import WorkspacePropertiesPanel from '../components/workspace/WorkspacePropertiesPanel'
import WorkspaceRibbon from '../components/workspace/WorkspaceRibbon'
import WorkspaceCamPanel from '../components/workspace/WorkspaceCamPanel'
import WorkspaceStatusBar from '../components/workspace/WorkspaceStatusBar'
import WorkspaceViewerToolbar from '../components/workspace/WorkspaceViewerToolbar'
import {
  detectFormat,
  DEFAULT_SIMULATION_STATE,
  DEFAULT_LAYOUT,
  DEFAULT_BG_PRESET,
  BACKGROUND_PRESETS,
  LAYOUT_PRESETS,
  MIN_PANEL_WIDTH,
  MAX_PANEL_WIDTH,
  MIN_BOTTOM_HEIGHT,
  MAX_BOTTOM_HEIGHT,
  loadWorkspaceLayout,
  saveWorkspaceLayout,
} from '../components/workspace/WorkspaceTypes'
import type {
  BackgroundPreset,
  BgPresetId,
  DisplayMode,
  LayoutPresetId,
  PartOpacityPreset,
  ViewPreset,
  WorkspaceFile,
  WorkspaceLayout,
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
  // Layout — MUST 4, 6, 7, 9
  layout: WorkspaceLayout
  onTogglePanel: (panel: keyof Pick<WorkspaceLayout, 'showModelTree' | 'showProperties' | 'showCamPanel' | 'showStatusBar'>) => void
  onLayoutPreset: (preset: LayoutPresetId) => void
  onSaveLayout: () => void
  onRestoreLayout: () => void
  onResetLayout: () => void
  onViewerMaximize: () => void
}

function MenuBar({
  onOpenFile, onConnectWorkflow, onCloseFile, hasFile,
  layout, onTogglePanel, onLayoutPreset,
  onSaveLayout, onRestoreLayout, onResetLayout, onViewerMaximize,
}: MenuBarProps) {
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

  const layoutPresets: LayoutPresetId[] = ['MODEL', 'DRAWING', 'MANUFACTURING', 'CAM', 'SIMULATION', 'INSPECTION']

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
              <DropdownItem label={t('ws_openFile')}     onClick={() => { setOpenMenu(null); onOpenFile() }} />
              <DropdownItem label={t('ws_loadWorkflow')} onClick={() => { setOpenMenu(null); onConnectWorkflow() }} />
              <div className="h-px bg-tp-border my-1" />
              <DropdownItem label={t('ws_closeFile')}    onClick={() => { setOpenMenu(null); onCloseFile() }} disabled={!hasFile} />
            </div>
          )}

          {/* VIEW menu — MUST 4, 6, 7, 9 */}
          {openMenu === 'view' && menu.id === 'view' && (
            <div className="absolute left-0 top-8 z-50 w-56 rounded border border-tp-border
                            bg-tp-surface shadow-lg shadow-black/40 py-1">
              {/* Panels — MUST 4 */}
              <div className="px-3 py-1 text-[9px] font-semibold uppercase tracking-widest text-tp-text-3">
                Panels
              </div>
              {([
                { key: 'showModelTree' as const,  label: 'Model Tree' },
                { key: 'showProperties' as const, label: 'Properties' },
                { key: 'showCamPanel' as const,   label: 'CAM Panel' },
                { key: 'showStatusBar' as const,  label: 'Status Bar' },
              ]).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => { onTogglePanel(key); setOpenMenu(null) }}
                  className="w-full text-left px-3 py-1.5 text-[11px] flex items-center gap-2
                             text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text"
                >
                  <Check size={10} className={layout[key] ? 'text-tp-accent-light' : 'opacity-0'} aria-hidden="true" />
                  {label}
                </button>
              ))}
              <div className="h-px bg-tp-border my-1" />
              {/* Layout presets — MUST 6 */}
              <div className="px-3 py-1 text-[9px] font-semibold uppercase tracking-widest text-tp-text-3">
                Layout Presets
              </div>
              {layoutPresets.map(preset => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => { onLayoutPreset(preset); setOpenMenu(null) }}
                  className="w-full text-left px-3 py-1.5 text-[11px] flex items-center gap-2
                             text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text"
                >
                  <Check size={10} className={layout.activePreset === preset ? 'text-tp-accent-light' : 'opacity-0'} aria-hidden="true" />
                  {preset.charAt(0) + preset.slice(1).toLowerCase()}
                </button>
              ))}
              <div className="h-px bg-tp-border my-1" />
              {/* Viewer maximize — MUST 9 */}
              <DropdownItem
                label={layout.viewerMaximized ? 'Restore Workspace' : 'Maximize Viewer'}
                onClick={() => { onViewerMaximize(); setOpenMenu(null) }}
              />
              <div className="h-px bg-tp-border my-1" />
              {/* Layout persistence — MUST 7 */}
              <DropdownItem label="Save Workspace Layout"    onClick={() => { onSaveLayout();    setOpenMenu(null) }} />
              <DropdownItem label="Restore Workspace Layout" onClick={() => { onRestoreLayout(); setOpenMenu(null) }} />
              <DropdownItem label="Reset to Default Layout"  onClick={() => { onResetLayout();   setOpenMenu(null) }} />
            </div>
          )}

          {openMenu === menu.id && menu.id !== 'file' && menu.id !== 'view' && (
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

  // ── Workspace layout state — MUST 2,3,4,6,7,8,9 ─────────────────────────
  // HARD RULE 7: layout is never stored in engineering state
  const [layout, setLayout] = useState<WorkspaceLayout>(() => loadWorkspaceLayout())
  const layoutRef            = useRef<WorkspaceLayout>(layout)
  const savedLayoutRef       = useRef<WorkspaceLayout | null>(null)  // for Restore

  useEffect(() => { layoutRef.current = layout }, [layout])

  const updateLayout = useCallback((patch: Partial<WorkspaceLayout>) => {
    setLayout(l => ({ ...l, ...patch }))
  }, [])

  // Auto-save layout to localStorage (MUST 7) — debounced
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => saveWorkspaceLayout(layoutRef.current), 600)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [layout])

  // Apply a layout preset — MUST 6
  const handleLayoutPreset = useCallback((presetId: LayoutPresetId) => {
    const preset = LAYOUT_PRESETS[presetId]
    updateLayout({ ...preset, activePreset: presetId })
  }, [updateLayout])

  // Save/Restore/Reset — MUST 7
  const handleSaveLayout   = useCallback(() => { savedLayoutRef.current = { ...layoutRef.current }; saveWorkspaceLayout(layoutRef.current) }, [])
  const handleRestoreLayout= useCallback(() => { if (savedLayoutRef.current) setLayout({ ...savedLayoutRef.current }) }, [])
  const handleResetLayout  = useCallback(() => setLayout({ ...DEFAULT_LAYOUT }), [])

  // Panel toggles — MUST 4
  const handleTogglePanel = useCallback((panel: keyof Pick<WorkspaceLayout, 'showModelTree' | 'showProperties' | 'showCamPanel' | 'showStatusBar'>) => {
    updateLayout({ [panel]: !layoutRef.current[panel] })
  }, [updateLayout])

  // Viewer maximize — MUST 9
  const handleViewerMaximize = useCallback(() => {
    updateLayout({ viewerMaximized: !layoutRef.current.viewerMaximized })
  }, [updateLayout])

  // Fullscreen — MUST 10
  const handleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => undefined)
    } else {
      document.exitFullscreen().catch(() => undefined)
    }
  }, [])

  // Panel collapse toggles — MUST 3
  const handleCollapseLeft   = useCallback(() => updateLayout({ collapsedLeft:   !layoutRef.current.collapsedLeft   }), [updateLayout])
  const handleCollapseRight  = useCallback(() => updateLayout({ collapsedRight:  !layoutRef.current.collapsedRight  }), [updateLayout])
  const handleCollapseBottom = useCallback(() => updateLayout({ collapsedBottom: !layoutRef.current.collapsedBottom }), [updateLayout])

  // ── Panel resize drag handles — MUST 2 ───────────────────────────────────
  // HARD RULE 2: resize never touches engineering state
  // HARD RULE 5: viewport never becomes zero-size

  const resizeRef = useRef<{
    type: 'left' | 'right' | 'bottom'
    startX: number; startY: number
    startW: number; startH: number
  } | null>(null)

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      const r = resizeRef.current
      if (!r) return
      if (r.type === 'left') {
        const delta = e.clientX - r.startX
        const newW = Math.max(MIN_PANEL_WIDTH, Math.min(MAX_PANEL_WIDTH, r.startW + delta))
        setLayout(l => ({ ...l, leftWidth: newW }))
      } else if (r.type === 'right') {
        const delta = r.startX - e.clientX
        const newW = Math.max(MIN_PANEL_WIDTH, Math.min(MAX_PANEL_WIDTH, r.startW + delta))
        setLayout(l => ({ ...l, rightWidth: newW }))
      } else {
        const delta = e.clientY - r.startY
        const newH = Math.max(MIN_BOTTOM_HEIGHT, Math.min(MAX_BOTTOM_HEIGHT, r.startH + delta))
        setLayout(l => ({ ...l, bottomHeight: newH }))
      }
    }
    const onMouseUp = () => {
      if (resizeRef.current) {
        resizeRef.current = null
        saveWorkspaceLayout(layoutRef.current)
      }
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup',   onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup',   onMouseUp)
    }
  }, [])

  const startResizeLeft   = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizeRef.current = { type: 'left',  startX: e.clientX, startY: e.clientY, startW: layoutRef.current.leftWidth,   startH: layoutRef.current.bottomHeight }
  }, [])
  const startResizeRight  = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizeRef.current = { type: 'right', startX: e.clientX, startY: e.clientY, startW: layoutRef.current.rightWidth,  startH: layoutRef.current.bottomHeight }
  }, [])
  const startResizeBottom = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizeRef.current = { type: 'bottom', startX: e.clientX, startY: e.clientY, startW: layoutRef.current.leftWidth,  startH: layoutRef.current.bottomHeight }
  }, [])

  // ── Appearance state — MUST 15, 16, 17, 20 ───────────────────────────────
  // These are user preferences only — HARD RULE 7: never in engineering state

  const bgPreset: BackgroundPreset =
    BACKGROUND_PRESETS.find(p => p.id === layout.bgPresetId) ?? DEFAULT_BG_PRESET

  const handleBgPreset = useCallback((id: BgPresetId) => updateLayout({ bgPresetId: id }), [updateLayout])
  const handlePartOpacity = useCallback((v: PartOpacityPreset) => updateLayout({ partOpacity: v }), [updateLayout])

  // ── File state ────────────────────────────────────────────────────────────
  const [wsFile,         setWsFile]         = useState<WorkspaceFile | null>(null)
  const [mesh,           setMesh]           = useState<PreviewMesh | null>(null)
  const [loadingBackend, setLoadingBackend] = useState(false)
  const [backendError,   setBackendError]   = useState<string | null>(null)
  const [vtxCount,       setVtxCount]       = useState(0)
  const [triCount,       setTriCount]       = useState(0)
  // MUST 12: file load status for model tree display
  const [fileLoadStatus, setFileLoadStatus] = useState<
    'IDLE' | 'LOADING' | 'GEOMETRY_READY' | 'GEOMETRY_READY_WITH_WARNINGS' | 'FAILED' | 'UNSUPPORTED'
  >('IDLE')
  // MUST 13: structured error diagnostic
  interface ImportDiagnostic {
    file: string; format: string; stage: string; cause: string; action: string
  }
  const [importDiagnostic, setImportDiagnostic] = useState<ImportDiagnostic | null>(null)
  // IGES-specific import diagnostics for properties panel
  const [igesDiagnostics, setIgesDiagnostics] = useState<import('../services/engineeringImport').ImportResult['iges_diagnostics']>(null)

  // ── Viewport state ────────────────────────────────────────────────────────
  const [displayMode,  setDisplayMode]  = useState<DisplayMode>('shaded_edges')  // MUST 6: professional default
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
    setImportDiagnostic(null)
    setIgesDiagnostics(null)
    setVtxCount(0)
    setTriCount(0)
    setFileLoadStatus('LOADING')

    if (format === 'STEP' || format === 'IGES') {
      setLoadingBackend(true)
      try {
        const result = await detectAndImport(file)
        if (result.iges_diagnostics) setIgesDiagnostics(result.iges_diagnostics)
        if (result.preview_mesh) {
          setMesh(result.preview_mesh)
          setVtxCount(result.preview_mesh.vertex_count)
          setTriCount(result.preview_mesh.triangle_count)
          // GEOMETRY_READY_WITH_WARNINGS when non-geometric entities were skipped
          const hasWarnings = result.iges_diagnostics?.iges_import_status === 'PARTIAL'
          setFileLoadStatus(hasWarnings ? 'GEOMETRY_READY_WITH_WARNINGS' : 'GEOMETRY_READY')
        } else {
          // MUST 13: structured diagnostic from real API data
          const firstError = result.fidelity_events?.find(ev => ev.class === 'LOST' || ev.class === 'UNSUPPORTED')
          const cause = firstError?.description
            ?? result.errors?.[0]
            ?? (result.import_status === 'PARTIAL_SUCCESS'
              ? 'Tessellation produced no geometry. The file may be empty, corrupted, or contain only non-solid entities.'
              : `Import status: ${result.import_status}`)
          const action = format === 'STEP'
            ? 'Ensure the STEP file contains solid or surface bodies. Try saving as AP214 or AP242 from your CAD application.'
            : 'Ensure the IGES file contains surfaces or solid geometry. Resave from the originating CAD tool.'
          setImportDiagnostic({
            file: file.name,
            format: result.format_id ?? format,
            stage: result.preview_mesh === undefined ? 'TESSELLATION_FAILED' : 'NO_GEOMETRY_RETURNED',
            cause,
            action,
          })
          setBackendError(t('ws_geometryError'))
          setFileLoadStatus('FAILED')
        }
      } catch (err) {
        const cause = err instanceof Error ? err.message : 'Network or server error.'
        setImportDiagnostic({
          file: file.name,
          format,
          stage: 'UPLOAD_FAILED',
          cause,
          action: 'Check that the backend service is running and you are authenticated.',
        })
        setBackendError(t('ws_geometryError'))
        setFileLoadStatus('FAILED')
      } finally {
        setLoadingBackend(false)
      }
    } else if (format === 'STL' || format === 'OBJ' || format === '3MF') {
      setFileLoadStatus('GEOMETRY_READY')
    } else {
      setFileLoadStatus('UNSUPPORTED')
    }
  }, [t])

  const handleCloseFile = useCallback(() => {
    setWsFile(null)
    setMesh(null)
    setLoadingBackend(false)
    setBackendError(null)
    setImportDiagnostic(null)
    setIgesDiagnostics(null)
    setFileLoadStatus('IDLE')
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

  // ── Left panel actual width (accounting for collapsed/hidden) ──────────────
  const leftVisible    = layout.showModelTree   && !layout.viewerMaximized
  const rightVisible   = layout.showProperties  && !layout.viewerMaximized
  const bottomVisible  = layout.showCamPanel    && !layout.viewerMaximized
  const statusVisible  = layout.showStatusBar

  return (
    <div className="h-full overflow-hidden flex flex-col bg-tp-surface-3">

      {/* Menu bar */}
      <MenuBar
        onOpenFile={handleOpenFile}
        onConnectWorkflow={() => setShowConnectDialog(true)}
        onCloseFile={handleCloseFile}
        hasFile={hasFile}
        layout={layout}
        onTogglePanel={handleTogglePanel}
        onLayoutPreset={handleLayoutPreset}
        onSaveLayout={handleSaveLayout}
        onRestoreLayout={handleRestoreLayout}
        onResetLayout={handleResetLayout}
        onViewerMaximize={handleViewerMaximize}
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
        layoutPreset={layout.activePreset}
        onLayoutPreset={handleLayoutPreset}
        bgPresetId={layout.bgPresetId}
        onBgPreset={handleBgPreset}
        partOpacity={layout.partOpacity}
        onPartOpacity={handlePartOpacity}
      />

      {/* Inner layout — flex col, flex-1 */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">

        {/* Three-panel row — takes remaining space minus CAM panel */}
        <div className="flex-1 overflow-hidden flex min-h-0">

          {/* Left: Model tree panel */}
          {leftVisible && (
            <>
              <WorkspaceModelTree
                wsFile={wsFile}
                workflow={workflow}
                selectedId={selectedId}
                onSelect={setSelectedId}
                vtxCount={vtxCount}
                triCount={triCount}
                fileLoadStatus={fileLoadStatus}
                collapsed={layout.collapsedLeft}
                onCollapse={handleCollapseLeft}
                style={!layout.collapsedLeft ? { width: layout.leftWidth, minWidth: layout.leftWidth } : undefined}
              />
              {/* Left resize handle — MUST 2: only when expanded */}
              {!layout.collapsedLeft && (
                <div
                  className="w-1 shrink-0 cursor-col-resize hover:bg-tp-accent/40
                             active:bg-tp-accent/60 transition-colors bg-tp-border/20"
                  onMouseDown={startResizeLeft}
                  aria-hidden="true"
                  title="Drag to resize Model Tree"
                />
              )}
            </>
          )}

          {/* Center: 3D viewport */}
          <div className="flex-1 overflow-hidden relative min-w-0">
            {/* MUST 13: Structured error diagnostic panel */}
            {importDiagnostic ? (
              <div className="absolute top-2 left-2 right-2 z-10 max-w-lg mx-auto
                              bg-tp-surface border border-tp-error/60 rounded shadow-lg shadow-black/40
                              text-[11px]">
                <div className="flex items-center gap-2 px-3 py-2 bg-tp-error/10 border-b border-tp-error/30">
                  <AlertTriangle size={12} className="text-tp-error shrink-0" aria-hidden="true" />
                  <span className="font-semibold text-tp-error uppercase tracking-wider text-[10px]">
                    Geometry Import Failed
                  </span>
                  <button
                    type="button"
                    className="ml-auto text-tp-text-3 hover:text-tp-text"
                    onClick={() => { setImportDiagnostic(null); setBackendError(null) }}
                    aria-label="Dismiss"
                  >
                    <X size={12} />
                  </button>
                </div>
                <div className="px-3 py-2 grid grid-cols-[80px_1fr] gap-x-2 gap-y-1">
                  <span className="text-tp-text-3 font-mono">File</span>
                  <span className="text-tp-text truncate">{importDiagnostic.file}</span>
                  <span className="text-tp-text-3 font-mono">Format</span>
                  <span className="text-tp-text font-mono">{importDiagnostic.format}</span>
                  <span className="text-tp-text-3 font-mono">Stage</span>
                  <span className="text-tp-text font-mono text-tp-error">{importDiagnostic.stage}</span>
                  <span className="text-tp-text-3 font-mono">Cause</span>
                  <span className="text-tp-text leading-relaxed">{importDiagnostic.cause}</span>
                  <span className="text-tp-text-3 font-mono">Action</span>
                  <span className="text-tp-text leading-relaxed">{importDiagnostic.action}</span>
                </div>
              </div>
            ) : backendError ? (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10
                              bg-tp-error/15 border border-tp-error text-tp-error
                              text-[11px] px-3 py-1.5 rounded flex items-center gap-2">
                <AlertTriangle size={12} aria-hidden="true" />
                {backendError}
              </div>
            ) : null}

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
              bgPreset={bgPreset}
              partOpacity={layout.partOpacity}
            />

            {/* Viewer toolbar overlay — MUST 14 */}
            <WorkspaceViewerToolbar
              hasFile={hasFile}
              displayMode={displayMode}
              showGrid={showGrid}
              showWcs={showWcs}
              showStock={showStock}
              showToolpath={showToolpath}
              hasStock={hasStock}
              hasToolpaths={hasToolpaths}
              viewerMaximized={layout.viewerMaximized}
              onViewPreset={setViewPreset}
              onFitAll={() => setViewPreset('iso')}
              onDisplayMode={setDisplayMode}
              onToggleGrid={() => setShowGrid(v => !v)}
              onToggleWcs={() => setShowWcs(v => !v)}
              onToggleStock={() => setShowStock(v => !v)}
              onToggleToolpath={() => setShowToolpath(v => !v)}
              onMaximize={handleViewerMaximize}
              onFullscreen={handleFullscreen}
            />

            {/* Viewer maximize restore overlay — MUST 9 */}
            {layout.viewerMaximized && (
              <button
                type="button"
                onClick={handleViewerMaximize}
                className="absolute top-2 right-14 z-20 flex items-center gap-1 px-2 py-1
                           rounded border border-tp-border bg-tp-surface/80 text-[10px]
                           text-tp-text-2 hover:bg-tp-surface hover:text-tp-text"
                title="Restore workspace panels"
              >
                <ChevronDown size={10} aria-hidden="true" />
                Restore
              </button>
            )}
          </div>

          {/* Right resize handle — MUST 2 */}
          {rightVisible && !layout.collapsedRight && (
            <div
              className="w-1 shrink-0 cursor-col-resize hover:bg-tp-accent/40
                         active:bg-tp-accent/60 transition-colors bg-tp-border/20"
              onMouseDown={startResizeRight}
              aria-hidden="true"
              title="Drag to resize Properties"
            />
          )}

          {/* Right: Properties panel */}
          {rightVisible && (
            <WorkspacePropertiesPanel
              wsFile={wsFile}
              mesh={mesh}
              workflow={workflow}
              selectedId={selectedId}
              igesDiagnostics={igesDiagnostics}
              collapsed={layout.collapsedRight}
              onCollapse={handleCollapseRight}
              style={!layout.collapsedRight ? { width: layout.rightWidth, minWidth: layout.rightWidth } : undefined}
            />
          )}
        </div>

        {/* Bottom resize handle — MUST 2 */}
        {bottomVisible && !layout.collapsedBottom && (
          <div
            className="h-1 shrink-0 cursor-row-resize hover:bg-tp-accent/40
                       active:bg-tp-accent/60 transition-colors bg-tp-border/20"
            onMouseDown={startResizeBottom}
            aria-hidden="true"
            title="Drag to resize CAM panel"
          />
        )}

        {/* CAM operations panel */}
        {bottomVisible && (
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
            panelHeight={layout.bottomHeight}
            collapsed={layout.collapsedBottom}
            onCollapse={handleCollapseBottom}
          />
        )}
      </div>

      {/* Status bar */}
      {statusVisible && (
        <WorkspaceStatusBar
          wsFile={wsFile}
          cursorPos={cursorPos}
          units={units}
          onToggleUnits={() => setUnits(u => u === 'mm' ? 'inch' : 'mm')}
          operationCount={opCount}
          toolpathCount={tpSegCount}
        />
      )}

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
