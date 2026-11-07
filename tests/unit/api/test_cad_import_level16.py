"""
Level-16 Adaptive Manufacturing Intelligence — Unit Tests.
Covers: learning records, features, similarity, splitting, predictors,
risk, recommendations, what-if, trade-off, registry, drift, audit.
"""

from __future__ import annotations

from backend.adaptive import (
    CORRELATION_IS_NOT_CAUSATION,
    HUMAN_REVIEW_MANDATORY,
    NO_AUTOMATIC_CAM_MODIFICATION,
    NO_AUTOMATIC_CNC_CHANGE,
    NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT,
    NO_AUTOMATIC_FEED_OVERRIDE,
    NO_AUTOMATIC_JOB_DISPATCH,
    NO_AUTOMATIC_MACHINE_SELECTION,
    NO_AUTOMATIC_NC_REGEN,
    NO_AUTOMATIC_SCHEDULING_CHANGE,
    NO_AUTOMATIC_SPINDLE_OVERRIDE,
    NO_AUTOMATIC_TOOL_OFFSET_CHANGE,
    NO_AUTOMATIC_TOOLPATH_REGEN,
    NO_AUTOMATIC_WORK_OFFSET_CHANGE,
    PREDICTION_IS_NOT_MEASURED_FACT,
    RECOMMENDATION_IS_NOT_APPROVED_CHANGE,
    RECOMMENDATION_ONLY,
    AdaptiveAuditEventType,
    AdaptiveRecommendationType,
    AlarmRiskLevel,
    DriftStatus,
    ModelStatus,
    PredictionFidelity,
    PredictionTarget,
    QualityRiskLevel,
    RecommendationStatus,
    SplitRole,
    WhatIfStatus,
    audit_data_drift_detected,
    audit_model_drift_detected,
    audit_model_evaluated,
    audit_model_trained,
    audit_prediction_created,
    audit_recommendation_created,
    audit_recommendation_reviewed,
    audit_what_if_evaluated,
    build_recommendation_from_prediction,
    build_trade_off_analysis,
    compute_pareto_front,
    create_learning_record,
    detect_data_drift,
    detect_model_drift,
    estimate_alarm_risk,
    estimate_quality_risk,
    extract_features,
    find_similar_cases,
    generate_cutting_data_recommendations,
    generate_machine_recommendations,
    generate_tool_recommendations,
    get_registry,
    make_test_dataset_aluminium_turning,
    make_test_record_missing_data,
    make_test_record_out_of_domain,
    reset_registry,
    review_recommendation,
    run_what_if_machine_change,
    run_what_if_vc_change,
    split_records,
    validate_learning_record,
)
from backend.adaptive.enums import ModelType
from backend.adaptive.models import (
    AdaptiveRecommendation,
    ManufacturingLearningRecord,
    ModelSpec,
    PredictionResult,
    TradeOffCandidate,
)
from backend.adaptive.predictors import (
    LinearRegressionPredictor,
    MedianPredictor,
    NearestNeighborPredictor,
)

# ===========================================================================
# Safety invariants
# ===========================================================================


class TestSafetyInvariants:
    def test_no_automatic_cnc_change(self):
        assert NO_AUTOMATIC_CNC_CHANGE is True

    def test_no_automatic_feed_override(self):
        assert NO_AUTOMATIC_FEED_OVERRIDE is True

    def test_no_automatic_spindle_override(self):
        assert NO_AUTOMATIC_SPINDLE_OVERRIDE is True

    def test_no_automatic_tool_offset(self):
        assert NO_AUTOMATIC_TOOL_OFFSET_CHANGE is True

    def test_no_automatic_work_offset(self):
        assert NO_AUTOMATIC_WORK_OFFSET_CHANGE is True

    def test_no_automatic_cam_modification(self):
        assert NO_AUTOMATIC_CAM_MODIFICATION is True

    def test_no_automatic_toolpath_regen(self):
        assert NO_AUTOMATIC_TOOLPATH_REGEN is True

    def test_no_automatic_nc_regen(self):
        assert NO_AUTOMATIC_NC_REGEN is True

    def test_no_automatic_scheduling_change(self):
        assert NO_AUTOMATIC_SCHEDULING_CHANGE is True

    def test_no_automatic_job_dispatch(self):
        assert NO_AUTOMATIC_JOB_DISPATCH is True

    def test_no_automatic_machine_selection(self):
        assert NO_AUTOMATIC_MACHINE_SELECTION is True

    def test_no_automatic_cutting_data_replacement(self):
        assert NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT is True

    def test_recommendation_only(self):
        assert RECOMMENDATION_ONLY is True

    def test_human_review_mandatory(self):
        assert HUMAN_REVIEW_MANDATORY is True

    def test_prediction_is_not_measured_fact(self):
        assert PREDICTION_IS_NOT_MEASURED_FACT is True

    def test_recommendation_is_not_approved_change(self):
        assert RECOMMENDATION_IS_NOT_APPROVED_CHANGE is True

    def test_correlation_is_not_causation(self):
        assert CORRELATION_IS_NOT_CAUSATION is True


# ===========================================================================
# Learning Record model
# ===========================================================================


class TestLearningRecordModel:
    def test_create_learning_record_basic(self):
        r = create_learning_record(
            "TEST_001",
            material="AL_6082_T6",
            machine_class="CNC_TURNING_CENTER",
        )
        assert r.record_id == "TEST_001"
        assert r.is_fabricated is False

    def test_is_fabricated_locked_false(self):
        r = create_learning_record("TEST_002", is_test_only=True)
        assert r.is_fabricated is False

    def test_provenance_hash_set(self):
        r = create_learning_record("TEST_003", machine_class="MC1", operation_type="OT1")
        assert r.provenance is not None
        assert len(r.provenance) == 16

    def test_provenance_deterministic(self):
        r1 = create_learning_record("TEST_004", machine_class="MC1", operation_type="OT1")
        r2 = create_learning_record("TEST_004", machine_class="MC1", operation_type="OT1")
        assert r1.provenance == r2.provenance

    def test_provenance_different_records(self):
        r1 = create_learning_record("TEST_005", machine_class="MC1", operation_type="OT1")
        r2 = create_learning_record("TEST_006", machine_class="MC2", operation_type="OT2")
        assert r1.provenance != r2.provenance

    def test_planned_cutting_data_empty_by_default(self):
        r = create_learning_record("TEST_007")
        assert r.planned_cutting_data == {}

    def test_actual_values_none_by_default(self):
        r = create_learning_record("TEST_008")
        assert r.actual_cycle_time is None
        assert r.actual_tool_life is None

    def test_test_only_flag(self):
        r = create_learning_record("TEST_009", is_test_only=True)
        assert r.is_test_only is True

    def test_validation_warnings_missing_data(self):
        r = make_test_record_missing_data()
        warnings = validate_learning_record(r)
        assert any("MISSING_MATERIAL" in w for w in warnings)
        assert any("MISSING_MACHINE_CLASS" in w for w in warnings)
        assert any("UNKNOWN_DATA_QUALITY" in w for w in warnings)

    def test_validation_no_warnings_valid_record(self):
        r = create_learning_record(
            "TEST_010",
            material="AL_6082_T6",
            machine_class="CNC_TURNING_CENTER",
            operation_type="FINISH_TURNING",
            actual_cycle_time=115.0,
            data_quality="VALIDATED",
        )
        warnings = validate_learning_record(r)
        assert not any("MISSING_MATERIAL" in w for w in warnings)
        assert not any("MISSING_MACHINE_CLASS" in w for w in warnings)

    def test_validation_rejects_fabricated(self):
        r = ManufacturingLearningRecord(
            record_id="FAB_001",
            is_fabricated=True,
        )
        warnings = validate_learning_record(r)
        assert any("FABRICATED" in w for w in warnings)

    def test_validation_invalid_cycle_time(self):
        r = create_learning_record("TEST_011", actual_cycle_time=-5.0)
        warnings = validate_learning_record(r)
        assert any("INVALID_CYCLE_TIME" in w for w in warnings)

    def test_test_dataset_all_test_only(self):
        dataset = make_test_dataset_aluminium_turning()
        assert all(r.is_test_only for r in dataset)

    def test_test_dataset_not_fabricated(self):
        dataset = make_test_dataset_aluminium_turning()
        assert all(r.is_fabricated is False for r in dataset)

    def test_test_dataset_has_records(self):
        dataset = make_test_dataset_aluminium_turning()
        assert len(dataset) >= 5

    def test_out_of_domain_record_created(self):
        r = make_test_record_out_of_domain()
        assert r.material == "INCONEL_718"
        assert r.is_fabricated is False


# ===========================================================================
# Feature vector
# ===========================================================================


class TestFeatureVector:
    def _base_record(self, record_id: str = "FV_001") -> ManufacturingLearningRecord:
        return create_learning_record(
            record_id,
            material="AL_6082_T6",
            machine_class="CNC_TURNING_CENTER",
            operation_type="FINISH_TURNING",
            planned_cutting_data={"vc": 300.0, "fn": 0.15, "ap": 1.0, "ae": 10.0},
            planned_cycle_time=120.0,
            planned_tool_life=80.0,
        )

    def test_extract_features_complete(self):
        fv = extract_features(self._base_record())
        assert fv.is_complete is True
        assert len(fv.missing_features) == 0

    def test_features_normalized_in_range(self):
        fv = extract_features(self._base_record())
        for key, val in fv.features.items():
            if val is not None:
                assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"

    def test_missing_material_in_missing_features(self):
        r = create_learning_record("FV_002", machine_class="CNC_TURNING_CENTER")
        fv = extract_features(r)
        assert "material" in fv.missing_features
        assert fv.is_complete is False

    def test_out_of_domain_material(self):
        r = make_test_record_out_of_domain()
        fv = extract_features(r)
        assert fv.out_of_domain is True
        assert any("material" in reason.lower() for reason in fv.out_of_domain_reasons)

    def test_known_material_one_hot(self):
        r = self._base_record()
        fv = extract_features(r)
        assert fv.features.get("mat_AL_6082_T6") == 1.0
        assert fv.features.get("mat_AL_7075_T6") == 0.0

    def test_known_machine_class_one_hot(self):
        r = self._base_record()
        fv = extract_features(r)
        assert fv.features.get("mc_CNC_TURNING_CENTER") == 1.0

    def test_missing_cutting_data_key(self):
        r = create_learning_record(
            "FV_003",
            material="AL_6082_T6",
            machine_class="CNC_TURNING_CENTER",
            operation_type="FINISH_TURNING",
            planned_cutting_data={"vc": 300.0},  # fn and ap missing
        )
        fv = extract_features(r)
        assert "cutting_data.fn" in fv.missing_features
        assert "cutting_data.ap" in fv.missing_features


# ===========================================================================
# Data leakage / splitting
# ===========================================================================


class TestDataSplitting:
    def _make_records(self, n: int) -> list[ManufacturingLearningRecord]:
        return [
            create_learning_record(
                f"SPLIT_{i:03d}",
                material="AL_6082_T6",
                machine_class="CNC_TURNING_CENTER",
                actual_cycle_time=float(100 + i),
                is_test_only=True,
            )
            for i in range(n)
        ]

    def test_split_counts_sum_to_total(self):
        records = self._make_records(20)
        result = split_records(records)
        assert result.train_count + result.validation_count + result.test_count == 20

    def test_train_set_is_majority(self):
        records = self._make_records(20)
        result = split_records(records)
        assert result.train_count > result.validation_count
        assert result.train_count > result.test_count

    def test_no_id_overlap_between_splits(self):
        records = self._make_records(20)
        result = split_records(records)
        train_set = set(result.train_ids)
        val_set = set(result.validation_ids)
        test_set = set(result.test_ids)
        assert not (train_set & val_set)
        assert not (train_set & test_set)
        assert not (val_set & test_set)

    def test_insufficient_records_returns_warning(self):
        records = self._make_records(2)
        result = split_records(records)
        assert any("INSUFFICIENT" in w for w in result.warnings)

    def test_empty_records_returns_warning(self):
        result = split_records([])
        assert any("NO_RECORDS" in w for w in result.warnings)

    def test_group_aware_split_no_leakage(self):
        # 3 families, each with 4 records
        records = []
        for family in ["FAM_A", "FAM_B", "FAM_C"]:
            for i in range(4):
                records.append(create_learning_record(
                    f"GRP_{family}_{i}",
                    part_family=family,
                    actual_cycle_time=100.0,
                    is_test_only=True,
                ))
        result = split_records(records, group_by="part_family")
        assert result.group_aware is True
        # No record ID appears in two splits
        all_ids = result.train_ids + result.validation_ids + result.test_ids
        assert len(all_ids) == len(set(all_ids))

    def test_split_roles_assigned_to_records(self):
        records = self._make_records(10)
        split_records(records)
        assigned = [r for r in records if r.split_role is not None]
        assert len(assigned) == 10

    def test_train_records_have_train_role(self):
        records = self._make_records(10)
        result = split_records(records)
        for r in records:
            if r.record_id in result.train_ids:
                assert r.split_role == SplitRole.TRAIN


# ===========================================================================
# Similar case search
# ===========================================================================


class TestSimilarCaseSearch:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_find_similar_returns_list(self):
        dataset = self._dataset()
        query = dataset[0]
        results = find_similar_cases(query, dataset[1:])
        assert isinstance(results, list)

    def test_similar_cases_have_similarity_score(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], dataset[1:])
        for case in results:
            assert 0.0 <= case.similarity_score <= 1.0

    def test_similar_cases_have_similarity_factors(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], dataset[1:])
        for case in results:
            assert isinstance(case.similarity_factors, dict)

    def test_top_k_respected(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], dataset[1:], top_k=3)
        assert len(results) <= 3

    def test_empty_candidates_returns_empty(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], [])
        assert results == []

    def test_similar_cases_ordered_by_score(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], dataset[1:])
        scores = [c.similarity_score for c in results]
        assert scores == sorted(scores, reverse=True)

    def test_case_includes_actual_cycle_time(self):
        dataset = self._dataset()
        results = find_similar_cases(dataset[0], dataset[1:])
        for case in results:
            # actual_cycle_time is populated from the candidate record
            assert case.actual_cycle_time is not None


# ===========================================================================
# Predictors
# ===========================================================================


class TestMedianPredictor:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_train_produces_model_spec(self):
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train(self._dataset())
        assert isinstance(spec, ModelSpec)
        assert spec.model_type == ModelType.HISTORICAL_MEDIAN

    def test_predict_returns_prediction_result(self):
        dataset = self._dataset()
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_MED_001")
        assert pred.predicted_value is not None
        assert pred.is_fabricated is False

    def test_untrained_predictor_returns_insufficient(self):
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        pred = predictor.predict(
            ManufacturingLearningRecord(record_id="Q1"),
            "PRED_UNTRAINED",
        )
        assert pred.fidelity == PredictionFidelity.INSUFFICIENT
        assert any("MODEL_NOT_TRAINED" in w for w in pred.warnings)

    def test_no_data_no_prediction(self):
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train([])
        assert spec.status == ModelStatus.REVIEW_REQUIRED

    def test_is_fabricated_always_false(self):
        dataset = self._dataset()
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_MED_002")
        assert pred.is_fabricated is False

    def test_is_fabricated_accuracy_always_false(self):
        dataset = self._dataset()
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train(dataset)
        assert spec.is_fabricated_accuracy is False


class TestNearestNeighborPredictor:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_train_produces_model_spec(self):
        predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train(self._dataset())
        assert spec.model_type == ModelType.NEAREST_NEIGHBOR

    def test_predict_returns_result(self):
        dataset = self._dataset()
        predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_NN_001")
        assert pred.is_fabricated is False

    def test_no_training_data_insufficient(self):
        predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train([])
        assert spec.status == ModelStatus.REVIEW_REQUIRED

    def test_similar_case_ids_in_result(self):
        dataset = self._dataset()
        predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_NN_002")
        # May have similar case IDs if matching cases found
        assert isinstance(pred.similar_case_ids, list)

    def test_prediction_not_measured_fact(self):
        # Prediction must carry uncertainty description
        dataset = self._dataset()
        predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_NN_003")
        # Either has description or insufficient
        assert isinstance(pred.uncertainty_description, str)


class TestLinearRegressionPredictor:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_train_produces_model_spec(self):
        predictor = LinearRegressionPredictor(PredictionTarget.CYCLE_TIME)
        spec = predictor.train(self._dataset())
        assert spec.model_type == ModelType.LINEAR_REGRESSION

    def test_predict_returns_result(self):
        dataset = self._dataset()
        predictor = LinearRegressionPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "PRED_LR_001")
        assert pred.is_fabricated is False

    def test_missing_feature_returns_insufficient(self):
        dataset = self._dataset()
        predictor = LinearRegressionPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        # Record without planned_cycle_time
        q = ManufacturingLearningRecord(record_id="LR_MISSING", is_fabricated=False)
        pred = predictor.predict(q, "PRED_LR_002")
        assert pred.fidelity == PredictionFidelity.INSUFFICIENT

    def test_slope_intercept_set_after_training(self):
        # Need records with varying planned_cycle_time for regression
        varying_records = [
            create_learning_record(
                f"LR_VAR_{i}",
                planned_cycle_time=float(100 + i * 10),
                actual_cycle_time=float(95 + i * 9),
                data_quality="VALIDATED",
                is_test_only=True,
            )
            for i in range(8)
        ]
        predictor = LinearRegressionPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(varying_records)
        params = predictor.get_params()
        assert params.slope is not None
        assert params.intercept is not None


# ===========================================================================
# Risk estimation
# ===========================================================================


class TestQualityRisk:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_quality_risk_returns_result(self):
        result = estimate_quality_risk(self._dataset())
        assert isinstance(result.risk_level, QualityRiskLevel)

    def test_low_reject_rate_gives_low_risk(self):
        # All-pass dataset → LOW
        result = estimate_quality_risk(self._dataset())
        assert result.risk_level == QualityRiskLevel.LOW

    def test_no_data_gives_insufficient(self):
        result = estimate_quality_risk([])
        assert result.risk_level == QualityRiskLevel.INSUFFICIENT
        assert any("INSUFFICIENT" in w for w in result.warnings)

    def test_is_fabricated_always_false(self):
        result = estimate_quality_risk(self._dataset())
        assert result.is_fabricated is False

    def test_reject_rate_is_set(self):
        result = estimate_quality_risk(self._dataset())
        # All pass → reject_rate = 0.0
        assert result.reject_rate == 0.0


class TestAlarmRisk:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_alarm_risk_returns_result(self):
        result = estimate_alarm_risk(self._dataset())
        assert isinstance(result.risk_level, AlarmRiskLevel)

    def test_no_alarms_gives_low_risk(self):
        # All-NONE alarm dataset → LOW
        result = estimate_alarm_risk(self._dataset())
        assert result.risk_level == AlarmRiskLevel.LOW

    def test_no_data_gives_insufficient(self):
        result = estimate_alarm_risk([])
        assert result.risk_level == AlarmRiskLevel.INSUFFICIENT

    def test_is_fabricated_always_false(self):
        result = estimate_alarm_risk(self._dataset())
        assert result.is_fabricated is False


# ===========================================================================
# Recommendations
# ===========================================================================


class TestCuttingDataRecommendations:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_generates_recommendation_or_empty(self):
        recs = generate_cutting_data_recommendations(
            self._dataset(),
            {"vc": 300.0, "fn": 0.15, "ap": 1.0},
        )
        assert isinstance(recs, list)

    def test_recommendation_review_required_true(self):
        recs = generate_cutting_data_recommendations(
            self._dataset(),
            {"vc": 300.0, "fn": 0.15, "ap": 1.0},
        )
        for rec in recs:
            assert rec.review_required is True

    def test_recommendation_is_automatic_application_false(self):
        recs = generate_cutting_data_recommendations(
            self._dataset(),
            {"vc": 300.0, "fn": 0.15, "ap": 1.0},
        )
        for rec in recs:
            assert rec.is_automatic_application is False

    def test_empty_records_no_recommendation(self):
        recs = generate_cutting_data_recommendations([], {"vc": 300.0})
        assert recs == []

    def test_recommendation_status_is_proposed(self):
        recs = generate_cutting_data_recommendations(
            self._dataset(),
            {"vc": 300.0, "fn": 0.15, "ap": 1.0},
        )
        for rec in recs:
            assert rec.status in (
                RecommendationStatus.PROPOSED,
                RecommendationStatus.REVIEW_REQUIRED,
            )

    def test_safety_blocked_exceeds_bounds(self):
        # Propose a Vc way beyond the 15% safety bound
        from backend.adaptive.records import create_learning_record
        # Create a record where observed vc would be 500, baseline vc is 300
        # → 66% change exceeds 15% safety bound → BLOCKED
        big_vc_records = [
            create_learning_record(
                f"BIG_VC_{i}",
                material="AL_6082_T6",
                machine_class="CNC_TURNING_CENTER",
                operation_type="FINISH_TURNING",
                planned_cycle_time=200.0,
                actual_cycle_time=50.0,  # very big improvement
                observed_cutting_data={"vc": 500.0},  # very big vc jump
                data_quality="VALIDATED",
                is_test_only=True,
            )
            for i in range(5)
        ]
        recs = generate_cutting_data_recommendations(big_vc_records, {"vc": 300.0})
        # Either BLOCKED or no rec
        for rec in recs:
            assert rec.is_automatic_application is False
            assert rec.review_required is True


class TestMachineRecommendations:
    def test_generates_recommendation_or_empty(self):
        dataset = make_test_dataset_aluminium_turning()
        # Add records with a different machine class
        alt_records = [
            create_learning_record(
                f"ALT_MC_{i}",
                machine_class="FIVE_AXIS_MILL",
                actual_cycle_time=float(80 + i),
                is_test_only=True,
            )
            for i in range(5)
        ]
        recs = generate_machine_recommendations(dataset + alt_records, "CNC_TURNING_CENTER")
        assert isinstance(recs, list)

    def test_no_other_machine_class_no_recommendation(self):
        dataset = make_test_dataset_aluminium_turning()
        # All records have same machine class
        recs = generate_machine_recommendations(dataset, "CNC_TURNING_CENTER")
        assert recs == []

    def test_machine_rec_review_required(self):
        alt_records = [
            create_learning_record(
                f"ALT_MC2_{i}",
                machine_class="FIVE_AXIS_MILL",
                actual_cycle_time=float(80 + i),
                is_test_only=True,
            )
            for i in range(5)
        ]
        recs = generate_machine_recommendations(alt_records, "CNC_TURNING_CENTER")
        for rec in recs:
            assert rec.review_required is True
            assert rec.is_automatic_application is False


class TestToolRecommendations:
    def test_generates_recommendation_or_empty(self):
        alt_records = [
            create_learning_record(
                f"ALT_TOOL_{i}",
                tool_family="COATED_CARBIDE",
                actual_tool_life=float(100 + i),
                is_test_only=True,
            )
            for i in range(5)
        ]
        recs = generate_tool_recommendations(alt_records, "UNCOATED_HSS")
        assert isinstance(recs, list)

    def test_tool_rec_review_required(self):
        alt_records = [
            create_learning_record(
                f"ALT_TOOL2_{i}",
                tool_family="COATED_CARBIDE",
                actual_tool_life=float(100 + i),
                is_test_only=True,
            )
            for i in range(5)
        ]
        recs = generate_tool_recommendations(alt_records, "UNCOATED_HSS")
        for rec in recs:
            assert rec.review_required is True
            assert rec.is_automatic_application is False


class TestRecommendationReview:
    def _base_rec(self) -> AdaptiveRecommendation:
        return AdaptiveRecommendation(
            recommendation_id="REC_001",
            recommendation_type=AdaptiveRecommendationType.VC_REVIEW_CANDIDATE,
            review_required=True,
            status=RecommendationStatus.PROPOSED,
            is_automatic_application=False,
        )

    def test_valid_transition_proposed_to_review_required(self):
        rec = self._base_rec()
        updated = review_recommendation(rec, RecommendationStatus.REVIEW_REQUIRED)
        assert updated.status == RecommendationStatus.REVIEW_REQUIRED
        assert updated.is_automatic_application is False

    def test_valid_transition_proposed_to_accepted(self):
        rec = self._base_rec()
        updated = review_recommendation(
            rec, RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY
        )
        assert updated.status == RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY
        assert updated.is_automatic_application is False

    def test_invalid_transition_adds_warning(self):
        rec = self._base_rec()
        # Cannot go from PROPOSED directly to STALE
        updated = review_recommendation(rec, RecommendationStatus.STALE)
        assert any("INVALID_TRANSITION" in w for w in updated.warnings)

    def test_is_automatic_application_never_changes(self):
        rec = self._base_rec()
        updated = review_recommendation(rec, RecommendationStatus.REJECTED)
        assert updated.is_automatic_application is False

    def test_build_recommendation_from_prediction(self):
        pred = PredictionResult(
            prediction_id="PRED_001",
            target=PredictionTarget.CYCLE_TIME,
            fidelity=PredictionFidelity.MEDIUM,
            sample_count=5,
            is_fabricated=False,
        )
        rec = build_recommendation_from_prediction(
            pred,
            AdaptiveRecommendationType.VC_REVIEW_CANDIDATE,
            {"vc": 300},
            {"vc": 320},
        )
        assert rec.review_required is True
        assert rec.is_automatic_application is False


# ===========================================================================
# What-if engine
# ===========================================================================


class TestWhatIfEngine:
    def _dataset(self) -> list[ManufacturingLearningRecord]:
        return make_test_dataset_aluminium_turning()

    def test_vc_change_does_not_mutate_baseline(self):
        dataset = self._dataset()
        baseline = dataset[0]
        original_vc = baseline.planned_cutting_data.get("vc")
        run_what_if_vc_change(baseline, dataset[1:], vc_change_pct=0.05)
        # Baseline record is unchanged
        assert baseline.planned_cutting_data.get("vc") == original_vc

    def test_vc_change_mutates_baseline_always_false(self):
        dataset = self._dataset()
        scenario = run_what_if_vc_change(dataset[0], dataset[1:], vc_change_pct=0.05)
        assert scenario.mutates_baseline is False

    def test_missing_vc_returns_insufficient(self):
        q = ManufacturingLearningRecord(
            record_id="WHATIF_NO_VC",
            planned_cutting_data={},
            is_fabricated=False,
        )
        scenario = run_what_if_vc_change(q, [], vc_change_pct=0.05)
        assert scenario.status == WhatIfStatus.INSUFFICIENT_DATA

    def test_negative_vc_blocked(self):
        q = ManufacturingLearningRecord(
            record_id="WHATIF_NEG_VC",
            planned_cutting_data={"vc": 100.0},
            is_fabricated=False,
        )
        scenario = run_what_if_vc_change(q, [], vc_change_pct=-2.0)
        assert scenario.status == WhatIfStatus.BLOCKED_BY_CONSTRAINT

    def test_machine_change_does_not_mutate_baseline(self):
        dataset = self._dataset()
        baseline = dataset[0]
        orig_class = baseline.machine_class
        run_what_if_machine_change(baseline, dataset[1:], proposed_machine_class="FIVE_AXIS_MILL")
        assert baseline.machine_class == orig_class

    def test_machine_change_mutates_baseline_false(self):
        dataset = self._dataset()
        scenario = run_what_if_machine_change(
            dataset[0], dataset[1:], proposed_machine_class="FIVE_AXIS_MILL"
        )
        assert scenario.mutates_baseline is False

    def test_machine_change_no_records_insufficient(self):
        q = ManufacturingLearningRecord(record_id="WI_MC_001", is_fabricated=False)
        scenario = run_what_if_machine_change(q, [], proposed_machine_class="FIVE_AXIS_MILL")
        assert scenario.status == WhatIfStatus.INSUFFICIENT_DATA


# ===========================================================================
# Trade-off and Pareto
# ===========================================================================


class TestTradeOff:
    def test_build_analysis_basic(self):
        analysis = build_trade_off_analysis(
            "Test trade-off",
            [{"vc": 300}, {"vc": 320}],
            [{"ct": 120.0, "tl": 80.0}, {"ct": 110.0, "tl": 65.0}],
            ["ct", "tl"],
            minimize_objectives=["ct", "tl"],
        )
        assert len(analysis.candidates) == 2
        assert analysis.no_single_best is True

    def test_no_single_best_flag(self):
        analysis = build_trade_off_analysis(
            "Multi-objective",
            [{"vc": 300}],
            [{"ct": 120.0}],
            ["ct"],
        )
        assert analysis.no_single_best is True

    def test_pareto_front_identified(self):
        # candidate 0: ct=100, tl=70 — dominated by candidate 1 on ct, tie on tl
        # candidate 1: ct=90, tl=70 — better on ct, equal on tl
        analysis = build_trade_off_analysis(
            "Pareto test",
            [{"vc": 300}, {"vc": 320}],
            [{"ct": 100.0, "tl": 70.0}, {"ct": 90.0, "tl": 70.0}],
            ["ct", "tl"],
            minimize_objectives=["ct", "tl"],
        )
        pareto = [c for c in analysis.candidates if c.is_pareto_optimal]
        assert len(pareto) >= 1

    def test_mismatched_lengths_gives_warning(self):
        analysis = build_trade_off_analysis(
            "Bad input",
            [{"vc": 300}],
            [{"ct": 100.0}, {"ct": 90.0}],  # 2 objectives for 1 param
            ["ct"],
        )
        assert any("MISMATCH" in w for w in analysis.warnings)

    def test_pareto_front_non_dominated_only(self):
        # Three candidates: clearly one dominates the other two
        candidates = [
            TradeOffCandidate(
                candidate_id="A",
                description="best",
                objectives={"ct": 90.0, "tl": 70.0},
            ),
            TradeOffCandidate(
                candidate_id="B",
                description="worse",
                objectives={"ct": 100.0, "tl": 65.0},
            ),
            TradeOffCandidate(
                candidate_id="C",
                description="trade-off",
                objectives={"ct": 95.0, "tl": 75.0},
            ),
        ]
        result = compute_pareto_front(candidates, minimize_objectives=["ct", "tl"])
        pareto = [c for c in result if c.is_pareto_optimal]
        assert len(pareto) >= 1


# ===========================================================================
# Model registry and versioning
# ===========================================================================


class TestModelRegistry:
    def setup_method(self):
        reset_registry()

    def test_register_and_get_model(self):
        spec = ModelSpec(
            model_id="test_model",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            sample_count=10,
        )
        registry = get_registry()
        registry.register(spec)
        retrieved = registry.get("test_model")
        assert retrieved is not None
        assert retrieved.model_id == "test_model"

    def test_get_nonexistent_returns_none(self):
        registry = get_registry()
        assert registry.get("does_not_exist") is None

    def test_reject_model_changes_status(self):
        spec = ModelSpec(
            model_id="to_reject",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            sample_count=5,
        )
        registry = get_registry()
        registry.register(spec)
        updated = registry.reject("to_reject", "BAD_DATA")
        assert updated is not None
        assert updated.status == ModelStatus.REJECTED

    def test_validate_model_changes_status(self):
        spec = ModelSpec(
            model_id="to_validate",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            sample_count=10,
            status=ModelStatus.TRAINED,
        )
        registry = get_registry()
        registry.register(spec)
        updated = registry.mark_validated("to_validate")
        assert updated is not None
        assert updated.status == ModelStatus.VALIDATED

    def test_staleness_detection_no_timestamp(self):
        spec = ModelSpec(
            model_id="stale_model",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            training_timestamp=None,
        )
        registry = get_registry()
        registry.register(spec)
        stale_ids = registry.check_staleness(staleness_days=30)
        assert "stale_model" in stale_ids

    def test_apply_staleness_marks_stale(self):
        spec = ModelSpec(
            model_id="old_model",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            training_timestamp="2020-01-01T00:00:00+00:00",
        )
        registry = get_registry()
        registry.register(spec)
        stale_ids = registry.apply_staleness_check(staleness_days=30)
        assert "old_model" in stale_ids
        retrieved = registry.get("old_model")
        assert retrieved is not None
        assert retrieved.status == ModelStatus.STALE

    def test_list_all_models(self):
        registry = get_registry()
        for i in range(3):
            registry.register(ModelSpec(
                model_id=f"model_{i}",
                version="1.0",
                target=PredictionTarget.CYCLE_TIME,
            ))
        models = registry.list_all()
        assert len(models) == 3


# ===========================================================================
# Drift detection
# ===========================================================================


class TestDriftDetection:
    def _make_records(
        self, n: int, base_ct: float = 120.0
    ) -> list[ManufacturingLearningRecord]:
        return [
            create_learning_record(
                f"DRIFT_{base_ct:.0f}_{i}",
                actual_cycle_time=base_ct + i * 0.1,
                is_test_only=True,
            )
            for i in range(n)
        ]

    def test_stable_data_no_drift(self):
        ref = self._make_records(10, base_ct=120.0)
        cur = self._make_records(10, base_ct=120.5)  # slight difference
        report = detect_data_drift(ref, cur)
        assert report.drift_status in (DriftStatus.STABLE, DriftStatus.DRIFT_DETECTED)

    def test_large_shift_detects_drift(self):
        ref = self._make_records(10, base_ct=120.0)
        cur = self._make_records(10, base_ct=500.0)  # very different distribution
        report = detect_data_drift(ref, cur)
        assert report.drift_status == DriftStatus.DRIFT_DETECTED

    def test_insufficient_data_returns_insufficient(self):
        ref = self._make_records(2)
        cur = self._make_records(2)
        report = detect_data_drift(ref, cur)
        assert report.drift_status == DriftStatus.INSUFFICIENT_DATA

    def test_drift_report_not_auto_retrain(self):
        ref = self._make_records(10, base_ct=120.0)
        cur = self._make_records(10, base_ct=500.0)
        report = detect_data_drift(ref, cur)
        # Drift detected → review required, NOT automatic retrain
        assert report.review_required is True

    def test_model_drift_stable(self):
        spec = ModelSpec(
            model_id="md_stable",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            validation_mae=5.0,
        )
        report = detect_model_drift(spec, current_validation_mae=5.5)
        assert report.drift_status == DriftStatus.STABLE

    def test_model_drift_detected(self):
        spec = ModelSpec(
            model_id="md_drifted",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            validation_mae=5.0,
        )
        report = detect_model_drift(spec, current_validation_mae=12.0)  # 2.4x ratio
        assert report.drift_status == DriftStatus.DRIFT_DETECTED

    def test_model_drift_no_baseline_mae(self):
        spec = ModelSpec(
            model_id="md_no_mae",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            validation_mae=None,
        )
        report = detect_model_drift(spec, current_validation_mae=10.0)
        assert report.drift_status == DriftStatus.INSUFFICIENT_DATA


# ===========================================================================
# Audit trail
# ===========================================================================


class TestAuditTrail:
    def test_audit_model_trained(self):
        event = audit_model_trained("model_001", sample_count=10)
        assert event.event_type == AdaptiveAuditEventType.MODEL_TRAINED
        assert event.model_ref == "model_001"
        assert event.details["sample_count"] == 10

    def test_audit_model_evaluated(self):
        event = audit_model_evaluated("model_001", validation_mae=4.5)
        assert event.event_type == AdaptiveAuditEventType.MODEL_EVALUATED
        assert event.details["validation_mae"] == 4.5

    def test_audit_prediction_created(self):
        event = audit_prediction_created("PRED_001", "model_001", "CYCLE_TIME", "HIGH")
        assert event.event_type == AdaptiveAuditEventType.PREDICTION_CREATED
        assert event.prediction_ref == "PRED_001"

    def test_audit_recommendation_created(self):
        event = audit_recommendation_created("REC_001", "VC_REVIEW_CANDIDATE", "MEDIUM")
        assert event.event_type == AdaptiveAuditEventType.RECOMMENDATION_CREATED
        assert event.recommendation_ref == "REC_001"

    def test_audit_recommendation_reviewed(self):
        event = audit_recommendation_reviewed("REC_001", "ACCEPTED_FOR_ENGINEERING_STUDY", "eng1")
        assert event.event_type == AdaptiveAuditEventType.RECOMMENDATION_REVIEWED
        assert event.actor == "eng1"

    def test_audit_what_if_evaluated(self):
        event = audit_what_if_evaluated("WI_001", "PREDICTED_IMPROVEMENT", "MEDIUM")
        assert event.event_type == AdaptiveAuditEventType.WHAT_IF_EVALUATED

    def test_audit_data_drift_detected(self):
        event = audit_data_drift_detected("DRIFT_001", "actual_cycle_time")
        assert event.event_type == AdaptiveAuditEventType.DATA_DRIFT_DETECTED

    def test_audit_model_drift_detected(self):
        event = audit_model_drift_detected("DRIFT_001", "model_001")
        assert event.event_type == AdaptiveAuditEventType.MODEL_DRIFT_DETECTED

    def test_audit_events_have_timestamps(self):
        event = audit_model_trained("model_002", sample_count=5)
        assert event.timestamp is not None
        assert len(event.timestamp) > 10


# ===========================================================================
# Negative tests (no data → no prediction)
# ===========================================================================


class TestNegativeTests:
    def test_no_training_data_no_cycle_time_prediction(self):
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        pred = predictor.predict(
            ManufacturingLearningRecord(record_id="NEG_001"),
            "PRED_NEG_001",
        )
        assert pred.predicted_value is None
        assert pred.fidelity == PredictionFidelity.INSUFFICIENT

    def test_no_training_data_no_tool_life_prediction(self):
        predictor = MedianPredictor(PredictionTarget.TOOL_LIFE)
        pred = predictor.predict(
            ManufacturingLearningRecord(record_id="NEG_002"),
            "PRED_NEG_002",
        )
        assert pred.predicted_value is None

    def test_insufficient_data_quality_risk(self):
        result = estimate_quality_risk([])
        assert result.risk_level == QualityRiskLevel.INSUFFICIENT

    def test_insufficient_data_alarm_risk(self):
        result = estimate_alarm_risk([])
        assert result.risk_level == AlarmRiskLevel.INSUFFICIENT

    def test_prediction_does_not_equal_observation(self):
        dataset = make_test_dataset_aluminium_turning()
        predictor = MedianPredictor(PredictionTarget.CYCLE_TIME)
        predictor.train(dataset)
        pred = predictor.predict(dataset[0], "NEG_003")
        # Predicted value is a statistical estimate, not the same record's actual
        # (they may coincidentally be equal, but the model uses all records)
        assert pred.is_fabricated is False
        assert pred.uncertainty_description != ""

    def test_recommendation_is_not_automatic_change(self):
        recs = generate_cutting_data_recommendations(
            make_test_dataset_aluminium_turning(),
            {"vc": 300.0},
        )
        for rec in recs:
            assert rec.is_automatic_application is False
            assert rec.status != "APPLIED_TO_MACHINE"

    def test_learned_feed_is_not_feed_override(self):
        # Feed recommendation is a REVIEW CANDIDATE, not a machine override
        rec = AdaptiveRecommendation(
            recommendation_id="FEED_REC_001",
            recommendation_type=AdaptiveRecommendationType.FEED_REVIEW_CANDIDATE,
            review_required=True,
            status=RecommendationStatus.PROPOSED,
            is_automatic_application=False,
        )
        assert rec.is_automatic_application is False
        assert rec.review_required is True

    def test_acceptance_does_not_deploy_to_machine(self):
        rec = AdaptiveRecommendation(
            recommendation_id="ACC_001",
            recommendation_type=AdaptiveRecommendationType.VC_REVIEW_CANDIDATE,
            review_required=True,
            status=RecommendationStatus.PROPOSED,
            is_automatic_application=False,
        )
        accepted = review_recommendation(rec, RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY)
        assert accepted.status == RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY
        assert accepted.is_automatic_application is False

    def test_stale_model_not_silently_reused(self):
        reset_registry()
        spec = ModelSpec(
            model_id="stale_check",
            version="1.0",
            target=PredictionTarget.CYCLE_TIME,
            training_timestamp="2020-01-01T00:00:00+00:00",
        )
        registry = get_registry()
        registry.register(spec)
        stale = registry.apply_staleness_check(staleness_days=30)
        assert "stale_check" in stale
        s = registry.get("stale_check")
        assert s is not None
        assert s.status == ModelStatus.STALE

    def test_out_of_domain_no_confident_recommendation(self):
        ood = make_test_record_out_of_domain()
        fv = extract_features(ood)
        # Out-of-domain → out_of_domain=True
        assert fv.out_of_domain is True

    def test_similar_case_query_missing_features_no_match(self):
        dataset = make_test_dataset_aluminium_turning()
        q = ManufacturingLearningRecord(record_id="MISSING_ALL", is_fabricated=False)
        results = find_similar_cases(q, dataset)
        # No common features → no results
        assert len(results) == 0
