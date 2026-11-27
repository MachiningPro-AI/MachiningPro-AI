/**
 * WorkspaceMachinePanel — Phase X machine properties panel
 *
 * Displays where available (never fabricates):
 *   Machine / Architecture / Axes
 *   X/Y/Z Travel, A/B/C Limits
 *   Spindle / Feed limits
 *   Active Tool / Holder / Stickout
 *   Current Axis Position / Axis Limit Margin
 *   Simulation Quality / Geometry Fidelity / Verification Status / Provenance
 *
 * Safety:
 *   NO_FABRICATED_MACHINE_DATA=YES
 *   NO_MACHINE_WRITE=YES
 *   NO_AUTO_APPROVAL=YES
 *   TR/EN localization preserved
 */

import { useLocale } from '../../i18n'
import type { MachineDigitalTwinState, WorkspaceQualityMode } from './WorkspaceTypes'

interface MachineProps {
  machine: MachineDigitalTwinState
  qualityMode: WorkspaceQualityMode
  activeToolId?: string
  activeHolderId?: string
  toolStickoutMm?: number
  verificationStatus?: string
  geometryFidelity?: string
  provenance?: string
}

function PRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-start gap-2 py-0.5 border-b border-tp-border/30">
      <span className="shrink-0 w-32 text-[10px] text-tp-text-3">{label}</span>
      <span className="flex-1 text-[10px] text-tp-text font-mono break-all">{String(value)}</span>
    </div>
  )
}

function SectionHdr({ label }: { label: string }) {
  return (
    <div className="pt-2 pb-0.5">
      <span className="text-[8px] font-semibold uppercase tracking-widest text-tp-text-3">
        {label}
      </span>
    </div>
  )
}

export default function WorkspaceMachinePanel({
  machine,
  qualityMode,
  activeToolId,
  activeHolderId,
  toolStickoutMm,
  verificationStatus,
  geometryFidelity,
  provenance,
}: MachineProps) {
  const { locale } = useLocale()
  const L = locale === 'tr'

  const title = L ? 'Makine Dijital İkizi' : 'Machine Digital Twin'
  const noMachine = L ? 'Makine seçilmedi' : 'No machine selected'

  if (!machine.ready || !machine.machineId) {
    return (
      <div className="px-3 py-2">
        <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 pb-1 border-b border-tp-border">
          {title}
        </div>
        <div className="text-[11px] text-tp-text-3 mt-2">{noMachine}</div>
      </div>
    )
  }

  const fidelityLabel = {
    FULL_MACHINE_KINEMATICS: L ? 'Tam Kinematik' : 'Full Kinematics',
    PARTIAL_MACHINE_KINEMATICS: L ? 'Kısmi Kinematik' : 'Partial Kinematics',
    TOOL_ONLY: L ? 'Yalnızca Takım' : 'Tool Only',
    NOT_AVAILABLE: L ? 'Mevcut Değil' : 'Not Available',
  }[machine.fidelity] ?? machine.fidelity

  const qmLabel: Record<WorkspaceQualityMode, string> = {
    FAST: L ? 'Hızlı (Yaklaşık)' : 'Fast (Approximate)',
    BALANCED: L ? 'Dengeli' : 'Balanced',
    HIGH_FIDELITY: L ? 'Yüksek Hassasiyet' : 'High Fidelity',
  }

  return (
    <div className="px-3 py-1 overflow-y-auto text-tp-text">
      <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3 pb-1 border-b border-tp-border">
        {title}
      </div>

      <SectionHdr label={L ? 'Makine' : 'Machine'} />
      <PRow label={L ? 'ID' : 'Machine ID'} value={machine.machineId} />
      <PRow label={L ? 'Mimari' : 'Architecture'} value={machine.architecture} />
      <PRow label={L ? 'Görsel Hassasiyet' : 'Visualization'} value={fidelityLabel} />

      <SectionHdr label={L ? 'Eksen Limitleri' : 'Axis Limits'} />
      {Object.entries(machine.axisLimits).map(([axis, [lo, hi]]) => (
        <PRow key={axis} label={axis} value={`${lo} … ${hi}`} />
      ))}
      {Object.keys(machine.axisLimits).length === 0 && (
        <div className="text-[10px] text-tp-text-3 py-0.5">
          {L ? 'Limit verisi yok' : 'No limit data'}
        </div>
      )}

      <SectionHdr label={L ? 'Mevcut Pozisyon' : 'Current Position'} />
      {Object.entries(machine.currentAxisPositions).map(([axis, val]) => {
        const limits = machine.axisLimits[axis]
        const margin = limits
          ? Math.min(val - limits[0], limits[1] - val)
          : null
        return (
          <div key={axis} className="flex items-start gap-2 py-0.5 border-b border-tp-border/30">
            <span className="shrink-0 w-32 text-[10px] text-tp-text-3">{axis}</span>
            <span className="flex-1 text-[10px] text-tp-text font-mono">{val.toFixed(3)}</span>
            {margin !== null && (
              <span className={`text-[9px] font-mono ${margin < 5 ? 'text-red-400' : 'text-green-400'}`}>
                ±{margin.toFixed(1)}
              </span>
            )}
          </div>
        )
      })}

      <SectionHdr label={L ? 'Takım Montajı' : 'Tool Assembly'} />
      <PRow label={L ? 'Takım ID' : 'Tool ID'} value={activeToolId} />
      <PRow label={L ? 'Tutucu ID' : 'Holder ID'} value={activeHolderId} />
      <PRow label={L ? 'Uzatma (mm)' : 'Stickout (mm)'} value={toolStickoutMm} />

      <SectionHdr label={L ? 'Doğrulama' : 'Verification'} />
      <PRow label={L ? 'Kalite Modu' : 'Quality Mode'} value={qmLabel[qualityMode]} />
      <PRow label={L ? 'Geometri Hassasiyeti' : 'Geometry Fidelity'} value={geometryFidelity} />
      <PRow label={L ? 'Doğrulama Durumu' : 'Verification Status'} value={verificationStatus} />
      <PRow label={L ? 'Kaynak' : 'Provenance'} value={provenance} />
    </div>
  )
}
