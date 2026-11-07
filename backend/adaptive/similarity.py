"""Level-16 Similar case retrieval with explicit similarity factors."""

from __future__ import annotations

import math

from .features import compute_known_features, extract_features
from .models import ManufacturingLearningRecord, SimilarCase


def _euclidean_distance(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = set(a.keys()) & set(b.keys())
    if not common:
        return None
    total = sum((a[k] - b[k]) ** 2 for k in common)
    return math.sqrt(total / len(common))


def _distance_to_similarity(dist: float) -> float:
    """Map Euclidean distance [0, ∞) to similarity score [0, 1]."""
    return 1.0 / (1.0 + dist)


def find_similar_cases(
    query: ManufacturingLearningRecord,
    candidates: list[ManufacturingLearningRecord],
    *,
    top_k: int = 5,
) -> list[SimilarCase]:
    """
    Return up to top_k most similar historical cases.

    Similarity is computed only over features present in both query and candidate.
    Cases with no common features are omitted.
    """
    if not candidates:
        return []

    query_fv = extract_features(query)
    query_known = compute_known_features(query_fv)

    if not query_known:
        return []

    scored: list[tuple[float, ManufacturingLearningRecord, dict[str, float]]] = []
    for cand in candidates:
        cand_fv = extract_features(cand)
        cand_known = compute_known_features(cand_fv)

        common_keys = set(query_known.keys()) & set(cand_known.keys())
        if not common_keys:
            continue

        q_sub = {k: query_known[k] for k in common_keys}
        c_sub = {k: cand_known[k] for k in common_keys}
        dist = _euclidean_distance(q_sub, c_sub)
        if dist is None:
            continue

        sim_score = _distance_to_similarity(dist)
        # Per-feature similarity factors
        factors: dict[str, float] = {
            k: _distance_to_similarity(abs(query_known[k] - cand_known[k]))
            for k in common_keys
        }
        scored.append((sim_score, cand, factors))

    scored.sort(key=lambda x: x[0], reverse=True)

    result: list[SimilarCase] = []
    for rank, (sim, cand, factors) in enumerate(scored[:top_k], start=1):
        matched = [k for k, v in factors.items() if v >= 0.9]
        result.append(SimilarCase(
            case_id=f"CASE_{rank:03d}_{cand.record_id}",
            record_ref=cand.record_id,
            similarity_score=round(sim, 6),
            similarity_factors=factors,
            matched_features=matched,
            actual_cycle_time=cand.actual_cycle_time,
            actual_tool_life=cand.actual_tool_life,
            quality_result=cand.quality_result,
        ))
    return result
