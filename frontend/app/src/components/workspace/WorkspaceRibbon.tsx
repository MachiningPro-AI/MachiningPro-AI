/**
 * WorkspaceRibbon — Professional CAD/CAM command toolbar.
 *
 * Groups: FILE | CAD | DISPLAY | OVERLAYS | CAM | INSPECT
 * Inspired by NX/CATIA/Mastercam ribbon layout.
 *
 * Safety:
 *   No dispatch controls
 *   No machine write controls
 *   No auto-approval controls
 */

import {
  FolderOpen, Maximize2, LayoutGrid, Box, Eye, Grid3x3,
  Ruler, Scissors, Layers, GitBranch, AlertTriangle,
  Play, Pause, Square, ChevronRight,
} from 'lucide-react'
import { useLocale } from '../../i18n'
import { ANIM_SPEEDS } from './WorkspaceTypes'
import type { AnimSpeed, DisplayMode, ViewPreset } from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// RibbonButton
// ---------------------------------------------------------------------------

interface RibbonBtnProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  active?: boolean
  disabled?: boolean
  title?: string
}

function RibbonBtn({ icon, label, onClick, active, disabled, title }: RibbonBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title ?? label}
      className={`flex flex-col items-center gap-0.5 px-2 py-1 rounded text-[10px]
                  transition-colors min-w-[40px]
                  ${active
                    ? 'bg-tp-accent/15 text-tp-accent-light border border-tp-accent/30'
                    : 'text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text border border-transparent'
                  }
                  ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
    >
      <span className="text-current">{icon}</span>
      <span className="leading-none whitespace-nowrap">{label}</span>
    </button>
  )
}

// Compact inline button (no label, just icon)
function IconBtn({ icon, onClick, active, disabled, title }: Omit<RibbonBtnProps, 'label'>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`w-7 h-7 flex items-center justify-center rounded transition-colors
                  ${active
                    ? 'bg-tp-accent/15 text-tp-accent-light border border-tp-accent/30'
                    : 'text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text border border-transparent'
                  }
                  ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
    >
      {icon}
    </button>
  )
}

// Ribbon group: children + labeled bottom bar
function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col shrink-0 h-[52px]">
      <div className="flex-1 flex items-center gap-0.5 px-1">
        {children}
      </div>
      <div className="text-[8px] text-tp-text-3 text-center uppercase tracking-wider
                      border-t border-tp-border/40 pb-0.5 px-1 leading-tight">
        {label}
      </div>
    </div>
  )
}

function Sep() {
  return <div className="w-px h-10 bg-tp-border/60 mx-0.5 shrink-0" />
}

// ---------------------------------------------------------------------------
// WorkspaceRibbon
// ---------------------------------------------------------------------------

export interface RibbonProps {
  hasFile:        boolean
  hasToolpaths:   boolean
  hasStock:       boolean
  displayMode:    DisplayMode
  showGrid:       boolean
  showWcs:        boolean
  showStock:      boolean
  showToolpath:   boolean
  animPlaying:    boolean
  animFrames:     number
  animSpeed:      AnimSpeed
  onOpenFile:     () => void
  onFitAll:       () => void
  onViewPreset:   (preset: ViewPreset) => void
  onDisplayMode:  (mode: DisplayMode) => void
  onToggleGrid:   () => void
  onToggleWcs:    () => void
  onToggleStock:  () => void
  onToggleToolpath: () => void
  onConnectWorkflow: () => void
  onAnimPlay:     () => void
  onAnimPause:    () => void
  onAnimStop:     () => void
  onAnimSpeed:    (s: AnimSpeed) => void
}

export default function WorkspaceRibbon({
  hasFile, hasToolpaths, hasStock,
  displayMode, showGrid, showWcs, showStock, showToolpath,
  animPlaying, animFrames, animSpeed,
  onOpenFile, onFitAll, onViewPreset, onDisplayMode,
  onToggleGrid, onToggleWcs, onToggleStock, onToggleToolpath,
  onConnectWorkflow,
  onAnimPlay, onAnimPause, onAnimStop, onAnimSpeed,
}: RibbonProps) {
  const { t } = useLocale()

  return (
    <div className="shrink-0 h-[52px] flex items-stretch gap-0 px-1
                    bg-tp-surface-2 border-b border-tp-border overflow-x-auto
                    [scrollbar-width:none]">

      {/* FILE */}
      <Group label="File">
        <RibbonBtn
          icon={<FolderOpen size={15} />}
          label={t('ws_ribbonOpen')}
          onClick={onOpenFile}
        />
        <RibbonBtn
          icon={<GitBranch size={15} />}
          label="Workflow"
          onClick={onConnectWorkflow}
        />
      </Group>

      <Sep />

      {/* CAD — view presets */}
      <Group label="View">
        <RibbonBtn
          icon={<Maximize2 size={15} />}
          label={t('ws_ribbonFit')}
          onClick={onFitAll}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<span className="text-[11px] font-mono font-bold">T</span>}
          label={t('ws_ribbonTop')}
          onClick={() => onViewPreset('top')}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<span className="text-[11px] font-mono font-bold">F</span>}
          label={t('ws_ribbonFront')}
          onClick={() => onViewPreset('front')}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<span className="text-[11px] font-mono font-bold">R</span>}
          label={t('ws_ribbonRight')}
          onClick={() => onViewPreset('right')}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<ChevronRight size={15} className="-rotate-45" />}
          label={t('ws_ribbonIso')}
          onClick={() => onViewPreset('iso')}
          disabled={!hasFile}
        />
      </Group>

      <Sep />

      {/* DISPLAY */}
      <Group label="Display">
        <RibbonBtn
          icon={<Box size={15} />}
          label={t('ws_ribbonShaded')}
          onClick={() => onDisplayMode('shaded')}
          active={displayMode === 'shaded'}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<LayoutGrid size={15} />}
          label={t('ws_ribbonEdges')}
          onClick={() => onDisplayMode('shaded_edges')}
          active={displayMode === 'shaded_edges'}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<Layers size={15} />}
          label={t('ws_ribbonWireframe')}
          onClick={() => onDisplayMode('wireframe')}
          active={displayMode === 'wireframe'}
          disabled={!hasFile}
        />
      </Group>

      <Sep />

      {/* OVERLAYS */}
      <Group label="Overlays">
        <RibbonBtn
          icon={<Grid3x3 size={15} />}
          label={t('ws_ribbonGrid')}
          onClick={onToggleGrid}
          active={showGrid}
        />
        <RibbonBtn
          icon={<span className="text-[10px] font-mono font-bold leading-none">WCS</span>}
          label="WCS"
          onClick={onToggleWcs}
          active={showWcs}
        />
        <RibbonBtn
          icon={<span className="text-[10px] font-mono font-bold leading-none">STK</span>}
          label="Stock"
          onClick={onToggleStock}
          active={showStock && hasStock}
          disabled={!hasStock}
        />
        <RibbonBtn
          icon={<Eye size={15} />}
          label="Path"
          onClick={onToggleToolpath}
          active={showToolpath && hasToolpaths}
          disabled={!hasToolpaths}
        />
      </Group>

      <Sep />

      {/* CAM — animation */}
      <Group label="Animate">
        <div className="flex items-center gap-0.5">
          <IconBtn
            icon={<Square size={12} />}
            onClick={onAnimStop}
            title="Stop"
            disabled={animFrames === 0}
          />
          {animPlaying
            ? <IconBtn icon={<Pause size={12} />} onClick={onAnimPause} title="Pause" active disabled={animFrames === 0} />
            : <IconBtn icon={<Play  size={12} />} onClick={onAnimPlay}  title="Play"  disabled={animFrames === 0} />
          }
          <select
            value={animSpeed}
            onChange={e => onAnimSpeed(Number(e.target.value) as AnimSpeed)}
            disabled={animFrames === 0}
            className="text-[9px] rounded border border-tp-border bg-tp-surface-3 px-0.5 py-px
                       text-tp-text focus:outline-none ml-0.5 disabled:opacity-30"
            title="Animation speed"
          >
            {ANIM_SPEEDS.map(s => <option key={s} value={s}>{s}×</option>)}
          </select>
        </div>
      </Group>

      <Sep />

      {/* INSPECT (pending) */}
      <Group label="Inspect">
        <RibbonBtn
          icon={<Ruler size={15} />}
          label={t('ws_ribbonMeasure')}
          onClick={() => {/* pending */}}
          disabled
        />
        <RibbonBtn
          icon={<Scissors size={15} />}
          label={t('ws_ribbonSection')}
          onClick={() => {/* pending */}}
          disabled
        />
      </Group>

      {/* Spacer + safety badge */}
      <div className="flex-1" />
      <div className="shrink-0 flex items-center gap-1 mr-1 self-center">
        <AlertTriangle size={10} className="text-tp-text-3" aria-hidden="true" />
        <span className="text-[9px] font-mono text-tp-text-3 whitespace-nowrap">
          {t('ws_noDispatch')} · {t('ws_noMachineWrite')}
        </span>
      </div>
    </div>
  )
}
