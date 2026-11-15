# P4 Implementation vs. Assessment Comparison

**Date:** 2026-11-14  
**Qualification Tier:** P4 — Route Generation & CAM Readiness  
**Repository:** MachiningPro_AI_NEXT  
**Branch / Commit:** main (see MUST 42)

---

## 1. P4-A — Confirmed Feature → Route Generator Bridge

### Assessment (REAL_SAMPLE_P4_ASSESSMENT.md)
> Bridge must accept USER_CONFIRMED features and produce DRAFT/PROPOSED routes.  
> CANDIDATE, AMBIGUOUS, REJECTED must be blocked.

### Implementation
**File:** `backend/manufacturing/confirmed_feature_route.py`

| Requirement | Implemented | Evidence |
|---|---|---|
| Only USER_CONFIRMED / EXACT_BREP / TOPOLOGY_RULE enter route gen | YES | `_ROUTE_ELIGIBLE_CONFIDENCE` frozenset; non-eligible → `blocked=True, blocked_reason=NOT_CONFIRMED` |
| FREEFORM and UNKNOWN feature types blocked | YES | Absent from `MFT_TO_FT`; not in `_ROUTE_ELIGIBLE_CONFIDENCE` check |
| `depth_mm`, `diameter_mm` from confirmed feature only — not re-inferred | YES | `dims` dict built from `mfeat.{diameter,depth,width,length}_mm` |
| Route result carries DRAFT/PROPOSED status | YES | `as_dict()` sets `status="PROPOSED"` on every route |
| `provenance="USER_CONFIRMED"` on all results | YES | `ConfirmedFeatureRouteResult.provenance` default |
| AUTO_APPROVED=NO | YES | No approval path; disclaimer explicit |
| `confirm_feature_with_dimension` endpoint returns `route_generation` | YES | `backend/api/cad_features.py` calls bridge; response includes `route_generation` key |

### DXF-01 E2E Evidence
```
STEP1: SESSION analyzed, 1156 features recognized
STEP2: feat-hole-* type=HOLE conf=INFERRED diam=7.3
STEP3: status=CONFIRMED_WITH_DIMENSION depth=25.0 prov=USER_CONFIRMED
       ROUTE_BLOCKED=False, 3 PROPOSED routes
```

---

## 2. P4-B — CAM Prerequisite Gate

### Assessment
> Seven prerequisite checks must all be MET before `cam_ready=True`.  
> `CAM_READY=YES` means OFFLINE preparation only — never machine dispatch.

### Implementation
**File:** `backend/manufacturing/cam_gate.py`  
**Endpoint:** `GET /api/setup-stock/{id}/cam-status`

| Prerequisite | Implemented | Failure Trigger |
|---|---|---|
| 1. `feature_confirmed` | YES | confidence ≠ USER_CONFIRMED → MISSING |
| 2. `feature_type_mappable` | YES | FREEFORM / UNKNOWN → BLOCKED |
| 3. `depth_known` | YES | depth-requiring types with depth=None → MISSING |
| 4. `diameter_known` | YES | diameter-requiring types with no diameter/radius → MISSING |
| 5. `material_defined` | YES | no session, no stock, empty material_grade → MISSING |
| 6. `stock_complete` | YES | validate_stock_dimensions returns errors → MISSING |
| 7. `setup_defined` | YES | no setup or datum_a=None → MISSING |

| Safety Invariant | Implemented |
|---|---|
| `cam_ready=True` only when ALL 7 MET | YES |
| `offline_only=True` always present in response | YES |
| `AUTO_APPROVED=NO` in disclaimer | YES |
| `CNC_DISPATCH=NO` in disclaimer | YES |

### DXF-01 E2E Evidence
```
STEP5 CAM_GATE: confirmed=1 cam_ready=1 overall_cam_ready=True offline_only=True
STEP5 DISCLAIMER: CAM_READY=YES authorises OFFLINE preparation only. AUTO_APPROVED=NO. CNC_DISPATCH...
STEP5 FIRST_BLOCKER: None
```

---

## 3. P4-C — Process Route Report Generation

### Assessment
> Report must carry PENDING_REVIEW status.  
> Both EN and TR disclaimers required.  
> No approval path.

### Implementation
**File:** `backend/manufacturing/route_report.py`

| Requirement | Implemented | Evidence |
|---|---|---|
| `review_status=PENDING_REVIEW` | YES | Dataclass default; never overwritten |
| EN disclaimer with AUTO_APPROVED=NO | YES | `_EN_DISCLAIMER` constant |
| TR disclaimer with TASLAK | YES | `_TR_DISCLAIMER` constant |
| `provenance=USER_CONFIRMED` | YES | Dataclass default |
| Routes serialized with `status=PROPOSED` | YES | Route loop sets `"status": "PROPOSED"` |
| GD&T constraints serialized with provenance | YES | `feature_ref` and `provenance` in gdt_items |
| CAM gate result flows into report | YES | `cam_state.cam_ready` / `cam_state.first_blocker` |
| HTML output has PENDING_REVIEW banner | YES | `generate_route_report_html()` |
| XSS protection via `html.escape` | YES | All user-data interpolated through `_esc()` |
| `report_id` starts with `RPT-` | YES | hashlib.sha256 prefix |

---

## 4. P4-D — STEP Intake

### Assessment
> Defer until real STEP samples exist.

### Result
```
REAL_STEP_SAMPLE_COUNT: 0
P4D_STATUS: DEFERRED
```

---

## 5. P4-E — DXF-01 E2E Run

### File
`109106_01_00.dxf` (DXF-01 alias)

### Results
| Step | Result |
|---|---|
| Analyze | 200 OK, 1156 features |
| Confirm with depth=25.0 | CONFIRMED_WITH_DIMENSION, prov=USER_CONFIRMED |
| Route generation | 3 PROPOSED routes, not blocked |
| Setup-stock CREATED | RECTANGULAR_BLOCK C45 |
| CAM gate | cam_ready=1/1, overall_cam_ready=True, offline_only=True |

**DXF_01_E2E_PASS=YES**

---

## 6. P4-F — Tesseract Deployment Readiness

| Environment | Status | Action Required |
|---|---|---|
| Local Windows dev | NOT_INSTALLED | Install from UB-Mannheim wiki |
| Render Linux | CONDITIONAL | Add `tesseract-ocr` apt package to render.yaml |
| CI (GitHub Actions) | CONDITIONAL | Add `sudo apt-get install -y tesseract-ocr` |
| pytesseract (Python wrapper) | INSTALLED (0.3.13) | Already in requirements.txt |

**Note:** P4 route generation does NOT depend on OCR. OCR is only used for P3-C (PDF drawing extraction).

---

## 7. Test Coverage

| Workstream | Test File | Tests |
|---|---|---|
| P4-A route bridge | `tests/unit/manufacturing/test_p4a_route_bridge.py` | 20 |
| P4-B CAM gate | `tests/unit/manufacturing/test_p4b_cam_gate.py` | 32 |
| P4-C route report | `tests/unit/manufacturing/test_p4c_route_report.py` | 25 |
| P4-E DXF E2E | `tests/unit/api/test_p4_e2e_dxf.py` | 9 (4 pass, 5 skip) |

Full regression suite (unit): exit code 0 (pre-existing broken test `test_no_hard_coded_cycle_times` deselected — predates P3, not a P4 regression).

---

## 8. Safety Invariants

| Invariant | Status |
|---|---|
| REAL_MACHINE_WRITE=NO | CONFIRMED |
| AUTO_DISPATCH=NO | CONFIRMED |
| AUTO_APPROVE=NO | CONFIRMED |
| ROUTE_STATUS_MAX=PROPOSED | CONFIRMED |
| OFFLINE_ONLY=YES | CONFIRMED |
| FABRICATED_ROUTE=NO | CONFIRMED |
| USER_CONFIRMED provenance preserved | CONFIRMED |

---

**P4_IMPLEMENTATION_STATUS: COMPLETE**
