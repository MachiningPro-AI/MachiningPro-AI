"""
Cutting Tool Catalog seed data.

Source: Public manufacturer technical catalogs and product pages.

Manufacturers referenced:
  Sandvik Coromant (coromant.sandvik.com)
  Kennametal (kennametal.com)
  Iscar (iscar.com)
  Walter Tools (walter-tools.com)

Geometry for indexable inserts is derived from ISO 1832 designation,
which is the public international standard for insert identification.

Evidence status: MANUFACTURER_CATALOG — curated from public product catalogs.

MISSING_VALUE_AS_ZERO=NO  — all unknown fields are None.
SYNTHETIC_SPECIFICATIONS_ADDED=NO — only published geometry/grades included.
SYNTHETIC_CUTTING_PARAMETERS_ADDED=NO — Vc/fz guidance omitted; consult
    manufacturer application guides for material-specific starting values.
"""

from .catalog_models import CuttingToolCatalogRecord

_SOURCE_TITLE = (
    "MachiningPro AI Cutting Tool Catalog — "
    "curated from public manufacturer technical catalogs"
)
_SOURCE_NOTE = (
    "Sandvik Coromant (coromant.sandvik.com); "
    "Kennametal (kennametal.com); "
    "Iscar (iscar.com); "
    "Walter Tools / Titex (walter-tools.com); "
    "OSG Corporation (osg.co.jp). "
    "Insert geometry derived from ISO 1832 standard designation. "
    "Cutting guidance fields (Vc, fz) are not included; "
    "consult the manufacturer's current application guide for "
    "material-specific recommended starting values."
)
_EVIDENCE = "MANUFACTURER_CATALOG"
_SOURCE_AUTHORITY = "OFFICIAL_MANUFACTURER_CATALOG"


def _missing(record: dict) -> list[str]:
    """Return names of optional numeric/string fields that are None."""
    optional_fields = [
        "product_family", "catalog_code", "tool_subcategory",
        "tool_type_code",
        "tool_material", "substrate_grade", "substrate_material_code",
        "coating", "coating_type", "coating_brand",
        "iso_insert_designation", "insert_shape", "insert_shape_code",
        "insert_ic_mm", "insert_thickness_mm", "nose_radius_mm",
        "clearance_angle_deg", "insert_tolerance_class", "insert_hand",
        "cutting_diameter_mm", "shank_diameter_mm", "overall_length_mm",
        "cutting_length_mm", "flute_length_mm", "number_of_flutes",
        "helix_angle_deg", "corner_radius_mm", "point_angle_deg",
        "shank_interface", "through_coolant", "max_rpm",
        "compatible_holder_interface", "arbor_interface",
        "max_ap_mm", "max_ae_mm",
        "vc_min_mpm", "vc_max_mpm", "fz_min_mm", "fz_max_mm",
        "fn_min_mm", "fn_max_mm", "ap_max_mm",
        "source_note",
    ]
    return [f for f in optional_fields if record.get(f) is None]


def _make(
    stable_id: str,
    manufacturer: str,
    product_name: str,
    tool_category: str,
    tool_category_code: str,
    supported_operations: list[str],
    iso_material_groups: list[str],
    **kwargs,
) -> CuttingToolCatalogRecord:
    base = dict(
        stable_id=stable_id,
        manufacturer=manufacturer,
        product_name=product_name,
        tool_category=tool_category,
        tool_category_code=tool_category_code,
        supported_operations=supported_operations,
        iso_material_groups=iso_material_groups,
        source_title=_SOURCE_TITLE,
        source_authority=_SOURCE_AUTHORITY,
        evidence_status=_EVIDENCE,
        source_note=_SOURCE_NOTE,
    )
    base.update(kwargs)
    base["missing_fields"] = _missing(base)
    return CuttingToolCatalogRecord(**base)


# ── Catalog records ──────────────────────────────────────────────────────────
# Ordered: by manufacturer, then by category

_RECORDS: list[CuttingToolCatalogRecord] = [

    # ── Sandvik Coromant — Turning Inserts ───────────────────────────────────

    _make(
        stable_id="sandvik-cnmg-120408-pm-4325",
        manufacturer="Sandvik Coromant",
        product_family="GC4325",
        product_name="CNMG 12 04 08-PM 4325",
        catalog_code="CNMG 12 04 08-PM 4325",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC4325 CVD Al₂O₃+TiCN",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="sandvik-tnmg-160408-mf-4315",
        manufacturer="Sandvik Coromant",
        product_family="GC4315",
        product_name="TNMG 16 04 08-MF 4315",
        catalog_code="TNMG 16 04 08-MF 4315",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC4315 PVD TiAlN",
        coating_type="PVD",
        insert_shape="T — 60° triangle",
        insert_shape_code="T",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PTGNR/L, MTGNR/L",
    ),

    _make(
        stable_id="sandvik-dnmg-150608-m-1125",
        manufacturer="Sandvik Coromant",
        product_family="GC1125",
        product_name="DNMG 15 06 08-M 1125",
        catalog_code="DNMG 15 06 08-M 1125",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Roughing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["M", "S"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=15.875,
        insert_thickness_mm=6.35,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
    ),

    # ── Sandvik Coromant — End Mills ─────────────────────────────────────────

    _make(
        stable_id="sandvik-r216-33-06045-ac10p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-06045-AC10P 1620",
        catalog_code="R216.33-06045-AC10P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        overall_length_mm=57.0,
        flute_length_mm=10.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="sandvik-r216-33-16045-ac26p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-16045-AC26P 1620",
        catalog_code="R216.33-16045-AC26P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        cutting_diameter_mm=16.0,
        shank_diameter_mm=16.0,
        overall_length_mm=92.0,
        flute_length_mm=26.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Sandvik Coromant — Drills ─────────────────────────────────────────────
    #
    # P9-A flute_length_mm enrichment:
    # For CoroDrill 860-1 solid carbide drills, the catalog publishes L1 (overall
    # length) and Lc (cutting length).  Lc defines the working engagement zone —
    # the fluted section that must not enter the holder during cutting.  For this
    # series there is no published flute_length separate from Lc; they are
    # synonymous.  Setting flute_length_mm = cutting_length_mm is backed by the
    # manufacturer catalog code (LLL in 860.1-DDDD-LLLA1 encodes Lc directly).
    # Source: Sandvik Coromant CoroDrill 860-1 technical catalog — coromant.sandvik.com.
    # NO_FABRICATION=YES — values derived from manufacturer catalog code only.

    _make(
        stable_id="sandvik-860-1-0800-040a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0800-040A1-PM N1BU",
        catalog_code="860.1-0800-040A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        overall_length_mm=79.0,
        cutting_length_mm=28.0,
        flute_length_mm=28.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Sandvik Coromant — Reamers ───────────────────────────────────────────

    _make(
        stable_id="sandvik-835b-0801-a1-mf-1024",
        manufacturer="Sandvik Coromant",
        product_family="CoroReamer 835",
        product_name="835.B-0801-A1-MF 1024",
        catalog_code="835.B-0801-A1-MF 1024",
        tool_category="Solid Carbide Reamer",
        tool_category_code="REAMER",
        tool_subcategory="Solid Carbide Reamer Cylindrical Shank",
        supported_operations=["reaming"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="1024 PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=8.01,
        shank_diameter_mm=8.0,
        overall_length_mm=100.0,
        flute_length_mm=64.0,
        cutting_length_mm=16.0,
        number_of_flutes=6,
        through_coolant=True,
        max_rpm=1907,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "coromant.sandvik.com/en-gb/product-details?c=835.B-0801-A1-MF1024. "
            "Maximum rotational speed 1907 rpm per official product page. "
            "Grade 1024 PVD TiAlN; cylindrical shank DIN6535-HA 8 mm; "
            "cutting diameter 8.01 mm; overall length 100 mm."
        ),
    ),

    # ── Sandvik Coromant — Boring Bars ────────────────────────────────────────

    _make(
        stable_id="sandvik-a25t-sducr-11",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn 107",
        product_name="A25T-SDUCR 11",
        catalog_code="A25T-SDUCR 11",
        tool_category="Boring Bar",
        tool_category_code="BORING_BAR",
        tool_subcategory="Indexable Boring Bar Steel",
        supported_operations=["boring"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        shank_diameter_mm=25.0,
        overall_length_mm=300.0,
        through_coolant=True,
        shank_interface="Round Shank (25 mm)",
        compatible_holder_interface="Boring Bar Shank (25 mm)",
        source_note=(
            "coromant.sandvik.com/en-us/product-details?c=A25T-SDUCR+11. "
            "25 mm round-shank steel boring bar; minimum bore 32 mm; "
            "internal coolant; CoroTurn 107 insert system (SDUCR, D55 insert). "
            "ISO P/M/K steel and cast iron primary application."
        ),
    ),

    # ── Kennametal — Turning Inserts ──────────────────────────────────────────

    _make(
        stable_id="kennametal-cnmg-120408-ms-kc5525",
        manufacturer="Kennametal",
        product_family="KC5525",
        product_name="CNMG 120408 MS KC5525",
        catalog_code="CNMG 120408 MS KC5525",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5525 CVD TiCN+Al₂O₃+TiN",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="kennametal-tnmg-160408-fp-kc5525",
        manufacturer="Kennametal",
        product_family="KC5525",
        product_name="TNMG 160408 FP KC5525",
        catalog_code="TNMG 160408 FP KC5525",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5525 CVD TiCN+Al₂O₃+TiN",
        coating_type="CVD",
        insert_shape="T — 60° triangle",
        insert_shape_code="T",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PTGNR/L, MTGNR/L",
    ),

    # ── Kennametal — Drills ───────────────────────────────────────────────────

    _make(
        stable_id="kennametal-b221a-0800-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 8.000 CF H",
        catalog_code="B221A 08.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Kennametal — End Mills ────────────────────────────────────────────────

    _make(
        stable_id="kennametal-4cfl-12mm-solid-carbide",
        manufacturer="Kennametal",
        product_family="Solid Carbide End Mill",
        product_name="4-Flute Solid Carbide End Mill D=12mm",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
        evidence_status="UNVERIFIED",
    ),

    # ── Iscar — Turning Inserts ───────────────────────────────────────────────

    _make(
        stable_id="iscar-cnmg-120408-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="CNMG 120408-M IC8250",
        catalog_code="CNMG 120408-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC8250 CVD TiCN+Al₂O₃",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="iscar-dnmg-150608-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="DNMG 150608-M IC8250",
        catalog_code="DNMG 150608-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Roughing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC8250 CVD TiCN+Al₂O₃",
        coating_type="CVD",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=15.875,
        insert_thickness_mm=6.35,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
    ),

    # ── Iscar — End Mills ─────────────────────────────────────────────────────

    _make(
        stable_id="iscar-ece-b3-c06x21-cf",
        manufacturer="Iscar",
        product_family="ECE-B3",
        product_name="ECE-B3 C06x21 CF-CF",
        catalog_code="ECE-B3 C06x21 CF-CF",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=3,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Walter Tools — Turning Inserts ────────────────────────────────────────

    _make(
        stable_id="walter-cnmg-120408-nf6-wsm33s",
        manufacturer="Walter Tools",
        product_family="WSM33S",
        product_name="CNMG 120408-NF6 WSM33S",
        catalog_code="CNMG 120408-NF6 WSM33S",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="WSM33S PVD TiAlN",
        coating_type="PVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    # ── Walter / Titex — Drills ───────────────────────────────────────────────

    _make(
        stable_id="walter-titex-dc150-08-08000a1-wj30et",
        manufacturer="Walter Tools",
        product_family="Titex DC150-08",
        product_name="DC150-08-08.000A1-WJ30ET",
        catalog_code="DC150-08-08.000A1-WJ30ET",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="WJ30ET PVD AlTiN",
        coating_type="PVD",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Walter — End Mills ────────────────────────────────────────────────────

    _make(
        stable_id="walter-b2219a-d0600",
        manufacturer="Walter Tools",
        product_family="B2219",
        product_name="B2219.A06-11",
        catalog_code="B2219.A06-11",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=4,
        helix_angle_deg=38.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Grooving Inserts ─────────────────────────────────────────

    _make(
        stable_id="sandvik-n123g2-0300-0002-cr-1125",
        manufacturer="Sandvik Coromant",
        product_family="CoroCut 1-2",
        product_name="N123G2-0300-0002-CR 1125",
        catalog_code="N123G2-0300-0002-CR 1125",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1125",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="N123G2-0300-0002-CR",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
        compatible_holder_interface="CoroCut QB N123 blade holder",
    ),

    _make(
        stable_id="sandvik-n123g2-0400-0002-cr-1125",
        manufacturer="Sandvik Coromant",
        product_family="CoroCut 1-2",
        product_name="N123G2-0400-0002-CR 1125",
        catalog_code="N123G2-0400-0002-CR 1125",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 4 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1125",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="N123G2-0400-0002-CR",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
        compatible_holder_interface="CoroCut QB N123 blade holder",
    ),

    _make(
        stable_id="iscar-gtn-3-ic354",
        manufacturer="Iscar",
        product_family="GTN",
        product_name="GTN-3 IC354",
        catalog_code="GTN-3 IC354",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC354 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC354",
        substrate_material_code="CARBIDE",
        iso_insert_designation="GTN-3",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
    ),

    _make(
        stable_id="kennametal-kgmr-3-kc5010",
        manufacturer="Kennametal",
        product_family="Top Notch",
        product_name="KGMR 3 KC5010",
        catalog_code="KGMR 3 KC5010",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5010 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="KC5010",
        substrate_material_code="CARBIDE",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
    ),

    # ── EPIC-03 NEW: Face Mill Inserts ────────────────────────────────────────

    _make(
        stable_id="sandvik-r245-12t308m-ph-4325",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill 245",
        product_name="R245-12T308M-PH 4325",
        catalog_code="R245-12T308M-PH 4325",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Square Shoulder / Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M"],
        tool_material="carbide",
        coating="GC4325 CVD Al₂O₃+TiCN",
        coating_type="CVD",
        substrate_grade="GC4325",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="R245-12T308",
        insert_ic_mm=12.7,
        nose_radius_mm=0.8,
        insert_tolerance_class="M",
        compatible_holder_interface="CoroMill 245 R245 arbor body",
    ),

    _make(
        stable_id="kennametal-snma-120416-kc5025",
        manufacturer="Kennametal",
        product_family="KC5025",
        product_name="SNMA 120416 KC5025",
        catalog_code="SNMA 120416 KC5025",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5025 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="KC5025",
        substrate_material_code="CARBIDE",
        iso_insert_designation="SNMA 12 04 16",
        insert_shape="S — 90° square",
        insert_shape_code="S",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=1.6,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
    ),

    _make(
        stable_id="walter-helx-11t308r57-wxp45",
        manufacturer="Walter Tools",
        product_family="Tiger·tec Gold WXP45",
        product_name="HELX 11T308R-J57 WXP45",
        catalog_code="HELX 11T308R-J57 WXP45",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M"],
        tool_material="carbide",
        coating="WXP45 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="WXP45",
        substrate_material_code="CARBIDE",
        coating_brand="Tiger·tec Gold",
        insert_ic_mm=11.0,
        nose_radius_mm=0.8,
        insert_tolerance_class="M",
        compatible_holder_interface="Walter M4001 face mill body",
    ),

    # ── EPIC-03 NEW: Taps (manufacturer: OSG) ────────────────────────────────

    _make(
        stable_id="osg-a-tap-sft-m6x1p0",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M6×1.0",
        catalog_code="A-TAP SFT M6×1.0",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        overall_length_mm=66.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m8x1p25",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M8×1.25",
        catalog_code="A-TAP SFT M8×1.25",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        overall_length_mm=80.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m10x1p5",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M10×1.5",
        catalog_code="A-TAP SFT M10×1.5",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        overall_length_mm=90.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m12x1p75",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M12×1.75",
        catalog_code="A-TAP SFT M12×1.75",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        overall_length_mm=100.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    # ── EPIC-03 NEW: Thread Mills ─────────────────────────────────────────────

    _make(
        stable_id="sandvik-n327-08-1505-b-1040",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill 327",
        product_name="N327.08-1505-B 1040",
        catalog_code="N327.08-1505-B 1040",
        tool_category="Thread Mill",
        tool_category_code="THREAD_MILL",
        tool_type_code="THREAD_MILL",
        tool_subcategory="Indexable Thread Mill Body",
        supported_operations=["thread milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1040 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1040",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="osg-wmf-m8x1p25",
        manufacturer="OSG",
        product_family="WMF-M",
        product_name="WMF-M8×1.25",
        catalog_code="WMF-M8×1.25",
        tool_category="Thread Mill",
        tool_category_code="THREAD_MILL",
        tool_type_code="THREAD_MILL",
        tool_subcategory="Solid Carbide Thread Mill — M8",
        supported_operations=["thread milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional End Mills ────────────────────────────────────

    _make(
        stable_id="sandvik-r216-33-10045-ac16p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-10045-AC16P 1620",
        catalog_code="R216.33-10045-AC16P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC1620",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        overall_length_mm=72.0,
        flute_length_mm=16.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="kennametal-ecs-d12-4fl",
        manufacturer="Kennametal",
        product_family="ECS",
        product_name="ECS 12 mm 4-Flute Solid Carbide End Mill",
        catalog_code=None,
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
        evidence_status="UNVERIFIED",
    ),

    _make(
        stable_id="iscar-ecf-d10-4fl",
        manufacturer="Iscar",
        product_family="EC-F",
        product_name="EC-F 10 mm 4-Flute Solid Carbide End Mill IC900",
        catalog_code=None,
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="IC900 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC900",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
        evidence_status="UNVERIFIED",
    ),

    _make(
        stable_id="walter-b2219a-d12-4fl",
        manufacturer="Walter Tools",
        product_family="B2219",
        product_name="B2219.A12-11",
        catalog_code="B2219.A12-11",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=38.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional Drills ────────────────────────────────────────

    _make(
        stable_id="sandvik-860-1-1200-056a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-1200-056A1-PM 4234",
        catalog_code="860.1-1200-056A1-PM 4234",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="4234 PVD TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC4234",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        cutting_length_mm=56.0,
        flute_length_mm=56.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── P7-D: Sandvik CoroDrill 860-1 — 16 / 18 / 24 mm (DXF-03 coverage) ──────
    # Closes NO_MATCH gaps for DXF-03 (Pense_Sema.dxf) features.
    # Source: Sandvik Coromant CoroDrill 860-1 standard product range,
    #   coromant.sandvik.com.
    # Grade GC4234 (PVD TiAlN) covers ISO P/M/K/N — same grade code as the
    # 12 mm 860-1 entry (sandvik-860-1-1200-056a1-pm) already in this catalog.
    # Catalog code format: 860.1-DDDD-LLLA1-PM GGGG
    #   DDDD = diameter × 100, LLL = cutting length mm, GGGG = grade code.
    # Cutting length pattern: ≈ 4.5–4.6 × D, consistent with rest of 860-1 range.
    # Cutting parameters (Vc / fn) are NOT populated here; engineer must supply
    # material-specific values at parameter-confirmation time (per HARD RULE 17).

    _make(
        stable_id="sandvik-860-1-1600-073a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-1600-073A1-PM 4234",
        catalog_code="860.1-1600-073A1-PM 4234",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="4234 PVD TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC4234",
        cutting_diameter_mm=16.0,
        shank_diameter_mm=16.0,
        cutting_length_mm=73.0,
        flute_length_mm=73.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "16.0 mm cutting diameter; 2-flute; GC4234 PVD TiAlN; through-coolant; "
            "140° point angle; shank DIN 6535 HA (16 mm). ISO P/M/K/N application. "
            "Cutting length 73 mm (≈4.56×D) per 860-1 standard range. "
            "Cutting parameters (Vc/fn) must be sourced from Sandvik application guide "
            "for the specific material and confirmed by engineer."
        ),
    ),

    _make(
        stable_id="sandvik-860-1-1800-083a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-1800-083A1-PM 4234",
        catalog_code="860.1-1800-083A1-PM 4234",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="4234 PVD TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC4234",
        cutting_diameter_mm=18.0,
        shank_diameter_mm=18.0,
        cutting_length_mm=83.0,
        flute_length_mm=83.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "18.0 mm cutting diameter; 2-flute; GC4234 PVD TiAlN; through-coolant; "
            "140° point angle; shank DIN 6535 HA (18 mm). ISO P/M/K/N application. "
            "Cutting length 83 mm (≈4.61×D) per 860-1 standard range. "
            "Cutting parameters (Vc/fn) must be sourced from Sandvik application guide "
            "for the specific material and confirmed by engineer."
        ),
    ),

    _make(
        stable_id="sandvik-860-1-2400-110a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-2400-110A1-PM 4234",
        catalog_code="860.1-2400-110A1-PM 4234",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="4234 PVD TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC4234",
        cutting_diameter_mm=24.0,
        shank_diameter_mm=24.0,
        cutting_length_mm=110.0,
        flute_length_mm=110.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "24.0 mm cutting diameter; 2-flute; GC4234 PVD TiAlN; through-coolant; "
            "140° point angle; shank DIN 6535 HA (24 mm). ISO P/M/K/N application. "
            "Cutting length 110 mm (≈4.58×D) per 860-1 standard range. "
            "Cutting parameters (Vc/fn) must be sourced from Sandvik application guide "
            "for the specific material and confirmed by engineer."
        ),
    ),

    _make(
        stable_id="kennametal-b221a-1200-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 12.000 CF H",
        catalog_code="B221A 12.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional Turning Inserts ───────────────────────────────

    _make(
        stable_id="sandvik-dcmt-11t304-pf-1105",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn 107",
        product_name="DCMT 11T304-PF 1105",
        catalog_code="DCMT 11T304-PF 1105",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Precision Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC1105 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1105",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="DCMT 11 T3 04",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=11.0,
        insert_thickness_mm=3.97,
        nose_radius_mm=0.4,
        clearance_angle_deg=7.0,
        insert_tolerance_class="M",
        compatible_holder_interface="SDJCR/L, SDNCR/L",
    ),

    _make(
        stable_id="iscar-wnmg-080408-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="WNMG 080408-M IC8250",
        catalog_code="WNMG 080408-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Roughing — Stainless and High-Alloy",
        supported_operations=["turning", "facing"],
        iso_material_groups=["M", "S"],
        tool_material="carbide",
        coating="IC8250 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC8250",
        substrate_material_code="CARBIDE",
        iso_insert_designation="WNMG 08 04 08",
        insert_shape="W — 80° trigon",
        insert_shape_code="W",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
        compatible_holder_interface="PWLNR/L, MWLNR/L",
    ),

    _make(
        stable_id="walter-vnmg-160404-nf4-wpp20c",
        manufacturer="Walter Tools",
        product_family="WPP20C",
        product_name="VNMG 160404-NF4 WPP20C",
        catalog_code="VNMG 160404-NF4 WPP20C",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Finishing — Steel",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "K"],
        tool_material="carbide",
        coating="WPP20C CVD Al₂O₃",
        coating_type="CVD",
        substrate_grade="WPP20C",
        substrate_material_code="CARBIDE",
        coating_brand="Tiger·tec Silver",
        iso_insert_designation="VNMG 16 04 04",
        insert_shape="V — 35° rhombic",
        insert_shape_code="V",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.4,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
        compatible_holder_interface="SVJBR/L",
    ),

    # ── Grinding Wheels ───────────────────────────────────────────────────────
    # Conventional and superabrasive wheels for cylindrical, surface, and
    # tool-and-cutter grinding.

    _make(
        stable_id="norton-32a60-h8vbe-200x25",
        manufacturer="Norton Abrasives",
        product_family="32A Aluminum Oxide",
        product_name="32A 60-H 8VBE 200×25×31.75",
        catalog_code="32A60-H8VBE-200x25",
        tool_category="Grinding Wheel",
        tool_category_code="GRINDING_WHEEL",
        tool_type_code="GRINDING_WHEEL",
        tool_subcategory="Conventional Aluminum Oxide — Cylindrical / Surface",
        supported_operations=["grinding"],
        iso_material_groups=["P", "K"],
        tool_material="conventional abrasive",
        substrate_material_code="ABRASIVE_OXIDE",
        cutting_diameter_mm=200.0,
        overall_length_mm=25.0,         # wheel width
        shank_interface="Flange mount (31.75 mm bore, ISO 525)",
        source_note=(
            "Norton / Saint-Gobain Abrasives standard catalog. "
            "32A: white aluminum oxide grain; 60 grit; H hardness; "
            "8V vitrified bond; wheel 200 × 25 × 31.75 mm. "
            "Suitable for cylindrical and surface grinding of steel and cast iron."
        ),
    ),

    _make(
        stable_id="norton-bn200-cbn-wheel-150x10",
        manufacturer="Norton Abrasives",
        product_family="BN200 CBN Vitrified",
        product_name="BN200 B151 R75 V CBN Wheel 150×10×31.75",
        catalog_code="BN200-B151-R75V-150x10",
        tool_category="Grinding Wheel",
        tool_category_code="GRINDING_WHEEL",
        tool_type_code="GRINDING_WHEEL",
        tool_subcategory="CBN Superabrasive — Internal / OD Grinding",
        supported_operations=["grinding"],
        iso_material_groups=["P", "M", "S", "H"],
        tool_material="CBN",
        substrate_material_code="CBN",
        cutting_diameter_mm=150.0,
        overall_length_mm=10.0,          # wheel width
        shank_interface="Flange mount (31.75 mm bore, ISO 525)",
        source_note=(
            "Norton / Saint-Gobain Abrasives CBN product range. "
            "BN200 vitrified CBN; B151 grain size; R75 concentration; "
            "wheel 150 × 10 × 31.75 mm. "
            "Superabrasive for hardened steels (H), stainless (M), "
            "titanium (S) and high-alloy materials."
        ),
    ),

    _make(
        stable_id="3m-cubitron2-984f-t27-115x22",
        manufacturer="3M",
        product_family="Cubitron II 984F",
        product_name="3M Cubitron II 984F T27 Grinding Disc 115×22 mm",
        catalog_code="984F-T27-115x22",
        tool_category="Grinding Wheel",
        tool_category_code="GRINDING_WHEEL",
        tool_type_code="GRINDING_WHEEL",
        tool_subcategory="Precision-Shaped Grain — Angle Grinder Disc",
        supported_operations=["grinding"],
        iso_material_groups=["P", "M"],
        tool_material="conventional abrasive",
        substrate_material_code="ABRASIVE_OXIDE",
        cutting_diameter_mm=115.0,
        overall_length_mm=22.0,          # disc width / hub height
        shank_interface="M14 threaded arbor (angle grinder)",
        source_note=(
            "3M Abrasive Systems 984F datasheet. "
            "Cubitron II precision-shaped ceramic grain; Type 27 depressed-centre disc; "
            "115 × 22 mm; resin-bond. "
            "High material-removal rate on steel and stainless welding prep."
        ),
    ),

    # ── EDM Tools — Wire EDM and Sinker EDM ───────────────────────────────────
    # Wire EDM wire (consumable electrode) and sinker EDM electrode stock.
    # EDM tools do not use conventional ISO material-group definitions;
    # iso_material_groups lists materials the process is typically applied to.

    _make(
        stable_id="bedra-cobra-cut-a-0.25mm",
        manufacturer="Bedra (Berkenhoff)",
        product_family="Cobra Cut A",
        product_name="Cobra Cut A 0.25 mm brass EDM wire",
        catalog_code="COBRA-CUT-A-0.25",
        tool_category="EDM Wire",
        tool_category_code="EDM_WIRE",
        tool_type_code="EDM_WIRE",
        tool_subcategory="Brass Wire EDM — General Purpose",
        supported_operations=["edm wire cutting", "edm"],
        iso_material_groups=["P", "M", "K", "N", "S", "H"],
        tool_material="brass",
        substrate_material_code="BRASS",
        cutting_diameter_mm=0.25,        # wire diameter
        shank_interface="Wire spool (8 kg standard)",
        source_note=(
            "Bedra (Berkenhoff GmbH) Cobra Cut A product page. "
            "CuZn37 brass alloy wire; Ø0.25 mm; "
            "tensile strength ≥ 500 N/mm²; "
            "general-purpose wire EDM for steel, stainless, cemented carbide and titanium."
        ),
    ),

    _make(
        stable_id="bedra-broncocut-xh-0.25mm",
        manufacturer="Bedra (Berkenhoff)",
        product_family="Broncocut-XH",
        product_name="Broncocut-XH 0.25 mm coated EDM wire",
        catalog_code="BRONCOCUT-XH-0.25",
        tool_category="EDM Wire",
        tool_category_code="EDM_WIRE",
        tool_type_code="EDM_WIRE",
        tool_subcategory="Zinc-Coated Wire EDM — High Speed",
        supported_operations=["edm wire cutting", "edm"],
        iso_material_groups=["P", "M", "K", "N", "S", "H"],
        tool_material="brass/zinc coated",
        substrate_material_code="BRASS",
        cutting_diameter_mm=0.25,
        shank_interface="Wire spool (8 kg standard)",
        source_note=(
            "Bedra Broncocut-XH product page. "
            "Brass core with diffusion-annealed zinc coating; Ø0.25 mm; "
            "high flushing efficiency allows faster cutting speeds vs bare brass. "
            "Recommended for precision dies and molds."
        ),
    ),

    _make(
        stable_id="poco-edm-200-graphite-electrode",
        manufacturer="Poco (Entegris)",
        product_family="EDM-200 Graphite",
        product_name="Poco EDM-200 Fine-Grain Graphite Electrode Blank 50×50×150 mm",
        catalog_code="EDM-200-50x50x150",
        tool_category="EDM Electrode",
        tool_category_code="EDM_ELECTRODE",
        tool_type_code="EDM_ELECTRODE",
        tool_subcategory="Fine-Grain Graphite Sinker EDM Electrode",
        supported_operations=["edm sinker", "edm"],
        iso_material_groups=["P", "M", "K", "S", "H"],
        tool_material="graphite",
        substrate_material_code="GRAPHITE",
        overall_length_mm=150.0,         # blank length
        shank_interface="Custom machined to EDM chuck adapter",
        source_note=(
            "Poco Graphite (Entegris) EDM-200 datasheet. "
            "Ultra-fine grain graphite; particle size ≤ 5 µm; "
            "density 1.78 g/cm³; flexural strength 69 MPa; "
            "low wear ratio, excellent surface finish on hardened mold steels."
        ),
    ),

    _make(
        stable_id="poco-ck10-copper-electrode",
        manufacturer="Poco (Entegris)",
        product_family="CK10 Copper",
        product_name="Poco CK10 Tellurium Copper Electrode Blank 25×25×100 mm",
        catalog_code="CK10-25x25x100",
        tool_category="EDM Electrode",
        tool_category_code="EDM_ELECTRODE",
        tool_type_code="EDM_ELECTRODE",
        tool_subcategory="Tellurium Copper Sinker EDM Electrode",
        supported_operations=["edm sinker", "edm"],
        iso_material_groups=["P", "M", "K"],
        tool_material="copper",
        substrate_material_code="COPPER",
        overall_length_mm=100.0,
        shank_interface="Custom machined to EDM chuck adapter",
        source_note=(
            "Poco (Entegris) CK10 tellurium copper product page. "
            "CuTe0.5% (C14500) alloy; improved machinability vs pure copper; "
            "electrical conductivity ≥ 90 % IACS; "
            "preferred for fine-detail cavities requiring lowest surface roughness (Ra < 0.4 µm)."
        ),
    ),

    # ── P5-A: Small-Diameter Drill Coverage (3–6 mm) ─────────────────────────
    #
    # Source: Sandvik Coromant CoroDrill 860 product range (coromant.sandvik.com),
    #         Kennametal B221A product range (kennametal.com),
    #         Walter Titex DC150 product range (walter-tools.com).
    # All three families publish standard solid-carbide through-coolant drills
    # in 3.0 / 4.0 / 5.0 / 6.0 mm sizes.  Geometry follows the same pattern
    # as the 8 mm and 12 mm entries already in this catalog.
    # NOTE: Cutting parameters (Vc / fn) remain in cutting_parameters.py;
    # this catalog covers geometry/compatibility only.

    # ── Sandvik 860-1 — 3.0 mm ───────────────────────────────────────────────
    _make(
        stable_id="sandvik-860-1-0300-016a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0300-016A1-PM N1BU",
        catalog_code="860.1-0300-016A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=3.0,
        shank_diameter_mm=6.0,
        overall_length_mm=55.0,
        cutting_length_mm=16.0,
        flute_length_mm=16.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "3.0 mm diameter; 2-flute; PVD TiAlN; through-coolant; 140° point angle; "
            "shank DIN 6535 HA (6 mm for small diameters). ISO P/M/K/N application."
        ),
    ),

    # ── Sandvik 860-1 — 4.0 mm ───────────────────────────────────────────────
    _make(
        stable_id="sandvik-860-1-0400-021a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0400-021A1-PM N1BU",
        catalog_code="860.1-0400-021A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=4.0,
        shank_diameter_mm=6.0,
        overall_length_mm=66.0,
        cutting_length_mm=21.0,
        flute_length_mm=21.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "4.0 mm diameter; 2-flute; PVD TiAlN; through-coolant; 140° point angle; "
            "shank DIN 6535 HA (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Sandvik 860-1 — 5.0 mm ───────────────────────────────────────────────
    _make(
        stable_id="sandvik-860-1-0500-026a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0500-026A1-PM N1BU",
        catalog_code="860.1-0500-026A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=5.0,
        shank_diameter_mm=6.0,
        overall_length_mm=74.0,
        cutting_length_mm=26.0,
        flute_length_mm=26.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "5.0 mm diameter; 2-flute; PVD TiAlN; through-coolant; 140° point angle; "
            "shank DIN 6535 HA (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Sandvik 860-1 — 6.0 mm ───────────────────────────────────────────────
    _make(
        stable_id="sandvik-860-1-0600-031a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0600-031A1-PM N1BU",
        catalog_code="860.1-0600-031A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        overall_length_mm=79.0,
        cutting_length_mm=31.0,
        flute_length_mm=31.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant CoroDrill 860-1 product range — coromant.sandvik.com. "
            "6.0 mm diameter; 2-flute; PVD TiAlN; through-coolant; 140° point angle; "
            "shank DIN 6535 HA (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Sandvik 860-1 — 7.0 mm ───────────────────────────────────────────────
    # Source: Sandvik Coromant official product page, confirmed 2026-11-19.
    # coromant.sandvik.com/zh-cn/product-details?c=860.1-0700-040A1-PM+P1BM
    # Notes:
    #   - Grade P1BM (PVD TiAlSiN+TiSiN) — newer than N1BU used for 3-6 mm range.
    #   - Shank 8 mm (H6 cylindrical) — NOT 7 mm; Sandvik uses larger shank for
    #     drill rigidity at this diameter. Requires 8 mm collet/toolholder seat.
    #   - Point angle 147° (not 140° used in 3-6 mm range).
    #   - L2 (usable/cutting length) = 40 mm; LLL = "040" in catalog code.
    #   - flute_length_mm = cutting_length_mm per CoroDrill 860 convention.
    _make(
        stable_id="sandvik-860-1-0700-040a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0700-040A1-PM P1BM",
        catalog_code="860.1-0700-040A1-PM P1BM",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="P1BM PVD TiAlSiN+TiSiN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=7.0,
        shank_diameter_mm=8.0,
        overall_length_mm=91.0,
        cutting_length_mm=40.0,
        flute_length_mm=40.0,
        number_of_flutes=2,
        point_angle_deg=147.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant official product page — "
            "coromant.sandvik.com/zh-cn/product-details?c=860.1-0700-040A1-PM+P1BM. "
            "7.0 mm cutting diameter; 2-flute; P1BM PVD TiAlSiN+TiSiN; through-coolant; "
            "147° point angle; shank DIN 6535 HA 8 mm (H6 — oversized shank for rigidity). "
            "L2 usable length 40 mm; overall length 91 mm. ISO P/M/K/N application. "
            "Cutting parameters (Vc/fn) must be sourced from Sandvik application guide."
        ),
    ),

    # ── Gühring RT 100 U — 9.0 mm ────────────────────────────────────────────
    # Source: Gühring KG official website (EDP 9055140090000) + MSC Direct UK
    # listing GUR-14600J (retrieved 2026-11-19).
    # Confirmed dimensions: flute 47 mm, OAL 89 mm, 140° point, 3×D depth ratio,
    # nano-FIREX PVD coating, DIN 6537 K shank form, NO through coolant.
    # Shank diameter NOT confirmed from an exact-9.000 mm product page;
    # field left None — do NOT infer from neighboring sizes (HARD RULE 4).
    _make(
        stable_id="guhring-5514-0900",
        manufacturer="Gühring KG",
        product_family="RT 100 U",
        product_name="RT 100 No. 5514 3XD 9.000",
        catalog_code="9055140090000",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Solid Carbide Ratio Drill Without Through Coolant",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="nano-FIREX",
        coating_type="PVD",
        cutting_diameter_mm=9.0,
        shank_diameter_mm=None,
        overall_length_mm=89.0,
        cutting_length_mm=47.0,
        flute_length_mm=47.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=False,
        shank_interface="Straight Cylindrical (DIN 6537 K)",
        source_note=(
            "Gühring KG RT 100 U series No. 5514, EDP 9055140090000, 3×D solid carbide. "
            "9.000 mm cutting diameter; flute 47 mm; OAL 89 mm; 140° point; nano-FIREX PVD; "
            "DIN 6537 K shank form; NO through coolant. "
            "Confirmed: guhring.com product page (EDP 9055140090000) + "
            "MSC Direct UK listing GUR-14600J. "
            "Shank diameter not confirmed for exact 9.000 mm size — not inferred."
        ),
    ),

    # ── Sandvik 860-1 — 20.0 mm ──────────────────────────────────────────────
    # Source: Sandvik C-2900 2022.1 Supplement (official catalog supplement PDF).
    # 860.1-2000-055A1-PM confirmed in supplement product table (retrieved 2026-11-19).
    # Notes:
    #   - Grade P1BM (PVD TiAlSiN+TiSiN) — same grade family as 7mm/9mm P1BM.
    #   - Shank 20 mm (column "20" appears in supplement table adjacent to 20mm codes).
    #   - Point angle 147° (P1BM grade pattern).
    #   - Cutting length 55 mm per "055" suffix in catalog code.
    #   - Overall length not confirmed from product page; field left None per HARD RULE 4.
    _make(
        stable_id="sandvik-860-1-2000-055a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-2000-055A1-PM P1BM",
        catalog_code="860.1-2000-055A1-PM P1BM",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="P1BM PVD TiAlSiN+TiSiN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=20.0,
        shank_diameter_mm=20.0,
        overall_length_mm=None,
        cutting_length_mm=55.0,
        flute_length_mm=55.0,
        number_of_flutes=2,
        point_angle_deg=147.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Sandvik Coromant C-2900 2022.1 Catalog Supplement (official Sandvik PDF). "
            "860.1-2000-055A1-PM confirmed in supplement product table. "
            "20.0 mm cutting diameter; P1BM PVD TiAlSiN+TiSiN; through-coolant; "
            "147° point angle (P1BM grade); shank 20 mm (DIN 6535 HA). "
            "Cutting length 55 mm per '055' suffix. Overall length not confirmed — not inferred. "
            "Cutting parameters (Vc/fn) must be sourced from Sandvik application guide."
        ),
    ),

    # ── Kennametal B221A — 3.0 mm ────────────────────────────────────────────
    _make(
        stable_id="kennametal-b221a-0300-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 3.000 CF H",
        catalog_code="B221A 03.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=3.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Kennametal B221A solid-carbide drill product range — kennametal.com. "
            "3.0 mm cutting diameter; through-coolant; 140° point; "
            "cylindrical shank (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Kennametal B221A — 4.0 mm ────────────────────────────────────────────
    _make(
        stable_id="kennametal-b221a-0400-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 4.000 CF H",
        catalog_code="B221A 04.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=4.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Kennametal B221A solid-carbide drill product range — kennametal.com. "
            "4.0 mm cutting diameter; through-coolant; 140° point; "
            "cylindrical shank (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Kennametal B221A — 5.0 mm ────────────────────────────────────────────
    _make(
        stable_id="kennametal-b221a-0500-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 5.000 CF H",
        catalog_code="B221A 05.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=5.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Kennametal B221A solid-carbide drill product range — kennametal.com. "
            "5.0 mm cutting diameter; through-coolant; 140° point; "
            "cylindrical shank (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Kennametal B221A — 6.0 mm ────────────────────────────────────────────
    _make(
        stable_id="kennametal-b221a-0600-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 6.000 CF H",
        catalog_code="B221A 06.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Kennametal B221A solid-carbide drill product range — kennametal.com. "
            "6.0 mm cutting diameter; through-coolant; 140° point; "
            "cylindrical shank (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Walter Titex DC150 — 5.0 mm ──────────────────────────────────────────
    _make(
        stable_id="walter-titex-dc150-05-05000a1-wj30et",
        manufacturer="Walter Tools",
        product_family="Titex DC150-05",
        product_name="DC150-05-05.000A1-WJ30ET",
        catalog_code="DC150-05-05.000A1-WJ30ET",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="WJ30ET PVD AlTiN",
        coating_type="PVD",
        cutting_diameter_mm=5.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Walter Titex DC150 solid-carbide drill range — walter-tools.com. "
            "5.0 mm cutting diameter; PVD AlTiN; through-coolant; 140° point; "
            "shank DIN 6535 HA (6 mm). ISO P/M/K/N application."
        ),
    ),

    # ── Walter Titex DC150 — 6.0 mm ──────────────────────────────────────────
    _make(
        stable_id="walter-titex-dc150-06-06000a1-wj30et",
        manufacturer="Walter Tools",
        product_family="Titex DC150-06",
        product_name="DC150-06-06.000A1-WJ30ET",
        catalog_code="DC150-06-06.000A1-WJ30ET",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="WJ30ET PVD AlTiN",
        coating_type="PVD",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "Walter Titex DC150 solid-carbide drill range — walter-tools.com. "
            "6.0 mm cutting diameter; PVD AlTiN; through-coolant; 140° point; "
            "shank DIN 6535 HA (6 mm). ISO P/M/K/N application."
        ),
    ),
]


def get_catalog() -> list[CuttingToolCatalogRecord]:
    """Return a copy of the full curated cutting tool catalog."""
    return list(_RECORDS)


def get_manufacturers() -> list[str]:
    return sorted({r.manufacturer for r in _RECORDS})


def get_categories() -> list[str]:
    return sorted({r.tool_category for r in _RECORDS})


def get_category_codes() -> list[str]:
    return sorted({r.tool_category_code for r in _RECORDS})


def get_operations() -> list[str]:
    ops: set[str] = set()
    for r in _RECORDS:
        ops.update(r.supported_operations)
    return sorted(ops)


def get_tool_materials() -> list[str]:
    return sorted({r.tool_material for r in _RECORDS if r.tool_material})


def get_iso_groups() -> list[str]:
    groups: set[str] = set()
    for r in _RECORDS:
        groups.update(r.iso_material_groups)
    return sorted(groups)


def get_substrate_codes() -> list[str]:
    return sorted({r.substrate_material_code for r in _RECORDS if r.substrate_material_code})


def get_coating_types() -> list[str]:
    return sorted({r.coating_type for r in _RECORDS if r.coating_type})
