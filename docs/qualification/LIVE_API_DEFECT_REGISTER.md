# Live API Defect Register

**Project:** MachiningPro AI  
**Branch:** main @ 007df1f  
**Deployment:** https://machiningpro-ai-demo.onrender.com  
**Tested:** 2026-11-12  
**Tester:** Synthetic qualification suite (v1 + v3 + v4 scripts)

---

## Summary

| ID       | Severity | Status  | Title                                    |
|----------|----------|---------|------------------------------------------|
| ADV-001  | ADVISORY | OPEN    | Missing HTTP security headers            |
| ADV-002  | ADVISORY | OPEN    | Health endpoint exposes version string   |
| INFO-001 | INFO     | CLOSED  | Q01 pilot branch guard on main           |

**Confirmed critical/major application defects: 0**  
**Advisory findings: 2**  
**Informational: 1**

---

## ADV-001 — Missing HTTP Security Headers

**Severity:** ADVISORY  
**Category:** Hardening  
**Status:** OPEN  

**Description:**  
The following security headers are absent from HTTP responses:

| Header                   | Expected Value                              | Actual  |
|--------------------------|---------------------------------------------|---------|
| x-content-type-options   | nosniff                                     | ABSENT  |
| x-frame-options          | DENY or SAMEORIGIN                          | ABSENT  |
| content-security-policy  | Restrictive CSP directive                   | ABSENT  |
| strict-transport-security | max-age=31536000; includeSubDomains        | ABSENT  |

**Impact:**  
No immediate exploitable vulnerability demonstrated. These headers reduce attack surface against MIME-type sniffing, clickjacking, and XSS on browsers.

**Risk:**  
LOW for internal/demo use. MEDIUM for public production deployment.

**Recommended fix:**  
Add `SecurityMiddleware` or response headers middleware in `backend/api/app.py`.

**Pilot blocker:** NO — does not affect `SAFE_FOR_PRODUCTION_PILOT` verdict but should be addressed before broad public deployment.

---

## ADV-002 — Health Endpoint Exposes Version String

**Severity:** ADVISORY  
**Category:** Information Disclosure  
**Status:** OPEN  

**Description:**  
`GET /api/health` returns `{"status":"ok","version":"0.1.0-alpha.20","database_ok":true,"artifact_store_ok":true}`.  
The version string `0.1.0-alpha.20` is visible without authentication. This is standard practice for many services but advisory for hardened environments.

**Impact:**  
An attacker knowing the version could look up known vulnerabilities for that exact release.

**Risk:** NEGLIGIBLE for demo. LOW for production.

**Recommended fix:**  
Consider removing `version` from unauthenticated health response, or restricting detailed health info to `/api/readiness` (already requires no auth but returns simpler format).

**Pilot blocker:** NO

---

## INFO-001 — Q01 Pilot Branch Guard on main

**Severity:** INFO  
**Category:** Test Infrastructure  
**Status:** CLOSED (by design)  

**Description:**  
`docs/qualification/execution/run_q01_pilot.py` line 90 contains a hard precondition:

```python
raise RuntimeError(f"WRONG BRANCH: {branch}  (expected work/next-stage)")
```

This prevents Q01 Ollama pilot from running on the `main` branch. As a result, 12 readiness gate tests in `tests/qualification/test_readiness_gate.py` that inspect Q01 artifact files remain `SKIP` on `main`.

**Root cause:**  
The Q01 pilot was designed for feature-branch qualification runs only. It was not intended to run on `main`.

**Impact:**  
- 12 tests in SKIP state permanently on `main`
- `READINESS_GATES_PASS = 0 / 12` (0 pass, 12 skip)
- `SAFE_FOR_PRODUCTION_PILOT` verdict remains `CONDITIONAL` (cannot be `YES` while gates skip)

**Resolution:**  
Architectural limitation acknowledged. The Q01 pilot is designed for `work/next-stage` development workflow. Running on `main` would require either:
1. Creating a `work/next-stage` branch from `main` and running Q01 there
2. Relaxing the branch guard with an explicit override flag

No code change made. Limitation is documented here.

**Pilot blocker:** CONDITIONAL — 12 readiness gate tests cannot pass on `main` without branch guard relaxation.

---

## Previously Identified False Alarms (Closed)

The following were initially flagged in test runs but confirmed as test-script errors, not application defects:

| ID         | Originally Flagged As       | Actual Root Cause                                            | Status  |
|------------|-----------------------------|--------------------------------------------------------------|---------|
| ~~LIVE-001~~ | PATH_TRAVERSAL (C:\temp\dxf) | Python `\t` escape → TAB in test string; not actual backslash | CLOSED  |
| ~~LIVE-002~~ | PATH_TRAVERSAL_ALL_REJECTED | Same as LIVE-001                                            | CLOSED  |
| ~~LIVE-003~~ | DRAWING_PARSER_ANALYZE 422   | Test sent `file_ref` but API needs `source_id`+`content_b64` | CLOSED  |
| ~~LIVE-004~~ | CAD_FEATURE_ENDPOINT 405     | Test used wrong path `/recognize` vs `/analyze`             | CLOSED  |
| ~~LIVE-005~~ | DFM_API 405                  | Test used GET on a POST endpoint                            | CLOSED  |
| ~~LIVE-006~~ | WORKFLOW_REQUIRES_AUTH 404   | `GET /api/workflow` route does not exist (normal FastAPI)   | CLOSED  |
| ~~LIVE-007~~ | SPA_SERVES_FRONTEND HTTP 0   | urllib timeout on HTTPS redirect — not application failure  | CLOSED  |

**CONFIRMED_APPLICATION_DEFECTS = 0**
