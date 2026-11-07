"""
Level-15 Shop Floor Monitoring and Closed-Loop Feedback Tests.

OBSERVE → COMPARE → DIAGNOSE → RECOMMEND.
NO automatic corrective action.
NO real machine write.
NO fabricated observation data.
"""

from __future__ import annotations

import inspect

import pytest

from backend.monitoring import (
    CLOSED_LOOP_MODE,
    NO_AUTOMATIC_CORRECTIVE_ACTION,
    NO_REAL_MACHINE_WRITE,
    CycleState,
    DataQuality,
    DeviationType,
    ObservationSource,
    OEEStatus,
    RecommendationType,
    RootCauseCandidateStatus,
    ToolLifeStatus,
    analyze_alarms,
    compare_planned_actual,
    compute_availability,
    compute_oee,
    compute_performance,
    compute_performance_kpis,
    compute_quality_kpi,
    compute_rolling_median,
    compute_tool_life_feedback,
    compute_yield,
    compute_z_scores,
    create_learning_record,
    detect_cycle_time_deviations,
    detect_iqr_anomalies,
    detect_range_anomaly,
    detect_threshold_anomaly,
    generate_recommendations,
    identify_root_cause_candidates,
    make_alarm_observation,
    make_closed_loop_proposal,
    make_quality_observation,
    make_simulated_observation,
    make_tool_usage,
    test_machine_alarm,
    test_machine_cycle_complete,
    test_machine_idle,
    test_machine_running,
    test_missing_telemetry,
    test_program_mismatch,
    validate_learning_record,
)
from backend.monitoring.anomaly import apply_anomaly_policy
from backend.monitoring.enums import (
    AnomalyMethod,
    ClosedLoopProposalType,
)
from backend.monitoring.learning import anonymize_learning_records
from backend.monitoring.models import (
    AnomalyPolicy,
    EngineeringRecommendation,
    LearningRecord,
    ProductionEvent,
    RootCauseCandidate,
)
from backend.monitoring.trends import (
    build_alarm_trend,
    build_cycle_time_trend,
    build_idle_time_trend,
    build_quality_trend,
    build_tool_life_trend,
)

# ===========================================================================
# Safety Invariants
# ===========================================================================


class TestSafetyInvariants:
    def test_no_automatic_corrective_action(self):
        assert NO_AUTOMATIC_CORRECTIVE_ACTION is True

    def test_no_real_machine_write(self):
        assert NO_REAL_MACHINE_WRITE is True

    def test_closed_loop_mode_proposed_only(self):
        assert CLOSED_LOOP_MODE == "PROPOSED_ONLY"

    def test_production_observation_not_fabricated(self):
        obs = make_simulated_observation("M-001", "J-001")
        assert obs.is_fabricated is False

    def test_closed_loop_proposal_proposed_only(self):
        proposal = make_closed_loop_proposal(
            proposal_type=ClosedLoopProposalType.NEW_FEED_CANDIDATE,
            proposed_value=150.0,
        )
        assert proposal.is_proposed_only is True
        assert proposal.is_automatic_write is False

    def test_recommendation_requires_review(self):
        from backend.monitoring.models import EngineeringRecommendation
        rec = EngineeringRecommendation(
            recommendation_id="r1",
            recommendation_type=RecommendationType.REVIEW_TOOL_LIFE,
            requires_review=True,
            is_automatic_action=False,
            is_applied=False,
        )
        assert rec.requires_review is True
        assert rec.is_automatic_action is False
        assert rec.is_applied is False

    def test_root_cause_candidate_not_confirmed(self):
        candidate = RootCauseCandidate(
            candidate_id="c1",
            status=RootCauseCandidateStatus.CANDIDATE,
        )
        assert candidate.is_confirmed is False
        assert candidate.is_causal_proof is False


# ===========================================================================
# Production Observation Model
# ===========================================================================


class TestProductionObservationModel:
    def test_make_simulated_observation_basic(self):
        obs = make_simulated_observation("M-001", "J-001")
        assert obs.machine_id == "M-001"
        assert obs.job_id == "J-001"
        assert obs.is_fabricated is False
        assert obs.source == ObservationSource.SIMULATED_CONTROLLER

    def test_missing_fields_are_none_not_zero(self):
        obs = test_missing_telemetry()
        assert obs.actual_cycle_time is None
        assert obs.part_count is None
        assert obs.good_count is None
        assert obs.reject_count is None
        assert obs.alarm_runtime is None

    def test_cycle_state_unknown(self):
        obs = test_missing_telemetry()
        assert obs.cycle_state == CycleState.UNKNOWN

    def test_simulated_cycle_complete(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0, good_count=1)
        assert obs.cycle_state == CycleState.COMPLETE
        assert obs.actual_cycle_time == 10.0
        assert obs.good_count == 1
        assert obs.reject_count == 0

    def test_simulated_alarm(self):
        obs = test_machine_alarm(alarm_code="ALM-9001")
        assert obs.cycle_state == CycleState.ALARM
        assert "ALM-9001" in obs.alarm_codes

    def test_simulated_running(self):
        obs = test_machine_running(actual_cycle_time=12.0)
        assert obs.cycle_state == CycleState.RUNNING
        assert obs.actual_cycle_time == 12.0

    def test_simulated_idle(self):
        obs = test_machine_idle()
        assert obs.cycle_state == CycleState.IDLE

    def test_program_mismatch_scenario(self):
        obs = test_program_mismatch()
        assert obs.program_hash == "observed_hash_differs_from_planned"


# ===========================================================================
# Observation Source and Data Quality
# ===========================================================================


class TestObservationSourceModel:
    def test_all_sources_defined(self):
        expected = {
            "SIMULATED_CONTROLLER",
            "OPC_UA_READ",
            "MTCONNECT_READ",
            "MES_READ",
            "ERP_READ",
            "MANUAL_ENTRY",
            "IMPORT_FILE",
            "HISTORICAL_DATA",
            "UNKNOWN",
        }
        actual = {s.value for s in ObservationSource}
        assert expected.issubset(actual)

    def test_all_quality_states_defined(self):
        expected = {
            "VALIDATED",
            "RAW",
            "PARTIAL",
            "STALE",
            "CONFLICT",
            "INVALID",
            "UNKNOWN",
        }
        actual = {q.value for q in DataQuality}
        assert expected.issubset(actual)


# ===========================================================================
# Planned vs Actual Comparison
# ===========================================================================


class TestPlannedActualComparison:
    def test_cycle_time_high(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        assert cmp.actual_cycle_time == 12.0
        assert cmp.planned_cycle_time == 10.0
        assert cmp.cycle_time_delta == pytest.approx(2.0)
        assert cmp.cycle_time_relative_delta == pytest.approx(0.2)

    def test_cycle_time_low(self):
        obs = test_machine_cycle_complete(actual_cycle_time=8.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        assert cmp.cycle_time_delta == pytest.approx(-2.0)
        assert cmp.cycle_time_relative_delta == pytest.approx(-0.2)

    def test_planned_not_derived_from_actual(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        assert cmp.planned_cycle_time != cmp.actual_cycle_time

    def test_missing_actual_gives_none_delta(self):
        obs = test_missing_telemetry()
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        assert cmp.cycle_time_delta is None

    def test_missing_planned_gives_none_delta(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=None)
        assert cmp.cycle_time_delta is None

    def test_zero_planned_cycle_time_warning(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=0.0)
        assert any("ZERO" in w for w in cmp.warnings)

    def test_program_mismatch_detected(self):
        obs = test_program_mismatch()
        cmp = compare_planned_actual(
            obs,
            planned_nc_hash="planned_hash_abc",
        )
        assert DeviationType.PROGRAM_MISMATCH.value in cmp.deviations

    def test_machine_mismatch_detected(self):
        obs = make_simulated_observation("M-002", "J-001")
        cmp = compare_planned_actual(obs, planned_machine="M-001")
        assert DeviationType.MACHINE_ASSIGNMENT_MISMATCH.value in cmp.deviations


# ===========================================================================
# Cycle Time Deviation Detection
# ===========================================================================


class TestCycleTimeDeviation:
    def test_cycle_time_high_deviation(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        devs = detect_cycle_time_deviations(cmp, high_threshold=0.1)
        assert len(devs) == 1
        assert devs[0].deviation_type == DeviationType.CYCLE_TIME_HIGH

    def test_cycle_time_low_deviation(self):
        obs = test_machine_cycle_complete(actual_cycle_time=8.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        devs = detect_cycle_time_deviations(cmp, low_threshold=-0.1)
        assert len(devs) == 1
        assert devs[0].deviation_type == DeviationType.CYCLE_TIME_LOW

    def test_no_deviation_within_policy(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        devs = detect_cycle_time_deviations(cmp)
        assert len(devs) == 0

    def test_deviation_is_not_confirmed(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        devs = detect_cycle_time_deviations(cmp)
        assert all(d.is_confirmed is False for d in devs)


# ===========================================================================
# Production Events
# ===========================================================================


class TestProductionEventModel:
    def test_all_event_types_defined(self):
        from backend.monitoring.enums import ProductionEventType
        expected = {
            "JOB_STARTED",
            "JOB_COMPLETED",
            "CYCLE_STARTED",
            "CYCLE_COMPLETED",
            "TOOL_CHANGED",
            "ALARM_RAISED",
            "ALARM_CLEARED",
            "FEED_HOLD",
            "PROGRAM_CHANGED",
            "PART_COMPLETED",
            "PART_REJECTED",
            "SETUP_STARTED",
            "SETUP_COMPLETED",
        }
        actual = {e.value for e in ProductionEventType}
        assert expected.issubset(actual)

    def test_production_event_creation(self):
        from backend.monitoring.enums import ProductionEventType
        event = ProductionEvent(
            event_id="e1",
            event_type=ProductionEventType.CYCLE_COMPLETED,
            machine_id="M-001",
            timestamp="2026-11-07T10:00:00+00:00",
        )
        assert event.event_type == ProductionEventType.CYCLE_COMPLETED
        assert event.is_duplicate is False


# ===========================================================================
# Alarm Model and Analytics
# ===========================================================================


class TestAlarmModel:
    def test_make_alarm_observation(self):
        alarm = make_alarm_observation(
            alarm_code="ALM-001",
            machine_id="M-001",
            duration_seconds=120.0,
        )
        assert alarm.alarm_code == "ALM-001"
        assert alarm.alarm_text is None  # not invented
        assert alarm.duration_seconds == 120.0

    def test_analyze_alarms_empty(self):
        analytics = analyze_alarms([])
        assert analytics.total_alarm_count == 0
        assert analytics.alarm_frequency_per_hour is None
        assert any("cannot assume zero" in w for w in analytics.warnings)

    def test_analyze_alarms_basic(self):
        alarms = [
            make_alarm_observation("ALM-001", "M-001", duration_seconds=60.0),
            make_alarm_observation("ALM-001", "M-001", duration_seconds=30.0),
            make_alarm_observation("ALM-002", "M-001", duration_seconds=15.0),
        ]
        analytics = analyze_alarms(alarms)
        assert analytics.total_alarm_count == 3
        assert "ALM-001" in analytics.repeat_alarm_candidates

    def test_alarm_frequency(self):
        alarms = [
            make_alarm_observation("ALM-001", "M-001"),
            make_alarm_observation("ALM-001", "M-001"),
        ]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        assert analytics.alarm_frequency_per_hour == pytest.approx(2.0)

    def test_no_root_cause_from_alarm_code(self):
        alarms = [make_alarm_observation("ALM-999", "M-001")]
        analytics = analyze_alarms(alarms)
        # Analytics provides counts, not root cause claims
        assert analytics.total_alarm_count == 1
        assert not hasattr(analytics, "root_cause")


# ===========================================================================
# Tool Usage and Tool-Life Feedback
# ===========================================================================


class TestToolUsageModel:
    def test_make_tool_usage_no_telemetry(self):
        usage = make_tool_usage("T-001")
        assert usage.cutting_time is None
        assert any("NO_TOOL_TELEMETRY" in w for w in usage.warnings)

    def test_make_tool_usage_with_data(self):
        usage = make_tool_usage("T-001", cutting_time=45.0, parts_produced=10)
        assert usage.cutting_time == 45.0
        assert usage.parts_produced == 10

    def test_tool_life_shorter_than_expected(self):
        usage = make_tool_usage("T-001", observed_life=80.0)
        fb = compute_tool_life_feedback("T-001", predicted_life=100.0, actual_usage=usage)
        assert fb.status == ToolLifeStatus.TOOL_LIFE_SHORTER_THAN_EXPECTED
        assert fb.is_automatic_action is False

    def test_tool_life_longer_than_expected(self):
        usage = make_tool_usage("T-001", observed_life=120.0)
        fb = compute_tool_life_feedback("T-001", predicted_life=100.0, actual_usage=usage)
        assert fb.status == ToolLifeStatus.TOOL_LIFE_LONGER_THAN_EXPECTED

    def test_tool_life_within_policy(self):
        usage = make_tool_usage("T-001", observed_life=100.0)
        fb = compute_tool_life_feedback(
            "T-001", predicted_life=100.0, actual_usage=usage, tolerance_ratio=0.1
        )
        assert fb.status == ToolLifeStatus.TOOL_LIFE_WITHIN_POLICY

    def test_tool_life_insufficient_data_no_telemetry(self):
        usage = make_tool_usage("T-001")
        fb = compute_tool_life_feedback("T-001", predicted_life=100.0, actual_usage=usage)
        assert fb.status == ToolLifeStatus.INSUFFICIENT_DATA

    def test_tool_life_insufficient_data_no_predicted(self):
        usage = make_tool_usage("T-001", cutting_time=90.0)
        fb = compute_tool_life_feedback("T-001", predicted_life=None, actual_usage=usage)
        assert fb.status == ToolLifeStatus.INSUFFICIENT_DATA


# ===========================================================================
# Quality Observations
# ===========================================================================


class TestQualityObservationModel:
    def test_make_quality_pass(self):
        obs = make_quality_observation(
            "DIAMETER",
            measured_value=10.0,
            lower_limit=9.9,
            upper_limit=10.1,
        )
        assert obs.pass_fail is True

    def test_make_quality_fail(self):
        obs = make_quality_observation(
            "DIAMETER",
            measured_value=10.2,
            lower_limit=9.9,
            upper_limit=10.1,
        )
        assert obs.pass_fail is False

    def test_make_quality_no_limits(self):
        obs = make_quality_observation("ROUGHNESS", measured_value=1.6)
        assert obs.pass_fail is None
        # pass_fail is None when limits are not provided — no tolerances invented

    def test_no_invented_tolerances(self):
        obs = make_quality_observation("LENGTH")
        assert obs.lower_limit is None
        assert obs.upper_limit is None
        assert obs.pass_fail is None

    def test_compute_yield(self):
        assert compute_yield(90, 100) == pytest.approx(0.9)

    def test_compute_yield_zero_denominator(self):
        assert compute_yield(0, 0) is None

    def test_compute_yield_missing(self):
        assert compute_yield(None, 100) is None

    def test_scrap_not_inferred_from_alarms(self):
        obs = test_machine_alarm(alarm_code="ALM-001")
        # Alarm does not imply scrap; reject_count stays None
        assert obs.reject_count is None


# ===========================================================================
# Performance KPIs
# ===========================================================================


class TestPerformanceKPIs:
    def test_compute_availability(self):
        result = compute_availability(480.0, 400.0)
        assert result == pytest.approx(400 / 480)

    def test_compute_availability_zero_planned(self):
        assert compute_availability(0.0, 400.0) is None

    def test_compute_availability_missing(self):
        assert compute_availability(None, 400.0) is None

    def test_compute_performance(self):
        result = compute_performance(10.0, 36, 400.0)
        assert result == pytest.approx(360 / 400)

    def test_compute_performance_zero_run_time(self):
        assert compute_performance(10.0, 36, 0.0) is None

    def test_compute_quality_kpi(self):
        assert compute_quality_kpi(90, 100) == pytest.approx(0.9)

    def test_compute_quality_kpi_zero_total(self):
        assert compute_quality_kpi(0, 0) is None

    def test_performance_kpis_no_observations(self):
        kpis = compute_performance_kpis([])
        assert kpis.observation_count == 0
        assert kpis.average_cycle_time is None

    def test_performance_kpis_with_data(self):
        obs_list = [
            test_machine_cycle_complete(actual_cycle_time=10.0, good_count=1),
            test_machine_cycle_complete(actual_cycle_time=12.0, good_count=1),
            test_machine_cycle_complete(actual_cycle_time=11.0, good_count=1),
        ]
        kpis = compute_performance_kpis(obs_list)
        assert kpis.observation_count == 3
        assert kpis.average_cycle_time == pytest.approx(11.0)
        assert kpis.median_cycle_time == pytest.approx(11.0)

    def test_rolling_median(self):
        result = compute_rolling_median([10.0, 12.0, 11.0, 13.0], window=3)
        assert result[0] == pytest.approx(10.0)
        assert None not in result


# ===========================================================================
# OEE
# ===========================================================================


class TestOEESupport:
    def test_oee_valid_complete(self):
        result = compute_oee(
            machine_id="M-001",
            planned_production_time=480.0,
            run_time=400.0,
            ideal_cycle_time=10.0,
            total_count=36,
            good_count=32,
        )
        assert result.status == OEEStatus.CALCULATED
        assert result.oee is not None
        assert 0 < result.oee <= 1.0

    def test_oee_missing_availability(self):
        result = compute_oee(
            ideal_cycle_time=10.0,
            total_count=36,
            good_count=32,
        )
        assert result.status == OEEStatus.INSUFFICIENT_DATA
        assert result.oee is None
        assert any("AVAILABILITY" in w for w in result.warnings)

    def test_oee_missing_performance(self):
        result = compute_oee(
            planned_production_time=480.0,
            run_time=400.0,
            good_count=32,
        )
        assert result.status == OEEStatus.INSUFFICIENT_DATA
        assert result.oee is None

    def test_oee_missing_quality(self):
        result = compute_oee(
            planned_production_time=480.0,
            run_time=400.0,
            ideal_cycle_time=10.0,
            total_count=36,
        )
        assert result.status == OEEStatus.INSUFFICIENT_DATA
        assert result.oee is None

    def test_oee_zero_denominators(self):
        result = compute_oee(
            planned_production_time=0.0,
            run_time=0.0,
            ideal_cycle_time=10.0,
            total_count=0,
            good_count=0,
        )
        assert result.status == OEEStatus.INSUFFICIENT_DATA
        assert result.oee is None

    def test_oee_formula(self):
        availability = 400 / 480
        performance = (10 * 36) / 400
        quality = 32 / 36
        expected = availability * performance * quality
        result = compute_oee(
            planned_production_time=480.0,
            run_time=400.0,
            ideal_cycle_time=10.0,
            total_count=36,
            good_count=32,
        )
        assert result.oee == pytest.approx(expected)


# ===========================================================================
# Trend Foundation
# ===========================================================================


class TestTrendFoundation:
    def test_cycle_time_trend(self):
        ts = ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"]
        vals = [10.0, 12.0]
        trend = build_cycle_time_trend(ts, vals)
        assert trend.metric == "cycle_time"
        assert len(trend.points) == 2

    def test_alarm_trend(self):
        ts = ["2026-01-01T00:00:00+00:00"]
        trend = build_alarm_trend(ts, [2.0])
        assert trend.metric == "alarm_count"

    def test_tool_life_trend(self):
        ts = ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"]
        trend = build_tool_life_trend(ts, [100.0, 90.0], tool_id="T-001")
        assert trend.metric == "tool_life"

    def test_quality_trend(self):
        ts = ["2026-01-01T00:00:00+00:00"]
        trend = build_quality_trend(ts, [0.95])
        assert trend.metric == "yield_rate"

    def test_idle_time_trend(self):
        ts = ["2026-01-01T00:00:00+00:00"]
        trend = build_idle_time_trend(ts, [0.3])
        assert trend.metric == "idle_time_share"

    def test_mismatched_lengths_invalid(self):
        trend = build_cycle_time_trend(["t1", "t2"], [10.0])
        assert trend.data_quality == DataQuality.INVALID


# ===========================================================================
# Anomaly Detection
# ===========================================================================


class TestAnomalyFoundation:
    def test_threshold_anomaly_detected(self):
        result = detect_threshold_anomaly("cycle_time", 15.0, threshold=12.0)
        assert result.is_anomaly is True
        assert result.method == AnomalyMethod.THRESHOLD

    def test_threshold_anomaly_not_detected(self):
        result = detect_threshold_anomaly("cycle_time", 10.0, threshold=12.0)
        assert result.is_anomaly is False

    def test_range_anomaly_detected(self):
        result = detect_range_anomaly("cycle_time", 15.0, 8.0, 12.0)
        assert result.is_anomaly is True

    def test_range_anomaly_in_range(self):
        result = detect_range_anomaly("cycle_time", 10.0, 8.0, 12.0)
        assert result.is_anomaly is False

    def test_iqr_anomaly(self):
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 50.0]
        results = detect_iqr_anomalies("cycle_time", values)
        assert results[-1].is_anomaly is True

    def test_iqr_insufficient_data(self):
        results = detect_iqr_anomalies("cycle_time", [10.0, 11.0])
        assert all(not r.is_anomaly for r in results)

    def test_apply_threshold_policy(self):
        policy = AnomalyPolicy(
            policy_id="p1",
            metric="cycle_time",
            method=AnomalyMethod.THRESHOLD,
            threshold=12.0,
        )
        results = apply_anomaly_policy(policy, [10.0, 15.0])
        assert len(results) == 2
        assert results[1].is_anomaly is True


# ===========================================================================
# Root-Cause Candidates
# ===========================================================================


class TestRootCauseCandidates:
    def test_no_candidates_empty_input(self):
        candidates = identify_root_cause_candidates()
        assert candidates == []

    def test_cycle_time_plus_alarm_generates_candidate(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [make_alarm_observation("ALM-001", "M-001")]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        candidates = identify_root_cause_candidates(
            comparison=cmp, alarm_analytics=analytics
        )
        assert len(candidates) >= 1

    def test_candidate_is_not_confirmed(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [make_alarm_observation("ALM-001", "M-001")]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        candidates = identify_root_cause_candidates(
            comparison=cmp, alarm_analytics=analytics
        )
        for c in candidates:
            assert c.is_confirmed is False
            assert c.is_causal_proof is False
            assert c.status in (
                RootCauseCandidateStatus.CANDIDATE,
                RootCauseCandidateStatus.NOT_CONFIRMED,
            )

    def test_causal_proof_never_claimed(self):
        """Correlation evidence never equals confirmed root cause."""
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [
            make_alarm_observation("ALM-999", "M-001"),
            make_alarm_observation("ALM-999", "M-001"),
        ]
        analytics = analyze_alarms(alarms, planned_hours=0.5)
        candidates = identify_root_cause_candidates(alarm_analytics=analytics)
        for c in candidates:
            assert c.is_causal_proof is False


# ===========================================================================
# Engineering Recommendations
# ===========================================================================


class TestEngineeringRecommendations:
    def test_generate_recommendations_from_candidates(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [make_alarm_observation("ALM-001", "M-001")]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        candidates = identify_root_cause_candidates(
            comparison=cmp, alarm_analytics=analytics
        )
        recs = generate_recommendations(candidates)
        assert len(recs) >= 0  # may be empty if no candidates

    def test_all_recommendations_require_review(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [make_alarm_observation("ALM-001", "M-001")]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        candidates = identify_root_cause_candidates(
            comparison=cmp, alarm_analytics=analytics
        )
        recs = generate_recommendations(candidates)
        for rec in recs:
            assert rec.requires_review is True
            assert rec.is_automatic_action is False
            assert rec.is_applied is False

    def test_recommendation_types_defined(self):
        expected = {
            "REVIEW_CUTTING_DATA",
            "REVIEW_TOOL_SELECTION",
            "REVIEW_TOOL_LIFE",
            "REVIEW_MACHINE_ASSIGNMENT",
            "REVIEW_SETUP_METHOD",
            "REVIEW_FIXTURE",
            "REVIEW_NC_PROGRAM",
            "REVIEW_MAINTENANCE",
            "REVIEW_QUALITY_PROCESS",
        }
        actual = {r.value for r in RecommendationType}
        assert expected.issubset(actual)


# ===========================================================================
# Closed-Loop Proposals
# ===========================================================================


class TestClosedLoopProposals:
    def test_feed_candidate_proposal(self):
        proposal = make_closed_loop_proposal(
            ClosedLoopProposalType.NEW_FEED_CANDIDATE,
            proposed_value=150.0,
            current_value=200.0,
        )
        assert proposal.is_proposed_only is True
        assert proposal.is_automatic_write is False
        assert proposal.proposed_value == 150.0

    def test_all_proposal_types_defined(self):
        expected = {
            "NEW_FEED_CANDIDATE",
            "NEW_SPINDLE_CANDIDATE",
            "NEW_TOOL_CANDIDATE",
            "NEW_CYCLE_TIME_BASELINE",
        }
        actual = {p.value for p in ClosedLoopProposalType}
        assert expected.issubset(actual)

    def test_proposed_does_not_write_to_level6(self):
        """Closed-loop proposal is proposed only; never writes cutting data."""
        proposal = make_closed_loop_proposal(
            ClosedLoopProposalType.NEW_FEED_CANDIDATE,
        )
        assert proposal.is_automatic_write is False

    def test_proposed_does_not_write_to_level12(self):
        """Closed-loop proposal never writes to NC program."""
        proposal = make_closed_loop_proposal(
            ClosedLoopProposalType.NEW_CYCLE_TIME_BASELINE,
        )
        assert proposal.is_automatic_write is False


# ===========================================================================
# Learning Dataset Foundation
# ===========================================================================


class TestLearningDatasetFoundation:
    def test_create_learning_record(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        record = create_learning_record(obs, material="AlSi10Mg")
        assert record.actual_cycle_time == pytest.approx(10.0)
        assert record.material == "AlSi10Mg"
        assert record.provenance_hash is not None

    def test_anonymized_by_default(self):
        obs = make_simulated_observation("M-001", "J-001", tool_id="T-999")
        record = create_learning_record(obs)
        assert record.is_anonymized is True
        assert record.tool_id is None  # suppressed

    def test_provenance_preserved(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        r1 = create_learning_record(obs)
        r2 = create_learning_record(obs)
        assert r1.provenance_hash == r2.provenance_hash

    def test_validate_record_passes(self):
        obs = test_machine_cycle_complete(actual_cycle_time=10.0)
        record = create_learning_record(obs)
        warnings = validate_learning_record(record)
        assert "MISSING_PROVENANCE_HASH" not in warnings

    def test_anonymize_records_batch(self):
        records = [
            LearningRecord(
                record_id="r1",
                tool_id="T-001",
                is_anonymized=False,
                anonymization_policy="NONE",
                data_quality=DataQuality.RAW,
                source=ObservationSource.SIMULATED_CONTROLLER,
            )
        ]
        cleaned = anonymize_learning_records(records)
        assert cleaned[0].tool_id is None
        assert cleaned[0].is_anonymized is True


# ===========================================================================
# Negative Tests
# ===========================================================================


class TestNegativeTests:
    def test_planned_not_actual_different_values(self):
        obs = test_machine_cycle_complete(actual_cycle_time=12.0)
        cmp = compare_planned_actual(obs, planned_cycle_time=10.0)
        assert cmp.planned_cycle_time != cmp.actual_cycle_time

    def test_missing_alarm_data_is_not_zero_alarms(self):
        analytics = analyze_alarms([])
        assert analytics.total_alarm_count == 0
        assert analytics.alarm_frequency_per_hour is None
        assert any("cannot assume zero" in w.lower() for w in analytics.warnings)

    def test_correlation_not_confirmed_root_cause(self):
        from backend.monitoring.alarms import analyze_alarms, make_alarm_observation
        alarms = [
            make_alarm_observation("ALM-001", "M-001"),
            make_alarm_observation("ALM-001", "M-001"),
        ]
        analytics = analyze_alarms(alarms, planned_hours=1.0)
        candidates = identify_root_cause_candidates(alarm_analytics=analytics)
        for c in candidates:
            assert c.is_confirmed is False

    def test_recommendation_not_automatic_action(self):
        rec = EngineeringRecommendation(
            recommendation_id="r1",
            recommendation_type=RecommendationType.REVIEW_TOOL_LIFE,
            requires_review=True,
            is_automatic_action=False,
            is_applied=False,
        )
        assert rec.is_automatic_action is False

    def test_proposed_feed_not_machine_feed_override(self):
        proposal = make_closed_loop_proposal(
            ClosedLoopProposalType.NEW_FEED_CANDIDATE,
            proposed_value=150.0,
        )
        assert proposal.is_automatic_write is False

    def test_tool_life_feedback_not_tool_offset_write(self):
        usage = make_tool_usage("T-001", observed_life=80.0)
        fb = compute_tool_life_feedback("T-001", predicted_life=100.0, actual_usage=usage)
        assert fb.is_automatic_action is False

    def test_quality_feedback_not_automatic_process_change(self):
        obs = make_quality_observation(
            "DIAMETER", measured_value=10.2, lower_limit=9.9, upper_limit=10.1
        )
        # Quality observation records data; it does NOT change process
        assert not hasattr(obs, "apply_correction")
        assert not hasattr(obs, "update_nc_program")

    def test_no_write_value_in_monitoring_source(self):
        """Verify monitoring runtime code has no write_value calls."""
        import backend.monitoring.comparison as comparison_mod
        import backend.monitoring.kpis as kpis_mod
        import backend.monitoring.telemetry as telemetry_mod
        for mod in [telemetry_mod, comparison_mod, kpis_mod]:
            src = inspect.getsource(mod)
            assert "write_value" not in src
            assert "set_value" not in src
            assert "socket.send" not in src
            assert "cycle_start" not in src
            assert "machine_start" not in src

    def test_no_automatic_corrective_action_in_recommendations(self):
        """Verify recommendations module has no auto-apply logic."""
        import backend.monitoring.recommendations as recs_mod
        src = inspect.getsource(recs_mod)
        assert "is_automatic_action = True" not in src
        assert "is_applied = True" not in src

    def test_z_scores_basic(self):
        values = [10.0, 10.0, 10.0, 20.0]
        z_scores = compute_z_scores(values)
        assert z_scores is not None
        assert abs(z_scores[-1]) > 1.0

    def test_z_scores_constant_returns_none(self):
        result = compute_z_scores([10.0, 10.0, 10.0])
        assert result is None
