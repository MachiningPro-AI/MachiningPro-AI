/**
 * Workflow history and export service — Level 20 production readiness.
 *
 * Pure TypeScript module (no React imports) so it can be unit-tested
 * with node:test without a DOM.
 *
 * Safety:
 *   NC_EXPORT_SAFETY=YES  — NC manifest always labelled OFFLINE_CANDIDATE
 *   NO_SEND_TO_CNC=YES    — no machine dispatch from this module
 *   NO_SERVER_PATH_LEAK=YES — authenticated download IDs only
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WorkflowHistoryItem {
  workflow_id: string
  part_reference: string
  status: string
  created_at: string
  updated_at: string
  objective: string | null
  current_stage: string | null
}

export type WorkflowExportFormat =
  | 'plan.json'
  | 'plan.html'
  | 'stages.csv'
  | 'dfm.json'
  | 'nc-manifest.json'

export interface ExportFormatMeta {
  id: WorkflowExportFormat
  label: string
  mimeType: string
  /** If true, display NC offline-candidate safety warning before download */
  ncSafetyWarning: boolean
}

// ---------------------------------------------------------------------------
// Export format registry
// ---------------------------------------------------------------------------

export const EXPORT_FORMATS: ExportFormatMeta[] = [
  { id: 'plan.json',         label: 'Manufacturing Plan JSON',  mimeType: 'application/json', ncSafetyWarning: false },
  { id: 'plan.html',         label: 'Manufacturing Plan HTML',  mimeType: 'text/html',        ncSafetyWarning: false },
  { id: 'stages.csv',        label: 'Stages CSV',               mimeType: 'text/csv',         ncSafetyWarning: false },
  { id: 'dfm.json',          label: 'DFM Analysis JSON',        mimeType: 'application/json', ncSafetyWarning: false },
  { id: 'nc-manifest.json',  label: 'NC Manifest JSON',         mimeType: 'application/json', ncSafetyWarning: true  },
]

/** NC manifest safety labels — always present in downloaded file. */
export const NC_MANIFEST_SAFETY_LABELS = {
  OFFLINE_CANDIDATE: true,
  NOT_MACHINE_APPROVED: true,
  NOT_DISPATCHED: true,
  NO_CNC_TRANSFER: true,
} as const

export function isNcSafetyFormat(format: WorkflowExportFormat): boolean {
  return format === 'nc-manifest.json'
}

export function getExportMeta(format: WorkflowExportFormat): ExportFormatMeta | undefined {
  return EXPORT_FORMATS.find(f => f.id === format)
}

// ---------------------------------------------------------------------------
// Session storage — reload recovery
// ---------------------------------------------------------------------------

const SESSION_KEY = 'machiningpro_current_workflow_id'

export function saveCurrentWorkflowId(workflowId: string): void {
  try {
    sessionStorage.setItem(SESSION_KEY, workflowId)
  } catch {
    // sessionStorage unavailable (private window, etc.) — degrade gracefully
  }
}

export function restoreCurrentWorkflowId(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

export function clearCurrentWorkflowId(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Export URL builder (no fetch — caller decides how to trigger download)
// ---------------------------------------------------------------------------

export function buildExportUrl(workflowId: string, format: WorkflowExportFormat): string {
  // Workflow IDs follow the pattern WF_<hex> — no path chars possible,
  // but we sanitize defensively.
  const safeId = workflowId.replace(/[^A-Za-z0-9_\-]/g, '')
  return `/api/workflow/${safeId}/export/${format}`
}

// ---------------------------------------------------------------------------
// Status display helpers
// ---------------------------------------------------------------------------

export function statusBadgeClass(status: string): string {
  switch (status) {
    case 'COMPLETED': return 'text-green-600'
    case 'PARTIAL':   return 'text-yellow-600'
    case 'RUNNING':   return 'text-blue-500'
    case 'INTERRUPTED': return 'text-orange-500'
    case 'FAILED':    return 'text-red-500'
    default:          return 'text-gray-400'
  }
}

export function formatHistoryDate(isoString: string): string {
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return isoString
  }
}
