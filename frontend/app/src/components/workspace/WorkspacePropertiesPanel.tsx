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

import { useLocale } from '../../i18n'
import { SAFETY, formatFileSize } from './WorkspaceTypes'
import type { WorkspaceFile, ConnectedWorkflow, OperationSummary } from './WorkspaceTypes'
import type { PreviewMesh } from '../../services/engineeringImport'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function PropRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-start gap-2 py-1 border-b border-tp-border/40">
      <span className="shrink-0 w-28 text-[11px] text-tp-text-3">{label}</span>
      <span className="flex-1 text-[11px] text-tp-text break-all font-mono">{String(value)}</span>
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

function FileProperties({ wsFile, mesh }: { wsFile: WorkspaceFile | null; mesh: PreviewMesh | null }) {
  const { t } = useLocale()
  if (!wsFile && !mesh) return null

  return (
    <div className="px-3 pb-2">
      <SectionHeader label={t('ws_fileName')} />
      {wsFile && <PropRow label={t('ws_fileName')} value={wsFile.name} />}
      {wsFile && <PropRow label={t('ws_fileFormat')} value={wsFile.format} />}
      {wsFile && <PropRow label={t('ws_fileSize')} value={formatFileSize(wsFile.sizeBytes)} />}
      {wsFile && <PropRow label={t('ws_loadedAt')} value={wsFile.loadedAt.toLocaleTimeString()} />}
      {mesh && <PropRow label={t('ws_vertices')} value={mesh.vertex_count.toLocaleString()} />}
      {mesh && <PropRow label={t('ws_triangles')} value={mesh.triangle_count.toLocaleString()} />}
      {mesh?.bounding_box && (
        <>
          <SectionHeader label={t('ws_boundingBox')} />
          <PropRow label="X" value={`${mesh.bounding_box.min[0].toFixed(3)} → ${mesh.bounding_box.max[0].toFixed(3)} mm`} />
          <PropRow label="Y" value={`${mesh.bounding_box.min[1].toFixed(3)} → ${mesh.bounding_box.max[1].toFixed(3)} mm`} />
          <PropRow label="Z" value={`${mesh.bounding_box.min[2].toFixed(3)} → ${mesh.bounding_box.max[2].toFixed(3)} mm`} />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Operation properties section
// ---------------------------------------------------------------------------

function OperationProperties({ op }: { op: OperationSummary }) {
  const { t } = useLocale()
  return (
    <div className="px-3 pb-2">
      <SectionHeader label={t('ws_camOperations')} />
      <PropRow label="ID"       value={op.operationId} />
      <PropRow label="Name"     value={op.name} />
      <PropRow label="Type"     value={op.type} />
      <PropRow label="Tool"     value={op.toolRef ?? '—'} />
      <PropRow label="Setup"    value={op.setupRef ?? '—'} />
      <PropRow label="Seq #"    value={op.sequenceNumber} />
      <PropRow label="Status"   value={op.status} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Verification section (always NOT_PERFORMED)
// ---------------------------------------------------------------------------

function VerificationSection() {
  const { t } = useLocale()
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
  wsFile:    WorkspaceFile | null
  mesh:      PreviewMesh | null
  workflow:  ConnectedWorkflow | null
  selectedId: string | null
}

type PanelTab = 'properties' | 'verification'

export default function WorkspacePropertiesPanel({
  wsFile,
  mesh,
  workflow,
  selectedId,
}: PropertiesPanelProps) {
  const { t } = useLocale()

  // Find selected operation from workflow
  const selectedOp = selectedId && workflow
    ? workflow.operations.find(op => `op-${op.operationId}` === selectedId)
    : null

  const tab: PanelTab = 'properties'  // single tab for now; verification always visible below

  return (
    <div className="h-full overflow-hidden flex flex-col border-l border-tp-border bg-tp-surface"
         style={{ width: '260px', minWidth: '260px' }}>
      {/* Header */}
      <div className="shrink-0 h-8 flex items-center px-3 border-b border-tp-border gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">
          {t('ws_properties')}
        </span>
        <span className="ml-auto text-[9px] font-mono text-tp-text-3 opacity-60">
          {t('ws_simNotVerified')}
        </span>
      </div>

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
              <OperationProperties op={selectedOp} />
            ) : (
              <FileProperties wsFile={wsFile} mesh={mesh} />
            )}
            {/* Workflow connection info */}
            {workflow && !selectedOp && (
              <div className="px-3 pb-2">
                <SectionHeader label="Workflow" />
                <PropRow label="ID"      value={workflow.workflowId} />
                <PropRow label="Part"    value={workflow.partName ?? '—'} />
                <PropRow label="Drawing" value={workflow.drawingNumber ?? '—'} />
                <PropRow label="Plan"    value={workflow.planStatus ?? '—'} />
                <PropRow label="Ops"     value={workflow.operations.length} />
                <PropRow label="TP Groups" value={workflow.toolpathGroups.length} />
              </div>
            )}
          </>
        )}

        {/* Verification — always visible */}
        <div className="border-t border-tp-border mt-1">
          <VerificationSection />
        </div>
      </div>
    </div>
  )
}
