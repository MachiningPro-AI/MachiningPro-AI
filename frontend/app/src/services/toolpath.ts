/**
 * Level-10 Toolpath Generation Service
 *
 * Safety contract
 * ---------------
 * NO_GCODE=YES        — service never sends or receives G-code.
 * SIMULATION_REQUIRED — every response declares simulation_required=true.
 * NOT_VERIFIED        — every response declares is_verified=false.
 * CONTRACT_ENFORCED   — service throws on any violation of these invariants.
 */

import { apiClient } from './apiClient'
import type {
  DrillToolpathRequest,
  ProfileToolpathRequest,
  ToolpathResponse,
} from '../types/api'

const BASE = '/api/toolpath'

function enforceContract(data: ToolpathResponse, endpoint: string): ToolpathResponse {
  if (data.simulation_required !== true) {
    throw new Error(
      `TOOLPATH_CONTRACT_VIOLATION: simulation_required must be true [${endpoint}]`
    )
  }
  if (data.is_verified !== false) {
    throw new Error(
      `TOOLPATH_CONTRACT_VIOLATION: is_verified must be false [${endpoint}]`
    )
  }
  const v = data.verification_requirements
  if (
    v.collision_check !== 'NOT_PERFORMED' ||
    v.gouge_check !== 'NOT_PERFORMED' ||
    v.fixture_check !== 'NOT_PERFORMED' ||
    v.machine_collision_check !== 'NOT_PERFORMED'
  ) {
    throw new Error(
      `TOOLPATH_CONTRACT_VIOLATION: all verification checks must be NOT_PERFORMED [${endpoint}]`
    )
  }
  return data
}

export async function requestDrillToolpath(
  req: DrillToolpathRequest,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/drill`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: drill ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'drill')
}

export async function requestProfileToolpath(
  req: ProfileToolpathRequest,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: profile ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'profile')
}

export async function requestPocketToolpath(
  req: Record<string, unknown>,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/pocket`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: pocket ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'pocket')
}

export async function requestFaceMillToolpath(
  req: Record<string, unknown>,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/face-mill`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: face-mill ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'face-mill')
}

export async function requestSlotToolpath(
  req: Record<string, unknown>,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/slot`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: slot ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'slot')
}

export async function requestChamferToolpath(
  req: Record<string, unknown>,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/chamfer`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: chamfer ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'chamfer')
}

export async function requestTurningToolpath(
  req: Record<string, unknown>,
  token: string
): Promise<ToolpathResponse> {
  const resp = await apiClient(`${BASE}/turning`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    throw new Error(`TOOLPATH_API_ERROR: turning ${resp.status} ${resp.statusText}`)
  }
  const data: ToolpathResponse = await resp.json()
  return enforceContract(data, 'turning')
}
