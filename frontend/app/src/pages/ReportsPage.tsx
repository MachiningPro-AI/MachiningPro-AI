/**
 * ReportsPage — Manufacturing Reports & Export
 *
 * Safety invariants (never bypassed in this component):
 *   IS_DISPATCHABLE=NO
 *   PRODUCTION_RELEASED=NO
 *   AUTO_APPROVED=NO
 *   ENGINEERING_STATE_CHANGED=NO
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useLocale } from '../i18n'
import { PipelineBreadcrumb } from '../components/PipelineBreadcrumb'
import { usePipeline } from '../context/PipelineContext'
import {
  listReportTypes,
  generateReport,
  downloadReportFormat,
  triggerDownload,
  type ReportTypeInfo,
  type GenerateReportResponse,
} from '../services/reports'
import { AlertTriangle, Download, FileDown, CheckCircle, Loader2 } from 'lucide-react'

const DRAFT_DISCLAIMER =
  'DRAFT - Engineering Review Required. IS_DISPATCHABLE=NO | PRODUCTION_RELEASED=NO | AUTO_APPROVED=NO | ENGINEERING_STATE_CHANGED=NO'

const FORMAT_LABELS: Record<string, string> = {
  PDF: 'PDF',
  DOCX: 'Word (DOCX)',
  XLSX: 'Excel (XLSX)',
  CSV: 'CSV',
  JSON: 'JSON',
  ZIP: 'All Formats (ZIP)',
}

const FORMAT_ORDER = ['PDF', 'DOCX', 'XLSX', 'CSV', 'JSON', 'ZIP']

export default function ReportsPage() {
  const { t } = useLocale()
  const { state: pipeline } = usePipeline()

  const [reportTypes, setReportTypes] = useState<ReportTypeInfo[]>([])
  const [selectedType, setSelectedType] = useState('MANUFACTURING_PLAN')
  const [language, setLanguage] = useState<'EN' | 'TR'>('EN')
  const [units, setUnits] = useState<'METRIC' | 'IMPERIAL'>('METRIC')
  const [selectedFormats, setSelectedFormats] = useState<string[]>(['PDF', 'JSON'])

  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GenerateReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  const workflowId = pipeline?.workflowId ?? null

  useEffect(() => {
    listReportTypes()
      .then(r => setReportTypes(r.report_types))
      .catch(() => {})
  }, [])

  const toggleFormat = useCallback((fmt: string) => {
    setSelectedFormats(prev =>
      prev.includes(fmt) ? prev.filter(f => f !== fmt) : [...prev, fmt]
    )
  }, [])

  const handleGenerate = useCallback(async () => {
    if (!workflowId) return
    setGenerating(true)
    setError(null)
    setResult(null)
    try {
      const res = await generateReport({
        workflow_id: workflowId,
        report_type: selectedType,
        formats: selectedFormats,
        language,
        units,
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }, [workflowId, selectedType, selectedFormats, language, units])

  const handleDownload = useCallback(async (format: string) => {
    if (!workflowId) return
    setDownloading(format)
    try {
      const { blob, filename } = await downloadReportFormat(workflowId, format, language, units)
      triggerDownload(blob, filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setDownloading(null)
    }
  }, [workflowId, language, units])

  const selectedTypeInfo = reportTypes.find(r => r.id === selectedType)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <PipelineBreadcrumb />

      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">

        {/* Page header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('reports_pageTitle')}
          </h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            {t('reports_pageSubtitle')}
          </p>
        </div>

        {/* Safety banner — always visible */}
        <div className="flex items-start gap-3 p-4 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-700">
          <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-800 dark:text-red-300">
              {t('reports_draftWarning')}
            </p>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-red-700 dark:text-red-400">
              <span>{t('reports_dispatchable')}</span>
              <span>{t('reports_productionReleased')}</span>
              <span>{t('reports_autoApproved')}</span>
              <span>{t('reports_engineeringStateChanged')}</span>
            </div>
          </div>
        </div>

        {/* No workflow warning */}
        {!workflowId && (
          <div className="p-4 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950 dark:border-amber-700">
            <p className="text-sm text-amber-800 dark:text-amber-300">
              {t('reports_selectWorkflow')}
            </p>
          </div>
        )}

        {/* Configuration card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5 space-y-5">

          {/* Report type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {t('reports_selectType')}
            </label>
            <div className="space-y-2">
              {reportTypes.map(rt => (
                <label key={rt.id} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="report_type"
                    value={rt.id}
                    checked={selectedType === rt.id}
                    onChange={() => setSelectedType(rt.id)}
                    className="mt-0.5"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {language === 'TR' ? rt.label_tr : rt.label_en}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {language === 'TR' ? rt.description_tr : rt.description_en}
                    </p>
                  </div>
                </label>
              ))}
              {reportTypes.length === 0 && (
                <p className="text-sm text-gray-500">{t('reports_type_manufacturingPlan')}</p>
              )}
            </div>
          </div>

          {/* Language + Units row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('reports_language')}
              </label>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value as 'EN' | 'TR')}
                className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-3 py-1.5 text-sm"
              >
                <option value="EN">English</option>
                <option value="TR">Türkçe</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('reports_units')}
              </label>
              <select
                value={units}
                onChange={e => setUnits(e.target.value as 'METRIC' | 'IMPERIAL')}
                className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-3 py-1.5 text-sm"
              >
                <option value="METRIC">Metric (mm)</option>
                <option value="IMPERIAL">Imperial (in)</option>
              </select>
            </div>
          </div>

          {/* Format checkboxes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {t('reports_formats')}
            </label>
            <div className="flex flex-wrap gap-2">
              {FORMAT_ORDER.map(fmt => (
                <label key={fmt} className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selectedFormats.includes(fmt)}
                    onChange={() => toggleFormat(fmt)}
                    className="rounded"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    {FORMAT_LABELS[fmt]}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Generate button */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={generating || !workflowId || selectedFormats.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded text-sm font-medium transition-colors"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="h-4 w-4" />
              )}
              {generating ? t('reports_generating') : t('reports_generate')}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-3 rounded border border-red-300 bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5 space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Report Ready
              </h2>
            </div>

            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
              <div className="text-gray-500 dark:text-gray-400">{t('reports_reportId')}</div>
              <div className="font-mono text-gray-700 dark:text-gray-300">{result.report_id}</div>
              <div className="text-gray-500 dark:text-gray-400">{t('reports_generatedAt')}</div>
              <div className="text-gray-700 dark:text-gray-300">{result.generated_at}</div>
              <div className="text-gray-500 dark:text-gray-400">{t('reports_reviewRequired')}</div>
              <div className="text-red-600 dark:text-red-400 font-semibold">YES</div>
            </div>

            <div className="pt-1 border-t border-gray-100 dark:border-gray-700">
              <p className="text-xs text-red-600 dark:text-red-400 mb-3">
                {result.disclaimer}
              </p>
              <div className="space-y-2">
                {result.items.map(item => (
                  <div
                    key={item.format}
                    className="flex items-center justify-between py-2 px-3 rounded bg-gray-50 dark:bg-gray-750"
                  >
                    <div>
                      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                        {FORMAT_LABELS[item.format] ?? item.format}
                      </span>
                      <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                        {item.filename} ({Math.round(item.size_bytes / 1024)} KB)
                      </span>
                    </div>
                    <button
                      onClick={() => handleDownload(item.format)}
                      disabled={downloading === item.format}
                      className="flex items-center gap-1 px-3 py-1 text-xs font-medium bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded transition-colors"
                    >
                      {downloading === item.format ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Download className="h-3 w-3" />
                      )}
                      {t('reports_download')}
                    </button>
                  </div>
                ))}
              </div>

              <div className="mt-3">
                <button
                  onClick={() => handleDownload('ZIP')}
                  disabled={downloading === 'ZIP'}
                  className="flex items-center gap-2 px-4 py-2 w-full justify-center border border-blue-300 dark:border-blue-600 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900 rounded text-sm font-medium transition-colors"
                >
                  {downloading === 'ZIP' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  {t('reports_exportAll')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Safety footer note */}
        <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
          {t('reports_safetyNote')}
        </p>
      </div>
    </div>
  )
}
