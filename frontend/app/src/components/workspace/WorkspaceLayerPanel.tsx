/**
 * WorkspaceLayerPanel — Phase W visibility toggles
 *
 * Shows toggles for all Phase W layers:
 * PART / TARGET / STOCK / MACHINED_RESULT / TOOL / HOLDER / FIXTURE /
 * MACHINE / TOOLPATH / GOUGE / REMAINING_MATERIAL / COLLISION
 *
 * Safety:
 *   Visibility toggles only affect rendering — never engineering state
 *   TR/EN localization preserved
 *   NO_FABRICATED_DATA=YES
 */

import { Eye, EyeOff } from 'lucide-react'
import { useLocale } from '../../i18n'
import { ALL_WORKSPACE_LAYERS } from './WorkspaceTypes'
import type { LayerVisibilityState, WorkspaceLayer } from './WorkspaceTypes'

const LAYER_LABELS_EN: Record<WorkspaceLayer, string> = {
  PART:             'Part',
  TARGET:           'Target',
  STOCK:            'Stock',
  MACHINED_RESULT:  'Machined Result',
  TOOL:             'Tool',
  HOLDER:           'Holder',
  FIXTURE:          'Fixture',
  MACHINE:          'Machine',
  TOOLPATH:         'Toolpath',
  GOUGE:            'Gouge',
  REMAINING_MATERIAL: 'Remaining Material',
  COLLISION:        'Collision',
}

const LAYER_LABELS_TR: Record<WorkspaceLayer, string> = {
  PART:             'Parça',
  TARGET:           'Hedef',
  STOCK:            'Ham Malzeme',
  MACHINED_RESULT:  'İşlenmiş Sonuç',
  TOOL:             'Takım',
  HOLDER:           'Tutucu',
  FIXTURE:          'Bağlama Aparatı',
  MACHINE:          'Makine',
  TOOLPATH:         'Takım Yolu',
  GOUGE:            'Aşım',
  REMAINING_MATERIAL: 'Kalan Malzeme',
  COLLISION:        'Çarpışma',
}

const LAYER_COLORS: Partial<Record<WorkspaceLayer, string>> = {
  GOUGE:           'text-red-400',
  COLLISION:       'text-red-400',
  REMAINING_MATERIAL: 'text-blue-400',
  TOOLPATH:        'text-cyan-400',
  MACHINE:         'text-purple-400',
  HOLDER:          'text-yellow-400',
}

interface Props {
  visibility: LayerVisibilityState
  onChange: (layer: WorkspaceLayer, visible: boolean) => void
}

export default function WorkspaceLayerPanel({ visibility, onChange }: Props) {
  const { locale } = useLocale()
  const labels = locale === 'tr' ? LAYER_LABELS_TR : LAYER_LABELS_EN
  const title = locale === 'tr' ? 'Katmanlar' : 'Layers'

  return (
    <div className="flex flex-col gap-0 select-none">
      <div className="px-3 py-1.5 border-b border-tp-border">
        <span className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3">
          {title}
        </span>
      </div>
      {ALL_WORKSPACE_LAYERS.map(layer => {
        const visible = visibility[layer]
        const colorClass = LAYER_COLORS[layer] ?? 'text-tp-text-2'
        return (
          <button
            key={layer}
            type="button"
            onClick={() => onChange(layer, !visible)}
            className={`flex items-center gap-2 px-3 py-1 text-left hover:bg-tp-surface-2/60
                        transition-colors border-b border-tp-border/30
                        ${visible ? 'opacity-100' : 'opacity-40'}`}
            title={visible
              ? (locale === 'tr' ? 'Gizle' : 'Hide')
              : (locale === 'tr' ? 'Göster' : 'Show')}
          >
            <span className={`shrink-0 ${colorClass}`}>
              {visible
                ? <Eye size={12} />
                : <EyeOff size={12} />}
            </span>
            <span className={`text-[11px] ${visible ? 'text-tp-text' : 'text-tp-text-3'}`}>
              {labels[layer]}
            </span>
          </button>
        )
      })}
    </div>
  )
}
