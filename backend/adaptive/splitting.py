"""Level-16 Train/validation/test splitting — group-aware to prevent leakage."""

from __future__ import annotations

from .enums import SplitRole
from .models import ManufacturingLearningRecord, SplitResult

_MIN_TRAIN = 3


def split_records(
    records: list[ManufacturingLearningRecord],
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    group_by: str | None = None,
) -> SplitResult:
    """
    Assign SplitRole to each record.

    When group_by is provided (e.g. 'part_family'), all records of a group
    are assigned to the same split to prevent label leakage.
    Returns SplitResult with counts and IDs — does NOT evaluate on training data.
    """
    warnings: list[str] = []

    if abs(train_ratio + validation_ratio + test_ratio - 1.0) > 1e-6:
        warnings.append(
            "SPLIT_RATIOS_DO_NOT_SUM_TO_ONE — using 0.70/0.15/0.15"
        )
        train_ratio, validation_ratio, test_ratio = 0.70, 0.15, 0.15

    if not records:
        return SplitResult(warnings=["NO_RECORDS_TO_SPLIT"])

    if len(records) < _MIN_TRAIN:
        return SplitResult(
            total=len(records),
            warnings=[f"INSUFFICIENT_RECORDS — need at least {_MIN_TRAIN}, got {len(records)}"],
        )

    if group_by:
        return _group_split(records, train_ratio, validation_ratio, test_ratio, group_by, warnings)
    return _random_deterministic_split(records, train_ratio, validation_ratio, warnings)


def _group_split(
    records: list[ManufacturingLearningRecord],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    group_by: str,
    warnings: list[str],
) -> SplitResult:
    # Collect groups in stable order (first appearance)
    group_order: list[str] = []
    groups: dict[str, list[ManufacturingLearningRecord]] = {}
    for r in records:
        key = getattr(r, group_by, None) or "UNKNOWN"
        if key not in groups:
            group_order.append(key)
            groups[key] = []
        groups[key].append(r)

    n_groups = len(group_order)
    n_val = max(1, round(n_groups * val_ratio))
    n_test = max(1, round(n_groups * test_ratio))
    n_train = n_groups - n_val - n_test
    if n_train < 1:
        warnings.append(
            "TOO_FEW_GROUPS_FOR_SPLIT — assigning all groups to TRAIN"
        )
        n_train, n_val, n_test = n_groups, 0, 0

    train_ids: list[str] = []
    val_ids: list[str] = []
    test_ids: list[str] = []

    for i, key in enumerate(group_order):
        if i < n_train:
            role = SplitRole.TRAIN
            train_ids.extend(r.record_id for r in groups[key])
        elif i < n_train + n_val:
            role = SplitRole.VALIDATION
            val_ids.extend(r.record_id for r in groups[key])
        else:
            role = SplitRole.TEST
            test_ids.extend(r.record_id for r in groups[key])
        for r in groups[key]:
            r.split_role = role

    return SplitResult(
        total=len(records),
        train_count=len(train_ids),
        validation_count=len(val_ids),
        test_count=len(test_ids),
        train_ids=train_ids,
        validation_ids=val_ids,
        test_ids=test_ids,
        group_aware=True,
        warnings=warnings,
    )


def _random_deterministic_split(
    records: list[ManufacturingLearningRecord],
    train_ratio: float,
    val_ratio: float,
    warnings: list[str],
) -> SplitResult:
    # Deterministic order by record_id (lexicographic)
    ordered = sorted(records, key=lambda r: r.record_id)
    n = len(ordered)
    n_train = max(1, round(n * train_ratio))
    n_val = max(1, round(n * val_ratio))
    n_test = n - n_train - n_val
    if n_test < 0:
        n_test = 0
        n_val = n - n_train
        warnings.append("ADJUSTED_VALIDATION_SIZE — test set became negative")

    train_ids: list[str] = []
    val_ids: list[str] = []
    test_ids: list[str] = []

    for i, r in enumerate(ordered):
        if i < n_train:
            r.split_role = SplitRole.TRAIN
            train_ids.append(r.record_id)
        elif i < n_train + n_val:
            r.split_role = SplitRole.VALIDATION
            val_ids.append(r.record_id)
        else:
            r.split_role = SplitRole.TEST
            test_ids.append(r.record_id)

    return SplitResult(
        total=n,
        train_count=len(train_ids),
        validation_count=len(val_ids),
        test_count=len(test_ids),
        train_ids=train_ids,
        validation_ids=val_ids,
        test_ids=test_ids,
        group_aware=False,
        warnings=warnings,
    )
