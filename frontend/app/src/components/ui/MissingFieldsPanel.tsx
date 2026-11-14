/**
 * MissingFieldsPanel — displays unknown/unconfirmed engineering fields and
 * allows the engineer to supply confirmed values before process planning.
 *
 * Calls POST /api/missing-data/analyze to get field status,
 * and POST /api/missing-data/confirm to submit engineer-confirmed values.
 *
 * NEVER auto-confirms — all values require explicit engineer input.
 * AUTO_CONFIRM=NO  FABRICATED_DATA=NO
 */
import { useState, useEffect } from 'react'
import { useLocale } from '../../i18n'
import Panel from './Panel'

interface MissingDataField {
  field_name: string
  status: 'KNOWN' | 'UNKNOWN' | 'CONFLICT' | string
  value?: string | null
  source?: string
  review_required?: boolean
}

interface MissingDataResponse {
  readiness_states: Record<string, string>
  blocking_stages: string[]
  required_missing_fields: string[]
  optional_missing_fields: string[]
  fields: Record<string, MissingDataField>
}

interface Props {
  drawingSessionId: string | null
  onConfirmed?: () => void
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export default function MissingFieldsPanel({ drawingSessionId, onConfirmed }: Props) {
  const { t } = useLocale()
  const [data, setData] = useState<MissingDataResponse | null>(null)
  const [materialInput, setMaterialInput] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [confirmOk, setConfirmOk] = useState(false)

  useEffect(() => {
    if (!drawingSessionId) return
    fetch(`${API_BASE}/api/missing-data/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: drawingSessionId }),
    })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((json) => setData(json))
      .catch(() => {/* no panel if unavailable */})
  }, [drawingSessionId])

  if (!data) return null

  const unknownFields = data.required_missing_fields
  if (unknownFields.length === 0 && !data.blocking_stages?.length) return null

  const handleConfirm = async () => {
    if (!materialInput.trim() || !drawingSessionId) return
    setConfirming(true)
    setConfirmError(null)
    try {
      const res = await fetch(`${API_BASE}/api/missing-data/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: drawingSessionId,
          confirmed_values: { material: materialInput.trim() },
          confirmed_by: 'engineer',
        }),
      })
      if (!res.ok) throw new Error(String(res.status))
      setConfirmOk(true)
      onConfirmed?.()
    } catch (e) {
      setConfirmError(String(e))
    } finally {
      setConfirming(false)
    }
  }

  const materialField = data.fields?.material
  const materialStatus = materialField?.status ?? 'UNKNOWN'
  const materialValue = materialField?.value

  return (
    <Panel title={t('p2Material_panelTitle')}>
      <p className="text-xs text-tp-text-2 mb-3">{t('p2Material_missingFields')}</p>

      {/* Material grade field */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-tp-text">{t('p2Material_grade')}</span>
          <span
            className={[
              'text-xs px-1.5 py-0.5 rounded border',
              materialStatus === 'KNOWN'
                ? 'bg-green-50 border-green-300 text-green-700 dark:bg-green-900/20 dark:text-green-300'
                : 'bg-yellow-50 border-yellow-300 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-300',
            ].join(' ')}
          >
            {materialStatus === 'KNOWN' ? (materialValue ?? '') : t('p2Material_unknownGrade')}
          </span>
        </div>

        {materialStatus !== 'KNOWN' && !confirmOk && (
          <div className="flex gap-2 mt-2">
            <input
              type="text"
              value={materialInput}
              onChange={(e) => setMaterialInput(e.target.value)}
              placeholder={t('p2Material_confirmHint')}
              className="flex-1 text-xs px-2 py-1.5 rounded border border-tp-border bg-tp-surface-2 text-tp-text placeholder-tp-text-3 focus:outline-none focus:ring-1 focus:ring-tp-accent"
              aria-label={t('p2Material_grade')}
            />
            <button
              onClick={handleConfirm}
              disabled={confirming || !materialInput.trim()}
              className="text-xs px-3 py-1.5 rounded border border-tp-accent bg-tp-accent text-white disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
            >
              {confirming ? '…' : t('p2Material_confirmButton')}
            </button>
          </div>
        )}

        {confirmOk && (
          <p className="text-xs text-green-600 dark:text-green-400 mt-1">
            ✓ {materialInput}
          </p>
        )}
        {confirmError && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{confirmError}</p>
        )}
      </div>

      <p className="text-xs text-tp-text-3 italic border-t border-tp-border pt-2">
        {t('p2Material_reviewNote')}
      </p>
    </Panel>
  )
}
