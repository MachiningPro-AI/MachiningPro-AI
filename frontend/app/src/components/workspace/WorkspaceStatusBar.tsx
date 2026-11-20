/**
 * WorkspaceStatusBar — bottom status line.
 *
 * Shows: cursor position, units toggle, file info, verification state.
 * Always displays NOT_PERFORMED for all verification checks.
 */

import { useLocale } from '../../i18n'
import { SAFETY } from './WorkspaceTypes'
import type { WorkspaceFile } from './WorkspaceTypes'

function coord(val: number): string {
  return val.toFixed(3).padStart(9)
}

export interface StatusBarProps {
  wsFile:        WorkspaceFile | null
  cursorPos:     [number, number, number] | null
  units:         'mm' | 'inch'
  onToggleUnits: () => void
  operationCount: number
  toolpathCount:  number
}

export default function WorkspaceStatusBar({
  wsFile,
  cursorPos,
  units,
  onToggleUnits,
  operationCount,
  toolpathCount,
}: StatusBarProps) {
  const { t } = useLocale()

  const scale = units === 'inch' ? 0.0393701 : 1
  const cp = cursorPos
    ? [cursorPos[0] * scale, cursorPos[1] * scale, cursorPos[2] * scale] as [number, number, number]
    : null

  return (
    <div className="shrink-0 h-6 flex items-center px-3 gap-3 bg-tp-surface-2
                    border-t border-tp-border text-[10px] font-mono text-tp-text-3
                    overflow-hidden select-none">

      {/* Cursor coordinates */}
      <div className="flex items-center gap-1 shrink-0">
        <span className="text-[8px] uppercase text-tp-text-3/60">X</span>
        <span className="text-tp-text-2">{cp ? coord(cp[0]) : '—'}</span>
        <span className="text-[8px] uppercase text-tp-text-3/60 ml-1">Y</span>
        <span className="text-tp-text-2">{cp ? coord(cp[1]) : '—'}</span>
        <span className="text-[8px] uppercase text-tp-text-3/60 ml-1">Z</span>
        <span className="text-tp-text-2">{cp ? coord(cp[2]) : '—'}</span>
      </div>

      {/* Units toggle */}
      <button
        type="button"
        onClick={onToggleUnits}
        className="shrink-0 px-1 py-px rounded border border-tp-border/60
                   hover:border-tp-border text-tp-text-2 hover:text-tp-text"
        title="Toggle units"
      >
        {units}
      </button>

      <div className="w-px h-3 bg-tp-border/40 shrink-0" />

      {/* File name */}
      {wsFile && (
        <span className="truncate max-w-[180px] text-tp-text-2">{wsFile.name}</span>
      )}

      <div className="flex-1" />

      {/* Operation and toolpath counts */}
      {operationCount > 0 && (
        <span className="shrink-0">
          {t('ws_operationCount')}: {operationCount}
        </span>
      )}
      {toolpathCount > 0 && (
        <span className="shrink-0">
          {t('ws_toolpathCount')}: {toolpathCount}
        </span>
      )}

      <div className="w-px h-3 bg-tp-border/40 shrink-0" />

      {/* Safety invariants */}
      <span className="shrink-0 text-tp-text-3/70">
        SIM: {SAFETY.SIMULATION_STATE}
      </span>
      <span className="shrink-0 text-tp-text-3/70">
        VER: {SAFETY.VERIFICATION_STATE}
      </span>
      <span className="shrink-0 text-tp-text-3/70">
        DISPATCH: NO
      </span>
    </div>
  )
}
