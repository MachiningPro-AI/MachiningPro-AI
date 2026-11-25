/**
 * WorkspaceSelectionFilter — compact BODY/FACE/EDGE/FEATURE toggle toolbar.
 *
 * Safety contract (MUST 38):
 *   SELECTION_DOES_NOT_CONFIRM_FEATURE=YES
 *   SELECTION_DOES_NOT_ALTER_WCS=YES
 *   SELECTION_DOES_NOT_REGENERATE_CAM=YES
 */

import { useLocale } from '../../i18n'
import type { SelectionMode } from './WorkspaceTypes'

const MODES: SelectionMode[] = ['BODY', 'FACE', 'EDGE', 'FEATURE']

interface SelectionFilterProps {
  mode:    SelectionMode
  onMode:  (m: SelectionMode) => void
  onClear: () => void
}

export default function WorkspaceSelectionFilter({ mode, onMode, onClear }: SelectionFilterProps) {
  const { t } = useLocale()

  const labels: Record<SelectionMode, string> = {
    BODY:    t('sel_modeBody'),
    FACE:    t('sel_modeFace'),
    EDGE:    t('sel_modeEdge'),
    FEATURE: t('sel_modeFeature'),
  }

  return (
    <div className="flex items-center gap-1 px-2 h-7 border-b border-tp-border bg-tp-surface shrink-0">
      <span className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 mr-1 shrink-0">
        {t('sel_filterLabel')}
      </span>
      {MODES.map(m => (
        <button
          key={m}
          type="button"
          onClick={() => onMode(m)}
          aria-pressed={mode === m}
          className={`px-2 py-0.5 rounded text-[9px] font-mono font-semibold transition-colors
            ${mode === m
              ? 'bg-tp-accent text-white'
              : 'text-tp-text-3 hover:text-tp-text hover:bg-tp-surface-2'
            }`}
        >
          {labels[m]}
        </button>
      ))}
      <div className="flex-1" />
      <button
        type="button"
        onClick={onClear}
        className="px-2 py-0.5 rounded text-[9px] text-tp-text-3 hover:text-tp-text hover:bg-tp-surface-2 font-mono"
        title={t('sel_clearSelection')}
      >
        {t('sel_clearSelection')}
      </button>
    </div>
  )
}
