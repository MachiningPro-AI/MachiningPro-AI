/**
 * API client for the /api/cam/plan endpoint (Level-9 Automatic CAM Planning).
 *
 * Returns CAM planning CANDIDATES only — NO G-code, no toolpath coordinates.
 * Every response declares simulation_required=true (Level-9 invariant).
 * All outputs require engineering review before use.
 */

import { getStoredAuth } from './apiClient'
import type {
  CamPlanRequest,
  CamPlanResponse,
} from '../types/api'

const BASE = '/api/cam'

function authHeaders(): Record<string, string> {
  const token = getStoredAuth().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Request a CAM planning candidate job from upstream feature/material
 * intelligence. Returns candidates only; never returns G-code.
 */
export async function requestCamPlan(req: CamPlanRequest): Promise<CamPlanResponse> {
  const resp = await fetch(`${BASE}/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(req),
  })

  if (!resp.ok) {
    const detail = await resp.text()
    throw new Error(`CAM plan request failed (${resp.status}): ${detail}`)
  }

  const data: CamPlanResponse = await resp.json()

  if (!data.simulation_required) {
    throw new Error('CAM_PLANNING_CONTRACT_VIOLATION: simulation_required must be true')
  }

  return data
}
