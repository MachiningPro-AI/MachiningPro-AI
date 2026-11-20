/**
 * Reports service — calls /api/reports endpoints.
 * Downloads trigger browser save-as via blob URL.
 * IS_DISPATCHABLE=NO / PRODUCTION_RELEASED=NO always.
 */
import { api } from './apiClient'

export interface ReportTypeInfo {
  id: string
  label_en: string
  label_tr: string
  description_en: string
  description_tr: string
  supported_formats: string[]
  section_ids?: string[]
}

export interface ReportTypesResponse {
  report_types: ReportTypeInfo[]
  safety: Record<string, boolean>
}

export interface ReportItemMeta {
  format: string
  filename: string
  mime_type: string
  size_bytes: number
}

export interface GenerateReportResponse {
  report_id: string
  generated_at: string
  language: string
  units: string
  items: ReportItemMeta[]
  safety: Record<string, boolean>
  disclaimer: string
}

export interface PreviewSectionInfo {
  section_id: string
  title: string
  content_types: string[]
  has_data: boolean
}

export interface PreviewReportResponse {
  report_id: string
  report_type: string
  generated_at: string
  language: string
  units: string
  section_count: number
  sections: PreviewSectionInfo[]
  safety: Record<string, boolean>
  disclaimer: string
}

export interface GenerateReportRequest {
  workflow_id: string
  report_type?: string
  formats?: string[]
  language?: string
  units?: string
  section_ids?: string[] | null
}

export async function listReportTypes(): Promise<ReportTypesResponse> {
  return api<ReportTypesResponse>('/reports/types')
}

export async function previewReport(req: GenerateReportRequest): Promise<PreviewReportResponse> {
  return api<PreviewReportResponse>('/reports/preview', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function generateReport(req: GenerateReportRequest): Promise<GenerateReportResponse> {
  return api<GenerateReportResponse>('/reports/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

/**
 * Generate a single format and trigger browser download.
 * Returns the blob for optional preview.
 */
export async function downloadReportFormat(
  workflowId: string,
  format: string,
  language: string,
  units: string,
  reportType: string = 'FULL_MANUFACTURING_REPORT',
  sectionIds?: string[] | null,
): Promise<{ blob: Blob; filename: string }> {
  const token = sessionStorage.getItem('machiningpro_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`/api/reports/generate/${format}/download`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      workflow_id: workflowId,
      report_type: reportType,
      formats: [format],
      language,
      units,
      section_ids: sectionIds ?? null,
    }),
  })
  if (!res.ok) {
    let detail = 'Report generation failed'
    try { const d = await res.json(); detail = d.detail || detail } catch {}
    throw new Error(detail)
  }

  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : `report.${format.toLowerCase()}`
  const blob = await res.blob()
  return { blob, filename }
}

export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}
