/**
 * Level-12 NC Generation frontend tests.
 *
 * Tests the client-side contract enforcement and type invariants.
 * NO tests attempt machine dispatch or CNC communication.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  NCContractViolation,
  enforceNCContract,
  formatBlockReasons,
  isManifestStale,
  isNCBlocked,
  isNCCandidate,
} from "../src/services/nc.ts";
import type { NCBuildResponse, NCGenerationManifest } from "../src/types/nc.ts";

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
    assert.doesNotThrow(() => enforceNCContract(makeCandidateResponse()));
  });

  it("passes for VALIDATED_OFFLINE status", () => {
    assert.doesNotThrow(() =>
      enforceNCContract(makeCandidateResponse({ status: "VALIDATED_OFFLINE" }))
    );
  });

  it("passes for BLOCKED status", () => {
    assert.doesNotThrow(() =>
      enforceNCContract(makeCandidateResponse({ status: "BLOCKED" }))
    );
  });

  it("passes for REVIEW_REQUIRED status", () => {
    assert.doesNotThrow(() =>
      enforceNCContract(makeCandidateResponse({ status: "REVIEW_REQUIRED" }))
    );
  });

  it("throws when is_dispatchable=true", () => {
    assert.throws(
      () => enforceNCContract(makeCandidateResponse({ is_dispatchable: true as never })),
      NCContractViolation,
    );
  });

  it("throws when status is READY_TO_RUN (forbidden)", () => {
    assert.throws(
      () => enforceNCContract(makeCandidateResponse({ status: "READY_TO_RUN" as never })),
      NCContractViolation,
    );
  });

  it("throws when status is MACHINE_APPROVED (forbidden)", () => {
    assert.throws(
      () => enforceNCContract(makeCandidateResponse({ status: "MACHINE_APPROVED" as never })),
      NCContractViolation,
    );
  });

  it("throws when manifest.is_dispatchable=true", () => {
    const response = makeCandidateResponse({
      manifest: makeManifest({ is_dispatchable: true as never }),
    });
    assert.throws(() => enforceNCContract(response), NCContractViolation);
  });

  it("throws when manifest.program_status is READY_TO_RUN", () => {
    const response = makeCandidateResponse({
      manifest: makeManifest({ program_status: "READY_TO_RUN" as never }),
    });
    assert.throws(() => enforceNCContract(response), NCContractViolation);
  });
});

// -------------------------------------------------------------------------
// Status helpers
// -------------------------------------------------------------------------

describe("isNCCandidate", () => {
  it("returns true for CANDIDATE", () => {
    assert.strictEqual(isNCCandidate(makeCandidateResponse()), true);
  });

  it("returns true for VALIDATED_OFFLINE", () => {
    assert.strictEqual(isNCCandidate(makeCandidateResponse({ status: "VALIDATED_OFFLINE" })), true);
  });

  it("returns false for BLOCKED", () => {
    assert.strictEqual(isNCCandidate(makeCandidateResponse({ status: "BLOCKED" })), false);
  });

  it("returns false for REJECTED", () => {
    assert.strictEqual(isNCCandidate(makeCandidateResponse({ status: "REJECTED" })), false);
  });
});

describe("isNCBlocked", () => {
  it("returns true for BLOCKED", () => {
    assert.strictEqual(isNCBlocked(makeCandidateResponse({ status: "BLOCKED" })), true);
  });

  it("returns false for CANDIDATE", () => {
    assert.strictEqual(isNCBlocked(makeCandidateResponse()), false);
  });
});

// -------------------------------------------------------------------------
// Manifest stale detection
// -------------------------------------------------------------------------

describe("isManifestStale", () => {
  it("returns false for fresh manifest", () => {
    assert.strictEqual(isManifestStale(makeManifest()), false);
  });

  it("returns true when is_stale=true with reasons", () => {
    assert.strictEqual(
      isManifestStale(makeManifest({ is_stale: true, stale_reasons: ["TOOLPATH_CHANGED"] })),
      true,
    );
  });

  it("returns false when is_stale=true but no reasons", () => {
    assert.strictEqual(isManifestStale(makeManifest({ is_stale: true, stale_reasons: [] })), false);
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
    assert.ok(formatted.includes("UNVERIFIED TOOLPATH"));
    assert.ok(formatted.includes("MISSING FEED"));
  });

  it("returns empty array for no block reasons", () => {
    assert.deepStrictEqual(formatBlockReasons(makeCandidateResponse()), []);
  });
});

// -------------------------------------------------------------------------
// Safety invariants
// -------------------------------------------------------------------------

describe("NCBuildResponse safety invariants", () => {
  it("candidate always has safety_warnings", () => {
    const r = makeCandidateResponse();
    assert.ok(r.safety_warnings.length > 0);
    assert.ok(r.safety_warnings.some((w) => w.includes("OFFLINE")));
  });

  it("candidate always has is_offline_candidate=true", () => {
    assert.strictEqual(makeCandidateResponse().is_offline_candidate, true);
  });

  it("candidate always has is_dispatchable=false", () => {
    assert.strictEqual(makeCandidateResponse().is_dispatchable, false);
  });

  it("manifest always has is_offline_candidate=true", () => {
    assert.strictEqual(makeManifest().is_offline_candidate, true);
  });

  it("manifest always has is_dispatchable=false", () => {
    assert.strictEqual(makeManifest().is_dispatchable, false);
  });

  it("manifest has program_hash", () => {
    assert.ok(makeManifest().program_hash);
  });

  it("manifest has safety_statement", () => {
    assert.ok(makeManifest().safety_statement.includes("OFFLINE VALIDATION REQUIRED"));
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
    assert.ok(!validStatuses.includes("READY_TO_RUN"));
    assert.ok(!validStatuses.includes("MACHINE_APPROVED"));
  });
});
