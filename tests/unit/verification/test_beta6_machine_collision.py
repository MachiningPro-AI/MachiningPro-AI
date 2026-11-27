"""Phase V — Machine component collision tests."""

import pytest
from backend.verification.machine_collision import (
    MachineComponentCollisionResult,
    MachineComponentGeometry,
    run_machine_collision_checks,
)


def _comp(x0=0.0, y0=0.0, z0=0.0, x1=50.0, y1=50.0, z1=50.0, cid="C1"):
    return MachineComponentGeometry(
        component_id=cid,
        min_x_mm=x0, min_y_mm=y0, min_z_mm=z0,
        max_x_mm=x1, max_y_mm=y1, max_z_mm=z1,
    )


def _bbox(x0, y0, z0, x1, y1, z1):
    return (x0, y0, z0, x1, y1, z1)


class TestMissingGeometry:
    def test_missing_component_not_verifiable(self):
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=None, table_geom=None,
            part_bbox=_bbox(0, 0, 0, 100, 100, 50),
            stock_bbox=None,
        )
        assert checks["HEAD_PART"].status == "NOT_VERIFIABLE"
        assert checks["SPINDLE_PART"].status == "NOT_VERIFIABLE"
        assert checks["TABLE_TOOL"].status == "NOT_VERIFIABLE"

    def test_missing_target_not_performed(self):
        head = _comp(cid="HEAD")
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=None, stock_bbox=None,
        )
        assert checks["HEAD_PART"].status == "NOT_PERFORMED"

    def test_missing_fixtures_not_performed(self):
        head = _comp(cid="HEAD")
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=None, stock_bbox=None, fixtures=[],
        )
        assert checks["HEAD_FIXTURE"].status == "NOT_PERFORMED"

    def test_no_fabricated_pass(self):
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=None, table_geom=None,
            part_bbox=None, stock_bbox=None,
        )
        for name, r in checks.items():
            assert r.status != "PASS", f"{name} must not fabricate PASS"


class TestCollisionDetection:
    def test_no_collision_pass(self):
        head = _comp(x0=-50, y0=-50, z0=200, x1=50, y1=50, z1=300, cid="HEAD")
        part = _bbox(0, 0, 0, 100, 100, 50)
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=part, stock_bbox=None,
        )
        assert checks["HEAD_PART"].status == "PASS"

    def test_collision_fail(self):
        head = _comp(x0=0, y0=0, z0=0, x1=100, y1=100, z1=100, cid="HEAD")
        part = _bbox(50, 50, 50, 150, 150, 150)  # overlaps head
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=part, stock_bbox=None,
        )
        assert checks["HEAD_PART"].status == "FAIL"
        assert checks["HEAD_PART"].collision_count > 0

    def test_clearance_positive_no_collision(self):
        head = _comp(x0=0, y0=0, z0=0, x1=50, y1=50, z1=50, cid="HEAD")
        part = _bbox(100, 100, 100, 200, 200, 200)
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=part, stock_bbox=None,
        )
        r = checks["HEAD_PART"]
        assert r.min_clearance_mm > 0

    def test_clearance_negative_on_overlap(self):
        head = _comp(x0=0, y0=0, z0=0, x1=100, y1=100, z1=100, cid="HEAD")
        part = _bbox(50, 50, 50, 150, 150, 150)
        checks = run_machine_collision_checks(
            head_geom=head, spindle_geom=None, table_geom=None,
            part_bbox=part, stock_bbox=None,
        )
        r = checks["HEAD_PART"]
        assert r.min_clearance_mm < 0

    def test_all_seven_checks_present(self):
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=None, table_geom=None,
            part_bbox=None, stock_bbox=None,
        )
        expected = {"HEAD_PART", "HEAD_STOCK", "HEAD_FIXTURE",
                    "SPINDLE_PART", "SPINDLE_FIXTURE",
                    "TABLE_TOOL", "TABLE_HOLDER"}
        assert set(checks.keys()) == expected

    def test_fixture_collision(self):
        spindle = _comp(x0=0, y0=0, z0=0, x1=100, y1=100, z1=100, cid="SPINDLE")
        fix = _comp(x0=50, y0=50, z0=50, x1=150, y1=150, z1=150, cid="FIX")
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=spindle, table_geom=None,
            part_bbox=None, stock_bbox=None, fixtures=[fix],
        )
        assert checks["SPINDLE_FIXTURE"].status == "FAIL"

    def test_fixture_no_collision(self):
        spindle = _comp(x0=0, y0=0, z0=0, x1=50, y1=50, z1=50, cid="SPINDLE")
        fix = _comp(x0=100, y0=100, z0=100, x1=150, y1=150, z1=150, cid="FIX")
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=spindle, table_geom=None,
            part_bbox=None, stock_bbox=None, fixtures=[fix],
        )
        assert checks["SPINDLE_FIXTURE"].status == "PASS"

    def test_table_tool_collision(self):
        table = _comp(x0=-300, y0=-300, z0=-50, x1=300, y1=300, z1=0, cid="TABLE")
        tool_bbox = _bbox(-10, -10, -60, 10, 10, 50)  # tool goes below table
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=None, table_geom=table,
            part_bbox=None, stock_bbox=None, tool_bbox=tool_bbox,
        )
        assert checks["TABLE_TOOL"].status == "FAIL"

    def test_result_dataclass(self):
        checks = run_machine_collision_checks(
            head_geom=None, spindle_geom=None, table_geom=None,
            part_bbox=None, stock_bbox=None,
        )
        for r in checks.values():
            assert isinstance(r, MachineComponentCollisionResult)
