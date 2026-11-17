"""
STEP/B-Rep foundation — P10 Phase 3.

Provides gmsh-based STEP parsing, B-Rep topology wiring, surface classification,
hole candidate detection, verification adapter, and in-house benchmark generation.

HARD RULES:
  - is_dispatchable=False and production_released=False always.
  - IN_HOUSE_BENCHMARK files are never called REAL_EXTERNAL_SAMPLE.
  - No fabricated topology, body/face counts, or bounding boxes.
  - Parser failure is fail-closed: status=FAILED, never silent downgrade.
"""

from __future__ import annotations

from backend.step_brep.benchmark_generator import (
    IN_HOUSE_BENCHMARK_STEP_DIR,
    generate_all_benchmarks,
    generate_p10_s1,
    generate_p10_s2,
    generate_p10_s3,
)
from backend.step_brep.feature_detector import (
    HoleCandidateRecord,
    detect_hole_candidates,
)
from backend.step_brep.gmsh_step_parser import (
    StepFaceSummary,
    StepImportRecord,
    parse_step_file,
)
from backend.step_brep.surface_classifier import (
    SurfaceClass,
    classify_surface,
    is_circular_curve,
)
from backend.step_brep.topology_adapter import build_canonical_topology
from backend.step_brep.verification_adapter import build_step_verification_input

__all__ = [
    "IN_HOUSE_BENCHMARK_STEP_DIR",
    "HoleCandidateRecord",
    "StepFaceSummary",
    "StepImportRecord",
    "SurfaceClass",
    "build_canonical_topology",
    "build_step_verification_input",
    "classify_surface",
    "detect_hole_candidates",
    "generate_all_benchmarks",
    "generate_p10_s1",
    "generate_p10_s2",
    "generate_p10_s3",
    "is_circular_curve",
    "parse_step_file",
]
