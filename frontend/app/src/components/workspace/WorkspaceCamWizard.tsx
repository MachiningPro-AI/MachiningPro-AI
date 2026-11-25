/**
 * WorkspaceCamWizard — Operation creation wizard modal.
 *
 * Creates a single machining operation from mesh bounding box inputs.
 * Pre-fills all geometry from the loaded mesh — user adjusts parameters.
 *
 * Safety contract:
 *   NO_FABRICATED_GEOMETRY=YES   — all coordinates derived from real mesh bbox
 *   SIMULATION_REQUIRED=YES      — passes through from toolpath API
 */

import { useState } from 'react'
import { X, Loader2, AlertTriangle } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { OperationSummary, ToolpathLineGroup } from './WorkspaceTypes'
import { generateSingleOperation } from '../../services/workspaceCam'
import type { SingleOpType } from '../../services/workspaceCam'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Field({
  label, children,
}: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="text-[11px] text-tp-text-3 w-36 shrink-0">{label}</span>
      {children}
    </div>
  )
}

function NumInput({
  value, onChange, placeholder, min, step,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  min?: number
  step?: number
}) {
  return (
    <input
      type="number"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      step={step ?? 0.01}
      className="flex-1 min-w-0 px-2 py-1 rounded border border-tp-border bg-tp-surface-2
                 text-[11px] text-tp-text placeholder:text-tp-text-3
                 focus:outline-none focus:border-tp-accent"
    />
  )
}

function Select({
  value, onChange, options,
}: {
  value: string
  onChange: (v: string) => void
  options: Array<{ value: string; label: string }>
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="flex-1 min-w-0 px-2 py-1 rounded border border-tp-border bg-tp-surface-2
                 text-[11px] text-tp-text focus:outline-none focus:border-tp-accent"
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3
                    border-b border-tp-border/40 pb-0.5 mt-3 mb-0.5">
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CamWizardProps {
  bbox: { min: [number, number, number]; max: [number, number, number] } | null
  token: string | null
  nextSequence: number
  onAdd: (op: OperationSummary, groups: ToolpathLineGroup[]) => void
  onClose: () => void
}

// ---------------------------------------------------------------------------
// WorkspaceCamWizard
// ---------------------------------------------------------------------------

export default function WorkspaceCamWizard({
  bbox, token, nextSequence, onAdd, onClose,
}: CamWizardProps) {
  const { t } = useLocale()

  const [xMin] = bbox ? [bbox.min[0].toFixed(2)] : ['0']
  const [xMax] = bbox ? [bbox.max[0].toFixed(2)] : ['100']
  const [yMin] = bbox ? [bbox.min[1].toFixed(2)] : ['0']
  const [yMax] = bbox ? [bbox.max[1].toFixed(2)] : ['100']
  const [zMax] = bbox ? [bbox.max[2].toFixed(2)] : ['0']
  const height = bbox ? (bbox.max[2] - bbox.min[2]) : 50
  const autoClrZ = bbox ? (bbox.max[2] + Math.max(height * 0.15, 5)).toFixed(2) : '15'

  const [opType,          setOpType]          = useState<SingleOpType>('FACE_MILL')
  const [toolDiam,        setToolDiam]        = useState('')
  const [clearanceZStr,   setClearanceZStr]   = useState(autoClrZ)
  const [stepdownStr,     setStepdownStr]     = useState('')
  const [stepoverStr,     setStepoverStr]     = useState('')
  const [pocketDepthStr,  setPocketDepthStr]  = useState((height * 0.3).toFixed(2))
  const [contourZStr,     setContourZStr]     = useState(bbox ? (bbox.max[2] - height * 0.1).toFixed(2) : '0')
  const [profileSide,     setProfileSide]     = useState('OUTER')
  const [pocketStrategy,  setPocketStrategy]  = useState('OFFSET')
  const [drillXStr,       setDrillXStr]       = useState(bbox ? ((bbox.min[0] + bbox.max[0]) / 2).toFixed(2) : '0')
  const [drillYStr,       setDrillYStr]       = useState(bbox ? ((bbox.min[1] + bbox.max[1]) / 2).toFixed(2) : '0')
  const [drillDepthStr,   setDrillDepthStr]   = useState((height * 0.5).toFixed(2))
  const [peckDepthStr,    setPeckDepthStr]    = useState('')

  const [generating, setGenerating] = useState(false)
  const [error,      setError]      = useState<string | null>(null)

  const opTypeOptions = [
    { value: 'FACE_MILL', label: 'Face Mill (Yüzey Frezeleme)' },
    { value: 'POCKET',    label: 'Pocket (Cep Frezeleme)' },
    { value: 'PROFILE',   label: 'Profile / Contour (Profil)' },
    { value: 'DRILL',     label: 'Drill (Matkap)' },
  ]
  const profileSideOptions = [
    { value: 'OUTER',       label: 'Outer (Dış)' },
    { value: 'INNER',       label: 'Inner (İç)' },
    { value: 'CENTERLINE',  label: 'Centerline (Merkez)' },
  ]
  const pocketStrategyOptions = [
    { value: 'OFFSET', label: 'Offset (Paralel ofset)' },
    { value: 'SPIRAL', label: 'Spiral' },
    { value: 'RASTER', label: 'Raster' },
  ]

  const handleGenerate = async () => {
    if (!bbox || !token) return
    setGenerating(true)
    setError(null)
    try {
      const { operation, toolpathGroups, warnings } = await generateSingleOperation({
        opType,
        bbox,
        fileRef: `op${nextSequence}`,
        token,
        sequenceNumber: nextSequence,
        toolDiameterMm: toolDiam ? Number(toolDiam) : null,
        clearanceZ: clearanceZStr ? Number(clearanceZStr) : null,
        stepdownMm: stepdownStr ? Number(stepdownStr) : null,
        stepoverMm: stepoverStr ? Number(stepoverStr) : null,
        pocketDepthMm: pocketDepthStr ? Number(pocketDepthStr) : null,
        pocketStrategy,
        contourZ: contourZStr ? Number(contourZStr) : null,
        profileSide,
        compensationSide: 'CENTERLINE',
        drillX: drillXStr ? Number(drillXStr) : null,
        drillY: drillYStr ? Number(drillYStr) : null,
        drillDepthMm: drillDepthStr ? Number(drillDepthStr) : null,
        peckDepthMm: peckDepthStr ? Number(peckDepthStr) : null,
      })
      if (warnings.length > 0) {
        setError(`Warnings: ${warnings.slice(0, 2).join('; ')}`)
      }
      onAdd(operation, toolpathGroups)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Toolpath generation failed')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div
        className="bg-tp-surface border border-tp-border rounded-lg shadow-xl shadow-black/50
                   w-[480px] max-h-[90vh] flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3
                        border-b border-tp-border bg-tp-surface-2">
          <h3 className="text-[12px] font-semibold text-tp-text">{t('ws_opWizardTitle')}</h3>
          <button type="button" onClick={onClose} className="text-tp-text-3 hover:text-tp-text" aria-label="Close">
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto [scrollbar-width:thin] p-4">

          {/* Operation type */}
          <SectionHead>{t('ws_opType')}</SectionHead>
          <Field label="">
            <Select value={opType} onChange={v => setOpType(v as SingleOpType)} options={opTypeOptions} />
          </Field>

          {/* Geometry — always from bbox, shown as reference */}
          <SectionHead>Geometry (from loaded part)</SectionHead>
          <div className="grid grid-cols-2 gap-x-3">
            <Field label="X min (mm)">
              <span className="flex-1 text-[11px] font-mono text-tp-text-2 bg-tp-surface-3 px-2 py-1 rounded border border-tp-border/50">{xMin}</span>
            </Field>
            <Field label="X max (mm)">
              <span className="flex-1 text-[11px] font-mono text-tp-text-2 bg-tp-surface-3 px-2 py-1 rounded border border-tp-border/50">{xMax}</span>
            </Field>
            <Field label="Y min (mm)">
              <span className="flex-1 text-[11px] font-mono text-tp-text-2 bg-tp-surface-3 px-2 py-1 rounded border border-tp-border/50">{yMin}</span>
            </Field>
            <Field label="Y max (mm)">
              <span className="flex-1 text-[11px] font-mono text-tp-text-2 bg-tp-surface-3 px-2 py-1 rounded border border-tp-border/50">{yMax}</span>
            </Field>
            <Field label="Part top Z (mm)">
              <span className="flex-1 text-[11px] font-mono text-tp-text-2 bg-tp-surface-3 px-2 py-1 rounded border border-tp-border/50">{zMax}</span>
            </Field>
          </div>

          {/* Profile / Contour Z */}
          {opType === 'PROFILE' && (
            <>
              <SectionHead>Contour Parameters</SectionHead>
              <Field label="Contour Z (mm)">
                <NumInput value={contourZStr} onChange={setContourZStr} placeholder={zMax} />
              </Field>
              <Field label={t('ws_profileSide')}>
                <Select value={profileSide} onChange={setProfileSide} options={profileSideOptions} />
              </Field>
            </>
          )}

          {/* Pocket parameters */}
          {opType === 'POCKET' && (
            <>
              <SectionHead>Pocket Parameters</SectionHead>
              <Field label={t('ws_pocketDepthMm')}>
                <NumInput value={pocketDepthStr} onChange={setPocketDepthStr} placeholder="auto" min={0.1} />
              </Field>
              <Field label={t('ws_stepdownMm')}>
                <NumInput value={stepdownStr} onChange={setStepdownStr} placeholder="auto" min={0.01} />
              </Field>
              <Field label={t('ws_strategyLabel')}>
                <Select value={pocketStrategy} onChange={setPocketStrategy} options={pocketStrategyOptions} />
              </Field>
            </>
          )}

          {/* Drill parameters */}
          {opType === 'DRILL' && (
            <>
              <SectionHead>Drill Parameters</SectionHead>
              <Field label="Hole center X (mm)">
                <NumInput value={drillXStr} onChange={setDrillXStr} />
              </Field>
              <Field label="Hole center Y (mm)">
                <NumInput value={drillYStr} onChange={setDrillYStr} />
              </Field>
              <Field label="Drill depth (mm)">
                <NumInput value={drillDepthStr} onChange={setDrillDepthStr} min={0.1} />
              </Field>
              <Field label="Peck depth (mm)">
                <NumInput value={peckDepthStr} onChange={setPeckDepthStr} placeholder="none (full)" min={0.1} />
              </Field>
            </>
          )}

          {/* Tool */}
          <SectionHead>Tool</SectionHead>
          <Field label={t('ws_toolDiam')}>
            <NumInput value={toolDiam} onChange={setToolDiam} placeholder="auto (backend default)" min={0.1} />
          </Field>

          {/* Common parameters */}
          <SectionHead>Setup Parameters</SectionHead>
          <Field label={t('ws_clearanceZ')}>
            <NumInput value={clearanceZStr} onChange={setClearanceZStr} placeholder={autoClrZ} />
          </Field>
          {(opType === 'FACE_MILL' || opType === 'POCKET') && (
            <Field label={t('ws_stepoverMm')}>
              <NumInput value={stepoverStr} onChange={setStepoverStr} placeholder="auto" min={0.01} />
            </Field>
          )}

          {/* Error */}
          {error && (
            <div className="mt-3 flex items-start gap-2 px-3 py-2 rounded border border-yellow-500/40
                            bg-yellow-500/10 text-[11px] text-yellow-300">
              <AlertTriangle size={12} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 flex items-center justify-end gap-2 px-4 py-3
                        border-t border-tp-border bg-tp-surface-2">
          <button
            type="button"
            onClick={onClose}
            disabled={generating}
            className="px-3 py-1.5 rounded text-[11px] text-tp-text-2 border border-tp-border
                       hover:bg-tp-surface disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating || !bbox || !token}
            className="px-4 py-1.5 rounded text-[11px] bg-tp-accent text-white
                       hover:bg-tp-accent/80 disabled:opacity-40 disabled:cursor-not-allowed
                       flex items-center gap-1.5"
          >
            {generating && <Loader2 size={11} className="animate-spin" />}
            {generating ? t('ws_camGenerating') : t('ws_generateOpBtn')}
          </button>
        </div>
      </div>
    </div>
  )
}
