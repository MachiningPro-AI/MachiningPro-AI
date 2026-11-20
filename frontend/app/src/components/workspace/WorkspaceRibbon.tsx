/**
 * WorkspaceRibbon — command toolbar for the CAD/CAM workspace.
 *
 * Groups: File Operations | View Presets | Display Mode | Overlays | Analysis
 *
 * Safety:
 *   No dispatch controls
 *   No machine write controls
 *   No auto-approval controls
 */

import {
  FolderOpen, Maximize2, LayoutGrid, Box, Eye, Grid3x3,
  Ruler, Scissors, Layers, GitBranch, AlertTriangle,
} from 'lucide-react'
import { useLocale } from '../../i18n'
import type { DisplayMode, ViewPreset } from './WorkspaceTypes'

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
      className={`flex flex-col items-center gap-0.5 px-2.5 py-1.5 rounded text-[10px]
                  transition-colors min-w-[44px]
                  ${active
                    ? 'bg-tp-accent/15 text-tp-accent-light border border-tp-accent/30'
                    : 'text-tp-text-2 hover:bg-tp-surface-2 hover:text-tp-text border border-transparent'
                  }
                  ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
    >
      <span className="text-current">{icon}</span>
      <span className="leading-none">{label}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// RibbonSeparator
// ---------------------------------------------------------------------------

function Sep() {
  return <div className="w-px h-9 bg-tp-border/60 mx-1 shrink-0" />
}

// ---------------------------------------------------------------------------
// WorkspaceRibbon
// ---------------------------------------------------------------------------

export interface RibbonProps {
  hasFile:        boolean
  displayMode:    DisplayMode
  showGrid:       boolean
  showWcs:        boolean
  showStock:      boolean
  showToolpath:   boolean
  hasToolpaths:   boolean
  onOpenFile:     () => void
  onFitAll:       () => void
  onViewPreset:   (preset: ViewPreset) => void
  onDisplayMode:  (mode: DisplayMode) => void
  onToggleGrid:   () => void
  onToggleWcs:    () => void
  onToggleStock:  () => void
  onToggleToolpath: () => void
  onConnectWorkflow: () => void
}

export default function WorkspaceRibbon({
  hasFile,
  displayMode,
  showGrid,
  showWcs,
  showStock,
  showToolpath,
  hasToolpaths,
  onOpenFile,
  onFitAll,
  onViewPreset,
  onDisplayMode,
  onToggleGrid,
  onToggleWcs,
  onToggleStock,
  onToggleToolpath,
  onConnectWorkflow,
}: RibbonProps) {
  const { t } = useLocale()

  return (
    <div className="shrink-0 h-[52px] flex items-center gap-0 px-2
                    bg-tp-surface border-b border-tp-border overflow-x-auto
                    [scrollbar-width:none]">

      {/* File group */}
      <div className="flex items-center gap-0.5 shrink-0">
        <RibbonBtn
          icon={<FolderOpen size={16} />}
          label={t('ws_ribbonOpen')}
          onClick={onOpenFile}
        />
        <RibbonBtn
          icon={<GitBranch size={16} />}
          label={t('ws_connectWorkflow')}
          onClick={onConnectWorkflow}
        />
      </div>

      <Sep />

      {/* View presets */}
      <div className="flex items-center gap-0.5 shrink-0">
        <RibbonBtn
          icon={<Maximize2 size={16} />}
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
          icon={<span className="text-[11px] font-mono font-bold">I</span>}
          label={t('ws_ribbonIso')}
          onClick={() => onViewPreset('iso')}
          disabled={!hasFile}
        />
      </div>

      <Sep />

      {/* Display modes */}
      <div className="flex items-center gap-0.5 shrink-0">
        <RibbonBtn
          icon={<Box size={16} />}
          label={t('ws_ribbonShaded')}
          onClick={() => onDisplayMode('shaded')}
          active={displayMode === 'shaded'}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<LayoutGrid size={16} />}
          label={t('ws_ribbonEdges')}
          onClick={() => onDisplayMode('shaded_edges')}
          active={displayMode === 'shaded_edges'}
          disabled={!hasFile}
        />
        <RibbonBtn
          icon={<Layers size={16} />}
          label={t('ws_ribbonWireframe')}
          onClick={() => onDisplayMode('wireframe')}
          active={displayMode === 'wireframe'}
          disabled={!hasFile}
        />
      </div>

      <Sep />

      {/* Overlays */}
      <div className="flex items-center gap-0.5 shrink-0">
        <RibbonBtn
          icon={<Grid3x3 size={16} />}
          label={t('ws_ribbonGrid')}
          onClick={onToggleGrid}
          active={showGrid}
        />
        <RibbonBtn
          icon={<span className="text-[11px] font-mono">WCS</span>}
          label={t('ws_showWcs')}
          onClick={onToggleWcs}
          active={showWcs}
        />
        <RibbonBtn
          icon={<span className="text-[11px] font-mono">STK</span>}
          label={t('ws_showStock')}
          onClick={onToggleStock}
          active={showStock}
          disabled
        />
        <RibbonBtn
          icon={<Eye size={16} />}
          label={t('ws_showToolpath')}
          onClick={onToggleToolpath}
          active={showToolpath && hasToolpaths}
          disabled={!hasToolpaths}
        />
      </div>

      <Sep />

      {/* Analysis tools (placeholders — pending implementation) */}
      <div className="flex items-center gap-0.5 shrink-0">
        <RibbonBtn
          icon={<Ruler size={16} />}
          label={t('ws_ribbonMeasure')}
          onClick={() => {/* measure mode pending */}}
          disabled
        />
        <RibbonBtn
          icon={<Scissors size={16} />}
          label={t('ws_ribbonSection')}
          onClick={() => {/* section view pending */}}
          disabled
        />
      </div>

      {/* Spacer + safety badge */}
      <div className="flex-1" />
      <div className="shrink-0 flex items-center gap-1 mr-1">
        <AlertTriangle size={11} className="text-tp-text-3" aria-hidden="true" />
        <span className="text-[9px] font-mono text-tp-text-3">
          {t('ws_noDispatch')} · {t('ws_noMachineWrite')}
        </span>
      </div>
    </div>
  )
}
