# MachiningPro AI — Pilot Post-Deploy Smoke Test Plan

**Status:** ACTIVE  
**Last updated:** 2026-11-12  
**Rule:** Use only synthetic fixtures from `tests/qualification/fixtures/`. No real customer CAD.

---

## Infrastructure Checks

| # | Test | Method | Expected |
|---|---|---|---|
| S-01 | Health endpoint | `GET /api/health` | HTTP 200, `status: ok` |
| S-02 | Readiness endpoint | `GET /api/ready` | HTTP 200 |
| S-03 | No cold-start | Repeat S-01 after 60s idle | Response time < 2s (confirms always-on) |

---

## Authentication Tests

| # | Test | Input | Expected |
|---|---|---|---|
| A-01 | Valid login — pilot_engineer | `pilot-engineer-01` + correct password | HTTP 200, `role: "pilot_engineer"`, token returned |
| A-02 | Valid login — pilot_reviewer | `pilot-reviewer-01` + correct password | HTTP 200, `role: "pilot_reviewer"`, token returned |
| A-03 | Valid login — pilot_admin | `pilot-admin-01` + correct password | HTTP 200, `role: "pilot_admin"`, token returned |
| A-04 | Invalid password | `pilot-engineer-01` + wrong password | HTTP 401, no token |
| A-05 | Nonexistent user | `nobody` + any password | HTTP 401, no token |
| A-06 | Inactive user | Deactivated user + correct password | HTTP 401, no token |
| A-07 | Demo credentials rejected | `demo` + `A1234` | HTTP 401 — MUST be rejected in pilot mode |
| A-08 | Missing credentials | Empty body | HTTP 422 or 401 |
| A-09 | No password in JWT | Decode pilot token | Token payload must not contain `password` or `password_hash` |

---

## Authorization Tests

| # | Test | Input | Expected |
|---|---|---|---|
| Z-01 | Protected endpoint without token | `GET /api/cad/sessions` (no auth) | HTTP 401 or 403 |
| Z-02 | Protected endpoint with invalid token | `Authorization: Bearer invalid` | HTTP 401 |
| Z-03 | Admin endpoint — pilot_admin | `GET /api/pilot/users` with admin token | HTTP 200, user list (no hashes) |
| Z-04 | Admin endpoint — pilot_engineer | `GET /api/pilot/users` with engineer token | HTTP 403 |
| Z-05 | Admin endpoint — pilot_reviewer | `GET /api/pilot/users` with reviewer token | HTTP 403 |

---

## CAD Upload Tests

| # | Test | Input | Expected |
|---|---|---|---|
| U-01 | Valid DXF upload | `part_a_simple_plate.dxf` from fixtures | HTTP 200, session_id returned |
| U-02 | Upload without auth | Same file, no token | HTTP 401 or 403 |
| U-03 | Empty file | 0-byte DXF | Controlled error, not 500 |
| U-04 | Unsupported format | `.txt` file | Controlled error |
| U-05 | Path traversal filename | `../evil.dxf` | Rejected, not 500 |

---

## Drawing Parser Tests

| # | Test | Input | Expected |
|---|---|---|---|
| D-01 | Parse synthetic DXF with units | `part_d_precision_component.dxf` | Detections returned, units identified |
| D-02 | Unitless DXF | `part_g_negative_incomplete.dxf` | UNIT_UNKNOWN or controlled response — not fabricated |
| D-03 | No annotations | Minimal geometry DXF | Controlled empty-detections response |

---

## CAD Feature Recognition Tests

| # | Test | Input | Expected |
|---|---|---|---|
| F-01 | Circles recognized | `part_a_simple_plate.dxf` | Hole candidates returned |
| F-02 | Square NOT a hole | Closed square polyline | No hole candidate |
| F-03 | Feature provenance | Any recognized feature | `feature_id`, `recognition_method`, `confidence` present; no fabricated depth/material |

---

## Process Routes Tests

| # | Test | Input | Expected |
|---|---|---|---|
| R-01 | Route with known feature | Recognized circle feature from F-01 | Route candidate generated |
| R-02 | Unknown values remain unknown | Partial feature without material/tolerance | UNKNOWN not substituted |

---

## Workflow Tests

| # | Test | Input | Expected |
|---|---|---|---|
| W-01 | Create workflow | Synthetic part with recognized features | Workflow ID returned |
| W-02 | Get workflow status | Valid workflow ID | Status response (not 404) |
| W-03 | List history | Authenticated request | History list (may be empty) |
| W-04 | History without auth | No token | HTTP 401 |

---

## Export Tests

| # | Test | Input | Expected |
|---|---|---|---|
| E-01 | Export plan.json | Valid workflow | Valid JSON, no server paths, auth required |
| E-02 | Export without auth | No token | HTTP 401 |

---

## Security Tests

| # | Test | Expected |
|---|---|---|
| SEC-01 | X-Content-Type-Options header | `nosniff` on all responses |
| SEC-02 | X-Frame-Options header | `DENY` on all responses |
| SEC-03 | Content-Security-Policy header | Present on all responses |
| SEC-04 | No stack trace in 4xx responses | Error responses: JSON `detail` only |
| SEC-05 | No server path in error responses | No `/home/`, `/etc/`, Windows paths |
| SEC-06 | No JWT secret in responses | Inspect all error and success responses |
| SEC-07 | NC output offline only | Any NC generation result must have `offline_candidate: true` |

---

## NC Safety Tests

| # | Test | Expected |
|---|---|---|
| NC-01 | NC generation returns offline candidate | `OFFLINE_CANDIDATE=True`, `NOT_DISPATCHED=True` |
| NC-02 | No dispatch endpoint exists or triggers machine | No `/api/dispatch` or equivalent that starts real action |

---

## Completion Criteria

All smoke tests must PASS before the pilot is considered live-ready.

Any failure blocks pilot onboarding until investigated and resolved.

Results should be recorded by the pilot coordinator with timestamps.
