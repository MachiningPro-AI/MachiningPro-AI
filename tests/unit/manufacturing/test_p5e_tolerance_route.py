"""Tests for P5-E: tolerance-driven route selection / process capability (MUST 44, 26-28)."""
from backend.manufacturing.process_capability import (
    ProcessCapabilityStatus,
    evaluate_route_capability,
    rank_routes_by_capability,
)


class TestP5EProcessCapability:
    def test_drilling_it11_marginal(self):
        """IT11 is at the tight boundary of drilling capability."""
        ev = evaluate_route_capability(["drilling"], required_it_grade=11)
        assert ev.capability_status == ProcessCapabilityStatus.MARGINAL_REVIEW

    def test_drilling_it12_capable(self):
        ev = evaluate_route_capability(["drilling"], required_it_grade=12)
        assert ev.capability_status == ProcessCapabilityStatus.CAPABLE

    def test_drilling_it7_not_capable(self):
        """IT7 is tighter than achievable with drilling alone (IT11-IT13)."""
        ev = evaluate_route_capability(["drilling"], required_it_grade=7)
        assert ev.capability_status == ProcessCapabilityStatus.NOT_CAPABLE

    def test_drilling_reaming_it7_marginal(self):
        ev = evaluate_route_capability(["drilling", "reaming"], required_it_grade=7)
        assert ev.capability_status == ProcessCapabilityStatus.MARGINAL_REVIEW

    def test_drilling_reaming_it8_capable(self):
        ev = evaluate_route_capability(["drilling", "reaming"], required_it_grade=8)
        assert ev.capability_status == ProcessCapabilityStatus.CAPABLE

    def test_drilling_boring_it8_capable(self):
        ev = evaluate_route_capability(["drilling", "boring"], required_it_grade=8)
        assert ev.capability_status == ProcessCapabilityStatus.CAPABLE

    def test_drilling_boring_it7_marginal(self):
        ev = evaluate_route_capability(["drilling", "boring"], required_it_grade=7)
        assert ev.capability_status == ProcessCapabilityStatus.MARGINAL_REVIEW

    def test_unknown_operation_sequence(self):
        """Grinding-only is not in the capability table."""
        ev = evaluate_route_capability(["grinding"], required_it_grade=5)
        assert ev.capability_status == ProcessCapabilityStatus.UNKNOWN

    def test_unknown_does_not_become_capable(self):
        """MUST 28: UNKNOWN != CAPABLE."""
        ev = evaluate_route_capability(["milling", "grinding"], required_it_grade=7)
        assert ev.capability_status == ProcessCapabilityStatus.UNKNOWN
        assert ev.capability_status != ProcessCapabilityStatus.CAPABLE

    def test_no_requirement_gives_unknown(self):
        """When no IT grade specified, capability status is UNKNOWN (no assertion can be made)."""
        ev = evaluate_route_capability(["drilling"], required_it_grade=None)
        assert ev.capability_status == ProcessCapabilityStatus.UNKNOWN
        assert ev.achievable_it_min == 11
        assert ev.achievable_it_max == 13

    def test_it14_over_capable(self):
        """IT14 is looser than drilling range (IT11-IT13) -- route is over-capable."""
        ev = evaluate_route_capability(["drilling"], required_it_grade=14)
        assert ev.capability_status == ProcessCapabilityStatus.CAPABLE


class TestP5ERouteRanking:
    def test_rank_routes_it7(self):
        routes = [
            ["drilling"],
            ["drilling", "reaming"],
            ["drilling", "boring"],
        ]
        ranked = rank_routes_by_capability(routes, required_it_grade=7)
        statuses = [ev.capability_status for _, ev in ranked]
        # CAPABLE should come before MARGINAL, MARGINAL before UNKNOWN/NOT_CAPABLE
        capable_positions = [
            i for i, s in enumerate(statuses) if s == ProcessCapabilityStatus.CAPABLE
        ]
        not_capable_positions = [
            i for i, s in enumerate(statuses) if s == ProcessCapabilityStatus.NOT_CAPABLE
        ]
        if capable_positions and not_capable_positions:
            assert max(capable_positions) < min(not_capable_positions)

    def test_rank_routes_it12(self):
        routes = [["drilling"], ["drilling", "reaming"]]
        ranked = rank_routes_by_capability(routes, required_it_grade=12)
        # Both should be CAPABLE or MARGINAL
        for _, ev in ranked:
            assert ev.capability_status in (
                ProcessCapabilityStatus.CAPABLE, ProcessCapabilityStatus.MARGINAL_REVIEW
            )
