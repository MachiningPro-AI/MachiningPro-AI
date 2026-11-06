/**
 * Level-12 NC Generation service.
 *
 * Client contract enforcement:
 * - is_dispatchable MUST always be false
 * - NCProgramStatus MUST NOT be READY_TO_RUN or MACHINE_APPROVED
 * - CANDIDATE is an offline artifact, not a machine-ready program
 *
 * NO CNC DISPATCH. NO SEND-TO-MACHINE. OFFLINE CANDIDATE ONLY.
 */

import type {
  NCBuildRequest,
  NCBuildResponse,
  NCGenerationManifest,
  NCProgramStatus,
  NCValidateResponse,
  PostProcessorProfileSummary,
} from "../types/nc";

/** Thrown when the NC program contract is violated. */
export class NCContractViolation extends Error {
  constructor(message: string) {
    super(`NCContractViolation: ${message}`);
    this.name = "NCContractViolation";
  }
}

/** Statuses that must never appear in Level-12 output. */
const FORBIDDEN_STATUSES: NCProgramStatus[] = ["READY_TO_RUN" as NCProgramStatus, "MACHINE_APPROVED" as NCProgramStatus];

/**
 * Enforce the NC generation contract on a build response.
 * Throws NCContractViolation if any invariant is broken.
 */
export function enforceNCContract(response: NCBuildResponse): void {
  if (response.is_dispatchable) {
    throw new NCContractViolation(
      "NCBuildResponse.is_dispatchable=true — this is never permitted at Level 12"
    );
  }
  if (FORBIDDEN_STATUSES.includes(response.status)) {
    throw new NCContractViolation(
      `NCBuildResponse.status=${response.status} — forbidden at Level 12`
    );
  }
  if (response.manifest && response.manifest.is_dispatchable) {
    throw new NCContractViolation(
      "NCGenerationManifest.is_dispatchable=true — this is never permitted"
    );
  }
  if (response.manifest && FORBIDDEN_STATUSES.includes(response.manifest.program_status)) {
    throw new NCContractViolation(
      `Manifest program_status=${response.manifest.program_status} — forbidden`
    );
  }
}

/** Returns true when the NC build response is a successful offline candidate. */
export function isNCCandidate(response: NCBuildResponse): boolean {
  return (
    response.status === "CANDIDATE" ||
    response.status === "VALIDATED_OFFLINE"
  );
}

/** Returns true when NC generation was blocked. */
export function isNCBlocked(response: NCBuildResponse): boolean {
  return response.status === "BLOCKED";
}

/** Returns true when the manifest indicates the program is stale. */
export function isManifestStale(manifest: NCGenerationManifest): boolean {
  return manifest.is_stale && manifest.stale_reasons.length > 0;
}

/** Count NC blocks of a given element kind. */
export function countBlocksByKind(response: NCBuildResponse, _kind: string): number {
  // Block count returned by server; kind-level counting requires full NCProgram
  return response.block_count;
}

/** Format block reasons for UI display. */
export function formatBlockReasons(response: NCBuildResponse): string[] {
  return response.block_reasons.map((r) => r.replace(/_/g, " "));
}

// -------------------------------------------------------------------------
// API client functions
// -------------------------------------------------------------------------

export async function requestNCBuild(
  request: NCBuildRequest,
  token: string
): Promise<NCBuildResponse> {
  const resp = await fetch("/api/nc/build", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(request),
  });
  if (!resp.ok) {
    throw new Error(`NC build failed: ${resp.status} ${resp.statusText}`);
  }
  const data: NCBuildResponse = await resp.json();
  enforceNCContract(data);
  return data;
}

export async function requestNCValidate(
  programId: string,
  profileId: string,
  token: string,
  toolpathId?: string
): Promise<NCValidateResponse> {
  const resp = await fetch("/api/nc/validate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      program_id: programId,
      profile_id: profileId,
      toolpath_id: toolpathId,
    }),
  });
  if (!resp.ok) {
    throw new Error(`NC validate failed: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchNCProfiles(token: string): Promise<PostProcessorProfileSummary[]> {
  const resp = await fetch("/api/nc/profiles", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    throw new Error(`Fetch profiles failed: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}
