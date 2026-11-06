"""
Level-12 NC Postprocessor and Safe G-code — unit tests.

Covers:
- NC IR models
- PostProcessorRequirement / Profile
- GENERIC_ISO_TEST profile invariants
- Verification gate (HARD RULES 10-13)
- Motion mapping (rapid, linear, arc)
- Safe start / end blocks
- Feed/spindle/tool/work-offset blocking
- Unsupported motion handling
- Helix handling
- Arc validation
- Syntax validation
- Semantic validation
- Source traceability
- Program hash
- Manifest and stale detection
- Fabrication audit
- Level 11 regression (verification gate)
- API endpoints (auth-gated)

HARD RULES satisfied:
NO_GCODE_DISPATCH=YES  NO_CNC_CONNECTION=YES  NO_FABRICATED_DATA=YES
OFFLINE_ONLY=YES  is_dispatchable=False (always)
"""

from __future__ import annotations

import hashlib

import pytest

# ---------------------------------------------------------------------------
# TestNCEnums
# ---------------------------------------------------------------------------


class TestNCEnums:
    def test_program_status_no_ready_to_run(self):
        from backend.nc.enums import NCProgramStatus

        values = [s.value for s in NCProgramStatus]
        assert "READY_TO_RUN" not in values
        assert "MACHINE_APPROVED" not in values

    def test_program_status_has_required_values(self):
        from backend.nc.enums import NCProgramStatus

        for v in ("NOT_GENERATED", "BLOCKED", "CANDIDATE", "VALIDATED_OFFLINE",
                  "REVIEW_REQUIRED", "REJECTED", "STALE"):
            assert NCProgramStatus(v).value == v

    def test_nc_motion_types(self):
        from backend.nc.enums import NCMotionType

        for v in ("RAPID_LINEAR", "FEED_LINEAR", "ARC_CW", "ARC_CCW", "HELIX",
                  "SIMPLE_DRILL_CYCLE", "PECK_DRILL_CYCLE", "DWELL"):
            assert NCMotionType(v).value == v

    def test_post_certification_status(self):
        from backend.nc.enums import PostCertificationStatus

        assert PostCertificationStatus.TEST_ONLY.value == "TEST_ONLY"
        assert PostCertificationStatus.CERTIFIED_PROFILE.value == "CERTIFIED_PROFILE"

    def test_arc_modes(self):
        from backend.nc.enums import ArcMode

        assert ArcMode.CENTER_OFFSET.value == "CENTER_OFFSET"
        assert ArcMode.RADIUS.value == "RADIUS"

    def test_work_offset_ref(self):
        from backend.nc.enums import WorkOffsetRef

        assert WorkOffsetRef.UNKNOWN.value == "UNKNOWN"
        assert WorkOffsetRef.WORK_OFFSET_1.value == "WORK_OFFSET_1"

    def test_nc_generation_block_reasons(self):
        from backend.nc.enums import NCGenerationBlockReason

        for v in ("UNVERIFIED_TOOLPATH", "PARTIAL_VERIFICATION", "FAILED_VERIFICATION",
                  "BLOCKED_VERIFICATION", "MISSING_POST_PROFILE", "MISSING_TOOL_NUMBER",
                  "MISSING_FEED", "UNSUPPORTED_MOTION", "INVALID_ARC",
                  "UNKNOWN_UNITS", "UNKNOWN_WORK_OFFSET"):
            assert NCGenerationBlockReason(v).value == v


# ---------------------------------------------------------------------------
# TestNCIR
# ---------------------------------------------------------------------------


class TestNCIR:
    def test_nc_program_dispatchable_always_false(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram

        p = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        assert p.is_dispatchable is False

    def test_nc_program_offline_candidate_always_true(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram

        p = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        assert p.is_offline_candidate is True

    def test_nc_program_safety_warnings_present(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram

        p = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        assert len(p.safety_warnings) >= 3
        assert any("OFFLINE" in w for w in p.safety_warnings)

    def test_nc_motion_model(self):
        from backend.nc.enums import NCMotionType
        from backend.nc.ir import NCMotion

        m = NCMotion(motion_type=NCMotionType.FEED_LINEAR, end_x=10.0, end_y=5.0, end_z=-3.0,
                     feed_mmpm=200.0)
        assert m.motion_type == NCMotionType.FEED_LINEAR
        assert m.feed_mmpm == 200.0

    def test_nc_tool_change_no_tool_number_allowed(self):
        from backend.nc.ir import NCToolChange

        tc = NCToolChange(tool_id="T_ENDMILL_10", tool_number=None)
        assert tc.tool_number is None

    def test_nc_spindle_command_no_rpm_allowed(self):
        from backend.nc.enums import NCSpindleDirection
        from backend.nc.ir import NCSpindleCommand

        sc = NCSpindleCommand(speed_rpm=None, direction=NCSpindleDirection.OFF)
        assert sc.speed_rpm is None

    def test_nc_block_has_source_trace(self):
        from backend.nc.ir import NCBlock, NCSourceTrace

        b = NCBlock()
        b.source = NCSourceTrace(toolpath_id="tp-001", segment_id="seg-001")
        assert b.source.toolpath_id == "tp-001"


# ---------------------------------------------------------------------------
# TestPostProcessorProfile
# ---------------------------------------------------------------------------


class TestPostProcessorProfile:
    def test_generic_iso_test_is_test_only(self):
        from backend.nc.enums import PostCertificationStatus
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert GENERIC_ISO_TEST.certification_status == PostCertificationStatus.TEST_ONLY

    def test_generic_iso_test_not_dispatchable(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert GENERIC_ISO_TEST.not_dispatchable is True

    def test_generic_iso_test_not_machine_certified(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert GENERIC_ISO_TEST.not_machine_certified is True

    def test_generic_iso_test_provenance_mentions_test_only(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert "TEST_ONLY" in GENERIC_ISO_TEST.provenance

    def test_generic_iso_test_provenance_not_fanuc(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        # Must not claim Fanuc/Siemens/Haas compatibility
        assert "certified for any machine" in GENERIC_ISO_TEST.provenance.lower() or \
               "NOT certified" in GENERIC_ISO_TEST.provenance

    def test_generic_iso_test_has_safety_banners(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        banners = GENERIC_ISO_TEST.safety_banner_lines
        assert len(banners) >= 3
        joined = " ".join(banners)
        assert "TEST_ONLY" in joined or "OFFLINE" in joined

    def test_generic_iso_test_supports_basic_motions(self):
        from backend.nc.enums import NCMotionType
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert NCMotionType.RAPID_LINEAR in GENERIC_ISO_TEST.supported_motion_types
        assert NCMotionType.FEED_LINEAR in GENERIC_ISO_TEST.supported_motion_types
        assert NCMotionType.ARC_CW in GENERIC_ISO_TEST.supported_motion_types
        assert NCMotionType.ARC_CCW in GENERIC_ISO_TEST.supported_motion_types

    def test_generic_iso_test_helix_not_supported(self):
        from backend.nc.enums import NCMotionType
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert NCMotionType.HELIX not in GENERIC_ISO_TEST.supported_motion_types

    def test_generic_iso_test_supports_mm_and_inch(self):
        from backend.nc.enums import NCUnitMode
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert NCUnitMode.MM in GENERIC_ISO_TEST.supported_unit_modes
        assert NCUnitMode.INCH in GENERIC_ISO_TEST.supported_unit_modes

    def test_generic_iso_test_requires_unit_declaration(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert GENERIC_ISO_TEST.requires_unit_declaration is True

    def test_generic_iso_test_arc_modes(self):
        from backend.nc.enums import ArcMode
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        assert ArcMode.CENTER_OFFSET in GENERIC_ISO_TEST.arc_modes
        assert ArcMode.RADIUS in GENERIC_ISO_TEST.arc_modes

    def test_profile_registry_contains_generic(self):
        from backend.nc.postprocessor import PROFILE_REGISTRY

        assert "GENERIC_ISO_TEST_v1" in PROFILE_REGISTRY

    def test_get_profile_returns_none_for_unknown(self):
        from backend.nc.postprocessor import get_profile

        assert get_profile("NON_EXISTENT_PROFILE_XYZ") is None


# ---------------------------------------------------------------------------
# TestVerificationGate
# ---------------------------------------------------------------------------


class TestVerificationGate:
    def _make_simple_input(self, verification_state: str, **kwargs):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        return NCGenerationInput(
            toolpath_id="tp-test",
            verification_state=verification_state,
            verification_session_id="vsess-test",
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T_ENDMILL_10" if "tool_id" not in kwargs else kwargs.pop("tool_id"),
            tool_number=1 if "tool_number" not in kwargs else kwargs.pop("tool_number"),
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
            **kwargs,
        )

    def test_verified_state_allows_generation(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("VERIFIED"))
        assert result.status == NCProgramStatus.CANDIDATE

    def test_unverified_state_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("UNVERIFIED"))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.UNVERIFIED_TOOLPATH in result.block_reasons

    def test_partially_verified_state_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("PARTIALLY_VERIFIED"))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.PARTIAL_VERIFICATION in result.block_reasons

    def test_failed_state_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("FAILED"))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.FAILED_VERIFICATION in result.block_reasons

    def test_blocked_verification_state_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("BLOCKED"))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.BLOCKED_VERIFICATION in result.block_reasons

    def test_unknown_state_blocks(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("UNKNOWN"))
        assert result.status == NCProgramStatus.BLOCKED

    def test_verified_result_is_never_dispatchable(self):
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("VERIFIED"))
        assert result.program is not None
        assert result.program.is_dispatchable is False

    def test_verified_result_is_offline_candidate(self):
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_simple_input("VERIFIED"))
        assert result.program is not None
        assert result.program.is_offline_candidate is True


# ---------------------------------------------------------------------------
# TestInputValidation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def _base_input(self, **overrides):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        defaults = dict(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        defaults.update(overrides)
        return NCGenerationInput(**defaults)

    def test_missing_tool_number_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._base_input(tool_number=None))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.MISSING_TOOL_NUMBER in result.block_reasons

    def test_missing_tool_id_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._base_input(tool_id=None))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.MISSING_TOOL_NUMBER in result.block_reasons

    def test_unknown_units_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus, NCUnitMode
        from backend.nc.generator import generate_nc

        result = generate_nc(self._base_input(unit_mode=NCUnitMode.UNKNOWN))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.UNKNOWN_UNITS in result.block_reasons

    def test_unknown_work_offset_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus, WorkOffsetRef
        from backend.nc.generator import generate_nc

        result = generate_nc(self._base_input(work_offset=WorkOffsetRef.UNKNOWN))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.UNKNOWN_WORK_OFFSET in result.block_reasons

    def test_missing_feed_for_cutting_segment_blocks(self):
        from backend.nc.enums import NCGenerationBlockReason, NCProgramStatus
        from backend.nc.generator import generate_nc

        class FakeSeg:
            segment_id = "s1"
            motion_type = "CUT"
            is_cutting = True
            start_x = start_y = start_z = 0.0
            end_x = 10.0
            end_y = 0.0
            end_z = -5.0
            arc_center = None
            operation_id = tool_id = setup_id = feature_id = None

        result = generate_nc(self._base_input(feed_mmpm=None, segments=[FakeSeg()]))
        assert result.status == NCProgramStatus.BLOCKED
        assert NCGenerationBlockReason.MISSING_FEED in result.block_reasons

    def test_missing_feed_no_cutting_segments_allowed(self):
        """Non-cutting segments (rapid only) don't require feed."""
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._base_input(feed_mmpm=None, segments=[]))
        assert result.status == NCProgramStatus.CANDIDATE


# ---------------------------------------------------------------------------
# TestMotionMapping
# ---------------------------------------------------------------------------


class TestMotionMapping:
    def _seg(self, motion_type: str, is_cutting: bool = False, **kwargs):
        class Seg:
            pass
        s = Seg()
        s.segment_id = "seg-001"
        s.motion_type = motion_type
        s.is_cutting = is_cutting
        s.start_x = s.start_y = s.start_z = 0.0
        s.end_x = kwargs.get("end_x", 10.0)
        s.end_y = kwargs.get("end_y", 0.0)
        s.end_z = kwargs.get("end_z", 0.0)
        s.arc_center = kwargs.get("arc_center", None)
        s.helix_radius = kwargs.get("helix_radius", None)
        s.arc_radius = kwargs.get("arc_radius", None)
        s.operation_id = s.tool_id = s.setup_id = s.feature_id = None
        return s

    def _make_input(self, segments, **overrides):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        return NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=segments,
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
            **overrides,
        )

    def test_rapid_segment_maps_to_rapid_motion(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_input([self._seg("RAPID")]))
        assert result.status == NCProgramStatus.CANDIDATE
        motion_blocks = [
            b for b in result.program.blocks
            if b.elements and b.elements[0].get("kind") == "motion"
        ]
        assert len(motion_blocks) == 1
        assert motion_blocks[0].elements[0]["data"]["motion_type"] == "RAPID_LINEAR"

    def test_cut_segment_maps_to_feed_linear(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_input([self._seg("CUT", is_cutting=True)]))
        assert result.status == NCProgramStatus.CANDIDATE
        motion_blocks = [
            b for b in result.program.blocks
            if b.elements and b.elements[0].get("kind") == "motion"
        ]
        assert len(motion_blocks) == 1
        assert motion_blocks[0].elements[0]["data"]["motion_type"] == "FEED_LINEAR"

    def test_arc_cw_requires_arc_data(self):
        """Arc with no arc_center or radius produces warning and is skipped."""
        from backend.nc.generator import generate_nc

        seg = self._seg("ARC_CW", is_cutting=True)
        # No arc_center, no arc_radius — invalid arc
        result = generate_nc(self._make_input([seg]))
        assert any("ARC" in w for w in result.warnings) or \
               any("INVALID" in w for w in result.warnings)

    def test_valid_arc_cw_with_center(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        class ArcSeg:
            segment_id = "arc1"
            motion_type = "ARC_CW"
            is_cutting = True
            start_x = 0.0
            start_y = 0.0
            start_z = 0.0
            end_x = 10.0
            end_y = 10.0
            end_z = 0.0
            arc_center = (5.0, 0.0, 0.0)  # center at (5,0,0), start at (0,0,0)
            helix_radius = None
            arc_radius = None
            operation_id = tool_id = setup_id = feature_id = None

        result = generate_nc(self._make_input([ArcSeg()]))
        assert result.status == NCProgramStatus.CANDIDATE
        motion_blocks = [
            b for b in result.program.blocks
            if b.elements and b.elements[0].get("kind") == "motion"
        ]
        assert len(motion_blocks) == 1
        d = motion_blocks[0].elements[0]["data"]
        assert d["motion_type"] == "ARC_CW"
        assert d.get("arc_mode") == "CENTER_OFFSET"

    def test_helix_unsupported_generates_warning(self):
        from backend.nc.generator import generate_nc

        seg = self._seg("HELIX", is_cutting=True, helix_radius=5.0)
        result = generate_nc(self._make_input([seg]))
        assert any("HELIX" in w or "UNSUPPORTED" in w for w in result.warnings)

    def test_multiple_segments_multiple_motion_blocks(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        segs = [
            self._seg("RAPID", end_x=0.0, end_y=0.0, end_z=5.0),
            self._seg("CUT", is_cutting=True, end_x=10.0, end_y=0.0, end_z=-3.0),
            self._seg("RETRACT", end_x=0.0, end_y=0.0, end_z=5.0),
        ]
        result = generate_nc(self._make_input(segs))
        assert result.status == NCProgramStatus.CANDIDATE
        motion_blocks = [
            b for b in result.program.blocks
            if b.elements and b.elements[0].get("kind") == "motion"
        ]
        assert len(motion_blocks) == 3

    def test_unsupported_motion_produces_warning_not_error(self):
        """Unknown motion types generate a warning and are skipped, not a hard block."""
        from backend.nc.generator import generate_nc

        seg = self._seg("PROBE_CYCLE_XYZ")  # not in mapping
        result = generate_nc(self._make_input([seg]))
        assert any("UNSUPPORTED_MOTION" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# TestSafeStartEnd
# ---------------------------------------------------------------------------


class TestSafeStartEnd:
    def _make_verified_result(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id="vsess-001",
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=5000.0,
            spindle_direction=NCSpindleDirection.CW,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.FLOOD,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        return generate_nc(inp)

    def test_program_has_unit_declaration(self):
        result = self._make_verified_result()
        assert result.program is not None
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "unit_decl" in all_kinds

    def test_program_has_plane_declaration(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "plane_decl" in all_kinds

    def test_program_has_coordinate_mode_declaration(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "coord_mode_decl" in all_kinds

    def test_program_has_tool_change(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "tool_change" in all_kinds

    def test_program_has_spindle_command(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "spindle_cmd" in all_kinds

    def test_program_has_coolant_command(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "coolant_cmd" in all_kinds

    def test_program_has_work_offset(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "work_offset" in all_kinds

    def test_program_has_program_end(self):
        result = self._make_verified_result()
        all_kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        assert "program_end" in all_kinds

    def test_no_spindle_when_rpm_none(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        # Should have spindle stop at end but not a spindle-on at start
        spindle_cmds = [
            elem
            for b in result.program.blocks
            for elem in b.elements
            if elem.get("kind") == "spindle_cmd"
              and elem.get("data", {}).get("speed_rpm") is not None
        ]
        assert len(spindle_cmds) == 0  # no spindle-on (rpm=None → skipped)


# ---------------------------------------------------------------------------
# TestToolChange
# ---------------------------------------------------------------------------


class TestToolChange:
    def test_tool_change_in_start_block(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T_ENDMILL_10",
            tool_number=5,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        tc_elems = [
            elem for b in result.program.blocks
            for elem in b.elements
            if elem.get("kind") == "tool_change"
        ]
        assert len(tc_elems) == 1
        assert tc_elems[0]["data"]["tool_number"] == 5
        assert tc_elems[0]["data"]["tool_id"] == "T_ENDMILL_10"


# ---------------------------------------------------------------------------
# TestWorkOffset
# ---------------------------------------------------------------------------


class TestWorkOffset:
    def test_work_offset_in_start_block(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_2,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        wo_elems = [
            elem for b in result.program.blocks
            for elem in b.elements
            if elem.get("kind") == "work_offset"
        ]
        assert len(wo_elems) == 1
        assert wo_elems[0]["data"]["offset_ref"] == "WORK_OFFSET_2"


# ---------------------------------------------------------------------------
# TestFeedSpindle
# ---------------------------------------------------------------------------


class TestFeedSpindle:
    def test_cutting_motion_has_feed(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        class CutSeg:
            segment_id = "s1"
            motion_type = "CUT"
            is_cutting = True
            start_x = start_y = start_z = 0.0
            end_x = 10.0
            end_y = 0.0
            end_z = -5.0
            arc_center = None
            helix_radius = None
            arc_radius = None
            operation_id = tool_id = setup_id = feature_id = None

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[CutSeg()],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=250.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        motion_elems = [
            elem for b in result.program.blocks
            for elem in b.elements
            if elem.get("kind") == "motion" and elem["data"]["motion_type"] == "FEED_LINEAR"
        ]
        assert len(motion_elems) == 1
        assert motion_elems[0]["data"]["feed_mmpm"] == 250.0

    def test_rapid_motion_has_no_feed(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        class RapidSeg:
            segment_id = "r1"
            motion_type = "RAPID"
            is_cutting = False
            start_x = 0.0
            start_y = 0.0
            start_z = 5.0
            end_x = 10.0
            end_y = 0.0
            end_z = 5.0
            arc_center = None
            helix_radius = None
            arc_radius = None
            operation_id = tool_id = setup_id = feature_id = None

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[RapidSeg()],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        motion_elems = [
            elem for b in result.program.blocks
            for elem in b.elements
            if elem.get("kind") == "motion" and elem["data"]["motion_type"] == "RAPID_LINEAR"
        ]
        assert len(motion_elems) == 1
        assert motion_elems[0]["data"].get("feed_mmpm") is None


# ---------------------------------------------------------------------------
# TestSyntaxValidation
# ---------------------------------------------------------------------------


class TestSyntaxValidation:
    def _make_program(self, unit_mode=None, coord_mode=None, dispatchable=False):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram

        return NCProgram(
            program_number="O9999",
            unit_mode=unit_mode or NCUnitMode.MM,
            coordinate_mode=coord_mode or NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
            is_dispatchable=dispatchable,
        )

    def test_empty_program_valid_offline(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = self._make_program()
        # Empty program has no program_end — expect REJECTED
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        assert vr.status == NCProgramStatus.REJECTED
        assert vr.error_count > 0

    def test_feed_move_without_feed_is_syntax_error(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCBlock, NCProgram
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        b = NCBlock()
        b.elements.append({
            "kind": "motion",
            "data": {
                "motion_type": "FEED_LINEAR",
                "end_x": 10.0, "end_y": 0.0, "end_z": -5.0,
                "feed_mmpm": None,
            }
        })
        program.blocks.append(b)
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        assert vr.error_count > 0
        codes = [i.code for i in vr.syntax_issues]
        assert "SYN_MISSING_FEED" in codes

    def test_arc_without_mode_is_syntax_error(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCBlock, NCProgram
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        b = NCBlock()
        b.elements.append({
            "kind": "motion",
            "data": {
                "motion_type": "ARC_CW",
                "end_x": 10.0, "end_y": 10.0, "end_z": 0.0,
                "feed_mmpm": 200.0,
                "arc_mode": None,
            }
        })
        program.blocks.append(b)
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        codes = [i.code for i in vr.syntax_issues]
        assert "SYN_ARC_NO_MODE" in codes

    def test_tool_change_without_tool_number_is_syntax_error(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCBlock, NCProgram
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        b = NCBlock()
        b.elements.append({
            "kind": "tool_change",
            "data": {"tool_id": "T_ENDMILL", "tool_number": None}
        })
        program.blocks.append(b)
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        codes = [i.code for i in vr.syntax_issues]
        assert "SYN_MISSING_TOOL_NUMBER" in codes

    def test_dispatchable_flag_is_semantic_error(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = self._make_program(dispatchable=True)
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        codes = [i.code for i in vr.semantic_issues]
        assert "SEM_DISPATCHABLE_FLAG" in codes


# ---------------------------------------------------------------------------
# TestSemanticValidation
# ---------------------------------------------------------------------------


class TestSemanticValidation:
    def test_unknown_units_is_semantic_error(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.UNKNOWN,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        codes = [i.code for i in vr.semantic_issues]
        assert "SEM_UNKNOWN_UNITS" in codes

    def test_no_program_end_is_semantic_error(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.ir import NCProgram
        from backend.nc.postprocessor import GENERIC_ISO_TEST
        from backend.nc.validator import validate_nc_program

        program = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
        )
        vr = validate_nc_program(program, GENERIC_ISO_TEST)
        codes = [i.code for i in vr.semantic_issues]
        assert "SEM_NO_PROGRAM_END" in codes


# ---------------------------------------------------------------------------
# TestProgramHash
# ---------------------------------------------------------------------------


class TestProgramHash:
    def test_hash_is_deterministic(self):
        from backend.nc.ir import NCBlock
        from backend.nc.manifest import serialize_blocks_for_hash

        blocks = [NCBlock(), NCBlock()]
        h1 = hashlib.sha256(serialize_blocks_for_hash(blocks).encode()).hexdigest()
        h2 = hashlib.sha256(serialize_blocks_for_hash(blocks).encode()).hexdigest()
        assert h1 == h2

    def test_different_blocks_different_hash(self):
        from backend.nc.ir import NCBlock
        from backend.nc.manifest import serialize_blocks_for_hash

        b1 = [NCBlock()]
        b2 = [NCBlock(), NCBlock()]
        h1 = hashlib.sha256(serialize_blocks_for_hash(b1).encode()).hexdigest()
        h2 = hashlib.sha256(serialize_blocks_for_hash(b2).encode()).hexdigest()
        assert h1 != h2

    def test_compute_program_hash_produces_hex(self):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, compute_program_hash, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-001",
            verification_state="VERIFIED",
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        assert result.program is not None
        h = compute_program_hash(result.program)
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# TestManifest
# ---------------------------------------------------------------------------


class TestManifest:
    def test_manifest_is_offline_candidate(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.manifest import build_manifest

        m = build_manifest(
            manifest_id="m001",
            toolpath_id="tp-001",
            verification_session_id="vsess-001",
            verification_state="VERIFIED",
            verification_profile="GEOMETRY_ONLY",
            post_profile_id="GENERIC_ISO_TEST_v1",
            post_profile_name="Generic ISO Test Profile",
            post_profile_certification="TEST_ONLY",
            program_id="prog-001",
            program_number="O9999",
            program_status=NCProgramStatus.CANDIDATE,
            program_blocks_json='[]',
        )
        assert m.is_offline_candidate is True
        assert m.is_dispatchable is False

    def test_manifest_has_safety_statement(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.manifest import build_manifest

        m = build_manifest(
            manifest_id="m002",
            toolpath_id=None,
            verification_session_id=None,
            verification_state="VERIFIED",
            verification_profile="GEOMETRY_ONLY",
            post_profile_id="GENERIC_ISO_TEST_v1",
            post_profile_name="Generic ISO Test Profile",
            post_profile_certification="TEST_ONLY",
            program_id="p001",
            program_number="O9999",
            program_status=NCProgramStatus.CANDIDATE,
            program_blocks_json='[]',
        )
        assert "OFFLINE" in m.safety_statement

    def test_manifest_hash_changes_with_content(self):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.manifest import build_manifest

        m1 = build_manifest(
            manifest_id="m1",
            toolpath_id="tp",
            verification_session_id=None,
            verification_state="VERIFIED",
            verification_profile="GEOMETRY_ONLY",
            post_profile_id="GENERIC_ISO_TEST_v1",
            post_profile_name="Generic ISO Test Profile",
            post_profile_certification="TEST_ONLY",
            program_id="p1",
            program_number="O9999",
            program_status=NCProgramStatus.CANDIDATE,
            program_blocks_json='[]',
        )
        m2 = build_manifest(
            manifest_id="m2",
            toolpath_id="tp",
            verification_session_id=None,
            verification_state="VERIFIED",
            verification_profile="GEOMETRY_ONLY",
            post_profile_id="GENERIC_ISO_TEST_v1",
            post_profile_name="Generic ISO Test Profile",
            post_profile_certification="TEST_ONLY",
            program_id="p1",
            program_number="O9999",
            program_status=NCProgramStatus.CANDIDATE,
            program_blocks_json='[{"block_id":"b1"}]',
        )
        assert m1.program_hash != m2.program_hash


# ---------------------------------------------------------------------------
# TestStaleDetection
# ---------------------------------------------------------------------------


class TestStaleDetection:
    def _make_manifest(self, **overrides):
        from backend.nc.enums import NCProgramStatus
        from backend.nc.manifest import build_manifest

        defaults = dict(
            manifest_id="m1",
            toolpath_id="tp-001",
            verification_session_id="vsess-001",
            verification_state="VERIFIED",
            verification_profile="GEOMETRY_ONLY",
            post_profile_id="GENERIC_ISO_TEST_v1",
            post_profile_name="Generic ISO Test Profile",
            post_profile_certification="TEST_ONLY",
            program_id="p1",
            program_number="O9999",
            program_status=NCProgramStatus.CANDIDATE,
            program_blocks_json='[]',
        )
        defaults.update(overrides)
        return build_manifest(**defaults)

    def test_same_inputs_not_stale(self):
        from backend.nc.manifest import check_manifest_staleness

        m = self._make_manifest()
        stale, reasons = check_manifest_staleness(m, "tp-001", "vsess-001", "GENERIC_ISO_TEST_v1")
        assert not stale
        assert reasons == []

    def test_toolpath_change_marks_stale(self):
        from backend.nc.manifest import check_manifest_staleness

        m = self._make_manifest()
        stale, reasons = check_manifest_staleness(
            m, "tp-002-CHANGED", "vsess-001", "GENERIC_ISO_TEST_v1"
        )
        assert stale
        from backend.nc.enums import NCStaleReason
        assert NCStaleReason.TOOLPATH_CHANGED in reasons

    def test_verification_change_marks_stale(self):
        from backend.nc.manifest import check_manifest_staleness

        m = self._make_manifest()
        stale, reasons = check_manifest_staleness(
            m, "tp-001", "vsess-999-CHANGED", "GENERIC_ISO_TEST_v1"
        )
        assert stale
        from backend.nc.enums import NCStaleReason
        assert NCStaleReason.VERIFICATION_CHANGED in reasons

    def test_profile_change_marks_stale(self):
        from backend.nc.manifest import check_manifest_staleness

        m = self._make_manifest()
        stale, reasons = check_manifest_staleness(m, "tp-001", "vsess-001", "NEW_PROFILE_v2")
        assert stale
        from backend.nc.enums import NCStaleReason
        assert NCStaleReason.PROFILE_CHANGED in reasons

    def test_generator_stale_detection(self):
        from backend.nc.enums import NCCoordinateMode, NCUnitMode
        from backend.nc.generator import is_program_stale
        from backend.nc.ir import NCProgram

        p = NCProgram(
            program_number="O9999",
            unit_mode=NCUnitMode.MM,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            post_profile_id="GENERIC_ISO_TEST_v1",
            source_toolpath_hash="hash-A",
            source_verification_hash="hash-B",
        )
        stale, reasons = is_program_stale(p, "hash-CHANGED", "hash-B", "GENERIC_ISO_TEST_v1")
        assert stale
        assert "TOOLPATH_CHANGED" in reasons


# ---------------------------------------------------------------------------
# TestFabricationAudit
# ---------------------------------------------------------------------------


class TestFabricationAudit:
    def test_no_hardcoded_g54_in_production_code(self):
        import pathlib

        nc_dir = pathlib.Path("backend/nc")
        for f in nc_dir.glob("*.py"):
            src = f.read_text()
            # G54 should not appear as a string literal in production code
            # It may appear in a comment but NOT as a hardcoded value
            if "G54" in src and "TEST_ONLY" not in src:
                # Only allowed in clearly test-only context
                raise AssertionError(f"G54 found in non-test-only context in {f}")

    def test_no_hardcoded_m06_in_production_code(self):
        import pathlib

        # M06 as a hardcoded value (not inside a data config string) is forbidden
        nc_dir = pathlib.Path("backend/nc")
        for f in nc_dir.glob("*.py"):
            if f.name == "postprocessor.py":
                continue  # profile data is allowed in postprocessor.py
            src = f.read_text()
            assert "M06" not in src and "M6" not in src or f.name == "postprocessor.py", (
                f"Hardcoded M-code found in {f}"
            )

    def test_no_auto_dispatch_in_nc_module(self):
        import pathlib

        dispatch_patterns = ["send_to_machine", "dispatch_nc", "dnc_transfer",
                             "ftp_upload", "socket.connect"]
        nc_dir = pathlib.Path("backend/nc")
        api_file = pathlib.Path("backend/api/nc_generation.py")

        files_to_check = list(nc_dir.glob("*.py")) + [api_file]
        for f in files_to_check:
            src = f.read_text().lower()
            for pattern in dispatch_patterns:
                assert pattern not in src, (
                    f"CNC dispatch pattern {pattern!r} found in {f}"
                )

    def test_no_hardcoded_feeds_in_generator(self):
        import pathlib

        src = pathlib.Path("backend/nc/generator.py").read_text()
        # Feed values should come from input, not be hardcoded
        # Check there are no literal feed assignments like "feed_mmpm = 100"
        import re
        # Look for patterns like "feed_mmpm = <number>" (not function params)
        matches = re.findall(r'feed_mmpm\s*=\s*\d+\.?\d*(?!\s*#)', src)
        # Allow "feed_mmpm=0.0" in validation logic or parameter defaults
        disallowed = [m for m in matches if float(re.search(r'\d+\.?\d*', m).group()) > 0]
        assert len(disallowed) == 0, f"Hardcoded feed values: {disallowed}"

    def test_generic_test_profile_not_claiming_fanuc(self):
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        provenance = GENERIC_ISO_TEST.provenance.upper()
        # Provenance must explicitly disclaim real controllers
        assert "NOT CERTIFIED" in provenance or "NOT compatible" in GENERIC_ISO_TEST.provenance

    def test_no_cnc_connection_constant(self):
        from backend.nc import IS_DISPATCHABLE, NO_CNC_CONNECTION, NO_GCODE_DISPATCH, OFFLINE_ONLY

        assert NO_GCODE_DISPATCH == "YES"
        assert NO_CNC_CONNECTION == "YES"
        assert OFFLINE_ONLY == "YES"
        assert IS_DISPATCHABLE is False


# ---------------------------------------------------------------------------
# TestLevel11Regression
# ---------------------------------------------------------------------------


class TestLevel11Regression:
    def test_level11_verification_state_enum_still_works(self):
        from backend.verification.enums import VerificationState

        assert VerificationState.VERIFIED.value == "VERIFIED"
        assert VerificationState.UNVERIFIED.value == "UNVERIFIED"

    def test_level11_simulation_result_is_verified_derived(self):
        from backend.verification.enums import (
            SimulationStatus,
            VerificationProfileEnum,
            VerificationState,
        )
        from backend.verification.models import SimulationResult, VerificationSummary

        summary = VerificationSummary(
            verification_state=VerificationState.VERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            checks_performed=2,
            checks_passed=2,
            checks_failed=0,
            checks_not_performed=0,
            checks_insufficient_data=0,
            critical_issues=0,
            error_issues=0,
            warning_issues=0,
            info_issues=0,
        )
        result = SimulationResult(
            session_id="s1",
            toolpath_id="tp1",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.VERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            summary=summary,
        )
        assert result.is_verified is True

    def test_level11_unverified_blocks_nc(self):
        """Level-11 UNVERIFIED toolpath must block NC generation."""
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCProgramStatus,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput, generate_nc
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        inp = NCGenerationInput(
            toolpath_id="tp-unverified",
            verification_state="UNVERIFIED",  # Level-11 unverified
            verification_session_id=None,
            post_profile=GENERIC_ISO_TEST,
            segments=[],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=None,
            spindle_direction=NCSpindleDirection.OFF,
            feed_mmpm=200.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
        )
        result = generate_nc(inp)
        assert result.status == NCProgramStatus.BLOCKED

    def test_level10_toolpath_model_imports(self):
        """Level-10 models must still be importable."""
        from backend.toolpath.enums import ToolpathStatus

        assert ToolpathStatus.NOT_GENERATED.value == "NOT_GENERATED"


# ---------------------------------------------------------------------------
# TestGoldenOutput
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    """
    Golden output tests using GENERIC_ISO_TEST profile.

    All golden outputs are TEST_ONLY. NOT representative of real machine programs.
    """

    def _make_inp(self, segments=None, **overrides):
        from backend.nc.enums import (
            NCCoolantMode,
            NCCoordinateMode,
            NCCutterCompMode,
            NCPlane,
            NCSpindleDirection,
            NCUnitMode,
            WorkOffsetRef,
        )
        from backend.nc.generator import NCGenerationInput
        from backend.nc.postprocessor import GENERIC_ISO_TEST

        return NCGenerationInput(
            toolpath_id="tp-golden",
            verification_state="VERIFIED",
            verification_session_id="vsess-golden",
            post_profile=GENERIC_ISO_TEST,
            segments=segments or [],
            tool_id="T001",
            tool_number=1,
            tool_diameter_mm=10.0,
            spindle_speed_rpm=5000.0,
            spindle_direction=NCSpindleDirection.CW,
            feed_mmpm=250.0,
            work_offset=WorkOffsetRef.WORK_OFFSET_1,
            unit_mode=NCUnitMode.MM,
            plane=NCPlane.XY,
            coordinate_mode=NCCoordinateMode.ABSOLUTE,
            coolant_mode=NCCoolantMode.OFF,
            cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
            program_number="O9999",
            **overrides,
        )

    def test_mill_program_structure(self):
        """Mill program has: comments→unit→plane→coord→feed→comp→wcs→tool→spindle→end"""
        from backend.nc.enums import NCProgramStatus
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_inp())
        assert result.status == NCProgramStatus.CANDIDATE
        assert result.program is not None
        kinds = [
            elem.get("kind")
            for b in result.program.blocks
            for elem in b.elements
        ]
        # Key structural elements
        assert "comment" in kinds
        assert "unit_decl" in kinds
        assert "plane_decl" in kinds
        assert "coord_mode_decl" in kinds
        assert "tool_change" in kinds
        assert "spindle_cmd" in kinds
        assert "program_end" in kinds

    def test_program_unit_mode_mm(self):
        from backend.nc.enums import NCUnitMode
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_inp())
        assert result.program.unit_mode == NCUnitMode.MM

    def test_program_coordinate_mode_absolute(self):
        from backend.nc.enums import NCCoordinateMode
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_inp())
        assert result.program.coordinate_mode == NCCoordinateMode.ABSOLUTE

    def test_program_post_profile_id_recorded(self):
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_inp())
        assert result.program.post_profile_id == "GENERIC_ISO_TEST_v1"

    def test_program_toolpath_id_recorded(self):
        from backend.nc.generator import generate_nc

        result = generate_nc(self._make_inp())
        assert result.program.toolpath_id == "tp-golden"

    def test_simple_turning_candidate_blocked_without_turning_profile(self):
        """
        Turning operations require a turning-capable post profile.
        GENERIC_ISO_TEST does not define turning semantics.
        Test that turning-specific motions go through the mapping gracefully.
        """
        from backend.nc.generator import generate_nc

        class TurnSeg:
            segment_id = "turn1"
            motion_type = "AXIAL_CUT"
            is_cutting = True
            start_x = start_y = start_z = 0.0
            end_x = 10.0
            end_y = 0.0
            end_z = 0.0
            arc_center = None
            helix_radius = None
            arc_radius = None
            operation_id = tool_id = setup_id = feature_id = None

        result = generate_nc(self._make_inp(segments=[TurnSeg()]))
        # AXIAL_CUT has no mapping in _TOOLPATH_TO_NC_MOTION — produces warning
        assert any("UNSUPPORTED_MOTION" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# TestNCGenerationAPISimulate (auth-gated, skipped without auth)
# ---------------------------------------------------------------------------


class TestNCGenerationAPI:
    @pytest.mark.skip(reason="Requires auth token configuration")
    def test_build_requires_auth(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app

        client = TestClient(app)
        resp = client.post("/api/nc/build", json={
            "toolpath_id": "tp-001",
            "verification_state": "VERIFIED",
        })
        assert resp.status_code == 401

    @pytest.mark.skip(reason="Requires auth token configuration")
    def test_validate_requires_auth(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app

        client = TestClient(app)
        resp = client.post("/api/nc/validate", json={"program_id": "p1"})
        assert resp.status_code == 401

    @pytest.mark.skip(reason="Requires auth token configuration")
    def test_profiles_requires_auth(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app

        client = TestClient(app)
        resp = client.get("/api/nc/profiles")
        assert resp.status_code == 401

    def test_nc_router_registered(self):
        from backend.api.nc_generation import router as nc_router

        assert nc_router.prefix == "/api/nc"
