/**
 * EngineeringFileInfo — shows structured import metadata after any engineering
 * file is selected.
 *
 * Displayed for all non-PDF formats (and optionally for PDF before the drawing
 * analysis result arrives).  Provides FILE_NAME, DETECTED_FORMAT, FORMAT_FAMILY,
 * IMPORT_STATUS, ENTITY_COUNT and a family-specific note.
 */

import { LoaderCircle } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { GeometrySummary, ImportResult } from '../../services/engineeringImport'
import type { FormatRoute } from '../../lib/engineeringFormats'

interface Props {
  fileName: string
  route: FormatRoute
  result: ImportResult | null   // null = loading
  error: string | null
  /** For IMAGE routes: object URL for preview (caller manages lifecycle) */
  previewUrl?: string | null
}

const ROW = 'flex flex-wrap gap-x-4 gap-y-0.5 text-sm'
const LABEL = 'w-36 shrink-0 text-tp-text-3'
const VALUE = 'font-medium text-tp-text break-all'

function StatusChip({ status }: { status: ImportResult['import_status'] }) {
  const colors: Record<string, string> = {
    SUCCESS:         'bg-tp-accent-muted text-tp-accent-light border-tp-accent-muted',
    PARTIAL_SUCCESS: 'bg-tp-warn-muted   text-tp-warn        border-tp-warn-muted',
    RECOGNIZED_ONLY: 'bg-tp-surface-2    text-tp-text-2      border-tp-border',
    FAILED:          'bg-tp-error-muted  text-tp-error       border-tp-error-muted',
    UNSUPPORTED:     'bg-tp-surface-2    text-tp-text-2      border-tp-border',
    UNRECOGNIZED:    'bg-tp-surface-2    text-tp-text-2      border-tp-border',
    PARSE_ERROR:     'bg-tp-error-muted  text-tp-error       border-tp-error-muted',
    UNKNOWN:         'bg-tp-surface-2    text-tp-text-2      border-tp-border',
  }
  const cls = colors[status] ?? colors.UNKNOWN
  return (
    <span className={`rounded border px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {status}
    </span>
  )
}

export default function EngineeringFileInfo({ fileName, route, result, error, previewUrl }: Props) {
  const { t } = useLocale()

  const familyNote = () => {
    if (!result) return null
    // Positive notes are only meaningful when the import actually succeeded or
    // partially succeeded; suppress them when the adapter reported a failure.
    const failed = result.import_status === 'FAILED' || result.import_status === 'PARSE_ERROR'
    switch (route) {
      case 'DRAWING_IMAGE':
        return t('drNonPdfNote')
      case 'DRAWING_VECTOR':
        return t('drDrawingAnalysisNote')
      case 'CAD_GEOMETRY':
        if (failed) return null
        return result.has_renderable_geometry ? t('drCadNote') : t('drCadStructureNote')
      case 'MESH_GEOMETRY':
        return failed ? null : t('drMeshNote')
      case 'NC_PROGRAM':
        return failed ? null : t('drNcNote')
      default:
        return null
    }
  }

  return (
    <div
      data-testid="engineering-file-info"
      className="mt-3 rounded-md border border-tp-border bg-tp-surface p-3 space-y-2"
    >
      <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
        {t('drImportInfoTitle')}
      </div>

      {/* Loading state */}
      {!result && !error && (
        <div className="flex items-center gap-2 text-sm text-tp-text-2">
          <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
          {t('drImportUploading')}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div role="alert" className="text-sm text-tp-error">
          {t('drImportError')}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-1.5">
          <div className={ROW}>
            <span className={LABEL}>{t('drFileName')}</span>
            <span className={VALUE}>{result.file_name}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drDetectedFormat')}</span>
            <span className={VALUE}>{result.format_id}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drFormatFamily')}</span>
            <span className={VALUE}>{result.format_family_label}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drImportStatus')}</span>
            <StatusChip status={result.import_status} />
          </div>
          {result.entity_count > 0 && (
            <div className={ROW}>
              <span className={LABEL}>{t('drEntityCount')}</span>
              <span className={VALUE}>{result.entity_count}</span>
            </div>
          )}
          <div className={ROW}>
            <span className={LABEL}>{t('drCapabilityLevel')}</span>
            <span className="text-xs text-tp-text-3">{result.capability_level}</span>
          </div>

          {/* Level-1 CAD fields */}
          {result.units && (
            <div className={ROW}>
              <span className={LABEL}>Units</span>
              <span className={VALUE}>{result.units}</span>
            </div>
          )}
          {result.source_file_name && result.source_file_name !== result.file_name && (
            <div className={ROW}>
              <span className={LABEL}>Source File</span>
              <span className={VALUE}>{result.source_file_name}</span>
            </div>
          )}
          {result.file_size_bytes != null && (
            <div className={ROW}>
              <span className={LABEL}>File Size</span>
              <span className={VALUE}>
                {result.file_size_bytes >= 1024 * 1024
                  ? `${(result.file_size_bytes / 1024 / 1024).toFixed(2)} MB`
                  : `${(result.file_size_bytes / 1024).toFixed(1)} KB`}
              </span>
            </div>
          )}
          {result.bounds && (
            <div className={ROW}>
              <span className={LABEL}>Model Bounds</span>
              <span className="text-[11px] text-tp-text-2 font-mono">
                X [{result.bounds.xmin.toFixed(3)}, {result.bounds.xmax.toFixed(3)}]{' '}
                Y [{result.bounds.ymin.toFixed(3)}, {result.bounds.ymax.toFixed(3)}]
                {(result.bounds.zmin !== 0 || result.bounds.zmax !== 0)
                  ? ` Z [${result.bounds.zmin.toFixed(3)}, ${result.bounds.zmax.toFixed(3)}]`
                  : ''}
              </span>
            </div>
          )}
          {result.entity_types && Object.keys(result.entity_types).length > 0 && (
            <div className="mt-1 border-t border-tp-border pt-1.5">
              <div className={ROW + ' mb-0.5'}>
                <span className={LABEL}>Entity Types</span>
              </div>
              <div className="pl-36 space-y-0.5">
                {Object.entries(result.entity_types)
                  .sort(([, a], [, b]) => b - a)
                  .map(([etype, count]) => (
                    <div key={etype} className="flex gap-2 text-[11px]">
                      <span className="text-tp-text-2 w-40 shrink-0">{etype}</span>
                      <span className="font-medium text-tp-text tabular-nums">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
          {/* Level-2 Geometry summary */}
          {(() => {
            const gs = result.geometry_summary as GeometrySummary | undefined
            if (!gs || typeof gs.parsed_geometry_count !== 'number') return null
            const typeRows: [string, number][] = [
              ['Lines', gs.lines],
              ['Arcs', gs.arcs],
              ['Circles', gs.circles],
              ['Ellipses', gs.ellipses],
              ['Polylines', gs.polylines],
              ['B-Spline Curves', gs.bspline_curves],
              ['Planes', gs.planes],
              ['Surfaces', gs.surfaces],
              ['Points', gs.points],
            ].filter(([, v]) => (v as number) > 0) as [string, number][]
            return (
              <div className="mt-1 border-t border-tp-border pt-1.5 space-y-0.5">
                <div className={ROW + ' mb-0.5'}>
                  <span className={LABEL}>Geometry</span>
                  <span className={VALUE}>
                    {gs.parsed_geometry_count} parsed
                    {gs.unsupported_geometry_count > 0 && ` · ${gs.unsupported_geometry_count} unsupported`}
                    {' '}({(gs.geometry_parse_ratio * 100).toFixed(1)}%)
                  </span>
                </div>
                {typeRows.length > 0 && (
                  <div className="pl-36 space-y-0.5">
                    {typeRows.map(([label, count]) => (
                      <div key={label} className="flex gap-2 text-[11px]">
                        <span className="text-tp-text-2 w-40 shrink-0">{label}</span>
                        <span className="font-medium text-tp-text tabular-nums">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className={ROW}>
                  <span className={LABEL}>Dimensionality</span>
                  <span className="text-[11px] text-tp-text-2">{gs.dimensionality}</span>
                </div>
                <div className={ROW}>
                  <span className={LABEL}>Bounds Status</span>
                  <span className={`text-[11px] ${
                    gs.bounds_status === 'COMPLETE' ? 'text-tp-accent-light' :
                    gs.bounds_status === 'PARTIAL' ? 'text-tp-warn' : 'text-tp-text-3'
                  }`}>{gs.bounds_status}</span>
                </div>
                <div className={ROW}>
                  <span className={LABEL}>Topology</span>
                  <span className="text-[11px] text-tp-text-3">Not available (3D visualization requires topology reconstruction)</span>
                </div>
              </div>
            )
          })()}
          {result.unsupported_entities && result.unsupported_entities.length > 0 && (
            <div className={ROW}>
              <span className={LABEL}>Unsupported</span>
              <span className="text-[11px] text-tp-warn">
                {result.unsupported_entities.join(', ')}
              </span>
            </div>
          )}
          {result.warnings && result.warnings.length > 0 && (
            <div className="mt-1 border-t border-tp-border pt-1.5 space-y-0.5">
              {result.warnings.slice(0, 5).map((w, i) => (
                <div key={i} className="text-[11px] text-tp-warn">⚠ {w}</div>
              ))}
            </div>
          )}

          {/* Format-specific metadata (key-value from first entity) */}
          {Object.keys(result.metadata).length > 0 && (
            <div className="mt-1 border-t border-tp-border pt-1.5 space-y-1">
              {Object.entries(result.metadata).map(([k, v]) => (
                <div key={k} className={ROW}>
                  <span className={LABEL + ' text-[11px]'}>{k.replace(/_/g, ' ')}</span>
                  <span className="text-[11px] text-tp-text-2">{String(v ?? '')}</span>
                </div>
              ))}
            </div>
          )}

          {/* Family-specific guidance note */}
          {familyNote() && (
            <p className="mt-1 text-xs text-tp-text-3 border-t border-tp-border pt-1.5">
              {familyNote()}
            </p>
          )}
        </div>
      )}

      {/* Image preview for DRAWING_IMAGE route */}
      {route === 'DRAWING_IMAGE' && previewUrl && (
        <div className="mt-2">
          <img
            data-testid="image-preview"
            src={previewUrl}
            alt={fileName}
            className="max-h-48 max-w-full rounded border border-tp-border object-contain"
          />
        </div>
      )}
    </div>
  )
}
