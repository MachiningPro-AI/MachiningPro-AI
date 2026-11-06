"""
Level-12 NC Generation Manifest, hash, and stale detection.

NCGenerationManifest captures provenance of a generated NC candidate.
Hash detects post-generation modification.
is_dispatchable is always False at Level 12.

NO_CNC_DISPATCH=YES  OFFLINE_ONLY=YES
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .enums import NCProgramStatus, NCStaleReason


class NCGenerationManifest(BaseModel):
    """
    Full provenance record for a generated NC candidate.

    DO NOT use program_hash as proof of machine safety.
    It detects post-generation modification only.
    """

    manifest_id: str
    # source references
    source_cad_ref: str | None = None
    cam_plan_ref: str | None = None
    toolpath_id: str | None = None
    # Level-11 verification
    verification_session_id: str | None = None
    verification_state: str = "UNKNOWN"
    verification_profile: str = "UNKNOWN"
    # postprocessor
    post_profile_id: str
    post_profile_name: str
    post_profile_certification: str
    # program
    program_id: str
    program_number: str
    program_status: NCProgramStatus
    # hash
    program_hash: str  # SHA-256 of program block content
    # timestamps
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds")
    )
    # warnings from generation and validation
    generation_warnings: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    # safety invariants — always stated in manifest
    is_offline_candidate: bool = True
    is_dispatchable: bool = False
    safety_statement: str = (
        "OFFLINE VALIDATION REQUIRED. "
        "MACHINE-SPECIFIC REVIEW REQUIRED. "
        "DO NOT RUN ON MACHINE WITHOUT APPROVAL."
    )
    # stale tracking
    is_stale: bool = False
    stale_reasons: list[str] = Field(default_factory=list)


def build_manifest(
    *,
    manifest_id: str,
    toolpath_id: str | None,
    verification_session_id: str | None,
    verification_state: str,
    verification_profile: str,
    post_profile_id: str,
    post_profile_name: str,
    post_profile_certification: str,
    program_id: str,
    program_number: str,
    program_status: NCProgramStatus,
    program_blocks_json: str,
    generation_warnings: list[str] | None = None,
    validation_warnings: list[str] | None = None,
    source_cad_ref: str | None = None,
    cam_plan_ref: str | None = None,
) -> NCGenerationManifest:
    program_hash = hashlib.sha256(program_blocks_json.encode()).hexdigest()
    return NCGenerationManifest(
        manifest_id=manifest_id,
        source_cad_ref=source_cad_ref,
        cam_plan_ref=cam_plan_ref,
        toolpath_id=toolpath_id,
        verification_session_id=verification_session_id,
        verification_state=verification_state,
        verification_profile=verification_profile,
        post_profile_id=post_profile_id,
        post_profile_name=post_profile_name,
        post_profile_certification=post_profile_certification,
        program_id=program_id,
        program_number=program_number,
        program_status=program_status,
        program_hash=program_hash,
        generation_warnings=generation_warnings or [],
        validation_warnings=validation_warnings or [],
        is_offline_candidate=True,
        is_dispatchable=False,
    )


def check_manifest_staleness(
    manifest: NCGenerationManifest,
    current_toolpath_id: str | None,
    current_verification_session_id: str | None,
    current_profile_id: str,
) -> tuple[bool, list[NCStaleReason]]:
    """Return (is_stale, reasons)."""
    reasons: list[NCStaleReason] = []

    if manifest.toolpath_id and manifest.toolpath_id != current_toolpath_id:
        reasons.append(NCStaleReason.TOOLPATH_CHANGED)

    if (
        manifest.verification_session_id
        and manifest.verification_session_id != current_verification_session_id
    ):
        reasons.append(NCStaleReason.VERIFICATION_CHANGED)

    if manifest.post_profile_id != current_profile_id:
        reasons.append(NCStaleReason.PROFILE_CHANGED)

    return bool(reasons), reasons


def serialize_blocks_for_hash(program_blocks: list) -> str:
    """Deterministic JSON serialization of program blocks for hashing."""
    return json.dumps(
        [b.model_dump() if hasattr(b, "model_dump") else b for b in program_blocks],
        sort_keys=True,
        default=str,
    )
