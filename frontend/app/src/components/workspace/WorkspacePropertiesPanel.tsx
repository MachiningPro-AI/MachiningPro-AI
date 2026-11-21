/**
 * WorkspacePropertiesPanel — right panel showing selected node properties
 * and verification state.
 *
 * Safety contract:
 *   VERIFICATION_STATE=NOT_PERFORMED for all checks
 *   IS_VERIFIED=false always shown
 *   SIMULATION_REQUIRED=true always shown
 *   NO_FABRICATED_PROPERTIES=YES — only shows real loaded data
 */

import { useState } from 'react'
import type { CSSProperties } from 'react'
import { ChevronRight, Pin, Search, X, Copy, Database } from 'lucide-react'
import { useLocale } from '../../i18n'
import { SAFETY, formatFileSize, COLLAPSED_STRIP_W } from './WorkspaceTypes'
import type { WorkspaceFile, ConnectedWorkflow, OperationSummary } from './WorkspaceTypes'
import type { PreviewMesh, ImportResult } from '../../services/engineeringImport'

type IgesDiagnostics = ImportResult['iges_diagnostics']

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function PropRow({ label, value, filter }: {
  label: string
  value: string | number | null | undefined
  filter?: string
}) {
  if (value === null || value === undefined || value === '') return null
  const str = String(value)
  if (filter) {
    const lc = filter.toLowerCase()
    if (!label.toLowerCase().includes(lc) && !str.toLowerCase().includes(lc)) return null
  }
  return (
    <div className="group flex items-start gap-2 py-1 border-b border-tp-border/40 hover:bg-tp-surface-2/40">
      <span className="shrink-0 w-28 text-[11px] text-tp-text-3">{label}</span>
      <span className="flex-1 text-[11px] text-tp-text break-all font-mono">{str}</span>
      <button
        type="button"
        onClick={() => void navigator.clipboard.writeText(str).catch(() => undefined)}
        title="Copy value"
        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity
                   text-tp-text-3 hover:text-tp-text p-px"
        aria-label="Copy value"
      >
        <Copy size={9} />
      </button>
    </div>
  )
}

function SectionHeader({ label }: { label: string }) {
  return (
    <div className="pt-2 pb-1">
      <span className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3">
        {label}
      </span>
    </div>
  )
}

function StatusBadge({ label, value }: { label: string; value: string }) {
  const isNotPerformed = value.includes('NOT_PERFORMED') || value.includes('NOT_VERIFIED')
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="shrink-0 w-28 text-[11px] text-tp-text-3">{label}</span>
      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded
                       ${isNotPerformed
                         ? 'bg-tp-surface-3 text-tp-text-3 border border-tp-border'
                         : 'bg-tp-accent/10 text-tp-accent-light border border-tp-accent/20'
                       }`}>
        {value}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// File properties section
// ---------------------------------------------------------------------------

function FileProperties({ wsFile, mesh, filter }: {
  wsFile: WorkspaceFile | null
  mesh: PreviewMesh | null
  filter?: string
}) {
  const { t } = useLocale()
  if (!wsFile && !mesh) return null

  return (
    <div className="px-3 pb-2">
      <SectionHeader label="File Properties" />
      {wsFile && <PropRow label={t('ws_fileName')}   value={wsFile.name}                              filter={filter} />}
      {wsFile && <PropRow label={t('ws_fileFormat')} value={wsFile.format}                           filter={filter} />}
      {wsFile && <PropRow label={t('ws_fileSize')}   value={formatFileSize(wsFile.sizeBytes)}        filter={filter} />}
      {wsFile && <PropRow label={t('ws_loadedAt')}   value={wsFile.loadedAt.toLocaleTimeString()}   filter={filter} />}
      {mesh   && <PropRow label="Context"            value="Geometry Properties"                     filter={filter} />}
      {mesh   && <PropRow label={t('ws_vertices')}   value={mesh.vertex_count.toLocaleString()}      filter={filter} />}
      {mesh   && <PropRow label={t('ws_triangles')}  value={mesh.triangle_count.toLocaleString()}    filter={filter} />}
      {mesh?.bounding_box && (
        <>
          <SectionHeader label={t('ws_boundingBox')} />
          <PropRow label="X" value={`${mesh.bounding_box.min[0].toFixed(3)} → ${mesh.bounding_box.max[0].toFixed(3)} mm`} filter={filter} />
          <PropRow label="Y" value={`${mesh.bounding_box.min[1].toFixed(3)} → ${mesh.bounding_box.max[1].toFixed(3)} mm`} filter={filter} />
          <PropRow label="Z" value={`${mesh.bounding_box.min[2].toFixed(3)} → ${mesh.bounding_box.max[2].toFixed(3)} mm`} filter={filter} />
          <PropRow label="Size X" value={`${(mesh.bounding_box.max[0] - mesh.bounding_box.min[0]).toFixed(3)} mm`} filter={filter} />
          <PropRow label="Size Y" value={`${(mesh.bounding_box.max[1] - mesh.bounding_box.min[1]).toFixed(3)} mm`} filter={filter} />
          <PropRow label="Size Z" value={`${(mesh.bounding_box.max[2] - mesh.bounding_box.min[2]).toFixed(3)} mm`} filter={filter} />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Operation properties section
// ---------------------------------------------------------------------------

function OperationProperties({ op, filter }: { op: OperationSummary; filter?: string }) {
  const { t } = useLocale()
  return (
    <div className="px-3 pb-2">
      <SectionHeader label="Operation Properties" />
      <PropRow label="Context"  value="Operation Properties" filter={filter} />
      <PropRow label="ID"       value={op.operationId}         filter={filter} />
      <PropRow label="Name"     value={op.name}                filter={filter} />
      <PropRow label="Type"     value={op.type}                filter={filter} />
      <PropRow label="Tool Ref" value={op.toolRef ?? '—'}      filter={filter} />
      <PropRow label="Setup"    value={op.setupRef ?? '—'}     filter={filter} />
      <PropRow label="Seq #"    value={op.sequenceNumber}      filter={filter} />
      <PropRow label="Status"   value={op.status}              filter={filter} />
      <SectionHeader label="CAM Context" />
      <PropRow label="Category" value={t('ws_camOperations')}  filter={filter} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Verification section (always NOT_PERFORMED)
// ---------------------------------------------------------------------------

function VerificationSection({ filter }: { filter?: string }) {
  const { t } = useLocale()
  // Filter check: show section only if filter matches any item
  if (filter) {
    const lc = filter.toLowerCase()
    const items = ['verification', 'collision', 'gouge', 'fixture', 'machine', 'envelope', 'not_performed']
    if (!items.some(s => s.includes(lc))) return null
  }
  return (
    <div className="px-3 pb-3">
      <SectionHeader label={t('ws_verification')} />
      <StatusBadge label={t('ws_collisionCheck')}  value={SAFETY.COLLISION_CHECK} />
      <StatusBadge label={t('ws_gougeCheck')}      value={SAFETY.GOUGE_CHECK} />
      <StatusBadge label={t('ws_fixtureCheck')}    value={SAFETY.FIXTURE_CHECK} />
      <StatusBadge label={t('ws_machineEnvCheck')} value={SAFETY.MACHINE_ENVELOPE_CHECK} />
      <div className="mt-2 p-2 rounded bg-tp-surface-3 border border-tp-border/50">
        <p className="text-[10px] text-tp-text-3 leading-relaxed">
          {t('ws_safetyNote')}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WorkspacePropertiesPanel
// ---------------------------------------------------------------------------

export interface PropertiesPanelProps {
  wsFile:          WorkspaceFile | null
  mesh:            PreviewMesh | null
  workflow:        ConnectedWorkflow | null
  selectedId:      string | null
  igesDiagnostics?: IgesDiagnostics
  collapsed?:      boolean
  onCollapse?:     () => void
  style?:          CSSProperties
}

export default function WorkspacePropertiesPanel({
  wsFile,
  mesh,
  workflow,
  selectedId,
  igesDiagnostics,
  collapsed = false,
  onCollapse,
  style,
}: PropertiesPanelProps) {
  const { t } = useLocale()
  const [searchTerm, setSearchTerm] = useState('')
  const [showSearch, setShowSearch] = useState(false)

  const filter = showSearch && searchTerm ? searchTerm : undefined

  // Determine context — MUST 12
  const selectedOp = selectedId && workflow
    ? workflow.operations.find(op => `op-${op.operationId}` === selectedId)
    : null

  const isMeshNode     = selectedId === 'body-0'
  const isRootNode     = selectedId === 'root' || selectedId?.startsWith('wf-')

  // Collapsed strip — MUST 3
  if (collapsed) {
    return (
      <div
        className="h-full shrink-0 flex flex-col items-center justify-between
                   border-l border-tp-border bg-tp-surface py-1 cursor-pointer
                   hover:bg-tp-surface-2 transition-colors"
        style={{ width: `${COLLAPSED_STRIP_W}px`, minWidth: `${COLLAPSED_STRIP_W}px` }}
        role="button"
        aria-label="Expand Properties"
        title="Expand Properties"
        onClick={onCollapse}
      >
        <button
          type="button"
          className="text-tp-text-3 hover:text-tp-text p-1"
          onClick={e => { e.stopPropagation(); onCollapse?.() }}
          aria-label="Expand"
        >
          <ChevronRight size={14} />
        </button>
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3
                           [writing-mode:vertical-rl]">
            {t('ws_properties')}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-hidden flex flex-col border-l border-tp-border bg-tp-surface"
         style={style ?? { width: '260px', minWidth: '260px' }}>

      {/* Properties toolbar — MUST 11 */}
      <div className="shrink-0 h-8 flex items-center px-2 border-b border-tp-border gap-1">
        <Pin size={10} className="text-tp-text-3 shrink-0" aria-hidden="true" />
        <span className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 flex-1 truncate">
          {selectedOp
            ? 'Operation'
            : (isMeshNode || (mesh && !isRootNode))
              ? 'Geometry'
              : t('ws_properties')
          }
        </span>
        <button
          type="button"
          onClick={() => { setShowSearch(v => !v); if (showSearch) setSearchTerm('') }}
          title="Filter properties"
          aria-label="Filter properties"
          className={`p-0.5 rounded ${showSearch ? 'text-tp-accent-light' : 'text-tp-text-3 hover:text-tp-text'}`}
        >
          <Search size={10} />
        </button>
        <button
          type="button"
          title="Source / provenance"
          aria-label="Show source"
          className="p-0.5 rounded text-tp-text-3 hover:text-tp-text"
        >
          <Database size={10} />
        </button>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-label="Collapse Properties"
            title="Collapse"
            className="p-0.5 rounded text-tp-text-3 hover:text-tp-text"
          >
            <X size={10} />
          </button>
        )}
      </div>

      {/* Search bar — MUST 13 */}
      {showSearch && (
        <div className="shrink-0 flex items-center border-b border-tp-border px-2 py-1 gap-1">
          <Search size={10} className="text-tp-text-3 shrink-0" aria-hidden="true" />
          <input
            type="text"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Filter properties…"
            className="flex-1 bg-transparent text-[11px] text-tp-text placeholder:text-tp-text-3
                       outline-none"
            autoFocus
          />
          {searchTerm && (
            <button type="button" onClick={() => setSearchTerm('')} className="text-tp-text-3 hover:text-tp-text">
              <X size={9} />
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto [scrollbar-width:thin]
                      [scrollbar-color:theme(colors.tp-border)_transparent]">
        {!wsFile && !workflow && !mesh ? (
          <div className="p-3 text-[11px] text-tp-text-3 italic">
            {t('ws_selectNode')}
          </div>
        ) : (
          <>
            {selectedOp ? (
              <OperationProperties op={selectedOp} filter={filter} />
            ) : (
              <>
                <FileProperties wsFile={wsFile} mesh={mesh} filter={filter} />
                {/* IGES import diagnostics — shown when non-geometric entities were skipped */}
                {igesDiagnostics && igesDiagnostics.iges_import_status !== 'COMPLETE' && (
                  <div className="px-3 pb-2">
                    <SectionHeader label="IGES Import Diagnostics" />
                    <PropRow label="Status"      value={igesDiagnostics.iges_import_status} filter={filter} />
                    <PropRow label="Geometry"    value={igesDiagnostics.renderable_geometry ? 'Present' : 'None'} filter={filter} />
                    {igesDiagnostics.skipped_presentation_count > 0 && (
                      <PropRow label="Presentation" value={`${igesDiagnostics.skipped_presentation_count} entities skipped (non-geometric)`} filter={filter} />
                    )}
                    {igesDiagnostics.skipped_annotation_count > 0 && (
                      <PropRow label="Annotation"   value={`${igesDiagnostics.skipped_annotation_count} entities skipped (non-geometric)`} filter={filter} />
                    )}
                    {igesDiagnostics.skipped_metadata_count > 0 && (
                      <PropRow label="Metadata"     value={`${igesDiagnostics.skipped_metadata_count} entities skipped (non-geometric)`} filter={filter} />
                    )}
                    {igesDiagnostics.unsupported_geometric_count > 0 && (
                      <PropRow label="Unsup. Geom." value={`${igesDiagnostics.unsupported_geometric_count} geometric entities unsupported`} filter={filter} />
                    )}
                    <PropRow label="Note" value="Geometric surfaces rendered; non-geometric records ignored" filter={filter} />
                  </div>
                )}
              </>
            )}
            {/* Workflow connection info — MUST 12: Workflow context */}
            {workflow && !selectedOp && (
              <div className="px-3 pb-2">
                <SectionHeader label="Workflow" />
                <PropRow label="ID"       value={workflow.workflowId}             filter={filter} />
                <PropRow label="Part"     value={workflow.partName ?? '—'}        filter={filter} />
                <PropRow label="Drawing"  value={workflow.drawingNumber ?? '—'}   filter={filter} />
                <PropRow label="Plan"     value={workflow.planStatus ?? '—'}      filter={filter} />
                <PropRow label="Ops"      value={workflow.operations.length}      filter={filter} />
                <PropRow label="TP Groups" value={workflow.toolpathGroups.length} filter={filter} />
              </div>
            )}
          </>
        )}

        {/* Verification — always visible — MUST 12: Verification context */}
        <div className="border-t border-tp-border mt-1">
          <VerificationSection filter={filter} />
        </div>
      </div>
    </div>
  )
}
