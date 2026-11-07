"""
Level-14 Package Integrity and Staleness Detection.

Packages become STALE when:
- NC candidate hash changes
- Assignment reference changes
- Setup/tool/fixture/post-profile changes
"""

from __future__ import annotations

import hashlib

from .enums import PackageIntegrityStatus
from .models import DispatchPackage, PackageIntegrityResult


def compute_package_hash(package: DispatchPackage) -> str:
    """Deterministic hash of package identity fields."""
    components = "|".join([
        package.package_id,
        package.job_ref,
        package.assignment_ref,
        package.machine_ref,
        package.nc_candidate_ref or "",
        package.nc_hash or "",
        package.post_profile_ref or "",
        package.fixture_ref or "",
        package.setup_ref or "",
        ",".join(sorted(package.tool_list)),
        ",".join(sorted(package.holder_list)),
    ])
    return hashlib.sha256(components.encode()).hexdigest()


def check_package_staleness(
    package: DispatchPackage,
    current_nc_hash: str | None = None,
    current_assignment_ref: str | None = None,
    current_setup_ref: str | None = None,
    current_fixture_ref: str | None = None,
    current_tool_list: list[str] | None = None,
    current_post_profile_ref: str | None = None,
) -> PackageIntegrityResult:
    """
    Detect staleness by comparing package fields against current values.
    Any mismatch marks the package STALE.
    """
    stale_reasons: list[str] = []

    if current_nc_hash is not None and package.nc_hash != current_nc_hash:
        stale_reasons.append(
            f"NC_HASH_CHANGED: package={package.nc_hash!r} "
            f"current={current_nc_hash!r}"
        )

    if (
        current_assignment_ref is not None
        and package.assignment_ref != current_assignment_ref
    ):
        stale_reasons.append(
            f"ASSIGNMENT_CHANGED: package={package.assignment_ref!r} "
            f"current={current_assignment_ref!r}"
        )

    if current_setup_ref is not None and package.setup_ref != current_setup_ref:
        stale_reasons.append(
            f"SETUP_CHANGED: package={package.setup_ref!r} "
            f"current={current_setup_ref!r}"
        )

    if current_fixture_ref is not None and package.fixture_ref != current_fixture_ref:
        stale_reasons.append(
            f"FIXTURE_CHANGED: package={package.fixture_ref!r} "
            f"current={current_fixture_ref!r}"
        )

    if current_tool_list is not None and sorted(package.tool_list) != sorted(
        current_tool_list
    ):
        stale_reasons.append(
            f"TOOL_LIST_CHANGED: package={sorted(package.tool_list)} "
            f"current={sorted(current_tool_list)}"
        )

    if (
        current_post_profile_ref is not None
        and package.post_profile_ref != current_post_profile_ref
    ):
        stale_reasons.append(
            f"POST_PROFILE_CHANGED: package={package.post_profile_ref!r} "
            f"current={current_post_profile_ref!r}"
        )

    if stale_reasons:
        return PackageIntegrityResult(
            status=PackageIntegrityStatus.STALE,
            stale_reasons=stale_reasons,
            expected_nc_hash=current_nc_hash,
            actual_nc_hash=package.nc_hash,
            expected_assignment_ref=current_assignment_ref,
            actual_assignment_ref=package.assignment_ref,
        )

    if not package.nc_hash or not package.assignment_ref:
        return PackageIntegrityResult(
            status=PackageIntegrityStatus.INCOMPLETE,
            stale_reasons=["MISSING_REQUIRED_FIELDS"],
        )

    return PackageIntegrityResult(status=PackageIntegrityStatus.INTACT)
