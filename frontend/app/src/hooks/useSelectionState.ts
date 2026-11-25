/**
 * useSelectionState — manages geometry selection, hover, measurement, and
 * visibility for the CAD/CAM workspace viewer.
 *
 * Safety contract (MUST 38):
 *   SELECTION_ENGINEERING_STATE_CHANGED=NO
 *   FEATURE_CONFIRMATION_CHANGED=NO
 *   WCS_CHANGED=NO
 *   TOOL_SELECTION_CHANGED=NO
 *   CAM_STATE_CHANGED=NO
 *   PRODUCTION_RELEASE_CHANGED=NO
 *
 * This hook manages viewer/visualization state only.
 */

import { useCallback, useRef, useState } from 'react'
import type {
  SelectedEntity,
  SelectionMode,
  HoverTarget,
  MeasurementEntry,
  MeasurementType,
  VisibilityOverride,
} from '../components/workspace/WorkspaceTypes'

let _measureId = 0
function nextMeasureId(): string {
  return `meas_${++_measureId}`
}

export interface SelectionState {
  mode: SelectionMode
  selected: SelectedEntity[]        // multi-select list
  hover: HoverTarget | null
  measurements: MeasurementEntry[]
  visibilityOverrides: VisibilityOverride[]
  pendingMeasurePoint: [number,number,number] | null  // first point of P2P measurement
}

export interface SelectionActions {
  setMode: (m: SelectionMode) => void
  selectEntity: (e: SelectedEntity, additive: boolean) => void
  clearSelection: () => void
  setHover: (h: HoverTarget | null) => void
  addMeasurePoint: (pt: [number,number,number]) => void
  clearMeasurements: () => void
  removeMeasurement: (id: string) => void
  addEdgeLengthMeasurement: (lengthUnits: number, label: string, anchorA: [number,number,number], anchorB: [number,number,number]) => void
  setHidden: (entityId: string, hidden: boolean) => void
  isolateEntity: (entityId: string) => void
  showAll: () => void
}

const DEFAULT_STATE: SelectionState = {
  mode: 'FACE',
  selected: [],
  hover: null,
  measurements: [],
  visibilityOverrides: [],
  pendingMeasurePoint: null,
}

export function useSelectionState(): [SelectionState, SelectionActions] {
  const [state, setState] = useState<SelectionState>(DEFAULT_STATE)

  // Stable ref so callbacks don't stale-close
  const stateRef = useRef(state)
  stateRef.current = state

  const setMode = useCallback((m: SelectionMode) => {
    setState(s => ({ ...s, mode: m, hover: null }))
  }, [])

  const selectEntity = useCallback((e: SelectedEntity, additive: boolean) => {
    setState(s => {
      if (additive) {
        // Deselect if already selected, otherwise add
        const exists = s.selected.some(x => entityKey(x) === entityKey(e))
        return {
          ...s,
          selected: exists
            ? s.selected.filter(x => entityKey(x) !== entityKey(e))
            : [...s.selected, e],
        }
      }
      return { ...s, selected: [e] }
    })
  }, [])

  const clearSelection = useCallback(() => {
    setState(s => ({ ...s, selected: [], pendingMeasurePoint: null }))
  }, [])

  const setHover = useCallback((h: HoverTarget | null) => {
    setState(s => {
      if (s.hover === h) return s
      if (!h && !s.hover) return s
      if (h && s.hover &&
          h.entityClass === s.hover.entityClass &&
          h.faceId === s.hover.faceId &&
          h.edgeId === s.hover.edgeId) return s
      return { ...s, hover: h }
    })
  }, [])

  const addMeasurePoint = useCallback((pt: [number,number,number]) => {
    setState(s => {
      if (!s.pendingMeasurePoint) {
        return { ...s, pendingMeasurePoint: pt }
      }
      // Complete P2P measurement
      const a = s.pendingMeasurePoint
      const b = pt
      const dx = b[0] - a[0]
      const dy = b[1] - a[1]
      const dz = b[2] - a[2]
      const dist = Math.sqrt(dx*dx + dy*dy + dz*dz)
      const entry: MeasurementEntry = {
        id: nextMeasureId(),
        type: 'POINT_DISTANCE',
        label: 'Point Distance',
        value: dist,
        unit: 'mm',
        display: `${dist.toFixed(3)} mm`,
        anchorA: a,
        anchorB: b,
        pending: false,
        status: 'OK',
      }
      return {
        ...s,
        pendingMeasurePoint: null,
        measurements: [...s.measurements, entry],
      }
    })
  }, [])

  const clearMeasurements = useCallback(() => {
    setState(s => ({ ...s, measurements: [], pendingMeasurePoint: null }))
  }, [])

  const removeMeasurement = useCallback((id: string) => {
    setState(s => ({ ...s, measurements: s.measurements.filter(m => m.id !== id) }))
  }, [])

  const addEdgeLengthMeasurement = useCallback((
    lengthUnits: number,
    label: string,
    anchorA: [number,number,number],
    anchorB: [number,number,number],
  ) => {
    const entry: MeasurementEntry = {
      id: nextMeasureId(),
      type: 'EDGE_LENGTH',
      label,
      value: lengthUnits,
      unit: 'mm',
      display: `${lengthUnits.toFixed(3)} mm`,
      anchorA,
      anchorB,
      pending: false,
      status: 'OK',
    }
    setState(s => ({ ...s, measurements: [...s.measurements, entry] }))
  }, [])

  const setHidden = useCallback((entityId: string, hidden: boolean) => {
    setState(s => {
      const others = s.visibilityOverrides.filter(v => v.entityId !== entityId)
      if (!hidden) return { ...s, visibilityOverrides: others }
      return { ...s, visibilityOverrides: [...others, { entityId, hidden: true }] }
    })
  }, [])

  const isolateEntity = useCallback((entityId: string) => {
    setState(s => {
      // Hide all OTHER entities; show the target
      const allIds = s.selected.map(entityKey)
      const others = allIds.filter(id => id !== entityId)
      const newOverrides: VisibilityOverride[] = others.map(id => ({ entityId: id, hidden: true }))
      return { ...s, visibilityOverrides: newOverrides }
    })
  }, [])

  const showAll = useCallback(() => {
    setState(s => ({ ...s, visibilityOverrides: [] }))
  }, [])

  return [
    state,
    {
      setMode,
      selectEntity,
      clearSelection,
      setHover,
      addMeasurePoint,
      clearMeasurements,
      removeMeasurement,
      addEdgeLengthMeasurement,
      setHidden,
      isolateEntity,
      showAll,
    },
  ]
}

function entityKey(e: SelectedEntity): string {
  if (e.kind === 'BODY') return 'body:0'
  if (e.kind === 'FACE') return `face:${e.faceId}`
  return `edge:${e.edgeId}`
}

/** Utility: compute triangle area from vertex positions. */
export function triangleArea(
  p0: [number,number,number],
  p1: [number,number,number],
  p2: [number,number,number],
): number {
  const ax = p1[0]-p0[0], ay = p1[1]-p0[1], az = p1[2]-p0[2]
  const bx = p2[0]-p0[0], by = p2[1]-p0[1], bz = p2[2]-p0[2]
  const cx = ay*bz - az*by
  const cy = az*bx - ax*bz
  const cz = ax*by - ay*bx
  return 0.5 * Math.sqrt(cx*cx + cy*cy + cz*cz)
}
