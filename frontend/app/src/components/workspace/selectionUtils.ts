/**
 * selectionUtils — mesh-level selection geometry utilities.
 *
 * All computations use engineering/world-space coordinates.
 * No B-Rep fabrication: boundary edges are labeled MESH_EDGE.
 */

import * as THREE from 'three'
import type { MeshFaceGroup } from '../../services/engineeringImport'
import type { SelectedFace, SelectedEdge } from './WorkspaceTypes'
import { triangleArea } from '../../hooks/useSelectionState'

// ---------------------------------------------------------------------------
// Face resolution
// ---------------------------------------------------------------------------

/**
 * Given a raycast intersection triangle index, find the face_group that
 * contains it. Returns the group (CAD_FACE) or synthesises a MESH_FACE entry.
 */
export function resolveFace(
  triIndex: number,
  faceGroups: MeshFaceGroup[] | undefined,
  positions: number[],
  indices: number[],
  hit: THREE.Intersection,
): SelectedFace {
  const hitPt: [number,number,number] = [hit.point.x, hit.point.y, hit.point.z]
  const faceNormal = hit.face?.normal ?? new THREE.Vector3(0,1,0)
  const normalArr: [number,number,number] = [faceNormal.x, faceNormal.y, faceNormal.z]

  if (faceGroups && faceGroups.length > 0) {
    for (const fg of faceGroups) {
      if (triIndex >= fg.tri_start && triIndex < fg.tri_start + fg.tri_count) {
        const area = sumGroupArea(fg.tri_start, fg.tri_count, positions, indices)
        return {
          kind: 'FACE',
          entityClass: 'CAD_FACE',
          faceId: fg.entity_tag,
          label: `Face ${fg.entity_tag}`,
          triIndex,
          hitPoint: hitPt,
          normal: normalArr,
          triStart: fg.tri_start,
          triCount: fg.tri_count,
          estimatedAreaUnits2: area,
        }
      }
    }
  }

  // No group match — emit MESH_FACE
  return {
    kind: 'FACE',
    entityClass: 'MESH_FACE',
    faceId: triIndex,
    label: `Mesh Face ${triIndex}`,
    triIndex,
    hitPoint: hitPt,
    normal: normalArr,
    triStart: triIndex,
    triCount: 1,
    estimatedAreaUnits2: singleTriArea(triIndex, positions, indices),
  }
}

function sumGroupArea(
  triStart: number,
  triCount: number,
  positions: number[],
  indices: number[],
): number {
  let area = 0
  for (let i = triStart; i < triStart + triCount; i++) {
    area += singleTriArea(i, positions, indices)
  }
  return area
}

function singleTriArea(triIdx: number, positions: number[], indices: number[]): number {
  const base = triIdx * 3
  if (base + 2 >= indices.length) return 0
  const i0 = indices[base]! * 3
  const i1 = indices[base+1]! * 3
  const i2 = indices[base+2]! * 3
  if (i2 + 2 >= positions.length) return 0
  const p0: [number,number,number] = [positions[i0]!, positions[i0+1]!, positions[i0+2]!]
  const p1: [number,number,number] = [positions[i1]!, positions[i1+1]!, positions[i1+2]!]
  const p2: [number,number,number] = [positions[i2]!, positions[i2+1]!, positions[i2+2]!]
  return triangleArea(p0, p1, p2)
}

// ---------------------------------------------------------------------------
// Boundary edge extraction (MESH_EDGE)
// ---------------------------------------------------------------------------

/**
 * Extract boundary / silhouette edges from a triangular mesh.
 * Returns a list of vertex-pair indices for edges that belong to exactly
 * one triangle (open boundary).  Labeled MESH_EDGE — not B-Rep edges.
 *
 * Performance: O(n) pass over triangles; suitable for preview meshes up to
 * ~100k triangles without BVH.
 */
export function extractBoundaryEdges(
  indices: number[],
  positions: number[],
): Array<[[number,number,number],[number,number,number]]> {
  // Edge key → occurrence count
  const edgeCount = new Map<string, number>()
  const edgeVerts = new Map<string, [[number,number,number],[number,number,number]]>()

  const triCount = Math.floor(indices.length / 3)
  for (let i = 0; i < triCount; i++) {
    const a = indices[i*3]!
    const b = indices[i*3+1]!
    const c = indices[i*3+2]!
    for (const [v0, v1] of [[a,b],[b,c],[c,a]] as [number,number][]) {
      const key = v0 < v1 ? `${v0}_${v1}` : `${v1}_${v0}`
      edgeCount.set(key, (edgeCount.get(key) ?? 0) + 1)
      if (!edgeVerts.has(key)) {
        const p0: [number,number,number] = [positions[v0*3]!, positions[v0*3+1]!, positions[v0*3+2]!]
        const p1: [number,number,number] = [positions[v1*3]!, positions[v1*3+1]!, positions[v1*3+2]!]
        edgeVerts.set(key, [p0, p1])
      }
    }
  }

  const result: Array<[[number,number,number],[number,number,number]]> = []
  for (const [key, count] of edgeCount) {
    if (count === 1) {
      result.push(edgeVerts.get(key)!)
    }
  }
  return result
}

/**
 * Build a SelectedEdge from a pair of boundary-edge points.
 * Class is always MESH_EDGE — not a B-Rep edge.
 */
export function buildMeshEdgeSelection(
  p0: [number,number,number],
  p1: [number,number,number],
  edgeIndex: number,
): SelectedEdge {
  const dx = p1[0]-p0[0], dy = p1[1]-p0[1], dz = p1[2]-p0[2]
  const len = Math.sqrt(dx*dx + dy*dy + dz*dz)
  const id = `mesh_edge_${edgeIndex}`
  return {
    kind: 'EDGE',
    entityClass: 'MESH_EDGE',
    edgeId: id,
    label: `Mesh Edge ${edgeIndex}`,
    points: [p0, p1],
    lengthUnits: len,
  }
}

// ---------------------------------------------------------------------------
// Highlight geometry builders
// ---------------------------------------------------------------------------

/** Build a highlight mesh (emissive overlay) for the selected triangle group. */
export function buildFaceHighlightGeometry(
  triStart: number,
  triCount: number,
  positions: number[],
  indices: number[],
): THREE.BufferGeometry {
  const verts: number[] = []
  for (let i = triStart; i < triStart + triCount; i++) {
    const base = i * 3
    for (let j = 0; j < 3; j++) {
      const vi = indices[base+j]! * 3
      verts.push(positions[vi]!, positions[vi+1]!, positions[vi+2]!)
    }
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
  geo.computeVertexNormals()
  return geo
}

/** Build a LINE_SEGMENTS geometry outlining a face group. */
export function buildFaceOutlineGeometry(
  triStart: number,
  triCount: number,
  positions: number[],
  indices: number[],
): THREE.BufferGeometry {
  const lineVerts: number[] = []
  for (let i = triStart; i < triStart + triCount; i++) {
    const base = i * 3
    const iA = indices[base]! * 3
    const iB = indices[base+1]! * 3
    const iC = indices[base+2]! * 3
    // Three edges of triangle
    lineVerts.push(
      positions[iA]!, positions[iA+1]!, positions[iA+2]!,
      positions[iB]!, positions[iB+1]!, positions[iB+2]!,
      positions[iB]!, positions[iB+1]!, positions[iB+2]!,
      positions[iC]!, positions[iC+1]!, positions[iC+2]!,
      positions[iC]!, positions[iC+1]!, positions[iC+2]!,
      positions[iA]!, positions[iA+1]!, positions[iA+2]!,
    )
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(lineVerts, 3))
  return geo
}

/** Build geometry for a polyline edge. */
export function buildEdgeGeometry(
  points: [number,number,number][],
): THREE.BufferGeometry {
  const verts: number[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]!, b = points[i+1]!
    verts.push(a[0],a[1],a[2], b[0],b[1],b[2])
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
  return geo
}

// ---------------------------------------------------------------------------
// Measurement geometry
// ---------------------------------------------------------------------------

/** Build a dashed line geometry between two world points for measurement viz. */
export function buildMeasurementLineGeometry(
  a: [number,number,number],
  b: [number,number,number],
): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b], 3))
  return geo
}
