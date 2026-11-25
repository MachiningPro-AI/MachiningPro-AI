/**
 * WorkspaceCamPanel — bottom panel: CAM operations, toolpath summary,
 * simulation controls + results, and verification display.
 *
 * Safety contract:
 *   SIMULATION_STATE=NOT_PERFORMED until real API result received
 *   NO_FAKE_SIMULATION_PASS=YES     — results come from /api/verification/simulate only
 *   NO_TOOLPATH_FABRICATION=YES     — only shows real toolpath data from API
 *   NO_DISPATCH_CONTROLS=YES        — no machine dispatch UI
 *   VIEWER_ENGINEERING_STATE_CHANGED=NO — animation/sim do not alter engineering state
 */

import { useState } from 'react'
import {
  ChevronDown, ChevronUp, AlertTriangle,
  Play, Pause, Square, SkipBack, SkipForward,
  StepBack, StepForward, Loader2,
  Eye, EyeOff, Trash2, RefreshCw, Plus,
} from 'lucide-react'
import { useLocale } from '../../i18n'
import { SAFETY, ANIM_SPEEDS } from './WorkspaceTypes'
import type {
  ConnectedWorkflow, OperationSummary,
  SimulationState, AnimSpeed,
} from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type CamTab = 'operations' | 'toolpaths' | 'simulation' | 'verification'

const TABS: Array<{ id: CamTab; labelKey: string }> = [
  { id: 'operations',   labelKey: 'ws_camOperations' },
  { id: 'toolpaths',    labelKey: 'ws_camToolpaths' },
  { id: 'simulation',   labelKey: 'ws_camSimulation' },
  { id: 'verification', labelKey: 'ws_verification' },
]

// ---------------------------------------------------------------------------
// Operations tab
// ---------------------------------------------------------------------------

function OperationsTab({
  workflow, selectedId, onSelect, opVisibility, onNewOperation, onToggleOpVisibility, onDeleteOperation,
}: {
  workflow: ConnectedWorkflow | null
  selectedId: string | null
  onSelect: (id: string) => void
  opVisibility: Record<string, boolean>
  onNewOperation: () => void
  onToggleOpVisibility: (id: string) => void
  onDeleteOperation: (id: string) => void
}) {
  const { t } = useLocale()

  if (!workflow || workflow.operations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 px-4">
        <p className="text-[11px] text-tp-text-3 italic">{t('ws_noOperations')}</p>
        <button
          type="button"
          onClick={onNewOperation}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px]
                     bg-tp-accent/10 text-tp-accent-light border border-tp-accent/30
                     hover:bg-tp-accent/20 transition-colors"
        >
          <Plus size={12} />
          {t('ws_newOperationBtn')}
        </button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* toolbar */}
      <div className="shrink-0 flex items-center justify-end px-2 py-1 border-b border-tp-border/40">
        <button
          type="button"
          onClick={onNewOperation}
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px]
                     text-tp-text-2 border border-tp-border hover:bg-tp-surface-2 transition-colors"
        >
          <Plus size={11} />
          {t('ws_newOperationBtn')}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto [scrollbar-width:thin]
                      [scrollbar-color:theme(colors.tp-border)_transparent]">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-tp-surface-2 border-b border-tp-border">
            <tr>
              <th className="text-left px-3 py-1 text-tp-text-3 font-medium w-8">#</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Name</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Type</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">{t('ws_strategyLabel')}</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Tool</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">{t('ws_estCutLength')}</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Status</th>
              <th className="text-left px-2 py-1 text-tp-text-3 font-medium w-20">Actions</th>
            </tr>
          </thead>
          <tbody>
            {workflow.operations.map((op: OperationSummary, i: number) => {
              const visible = opVisibility[op.operationId] !== false
              return (
                <tr
                  key={op.operationId}
                  onClick={() => onSelect(op.operationId)}
                  className={`border-b border-tp-border/40 cursor-pointer
                             ${selectedId === op.operationId
                               ? 'bg-tp-accent/10'
                               : i % 2 === 0 ? 'hover:bg-tp-surface-2' : 'bg-tp-surface/50 hover:bg-tp-surface-2'
                             } ${visible ? '' : 'opacity-50'}`}
                >
                  <td className="px-3 py-1 text-tp-text-3">{op.sequenceNumber}</td>
                  <td className="px-2 py-1 text-tp-text font-medium truncate max-w-[160px]">{op.name}</td>
                  <td className="px-2 py-1 text-tp-text-2 font-mono text-[10px]">{op.type}</td>
                  <td className="px-2 py-1 text-tp-text-3 font-mono text-[10px]">{op.strategy ?? '—'}</td>
                  <td className="px-2 py-1 text-tp-text-3 truncate max-w-[80px]">
                    {op.toolDiameterMm ? `Ø${op.toolDiameterMm}mm` : (op.toolRef ?? '—')}
                  </td>
                  <td className="px-2 py-1 text-tp-text-3 font-mono text-[10px]">
                    {op.estimatedCutLengthMm != null ? `${op.estimatedCutLengthMm.toFixed(0)}mm` : '—'}
                  </td>
                  <td className="px-2 py-1">
                    <span className="text-[9px] font-mono px-1 py-px rounded
                                    bg-tp-surface-3 text-tp-text-3 border border-tp-border">
                      {op.status}
                    </span>
                  </td>
                  <td className="px-2 py-1">
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => onToggleOpVisibility(op.operationId)}
                        title={visible ? t('ws_opVisible') : t('ws_opVisible')}
                        className="w-5 h-5 flex items-center justify-center rounded
                                   text-tp-text-3 hover:text-tp-text hover:bg-tp-surface-3"
                      >
                        {visible ? <Eye size={11} /> : <EyeOff size={11} />}
                      </button>
                      <button
                        type="button"
                        onClick={onNewOperation}
                        title={t('ws_opRegenerateBtn')}
                        className="w-5 h-5 flex items-center justify-center rounded
                                   text-tp-text-3 hover:text-tp-text hover:bg-tp-surface-3"
                      >
                        <RefreshCw size={10} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteOperation(op.operationId)}
                        title={t('ws_opDeleteBtn')}
                        className="w-5 h-5 flex items-center justify-center rounded
                                   text-tp-text-3 hover:text-tp-error hover:bg-tp-error/10"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Toolpaths tab
// ---------------------------------------------------------------------------

function ToolpathsTab({
  workflow, onNewOperation,
}: { workflow: ConnectedWorkflow | null; onNewOperation: () => void }) {
  const { t } = useLocale()

  if (!workflow || workflow.toolpathGroups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 px-4">
        <p className="text-[11px] text-tp-text-3 italic">{t('ws_noToolpaths')}</p>
        <button
          type="button"
          onClick={onNewOperation}
          className="flex items-center gap-1.5 px-4 py-2 rounded text-[11px]
                     bg-tp-accent text-white hover:bg-tp-accent/80 transition-colors"
        >
          <Plus size={12} />
          {t('ws_genToolpath')}
        </button>
      </div>
    )
  }

  const totalPoints = workflow.toolpathGroups.reduce((sum, g) => sum + g.points.length / 3, 0)

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center justify-end px-2 py-1 border-b border-tp-border/40">
        <button
          type="button"
          onClick={onNewOperation}
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px]
                     text-tp-text-2 border border-tp-border hover:bg-tp-surface-2 transition-colors"
        >
          <Plus size={11} />
          {t('ws_newOperationBtn')}
        </button>
      </div>
    <div className="flex-1 overflow-y-auto [scrollbar-width:thin]
                    [scrollbar-color:theme(colors.tp-border)_transparent] p-3">
      <div className="flex gap-4 mb-3">
        <Stat label={t('ws_toolpathCount')} value={totalPoints.toFixed(0)} />
        <Stat label="Groups" value={workflow.toolpathGroups.length} />
        <Stat label={t('ws_simRequired')} value={SAFETY.SIMULATION_REQUIRED ? 'YES' : 'NO'} />
        <Stat label={t('ws_simNotVerified')} value={String(!SAFETY.IS_VERIFIED).toUpperCase()} />
      </div>

      <table className="w-full text-[11px]">
        <thead className="bg-tp-surface-2 border-b border-tp-border">
          <tr>
            <th className="text-left px-3 py-1 text-tp-text-3 font-medium">Motion</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Points</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Operation</th>
          </tr>
        </thead>
        <tbody>
          {workflow.toolpathGroups.map((g, i) => (
            <tr key={i} className="border-b border-tp-border/40 hover:bg-tp-surface-2">
              <td className="px-3 py-1">
                <span className="text-[9px] font-mono px-1 py-px rounded"
                      style={{ background: motionBg(g.motionType) }}>
                  {g.motionType}
                </span>
              </td>
              <td className="px-2 py-1 text-tp-text-2">{(g.points.length / 3).toFixed(0)}</td>
              <td className="px-2 py-1 text-tp-text-3 truncate max-w-[200px]">{g.operationRef}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  )
}

function motionBg(type: string): string {
  const map: Record<string, string> = {
    RAPID:   'rgba(255,179,0,0.18)',
    FEED:    'rgba(0,229,255,0.18)',
    PLUNGE:  'rgba(255,87,34,0.18)',
    RETRACT: 'rgba(255,152,0,0.18)',
    LINK:    'rgba(96,125,139,0.18)',
  }
  return map[type] ?? 'rgba(100,100,100,0.1)'
}

// ---------------------------------------------------------------------------
// Simulation tab (animation controls + real results)
// ---------------------------------------------------------------------------

interface SimulationTabProps {
  workflow:    ConnectedWorkflow | null
  animFrames:  number
  animFrame:   number
  animPlaying: boolean
  animSpeed:   AnimSpeed
  simState:    SimulationState
  simRunning:  boolean
  onPlay:      () => void
  onPause:     () => void
  onStop:      () => void
  onStepFwd:   () => void
  onStepBack:  () => void
  onSeek:      (frame: number) => void
  onSpeed:     (s: AnimSpeed) => void
  onRunSim:    () => void
  // Visibility toggles (MUST 32)
  showTool?:        boolean
  showHolder?:      boolean
  showFixture?:     boolean
  showGouge?:       boolean
  showCollision?:   boolean
  stockOpacity?:    number
  onToggleTool?:    () => void
  onToggleHolder?:  () => void
  onToggleFixture?: () => void
  onToggleGouge?:   () => void
  onToggleCollision?: () => void
  onStockOpacity?:  (v: number) => void
}

function SimulationTab({
  workflow, animFrames, animFrame, animPlaying, animSpeed,
  simState, simRunning,
  onPlay, onPause, onStop, onStepFwd, onStepBack, onSeek, onSpeed, onRunSim,
  showTool = true, showHolder = false, showFixture = false,
  showGouge = true, showCollision = true, stockOpacity = 1,
  onToggleTool, onToggleHolder, onToggleFixture,
  onToggleGouge, onToggleCollision, onStockOpacity,
}: SimulationTabProps) {
  const { t } = useLocale()
  const hasFrames = animFrames > 0
  const pct = hasFrames ? (animFrame / (animFrames - 1)) * 100 : 0

  // MUST 12: gate simulation until toolpaths exist
  const hasToolpaths = (workflow?.toolpathGroups?.length ?? 0) > 0
  if (!hasToolpaths) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 px-6 text-center">
        <AlertTriangle size={20} className="text-tp-text-3" />
        <p className="text-[11px] text-tp-text-3 leading-relaxed">{t('ws_simNeedsToolpath')}</p>
      </div>
    )
  }

  return (
    <div className="p-3 h-full overflow-y-auto space-y-3">
      {/* Safety banner */}
      <div className="flex items-start gap-2 px-2.5 py-2 rounded border border-tp-border bg-tp-surface-3">
        <AlertTriangle size={12} className="text-tp-text-3 mt-0.5 shrink-0" aria-hidden="true" />
        <span className="text-[10px] text-tp-text-3">{t('ws_safetyNote')}</span>
      </div>

      {/* Animation controls */}
      <div className="rounded border border-tp-border bg-tp-surface-2 p-2.5">
        <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
          Toolpath Animation
        </div>

        {/* Transport controls */}
        <div className="flex items-center gap-1 mb-2">
          <CtrlBtn onClick={onStop}      title="Stop"      disabled={!hasFrames}><Square     size={10}/></CtrlBtn>
          <CtrlBtn onClick={() => onSeek(0)} title="Restart"  disabled={!hasFrames}><SkipBack    size={10}/></CtrlBtn>
          <CtrlBtn onClick={onStepBack}  title="Step back" disabled={!hasFrames}><StepBack    size={10}/></CtrlBtn>
          {animPlaying
            ? <CtrlBtn onClick={onPause} title="Pause" disabled={!hasFrames} active><Pause  size={10}/></CtrlBtn>
            : <CtrlBtn onClick={onPlay}  title="Play"  disabled={!hasFrames}><Play          size={10}/></CtrlBtn>
          }
          <CtrlBtn onClick={onStepFwd}   title="Step fwd"  disabled={!hasFrames}><StepForward size={10}/></CtrlBtn>
          <CtrlBtn onClick={() => onSeek(animFrames - 1)} title="End" disabled={!hasFrames}><SkipForward size={10}/></CtrlBtn>

          {/* Speed selector */}
          <div className="ml-auto flex items-center gap-1">
            <span className="text-[9px] text-tp-text-3">Speed:</span>
            <select
              value={animSpeed}
              onChange={e => onSpeed(Number(e.target.value) as AnimSpeed)}
              className="text-[10px] rounded border border-tp-border bg-tp-surface px-1 py-px
                         text-tp-text focus:outline-none"
            >
              {ANIM_SPEEDS.map(s => (
                <option key={s} value={s}>{s}×</option>
              ))}
            </select>
          </div>
        </div>

        {/* Timeline scrubber */}
        <input
          type="range"
          min={0}
          max={Math.max(animFrames - 1, 0)}
          value={animFrame}
          onChange={e => onSeek(Number(e.target.value))}
          disabled={!hasFrames}
          className="w-full h-1.5 accent-tp-accent disabled:opacity-30"
        />
        <div className="flex justify-between text-[9px] text-tp-text-3 mt-1">
          <span>Frame {hasFrames ? animFrame + 1 : 0}/{animFrames}</span>
          <span>{pct.toFixed(0)}%</span>
        </div>
        {!hasFrames && (
          <p className="text-[10px] text-tp-text-3 italic mt-1">
            {!workflow ? 'No workflow connected' : 'No toolpath data'}
          </p>
        )}
      </div>

      {/* Visibility toggles */}
      <div className="rounded border border-tp-border bg-tp-surface-2 p-2.5">
        <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
          Viewport Visibility
        </div>
        <div className="flex flex-wrap gap-1 mb-2">
          {[
            { label: 'Tool', val: showTool, fn: onToggleTool },
            { label: 'Holder', val: showHolder, fn: onToggleHolder },
            { label: 'Fixture', val: showFixture, fn: onToggleFixture },
            { label: 'Gouge pts', val: showGouge, fn: onToggleGouge },
            { label: 'Collision pts', val: showCollision, fn: onToggleCollision },
          ].map(({ label, val, fn }) => (
            <button
              key={label}
              type="button"
              onClick={fn}
              className={`px-2 py-0.5 rounded text-[9px] border transition-colors
                ${val
                  ? 'border-tp-accent/40 bg-tp-accent/10 text-tp-accent-light'
                  : 'border-tp-border text-tp-text-3 hover:bg-tp-surface'
                }`}
            >
              {val ? <Eye size={8} className="inline mr-1" /> : <EyeOff size={8} className="inline mr-1" />}
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-tp-text-3">Stock opacity:</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={stockOpacity}
            onChange={e => onStockOpacity?.(Number(e.target.value))}
            className="flex-1 h-1 accent-tp-accent"
          />
          <span className="text-[9px] font-mono text-tp-text-3 w-8">{Math.round(stockOpacity * 100)}%</span>
        </div>
      </div>

      {/* Run Simulation */}
      <div className="rounded border border-tp-border bg-tp-surface-2 p-2.5">
        <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
          Verification Simulation
        </div>
        <div className="flex items-center gap-2 mb-2">
          <button
            type="button"
            onClick={onRunSim}
            disabled={!workflow || workflow.toolpathGroups.length === 0 || simRunning}
            className="px-3 py-1.5 rounded text-[11px] bg-tp-accent text-white
                       hover:bg-tp-accent/80 disabled:opacity-40 disabled:cursor-not-allowed
                       flex items-center gap-1.5"
          >
            {simRunning && <Loader2 size={11} className="animate-spin" />}
            {simRunning ? 'Running…' : 'Run Simulation'}
          </button>
          <span className="text-[10px] font-mono text-tp-text-3">
            Status: {simState.runStatus}
          </span>
        </div>

        {simState.runStatus !== 'NOT_PERFORMED' && (
          <div className="space-y-1.5">
            {/* Volume report */}
            {simState.initialStockVolumeMm3 !== null && (
              <div className="grid grid-cols-3 gap-2">
                <VolumeCard label="Initial" mm3={simState.initialStockVolumeMm3} />
                <VolumeCard label="Remaining" mm3={simState.remainingStockVolumeMm3} />
                <VolumeCard label="Removed" mm3={simState.removedVolumeMm3} />
              </div>
            )}
            {simState.initialStockVolumeMm3 === null && simState.runStatus === 'COMPLETED' && (
              <p className="text-[10px] text-tp-text-3 italic">
                Stock volume: NOT_VERIFIABLE (no confirmed stock dimensions)
              </p>
            )}
            {/* Fidelity */}
            <p className="text-[9px] text-tp-text-3">
              Stock removal fidelity: {simState.stockRemovalFidelity}
            </p>
            {/* Verification state */}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[9px] text-tp-text-3">Verification state:</span>
              <span className={`text-[9px] font-mono px-1 rounded ${
                simState.verificationState === 'VERIFIED'
                  ? 'bg-green-900/20 text-green-400'
                  : simState.verificationState === 'FAILED'
                    ? 'bg-tp-error/10 text-tp-error'
                    : 'bg-tp-surface-3 text-tp-text-3'
              }`}>
                {simState.verificationState}
              </span>
            </div>
            {/* Collision + gouge point counts */}
            {(simState.collisionPoints.length > 0 || simState.gougePoints.length > 0) && (
              <div className="flex gap-3 mt-1">
                {simState.collisionPoints.length > 0 && (
                  <span className="text-[9px] text-tp-error">
                    Collision pts: {simState.collisionPoints.length}
                  </span>
                )}
                {simState.gougePoints.length > 0 && (
                  <span className="text-[9px] text-tp-warning">
                    Gouge pts: {simState.gougePoints.length}
                  </span>
                )}
              </div>
            )}
            {/* Checks */}
            {Object.keys(simState.checks).length > 0 && (
              <div className="mt-2">
                <p className="text-[9px] text-tp-text-3 mb-1 uppercase tracking-wider">Check Results:</p>
                {Object.entries(simState.checks).map(([key, chk]) => (
                  <CheckRow key={key} name={key} status={chk.status} severity={chk.severity} />
                ))}
              </div>
            )}
            {simState.errorMessage && (
              <p className="text-[10px] text-tp-error">{simState.errorMessage}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CtrlBtn({ children, onClick, title, disabled, active }: {
  children: React.ReactNode
  onClick: () => void
  title: string
  disabled?: boolean
  active?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={`w-6 h-6 rounded border flex items-center justify-center transition-colors
                 ${active
                   ? 'border-tp-accent bg-tp-accent/15 text-tp-accent-light'
                   : 'border-tp-border text-tp-text-2 hover:bg-tp-surface hover:text-tp-text'
                 } disabled:opacity-30 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  )
}

function VolumeCard({ label, mm3 }: { label: string; mm3: number | null }) {
  const val = mm3 !== null ? `${mm3.toFixed(0)} mm³` : 'N/A'
  return (
    <div className="p-1.5 rounded bg-tp-surface-3 border border-tp-border">
      <div className="text-[9px] text-tp-text-3 mb-0.5">{label}</div>
      <div className="text-[10px] font-mono text-tp-text">{val}</div>
    </div>
  )
}

function CheckRow({ name, status, severity }: { name: string; status: string; severity: string }) {
  const color = status === 'PASS' ? 'text-green-400'
    : status === 'FAIL' ? 'text-tp-error'
    : status === 'INSUFFICIENT_DATA' ? 'text-tp-text-3'
    : 'text-tp-text-3'
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className={`text-[9px] font-mono w-16 shrink-0 ${color}`}>{status}</span>
      <span className="text-[9px] text-tp-text-3 truncate">{name}</span>
      {severity !== 'NONE' && severity !== '' && (
        <span className="text-[8px] text-tp-text-3 ml-auto">[{severity}]</span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Verification tab (real check results when available)
// ---------------------------------------------------------------------------

function VerificationTab({ simState }: { simState: SimulationState }) {
  const { t } = useLocale()

  const hasRealResults = simState.runStatus === 'COMPLETED' && Object.keys(simState.checks).length > 0

  const defaultChecks = [
    { label: t('ws_collisionCheck'),  key: 'tool_collision',   value: SAFETY.COLLISION_CHECK  as string },
    { label: t('ws_gougeCheck'),      key: 'part_gouge',       value: SAFETY.GOUGE_CHECK      as string },
    { label: t('ws_fixtureCheck'),    key: 'fixture_collision', value: SAFETY.FIXTURE_CHECK    as string },
    { label: t('ws_machineEnvCheck'), key: 'machine_envelope',  value: SAFETY.MACHINE_ENVELOPE_CHECK as string },
  ]

  return (
    <div className="p-4 h-full overflow-y-auto">
      <div className="text-[11px] text-tp-text-2 mb-3">
        {hasRealResults
          ? `Simulation completed — ${Object.keys(simState.checks).length} checks performed`
          : t('ws_verRequired')}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        {defaultChecks.map(c => {
          const realResult = simState.checks[c.key]
          const displayVal = realResult ? realResult.status : c.value
          return <StatCard key={c.label} label={c.label} value={displayVal} />
        })}
      </div>

      {hasRealResults && (
        <div className="mt-2 space-y-1">
          <p className="text-[9px] text-tp-text-3 uppercase tracking-wider mb-1">All Checks:</p>
          {Object.entries(simState.checks).map(([key, chk]) => (
            <CheckRow key={key} name={key} status={chk.status} severity={chk.severity} />
          ))}
        </div>
      )}

      <div className="mt-3 p-2 rounded bg-tp-surface-3 border border-tp-border/50">
        <p className="text-[10px] text-tp-text-3 leading-relaxed">{t('ws_safetyNote')}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] text-tp-text-3 uppercase tracking-wider">{label}</span>
      <span className="text-[12px] font-mono text-tp-text">{value}</span>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  const isOk = value === 'NOT_PERFORMED' || value === 'TRUE' || value === 'YES' || value === 'PASS'
  const isFail = value === 'FAIL'
  return (
    <div className="p-2 rounded border border-tp-border bg-tp-surface-2">
      <div className="text-[9px] text-tp-text-3 mb-1">{label}</div>
      <div className={`text-[11px] font-mono ${isFail ? 'text-tp-error' : isOk ? 'text-tp-text-3' : 'text-tp-text-2'}`}>
        {value}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WorkspaceCamPanel
// ---------------------------------------------------------------------------

export interface CamPanelProps {
  workflow:    ConnectedWorkflow | null
  selectedId:  string | null
  onSelect:    (id: string) => void
  animFrames:  number
  animFrame:   number
  animPlaying: boolean
  animSpeed:   AnimSpeed
  simState:    SimulationState
  simRunning:  boolean
  onPlay:      () => void
  onPause:     () => void
  onStop:      () => void
  onStepFwd:   () => void
  onStepBack:  () => void
  onSeek:      (frame: number) => void
  onSpeed:     (s: AnimSpeed) => void
  onRunSim:    () => void
  // Operation controls (MUST 7, 8)
  onNewOperation:         () => void
  opVisibility:           Record<string, boolean>
  onToggleOpVisibility:   (id: string) => void
  onDeleteOperation:      (id: string) => void
  // Viewport visibility toggles (MUST 32)
  showTool?:          boolean
  showHolder?:        boolean
  showFixture?:       boolean
  showGouge?:         boolean
  showCollision?:     boolean
  stockOpacity?:      number
  onToggleTool?:      () => void
  onToggleHolder?:    () => void
  onToggleFixture?:   () => void
  onToggleGouge?:     () => void
  onToggleCollision?: () => void
  onStockOpacity?:    (v: number) => void
  // Layout — MUST 3: collapse support
  panelHeight?:  number
  collapsed?:    boolean
  onCollapse?:   () => void
}

export default function WorkspaceCamPanel({
  workflow, selectedId, onSelect,
  animFrames, animFrame, animPlaying, animSpeed,
  simState, simRunning,
  onPlay, onPause, onStop, onStepFwd, onStepBack, onSeek, onSpeed, onRunSim,
  onNewOperation, opVisibility, onToggleOpVisibility, onDeleteOperation,
  showTool, showHolder, showFixture, showGouge, showCollision, stockOpacity,
  onToggleTool, onToggleHolder, onToggleFixture, onToggleGouge, onToggleCollision, onStockOpacity,
  panelHeight,
  collapsed = false,
  onCollapse,
}: CamPanelProps) {
  const { t } = useLocale()
  const [activeTab, setActiveTab] = useState<CamTab>('operations')
  const [expanded,  setExpanded]  = useState(true)

  // Fully collapsed by external layout state — render minimal strip
  if (collapsed) {
    return (
      <div
        className="shrink-0 flex items-center justify-between border-t border-tp-border
                   bg-tp-surface px-2 cursor-pointer hover:bg-tp-surface-2 transition-colors"
        style={{ height: '32px' }}
        role="button"
        aria-label="Expand CAM panel"
        onClick={onCollapse}
      >
        <div className="flex items-center gap-2">
          {TABS.map(tab => (
            <span key={tab.id} className="text-[9px] text-tp-text-3 uppercase">
              {t(tab.labelKey as Parameters<typeof t>[0])}
            </span>
          ))}
        </div>
        <button
          type="button"
          onClick={e => { e.stopPropagation(); onCollapse?.() }}
          aria-label="Expand"
          className="text-tp-text-3 hover:text-tp-text"
        >
          <ChevronUp size={12} />
        </button>
      </div>
    )
  }

  const effectiveHeight = panelHeight ?? 220

  return (
    <div
      className="shrink-0 flex flex-col border-t border-tp-border bg-tp-surface"
      style={{ height: expanded ? `${effectiveHeight}px` : '32px' }}
    >
      {/* Tab bar + collapse toggle */}
      <div className="shrink-0 h-8 flex items-center border-b border-tp-border">
        <div className="flex items-center flex-1 overflow-x-auto [scrollbar-width:none]">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setActiveTab(tab.id); if (!expanded) setExpanded(true) }}
              className={`shrink-0 h-8 px-3 text-[11px] border-b-2 transition-colors
                         ${activeTab === tab.id && expanded
                           ? 'text-tp-accent-light border-tp-accent'
                           : 'text-tp-text-3 border-transparent hover:text-tp-text-2'
                         }`}
            >
              {t(tab.labelKey as Parameters<typeof t>[0])}
            </button>
          ))}
        </div>
        {/* Workflow badge */}
        {workflow && (
          <span className="shrink-0 mr-2 text-[9px] font-mono px-1.5 py-0.5
                           rounded bg-tp-accent/10 text-tp-accent-light border border-tp-accent/20">
            {workflow.partName ?? workflow.workflowId}
          </span>
        )}
        {/* Sim state badge */}
        {simState.runStatus !== 'NOT_PERFORMED' && (
          <span className={`shrink-0 mr-1 text-[9px] font-mono px-1.5 py-0.5 rounded border
                           ${simState.runStatus === 'COMPLETED'
                             ? 'bg-green-900/20 text-green-400 border-green-700/30'
                             : simState.runStatus === 'RUNNING'
                               ? 'bg-tp-accent/10 text-tp-accent-light border-tp-accent/20'
                               : 'bg-tp-error/10 text-tp-error border-tp-error/20'
                           }`}>
            SIM={simState.runStatus}
          </span>
        )}
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="shrink-0 w-8 h-8 flex items-center justify-center
                     text-tp-text-3 hover:text-tp-text-2"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
        </button>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="shrink-0 w-7 h-8 flex items-center justify-center
                       text-tp-text-3 hover:text-tp-text-2"
            aria-label="Hide CAM panel"
            title="Hide panel"
          >
            <ChevronDown size={11} className="opacity-60" />
          </button>
        )}
      </div>

      {/* Tab content */}
      {expanded && (
        <div className="flex-1 overflow-hidden">
          {activeTab === 'operations'   && (
            <OperationsTab
              workflow={workflow}
              selectedId={selectedId}
              onSelect={onSelect}
              opVisibility={opVisibility}
              onNewOperation={onNewOperation}
              onToggleOpVisibility={onToggleOpVisibility}
              onDeleteOperation={onDeleteOperation}
            />
          )}
          {activeTab === 'toolpaths'    && (
            <ToolpathsTab workflow={workflow} onNewOperation={onNewOperation} />
          )}
          {activeTab === 'simulation'   && (
            <SimulationTab
              workflow={workflow}
              animFrames={animFrames}
              animFrame={animFrame}
              animPlaying={animPlaying}
              animSpeed={animSpeed}
              simState={simState}
              simRunning={simRunning}
              onPlay={onPlay}
              onPause={onPause}
              onStop={onStop}
              onStepFwd={onStepFwd}
              onStepBack={onStepBack}
              onSeek={onSeek}
              onSpeed={onSpeed}
              onRunSim={onRunSim}
              showTool={showTool}
              showHolder={showHolder}
              showFixture={showFixture}
              showGouge={showGouge}
              showCollision={showCollision}
              stockOpacity={stockOpacity}
              onToggleTool={onToggleTool}
              onToggleHolder={onToggleHolder}
              onToggleFixture={onToggleFixture}
              onToggleGouge={onToggleGouge}
              onToggleCollision={onToggleCollision}
              onStockOpacity={onStockOpacity}
            />
          )}
          {activeTab === 'verification' && <VerificationTab simState={simState} />}
        </div>
      )}
    </div>
  )
}
