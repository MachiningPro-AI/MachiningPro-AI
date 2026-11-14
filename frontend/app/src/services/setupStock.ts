import api from './apiClient'

// ---------------------------------------------------------------------------
// Request / Response types
// ---------------------------------------------------------------------------

export interface StockRequest {
  shape: string
  material_grade: string
  length_mm?: number | null
  width_mm?: number | null
  height_mm?: number | null
  outer_diameter_mm?: number | null
  inner_diameter_mm?: number | null
  stock_notes?: string | null
  confirmed_by?: string
}

export interface SetupRequest {
  n_setups?: number
  datum_a?: string | null
  datum_b?: string | null
  datum_c?: string | null
  orientation?: string | null
  fixture_note?: string | null
  confirmed_by?: string
}

export interface CreateSessionRequest {
  cad_session_id?: string | null
  stock?: StockRequest | null
  setup?: SetupRequest | null
}

export interface UpdateSessionRequest {
  stock?: StockRequest | null
  setup?: SetupRequest | null
}

export interface StockOut {
  stock_id: string
  shape: string
  material_grade: string
  length_mm: number | null
  width_mm: number | null
  height_mm: number | null
  outer_diameter_mm: number | null
  inner_diameter_mm: number | null
  stock_notes: string | null
  confirmed_by: string
  provenance: string
  created_at: string
}

export interface SetupOut {
  setup_id: string
  n_setups: number
  datum_a: string | null
  datum_b: string | null
  datum_c: string | null
  orientation: string | null
  fixture_note: string | null
  confirmed_by: string
  provenance: string
  created_at: string
}

export interface SetupStockSessionOut {
  session_id: string
  cad_session_id: string | null
  stock: StockOut | null
  setup: SetupOut | null
  stock_complete: boolean
  setup_complete: boolean
  stock_missing: string[]
  setup_errors: string[]
  cam_prerequisites_met: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function createSetupStockSession(
  req: CreateSessionRequest,
): Promise<SetupStockSessionOut & { session_id: string; status: string }> {
  return api('/setup-stock/', { method: 'POST', body: JSON.stringify(req) })
}

export async function getSetupStockSession(
  sessionId: string,
): Promise<SetupStockSessionOut> {
  return api(`/setup-stock/${encodeURIComponent(sessionId)}`)
}

export async function updateSetupStockSession(
  sessionId: string,
  req: UpdateSessionRequest,
): Promise<SetupStockSessionOut & { status: string }> {
  return api(`/setup-stock/${encodeURIComponent(sessionId)}`, {
    method: 'PUT',
    body: JSON.stringify(req),
  })
}

export const STOCK_SHAPES = [
  'RECTANGULAR_BLOCK',
  'ROUND_BAR',
  'RING',
  'PLATE',
  'FORGING',
] as const

export type StockShape = typeof STOCK_SHAPES[number]
