/**
 * WorkspaceAutoCAM — 20-stage Auto CAM orchestration panel.
 *
 * Safety contract (displayed to user, hardcoded, cannot be overridden):
 *   AUTO_CAM_CAN_DISPATCH_CNC=NO
 *   AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
 *   AUTO_CAM_CAN_AUTO_APPROVE=NO
 *   REAL_MACHINE_WRITE_FOUND=NO
 *   DISPATCH_GATE=ALWAYS_BLOCKED
 *   SIMULATION_REQUIRED=YES
 *   CANDIDATE_ONLY=YES
 *   ENGINEER_REVIEW_REQUIRED=YES
 *
 * State machine: IDLE → RUNNING → REVIEW (or BLOCKED)
 * No G-code output. No dispatch controls. No production release.
 */

import { useState } from 'react'
import {
  Play, ShieldAlert, CheckCircle2, XCircle,
  AlertTriangle, Clock, Cpu, Wrench,
  ChevronDown, ChevronRight, Info,
  FileText, Shield,
} from 'lucide-react'
import { useLocale } from '../../i18n'

// ---------------------------------------------------------------------------
// Types (mirrors backend AutoCamPlan shape)
// ---------------------------------------------------------------------------

type StageStatus =
  | 'NOT_STARTED' | 'RUNNING' | 'PASS' | 'PARTIAL'
  | 'WARNING' | 'BLOCKED' | 'INSUFFICIENT_DATA'
  | 'NOT_VERIFIABLE' | 'NOT_PERFORMED' | 'FAILED'

interface StageResult {
  stage: string
  status: StageStatus
  duration_ms: number
  warnings: string[]
  blockers: string[]
  missing_inputs: string[]
  outputs: Record<string, unknown>
}

interface ToolResult {
  tool_id: string | null
  tool_type: string | null
  tool_diameter_mm: number | null
  tool_status: string
}

interface CuttingParamResult {
  vc_m_per_min: number | null
  rpm: number | null
  feed_mm_per_min: number | null
  fz_mm: number | null
  status: string
  provenance: string
}

interface CostCategoryItem {
  category: string
  value: number | null
  currency: string | null
  source_type: string
  source_name: string | null
  provenance: string
  status: string
  notes: string | null
  formula: string | null
}

interface AutoCamCostEstimate {
  material_cost: CostCategoryItem
  machine_cost: CostCategoryItem
  tool_cost: CostCategoryItem
  setup_cost: CostCategoryItem
  labor_cost: CostCategoryItem
  energy_cost: CostCategoryItem
  overhead_cost: CostCategoryItem
  other_cost: CostCategoryItem
  known_total: number | null
  unknown_component_count: number
  completeness_pct: number
  total_status: string
  currency: string | null
  computed_at: string
  cost_input_received: boolean
  warnings: string[]
}

interface OperationResult {
  operation_ref: string
  feature_id: string
  feature_type: string
  operation_type: string
  cam_strategy: string
  tool: ToolResult
  cutting_params: CuttingParamResult
  toolpath_status: string
  segment_count: number
  warnings: string[]
  missing_inputs: string[]
  simulation_required: boolean
}

interface MachineResult {
  machine_id: string | null
  manufacturer: string | null
  model: string | null
  machine_type_code: string | null
  status: string
}

interface CycleTimeResult {
  total_known_s: number | null
  status: string
}

interface VerificationSummaryResult {
  state: string
  stock_removal_fidelity: string
  collision_check: string
  gouge_check: string
  tool_reach_check: string
  machine_envelope_check: string
}

interface AutoCamBlocker {
  code: string
  stage: string
  message: string
}

interface AutoCamPlan {
  plan_id: string
  file_ref: string
  plan_status: string
  stages: StageResult[]
  operations: OperationResult[]
  machine: MachineResult
  cycle_time: CycleTimeResult
  verification: VerificationSummaryResult
  blockers: AutoCamBlocker[]
  warnings: Array<{ stage: string; message: string }>
  cost_estimate_status: string
  cost_estimate: AutoCamCostEstimate | null
  report_status: string
  created_at: string
  safety: Record<string, boolean | string>
}

export interface AutoCamFeatureInput {
  feature_id: string
  feature_type: string
  center_x?: number
  center_y?: number
  center_z_top?: number
  depth_mm?: number
  diameter_mm?: number
  width_mm?: number
  length_mm?: number
}

export interface AutoCamStockBbox {
  min_x: number; min_y: number; min_z: number
  max_x: number; max_y: number; max_z: number
}

export interface WorkspaceAutoCAMProps {
  token: string
  fileRef: string | null
  features: AutoCamFeatureInput[]
  stockBbox: AutoCamStockBbox | null
  materialGrade: string | null
}

// ---------------------------------------------------------------------------
// Stage label map (S01..S20)
// ---------------------------------------------------------------------------

const STAGE_SHORT: Record<string, string> = {
  S01_INPUT_VALIDATION:    'S01',
  S02_STOCK_GATE:          'S02',
  S03_FEATURE_CLASSIFY:    'S03',
  S04_MACHINE_SELECTION:   'S04',
  S05_FEASIBILITY:         'S05',
  S06_TOOL_SELECTION:      'S06',
  S07_OP_PLANNING:         'S07',
  S08_CUTTING_PARAMS:      'S08',
  S09_TOOLPATH_GEN:        'S09',
  S10_TOOLPATH_VALIDATION: 'S10',
  S11_STOCK_REMOVAL_SIM:   'S11',
  S12_GOUGE_CHECK:         'S12',
  S13_COLLISION_CHECK:     'S13',
  S14_CYCLE_TIME:          'S14',
  S15_TOOL_REACH:          'S15',
  S16_MACHINE_ENVELOPE:    'S16',
  S17_COST_ESTIMATE:       'S17',
  S18_REPORT_GEN:          'S18',
  S19_DISPATCH_SAFETY_GATE:'S19',
  S20_REPORT:              'S20',
}

const STAGE_LABEL_KEY: Record<string, `autocam_stage_${'S01'|'S02'|'S03'|'S04'|'S05'|'S06'|'S07'|'S08'|'S09'|'S10'|'S11'|'S12'|'S13'|'S14'|'S15'|'S16'|'S17'|'S18'|'S19'|'S20'}`> = {
  S01_INPUT_VALIDATION:    'autocam_stage_S01',
  S02_STOCK_GATE:          'autocam_stage_S02',
  S03_FEATURE_CLASSIFY:    'autocam_stage_S03',
  S04_MACHINE_SELECTION:   'autocam_stage_S04',
  S05_FEASIBILITY:         'autocam_stage_S05',
  S06_TOOL_SELECTION:      'autocam_stage_S06',
  S07_OP_PLANNING:         'autocam_stage_S07',
  S08_CUTTING_PARAMS:      'autocam_stage_S08',
  S09_TOOLPATH_GEN:        'autocam_stage_S09',
  S10_TOOLPATH_VALIDATION: 'autocam_stage_S10',
  S11_STOCK_REMOVAL_SIM:   'autocam_stage_S11',
  S12_GOUGE_CHECK:         'autocam_stage_S12',
  S13_COLLISION_CHECK:     'autocam_stage_S13',
  S14_CYCLE_TIME:          'autocam_stage_S14',
  S15_TOOL_REACH:          'autocam_stage_S15',
  S16_MACHINE_ENVELOPE:    'autocam_stage_S16',
  S17_COST_ESTIMATE:       'autocam_stage_S17',
  S18_REPORT_GEN:          'autocam_stage_S18',
  S19_DISPATCH_SAFETY_GATE:'autocam_stage_S19',
  S20_REPORT:              'autocam_stage_S20',
}

// ---------------------------------------------------------------------------
// Status badge helpers
// ---------------------------------------------------------------------------

function statusColor(s: StageStatus | string): string {
  switch (s) {
    case 'PASS':              return 'text-green-400'
    case 'PARTIAL':           return 'text-yellow-400'
    case 'WARNING':           return 'text-yellow-400'
    case 'BLOCKED':           return 'text-red-400'
    case 'FAILED':            return 'text-red-400'
    case 'INSUFFICIENT_DATA': return 'text-orange-400'
    case 'NOT_VERIFIABLE':    return 'text-blue-400'
    case 'NOT_PERFORMED':     return 'text-tp-text-3'
    case 'RUNNING':           return 'text-tp-accent-light animate-pulse'
    default:                  return 'text-tp-text-3'
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'PASS')           return <CheckCircle2 size={12} className="text-green-400 shrink-0" />
  if (status === 'WARNING' || status === 'PARTIAL' || status === 'INSUFFICIENT_DATA')
                                   return <AlertTriangle size={12} className="text-yellow-400 shrink-0" />
  if (status === 'BLOCKED' || status === 'FAILED')
                                   return <XCircle size={12} className="text-red-400 shrink-0" />
  if (status === 'NOT_VERIFIABLE') return <Info size={12} className="text-blue-400 shrink-0" />
  return <span className="w-3 h-3 rounded-full bg-tp-surface-3 shrink-0 inline-block" />
}

// ---------------------------------------------------------------------------
// Pre-run summary panel (MUST 32)
// ---------------------------------------------------------------------------

function PreRunSummary({
  fileRef, features, stockBbox, materialGrade,
}: {
  fileRef: string | null
  features: AutoCamFeatureInput[]
  stockBbox: AutoCamStockBbox | null
  materialGrade: string | null
}) {
  const { t } = useLocale()
  const stockLabel = stockBbox
    ? `${(stockBbox.max_x - stockBbox.min_x).toFixed(0)} × ${(stockBbox.max_y - stockBbox.min_y).toFixed(0)} × ${(stockBbox.max_z - stockBbox.min_z).toFixed(0)} mm`
    : '—'

  return (
    <div className="bg-tp-surface-2 border border-tp-border rounded p-3 text-[11px] space-y-1">
      <Row label={t('autocam_fileRef')}      value={fileRef ?? '—'} />
      <Row label={t('autocam_materialGrade')} value={materialGrade ?? '—'} />
      <Row label={t('autocam_featureCount')} value={String(features.length)} />
      <Row label={t('autocam_stockDims')}    value={stockLabel} />
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-tp-text-3 w-24 shrink-0">{label}</span>
      <span className="text-tp-text truncate">{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 20-stage progress tracker (MUST 33)
// ---------------------------------------------------------------------------

function StageTracker({ stages }: { stages: StageResult[] }) {
  const { t } = useLocale()
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div className="space-y-0.5">
      {stages.map((s) => {
        const short = STAGE_SHORT[s.stage] ?? s.stage.slice(0, 3)
        const labelKey = STAGE_LABEL_KEY[s.stage]
        const label = labelKey ? t(labelKey) : s.stage
        const isOpen = expanded === s.stage
        const hasDetail = s.warnings.length > 0 || s.blockers.length > 0 || s.missing_inputs.length > 0

        return (
          <div key={s.stage} className="text-[10px]">
            <button
              type="button"
              className="w-full flex items-center gap-1.5 px-2 py-0.5 hover:bg-tp-surface-2 rounded transition-colors"
              onClick={() => hasDetail ? setExpanded(isOpen ? null : s.stage) : undefined}
            >
              <span className="text-tp-text-3 w-6 shrink-0 font-mono">{short}</span>
              <StatusIcon status={s.status} />
              <span className="flex-1 text-left truncate">{label}</span>
              <span className={`${statusColor(s.status)} font-mono`}>{s.status}</span>
              {hasDetail && (
                isOpen ? <ChevronDown size={10} className="text-tp-text-3 shrink-0" />
                        : <ChevronRight size={10} className="text-tp-text-3 shrink-0" />
              )}
            </button>
            {isOpen && (
              <div className="ml-8 mr-2 mb-1 space-y-0.5 bg-tp-surface-2 rounded p-1.5">
                {s.blockers.map((b, i) => (
                  <p key={i} className="text-red-400">⊗ {b}</p>
                ))}
                {s.warnings.map((w, i) => (
                  <p key={i} className="text-yellow-400">⚠ {w}</p>
                ))}
                {s.missing_inputs.map((m, i) => (
                  <p key={i} className="text-orange-400">? {m}</p>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Operations table (MUST 34 — review screen)
// ---------------------------------------------------------------------------

function OperationsTable({ operations }: { operations: OperationResult[] }) {
  const { t } = useLocale()
  if (operations.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px]">
        <thead>
          <tr className="text-tp-text-3 border-b border-tp-border">
            <th className="text-left pb-1 pr-2 font-normal">{t('autocam_opType')}</th>
            <th className="text-left pb-1 pr-2 font-normal">{t('autocam_strategy')}</th>
            <th className="text-left pb-1 pr-2 font-normal">{t('autocam_toolDiam')}</th>
            <th className="text-left pb-1 pr-2 font-normal">{t('autocam_segCount')}</th>
            <th className="text-left pb-1 font-normal">{t('autocam_cuttingParams')}</th>
          </tr>
        </thead>
        <tbody>
          {operations.map((op) => (
            <tr key={op.operation_ref} className="border-b border-tp-border/40 hover:bg-tp-surface-2">
              <td className="py-0.5 pr-2">
                <span className={`${statusColor(op.toolpath_status)} mr-1`}>•</span>
                {op.operation_type}
              </td>
              <td className="py-0.5 pr-2 text-tp-text-3">{op.cam_strategy}</td>
              <td className="py-0.5 pr-2">
                {op.tool.tool_diameter_mm != null ? `${op.tool.tool_diameter_mm} mm` : t('autocam_notAvailable')}
              </td>
              <td className="py-0.5 pr-2 text-tp-text-3">{op.segment_count}</td>
              <td className="py-0.5 text-tp-text-3">{op.cutting_params.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Safety invariants display (MUST 35)
// ---------------------------------------------------------------------------

function SafetyInvariantsPanel({ safety: _safety }: { safety: Record<string, boolean | string> }) {
  const { t } = useLocale()
  const LOCKED_FALSE = [
    'AUTO_CAM_CAN_DISPATCH_CNC',
    'AUTO_CAM_CAN_RELEASE_PRODUCTION',
    'AUTO_CAM_CAN_AUTO_APPROVE',
    'REAL_MACHINE_WRITE_FOUND',
  ]

  return (
    <div className="bg-red-950/30 border border-red-900/40 rounded p-2 space-y-1">
      <div className="flex items-center gap-1.5 mb-1.5">
        <ShieldAlert size={12} className="text-red-400 shrink-0" />
        <span className="text-[10px] text-red-400 font-semibold uppercase tracking-wider">
          {t('autocam_safetyTitle')}
        </span>
      </div>
      {LOCKED_FALSE.map((k) => (
        <div key={k} className="flex items-center gap-1.5 text-[10px]">
          <XCircle size={10} className="text-red-400 shrink-0" />
          <span className="text-tp-text-3 font-mono">{k}=</span>
          <span className="text-red-400 font-mono font-semibold">FALSE</span>
          <span className="text-tp-text-3">(locked)</span>
        </div>
      ))}
      <div className="flex items-center gap-1.5 text-[10px] mt-1">
        <XCircle size={10} className="text-red-400 shrink-0" />
        <span className="text-tp-text-3 font-mono">DISPATCH_GATE=</span>
        <span className="text-red-400 font-mono font-semibold">ALWAYS_BLOCKED</span>
      </div>
      <div className="mt-1.5 pt-1.5 border-t border-red-900/30 space-y-0.5">
        <p className="text-[10px] text-yellow-400">⚠ {t('autocam_candidateOnly')}</p>
        <p className="text-[10px] text-yellow-400">⚠ {t('autocam_engineerReviewRequired')}</p>
        <p className="text-[10px] text-yellow-400">⚠ {t('autocam_simulationRequired')}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Machine + cycle time summary
// ---------------------------------------------------------------------------

function MachinePanel({ machine, cycleTime }: { machine: MachineResult; cycleTime: CycleTimeResult }) {
  const { t } = useLocale()
  return (
    <div className="bg-tp-surface-2 border border-tp-border rounded p-2 text-[10px] space-y-0.5">
      <div className="flex items-center gap-1 mb-1 text-tp-text-2 font-medium">
        <Cpu size={11} />
        <span>{t('autocam_machineTitle')}</span>
      </div>
      {machine.manufacturer && machine.model ? (
        <>
          <Row label="ID" value={machine.machine_id ?? '—'} />
          <Row label="Make" value={machine.manufacturer} />
          <Row label="Model" value={machine.model} />
          <Row label="Type" value={machine.machine_type_code ?? '—'} />
        </>
      ) : (
        <p className="text-tp-text-3">{machine.status}</p>
      )}
      <div className="mt-1.5 pt-1.5 border-t border-tp-border flex items-center gap-1 text-tp-text-2 font-medium">
        <Clock size={11} />
        <span>{t('autocam_cycleTimeTitle')}</span>
      </div>
      {cycleTime.total_known_s != null
        ? <Row label="Total" value={`${cycleTime.total_known_s.toFixed(1)} s`} />
        : <p className="text-tp-text-3">{cycleTime.status}</p>
      }
    </div>
  )
}

// ---------------------------------------------------------------------------
// Verification summary
// ---------------------------------------------------------------------------

function VerificationPanel({ v }: { v: VerificationSummaryResult }) {
  const { t } = useLocale()
  return (
    <div className="bg-tp-surface-2 border border-tp-border rounded p-2 text-[10px] space-y-0.5">
      <div className="flex items-center gap-1 mb-1 text-tp-text-2 font-medium">
        <Wrench size={11} />
        <span>{t('autocam_verificationTitle')}</span>
      </div>
      {[
        ['Stock removal',  v.stock_removal_fidelity],
        ['Gouge',          v.gouge_check],
        ['Collision',      v.collision_check],
        ['Tool reach',     v.tool_reach_check],
        ['Machine env.',   v.machine_envelope_check],
      ].map(([label, val]) => (
        <div key={label} className="flex items-center gap-1.5">
          <StatusIcon status={val} />
          <span className="text-tp-text-3 w-20 shrink-0">{label}</span>
          <span className={statusColor(val)}>{val}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Cost panel
// ---------------------------------------------------------------------------

interface CostFormState {
  machine_hourly_rate: string
  machine_rate_currency: string
  material_cost_total: string
  tool_cost_total: string
  setup_cost_total: string
  labor_hours: string
  labor_rate: string
  overhead_pct: string
  quantity: string
  currency: string
}

const _EMPTY_COST_FORM: CostFormState = {
  machine_hourly_rate: '', machine_rate_currency: '', material_cost_total: '',
  tool_cost_total: '', setup_cost_total: '', labor_hours: '', labor_rate: '',
  overhead_pct: '', quantity: '', currency: '',
}

function CostPanel({
  planId, estimate, token, onUpdated,
}: {
  planId: string
  estimate: AutoCamCostEstimate | null
  token: string
  onUpdated: (plan: AutoCamPlan) => void
}) {
  const { t } = useLocale()
  const [form, setForm] = useState<CostFormState>(_EMPTY_COST_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [showForm, setShowForm] = useState(!estimate?.cost_input_received)

  function fNum(v: string): number | null {
    const n = parseFloat(v)
    return isNaN(n) ? null : n
  }
  function fInt(v: string): number | null {
    const n = parseInt(v, 10)
    return isNaN(n) ? null : n
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setMsg(null)
    const payload = {
      machine_hourly_rate: fNum(form.machine_hourly_rate),
      machine_rate_currency: form.machine_rate_currency || null,
      material_cost_total: fNum(form.material_cost_total),
      material_cost_currency: form.currency || null,
      tool_cost_total: fNum(form.tool_cost_total),
      tool_cost_currency: form.currency || null,
      setup_cost_total: fNum(form.setup_cost_total),
      setup_cost_currency: form.currency || null,
      labor_hours: fNum(form.labor_hours),
      labor_rate: fNum(form.labor_rate),
      labor_rate_currency: form.currency || null,
      overhead_pct: fNum(form.overhead_pct),
      quantity: fInt(form.quantity),
      currency: form.currency || null,
    }
    try {
      const resp = await fetch(`/api/autocam/${planId}/cost-input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const updated: AutoCamPlan = await resp.json()
      onUpdated(updated)
      setMsg({ ok: true, text: t('autocam_costInputSuccess') })
      setShowForm(false)
    } catch {
      setMsg({ ok: false, text: t('autocam_costInputError') })
    } finally {
      setSubmitting(false)
    }
  }

  const inp = 'w-full bg-tp-surface-3 border border-tp-border rounded px-2 py-0.5 text-[10px] text-tp-text focus:outline-none focus:border-tp-accent/60'
  const lbl = 'text-[9px] text-tp-text-3 mb-0.5'

  const totalStatus = estimate?.total_status ?? 'NOT_PROVIDED'
  const statusCls =
    totalStatus === 'COMPLETE_COST_ESTIMATE' ? 'text-green-400' :
    totalStatus === 'PARTIAL_COST_ESTIMATE' ? 'text-yellow-400' :
    'text-tp-text-3'

  const cats = estimate ? [
    estimate.material_cost, estimate.machine_cost, estimate.tool_cost,
    estimate.setup_cost, estimate.labor_cost, estimate.energy_cost,
    estimate.overhead_cost, estimate.other_cost,
  ] : []

  return (
    <div className="bg-tp-surface-2 border border-tp-border rounded p-2 text-[10px] space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-tp-text-2 font-medium">
          <FileText size={11} />
          <span>{t('autocam_costTitle')}</span>
        </div>
        <span className={`font-mono font-semibold ${statusCls}`}>{totalStatus}</span>
      </div>

      {/* Summary row when estimate exists */}
      {estimate?.cost_input_received && (
        <>
          <div className="flex gap-3 text-[9px] text-tp-text-3">
            <span>{t('autocam_costKnownTotal')}: <span className="text-tp-text font-mono">{estimate.known_total != null ? `${estimate.known_total.toFixed(2)} ${estimate.currency ?? ''}` : 'N/A'}</span></span>
            <span>{t('autocam_costCompleteness')}: <span className="text-tp-text">{estimate.completeness_pct}%</span></span>
            <span>{t('autocam_costUnknownComponents')}: <span className="text-tp-text">{estimate.unknown_component_count}</span></span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[9px] border-collapse">
              <thead>
                <tr className="text-tp-text-3 border-b border-tp-border">
                  <th className="text-left py-0.5 pr-2">{t('autocam_costCategory')}</th>
                  <th className="text-right py-0.5 pr-2">{t('autocam_costValue')}</th>
                  <th className="text-left py-0.5 pr-2">{t('autocam_costCurrency')}</th>
                  <th className="text-left py-0.5">{t('autocam_costStatus')}</th>
                </tr>
              </thead>
              <tbody>
                {cats.map(cat => (
                  <tr key={cat.category} className="border-b border-tp-border/40">
                    <td className="py-0.5 pr-2 text-tp-text-3">{cat.category}</td>
                    <td className="py-0.5 pr-2 text-right font-mono text-tp-text">{cat.value != null ? cat.value.toFixed(2) : '—'}</td>
                    <td className="py-0.5 pr-2 text-tp-text-3">{cat.currency ?? '—'}</td>
                    <td className={`py-0.5 ${cat.status === 'NOT_PROVIDED' ? 'text-tp-text-3' : cat.value != null ? 'text-green-400' : 'text-yellow-400'}`}>{cat.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[9px] text-orange-400/80 italic">{t('autocam_costAdvisoryWarning')}</p>
        </>
      )}

      {!estimate?.cost_input_received && !showForm && (
        <p className="text-tp-text-3">{t('autocam_costNotProvided')}</p>
      )}

      {/* Toggle form */}
      <button
        type="button"
        onClick={() => setShowForm(v => !v)}
        className="text-[9px] text-tp-accent-light hover:underline"
      >
        {showForm ? '▲ Hide form' : '▼ ' + t('autocam_costInputSubmit')}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-1.5 mt-1">
          <div className="grid grid-cols-2 gap-1.5">
            <div>
              <p className={lbl}>{t('autocam_costInputCurrency')}</p>
              <input className={inp} value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))} placeholder="EUR" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputQuantity')}</p>
              <input className={inp} type="number" min="1" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} placeholder="1" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputMachineRate')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.machine_hourly_rate} onChange={e => setForm(f => ({ ...f, machine_hourly_rate: e.target.value }))} placeholder="85.00" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputMaterialTotal')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.material_cost_total} onChange={e => setForm(f => ({ ...f, material_cost_total: e.target.value }))} placeholder="0.00" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputToolTotal')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.tool_cost_total} onChange={e => setForm(f => ({ ...f, tool_cost_total: e.target.value }))} placeholder="0.00" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputSetupTotal')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.setup_cost_total} onChange={e => setForm(f => ({ ...f, setup_cost_total: e.target.value }))} placeholder="0.00" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputLaborHours')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.labor_hours} onChange={e => setForm(f => ({ ...f, labor_hours: e.target.value }))} placeholder="0.5" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputLaborRate')}</p>
              <input className={inp} type="number" min="0" step="0.01" value={form.labor_rate} onChange={e => setForm(f => ({ ...f, labor_rate: e.target.value }))} placeholder="0.00" />
            </div>
            <div>
              <p className={lbl}>{t('autocam_costInputOverheadPct')}</p>
              <input className={inp} type="number" min="0" max="200" step="0.1" value={form.overhead_pct} onChange={e => setForm(f => ({ ...f, overhead_pct: e.target.value }))} placeholder="10" />
            </div>
          </div>
          {msg && (
            <p className={`text-[9px] ${msg.ok ? 'text-green-400' : 'text-red-400'}`}>{msg.text}</p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-1.5 rounded text-[10px] font-semibold bg-tp-accent/20 text-tp-accent-light border border-tp-accent/40 hover:bg-tp-accent/30 transition-colors disabled:opacity-40"
          >
            {submitting ? t('autocam_costInputSubmitting') : t('autocam_costInputSubmit')}
          </button>
        </form>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Report panel
// ---------------------------------------------------------------------------

function ReportPanel({ planId, token }: { planId: string; token: string }) {
  const { t } = useLocale()
  const [downloading, setDownloading] = useState<string | null>(null)

  async function handleDownload(fmt: string) {
    setDownloading(fmt)
    try {
      const resp = await fetch(`/api/autocam/${planId}/report/${fmt}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const blob = await resp.blob()
      const cd = resp.headers.get('Content-Disposition') ?? ''
      const fnMatch = cd.match(/filename="([^"]+)"/)
      const filename = fnMatch?.[1] ?? `autocam_report.${fmt.toLowerCase()}`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    } catch {
      // silent — network errors show no toast in this minimal panel
    } finally {
      setDownloading(null)
    }
  }

  const formats = [
    { key: 'JSON', label: t('autocam_reportFormatJson') },
    { key: 'CSV',  label: t('autocam_reportFormatCsv') },
    { key: 'PDF',  label: t('autocam_reportFormatPdf') },
    { key: 'XLSX', label: t('autocam_reportFormatXlsx') },
    { key: 'ZIP',  label: t('autocam_reportFormatZip') },
  ]

  return (
    <div className="bg-tp-surface-2 border border-tp-border rounded p-2 text-[10px]">
      <div className="flex items-center gap-1 mb-2 text-tp-text-2 font-medium">
        <FileText size={11} />
        <span>{t('autocam_reportTitle')}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {formats.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            disabled={downloading === key}
            onClick={() => handleDownload(key)}
            className="px-2 py-1 rounded text-[9px] font-semibold bg-tp-surface-3 text-tp-text-2 border border-tp-border hover:bg-tp-surface-3/80 hover:text-tp-text transition-colors disabled:opacity-40"
          >
            {downloading === key ? t('autocam_reportGenerating') : `↓ ${label}`}
          </button>
        ))}
      </div>
      <p className="mt-1.5 text-[9px] text-tp-text-3 italic">{t('autocam_reportSafetyNote')}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Plan status badge
// ---------------------------------------------------------------------------

function PlanStatusBadge({ status }: { status: string }) {
  const { t } = useLocale()
  let cls = 'text-tp-text-3 bg-tp-surface-2'
  if (status === 'COMPLETE')               cls = 'text-green-400 bg-green-950/30 border-green-900/40'
  else if (status === 'COMPLETE_WITH_WARNINGS') cls = 'text-yellow-400 bg-yellow-950/30 border-yellow-900/40'
  else if (status === 'BLOCKED')           cls = 'text-red-400 bg-red-950/30 border-red-900/40'
  else if (status === 'FAILED')            cls = 'text-red-400 bg-red-950/30 border-red-900/40'

  const label = status === 'BLOCKED' ? t('autocam_blockedLabel')
    : status.includes('WARNING') ? t('autocam_warningLabel')
    : status === 'COMPLETE' ? t('autocam_passLabel')
    : status

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-1.5 mt-3 mb-1 text-[10px] text-tp-text-2 font-semibold uppercase tracking-wider border-b border-tp-border pb-0.5">
      {icon}
      <span>{label}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main WorkspaceAutoCAM component
// ---------------------------------------------------------------------------

type PanelState = 'IDLE' | 'RUNNING' | 'REVIEW'

export default function WorkspaceAutoCAM({
  token, fileRef, features, stockBbox, materialGrade,
}: WorkspaceAutoCAMProps) {
  const { t } = useLocale()
  const [state, setState]   = useState<PanelState>('IDLE')
  const [plan, setPlan]     = useState<AutoCamPlan | null>(null)
  const [error, setError]   = useState<string | null>(null)

  const canRun = !!fileRef && features.length > 0

  async function handleRun() {
    if (!canRun) return
    setState('RUNNING')
    setError(null)
    setPlan(null)

    try {
      const body = {
        file_ref: fileRef,
        features,
        stock_bbox: stockBbox,
        material_grade: materialGrade,
        is_dispatchable: false,
        production_released: false,
      }
      const resp = await fetch('/api/autocam/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err?.detail?.message ?? `HTTP ${resp.status}`)
      }
      const data: AutoCamPlan = await resp.json()
      setPlan(data)
      setState('REVIEW')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
      setState('IDLE')
    }
  }

  // ── IDLE state ──────────────────────────────────────────────────────────
  if (state === 'IDLE') {
    return (
      <div className="flex flex-col h-full overflow-y-auto p-3 gap-3">
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-tp-accent-light shrink-0" />
          <span className="text-[12px] font-semibold text-tp-text">{t('autocam_title')}</span>
        </div>

        <PreRunSummary
          fileRef={fileRef}
          features={features}
          stockBbox={stockBbox}
          materialGrade={materialGrade}
        />

        {!canRun && (
          <p className="text-[10px] text-orange-400">{t('autocam_noFeaturesHint')}</p>
        )}

        {error && (
          <p className="text-[10px] text-red-400">⊗ {error}</p>
        )}

        <SafetyInvariantsPanel safety={{
          AUTO_CAM_CAN_DISPATCH_CNC: false,
          AUTO_CAM_CAN_RELEASE_PRODUCTION: false,
          AUTO_CAM_CAN_AUTO_APPROVE: false,
          REAL_MACHINE_WRITE_FOUND: false,
          DISPATCH_GATE: 'ALWAYS_BLOCKED',
        }} />

        <button
          type="button"
          disabled={!canRun}
          onClick={handleRun}
          className="flex items-center justify-center gap-2 w-full py-2 rounded text-[11px] font-semibold
                     bg-tp-accent/20 text-tp-accent-light border border-tp-accent/40
                     hover:bg-tp-accent/30 transition-colors
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Play size={13} />
          {t('autocam_runBtn')}
        </button>
      </div>
    )
  }

  // ── RUNNING state ────────────────────────────────────────────────────────
  if (state === 'RUNNING') {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-3 p-6">
        <Cpu size={28} className="text-tp-accent-light animate-pulse" />
        <p className="text-[12px] text-tp-text">{t('autocam_running')}</p>
        <div className="w-full max-w-xs space-y-1">
          {Array.from({ length: 20 }, (_, i) => (
            <div key={i} className="h-1 rounded bg-tp-surface-2 overflow-hidden">
              <div
                className="h-full bg-tp-accent/30 animate-pulse rounded"
                style={{ width: `${Math.min(100, (i + 1) * 5)}%`, animationDelay: `${i * 80}ms` }}
              />
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── REVIEW state ─────────────────────────────────────────────────────────
  if (!plan) return null

  return (
    <div className="flex flex-col h-full overflow-y-auto p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Shield size={14} className="text-tp-accent-light shrink-0" />
          <span className="text-[12px] font-semibold text-tp-text">{t('autocam_reviewTitle')}</span>
        </div>
        <button
          type="button"
          onClick={() => setState('IDLE')}
          className="text-[10px] text-tp-text-3 hover:text-tp-text transition-colors px-2 py-0.5
                     border border-tp-border/50 rounded hover:border-tp-border"
        >
          ← Back
        </button>
      </div>

      {/* Plan status */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] text-tp-text-3">{t('autocam_planStatus')}</span>
        <PlanStatusBadge status={plan.plan_status} />
      </div>

      {/* Blockers */}
      {plan.blockers.length > 0 && (
        <div className="bg-red-950/30 border border-red-900/40 rounded p-2 mb-2 space-y-0.5">
          {plan.blockers.map((b, i) => (
            <p key={i} className="text-[10px] text-red-400">⊗ {b.message}</p>
          ))}
        </div>
      )}

      {/* Meta */}
      <div className="text-[10px] text-tp-text-3 mb-2 flex gap-3">
        <span>{t('autocam_planId')}: <span className="font-mono text-tp-text">{plan.plan_id}</span></span>
        <span>{t('autocam_createdAt')}: <span className="text-tp-text">{plan.created_at.slice(0, 19).replace('T', ' ')}</span></span>
      </div>

      {/* Safety invariants */}
      <SafetyInvariantsPanel safety={plan.safety} />

      {/* Stage tracker */}
      <SectionHeader
        icon={<CheckCircle2 size={11} />}
        label={t('autocam_stagesTitle')}
      />
      <StageTracker stages={plan.stages} />

      {/* Operations */}
      {plan.operations.length > 0 && (
        <>
          <SectionHeader
            icon={<Wrench size={11} />}
            label={t('autocam_operationsTitle')}
          />
          <OperationsTable operations={plan.operations} />
        </>
      )}

      {/* Machine + verification */}
      <SectionHeader
        icon={<Cpu size={11} />}
        label={t('autocam_machineTitle')}
      />
      <MachinePanel machine={plan.machine} cycleTime={plan.cycle_time} />

      <SectionHeader
        icon={<AlertTriangle size={11} />}
        label={t('autocam_verificationTitle')}
      />
      <VerificationPanel v={plan.verification} />

      {/* Cost Analysis */}
      <SectionHeader
        icon={<FileText size={11} />}
        label={t('autocam_costTitle')}
      />
      <CostPanel
        planId={plan.plan_id}
        estimate={plan.cost_estimate}
        token={token}
        onUpdated={setPlan}
      />

      {/* Report Download */}
      <SectionHeader
        icon={<FileText size={11} />}
        label={t('autocam_reportTitle')}
      />
      <ReportPanel planId={plan.plan_id} token={token} />

      {/* Run again */}
      <button
        type="button"
        onClick={handleRun}
        className="mt-4 flex items-center justify-center gap-2 w-full py-2 rounded text-[11px]
                   font-semibold bg-tp-surface-2 text-tp-text-2 border border-tp-border
                   hover:bg-tp-surface-3 transition-colors"
      >
        <Play size={13} />
        {t('autocam_runBtn')}
      </button>
    </div>
  )
}
