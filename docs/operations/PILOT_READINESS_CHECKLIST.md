# MachiningPro AI — Production Pilot Readiness Checklist

**Status:** PARTIAL — Engineering + Auth complete; Infrastructure + Governance pending  
**Last updated:** 2026-11-12  
**Qualification baseline:** main @ ff209ce

---

## Engineering Readiness (Code — Completed)

| # | Check | Status | Evidence |
|---|---|---|---|
| E-01 | Synthetic qualification — 235 tests PASS | ✓ DONE | commit 2539ab2 |
| E-02 | TR/EN localization — 1815 key parity, 0 leaks | ✓ DONE | commit 007df1f |
| E-03 | Live API qualification — 83 live tests PASS | ✓ DONE | commit 7b2e3e7 |
| E-04 | 12/12 readiness gates PASS | ✓ DONE | commit 7b2e3e7 |
| E-05 | Security headers (CSP, HSTS, nosniff, X-Frame) | ✓ DONE | commit edd73c4 |
| E-06 | Version removed from /api/health | ✓ DONE | commit edd73c4 |
| E-07 | Safety invariants: no CNC write, no auto-dispatch | ✓ DONE | all qualification runs |
| E-08 | 0 confirmed application defects | ✓ DONE | LIVE_API_DEFECT_REGISTER.md |
| E-09 | 0 security vulnerabilities | ✓ DONE | security qualification |

---

## Infrastructure (Ops — Pending)

| # | Check | Status | Action Required |
|---|---|---|---|
| I-01 | Pilot deployment on always-on hosting (not Render Free) | ✗ PENDING | Create machiningpro-ai-pilot on Render Starter (or equivalent) — see PILOT_HOSTING_OPTIONS.md |
| I-02 | Persistent disk attached to pilot service (optional) | ✗ PENDING | Configure Render disk if workflow persistence is required |
| I-03 | Pilot service responds to /api/health without cold-start | ✗ PENDING | Verify after I-01 |
| I-04 | Pilot CORS_ORIGINS set to pilot URL only | ✗ PENDING | Set in pilot service env vars |
| I-05 | Render Free demo service kept separate (not upgraded) | ✗ PENDING | Confirm demo and pilot are separate services |

---

## Authentication & Credentials (Dev — Complete; Ops — Partial)

| # | Check | Status | Evidence |
|---|---|---|---|
| A-01 | Multi-user auth implemented | ✓ DONE | commit 836719c — backend/auth/pilot_users.py |
| A-02 | Bcrypt password hashing in use | ✓ DONE | bcrypt cost=12, constant-time checkpw |
| A-03 | Pilot JWT secret separate from demo JWT secret | ✗ PENDING (ops) | Set `MACHININGPRO_DEV_JWT_SECRET` to a fresh value in pilot env (do NOT reuse the demo value) |
| A-04 | Individual credentials provisioned for each pilot user | ✓ DEMONSTRATED | 3 placeholder users generated; real passwords must be rotated before go-live — see PILOT_USER_PROVISIONING_RUNBOOK.md |
| A-05 | Demo credentials (demo/A1234) NOT usable in pilot env | ✓ DONE | Enforced in auth.py; 33 tests confirm; test_demo_credentials_rejected_in_pilot_mode PASS |
| A-06 | No shared pilot account | ✓ DONE | Per-user bcrypt records enforced by design |
| A-07 | Auth regression tests PASS | ✓ DONE | 57 auth+security tests PASS, 0 FAIL (ff209ce) |

**Note on A-03:** The implementation reads `MACHININGPRO_DEV_JWT_SECRET` for both demo and pilot modes. The pilot service must set this variable to a NEW, strong, independent value (not the demo value). Documentation references to `MACHININGPRO_PILOT_JWT_SECRET` describe the intent (use a separate secret) — the actual env var name is `MACHININGPRO_DEV_JWT_SECRET`.

---

## Provisioning (Demonstrated)

| # | Check | Status | Evidence |
|---|---|---|---|
| P-01 | Provision script found and validated | ✓ DONE | scripts/provision_pilot_user.py — interactive getpass, bcrypt cost=12 |
| P-02 | Credential store file git-ignored | ✓ DONE | .gitignore entry confirmed |
| P-03 | Placeholder users provisioned and tested | ✓ DEMONSTRATED | pilot-engineer-01, pilot-reviewer-01, pilot-admin-01 |
| P-04 | Placeholder passwords MUST be rotated before go-live | ✗ PENDING (ops) | Run provision_pilot_user.py for each user before pilot onboarding |
| P-05 | Render secret file deployment documented | ✓ DONE | PILOT_FINAL_DEPLOYMENT_RUNBOOK.md Step 5 |
| P-06 | Expected secret file path confirmed from source | ✓ DONE | `MACHININGPRO_PILOT_USERS_FILE` → `/etc/secrets/pilot_users.json` |

---

## Audit & Observability (Planned)

| # | Check | Status | Action Required |
|---|---|---|---|
| O-01 | Login events logged (username, timestamp, success/fail) | ✗ PARTIAL | Metrics counter exists (AUTH_FAILED); structured login event log not yet implemented |
| O-02 | File upload events logged (user, filename hash, timestamp) | ✗ PENDING | Extend existing observability |
| O-03 | Analysis run events logged | ✗ PENDING | Extend existing observability |
| O-04 | Export events logged | ✗ PENDING | Extend existing observability |
| O-05 | Audit log accessible to pilot_admin | ✗ PENDING | Add audit log endpoint (auth-protected) |

Audit logs must NOT contain: passwords, JWT secrets, full file contents, or customer PII.

---

## Security (Completed)

| # | Check | Status | Evidence |
|---|---|---|---|
| S-01 | X-Content-Type-Options: nosniff | ✓ DONE | SecurityHeadersMiddleware, commit edd73c4 |
| S-02 | X-Frame-Options: DENY | ✓ DONE | SecurityHeadersMiddleware, commit edd73c4 |
| S-03 | Content-Security-Policy | ✓ DONE | SecurityHeadersMiddleware, commit edd73c4 |
| S-04 | HSTS (HTTPS-only) | ✓ DONE | SecurityHeadersMiddleware, commit edd73c4 |
| S-05 | No path traversal | ✓ DONE | Upload path validation; live test PASS |
| S-06 | No server path leakage | ✓ DONE | Live security qualification |
| S-07 | No stack trace leakage | ✓ DONE | Live security qualification |
| S-08 | No password/hash in API responses | ✓ DONE | list_pilot_users_safe() strips hashes |
| S-09 | No JWT secret in logs/responses | ✓ DONE | Code review + live qualification |

---

## Governance

| # | Check | Status | Action Required |
|---|---|---|---|
| G-01 | Pilot user list documented (names/roles only, no passwords) | ✗ PENDING | Pilot coordinator creates list |
| G-02 | Data handling policy agreed for any customer CAD | ✗ PENDING | Legal/stakeholder sign-off |
| G-03 | Rollback procedure tested | ✗ PENDING | Test redeploy to previous commit on pilot service |
| G-04 | Pilot coordinator designated | ✗ PENDING | Explicit designation required |
| G-05 | Pilot duration defined | ✗ PENDING | Set start/end dates |
| G-06 | Feedback collection channel defined | ✗ PENDING | Issue tracker / form / meeting cadence |

---

## Post-Deploy Smoke Test

| # | Check | Status |
|---|---|---|
| SM-01 | Health and readiness endpoints | ✗ PENDING (run after deployment) |
| SM-02 | All 3 role logins succeed | ✗ PENDING |
| SM-03 | Demo credentials rejected | ✗ PENDING |
| SM-04 | Role authorization enforced | ✗ PENDING |
| SM-05 | Synthetic DXF upload and pipeline | ✗ PENDING |
| SM-06 | Exports function and are authenticated | ✗ PENDING |
| SM-07 | Security headers present on all responses | ✗ PENDING |
| SM-08 | NC output is offline candidate only | ✗ PENDING |

See `PILOT_POST_DEPLOY_SMOKE_TEST_PLAN.md` for details.

---

## Persistence

| # | Item | Status | Notes |
|---|---|---|---|
| PR-01 | Auth credential persistence | ✓ DONE (design) | Render secret file is durable across redeployments |
| PR-02 | Workflow/CAD data persistence | ✗ EPHEMERAL | Render Free/Starter without disk: lost on restart. Warn pilot users. |
| PR-03 | Persistent disk (optional) | ✗ PENDING | Configure Render disk on pilot service if workflow history must persist |

---

## Go/No-Go Summary

```
ENGINEERING_READY              = YES   (E-01 through E-09 complete)
SECURITY_HEADERS_READY         = YES   (S-01 through S-09 complete)
AUTH_CODE_READY                = YES   (A-01, A-02, A-05, A-06, A-07 complete)
AUTH_OPS_READY                 = NO    (A-03 pending: set fresh MACHININGPRO_DEV_JWT_SECRET in pilot env)
PROVISIONING_DEMONSTRATED      = YES   (P-01 through P-06; real passwords must be rotated, P-04)
INFRASTRUCTURE_READY           = NO    (I-01 through I-05 pending)
AUDIT_READY                    = PARTIAL (O-01 partial: metrics only; structured login events pending)
GOVERNANCE_READY               = NO    (G-01 through G-06 pending)
SMOKE_TEST_READY               = NO    (SM-01 through SM-08 pending — run after deployment)

SAFE_FOR_PRODUCTION_PILOT      = CONDITIONAL
  Minimum viable gate — these MUST be complete before first pilot user is onboarded:
  → [INFRA] I-01: Deploy on always-on hosting (Render Starter or equivalent)
  → [OPS]   A-03: Set fresh MACHININGPRO_DEV_JWT_SECRET in pilot env (not the demo value)
  → [OPS]   P-04: Rotate placeholder passwords / provision real user credentials
  → [OPS]   G-04: Designate pilot coordinator
  → [OPS]   SM-01..08: Post-deploy smoke test must PASS

SAFE_FOR_AUTONOMOUS_MANUFACTURING = NO (non-negotiable; no code path exists)
```

---

## Minimum Viable Pilot Gate (5 items)

| # | Item | Status |
|---|---|---|
| 1 | ✓ Multi-user bcrypt auth implemented | DONE |
| 2 | ✗ Always-on hosting (Render Starter or equivalent) | PENDING |
| 3 | ✗ Fresh MACHININGPRO_DEV_JWT_SECRET in pilot env | PENDING |
| 4 | ✗ Real user credentials provisioned (placeholder passwords rotated) | PENDING |
| 5 | ✗ Pilot coordinator designated | PENDING |
| 6 | ✗ Post-deploy smoke test PASS | PENDING |

Items 2–6 must all be ✓ before first pilot user is onboarded.
