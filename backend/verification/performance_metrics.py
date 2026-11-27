"""
Phase Z — Performance Metrics

Measure actual execution timing for all Phase N-V operations.
Never invents performance limits.

Wraps timed calls and collects:
  MEDIAN, MIN, MAX over SAMPLE_COUNT samples.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TimingResult:
    label: str
    sample_count: int = 0
    median_ms: float | None = None
    min_ms: float | None = None
    max_ms: float | None = None
    all_samples_ms: list[float] = field(default_factory=list)

    def as_report(self) -> dict:
        return {
            "label": self.label,
            "sample_count": self.sample_count,
            "median_ms": round(self.median_ms, 1) if self.median_ms is not None else None,
            "min_ms": round(self.min_ms, 1) if self.min_ms is not None else None,
            "max_ms": round(self.max_ms, 1) if self.max_ms is not None else None,
        }


def time_call(label: str, fn: Callable, *args, **kwargs) -> tuple[any, TimingResult]:
    """Execute fn once and return (result, TimingResult)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    tr = TimingResult(
        label=label,
        sample_count=1,
        median_ms=elapsed_ms,
        min_ms=elapsed_ms,
        max_ms=elapsed_ms,
        all_samples_ms=[elapsed_ms],
    )
    return result, tr


def time_calls(
    label: str, fn: Callable, args_list: list, kwargs_list: list | None = None
) -> tuple[list, TimingResult]:
    """Execute fn for each args in args_list, collect timing stats."""
    if kwargs_list is None:
        kwargs_list = [{} for _ in args_list]

    samples_ms = []
    results = []
    for args, kwargs in zip(args_list, kwargs_list, strict=False):
        t0 = time.perf_counter()
        r = fn(*args, **kwargs)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
        results.append(r)

    if not samples_ms:
        return results, TimingResult(label=label)

    tr = TimingResult(
        label=label,
        sample_count=len(samples_ms),
        median_ms=statistics.median(samples_ms),
        min_ms=min(samples_ms),
        max_ms=max(samples_ms),
        all_samples_ms=samples_ms,
    )
    return results, tr


@dataclass
class PerformanceReport:
    tool_brep_build: TimingResult | None = None
    holder_brep_build: TimingResult | None = None
    assembly_build: TimingResult | None = None
    stock_boolean: TimingResult | None = None
    gouge_boolean: TimingResult | None = None
    exact_volume: TimingResult | None = None
    machine_kinematics: TimingResult | None = None
    collision: TimingResult | None = None
    total_high_fidelity: TimingResult | None = None

    def as_report(self) -> dict:
        out = {}
        for field_name, tr in self.__dict__.items():
            if tr is not None:
                out[field_name.upper() + "_MS"] = tr.as_report()
        return out
