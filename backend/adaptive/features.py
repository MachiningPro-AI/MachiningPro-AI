"""Level-16 Feature vector extraction with deterministic normalization."""

from __future__ import annotations

from .models import FeatureVector, ManufacturingLearningRecord

# Known material categories for one-hot encoding
_KNOWN_MATERIALS = [
    "AL_6082_T6",
    "AL_7075_T6",
    "SS_304",
    "SS_316L",
    "ST_42CRMO4",
    "ST_C45",
    "CAST_IRON_GG25",
    "TITANIUM_TI6AL4V",
]

# Known machine classes for one-hot encoding
_KNOWN_MACHINE_CLASSES = [
    "CNC_TURNING_CENTER",
    "THREE_AXIS_MILL",
    "FIVE_AXIS_MILL",
    "CNC_LATHE",
    "GRINDING_CENTER",
]

# Known operation types for one-hot encoding
_KNOWN_OPS = [
    "ROUGH_TURNING",
    "FINISH_TURNING",
    "ROUGH_MILLING",
    "FINISH_MILLING",
    "DRILLING",
    "BORING",
    "REAMING",
    "THREADING",
]

# Domain bounds for normalization (min, max) — from engineering knowledge
_BOUNDS: dict[str, tuple[float, float]] = {
    "vc": (10.0, 1500.0),
    "fn": (0.01, 2.0),
    "ap": (0.05, 25.0),
    "ae": (0.05, 100.0),
    "planned_cycle_time": (5.0, 7200.0),
    "planned_tool_life": (5.0, 500.0),
}


def _normalize(value: float, low: float, high: float) -> float | None:
    if high <= low:
        return None
    if value < low or value > high:
        return None  # out of domain — do not clip silently
    return (value - low) / (high - low)


def extract_features(record: ManufacturingLearningRecord) -> FeatureVector:
    features: dict[str, float | None] = {}
    missing: list[str] = []
    ood_reasons: list[str] = []

    # Numerical cutting data features from planned set
    for key in ("vc", "fn", "ap", "ae"):
        val = record.planned_cutting_data.get(key)
        if val is None:
            missing.append(f"cutting_data.{key}")
            features[f"plan_{key}"] = None
        else:
            norm = _normalize(float(val), *_BOUNDS[key])
            if norm is None:
                ood_reasons.append(f"plan_{key} out of normalization bounds: {val}")
                features[f"plan_{key}"] = None
            else:
                features[f"plan_{key}"] = norm

    # Planned cycle time
    pct = record.planned_cycle_time
    if pct is None:
        missing.append("planned_cycle_time")
        features["plan_ct_norm"] = None
    else:
        norm = _normalize(pct, *_BOUNDS["planned_cycle_time"])
        if norm is None:
            ood_reasons.append(f"planned_cycle_time out of bounds: {pct}")
            features["plan_ct_norm"] = None
        else:
            features["plan_ct_norm"] = norm

    # Planned tool life
    ptl = record.planned_tool_life
    if ptl is None:
        missing.append("planned_tool_life")
        features["plan_tl_norm"] = None
    else:
        norm = _normalize(ptl, *_BOUNDS["planned_tool_life"])
        if norm is None:
            ood_reasons.append(f"planned_tool_life out of bounds: {ptl}")
            features["plan_tl_norm"] = None
        else:
            features["plan_tl_norm"] = norm

    # Material one-hot
    mat = record.material
    if mat is None:
        missing.append("material")
        for m in _KNOWN_MATERIALS:
            features[f"mat_{m}"] = None
    elif mat not in _KNOWN_MATERIALS:
        ood_reasons.append(f"material '{mat}' not in training distribution")
        for m in _KNOWN_MATERIALS:
            features[f"mat_{m}"] = 0.0
    else:
        for m in _KNOWN_MATERIALS:
            features[f"mat_{m}"] = 1.0 if m == mat else 0.0

    # Machine class one-hot
    mc = record.machine_class
    if mc is None:
        missing.append("machine_class")
        for c in _KNOWN_MACHINE_CLASSES:
            features[f"mc_{c}"] = None
    elif mc not in _KNOWN_MACHINE_CLASSES:
        ood_reasons.append(f"machine_class '{mc}' not in training distribution")
        for c in _KNOWN_MACHINE_CLASSES:
            features[f"mc_{c}"] = 0.0
    else:
        for c in _KNOWN_MACHINE_CLASSES:
            features[f"mc_{c}"] = 1.0 if c == mc else 0.0

    # Operation type one-hot
    op = record.operation_type
    if op is None:
        missing.append("operation_type")
        for o in _KNOWN_OPS:
            features[f"op_{o}"] = None
    elif op not in _KNOWN_OPS:
        ood_reasons.append(f"operation_type '{op}' not in training distribution")
        for o in _KNOWN_OPS:
            features[f"op_{o}"] = 0.0
    else:
        for o in _KNOWN_OPS:
            features[f"op_{o}"] = 1.0 if o == op else 0.0

    is_complete = len(missing) == 0
    out_of_domain = len(ood_reasons) > 0

    return FeatureVector(
        record_id=record.record_id,
        features=features,
        missing_features=missing,
        is_complete=is_complete,
        data_quality=record.data_quality,
        out_of_domain=out_of_domain,
        out_of_domain_reasons=ood_reasons,
    )


def compute_known_features(fv: FeatureVector) -> dict[str, float]:
    """Return only the known (non-None) features for distance computation."""
    return {k: v for k, v in fv.features.items() if v is not None}
