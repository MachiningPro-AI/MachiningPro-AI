"""Stage dependency graph, topological ordering, and invalidation logic."""
from __future__ import annotations

from .enums import WorkflowMode, WorkflowStage

# ---------------------------------------------------------------------------
# Explicit dependency map — stage → set of stages that must PASS before it runs
# ---------------------------------------------------------------------------

STAGE_DEPENDENCIES: dict[WorkflowStage, frozenset[WorkflowStage]] = {
    WorkflowStage.CAD_IMPORT:              frozenset(),
    WorkflowStage.GEOMETRY:               frozenset({WorkflowStage.CAD_IMPORT}),
    WorkflowStage.FEATURE_RECOGNITION:    frozenset({WorkflowStage.GEOMETRY}),
    WorkflowStage.DFM:                    frozenset({WorkflowStage.FEATURE_RECOGNITION}),
    WorkflowStage.PROCESS_PLANNING:       frozenset({WorkflowStage.FEATURE_RECOGNITION}),
    WorkflowStage.MACHINE_SELECTION:      frozenset({WorkflowStage.PROCESS_PLANNING}),
    WorkflowStage.TOOL_SELECTION:         frozenset({WorkflowStage.PROCESS_PLANNING}),
    WorkflowStage.CUTTING_DATA:           frozenset({
        WorkflowStage.TOOL_SELECTION,
        WorkflowStage.MACHINE_SELECTION,
    }),
    WorkflowStage.CYCLE_TIME:             frozenset({WorkflowStage.CUTTING_DATA}),
    WorkflowStage.COST_RFQ:              frozenset({WorkflowStage.CYCLE_TIME}),
    WorkflowStage.CAM_PLANNING:           frozenset({
        WorkflowStage.PROCESS_PLANNING,
        WorkflowStage.TOOL_SELECTION,
    }),
    WorkflowStage.TOOLPATH:              frozenset({WorkflowStage.CAM_PLANNING}),
    WorkflowStage.VERIFICATION:          frozenset({WorkflowStage.TOOLPATH}),
    WorkflowStage.NC_CANDIDATE:          frozenset({WorkflowStage.VERIFICATION}),
    WorkflowStage.SCHEDULING:            frozenset({WorkflowStage.MACHINE_SELECTION}),
    WorkflowStage.JOB_ASSIGNMENT:        frozenset({
        WorkflowStage.SCHEDULING,
        WorkflowStage.MACHINE_SELECTION,
    }),
    WorkflowStage.ADAPTIVE_INTELLIGENCE: frozenset({WorkflowStage.PROCESS_PLANNING}),
    WorkflowStage.DIGITAL_TWIN:          frozenset({
        WorkflowStage.MACHINE_SELECTION,
        WorkflowStage.CUTTING_DATA,
    }),
    WorkflowStage.FINAL_MANUFACTURING_PLAN: frozenset({WorkflowStage.PROCESS_PLANNING}),
}

# ---------------------------------------------------------------------------
# Invalidation graph — if stage X changes, invalidate these downstream stages
# ---------------------------------------------------------------------------

INVALIDATION_MAP: dict[str, frozenset[WorkflowStage]] = {
    "CAD_CHANGE": frozenset({
        WorkflowStage.GEOMETRY,
        WorkflowStage.FEATURE_RECOGNITION,
        WorkflowStage.DFM,
        WorkflowStage.PROCESS_PLANNING,
        WorkflowStage.MACHINE_SELECTION,
        WorkflowStage.TOOL_SELECTION,
        WorkflowStage.CUTTING_DATA,
        WorkflowStage.CYCLE_TIME,
        WorkflowStage.COST_RFQ,
        WorkflowStage.CAM_PLANNING,
        WorkflowStage.TOOLPATH,
        WorkflowStage.VERIFICATION,
        WorkflowStage.NC_CANDIDATE,
        WorkflowStage.SCHEDULING,
        WorkflowStage.JOB_ASSIGNMENT,
        WorkflowStage.ADAPTIVE_INTELLIGENCE,
        WorkflowStage.DIGITAL_TWIN,
        WorkflowStage.FINAL_MANUFACTURING_PLAN,
    }),
    "MATERIAL_CHANGE": frozenset({
        WorkflowStage.DFM,
        WorkflowStage.CUTTING_DATA,
        WorkflowStage.CYCLE_TIME,
        WorkflowStage.COST_RFQ,
        WorkflowStage.CAM_PLANNING,
        WorkflowStage.TOOLPATH,
        WorkflowStage.VERIFICATION,
        WorkflowStage.NC_CANDIDATE,
        WorkflowStage.ADAPTIVE_INTELLIGENCE,
        WorkflowStage.DIGITAL_TWIN,
        WorkflowStage.FINAL_MANUFACTURING_PLAN,
    }),
    "TOOL_CHANGE": frozenset({
        WorkflowStage.CUTTING_DATA,
        WorkflowStage.CYCLE_TIME,
        WorkflowStage.COST_RFQ,
        WorkflowStage.CAM_PLANNING,
        WorkflowStage.TOOLPATH,
        WorkflowStage.VERIFICATION,
        WorkflowStage.NC_CANDIDATE,
        WorkflowStage.ADAPTIVE_INTELLIGENCE,
        WorkflowStage.DIGITAL_TWIN,
        WorkflowStage.FINAL_MANUFACTURING_PLAN,
    }),
    "MACHINE_CHANGE": frozenset({
        WorkflowStage.CUTTING_DATA,
        WorkflowStage.CYCLE_TIME,
        WorkflowStage.COST_RFQ,
        WorkflowStage.CAM_PLANNING,
        WorkflowStage.TOOLPATH,
        WorkflowStage.VERIFICATION,
        WorkflowStage.NC_CANDIDATE,
        WorkflowStage.SCHEDULING,
        WorkflowStage.JOB_ASSIGNMENT,
        WorkflowStage.DIGITAL_TWIN,
        WorkflowStage.FINAL_MANUFACTURING_PLAN,
    }),
    "COST_INPUT_CHANGE": frozenset({
        WorkflowStage.COST_RFQ,
        WorkflowStage.FINAL_MANUFACTURING_PLAN,
    }),
}

# ---------------------------------------------------------------------------
# Stages required by each WorkflowMode
# ---------------------------------------------------------------------------

_ANALYSIS_STAGES = {
    WorkflowStage.CAD_IMPORT,
    WorkflowStage.GEOMETRY,
    WorkflowStage.FEATURE_RECOGNITION,
}

_DFM_STAGES = _ANALYSIS_STAGES | {WorkflowStage.DFM}

_QUOTE_STAGES = _DFM_STAGES | {
    WorkflowStage.PROCESS_PLANNING,
    WorkflowStage.MACHINE_SELECTION,
    WorkflowStage.TOOL_SELECTION,
    WorkflowStage.CUTTING_DATA,
    WorkflowStage.CYCLE_TIME,
    WorkflowStage.COST_RFQ,
}

_MACHINE_SELECTION_STAGES = _ANALYSIS_STAGES | {
    WorkflowStage.PROCESS_PLANNING,
    WorkflowStage.MACHINE_SELECTION,
}

_CAM_PLAN_STAGES = _DFM_STAGES | {
    WorkflowStage.PROCESS_PLANNING,
    WorkflowStage.MACHINE_SELECTION,
    WorkflowStage.TOOL_SELECTION,
    WorkflowStage.CUTTING_DATA,
    WorkflowStage.CAM_PLANNING,
}

_CAM_TOOLPATH_STAGES = _CAM_PLAN_STAGES | {
    WorkflowStage.TOOLPATH,
    WorkflowStage.VERIFICATION,
}

_OFFLINE_NC_STAGES = _CAM_TOOLPATH_STAGES | {WorkflowStage.NC_CANDIDATE}

_FULL_STAGES = frozenset(WorkflowStage)

MODE_STAGES: dict[WorkflowMode, frozenset[WorkflowStage]] = {
    WorkflowMode.ANALYSIS_ONLY:        frozenset(_ANALYSIS_STAGES),
    WorkflowMode.DFM_ONLY:             frozenset(_DFM_STAGES),
    WorkflowMode.QUOTE_ONLY:           frozenset(_QUOTE_STAGES),
    WorkflowMode.MACHINE_SELECTION:    frozenset(_MACHINE_SELECTION_STAGES),
    WorkflowMode.CAM_PLAN_ONLY:        frozenset(_CAM_PLAN_STAGES),
    WorkflowMode.CAM_AND_TOOLPATH:     frozenset(_CAM_TOOLPATH_STAGES),
    WorkflowMode.OFFLINE_NC:           frozenset(_OFFLINE_NC_STAGES),
    WorkflowMode.FULL_MANUFACTURING_PLAN: _FULL_STAGES,
}


def required_stages(mode: WorkflowMode) -> frozenset[WorkflowStage]:
    return MODE_STAGES[mode]


def execution_order(stages: frozenset[WorkflowStage]) -> list[WorkflowStage]:
    """Return stages in topological dependency order using Kahn's algorithm."""
    in_degree: dict[WorkflowStage, int] = {s: 0 for s in stages}
    for stage in stages:
        for dep in STAGE_DEPENDENCIES.get(stage, frozenset()):
            if dep in stages:
                in_degree[stage] += 1

    ready = sorted([s for s, d in in_degree.items() if d == 0], key=lambda s: s.value)
    result: list[WorkflowStage] = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for other in sorted(stages, key=lambda s: s.value):
            if current in STAGE_DEPENDENCIES.get(other, frozenset()):
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    ready.append(other)
    return result


def invalidated_by(change_key: str) -> frozenset[WorkflowStage]:
    """Return stages that must be re-run after a named input change."""
    return INVALIDATION_MAP.get(change_key, frozenset())


def dependencies_satisfied(
    stage: WorkflowStage,
    stage_statuses: dict[WorkflowStage, str],
) -> tuple[bool, list[str]]:
    """Return (ok, reasons) — ok=True when all required deps have PASS status."""
    reasons: list[str] = []
    for dep in STAGE_DEPENDENCIES.get(stage, frozenset()):
        status = stage_statuses.get(dep, "NOT_STARTED")
        if status not in ("PASS", "PARTIAL"):
            reasons.append(f"Dependency {dep} has status {status}")
    return (len(reasons) == 0, reasons)
