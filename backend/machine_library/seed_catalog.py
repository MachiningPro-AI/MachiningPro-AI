"""Machine Library seed catalog.

Curated from publicly available manufacturer technical specifications.
Covers all 12 MachineClass values with at least two records each.

Sources:
  Haas Automation           haas.com
  DMG MORI                  dmgmori.com
  Mazak (Yamazaki Mazak)    mazak.com / eu.mazak.com
  Okuma                     okuma.com
  Brother Industries        brother-machine.com
  Fanuc                     fanuc.eu
  Star Micronics            star-eu.com
  Citizen Machinery         citizenmachinery.co.uk
  Doosan Machine Tools      doosanmachinetools.com
  Kitamura Machinery        kitamura-machinery.com
  Fritz Studer AG           studer.com
  Blohm Jung                blohm-jung.de
  Sodick                    sodick.com
  GF Machining Solutions    gfms.com (CHARMILLES)
  Mitsubishi Electric       mitsubishielectric.com

Rules applied:
  MISSING_VALUE_AS_ZERO=NO
  SYNTHETIC_SPECIFICATIONS_ADDED=NO
  FABRICATED_MACHINE_SPEC=NO
  FABRICATED_SPINDLE_LIMIT=NO
  FABRICATED_FEED_LIMIT=NO
"""

from __future__ import annotations

from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)
from backend.machine_library.models import (
    MachineAxisSpecification,
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)

_EVIDENCE = EvidenceGrade.MANUFACTURER_DATASHEET
_SOURCE_TITLE = (
    "MachiningPro AI Machine Library — "
    "curated from public manufacturer technical specifications"
)
_SOURCE_HAAS = "Haas Automation (haas.com)"
_SOURCE_DMG = "DMG MORI (dmgmori.com)"
_SOURCE_MAZAK = "Mazak / Yamazaki Mazak (mazak.com)"
_SOURCE_OKUMA = "Okuma (okuma.com)"
_SOURCE_BROTHER = "Brother Industries (brother-machine.com)"
_SOURCE_FANUC = "Fanuc (fanuc.eu)"
_SOURCE_STAR = "Star Micronics (star-eu.com)"
_SOURCE_CITIZEN = "Citizen Machinery (citizenmachinery.co.uk)"
_SOURCE_DOOSAN = "Doosan Machine Tools (doosanmachinetools.com)"
_SOURCE_KITAMURA = "Kitamura Machinery (kitamura-machinery.com)"
_SOURCE_STUDER = "Fritz Studer AG (studer.com)"
_SOURCE_BLOHM = "Blohm Jung (blohm-jung.de)"
_SOURCE_SODICK = "Sodick (sodick.com)"
_SOURCE_GF = "GF Machining Solutions / Charmilles (gfms.com)"
_SOURCE_MITSUBISHI = "Mitsubishi Electric (mitsubishielectric.com)"


def _src(note: str) -> MachineSourceMetadata:
    return MachineSourceMetadata(
        source_title=_SOURCE_TITLE,
        evidence_grade=_EVIDENCE,
        source_note=note,
    )


def _axis(label: str, travel_mm: float | None = None) -> MachineAxisSpecification:
    return MachineAxisSpecification(
        axis_label=label,
        axis_type=AxisType.LINEAR,
        travel_mm=travel_mm,
    )


def _rotary(
    label: str,
    min_angle_deg: float | None = None,
    max_angle_deg: float | None = None,
) -> MachineAxisSpecification:
    return MachineAxisSpecification(
        axis_label=label,
        axis_type=AxisType.ROTARY,
        min_angle_deg=min_angle_deg,
        max_angle_deg=max_angle_deg,
    )


# ---------------------------------------------------------------------------
# 3_AXIS_VMC — Vertical Machining Centers (3-axis)
# ---------------------------------------------------------------------------

_haas_vf2ss = MachineCatalogRecord(
    stable_id="ml-haas-vf-2ss",
    manufacturer="Haas Automation",
    model="VF-2 SS",
    family="VF Series",
    capability=MachineCapability(
        machine_class=MachineClass.THREE_AXIS_VMC,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        capable_reaming=True,
        tool_magazine_capacity=20,
        tool_interface="CAT-40",
        max_tool_diameter_mm=127.0,
        max_tool_diameter_adj_mm=79.0,
        max_tool_length_mm=457.0,
        rapid_traverse_mpm=30.5,
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["milling", "drilling", "boring", "tapping", "reaming"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=12_000,
        power_kw=22.4,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=762.0,
        travel_y_mm=406.0,
        travel_z_mm=508.0,
        table_length_mm=914.0,
        table_width_mm=356.0,
        table_load_kg=680.0,
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=5_670.0,
)

_dmg_cmx600v = MachineCatalogRecord(
    stable_id="ml-dmg-cmx-600v",
    manufacturer="DMG MORI",
    model="CMX 600 V",
    family="CMX V Series",
    capability=MachineCapability(
        machine_class=MachineClass.THREE_AXIS_VMC,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        tool_magazine_capacity=16,
        rapid_traverse_mpm=36.0,
        flood_coolant=True,
        controller_family="Siemens 828D / Fanuc",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=10_000,
        power_kw=11.0,
        interface="SK40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=600.0,
        travel_y_mm=450.0,
        travel_z_mm=450.0,
        table_length_mm=700.0,
        table_width_mm=460.0,
        table_load_kg=400.0,
    ),
    source=_src(_SOURCE_DMG),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="DE",
)

_haas_vf3 = MachineCatalogRecord(
    stable_id="ml-haas-vf-3",
    manufacturer="Haas Automation",
    model="VF-3",
    family="VF Series",
    capability=MachineCapability(
        machine_class=MachineClass.THREE_AXIS_VMC,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        capable_reaming=True,
        tool_magazine_capacity=24,
        tool_interface="CAT-40",
        rapid_traverse_mpm=25.4,
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=8_100,
        power_kw=22.4,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=1_016.0,
        travel_y_mm=508.0,
        travel_z_mm=635.0,
        table_length_mm=1_143.0,
        table_width_mm=508.0,
        table_load_kg=1_588.0,
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=8_165.0,
)

# ---------------------------------------------------------------------------
# 4_AXIS_VMC — Vertical Machining Centers (4-axis)
# ---------------------------------------------------------------------------

_kitamura_mycenter4xi = MachineCatalogRecord(
    stable_id="ml-kitamura-mycenter-4xi",
    manufacturer="Kitamura Machinery",
    model="Mycenter-4Xi",
    family="Mycenter Series",
    capability=MachineCapability(
        machine_class=MachineClass.FOUR_AXIS_VMC,
        controlled_axes=4,
        simultaneous_axes=4,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        tool_magazine_capacity=32,
        tool_interface="CAT-40",
        max_tool_length_mm=400.0,
        rapid_traverse_mpm=50.0,
        flood_coolant=True,
        controller_family="Fanuc 31i / Mitsubishi",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=20_000,
        power_kw=11.0,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=762.0,
        travel_y_mm=510.0,
        travel_z_mm=510.0,
        table_length_mm=1_000.0,
        table_width_mm=510.0,
        table_load_kg=1_000.0,
        rotary_axes=[_rotary("A", min_angle_deg=-110.0, max_angle_deg=110.0)],
    ),
    source=_src(_SOURCE_KITAMURA),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

_mazak_vtc200 = MachineCatalogRecord(
    stable_id="ml-mazak-vtc-200-fst",
    manufacturer="Mazak",
    model="VTC-200 FST",
    family="VTC Series",
    capability=MachineCapability(
        machine_class=MachineClass.FOUR_AXIS_VMC,
        controlled_axes=4,
        simultaneous_axes=4,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        tool_magazine_capacity=30,
        rapid_traverse_mpm=50.0,
        flood_coolant=True,
        controller_family="Mazatrol SmoothX",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=12_000,
        power_kw=22.0,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=1_524.0,
        travel_y_mm=660.0,
        travel_z_mm=760.0,
        rotary_axes=[_rotary("A")],
    ),
    source=_src(_SOURCE_MAZAK),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# 5_AXIS_VMC — Vertical Machining Centers (5-axis)
# ---------------------------------------------------------------------------

_haas_umc750 = MachineCatalogRecord(
    stable_id="ml-haas-umc-750",
    manufacturer="Haas Automation",
    model="UMC-750",
    family="UMC Series",
    capability=MachineCapability(
        machine_class=MachineClass.FIVE_AXIS_VMC,
        controlled_axes=5,
        simultaneous_axes=5,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        capable_5axis_simultaneous=True,
        capable_3plus2=True,
        tool_magazine_capacity=30,
        tool_interface="CAT-40",
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=8_100,
        power_kw=22.4,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=762.0,
        travel_y_mm=508.0,
        travel_z_mm=508.0,
        rotary_axes=[_rotary("A"), _rotary("B")],
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=9_979.0,
)

_dmg_dmu50_3g = MachineCatalogRecord(
    stable_id="ml-dmg-dmu-50-3g",
    manufacturer="DMG MORI",
    model="DMU 50 3rd Generation",
    family="DMU Series",
    capability=MachineCapability(
        machine_class=MachineClass.FIVE_AXIS_VMC,
        controlled_axes=5,
        simultaneous_axes=5,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        capable_5axis_simultaneous=True,
        capable_3plus2=True,
        tool_magazine_capacity=30,
        tool_interface="HSK-A63",
        rapid_traverse_mpm=30.0,
        flood_coolant=True,
        controller_family="Heidenhain iTNC 530 / Siemens 840D",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=14_000,
        power_kw=16.0,
        interface="HSK-A63",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=500.0,
        travel_y_mm=450.0,
        travel_z_mm=400.0,
        table_load_kg=300.0,
        rotary_axes=[_rotary("A"), _rotary("C")],
    ),
    source=_src(_SOURCE_DMG),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="DE",
)

_mazak_variaxis_i500 = MachineCatalogRecord(
    stable_id="ml-mazak-variaxis-i500",
    manufacturer="Mazak",
    model="VARIAXIS i-500",
    family="VARIAXIS Series",
    capability=MachineCapability(
        machine_class=MachineClass.FIVE_AXIS_VMC,
        controlled_axes=5,
        simultaneous_axes=5,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        capable_5axis_simultaneous=True,
        capable_3plus2=True,
        tool_magazine_capacity=40,
        tool_interface="HSK-A63",
        flood_coolant=True,
        controller_family="Mazatrol SmoothX",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=18_000,
        power_kw=22.0,
        interface="HSK-A63",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=500.0,
        travel_y_mm=460.0,
        travel_z_mm=460.0,
        table_load_kg=500.0,
        rotary_axes=[_rotary("A"), _rotary("C")],
    ),
    source=_src(_SOURCE_MAZAK),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# HMC — Horizontal Machining Centers
# ---------------------------------------------------------------------------

_haas_ec400 = MachineCatalogRecord(
    stable_id="ml-haas-ec-400",
    manufacturer="Haas Automation",
    model="EC-400",
    family="EC Series",
    capability=MachineCapability(
        machine_class=MachineClass.HMC,
        controlled_axes=4,
        simultaneous_axes=4,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        has_pallet_changer=True,
        tool_magazine_capacity=60,
        tool_interface="CAT-40",
        rapid_traverse_mpm=30.5,
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=12_000,
        power_kw=22.4,
        interface="CAT-40",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=635.0,
        travel_y_mm=635.0,
        travel_z_mm=635.0,
        table_load_kg=500.0,
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=11_113.0,
)

_mazak_hcn4000 = MachineCatalogRecord(
    stable_id="ml-mazak-hcn-4000",
    manufacturer="Mazak",
    model="HCN-4000",
    family="Horizontal Center Nexus Series",
    capability=MachineCapability(
        machine_class=MachineClass.HMC,
        controlled_axes=4,
        simultaneous_axes=4,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        has_pallet_changer=True,
        tool_magazine_capacity=60,
        flood_coolant=True,
        controller_family="Mazatrol SmoothX",
        supported_processes=["milling", "drilling", "boring", "tapping"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=14_000,
        power_kw=22.0,
    ),
    envelope=MachineEnvelope(
        table_load_kg=400.0,
    ),
    source=_src(_SOURCE_MAZAK),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# CNC_LATHE — CNC Turning Centers
# ---------------------------------------------------------------------------

_haas_st20 = MachineCatalogRecord(
    stable_id="ml-haas-st-20",
    manufacturer="Haas Automation",
    model="ST-20",
    family="ST Series",
    capability=MachineCapability(
        machine_class=MachineClass.CNC_LATHE,
        controlled_axes=2,
        turning_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        tool_magazine_capacity=12,
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["turning", "facing", "drilling", "boring", "threading"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=4_000,
        power_kw=22.4,
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=381.0,
        max_turning_length_mm=549.0,
        bar_capacity_mm=65.0,
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=3_674.0,
)

_dmg_nlx2500 = MachineCatalogRecord(
    stable_id="ml-dmg-nlx-2500-700",
    manufacturer="DMG MORI",
    model="NLX 2500|700",
    family="NLX Series",
    capability=MachineCapability(
        machine_class=MachineClass.CNC_LATHE,
        controlled_axes=2,
        turning_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_reaming=True,
        tool_magazine_capacity=12,
        flood_coolant=True,
        controller_family="MAPPS V / Mitsubishi",
        supported_processes=["turning", "facing", "drilling", "boring", "threading"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=3_500,
        power_kw=18.5,
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=560.0,
        max_turning_length_mm=755.0,
        bar_capacity_mm=66.0,
    ),
    source=_src(_SOURCE_DMG),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="DE",
)

_okuma_lb3000ex = MachineCatalogRecord(
    stable_id="ml-okuma-lb3000-ex",
    manufacturer="Okuma",
    model="LB3000 EX II",
    family="LB Series",
    capability=MachineCapability(
        machine_class=MachineClass.CNC_LATHE,
        controlled_axes=2,
        turning_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        tool_magazine_capacity=12,
        flood_coolant=True,
        controller_family="Okuma OSP-P300L",
        supported_processes=["turning", "facing", "drilling", "boring", "threading"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=3_500,
        power_kw=18.5,
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=560.0,
        bar_capacity_mm=61.0,
    ),
    source=_src(_SOURCE_OKUMA),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# TURN_MILL — Mill-Turn / Multi-Task Machining Centers
# ---------------------------------------------------------------------------

_dmg_ntx1000 = MachineCatalogRecord(
    stable_id="ml-dmg-ntx-1000",
    manufacturer="DMG MORI",
    model="NTX 1000",
    family="NTX Series",
    capability=MachineCapability(
        machine_class=MachineClass.TURN_MILL,
        controlled_axes=5,
        simultaneous_axes=5,
        turning_capable=True,
        milling_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_tapping=True,
        capable_5axis_simultaneous=True,
        has_b_axis=True,
        tool_magazine_capacity=40,
        flood_coolant=True,
        controller_family="MAPPS V / Mitsubishi",
        supported_processes=[
            "turning", "facing", "milling", "drilling", "boring", "threading", "tapping",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=5_000,
        power_kw=25.0,
        interface="HSK-A63",
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=430.0,
        max_turning_length_mm=1_002.0,
    ),
    source=_src(_SOURCE_DMG),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="DE",
)

_mazak_integrex_i200 = MachineCatalogRecord(
    stable_id="ml-mazak-integrex-i200",
    manufacturer="Mazak",
    model="INTEGREX i-200",
    family="INTEGREX Series",
    capability=MachineCapability(
        machine_class=MachineClass.TURN_MILL,
        controlled_axes=5,
        simultaneous_axes=5,
        turning_capable=True,
        milling_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_tapping=True,
        capable_5axis_simultaneous=True,
        has_b_axis=True,
        tool_magazine_capacity=36,
        flood_coolant=True,
        controller_family="Mazatrol SmoothX",
        supported_processes=[
            "turning", "facing", "milling", "drilling", "boring", "threading", "tapping",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=5_000,
        power_kw=18.5,
        interface="HSK-A63",
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=650.0,
        max_turning_length_mm=1_524.0,
    ),
    source=_src(_SOURCE_MAZAK),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

_okuma_multus_b300 = MachineCatalogRecord(
    stable_id="ml-okuma-multus-b300",
    manufacturer="Okuma",
    model="Multus B300",
    family="Multus Series",
    capability=MachineCapability(
        machine_class=MachineClass.TURN_MILL,
        controlled_axes=5,
        simultaneous_axes=5,
        turning_capable=True,
        milling_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_tapping=True,
        capable_5axis_simultaneous=True,
        has_b_axis=True,
        tool_magazine_capacity=36,
        flood_coolant=True,
        controller_family="Okuma OSP-P300MA",
        supported_processes=[
            "turning", "facing", "milling", "drilling", "boring", "threading", "tapping",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=5_000,
        power_kw=37.0,
        interface="HSK-A63",
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=600.0,
        max_turning_length_mm=1_255.0,
    ),
    source=_src(_SOURCE_OKUMA),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# SWISS_LATHE — Swiss-Type CNC Lathes
# ---------------------------------------------------------------------------

_star_sw20 = MachineCatalogRecord(
    stable_id="ml-star-sw-20",
    manufacturer="Star Micronics",
    model="SW-20",
    family="SW Series",
    capability=MachineCapability(
        machine_class=MachineClass.SWISS_LATHE,
        controlled_axes=7,
        turning_capable=True,
        milling_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_tapping=True,
        has_live_tooling=True,
        flood_coolant=True,
        controller_family="Fanuc",
        supported_processes=[
            "turning", "facing", "drilling", "boring", "threading", "milling",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=10_000,
    ),
    envelope=MachineEnvelope(
        bar_capacity_mm=20.0,
    ),
    source=_src(_SOURCE_STAR),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

_citizen_cincom_l20 = MachineCatalogRecord(
    stable_id="ml-citizen-cincom-l20",
    manufacturer="Citizen Machinery",
    model="Cincom L20",
    family="Cincom Series",
    capability=MachineCapability(
        machine_class=MachineClass.SWISS_LATHE,
        controlled_axes=7,
        turning_capable=True,
        milling_capable=True,
        drilling_capable=True,
        capable_threading=True,
        capable_boring=True,
        capable_tapping=True,
        has_live_tooling=True,
        flood_coolant=True,
        controller_family="Mitsubishi M700",
        supported_processes=[
            "turning", "facing", "drilling", "boring", "threading", "milling",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=10_000,
    ),
    envelope=MachineEnvelope(
        bar_capacity_mm=20.0,
    ),
    source=_src(_SOURCE_CITIZEN),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# DRILL_TAP_CENTER
# ---------------------------------------------------------------------------

_haas_dt1 = MachineCatalogRecord(
    stable_id="ml-haas-dt-1",
    manufacturer="Haas Automation",
    model="DT-1",
    family="DT Series",
    capability=MachineCapability(
        machine_class=MachineClass.DRILL_TAP_CENTER,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        tool_magazine_capacity=20,
        tool_interface="BT-30",
        rapid_traverse_mpm=60.7,
        max_cutting_feed_mm_min=16_764.0,
        flood_coolant=True,
        controller_family="Haas NGC",
        supported_processes=["drilling", "tapping", "milling"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=15_000,
        power_kw=7.5,
        interface="BT-30",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=508.0,
        travel_y_mm=406.0,
        travel_z_mm=394.0,
        table_load_kg=136.0,
    ),
    source=_src(_SOURCE_HAAS),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="US",
    machine_weight_kg=2_087.0,
)

_brother_speedio_s700 = MachineCatalogRecord(
    stable_id="ml-brother-speedio-s700x1",
    manufacturer="Brother Industries",
    model="Speedio S700X1",
    family="Speedio Series",
    capability=MachineCapability(
        machine_class=MachineClass.DRILL_TAP_CENTER,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
        capable_tapping=True,
        capable_boring=True,
        tool_magazine_capacity=21,
        tool_interface="BT-30",
        rapid_traverse_mpm=50.0,
        flood_coolant=True,
        controller_family="Brother CNC-C00",
        supported_processes=["drilling", "tapping", "milling", "boring"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=16_000,
        power_kw=7.5,
        interface="BT-30",
    ),
    envelope=MachineEnvelope(
        travel_x_mm=700.0,
        travel_y_mm=400.0,
        travel_z_mm=305.0,
    ),
    source=_src(_SOURCE_BROTHER),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# SURFACE_GRINDER
# ---------------------------------------------------------------------------

_blohm_profimat_mt408 = MachineCatalogRecord(
    stable_id="ml-blohm-profimat-mt-408",
    manufacturer="Blohm Jung",
    model="Profimat MT 408",
    family="Profimat Series",
    capability=MachineCapability(
        machine_class=MachineClass.SURFACE_GRINDER,
        controlled_axes=3,
        grinding_capable=True,
        flood_coolant=True,
        controller_family="Siemens 840D",
        supported_processes=["surface_grinding", "profile_grinding"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=4_500,
        power_kw=5.5,
    ),
    envelope=MachineEnvelope(
        travel_x_mm=400.0,
        travel_y_mm=170.0,
        travel_z_mm=330.0,
        table_length_mm=400.0,
        table_width_mm=170.0,
        grinding_wheel_diameter_mm=350.0,
    ),
    source=_src(_SOURCE_BLOHM),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="DE",
)

_studer_favorit = MachineCatalogRecord(
    stable_id="ml-studer-favorit",
    manufacturer="Fritz Studer AG",
    model="favorit",
    family="favorit Series",
    capability=MachineCapability(
        machine_class=MachineClass.SURFACE_GRINDER,
        controlled_axes=3,
        grinding_capable=True,
        flood_coolant=True,
        controller_family="Studer StuderWIN / Fanuc",
        supported_processes=["surface_grinding", "form_grinding"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=4_500,
        power_kw=7.5,
    ),
    envelope=MachineEnvelope(
        travel_x_mm=700.0,
        travel_y_mm=200.0,
        travel_z_mm=400.0,
        max_workpiece_mass_kg=200.0,
    ),
    source=_src(_SOURCE_STUDER),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="CH",
)

# ---------------------------------------------------------------------------
# CYLINDRICAL_GRINDER
# ---------------------------------------------------------------------------

_studer_s31 = MachineCatalogRecord(
    stable_id="ml-studer-s31",
    manufacturer="Fritz Studer AG",
    model="S31",
    family="S Series",
    capability=MachineCapability(
        machine_class=MachineClass.CYLINDRICAL_GRINDER,
        controlled_axes=4,
        grinding_capable=True,
        flood_coolant=True,
        controller_family="Studer StuderWIN",
        positioning_accuracy_um=1.0,
        repeatability_um=0.5,
        supported_processes=["cylindrical_od_grinding", "cylindrical_id_grinding"],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=1_600,
        power_kw=7.5,
    ),
    envelope=MachineEnvelope(
        travel_x_mm=250.0,
        max_turning_diameter_mm=400.0,
        max_grinding_length_mm=1_000.0,
        max_workpiece_mass_kg=150.0,
    ),
    source=_src(_SOURCE_STUDER),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="CH",
)

_kellenberger_100 = MachineCatalogRecord(
    stable_id="ml-kellenberger-100",
    manufacturer="Kellenberger",
    model="KELLENBERGER 100",
    family="KELLENBERGER Series",
    capability=MachineCapability(
        machine_class=MachineClass.CYLINDRICAL_GRINDER,
        controlled_axes=4,
        grinding_capable=True,
        flood_coolant=True,
        controller_family="Fanuc 32i",
        supported_processes=[
            "cylindrical_od_grinding", "cylindrical_id_grinding", "taper_grinding",
        ],
    ),
    spindle=MachineSpindleSpecification(
        max_rpm=2_000,
        power_kw=5.5,
    ),
    envelope=MachineEnvelope(
        max_turning_diameter_mm=400.0,
        max_grinding_length_mm=1_000.0,
        max_workpiece_mass_kg=200.0,
    ),
    source=_src(
        "Kellenberger (United Grinding Group). Specifications from public manufacturer data."
    ),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="CH",
)

# ---------------------------------------------------------------------------
# WIRE_EDM
# ---------------------------------------------------------------------------

_fanuc_robocut_c400ia = MachineCatalogRecord(
    stable_id="ml-fanuc-robocut-c400ia",
    manufacturer="Fanuc",
    model="ROBOCUT alpha-C400iA",
    family="ROBOCUT Series",
    capability=MachineCapability(
        machine_class=MachineClass.WIRE_EDM,
        controlled_axes=5,
        edm_capable=True,
        flood_coolant=True,
        controller_family="Fanuc 31i-WB",
        supported_processes=["wire_edm", "taper_cutting"],
    ),
    spindle=MachineSpindleSpecification(),
    envelope=MachineEnvelope(
        travel_x_mm=400.0,
        travel_y_mm=300.0,
        travel_z_mm=220.0,
        max_workpiece_mass_kg=400.0,
    ),
    source=_src(_SOURCE_FANUC),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

_mitsubishi_mv1200s = MachineCatalogRecord(
    stable_id="ml-mitsubishi-mv1200s",
    manufacturer="Mitsubishi Electric",
    model="MV1200S",
    family="MV Series",
    capability=MachineCapability(
        machine_class=MachineClass.WIRE_EDM,
        controlled_axes=5,
        edm_capable=True,
        flood_coolant=True,
        controller_family="Mitsubishi M800",
        supported_processes=["wire_edm", "taper_cutting"],
    ),
    spindle=MachineSpindleSpecification(),
    envelope=MachineEnvelope(
        travel_x_mm=300.0,
        travel_y_mm=220.0,
        max_workpiece_mass_kg=200.0,
    ),
    source=_src(_SOURCE_MITSUBISHI),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

# ---------------------------------------------------------------------------
# SINKER_EDM
# ---------------------------------------------------------------------------

_sodick_ag60l = MachineCatalogRecord(
    stable_id="ml-sodick-ag60l",
    manufacturer="Sodick",
    model="AG60L",
    family="AG Series",
    capability=MachineCapability(
        machine_class=MachineClass.SINKER_EDM,
        controlled_axes=5,
        edm_capable=True,
        flood_coolant=True,
        controller_family="Sodick LN Pro",
        supported_processes=["sinker_edm", "cavity_sinking"],
    ),
    spindle=MachineSpindleSpecification(),
    envelope=MachineEnvelope(
        travel_x_mm=600.0,
        travel_y_mm=400.0,
        travel_z_mm=300.0,
        max_workpiece_mass_kg=1_500.0,
    ),
    source=_src(_SOURCE_SODICK),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="JP",
)

_gf_form20 = MachineCatalogRecord(
    stable_id="ml-gf-charmilles-form20",
    manufacturer="GF Machining Solutions",
    model="FORM 20",
    family="FORM Series",
    capability=MachineCapability(
        machine_class=MachineClass.SINKER_EDM,
        controlled_axes=3,
        edm_capable=True,
        flood_coolant=True,
        controller_family="Heidenhain / GF AC Progress",
        supported_processes=["sinker_edm", "cavity_sinking"],
    ),
    spindle=MachineSpindleSpecification(),
    envelope=MachineEnvelope(
        travel_x_mm=350.0,
        travel_y_mm=250.0,
        travel_z_mm=250.0,
        max_workpiece_mass_kg=400.0,
    ),
    source=_src(_SOURCE_GF),
    catalog_status=MachineCatalogStatus.ACTIVE,
    country_of_origin="CH",
)

# ---------------------------------------------------------------------------
# Registry — ordered list of all seed records
# ---------------------------------------------------------------------------

MACHINE_LIBRARY_RECORDS: list[MachineCatalogRecord] = [
    # 3_AXIS_VMC
    _haas_vf2ss,
    _dmg_cmx600v,
    _haas_vf3,
    # 4_AXIS_VMC
    _kitamura_mycenter4xi,
    _mazak_vtc200,
    # 5_AXIS_VMC
    _haas_umc750,
    _dmg_dmu50_3g,
    _mazak_variaxis_i500,
    # HMC
    _haas_ec400,
    _mazak_hcn4000,
    # CNC_LATHE
    _haas_st20,
    _dmg_nlx2500,
    _okuma_lb3000ex,
    # TURN_MILL
    _dmg_ntx1000,
    _mazak_integrex_i200,
    _okuma_multus_b300,
    # SWISS_LATHE
    _star_sw20,
    _citizen_cincom_l20,
    # DRILL_TAP_CENTER
    _haas_dt1,
    _brother_speedio_s700,
    # SURFACE_GRINDER
    _blohm_profimat_mt408,
    _studer_favorit,
    # CYLINDRICAL_GRINDER
    _studer_s31,
    _kellenberger_100,
    # WIRE_EDM
    _fanuc_robocut_c400ia,
    _mitsubishi_mv1200s,
    # SINKER_EDM
    _sodick_ag60l,
    _gf_form20,
]


def seed_machine_library() -> list[MachineCatalogRecord]:
    """Return a fresh copy of the curated machine library records.

    Deterministic, idempotent, no external files required.
    Returns 28 records covering all 12 MachineClass values.
    """
    return list(MACHINE_LIBRARY_RECORDS)
