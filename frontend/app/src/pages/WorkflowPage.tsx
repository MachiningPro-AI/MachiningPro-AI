/**
 * Level-19 Manufacturing Workflow — One-Click Manufacturing Analysis.
 *
 * Provides a unified end-to-end manufacturing analysis workflow:
 * CAD → Geometry → Features → DFM → Process → Machine → Tool → Cutting Data
 * → Cycle Time → Cost/RFQ → CAM → Toolpath → Verification → NC → Scheduling
 * → Assignment → Adaptive AI → Digital Twin → Final Manufacturing Plan
 *
 * Safety constraints (enforced by backend — UI reflects, never bypasses):
 *   PRODUCTION_APPROVED=NO  — plan is proposal only, requires engineering review
 *   NO_AUTO_DISPATCH=YES    — no machine dispatch from this UI
 *   NO_CNC_WRITE=YES        — no machine writes
 */

import { useState, useCallback } from 'react'
import {
  CheckCircle, XCircle, AlertCircle, Clock, Loader,
  SkipForward, ChevronRight, FileText, AlertTriangle,
  Eye, Download
} from 'lucide-react'

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

const STAGE_LABELS: Record<string, string> = {
  '01_CAD_IMPORT': 'CAD Import',
  '02_GEOMETRY': 'Geometry',
  '03_FEATURE_RECOGNITION': 'Features',
  '04_DFM': 'DFM',
  '05_PROCESS_PLANNING': 'Process',
  '06_MACHINE_SELECTION': 'Machine',
  '07_TOOL_SELECTION': 'Tool',
  '08_CUTTING_DATA': 'Cutting Data',
  '09_CYCLE_TIME': 'Cycle Time',
  '10_COST_RFQ': 'Cost / RFQ',
  '11_CAM_PLANNING': 'CAM',
  '12_TOOLPATH': 'Toolpath',
  '13_VERIFICATION': 'Verification',
  '14_NC_CANDIDATE': 'NC',
  '15_SCHEDULING': 'Scheduling',
  '16_JOB_ASSIGNMENT': 'Assignment',
  '17_ADAPTIVE_INTELLIGENCE': 'Adaptive AI',
  '18_DIGITAL_TWIN': 'Digital Twin',
  '19_FINAL_MANUFACTURING_PLAN': 'Plan',
}

const ALL_STAGES = Object.keys(STAGE_LABELS)

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

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)
  return resp.json()
}

async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(path)
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)
  return resp.json()
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function WorkflowPage() {
  // Input state
  const [cadFile, setCadFile] = useState('')
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

  const runWorkflow = useCallback(async () => {
    setRunning(true)
    setError(null)
    setStages([])
    setPlan(null)
    setSelectedStage(null)

    try {
      // Create workflow
      const created = await apiPost<WorkflowSummary & { workflow_id: string }>('/api/workflow', {
        part_reference: cadFile || 'UNNAMED_PART',
        revision: 'REV-A',
        source_file_ref: cadFile || null,
        requested_mode: mode,
        objective,
        material_ref: material || null,
        quantity,
        stock_ref: stock || null,
      })
      setWorkflowId(created.workflow_id)

      // Run workflow
      const ran = await apiPost<WorkflowSummary>(`/api/workflow/${created.workflow_id}/run`)
      setSummary(ran as WorkflowSummary)

      // Fetch stage details
      const stageData = await apiGet<StageInfo[]>(`/api/workflow/${created.workflow_id}/stages`)
      setStages(stageData)

      // Try to fetch plan
      try {
        const planData = await apiGet<PlanSummary>(`/api/workflow/${created.workflow_id}/plan`)
        setPlan(planData)
      } catch {
        // Plan may not be available (PARTIAL workflow)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }, [cadFile, material, quantity, stock, objective, mode])

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
          Level 19 — End-to-End Workflow
        </div>
        <h1 className="text-lg font-semibold text-tp-text">Manufacturing Analysis</h1>
      </div>

      <div className="flex flex-col lg:flex-row h-full" style={{ minHeight: 0 }}>
        {/* ---------------------------------------------------------------- */}
        {/* LEFT: Stage progress panel */}
        {/* ---------------------------------------------------------------- */}
        <div className="w-full lg:w-56 shrink-0 border-r border-tp-border bg-tp-surface p-3 overflow-y-auto">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-3">
            Stages
          </div>

          {hasRun && (
            <div className="mb-3">
              <div className="flex justify-between text-xs text-tp-text-2 mb-1">
                <span>Progress</span>
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
                    <span className="truncate">{STAGE_LABELS[stageKey]}</span>
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
            <h2 className="text-sm font-semibold text-tp-text mb-4">Analysis Input</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">CAD File Path</label>
                <input
                  type="text"
                  value={cadFile}
                  onChange={e => setCadFile(e.target.value)}
                  placeholder="/path/to/part.dxf"
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text placeholder:text-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">Material</label>
                <input
                  type="text"
                  value={material}
                  onChange={e => setMaterial(e.target.value)}
                  placeholder="AL6061, SS316L…"
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text placeholder:text-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">Quantity</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={e => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">Stock Reference</label>
                <input
                  type="text"
                  value={stock}
                  onChange={e => setStock(e.target.value)}
                  placeholder="BAR-50MM, BILLET-100…"
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text placeholder:text-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">Objective</label>
                <select
                  value={objective}
                  onChange={e => setObjective(e.target.value as WorkflowObjective)}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                >
                  <option value="BALANCED">Balanced</option>
                  <option value="MINIMUM_CYCLE_TIME">Minimum Cycle Time</option>
                  <option value="MINIMUM_COST">Minimum Cost</option>
                  <option value="MAXIMUM_TOOL_LIFE">Maximum Tool Life</option>
                  <option value="MINIMUM_RISK">Minimum Risk</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-tp-text-2 mb-1">Analysis Mode</label>
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value as WorkflowMode)}
                  className="w-full text-sm bg-tp-bg border border-tp-border rounded px-3 py-2 text-tp-text focus:outline-none focus:ring-1 focus:ring-tp-accent-light"
                >
                  <option value="FULL_MANUFACTURING_PLAN">Full Manufacturing Plan</option>
                  <option value="ANALYSIS_ONLY">Analysis Only</option>
                  <option value="DFM_ONLY">DFM Only</option>
                  <option value="QUOTE_ONLY">Quote Only</option>
                  <option value="MACHINE_SELECTION">Machine Selection</option>
                  <option value="CAM_PLAN_ONLY">CAM Plan Only</option>
                  <option value="CAM_AND_TOOLPATH">CAM + Toolpath</option>
                  <option value="OFFLINE_NC">Offline NC</option>
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
                RUN MANUFACTURING ANALYSIS
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
                  {STAGE_LABELS[selectedStage.stage] ?? selectedStage.stage}
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
                  <div className="text-xs font-medium text-yellow-600 mb-1">Warnings</div>
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
                  <div className="text-xs font-medium text-red-500 mb-1">Errors</div>
                  <ul className="space-y-0.5">
                    {selectedStage.errors.map((e, i) => (
                      <li key={i} className="text-xs text-red-500">{e}</li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedStage.blocking_reasons.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-red-500 mb-1">Blocking Reasons</div>
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
                  Engineering review required
                </div>
              )}
            </div>
          )}

          {/* Final plan dashboard */}
          {plan && (
            <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-tp-text">Final Manufacturing Plan</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-yellow-100 dark:bg-yellow-950/30 text-yellow-700 dark:text-yellow-400 px-2 py-0.5 rounded font-medium">
                    PROPOSAL — Engineering Review Required
                  </span>
                </div>
              </div>

              {/* Safety badges */}
              <div className="flex flex-wrap gap-2 mb-4">
                {[
                  { label: 'Production Approved', value: plan.production_approved, safe: !plan.production_approved },
                  { label: 'Dispatched', value: plan.dispatched, safe: !plan.dispatched },
                  { label: 'Machine Started', value: plan.machine_started, safe: !plan.machine_started },
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

              {/* Export foundation button */}
              <button
                disabled
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-tp-border text-tp-text-2 opacity-50 cursor-not-allowed"
                title="Export requires engineering review and approval"
              >
                <Download className="w-3.5 h-3.5" />
                Export Plan (requires review)
              </button>
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
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
