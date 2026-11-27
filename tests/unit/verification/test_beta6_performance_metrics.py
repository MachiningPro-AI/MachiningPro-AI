"""Phase Z — Performance metrics tests."""

import time
import pytest
from backend.verification.performance_metrics import (
    TimingResult,
    PerformanceReport,
    time_call,
    time_calls,
)


def _noop(*args, **kwargs):
    return "result"


def _slow(n=0.001):
    time.sleep(n)
    return n


class TestTimingResult:
    def test_as_report_all_fields(self):
        tr = TimingResult(
            label="test",
            sample_count=3,
            median_ms=12.5,
            min_ms=10.0,
            max_ms=15.0,
            all_samples_ms=[10.0, 12.5, 15.0],
        )
        r = tr.as_report()
        assert r["label"] == "test"
        assert r["sample_count"] == 3
        assert r["median_ms"] == pytest.approx(12.5, abs=0.1)
        assert r["min_ms"] == pytest.approx(10.0, abs=0.1)
        assert r["max_ms"] == pytest.approx(15.0, abs=0.1)

    def test_none_values_in_report(self):
        tr = TimingResult(label="empty")
        r = tr.as_report()
        assert r["median_ms"] is None
        assert r["min_ms"] is None
        assert r["max_ms"] is None


class TestTimeCall:
    def test_returns_result_and_timing(self):
        result, tr = time_call("noop", _noop)
        assert result == "result"
        assert isinstance(tr, TimingResult)

    def test_elapsed_positive(self):
        _, tr = time_call("noop", _noop)
        assert tr.median_ms >= 0.0

    def test_sample_count_one(self):
        _, tr = time_call("noop", _noop)
        assert tr.sample_count == 1

    def test_slow_function_measured(self):
        _, tr = time_call("slow", _slow, 0.005)
        assert tr.median_ms >= 4.0  # at least 4ms for 5ms sleep

    def test_args_forwarded(self):
        result, _ = time_call("noop", lambda x, y: x + y, 2, 3)
        assert result == 5

    def test_kwargs_forwarded(self):
        def add(a=0, b=0):
            return a + b
        result, _ = time_call("add", add, a=10, b=20)
        assert result == 30


class TestTimeCalls:
    def test_returns_results_list(self):
        args_list = [(i,) for i in range(3)]
        results, tr = time_calls("batch", lambda x: x * 2, args_list)
        assert results == [0, 2, 4]

    def test_sample_count_matches(self):
        args_list = [(i,) for i in range(5)]
        _, tr = time_calls("batch", _noop, args_list)
        assert tr.sample_count == 5

    def test_median_between_min_max(self):
        args_list = [(0.001,), (0.005,), (0.003,)]
        _, tr = time_calls("slow_batch", _slow, args_list)
        assert tr.min_ms <= tr.median_ms <= tr.max_ms

    def test_empty_list_returns_empty(self):
        results, tr = time_calls("empty", _noop, [])
        assert results == []
        assert tr.sample_count == 0
        assert tr.median_ms is None


class TestPerformanceReport:
    def test_empty_report(self):
        rpt = PerformanceReport()
        d = rpt.as_report()
        assert d == {}

    def test_filled_report_has_key(self):
        tr = TimingResult(label="brep", sample_count=1,
                          median_ms=50.0, min_ms=50.0, max_ms=50.0)
        rpt = PerformanceReport(tool_brep_build=tr)
        d = rpt.as_report()
        assert "TOOL_BREP_BUILD_MS" in d
        assert d["TOOL_BREP_BUILD_MS"]["median_ms"] == pytest.approx(50.0, abs=0.1)

    def test_none_fields_absent(self):
        rpt = PerformanceReport(stock_boolean=None)
        d = rpt.as_report()
        assert "STOCK_BOOLEAN_MS" not in d
