/**
 * WorkspaceMeasurementPanel — measurement results table.
 *
 * Safety contract (MUST 38):
 *   MEASUREMENT_DOES_NOT_IMPLY_METROLOGY_GRADE_INSPECTION=YES
 *   MEASUREMENT_USES_WORLD_SPACE_COORDINATES=YES
 *   NO_FABRICATED_DIMENSIONS=YES
 */

import { X, Trash2 } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { MeasurementEntry } from './WorkspaceTypes'

interface MeasurementPanelProps {
  measurements:    MeasurementEntry[]
  pendingPoint:    [number,number,number] | null
  onClear:         () => void
  onRemove:        (id: string) => void
  onMeasureMode:   () => void  // triggers "select first point" state
}

export default function WorkspaceMeasurementPanel({
  measurements,
  pendingPoint,
  onClear,
  onRemove,
}: MeasurementPanelProps) {
  const { t } = useLocale()

  const statusLabel = (m: MeasurementEntry) => {
    if (m.status === 'APPROXIMATE') return t('meas_approximate')
    if (m.status === 'INSUFFICIENT_DATA') return t('meas_noData')
    return t('meas_ok')
  }

  const typeLabel = (m: MeasurementEntry) => {
    switch (m.type) {
      case 'POINT_DISTANCE': return t('meas_pointDistance')
      case 'EDGE_LENGTH':    return t('meas_edgeLength')
      case 'RADIUS':         return t('meas_radius')
      case 'DIAMETER':       return t('meas_diameter')
      case 'ANGLE':          return t('meas_angle')
      default: return m.type
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-1 px-3 h-8 border-b border-tp-border">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 flex-1">
          {t('meas_title')}
        </span>
        {measurements.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            title={t('meas_clear')}
            aria-label={t('meas_clear')}
            className="p-0.5 rounded text-tp-text-3 hover:text-tp-error"
          >
            <Trash2 size={10} />
          </button>
        )}
      </div>

      {/* Pending prompt */}
      {pendingPoint && (
        <div className="shrink-0 px-3 py-1.5 bg-tp-accent/10 border-b border-tp-border/50 text-[10px] text-tp-accent-light">
          {t('sel_selectSecondPoint')}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-y-auto [scrollbar-width:thin]">
        {measurements.length === 0 && !pendingPoint ? (
          <div className="p-3 text-[11px] text-tp-text-3 italic">
            {t('meas_noData')}
          </div>
        ) : (
          <table className="w-full text-[10px]">
            <thead>
              <tr className="border-b border-tp-border">
                <th className="text-left px-3 py-1 font-semibold text-tp-text-3 w-28">{t('meas_type')}</th>
                <th className="text-right px-2 py-1 font-semibold text-tp-text-3">{t('meas_value')}</th>
                <th className="text-left px-2 py-1 font-semibold text-tp-text-3 w-16">{t('meas_status')}</th>
                <th className="w-5" />
              </tr>
            </thead>
            <tbody>
              {measurements.map(m => (
                <tr key={m.id} className="border-b border-tp-border/40 hover:bg-tp-surface-2/40">
                  <td className="px-3 py-1 text-tp-text font-mono">{typeLabel(m)}</td>
                  <td className="px-2 py-1 text-right text-tp-text font-mono font-semibold">
                    {m.display}
                  </td>
                  <td className="px-2 py-1">
                    <span className={`font-mono text-[9px] px-1 py-0.5 rounded
                      ${m.status === 'OK'
                        ? 'text-tp-text-3'
                        : 'text-yellow-400 bg-yellow-900/20'
                      }`}>
                      {statusLabel(m)}
                    </span>
                  </td>
                  <td className="pr-2 py-1">
                    <button
                      type="button"
                      onClick={() => onRemove(m.id)}
                      title={t('meas_remove')}
                      aria-label={t('meas_remove')}
                      className="text-tp-text-3 hover:text-tp-error p-0.5 rounded"
                    >
                      <X size={9} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
