"""Level-16 Model registry — versioning, staleness detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .enums import ModelStatus
from .models import ModelSpec

_DEFAULT_STALENESS_DAYS = 30


class ModelRegistry:
    """In-memory model registry for the current session."""

    def __init__(self) -> None:
        self._registry: dict[str, ModelSpec] = {}  # model_id -> ModelSpec

    def register(self, spec: ModelSpec) -> None:
        self._registry[spec.model_id] = spec

    def get(self, model_id: str) -> ModelSpec | None:
        return self._registry.get(model_id)

    def list_all(self) -> list[ModelSpec]:
        return list(self._registry.values())

    def reject(self, model_id: str, reason: str = "") -> ModelSpec | None:
        spec = self._registry.get(model_id)
        if spec is None:
            return None
        updated = spec.model_copy(update={
            "status": ModelStatus.REJECTED,
            "limitations": spec.limitations + ([reason] if reason else []),
        })
        self._registry[model_id] = updated
        return updated

    def mark_validated(self, model_id: str) -> ModelSpec | None:
        spec = self._registry.get(model_id)
        if spec is None:
            return None
        if spec.status not in (ModelStatus.TRAINED, ModelStatus.REVIEW_REQUIRED):
            return spec
        updated = spec.model_copy(update={"status": ModelStatus.VALIDATED})
        self._registry[model_id] = updated
        return updated

    def mark_stale(self, model_id: str) -> ModelSpec | None:
        spec = self._registry.get(model_id)
        if spec is None:
            return None
        updated = spec.model_copy(update={"status": ModelStatus.STALE})
        self._registry[model_id] = updated
        return updated

    def check_staleness(
        self,
        staleness_days: int = _DEFAULT_STALENESS_DAYS,
    ) -> list[str]:
        """Return model_ids that are stale based on training timestamp."""
        stale_ids: list[str] = []
        cutoff = datetime.now(UTC) - timedelta(days=staleness_days)
        for model_id, spec in self._registry.items():
            if spec.status in (ModelStatus.STALE, ModelStatus.REJECTED):
                continue
            if spec.training_timestamp is None:
                stale_ids.append(model_id)
                continue
            try:
                ts = datetime.fromisoformat(spec.training_timestamp)
                if ts < cutoff:
                    stale_ids.append(model_id)
            except ValueError:
                stale_ids.append(model_id)
        return stale_ids

    def apply_staleness_check(
        self,
        staleness_days: int = _DEFAULT_STALENESS_DAYS,
    ) -> list[str]:
        """Mark stale models and return their IDs."""
        stale_ids = self.check_staleness(staleness_days)
        for model_id in stale_ids:
            self.mark_stale(model_id)
        return stale_ids


# Module-level default registry
_default_registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    return _default_registry


def reset_registry() -> None:
    global _default_registry
    _default_registry = ModelRegistry()
