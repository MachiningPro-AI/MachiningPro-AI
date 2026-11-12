"""Generate deterministic synthetic part DXF artifacts for qualification campaign.

Generates 7 synthetic parts as minimal DXF R12 files. No external dependencies beyond stdlib.
Each part has known, independently-specified geometry.

HARD RULE: Generated geometry is deterministic. Random values are never used.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _dxf_header(units_flag: int = 4) -> str:
    """Minimal DXF R12 header. units_flag: 4=mm, 1=inches, 0=unitless."""
    return f"""  0
SECTION
  2
HEADER
  9
$ACADVER
  1
AC1009
  9
$INSUNITS
 70
{units_flag}
  0
ENDSEC
  0
SECTION
  2
ENTITIES
"""


def _dxf_footer() -> str:
    return """  0
ENDSEC
  0
EOF
"""


def _line(x1: float, y1: float, x2: float, y2: float, layer: str = "0") -> str:
    return (
        f"  0\nLINE\n  8\n{layer}\n"
        f" 10\n{x1:.6f}\n 20\n{y1:.6f}\n 30\n0.000000\n"
        f" 11\n{x2:.6f}\n 21\n{y2:.6f}\n 31\n0.000000\n"
    )


def _circle(cx: float, cy: float, r: float, layer: str = "0") -> str:
    return (
        f"  0\nCIRCLE\n  8\n{layer}\n"
        f" 10\n{cx:.6f}\n 20\n{cy:.6f}\n 30\n0.000000\n"
        f" 40\n{r:.6f}\n"
    )


def _arc(cx: float, cy: float, r: float, start_deg: float, end_deg: float, layer: str = "0") -> str:
    return (
        f"  0\nARC\n  8\n{layer}\n"
        f" 10\n{cx:.6f}\n 20\n{cy:.6f}\n 30\n0.000000\n"
        f" 40\n{r:.6f}\n"
        f" 50\n{start_deg:.6f}\n 51\n{end_deg:.6f}\n"
    )


def _text(x: float, y: float, text: str, height: float = 2.5, layer: str = "ANNOTATION") -> str:
    return (
        f"  0\nTEXT\n  8\n{layer}\n"
        f" 10\n{x:.6f}\n 20\n{y:.6f}\n 30\n0.000000\n"
        f" 40\n{height:.6f}\n"
        f"  1\n{text}\n"
    )


def _rect(x: float, y: float, w: float, h: float, layer: str = "0") -> str:
    return (
        _line(x, y, x + w, y, layer)
        + _line(x + w, y, x + w, y + h, layer)
        + _line(x + w, y + h, x, y + h, layer)
        + _line(x, y + h, x, y, layer)
    )


# ---------------------------------------------------------------------------
# PART_A: Simple Plate 120x80x12 — 4 corner holes Ø10, 1 center Ø20
# ---------------------------------------------------------------------------
def gen_part_a() -> str:
    """PART_A_SIMPLE_PLATE: 120×80 mm outline, 4×Ø10 through-hole candidates,
    1×Ø20 center circle. Units: mm. Material: unspecified (UNKNOWN)."""
    entities = ""
    # Outline
    entities += _rect(0, 0, 120, 80, "OUTLINE")
    # 4 corner hole candidates — Ø10, radius 5
    corners = [(15, 15), (105, 15), (15, 65), (105, 65)]
    for cx, cy in corners:
        entities += _circle(cx, cy, 5.0, "HOLE_CANDIDATES")
    # Center feature Ø20, radius 10
    entities += _circle(60, 40, 10.0, "CENTER_FEATURE")
    # Annotations
    entities += _text(130, 40, "120x80x12 PLATE", layer="ANNOTATION")
    entities += _text(130, 35, "4xPHI10 THRU", layer="ANNOTATION")
    entities += _text(130, 30, "PHI20 CENTER", layer="ANNOTATION")
    entities += _text(130, 25, "MATERIAL: UNSPECIFIED", layer="ANNOTATION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_B: Stepped Shaft — turning part with shoulder and chamfer
# Note: 2D cross-section view only (turning part shown as half-profile)
# ---------------------------------------------------------------------------
def gen_part_b() -> str:
    """PART_B_STEPPED_SHAFT: C45 steel. 2D profile cross-section.
    Ø60 (L=80), shoulder → Ø40 (L=50), Ø30 (L=30). M30x1.5 thread on Ø30 end.
    Chamfer 1x45° at shoulder transitions. Units: mm."""
    entities = ""
    # Half-profile (top half, rotation axis at y=0)
    # Section 1: Ø60 for 80mm length → half-radius=30, from x=0 to x=80
    entities += _line(0, 0, 80, 0, "CENTER_LINE")  # axis
    entities += _line(0, 30, 80, 30, "PROFILE")     # top of Ø60
    entities += _line(0, 0, 0, 30, "PROFILE")        # left face
    entities += _line(80, 30, 81, 20, "CHAMFER")     # chamfer at shoulder
    # Section 2: Ø40 for 50mm → half-radius=20, from x=81 to x=130
    entities += _line(81, 20, 130, 20, "PROFILE")
    entities += _line(130, 20, 131, 15, "CHAMFER")
    # Section 3: Ø30 for 30mm → half-radius=15, from x=131 to x=160
    entities += _line(131, 15, 160, 15, "PROFILE")
    entities += _line(160, 0, 160, 15, "PROFILE")  # right face
    # Thread annotation on Ø30 section
    entities += _text(145, 17, "M30x1.5-6g", layer="ANNOTATION")
    entities += _text(0, 35, "MATERIAL: C45 DIN EN 10083-2", layer="ANNOTATION")
    entities += _text(0, 32, "Ra 1.6 on Phi40 (journal)", layer="ANNOTATION")
    entities += _text(0, 29, "Ra 3.2 elsewhere", layer="ANNOTATION")
    entities += _text(0, 26, "UNITS: mm", layer="ANNOTATION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_C: Milling Block with pocket, slot, holes, counterbore
# ---------------------------------------------------------------------------
def gen_part_c() -> str:
    """PART_C_MILLING_BLOCK: 100×60×30 mm. Central pocket 60×30×10 mm deep.
    Through slot 80×10 mm. 4×Ø8 holes. 2×Ø12/Ø20 counterbore. Chamfer 1×45°.
    Material: S355JR. Units: mm."""
    entities = ""
    # Outer profile
    entities += _rect(0, 0, 100, 60, "OUTLINE")
    # Central pocket outline
    entities += _rect(20, 15, 60, 30, "POCKET")
    # Through slot (open feature — intentionally ambiguous)
    entities += _rect(10, 25, 80, 10, "SLOT")
    # 4 through holes Ø8, r=4
    for cx, cy in [(10, 10), (90, 10), (10, 50), (90, 50)]:
        entities += _circle(cx, cy, 4.0, "HOLE_CANDIDATES")
    # 2 counterbore holes: inner Ø12/r=6, outer Ø20/r=10
    for cx, cy in [(35, 30), (65, 30)]:
        entities += _circle(cx, cy, 6.0, "HOLE_CANDIDATES")   # drill hole
        entities += _circle(cx, cy, 10.0, "COUNTERBORE")      # cbore
    entities += _text(0, -8, "100x60x30 MILLING BLOCK", layer="ANNOTATION")
    entities += _text(0, -13, "MATERIAL: S355JR", layer="ANNOTATION")
    entities += _text(0, -18, "POCKET DEPTH: 10mm (see note)", layer="ANNOTATION")
    entities += _text(0, -23, "UNITS: mm", layer="ANNOTATION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_D: Precision Component — explicit GD&T data
# ---------------------------------------------------------------------------
def gen_part_d() -> str:
    """PART_D_PRECISION_COMPONENT: Explicit drawing data.
    Ø20 H7 (0 / +0.021). Position tolerance 0.05 ⌀ | Datum A | Datum B.
    Ra 1.6 on bore. General tolerance: ISO 2768-m. Material: 42CrMo4.
    Units: mm."""
    entities = ""
    # Simple rectangular part outline 80×50mm
    entities += _rect(0, 0, 80, 50, "OUTLINE")
    # Precision bore Ø20 H7, r=10
    entities += _circle(40, 25, 10.0, "PRECISION_BORE")
    # Datum A indicator (bottom face)
    entities += _line(0, -5, 80, -5, "DATUM_A")
    entities += _text(82, -5, "[A]", layer="DATUM_ANNOTATION")
    # Datum B indicator (left face)
    entities += _line(-5, 0, -5, 50, "DATUM_B")
    entities += _text(-10, 52, "[B]", layer="DATUM_ANNOTATION")
    # Dimension annotations
    entities += _text(0, 56, "PHI20 H7 (+0.000/+0.021)", layer="DIMENSION")
    entities += _text(0, 61, "POS: PHI0.05 | A | B", layer="GDT_FRAME")
    entities += _text(0, 66, "Ra 1.6 (bore only)", layer="SURFACE_FINISH")
    entities += _text(0, 71, "GENERAL TOL: ISO 2768-m", layer="GENERAL_TOL")
    entities += _text(0, 76, "MATERIAL: 42CrMo4 DIN EN 10083-1 +QT", layer="TITLE_BLOCK")
    entities += _text(0, 81, "UNITS: mm", layer="TITLE_BLOCK")
    entities += _text(0, 86, "INSPECTION: 100% bore CMM", layer="INSPECTION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_E: Multi-setup Component
# ---------------------------------------------------------------------------
def gen_part_e() -> str:
    """PART_E_MULTI_SETUP_COMPONENT: L-shaped bracket.
    Setup 1 (VMC): face mill top, 4×Ø12 through holes.
    Setup 2 (VMC): face mill side, 2×Ø6 cross holes.
    Material: AlMg1SiCu. Units: mm."""
    entities = ""
    # L-shape outline
    entities += _line(0, 0, 100, 0, "OUTLINE")
    entities += _line(100, 0, 100, 40, "OUTLINE")
    entities += _line(100, 40, 60, 40, "OUTLINE")
    entities += _line(60, 40, 60, 80, "OUTLINE")
    entities += _line(60, 80, 0, 80, "OUTLINE")
    entities += _line(0, 80, 0, 0, "OUTLINE")
    # Setup 1 holes — 4×Ø12, r=6
    for cx, cy in [(20, 20), (80, 20), (20, 60), (45, 60)]:
        entities += _circle(cx, cy, 6.0, "HOLE_SETUP1")
    # Setup 2 cross holes — 2×Ø6, r=3 (from side face)
    for cx, cy in [(30, 40), (50, 40)]:
        entities += _circle(cx, cy, 3.0, "HOLE_SETUP2")
    entities += _text(0, -8, "L-BRACKET MULTI-SETUP", layer="ANNOTATION")
    entities += _text(0, -13, "MATERIAL: AlMg1SiCu (6061-equivalent)", layer="ANNOTATION")
    entities += _text(0, -18, "SETUP 1: VMC (top face)", layer="ANNOTATION")
    entities += _text(0, -23, "SETUP 2: VMC (side face)", layer="ANNOTATION")
    entities += _text(0, -28, "UNITS: mm", layer="ANNOTATION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_F: Turning + Milling (mill-turn or separate ops)
# ---------------------------------------------------------------------------
def gen_part_f() -> str:
    """PART_F_TURNING_AND_MILLING: Turned diameter Ø50, Ø35 journal.
    1×Ø8 cross-hole from side. 2 flats (across flats 30mm). M24x2 thread.
    Material: S355JR. Units: mm."""
    entities = ""
    # Turned profile half-section
    entities += _line(0, 0, 100, 0, "CENTER_LINE")
    entities += _line(0, 25, 50, 25, "PROFILE")   # Ø50 section
    entities += _line(50, 25, 51, 17.5, "CHAMFER")
    entities += _line(51, 17.5, 90, 17.5, "PROFILE")  # Ø35 journal
    entities += _line(90, 17.5, 91, 12, "CHAMFER")
    entities += _line(91, 12, 100, 12, "PROFILE")  # threaded end Ø24
    entities += _line(0, 0, 0, 25, "PROFILE")
    entities += _line(100, 0, 100, 12, "PROFILE")
    # Cross-hole Ø8, centered at x=65 on turned axis — shown as circle on face view
    entities += _circle(65, 25, 4.0, "CROSS_HOLE")
    # Flat indicator (dashed line or annotation only in 2D)
    entities += _text(60, 30, "2 FLATS: SW30", layer="ANNOTATION")
    entities += _text(85, 15, "M24x2-6g", layer="ANNOTATION")
    entities += _text(0, 35, "MATERIAL: S355JR", layer="ANNOTATION")
    entities += _text(0, 32, "UNITS: mm", layer="ANNOTATION")
    return _dxf_header(units_flag=4) + entities + _dxf_footer()


# ---------------------------------------------------------------------------
# PART_G: Negative / Incomplete — deliberately omits key data
# ---------------------------------------------------------------------------
def gen_part_g() -> str:
    """PART_G_NEGATIVE_INCOMPLETE: Deliberately incomplete drawing.
    - No units annotation
    - No material
    - Hole depth not given (through vs blind unknown)
    - Tolerance not specified on bore
    - Surface finish absent
    - Ambiguous open polyline (not a valid closed feature)
    Purpose: test fail-closed behavior."""
    entities = ""
    # Outline — missing dimension lines
    entities += _rect(0, 0, 50, 50, "OUTLINE")
    # Circle that might or might not be a hole — no depth, no tolerance
    entities += _circle(25, 25, 8.0, "UNKNOWN_FEATURE")
    # Partial arc — open, not a closed feature
    entities += _arc(10, 10, 5.0, 0, 270, "PARTIAL_GEOMETRY")
    # Open polyline / incomplete geometry (3 lines, not closed)
    entities += _line(5, 45, 20, 45, "OPEN_GEOMETRY")
    entities += _line(20, 45, 20, 35, "OPEN_GEOMETRY")
    # Deliberately NO unit annotation
    # Deliberately NO material annotation
    # Deliberately NO tolerance on circle
    entities += _text(0, -8, "NO MATERIAL", layer="ANNOTATION")
    entities += _text(0, -13, "NO UNITS GIVEN", layer="ANNOTATION")
    entities += _text(0, -18, "NO DEPTH GIVEN", layer="ANNOTATION")
    entities += _text(0, -23, "NO TOLERANCE ON BORE", layer="ANNOTATION")
    return _dxf_header(units_flag=0) + entities + _dxf_footer()  # units_flag=0 = unitless


def generate_all(output_dir: Path | None = None) -> dict[str, Path]:
    """Generate all 7 synthetic part DXF files. Returns dict of part_id -> path."""
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    parts = {
        "PART_A": gen_part_a,
        "PART_B": gen_part_b,
        "PART_C": gen_part_c,
        "PART_D": gen_part_d,
        "PART_E": gen_part_e,
        "PART_F": gen_part_f,
        "PART_G": gen_part_g,
    }

    written = {}
    for part_id, fn in parts.items():
        path = out / f"{part_id.lower()}_synthetic.dxf"
        path.write_text(fn(), encoding="ascii")
        written[part_id] = path
        print(f"Generated {part_id}: {path}")

    return written


if __name__ == "__main__":
    generate_all()
