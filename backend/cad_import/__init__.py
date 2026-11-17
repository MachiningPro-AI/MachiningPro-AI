"""CAD import pipeline — STEP/B-Rep intake and topology extraction.

P10-B: Fail-closed STEP qualification intake.

Status: STEP_IMPORT_READY=NO (cadquery not installed)
  Real STEP qualification remains DEFERRED_REAL_STEP_SAMPLE_REQUIRED.
  This package provides the intake gate and schema that will be populated
  once real STEP samples are available and cadquery is installed.

HARD RULES:
  - Do NOT fabricate STEP files or claim real qualification without real evidence.
  - GOUGE_VALIDATED remains NOT_VERIFIABLE until real STEP samples qualify.
  - REAL_STEP_SAMPLE_COUNT=0 until physical files are present and pass intake.
"""

from backend.cad_import.step_intake import (
    StepIntakeRequest,
    StepIntakeResult,
    StepIntakeStatus,
    accept_step_file,
    scan_step_samples,
)

__all__ = [
    "StepIntakeRequest",
    "StepIntakeResult",
    "StepIntakeStatus",
    "accept_step_file",
    "scan_step_samples",
]
