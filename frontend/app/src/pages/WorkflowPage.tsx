/**
 * Level-19/20 Manufacturing Workflow — One-Click Manufacturing Analysis.
 *
 * Level-20 additions:
 *   - Workflow history panel (Recent Workflows) backed by /api/workflow/history
 *   - Browser reload recovery via sessionStorage + /api/workflow/{id}
 *   - Authenticated export downloads via /api/workflow/{id}/export/{format}
 *
 * Safety constraints (enforced by backend — UI reflects, never bypasses):
 *   PRODUCTION_APPROVED=NO  — plan is proposal only, requires engineering review
 *   NO_AUTO_DISPATCH=YES    — no machine dispatch from this UI
 *   NO_CNC_WRITE=YES        — no machine writes
 *   NC_EXPORT_UI_SAFE=YES   — NC manifest always labelled OFFLINE CANDIDATE
 */

import { useState, useCallback, useEffect, type ChangeEvent } from 'react'
import { useLocale } from '../i18n'
import type { TranslationDictionary } from '../i18n/types'
import {
  CheckCircle, XCircle, AlertCircle, Clock, Loader,
  SkipForward, ChevronRight, FileText, AlertTriangle,
  Eye, Download, History, RefreshCw
} from 'lucide-react'

import {
  EXPORT_FORMATS,
  buildExportUrl,
  formatHistoryDate,
  isNcSafetyFormat,
  saveCurrentWorkflowId,
  restoreCurrentWorkflowId,
  statusBadgeClass,
  type WorkflowHistoryItem,
  type WorkflowExportFormat,
} from '../services/workflowHistory'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type WorkflowObjective =
  | 'BALANCED' | 'MINIMUM_CYCLE_TIME' | 'MINIMUM_COST'
  | 'MAXIMUM_TOOL_LIFE' | 'MINIMUM_RISK'

type WorkflowMode =
  | 'ANALYSIS_ONLY' | 'DFM_ONLY' | 'QUOTE_ONLY' | 'CAM_PLAN_ONLY'
  | 'CAM_AND_TOOLPATH' | 'OFFLINE_NC' | 'MACHINE_SELECTION' | 'FULL_MANUFACTURING_PLAN'

type StageStatus =
  | 'NOT_STARTED' | 'RUNNING' | 'PASS' | 'PARTIAL'
  | 'BLOCKED' | 'FAILED' | 'REVIEW_REQUIRED' | 'SKIPPED_NOT_REQUESTED'

type UploadState = 'NOT_SELECTED' | 'UPLOADING' | 'UPLOADED' | 'UPLOAD_FAILED'

interface StageInfo {
  stage: string
  status: StageStatus
  duration_ms: number | null
  warnings: string[]
  errors: string[]
  blocking_reasons: string[]
  review_required: boolean
}

interface WorkflowSummary {
  workflow_id: string
  status: string
  blocking_issue_count: number
  known_unknown_count: number
  review_item_count: number
}

interface PlanSummary {
  plan_id: string
  production_approved: boolean
  dispatched: boolean
  machine_started: boolean
  blocking_issues: Array<{ code: string; description: string; required_action: string }>
  known_unknowns: Array<{ category: string; description: string }>
  review_items: Array<{ category: string; description: string; mandatory: boolean }>
  alternative_plans: Array<{ plan_type: string; description: string; evidence: string }>
}

// ---------------------------------------------------------------------------
// Stage display metadata
// ---------------------------------------------------------------------------

const ALL_STAGES = [
  '01_CAD_IMPORT', '02_GEOMETRY', '03_FEATURE_RECOGNITION', '04_DFM',
  '05_PROCESS_PLANNING', '06_MACHINE_SELECTION', '07_TOOL_SELECTION',
  '08_CUTTING_DATA', '09_CYCLE_TIME', '10_COST_RFQ', '11_CAM_PLANNING',
  '12_TOOLPATH', '13_VERIFICATION', '14_NC_CANDIDATE', '15_SCHEDULING',
  '16_JOB_ASSIGNMENT', '17_ADAPTIVE_INTELLIGENCE', '18_DIGITAL_TWIN',
  '19_FINAL_MANUFACTURING_PLAN',
]

function getStageLabels(t: (key: keyof TranslationDictionary) => string): Record<string, string> {
  return {
    '01_CAD_IMPORT':              t('wfStageCadImport'),
    '02_GEOMETRY':                t('wfStageGeometry'),
    '03_FEATURE_RECOGNITION':     t('wfStageFeatures'),
    '04_DFM':                     t('wfStageDfm'),
    '05_PROCESS_PLANNING':        t('wfStageProcess'),
    '06_MACHINE_SELECTION':       t('wfStageMachine'),
    '07_TOOL_SELECTION':          t('wfStageTool'),
    '08_CUTTING_DATA':            t('wfStageCuttingData'),
    '09_CYCLE_TIME':              t('wfStageCycleTime'),
    '10_COST_RFQ':                t('wfStageCostRfq'),
    '11_CAM_PLANNING':            t('wfStageCam'),
    '12_TOOLPATH':                t('wfStageToolpath'),
    '13_VERIFICATION':            t('wfStageVerification'),
    '14_NC_CANDIDATE':            t('wfStageNc'),
    '15_SCHEDULING':              t('wfStageScheduling'),
    '16_JOB_ASSIGNMENT':          t('wfStageAssignment'),
    '17_ADAPTIVE_INTELLIGENCE':   t('wfStageAdaptiveAi'),
    '18_DIGITAL_TWIN':            t('wfStageDigitalTwin'),
    '19_FINAL_MANUFACTURING_PLAN': t('wfStagePlan'),
  }
}

// ---------------------------------------------------------------------------
// Status icon component
// ---------------------------------------------------------------------------

function StatusIcon({ status }: { status: StageStatus }) {
  const cls = 'w-4 h-4 shrink-0'
  switch (status) {
    case 'PASS':
      return <CheckCircle className={`${cls} text-green-500`} />
    case 'PARTIAL':
      return <AlertCircle className={`${cls} text-yellow-500`} />
    case 'BLOCKED':
    case 'FAILED':
      return <XCircle className={`${cls} text-red-500`} />
    case 'RUNNING':
      return <Loader className={`${cls} text-blue-500 animate-spin`} />
    case 'REVIEW_REQUIRED':
      return <Eye className={`${cls} text-purple-500`} />
    case 'SKIPPED_NOT_REQUESTED':
      return <SkipForward className={`${cls} text-tp-text-3`} />
    default:
      return <Clock className={`${cls} text-tp-text-3`} />
  }
}

function statusColor(status: StageStatus): string {
  switch (status) {
    case 'PASS': return 'text-green-500'
    case 'PARTIAL': return 'text-yellow-500'
    case 'BLOCKED': case 'FAILED': return 'text-red-500'
    case 'RUNNING': return 'text-blue-500'
    case 'REVIEW_REQUIRED': return 'text-purple-500'
    default: return 'text-tp-text-3'
  }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function getAuthHeaders(): Record<string, string> {
  try {
    const raw = sessionStorage.getItem('machiningpro_token')
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const token: string = parsed?.token ?? parsed
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)
  return resp.json()
}

async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: getAuthHeaders() })
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)
  return resp.json()
}

// ---------------------------------------------------------------------------
// Export download helper
// ---------------------------------------------------------------------------

async function downloadExport(workflowId: string, format: WorkflowExportFormat): Promise<void> {
  const url = buildExportUrl(workflowId, format)
  const resp = await fetch(url, { headers: getAuthHeaders() })
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}: ${await resp.text()}`)
  const blob = await resp.blob()
  const cd = resp.headers.get('content-disposition') ?? ''
  const fnMatch = cd.match(/filename="([^"]+)"/)
  const filename = fnMatch?.[1] ?? `machiningpro_${format}`
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(a.href)
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function WorkflowPage() {
  const { t } = useLocale()
  const stageLabels = getStageLabels(t)
  // Input state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadState, setUploadState] = useState<UploadState>('NOT_SELECTED')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [fileRef, setFileRef] = useState<string | null>(null)
  const [material, setMaterial] = useState('')
  const [quantity, setQuantity] = useState(1)
  const [stock, setStock] = useState('')
  const [objective, setObjective] = useState<WorkflowObjective>('BALANCED')
  const [mode, setMode] = useState<WorkflowMode>('FULL_MANUFACTURING_PLAN')

  // Workflow state
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [summary, setSummary] = useState<WorkflowSummary | null>(null)
  const [stages, setStages] = useState<StageInfo[]>([])
  const [plan, setPlan] = useState<PlanSummary | null>(null)
  const [selectedStage, setSelectedStage] = useState<StageInfo | null>(null)

  // Level-20: History state
  const [history, setHistory] = useState<WorkflowHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportingFormat, setExportingFormat] = useState<WorkflowExportFormat | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  // ---------------------------------------------------------------------------
  // Level-20: Load workflow history
  // ---------------------------------------------------------------------------

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const items = await apiGet<WorkflowHistoryItem[]>('/api/workflow/history?limit=20')
      setHistory(items)
    } catch {
      // History is a convenience feature — fail silently
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Level-20: Load a persisted workflow by ID
  // ---------------------------------------------------------------------------

  const loadWorkflowById = useCallback(async (id: string) => {
    try {
      const wf = await apiGet<WorkflowSummary>(`/api/workflow/${id}`)
      setWorkflowId(id)
      setSummary(wf)
      const stageData = await apiGet<StageInfo[]>(`/api/workflow/${id}/stages`)
      setStages(stageData)
      try {
        const planData = await apiGet<PlanSummary>(`/api/workflow/${id}/plan`)
        setPlan(planData)
      } catch {
        // No plan yet
      }
      saveCurrentWorkflowId(id)
    } catch {
      // Workflow may have been deleted or session expired
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Level-20: On mount — reload recovery + history
  // ---------------------------------------------------------------------------

  useEffect(() => {
    // Reload recovery: restore last workflow from sessionStorage
    const savedId = restoreCurrentWorkflowId()
    if (savedId) {
      loadWorkflowById(savedId)
    }
    // Always load history
    loadHistory()
  }, [loadHistory, loadWorkflowById])

  // ---------------------------------------------------------------------------
  // File upload
  // ---------------------------------------------------------------------------

  const handleFileSelect = useCallback(async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setSelectedFile(file)
    setFileRef(null)
    setUploadError(null)
    if (!file) { setUploadState('NOT_SELECTED'); return }
    setUploadState('UPLOADING')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const resp = await fetch('/api/cad-upload', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData,
      })
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)
      const data = await resp.json()
      setFileRef(data.file_ref)
      setUploadState('UPLOADED')
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err))
      setUploadState('UPLOAD_FAILED')
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Run workflow
  // ---------------------------------------------------------------------------

  const runWorkflow = useCallback(async () => {
    setRunning(true)
    setError(null)
    setStages([])
    setPlan(null)
    setSelectedStage(null)
    setExportError(null)

    try {
      const created = await apiPost<WorkflowSummary & { workflow_id: string }>('/api/workflow', {
        part_reference: selectedFile?.name.replace(/\.[^.]+$/, '') || 'UNNAMED_PART',
        revision: 'REV-A',
        source_file_ref: fileRef || null,
        requested_mode: mode,
        objective,
        material_ref: material || null,
        quantity,
        stock_ref: stock || null,
      })
      setWorkflowId(created.workflow_id)
      // Level-20: persist for reload recovery
      saveCurrentWorkflowId(created.workflow_id)

      const ran = await apiPost<WorkflowSummary>(`/api/workflow/${created.workflow_id}/run`)
      setSummary(ran as WorkflowSummary)

      const stageData = await apiGet<StageInfo[]>(`/api/workflow/${created.workflow_id}/stages`)
      setStages(stageData)

      try {
        const planData = await apiGet<PlanSummary>(`/api/workflow/${created.workflow_id}/plan`)
        setPlan(planData)
      } catch {
        // Plan may not be available (PARTIAL workflow)
      }

      // Refresh history after run
      loadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }, [fileRef, selectedFile, material, quantity, stock, objective, mode, loadHistory])

  // ---------------------------------------------------------------------------
  // Export handler
  // ---------------------------------------------------------------------------

  const handleExport = useCallback(async (format: WorkflowExportFormat) => {
    if (!workflowId) return
    setExportError(null)
    setExportingFormat(format)
    try {
      await downloadExport(workflowId, format)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err))
    } finally {
      setExportingFormat(null)
    }
  }, [workflowId])

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const stageMap = new Map(stages.map(s => [s.stage, s]))
  const totalStages = ALL_STAGES.length
  const passedStages = stages.filter(s => s.status === 'PASS').length
  const progressPct = totalStages > 0 ? Math.round((passedStages / totalStages) * 100) : 0
  const hasRun = stages.length > 0

  return (
    <div className="h-full overflow-y-auto">
      {/* Page header */}
      <div className="border-b border-tp-border bg-tp-bg px-6 py-4">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
          Level 19/20 — End-to-End Workflow
        </div>
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-tp-text">{t('wfPageTitle')}</h1>
          <button
            onClick={() => setShowHistory(h => !h)}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-tp-border text-tp-text-2 hover:bg-tp-border/50 transition-colors"
          >
            <History className="w-3.5 h-3.5" />
            Recent
          </button>
        </div>
      </div>

      {/* Level-20: History panel (collapsible) */}
      {showHistory && (
        <div className="border-b border-tp-border bg-tp-surface px-6 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">
              {t('wfRecentWorkflows')}
            </div>
            <button
              onClick={loadHistory}
              disabled={historyLoading}
              className="text-xs text-tp-text-3 hover:text-tp-text-2 disabled:opacity-40"
              title="Refresh history"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          {historyLoading && (
            <div className="text-xs text-tp-text-3 flex items-center gap-1">
              <Loader className="w-3 h-3 animate-spin" /> Loading…
            </div>
          )}
          {!historyLoading && history.length === 0 && (
            <div className="text-xs text-tp-text-3">{t('wfNoWorkflows')}</div>
          )}
          <ul className="space-y-1">
            {history.map(item => (
              <li key={item.workflow_id}>
                <button
                  onClick={() => { loadWorkflowById(item.workflow_id); setShowHistory(false) }}
                  className={`w-full text-left px-3 py-2 rounded border transition-colors text-xs ${
                    workflowId === item.workflow_id
                      ? 'border-tp-accent-light bg-tp-accent-light/10 text-tp-text'
                      : 'border-tp-border hover:bg-tp-border/40 text-tp-text-2'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">{item.part_reference}</span>
                    <span className={`font-semibold ${statusBadgeClass(item.status)}`}>
                      {item.status}
                    </span>
                  </div>
                  <div className="mt-0.5 text-tp-text-3 flex items-center gap-3">
                    <span>{formatHistoryDate(item.created_at)}</span>
                    {item.objective && <span>{item.objective}</span>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-col lg:flex-row h-full" style={{ minHeight: 0 }}>
        {/* ---------------------------------------------------------------- */}
        {/* LEFT: Stage progress panel */}
        {/* ---------------------------------------------------------------- */}
        <div className="w-full lg:w-56 shrink-0 border-r border-tp-border bg-tp-surface p-3 overflow-y-auto">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-3">
            {t('wfStages')}
          </div>

          {hasRun && (
            <div className="mb-3">
              <div className="flex justify-between text-xs text-tp-text-2 mb-1">
                <span>{t('wfProgress')}</span>
                <span>{passedStages}/{totalStages}</span>
              </div>
              <div className="h-1.5 bg-tp-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}

          <ul className="space-y-0.5">
            {ALL_STAGES.map(stageKey => {
              const info = stageMap.get(stageKey)
              const status: StageStatus = info?.status ?? 'NOT_STARTED'
              const isSelected = selectedStage?.stage === stageKey
              return (
                <li key={stageKey}>
                  <button
                    onClick={() => info && setSelectedStage(info)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left transition-colors ${
                      isSelected
                        ? 'bg-tp-border text-tp-text'
                        : 'text-tp-text-2 hover:bg-tp-border/50'
                    }`}
                  >
                    <StatusIcon status={status} />
                    <span className="truncate">{stageLabels[stageKey]}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* CENTER: Input panel + current stage detail */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* Input panel */}
          <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
            <h2 className="text-sm font-semibold text-tp-text mb-4">{t('wfAnalysisInput')}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfCadFile')}</label>
                <input
                  type="file"
                  accept=".dxf,.igs,.iges,.stp,.step"
                  onChange={handleFileSelect}
                  disabled={running}
                  className="w-full text-xs bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light file:mr-2 file:text-xs file:border-0 file:bg-tp-accent-light file:text-white file:px-2 file:py-0.5 file:rounded"
                />
                {uploadState === 'UPLOADING' && (
                  <div className="mt-1 flex items-center gap-1 text-xs text-blue-500">
                    <Loader className="w-3 h-3 animate-spin" />
                    {t('wfUploading')}
                  </div>
                )}
                {uploadState === 'UPLOADED' && (
                  <div className="mt-1 flex items-center gap-1 text-xs text-green-500">
                    <CheckCircle className="w-3 h-3" />
                    {selectedFile?.name}
                  </div>
                )}
                {uploadState === 'UPLOAD_FAILED' && (
                  <div className="mt-1 text-xs text-red-500">{uploadError}</div>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfMaterial')}</label>
                <input
                  type="text"
                  value={material}
                  onChange={e => setMaterial(e.target.value)}
                  placeholder="AL6061, SS316L…"
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text placeholder:text-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfQuantity')}</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={e => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfStockReference')}</label>
                <input
                  type="text"
                  value={stock}
                  onChange={e => setStock(e.target.value)}
                  placeholder="BAR-50MM, BILLET-100…"
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text placeholder:text-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfObjective')}</label>
                <select
                  value={objective}
                  onChange={e => setObjective(e.target.value as WorkflowObjective)}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                >
                  <option value="BALANCED">{t('wfObjectiveBalanced')}</option>
                  <option value="MINIMUM_CYCLE_TIME">{t('wfObjectiveMinCycleTime')}</option>
                  <option value="MINIMUM_COST">{t('wfObjectiveMinCost')}</option>
                  <option value="MAXIMUM_TOOL_LIFE">{t('wfObjectiveMaxToolLife')}</option>
                  <option value="MINIMUM_RISK">{t('wfObjectiveMinRisk')}</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">{t('wfAnalysisMode')}</label>
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value as WorkflowMode)}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                >
                  <option value="FULL_MANUFACTURING_PLAN">{t('wfModeFullPlan')}</option>
                  <option value="ANALYSIS_ONLY">{t('wfModeAnalysisOnly')}</option>
                  <option value="DFM_ONLY">{t('wfModeDfmOnly')}</option>
                  <option value="QUOTE_ONLY">{t('wfModeQuoteOnly')}</option>
                  <option value="MACHINE_SELECTION">{t('wfModeMachineSelection')}</option>
                  <option value="CAM_PLAN_ONLY">{t('wfModeCamPlanOnly')}</option>
                  <option value="CAM_AND_TOOLPATH">{t('wfModeCamAndToolpath')}</option>
                  <option value="OFFLINE_NC">{t('wfModeOfflineNc')}</option>
                </select>
              </div>
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                onClick={runWorkflow}
                disabled={running}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded bg-tp-accent-light text-white text-sm font-semibold transition-opacity disabled:opacity-50 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-tp-accent-light"
              >
                {running && <Loader className="w-4 h-4 animate-spin" />}
                {t('wfRunAnalysis')}
              </button>
              {workflowId && (
                <span className="text-xs text-tp-text-3 font-mono">{workflowId}</span>
              )}
            </div>

            {error && (
              <div className="mt-3 flex items-start gap-2 text-xs text-red-500 bg-red-50 dark:bg-red-950/20 p-3 rounded border border-red-200 dark:border-red-900">
                <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Stage detail */}
          {selectedStage && (
            <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <StatusIcon status={selectedStage.status} />
                <h2 className="text-sm font-semibold text-tp-text">
                  {stageLabels[selectedStage.stage] ?? selectedStage.stage}
                </h2>
                <span className={`ml-auto text-xs font-medium ${statusColor(selectedStage.status)}`}>
                  {selectedStage.status}
                </span>
              </div>
              {selectedStage.duration_ms != null && (
                <div className="text-xs text-tp-text-3 mb-2">{selectedStage.duration_ms.toFixed(0)} ms</div>
              )}
              {selectedStage.warnings.length > 0 && (
                <div className="mb-2">
                  <div className="text-xs font-medium text-yellow-600 mb-1">{t('wfWarnings')}</div>
                  <ul className="space-y-0.5">
                    {selectedStage.warnings.map((w, i) => (
                      <li key={i} className="text-xs text-tp-text-2 flex items-start gap-1">
                        <AlertTriangle className="w-3 h-3 shrink-0 text-yellow-500 mt-0.5" />
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedStage.errors.length > 0 && (
                <div className="mb-2">
                  <div className="text-xs font-medium text-red-500 mb-1">{t('wfErrors')}</div>
                  <ul className="space-y-0.5">
                    {selectedStage.errors.map((e, i) => (
                      <li key={i} className="text-xs text-red-500">{e}</li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedStage.blocking_reasons.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-red-500 mb-1">{t('wfBlockingReasons')}</div>
                  <ul className="space-y-0.5">
                    {selectedStage.blocking_reasons.map((r, i) => (
                      <li key={i} className="text-xs text-red-500">{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedStage.review_required && (
                <div className="mt-2 flex items-center gap-1.5 text-xs text-purple-500">
                  <Eye className="w-3.5 h-3.5" />
                  {t('wfEngineerReview')}
                </div>
              )}
            </div>
          )}

          {/* Final plan dashboard */}
          {plan && (
            <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-tp-text">{t('wfFinalPlan')}</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-yellow-100 dark:bg-yellow-950/30 text-yellow-700 dark:text-yellow-400 px-2 py-0.5 rounded font-medium">
                    {t('wfProposal')}
                  </span>
                </div>
              </div>

              {/* Safety badges */}
              <div className="flex flex-wrap gap-2 mb-4">
                {[
                  { label: t('wfProductionApproved'), value: plan.production_approved, safe: !plan.production_approved },
                  { label: t('wfDispatched'), value: plan.dispatched, safe: !plan.dispatched },
                  { label: t('wfMachineStarted'), value: plan.machine_started, safe: !plan.machine_started },
                ].map(({ label, value, safe }) => (
                  <div
                    key={label}
                    className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded border font-medium ${
                      safe
                        ? 'border-green-200 dark:border-green-900 text-green-600 dark:text-green-400'
                        : 'border-red-200 dark:border-red-900 text-red-500'
                    }`}
                  >
                    {safe ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    {label}: {value ? 'YES' : 'NO'}
                  </div>
                ))}
              </div>

              {/* Alternative plans */}
              {plan.alternative_plans.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs font-medium text-tp-text-2 mb-2">Alternative Plans</div>
                  <div className="space-y-2">
                    {plan.alternative_plans.map((ap, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 bg-tp-bg rounded border border-tp-border">
                        <ChevronRight className="w-3.5 h-3.5 text-tp-accent-light mt-0.5 shrink-0" />
                        <div>
                          <div className="text-xs font-medium text-tp-text">{ap.plan_type}</div>
                          <div className="text-xs text-tp-text-2">{ap.description}</div>
                          <div className="text-xs text-tp-text-3 mt-0.5">Evidence: {ap.evidence}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Level-20: Export buttons */}
              {workflowId && (
                <div className="mt-4 border-t border-tp-border pt-4">
                  <div className="text-xs font-medium text-tp-text-2 mb-2 flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" />
                    Export Results
                    <span className="text-tp-text-3 font-normal ml-1">— requires engineering review before production use</span>
                  </div>
                  {exportError && (
                    <div className="mb-2 text-xs text-red-500 flex items-center gap-1">
                      <XCircle className="w-3.5 h-3.5" />
                      {exportError}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {EXPORT_FORMATS.map(fmt => (
                      <button
                        key={fmt.id}
                        onClick={() => handleExport(fmt.id)}
                        disabled={exportingFormat !== null}
                        title={
                          isNcSafetyFormat(fmt.id)
                            ? 'OFFLINE CANDIDATE — NOT MACHINE APPROVED — NOT DISPATCHED'
                            : fmt.label
                        }
                        className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border transition-colors disabled:opacity-50 ${
                          isNcSafetyFormat(fmt.id)
                            ? 'border-orange-300 dark:border-orange-800 text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-950/20'
                            : 'border-tp-border text-tp-text-2 hover:bg-tp-border/50'
                        }`}
                      >
                        {exportingFormat === fmt.id
                          ? <Loader className="w-3 h-3 animate-spin" />
                          : <Download className="w-3 h-3" />
                        }
                        {fmt.label}
                        {isNcSafetyFormat(fmt.id) && (
                          <span className="text-orange-500 font-semibold">⚠</span>
                        )}
                      </button>
                    ))}
                  </div>
                  {/* NC export safety notice */}
                  <p className="mt-2 text-[10px] text-orange-500">
                    ⚠ NC Manifest: OFFLINE CANDIDATE only. NOT MACHINE APPROVED. NOT DISPATCHED.
                    No CNC transfer.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Export buttons also available for any completed workflow (no plan yet) */}
          {workflowId && !plan && hasRun && (
            <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
              <div className="text-xs font-medium text-tp-text-2 mb-2 flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5" />
                Export Partial Results
              </div>
              {exportError && (
                <div className="mb-2 text-xs text-red-500">{exportError}</div>
              )}
              <div className="flex flex-wrap gap-2">
                {EXPORT_FORMATS.filter(f => f.id !== 'plan.json').map(fmt => (
                  <button
                    key={fmt.id}
                    onClick={() => handleExport(fmt.id)}
                    disabled={exportingFormat !== null}
                    title={isNcSafetyFormat(fmt.id) ? 'OFFLINE CANDIDATE — NOT DISPATCHED' : fmt.label}
                    className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border transition-colors disabled:opacity-50 ${
                      isNcSafetyFormat(fmt.id)
                        ? 'border-orange-300 dark:border-orange-800 text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-950/20'
                        : 'border-tp-border text-tp-text-2 hover:bg-tp-border/50'
                    }`}
                  >
                    {exportingFormat === fmt.id
                      ? <Loader className="w-3 h-3 animate-spin" />
                      : <Download className="w-3 h-3" />
                    }
                    {fmt.label}
                    {isNcSafetyFormat(fmt.id) && <span className="text-orange-500">⚠</span>}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* RIGHT: Summary / warnings / blocking / unknowns / review */}
        {/* ---------------------------------------------------------------- */}
        <div className="w-full lg:w-72 shrink-0 border-l border-tp-border bg-tp-surface p-4 overflow-y-auto space-y-4">

          {/* Workflow status */}
          {summary && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
                Status
              </div>
              <div className="flex items-center gap-2 text-sm font-medium text-tp-text">
                <span className={`w-2 h-2 rounded-full shrink-0 ${
                  summary.status === 'COMPLETED' ? 'bg-green-500' :
                  summary.status === 'PARTIAL' ? 'bg-yellow-500' :
                  summary.status === 'FAILED' ? 'bg-red-500' :
                  'bg-tp-text-3'
                }`} />
                {summary.status}
              </div>
            </div>
          )}

          {/* Blocking issues */}
          {plan && plan.blocking_issues.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-red-500 mb-2 flex items-center gap-1">
                <XCircle className="w-3 h-3" />
                Blocking Issues ({plan.blocking_issues.length})
              </div>
              <ul className="space-y-2">
                {plan.blocking_issues.map((bi, i) => (
                  <li key={i} className="text-xs text-tp-text-2 p-2 bg-red-50 dark:bg-red-950/20 rounded border border-red-200 dark:border-red-900">
                    <div className="font-medium text-red-500">{bi.code}</div>
                    <div className="mt-0.5">{bi.description}</div>
                    <div className="mt-1 text-tp-text-3">→ {bi.required_action}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Known unknowns */}
          {plan && plan.known_unknowns.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-yellow-600 mb-2 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                Known Unknowns ({plan.known_unknowns.length})
              </div>
              <ul className="space-y-1.5">
                {plan.known_unknowns.map((ku, i) => (
                  <li key={i} className="text-xs text-tp-text-2 p-2 bg-yellow-50 dark:bg-yellow-950/20 rounded border border-yellow-200 dark:border-yellow-900">
                    <span className="font-medium text-yellow-700 dark:text-yellow-400">{ku.category}</span>
                    <span className="ml-1">{ku.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Review items */}
          {plan && plan.review_items.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-purple-500 mb-2 flex items-center gap-1">
                <Eye className="w-3 h-3" />
                Review Required ({plan.review_items.length})
              </div>
              <ul className="space-y-1.5">
                {plan.review_items.map((ri, i) => (
                  <li key={i} className="text-xs text-tp-text-2 p-2 bg-purple-50 dark:bg-purple-950/20 rounded border border-purple-200 dark:border-purple-900">
                    <span className="font-medium text-purple-500">{ri.category}</span>
                    {ri.mandatory && <span className="ml-1 text-purple-400">(mandatory)</span>}
                    <div className="mt-0.5">{ri.description}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Workflow warnings from stages */}
          {stages.some(s => s.warnings.length > 0) && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-yellow-600 mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Warnings
              </div>
              <ul className="space-y-1">
                {stages.flatMap(s =>
                  s.warnings.map((w, i) => (
                    <li key={`${s.stage}-${i}`} className="text-xs text-tp-text-2">
                      <span className="font-medium text-tp-text-3">{STAGE_LABELS[s.stage]}: </span>
                      {w}
                    </li>
                  ))
                )}
              </ul>
            </div>
          )}

          {/* Empty state */}
          {!hasRun && !running && (
            <div className="text-center py-8">
              <FileText className="w-8 h-8 text-tp-text-3 mx-auto mb-2" />
              <p className="text-xs text-tp-text-3">
                Configure inputs and run the manufacturing analysis to see results.
              </p>
              {history.length > 0 && (
                <button
                  onClick={() => setShowHistory(true)}
                  className="mt-2 text-xs text-tp-accent-light hover:underline"
                >
                  Open a recent workflow
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
