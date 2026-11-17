"""
P10-E: Advanced holemaking assessment — DXF-02 60mm feature.

Provides a bounded, fail-closed assessment of viable machining strategies for
large-diameter features where standard drilling is not viable.

Assessed strategies for DXF-02 ≈60 mm feature:
  BORING             — single-point tool traversal of bore diameter
  HELICAL_INTERPOLATION — end mill following a helical path
  LARGE_DRILLING     — oversize drill (not viable for 60mm; no such tool in catalog)
  REAMING            — finishing pass after rough bore (requires pre-bore)
  UNSUPPORTED        — architecture does not safely support this strategy

HARD RULES:
  - Do NOT create fake boring bars, inserts, cutting data, or machine capability.
  - Do NOT auto-approve any strategy without architecture + tool + machine evidence.
  - If architecture does not safely support a method: DXF02_STATUS=DEFERRED_CAPABILITY_GAP.
  - is_dispatchable=False at all times.
  - production_released=False at all times.

Current status: DXF02_STATUS=DEFERRED_CAPABILITY_GAP
  - Boring bar exists in catalog (sandvik-a25t-sducr-11, min_bore=32mm).
  - No boring CAM strategy implemented in nc/ or cam_planning/.
  - No helical interpolation toolpath generator.
  - No large-diameter drill (60mm) in tool catalog.
  - No pre-bore workflow for reaming.
  - Architecture gap: CAM strategy for bore diameter > drill catalog maximum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "HolemakingStrategy",
    "HolemakingStrategyStatus",
    "HolemakingFeatureClass",
    "HolemakingAssessment",
    "HolemakingStrategyResult",
    "assess_large_hole_strategies",
    "DXF02_ADVANCED_HOLEMAKING_STATUS",
]

# P10-E status constant (MUST 17)
DXF02_ADVANCED_HOLEMAKING_STATUS: str = "DEFERRED_CAPABILITY_GAP"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HolemakingStrategy(StrEnum):
    """Candidate machining strategies for large-diameter hole features."""
    BORING = "BORING"
    HELICAL_INTERPOLATION = "HELICAL_INTERPOLATION"
    LARGE_DRILLING = "LARGE_DRILLING"
    REAMING = "REAMING"
    UNSUPPORTED = "UNSUPPORTED"


class HolemakingStrategyStatus(StrEnum):
    """Assessment result for a candidate strategy."""
    VIABLE = "VIABLE"               # all required conditions met
    CONDITIONAL = "CONDITIONAL"     # viable if additional evidence supplied
    DEFERRED = "DEFERRED"           # requires capability gap to be filled
    NOT_VIABLE = "NOT_VIABLE"       # definitively cannot work for this feature
    UNSUPPORTED = "UNSUPPORTED"     # architecture does not support this strategy


class HolemakingFeatureClass(StrEnum):
    """Classification of the hole feature geometry."""
    STANDARD_DRILL      = "STANDARD_DRILL"       # ≤12mm, circular profile
    LARGE_DRILL         = "LARGE_DRILL"           # 12–50mm, requires special drill or boring
    PRECISION_BORE      = "PRECISION_BORE"        # any diameter, tight tolerance (IT7+)
    LARGE_BORE          = "LARGE_BORE"            # >50mm, standard drilling not viable
    HELICAL_POCKET      = "HELICAL_POCKET"  # large diameter, pocket entrance, no existing bore
    UNKNOWN             = "UNKNOWN"


# ---------------------------------------------------------------------------
# Assessment dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HolemakingStrategyResult:
    """Assessment result for one strategy applied to one feature.

    status:
        VIABLE      — all required architecture, tool, and machine conditions met.
        CONDITIONAL — viable if the engineer supplies additional evidence.
        DEFERRED    — requires a capability gap in architecture/library to be filled first.
        NOT_VIABLE  — definitively cannot work (e.g. drill too large, no tool).
        UNSUPPORTED — architecture does not implement this strategy.

    gap_summary:
        Human-readable description of what is missing.
    """
    strategy: HolemakingStrategy
    status: HolemakingStrategyStatus
    gap_summary: str
    toolpath_generator_exists: bool = False
    tool_exists_in_catalog: bool = False
    machine_capability_verified: bool = False
    cam_strategy_exists: bool = False


@dataclass
class HolemakingAssessment:
    """Full holemaking assessment for a large-diameter feature.

    feature_diameter_mm:
        Measured or extracted feature diameter.
    feature_depth_mm:
        Estimated or stated depth. None if unknown.
    feature_class:
        Classification of the feature geometry.
    strategy_results:
        Assessment for each candidate strategy.
    recommended_strategy:
        The most viable strategy, or UNSUPPORTED if none.
    deferral_reason:
        Human-readable reason for deferral (if status=DEFERRED_CAPABILITY_GAP).
    is_dispatchable:
        Always False.
    production_released:
        Always False.
    """
    feature_diameter_mm: float
    feature_depth_mm: float | None
    feature_class: HolemakingFeatureClass
    strategy_results: list[HolemakingStrategyResult]
    recommended_strategy: HolemakingStrategy
    deferral_status: str
    deferral_reason: str
    warnings: list[str] = field(default_factory=list)

    # Safety invariants
    is_dispatchable: bool = False
    production_released: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)


# ---------------------------------------------------------------------------
# assess_large_hole_strategies
# ---------------------------------------------------------------------------


def assess_large_hole_strategies(
    diameter_mm: float,
    depth_mm: float | None = None,
    *,
    catalog_max_drill_mm: float = 24.0,
    boring_bar_min_bore_mm: float = 32.0,
    has_boring_cam: bool = False,
    has_helical_cam: bool = False,
) -> HolemakingAssessment:
    """Assess viable strategies for a large-diameter hole feature.

    Parameters
    ----------
    diameter_mm:
        Feature diameter in mm. For DXF-02 ≈ 60 mm.
    depth_mm:
        Feature depth in mm. None if unknown.
    catalog_max_drill_mm:
        Maximum drill diameter available in the tool catalog.
        Default 24.0mm (Sandvik 860-1-2400 = largest in P7-D catalog).
    boring_bar_min_bore_mm:
        Minimum bore diameter for available boring bar.
        Default 32.0mm (sandvik-a25t-sducr-11 published min bore).
    has_boring_cam:
        True when a boring CAM strategy is implemented in nc/cam_planning/.
        Default False (not implemented).
    has_helical_cam:
        True when helical interpolation toolpath generator is implemented.
        Default False (not implemented).

    Returns
    -------
    HolemakingAssessment with per-strategy status and overall recommendation.
    """
    warnings: list[str] = []

    # Feature classification
    if diameter_mm > 50.0:
        feature_class = HolemakingFeatureClass.LARGE_BORE
    elif diameter_mm > 12.0:
        feature_class = HolemakingFeatureClass.LARGE_DRILL
    else:
        feature_class = HolemakingFeatureClass.STANDARD_DRILL

    # ---- BORING ----
    if diameter_mm < boring_bar_min_bore_mm:
        boring_status = HolemakingStrategyStatus.NOT_VIABLE
        boring_gap = (
            f"Feature diameter {diameter_mm}mm < boring bar minimum bore "
            f"{boring_bar_min_bore_mm}mm. Bar cannot enter bore."
        )
    elif not has_boring_cam:
        boring_status = HolemakingStrategyStatus.DEFERRED
        boring_gap = (
            "Boring CAM strategy not implemented in nc/ or cam_planning/. "
            "Architecture gap: no boring toolpath generator. "
            "Boring bar sandvik-a25t-sducr-11 exists in catalog "
            f"(min bore {boring_bar_min_bore_mm}mm; feature {diameter_mm}mm — "
            "bar would fit geometrically). "
            "DEFERRED until boring toolpath generator implemented."
        )
    else:
        boring_status = HolemakingStrategyStatus.VIABLE
        boring_gap = "Boring bar fits and CAM strategy available."

    boring_result = HolemakingStrategyResult(
        strategy=HolemakingStrategy.BORING,
        status=boring_status,
        gap_summary=boring_gap,
        toolpath_generator_exists=has_boring_cam,
        tool_exists_in_catalog=True,   # sandvik-a25t-sducr-11 is in catalog
        machine_capability_verified=False,  # no claim without real STEP + machine spec
        cam_strategy_exists=has_boring_cam,
    )

    # ---- HELICAL INTERPOLATION ----
    if not has_helical_cam:
        helical_status = HolemakingStrategyStatus.DEFERRED
        helical_gap = (
            "Helical interpolation toolpath generator not implemented. "
            "Architecture gap: nc/ generates linear drill segments only; "
            "no helical milling strategy available. "
            "An end mill approaching a 60mm bore would require helical interpolation. "
            "DEFERRED until helical toolpath generator implemented and "
            "suitable end mill added to catalog."
        )
    else:
        helical_status = HolemakingStrategyStatus.VIABLE
        helical_gap = "Helical CAM strategy available."

    helical_result = HolemakingStrategyResult(
        strategy=HolemakingStrategy.HELICAL_INTERPOLATION,
        status=helical_status,
        gap_summary=helical_gap,
        toolpath_generator_exists=has_helical_cam,
        tool_exists_in_catalog=False,  # no large-diameter end mill for 60mm bore
        machine_capability_verified=False,
        cam_strategy_exists=has_helical_cam,
    )

    # ---- LARGE DRILLING ----
    if diameter_mm > catalog_max_drill_mm:
        large_drill_status = HolemakingStrategyStatus.NOT_VIABLE
        large_drill_gap = (
            f"No drill in catalog for {diameter_mm}mm. "
            f"Catalog maximum: {catalog_max_drill_mm}mm "
            f"(sandvik-860-1-2400-110a1-pm). "
            "Standard drilling cannot produce a 60mm feature. "
            "NOT_VIABLE: would require a specialised step drill or gun drill "
            "not present in catalog and not architecturally supported."
        )
    else:
        large_drill_status = HolemakingStrategyStatus.VIABLE
        large_drill_gap = "Drill exists in catalog."

    large_drill_result = HolemakingStrategyResult(
        strategy=HolemakingStrategy.LARGE_DRILLING,
        status=large_drill_status,
        gap_summary=large_drill_gap,
        toolpath_generator_exists=True,  # drilling toolpath generator exists
        tool_exists_in_catalog=False,     # no 60mm drill
        machine_capability_verified=False,
        cam_strategy_exists=True,         # but toolpath strategy exists for drills
    )

    # ---- REAMING ----
    # Reaming requires a pre-drilled bore at a compatible diameter,
    # then a finishing pass. For 60mm, the pre-bore would need boring or helical.
    if diameter_mm > catalog_max_drill_mm:
        reaming_status = HolemakingStrategyStatus.DEFERRED
        reaming_gap = (
            f"Reaming {diameter_mm}mm requires a pre-drilled / pre-bored hole. "
            "Pre-bore workflow requires boring CAM (not implemented). "
            f"No {diameter_mm}mm reamer in catalog. "
            "DEFERRED: depends on boring or helical pre-bore capability being available first."
        )
    else:
        reaming_status = HolemakingStrategyStatus.CONDITIONAL
        reaming_gap = "Pre-bore required; engineer must supply pre-bore plan."

    reaming_result = HolemakingStrategyResult(
        strategy=HolemakingStrategy.REAMING,
        status=reaming_status,
        gap_summary=reaming_gap,
        toolpath_generator_exists=True,  # reaming uses drilling toolpath
        tool_exists_in_catalog=False,    # no 60mm reamer in catalog
        machine_capability_verified=False,
        cam_strategy_exists=True,
    )

    # ---- Determine recommended strategy ----
    # Priority: VIABLE > CONDITIONAL > DEFERRED > NOT_VIABLE > UNSUPPORTED
    all_results = [boring_result, helical_result, large_drill_result, reaming_result]

    viable = [r for r in all_results if r.status == HolemakingStrategyStatus.VIABLE]
    conditional = [r for r in all_results if r.status == HolemakingStrategyStatus.CONDITIONAL]
    deferred = [r for r in all_results if r.status == HolemakingStrategyStatus.DEFERRED]

    if viable:
        recommended = viable[0].strategy
    elif conditional:
        recommended = conditional[0].strategy
    elif deferred:
        recommended = deferred[0].strategy
    else:
        recommended = HolemakingStrategy.UNSUPPORTED

    # Determine overall deferral status
    has_viable = bool(viable)
    if has_viable:
        deferral_status = "VIABLE_STRATEGY_AVAILABLE"
        deferral_reason = (
            f"At least one viable strategy for {diameter_mm}mm: "
            + ", ".join(r.strategy for r in viable)
        )
    else:
        deferral_status = DXF02_ADVANCED_HOLEMAKING_STATUS
        deferral_reason = (
            f"No viable strategy available for {diameter_mm}mm feature. "
            "Required capability gaps: boring CAM strategy and/or helical interpolation "
            "toolpath generator. DXF02_STATUS=DEFERRED_CAPABILITY_GAP per P10-E MUST 17."
        )
        warnings.append(
            "DXF02_DEFERRED_CAPABILITY_GAP: "
            "No implemented CAM strategy can machine a 60mm feature. "
            "Boring bar catalog record exists (sandvik-a25t-sducr-11) but "
            "boring toolpath generator is not implemented. "
            "Helical interpolation not implemented. "
            "Large drilling not viable (no 60mm drill). "
            "HARD_RULE: do NOT auto-approve or fabricate boring bar data."
        )

    return HolemakingAssessment(
        feature_diameter_mm=diameter_mm,
        feature_depth_mm=depth_mm,
        feature_class=feature_class,
        strategy_results=all_results,
        recommended_strategy=recommended,
        deferral_status=deferral_status,
        deferral_reason=deferral_reason,
        warnings=warnings,
    )
