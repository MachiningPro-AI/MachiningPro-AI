/**
 * WorkspaceCamPanel — bottom panel: CAM operations, toolpath summary,
 * simulation state, and verification display.
 *
 * Safety contract:
 *   SIMULATION_STATE=NOT_PERFORMED — no fabricated sim results shown
 *   VERIFICATION_STATE=NOT_PERFORMED — all checks NOT_PERFORMED
 *   NO_TOOLPATH_FABRICATION=YES — only shows real toolpath data from API
 *   NO_DISPATCH_CONTROLS=YES — no machine dispatch UI
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react'
import { useLocale } from '../../i18n'
import { SAFETY } from './WorkspaceTypes'
import type { ConnectedWorkflow, OperationSummary } from './WorkspaceTypes'

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type CamTab = 'operations' | 'toolpaths' | 'simulation' | 'verification'

const TABS: Array<{ id: CamTab; labelKey: string }> = [
  { id: 'operations',   labelKey: 'ws_camOperations' },
  { id: 'toolpaths',    labelKey: 'ws_camToolpaths' },
  { id: 'simulation',   labelKey: 'ws_camSimulation' },
  { id: 'verification', labelKey: 'ws_verification' },
]

// ---------------------------------------------------------------------------
// Operations tab
// ---------------------------------------------------------------------------

function OperationsTab({ workflow }: { workflow: ConnectedWorkflow | null }) {
  const { t } = useLocale()

  if (!workflow || workflow.operations.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-[11px] text-tp-text-3 italic px-4">
        {t('ws_noOperations')}
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto [scrollbar-width:thin]
                    [scrollbar-color:theme(colors.tp-border)_transparent]">
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-tp-surface-2 border-b border-tp-border">
          <tr>
            <th className="text-left px-3 py-1 text-tp-text-3 font-medium w-8">#</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Name</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Type</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Tool</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {workflow.operations.map((op: OperationSummary, i: number) => (
            <tr
              key={op.operationId}
              className={`border-b border-tp-border/40 hover:bg-tp-surface-2 cursor-pointer
                         ${i % 2 === 0 ? '' : 'bg-tp-surface/50'}`}
            >
              <td className="px-3 py-1 text-tp-text-3">{op.sequenceNumber}</td>
              <td className="px-2 py-1 text-tp-text font-medium truncate max-w-[200px]">{op.name}</td>
              <td className="px-2 py-1 text-tp-text-2 font-mono text-[10px]">{op.type}</td>
              <td className="px-2 py-1 text-tp-text-3 truncate max-w-[120px]">{op.toolRef ?? '—'}</td>
              <td className="px-2 py-1">
                <span className="text-[9px] font-mono px-1 py-px rounded
                                bg-tp-surface-3 text-tp-text-3 border border-tp-border">
                  {op.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Toolpaths tab
// ---------------------------------------------------------------------------

function ToolpathsTab({ workflow }: { workflow: ConnectedWorkflow | null }) {
  const { t } = useLocale()

  if (!workflow || workflow.toolpathGroups.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-[11px] text-tp-text-3 italic px-4">
        {t('ws_noToolpaths')}
      </div>
    )
  }

  const totalPoints = workflow.toolpathGroups.reduce((sum, g) => sum + g.points.length / 3, 0)

  return (
    <div className="h-full overflow-y-auto [scrollbar-width:thin]
                    [scrollbar-color:theme(colors.tp-border)_transparent] p-3">
      <div className="flex gap-4 mb-3">
        <Stat label={t('ws_toolpathCount')} value={totalPoints.toFixed(0)} />
        <Stat label="Groups" value={workflow.toolpathGroups.length} />
        <Stat label={t('ws_simRequired')} value={SAFETY.SIMULATION_REQUIRED ? 'YES' : 'NO'} />
        <Stat label={t('ws_simNotVerified')} value={String(!SAFETY.IS_VERIFIED)} />
      </div>

      <table className="w-full text-[11px]">
        <thead className="bg-tp-surface-2 border-b border-tp-border">
          <tr>
            <th className="text-left px-3 py-1 text-tp-text-3 font-medium">Motion</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Points</th>
            <th className="text-left px-2 py-1 text-tp-text-3 font-medium">Operation</th>
          </tr>
        </thead>
        <tbody>
          {workflow.toolpathGroups.map((g, i) => (
            <tr key={i} className="border-b border-tp-border/40 hover:bg-tp-surface-2">
              <td className="px-3 py-1">
                <span className="text-[9px] font-mono px-1 py-px rounded"
                      style={{ background: motionBg(g.motionType) }}>
                  {g.motionType}
                </span>
              </td>
              <td className="px-2 py-1 text-tp-text-2">{(g.points.length / 3).toFixed(0)}</td>
              <td className="px-2 py-1 text-tp-text-3 truncate max-w-[200px]">{g.operationRef}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function motionBg(type: string): string {
  const map: Record<string, string> = {
    RAPID:   'rgba(255,179,0,0.15)',
    FEED:    'rgba(0,229,255,0.15)',
    PLUNGE:  'rgba(255,87,34,0.15)',
    RETRACT: 'rgba(255,152,0,0.15)',
    LINK:    'rgba(96,125,139,0.15)',
  }
  return map[type] ?? 'rgba(100,100,100,0.1)'
}

// ---------------------------------------------------------------------------
// Simulation tab
// ---------------------------------------------------------------------------

function SimulationTab() {
  const { t } = useLocale()
  return (
    <div className="p-4 h-full overflow-y-auto">
      <div className="flex items-start gap-3 p-3 rounded border border-tp-border bg-tp-surface-3 mb-3">
        <AlertTriangle size={16} className="text-tp-text-3 mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <div className="text-[11px] font-semibold text-tp-text mb-1">{t('ws_simRequired')}</div>
          <div className="text-[11px] text-tp-text-2">{t('ws_safetyNote')}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <StatCard label={t('ws_simulation_state')} value={SAFETY.SIMULATION_STATE} />
        <StatCard label="is_verified"              value={String(SAFETY.IS_VERIFIED).toUpperCase()} />
        <StatCard label="simulation_required"      value={String(SAFETY.SIMULATION_REQUIRED).toUpperCase()} />
        <StatCard label={t('ws_noDispatch')}       value="YES" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Verification tab
// ---------------------------------------------------------------------------

function VerificationTab() {
  const { t } = useLocale()
  const checks = [
    { label: t('ws_collisionCheck'),  value: SAFETY.COLLISION_CHECK },
    { label: t('ws_gougeCheck'),      value: SAFETY.GOUGE_CHECK },
    { label: t('ws_fixtureCheck'),    value: SAFETY.FIXTURE_CHECK },
    { label: t('ws_machineEnvCheck'), value: SAFETY.MACHINE_ENVELOPE_CHECK },
  ]
  return (
    <div className="p-4 h-full overflow-y-auto">
      <div className="text-[11px] text-tp-text-2 mb-3">{t('ws_verRequired')}</div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        {checks.map(c => (
          <StatCard key={c.label} label={c.label} value={c.value} />
        ))}
      </div>
      <div className="p-2 rounded bg-tp-surface-3 border border-tp-border/50">
        <p className="text-[10px] text-tp-text-3 leading-relaxed">{t('ws_safetyNote')}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] text-tp-text-3 uppercase tracking-wider">{label}</span>
      <span className="text-[12px] font-mono text-tp-text">{value}</span>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  const isOk = value === 'NOT_PERFORMED' || value === 'TRUE' || value === 'YES'
  return (
    <div className="p-2 rounded border border-tp-border bg-tp-surface-2">
      <div className="text-[9px] text-tp-text-3 mb-1">{label}</div>
      <div className={`text-[11px] font-mono ${isOk ? 'text-tp-text-3' : 'text-tp-error'}`}>
        {value}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WorkspaceCamPanel
// ---------------------------------------------------------------------------

export interface CamPanelProps {
  workflow: ConnectedWorkflow | null
}

export default function WorkspaceCamPanel({ workflow }: CamPanelProps) {
  const { t } = useLocale()
  const [activeTab, setActiveTab]   = useState<CamTab>('operations')
  const [expanded,  setExpanded]    = useState(true)

  const PANEL_HEIGHT = 180

  return (
    <div
      className="shrink-0 flex flex-col border-t border-tp-border bg-tp-surface"
      style={{ height: expanded ? `${PANEL_HEIGHT}px` : '32px' }}
    >
      {/* Tab bar + collapse toggle */}
      <div className="shrink-0 h-8 flex items-center border-b border-tp-border">
        <div className="flex items-center flex-1 overflow-x-auto [scrollbar-width:none]">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setActiveTab(tab.id); if (!expanded) setExpanded(true) }}
              className={`shrink-0 h-8 px-3 text-[11px] border-b-2 transition-colors
                         ${activeTab === tab.id && expanded
                           ? 'text-tp-accent-light border-tp-accent'
                           : 'text-tp-text-3 border-transparent hover:text-tp-text-2'
                         }`}
            >
              {t(tab.labelKey as Parameters<typeof t>[0])}
            </button>
          ))}
        </div>
        {/* Workflow badge */}
        {workflow && (
          <span className="shrink-0 mr-2 text-[9px] font-mono px-1.5 py-0.5
                           rounded bg-tp-accent/10 text-tp-accent-light border border-tp-accent/20">
            {workflow.partName ?? workflow.workflowId}
          </span>
        )}
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="shrink-0 w-8 h-8 flex items-center justify-center
                     text-tp-text-3 hover:text-tp-text-2"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
        </button>
      </div>

      {/* Tab content */}
      {expanded && (
        <div className="flex-1 overflow-hidden">
          {activeTab === 'operations'   && <OperationsTab workflow={workflow} />}
          {activeTab === 'toolpaths'    && <ToolpathsTab workflow={workflow} />}
          {activeTab === 'simulation'   && <SimulationTab />}
          {activeTab === 'verification' && <VerificationTab />}
        </div>
      )}
    </div>
  )
}
