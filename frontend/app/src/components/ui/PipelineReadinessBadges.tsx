/**
 * PipelineReadinessBadges — visual stage-gate indicators for the manufacturing pipeline.
 *
 * Displays which readiness stages a file has passed.
 * Never fabricates or infers readiness — only reflects what the backend confirmed.
 * All stages default to NOT READY until the backend explicitly sets them.
 *
 * READINESS_FABRICATED=NO
 */
import { useLocale } from '../../i18n'

export type ReadinessStage =
  | 'IMPORT_READY'
  | 'GEOMETRY_READY'
  | 'DRAWING_INTELLIGENCE_READY'
  | 'FEATURE_READY'
  | 'METADATA_READY'
  | 'PROCESS_PLANNING_READY'
  | 'CAM_READY'

export interface PipelineReadinessState {
  stages: ReadinessStage[]
}

const STAGE_ORDER: ReadinessStage[] = [
  'IMPORT_READY',
  'GEOMETRY_READY',
  'DRAWING_INTELLIGENCE_READY',
  'FEATURE_READY',
  'METADATA_READY',
  'PROCESS_PLANNING_READY',
  'CAM_READY',
]

type BadgeKey =
  | 'p2ReadinessBadge_importReady'
  | 'p2ReadinessBadge_geometryReady'
  | 'p2ReadinessBadge_drawingIntelligenceReady'
  | 'p2ReadinessBadge_featureReady'
  | 'p2ReadinessBadge_metadataReady'
  | 'p2ReadinessBadge_processPlanning'
  | 'p2ReadinessBadge_camReady'

const STAGE_LABEL_KEY: Record<ReadinessStage, BadgeKey> = {
  IMPORT_READY: 'p2ReadinessBadge_importReady',
  GEOMETRY_READY: 'p2ReadinessBadge_geometryReady',
  DRAWING_INTELLIGENCE_READY: 'p2ReadinessBadge_drawingIntelligenceReady',
  FEATURE_READY: 'p2ReadinessBadge_featureReady',
  METADATA_READY: 'p2ReadinessBadge_metadataReady',
  PROCESS_PLANNING_READY: 'p2ReadinessBadge_processPlanning',
  CAM_READY: 'p2ReadinessBadge_camReady',
}

export default function PipelineReadinessBadges({
  readiness,
}: {
  readiness: PipelineReadinessState | null
}) {
  const { t } = useLocale()

  if (!readiness) return null

  const passedSet = new Set(readiness.stages)

  return (
    <div className="flex flex-wrap gap-1.5 items-center" role="list" aria-label={t('p2ReadinessBadge_tooltip')}>
      {STAGE_ORDER.map((stage) => {
        const passed = passedSet.has(stage)
        return (
          <span
            key={stage}
            role="listitem"
            title={t('p2ReadinessBadge_tooltip')}
            className={[
              'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border',
              passed
                ? 'bg-green-50 border-green-300 text-green-800 dark:bg-green-900/20 dark:border-green-700 dark:text-green-300'
                : 'bg-tp-surface border-tp-border text-tp-text-3 opacity-50',
            ].join(' ')}
          >
            <span
              className={[
                'w-1.5 h-1.5 rounded-full flex-shrink-0',
                passed ? 'bg-green-500' : 'bg-tp-text-3',
              ].join(' ')}
            />
            {t(STAGE_LABEL_KEY[stage])}
          </span>
        )
      })}
    </div>
  )
}
