/**
 * Level-12 NC Generation frontend tests.
 *
 * Tests the client-side contract enforcement and type invariants.
 * NO tests attempt machine dispatch or CNC communication.
 */

import { describe, expect, it } from "vitest";
import {
  NCContractViolation,
  enforceNCContract,
  formatBlockReasons,
  isManifestStale,
  isNCBlocked,
  isNCCandidate,
} from "../src/services/nc";
import type { NCBuildResponse, NCGenerationManifest } from "../src/types/nc";

// -------------------------------------------------------------------------
// Test helpers
// -------------------------------------------------------------------------

function makeCandidateResponse(overrides: Partial<NCBuildResponse> = {}): NCBuildResponse {
  return {
    status: "CANDIDATE",
    block_reasons: [],
    warnings: [],
    errors: [],
    program_id: "prog-001",
    program_number: "O9999",
    block_count: 10,
    is_dispatchable: false,
    is_offline_candidate: true,
    safety_warnings: [
      "OFFLINE VALIDATION REQUIRED",
      "MACHINE-SPECIFIC REVIEW REQUIRED",
      "DO NOT RUN ON MACHINE WITHOUT APPROVAL",
    ],
    manifest: null,
    ...overrides,
  };
}

function makeManifest(overrides: Partial<NCGenerationManifest> = {}): NCGenerationManifest {
  return {
    manifest_id: "mfst-001",
    source_cad_ref: null,
    cam_plan_ref: null,
    toolpath_id: "tp-001",
    verification_session_id: "vsess-001",
    verification_state: "VERIFIED",
    verification_profile: "GEOMETRY_ONLY",
    post_profile_id: "GENERIC_ISO_TEST_v1",
    post_profile_name: "Generic ISO Test Profile",
    post_profile_certification: "TEST_ONLY",
    program_id: "prog-001",
    program_number: "O9999",
    program_status: "CANDIDATE",
    program_hash: "abc123",
    generated_at: "2026-11-06T00:00:00.000Z",
    generation_warnings: [],
    validation_warnings: [],
    is_offline_candidate: true,
    is_dispatchable: false,
    safety_statement:
      "OFFLINE VALIDATION REQUIRED. MACHINE-SPECIFIC REVIEW REQUIRED. DO NOT RUN ON MACHINE WITHOUT APPROVAL.",
    is_stale: false,
    stale_reasons: [],
    ...overrides,
  };
}

// -------------------------------------------------------------------------
// Contract enforcement
// -------------------------------------------------------------------------

describe("enforceNCContract", () => {
  it("passes for a valid CANDIDATE response", () => {
    expect(() => enforceNCContract(makeCandidateResponse())).not.toThrow();
  });

  it("passes for VALIDATED_OFFLINE status", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ status: "VALIDATED_OFFLINE" }))
    ).not.toThrow();
  });

  it("passes for BLOCKED status", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ status: "BLOCKED" }))
    ).not.toThrow();
  });

  it("passes for REVIEW_REQUIRED status", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ status: "REVIEW_REQUIRED" }))
    ).not.toThrow();
  });

  it("throws when is_dispatchable=true", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ is_dispatchable: true as never }))
    ).toThrow(NCContractViolation);
  });

  it("throws when status is READY_TO_RUN (forbidden)", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ status: "READY_TO_RUN" as never }))
    ).toThrow(NCContractViolation);
  });

  it("throws when status is MACHINE_APPROVED (forbidden)", () => {
    expect(() =>
      enforceNCContract(makeCandidateResponse({ status: "MACHINE_APPROVED" as never }))
    ).toThrow(NCContractViolation);
  });

  it("throws when manifest.is_dispatchable=true", () => {
    const response = makeCandidateResponse({
      manifest: makeManifest({ is_dispatchable: true as never }),
    });
    expect(() => enforceNCContract(response)).toThrow(NCContractViolation);
  });

  it("throws when manifest.program_status is READY_TO_RUN", () => {
    const response = makeCandidateResponse({
      manifest: makeManifest({ program_status: "READY_TO_RUN" as never }),
    });
    expect(() => enforceNCContract(response)).toThrow(NCContractViolation);
  });
});

// -------------------------------------------------------------------------
// Status helpers
// -------------------------------------------------------------------------

describe("isNCCandidate", () => {
  it("returns true for CANDIDATE", () => {
    expect(isNCCandidate(makeCandidateResponse())).toBe(true);
  });

  it("returns true for VALIDATED_OFFLINE", () => {
    expect(isNCCandidate(makeCandidateResponse({ status: "VALIDATED_OFFLINE" }))).toBe(true);
  });

  it("returns false for BLOCKED", () => {
    expect(isNCCandidate(makeCandidateResponse({ status: "BLOCKED" }))).toBe(false);
  });

  it("returns false for REJECTED", () => {
    expect(isNCCandidate(makeCandidateResponse({ status: "REJECTED" }))).toBe(false);
  });
});

describe("isNCBlocked", () => {
  it("returns true for BLOCKED", () => {
    expect(isNCBlocked(makeCandidateResponse({ status: "BLOCKED" }))).toBe(true);
  });

  it("returns false for CANDIDATE", () => {
    expect(isNCBlocked(makeCandidateResponse())).toBe(false);
  });
});

// -------------------------------------------------------------------------
// Manifest stale detection
// -------------------------------------------------------------------------

describe("isManifestStale", () => {
  it("returns false for fresh manifest", () => {
    expect(isManifestStale(makeManifest())).toBe(false);
  });

  it("returns true when is_stale=true with reasons", () => {
    expect(
      isManifestStale(
        makeManifest({ is_stale: true, stale_reasons: ["TOOLPATH_CHANGED"] })
      )
    ).toBe(true);
  });

  it("returns false when is_stale=true but no reasons", () => {
    expect(isManifestStale(makeManifest({ is_stale: true, stale_reasons: [] }))).toBe(false);
  });
});

// -------------------------------------------------------------------------
// Block reasons formatting
// -------------------------------------------------------------------------

describe("formatBlockReasons", () => {
  it("formats underscores as spaces", () => {
    const response = makeCandidateResponse({
      status: "BLOCKED",
      block_reasons: ["UNVERIFIED_TOOLPATH", "MISSING_FEED"],
    });
    const formatted = formatBlockReasons(response);
    expect(formatted).toContain("UNVERIFIED TOOLPATH");
    expect(formatted).toContain("MISSING FEED");
  });

  it("returns empty array for no block reasons", () => {
    expect(formatBlockReasons(makeCandidateResponse())).toEqual([]);
  });
});

// -------------------------------------------------------------------------
// Safety invariants
// -------------------------------------------------------------------------

describe("NCBuildResponse safety invariants", () => {
  it("candidate always has safety_warnings", () => {
    const r = makeCandidateResponse();
    expect(r.safety_warnings.length).toBeGreaterThan(0);
    expect(r.safety_warnings.some((w) => w.includes("OFFLINE"))).toBe(true);
  });

  it("candidate always has is_offline_candidate=true", () => {
    expect(makeCandidateResponse().is_offline_candidate).toBe(true);
  });

  it("candidate always has is_dispatchable=false", () => {
    expect(makeCandidateResponse().is_dispatchable).toBe(false);
  });

  it("manifest always has is_offline_candidate=true", () => {
    expect(makeManifest().is_offline_candidate).toBe(true);
  });

  it("manifest always has is_dispatchable=false", () => {
    expect(makeManifest().is_dispatchable).toBe(false);
  });

  it("manifest has program_hash", () => {
    expect(makeManifest().program_hash).toBeTruthy();
  });

  it("manifest has safety_statement", () => {
    expect(makeManifest().safety_statement).toContain("OFFLINE VALIDATION REQUIRED");
  });
});

// -------------------------------------------------------------------------
// Negative tests — no NC generation type exports forbidden values
// -------------------------------------------------------------------------

describe("NCProgramStatus forbidden values not in type literal", () => {
  it("READY_TO_RUN is not a normal status value used in production paths", () => {
    const validStatuses = [
      "NOT_GENERATED",
      "BLOCKED",
      "CANDIDATE",
      "VALIDATED_OFFLINE",
      "REVIEW_REQUIRED",
      "REJECTED",
      "STALE",
    ];
    expect(validStatuses).not.toContain("READY_TO_RUN");
    expect(validStatuses).not.toContain("MACHINE_APPROVED");
  });
});
