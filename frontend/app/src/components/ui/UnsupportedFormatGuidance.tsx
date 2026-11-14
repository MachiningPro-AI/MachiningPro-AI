/**
 * UnsupportedFormatGuidance — actionable offline conversion guidance for
 * DWG and CATIA V4 .model files that cannot be imported directly.
 *
 * Shows format-specific instructions when the import result is UNSUPPORTED.
 * No automatic processing — engineer must convert and re-import.
 */
import { useLocale } from '../../i18n'
import Panel from './Panel'

type UnsupportedFormat = 'DWG' | 'MODEL' | 'OTHER'

function detectUnsupportedFormat(errorMessage: string | undefined): UnsupportedFormat {
  if (!errorMessage) return 'OTHER'
  const msg = errorMessage.toUpperCase()
  if (msg.includes('DWG')) return 'DWG'
  if (msg.includes('MODEL') || msg.includes('CATIA')) return 'MODEL'
  return 'OTHER'
}

interface Props {
  errorMessage?: string
  formatId?: string
}

export default function UnsupportedFormatGuidance({ errorMessage, formatId }: Props) {
  const { t } = useLocale()

  const format = formatId?.toUpperCase() === 'DWG'
    ? 'DWG'
    : formatId?.toUpperCase().includes('MODEL')
      ? 'MODEL'
      : detectUnsupportedFormat(errorMessage)

  if (format === 'DWG') {
    return (
      <Panel title={t('p2Unsupported_dwgTitle')}>
        <p className="text-xs text-tp-text-2 mb-3">{t('p2Unsupported_dwgBody')}</p>
        <ol className="list-decimal list-inside space-y-1.5 text-xs text-tp-text">
          <li>{t('p2Unsupported_dwgStep1')}</li>
          <li>{t('p2Unsupported_dwgStep2')}</li>
        </ol>
        <p className="text-xs text-tp-text-3 mt-3 italic">
          {t('p2Unsupported_contactSupport')}
        </p>
      </Panel>
    )
  }

  if (format === 'MODEL') {
    return (
      <Panel title={t('p2Unsupported_modelTitle')}>
        <p className="text-xs text-tp-text-2 mb-3">{t('p2Unsupported_modelBody')}</p>
        <p className="text-xs text-tp-text-3 mt-2 italic">
          {t('p2Unsupported_contactSupport')}
        </p>
      </Panel>
    )
  }

  return null
}
