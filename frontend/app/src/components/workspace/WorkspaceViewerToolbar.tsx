/**
 * WorkspaceViewerToolbar — compact floating toolbar overlay inside the 3D viewport.
 *
 * Groups: VIEW | DISPLAY | OVERLAYS | TOOLS
 *
 * Safety: no engineering state changes — only view controls and window controls.
 * HARD RULE 2: toolbar actions never trigger feature confirmation, WCS confirm,
 *              CAM regeneration, simulation, or production release.
 */

import type { DisplayMode, ViewPreset } from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// Toolbar button
// ---------------------------------------------------------------------------

interface VTBtnProps {
  onClick: () => void
  active?: boolean
  disabled?: boolean
  title: string
  children: React.ReactNode
}

function VTBtn({ onClick, active, disabled, title, children }: VTBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`w-6 h-6 flex items-center justify-center rounded text-[10px] font-mono
                  transition-colors select-none
                  ${active
                    ? 'bg-tp-accent/25 text-tp-accent-light border border-tp-accent/50'
                    : 'bg-tp-surface-3/80 text-tp-text-2 border border-tp-border/50 hover:bg-tp-surface-2/90 hover:text-tp-text'
                  }
                  ${disabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      {children}
    </button>
  )
}

function Sep() {
  return <div className="w-px h-5 bg-tp-border/40 mx-0.5 shrink-0" />
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ViewerToolbarProps {
  hasFile:          boolean
  displayMode:      DisplayMode
  showGrid:         boolean
  showWcs:          boolean
  showStock:        boolean
  showToolpath:     boolean
  hasStock:         boolean
  hasToolpaths:     boolean
  viewerMaximized:  boolean
  onViewPreset:     (preset: ViewPreset) => void
  onFitAll:         () => void
  onDisplayMode:    (mode: DisplayMode) => void
  onToggleGrid:     () => void
  onToggleWcs:      () => void
  onToggleStock:    () => void
  onToggleToolpath: () => void
  onMaximize:       () => void
  onFullscreen:     () => void
}

// ---------------------------------------------------------------------------
// WorkspaceViewerToolbar
// ---------------------------------------------------------------------------

export default function WorkspaceViewerToolbar({
  hasFile, displayMode,
  showGrid, showWcs, showStock, showToolpath,
  hasStock, hasToolpaths, viewerMaximized,
  onViewPreset, onFitAll, onDisplayMode,
  onToggleGrid, onToggleWcs, onToggleStock, onToggleToolpath,
  onMaximize, onFullscreen,
}: ViewerToolbarProps) {
  return (
    <div
      className="absolute bottom-12 left-24 z-10 flex items-center gap-0.5
                 rounded border border-tp-border/50 bg-tp-surface-3/85 backdrop-blur-sm
                 px-1 py-0.5 pointer-events-none"
      aria-label="Viewer toolbar"
      role="toolbar"
    >
      <div className="flex items-center gap-0.5 pointer-events-auto">

        {/* VIEW group */}
        <VTBtn onClick={onFitAll}                   disabled={!hasFile} title="Fit All (double-click)">↗</VTBtn>
        <VTBtn onClick={() => onViewPreset('iso')}  disabled={!hasFile} title="Isometric">◫</VTBtn>
        <VTBtn onClick={() => onViewPreset('top')}  disabled={!hasFile} title="Top">T</VTBtn>
        <VTBtn onClick={() => onViewPreset('front')}disabled={!hasFile} title="Front">F</VTBtn>
        <VTBtn onClick={() => onViewPreset('right')}disabled={!hasFile} title="Right">R</VTBtn>

        <Sep />

        {/* DISPLAY group */}
        <VTBtn
          onClick={() => onDisplayMode('shaded')}
          active={displayMode === 'shaded'}
          disabled={!hasFile}
          title="Shaded"
        >◼</VTBtn>
        <VTBtn
          onClick={() => onDisplayMode('shaded_edges')}
          active={displayMode === 'shaded_edges'}
          disabled={!hasFile}
          title="Shaded + Edges"
        >⬛</VTBtn>
        <VTBtn
          onClick={() => onDisplayMode('wireframe')}
          active={displayMode === 'wireframe'}
          disabled={!hasFile}
          title="Wireframe"
        >□</VTBtn>

        <Sep />

        {/* OVERLAYS group */}
        <VTBtn onClick={onToggleGrid} active={showGrid} title="Grid">▦</VTBtn>
        <VTBtn onClick={onToggleWcs}  active={showWcs}  title="WCS axes">⊕</VTBtn>
        <VTBtn
          onClick={onToggleStock}
          active={showStock && hasStock}
          disabled={!hasStock}
          title="Stock envelope"
        >◫</VTBtn>
        <VTBtn
          onClick={onToggleToolpath}
          active={showToolpath && hasToolpaths}
          disabled={!hasToolpaths}
          title="Toolpath"
        >⟿</VTBtn>

        <Sep />

        {/* TOOLS group */}
        <VTBtn
          onClick={onMaximize}
          active={viewerMaximized}
          title={viewerMaximized ? 'Restore workspace' : 'Maximize viewer'}
        >{viewerMaximized ? '⊡' : '⊠'}</VTBtn>
        <VTBtn onClick={onFullscreen} title="Full screen (browser)">⛶</VTBtn>

      </div>
    </div>
  )
}
