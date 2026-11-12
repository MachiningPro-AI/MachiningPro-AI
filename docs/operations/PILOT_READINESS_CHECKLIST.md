# MachiningPro AI — Production Pilot Readiness Checklist

**Status:** PENDING — Items marked ✗ must be completed before pilot go-live  
**Last updated:** 2026-11-12  
**Qualification baseline:** main @ edd73c4

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
| I-02 | Persistent disk attached to pilot service | ✗ PENDING | Configure Render disk on pilot service |
| I-03 | Pilot service responds to /api/health without cold-start | ✗ PENDING | Verify after I-01 |
| I-04 | Pilot CORS_ORIGINS set to pilot URL only | ✗ PENDING | Set in pilot service env vars |
| I-05 | Render Free demo service kept separate (not upgraded) | ✗ PENDING | Confirm demo and pilot are separate services |

---

## Authentication & Credentials (Dev + Ops — Pending)

| # | Check | Status | Action Required |
|---|---|---|---|
| A-01 | Multi-user auth implemented | ✗ PENDING | Implement per MULTI_USER_AUTH_EXTENSION_PLAN.md (~2–4h) |
| A-02 | Bcrypt password hashing in use | ✗ PENDING | Part of A-01 |
| A-03 | Pilot JWT secret separate from demo JWT secret | ✗ PENDING | Generate and set MACHININGPRO_PILOT_JWT_SECRET in pilot env |
| A-04 | Individual credentials provisioned for each pilot user | ✗ PENDING | Run provision_pilot_user.py for each user after A-01 |
| A-05 | Demo credentials (demo/A1234) NOT usable in pilot env | ✗ PENDING | Verified after A-01+A-03 |
| A-06 | No shared pilot account | ✗ PENDING | Enforced by A-01 |
| A-07 | Auth regression tests PASS with new multi-user code | ✗ PENDING | Part of A-01 |

---

## Audit & Observability (Planned)

| # | Check | Status | Action Required |
|---|---|---|---|
| O-01 | Login events logged (username, timestamp, success/fail) | ✗ PENDING | Extend audit log in auth.py |
| O-02 | File upload events logged (user, filename hash, timestamp) | ✗ PENDING | Extend existing observability |
| O-03 | Analysis run events logged | ✗ PENDING | Extend existing observability |
| O-04 | Export events logged | ✗ PENDING | Extend existing observability |
| O-05 | Audit log accessible to pilot_admin | ✗ PENDING | Add audit log endpoint (auth-protected) |

Audit logs must NOT contain: passwords, JWT secrets, full file contents, or customer PII.

---

## Governance

| # | Check | Status | Action Required |
|---|---|---|---|
| G-01 | Pilot user list documented (names/roles only, no passwords) | ✗ PENDING | Pilot coordinator creates list |
| G-02 | Data handling policy agreed for any customer CAD | ✗ PENDING | Legal/stakeholder sign-off |
| G-03 | Rollback procedure tested | ✗ PENDING | Test redeploy to previous commit on pilot service |
| G-04 | Pilot coordinator designated | ✗ PENDING | Name the pilot admin |
| G-05 | Pilot duration defined | ✗ PENDING | Set start/end dates |
| G-06 | Feedback collection channel defined | ✗ PENDING | Issue tracker / form / meeting cadence |

---

## Go/No-Go Summary

```
ENGINEERING_READY              = YES   (E-01 through E-09 complete)
INFRASTRUCTURE_READY           = NO    (I-01 through I-05 pending)
AUTH_READY                     = NO    (A-01 through A-07 pending)
AUDIT_READY                    = NO    (O-01 through O-05 pending)
GOVERNANCE_READY               = NO    (G-01 through G-06 pending)

SAFE_FOR_PRODUCTION_PILOT      = CONDITIONAL
  → Must complete: I-01, I-03, A-01, A-02, A-03, A-04, A-05 at minimum
SAFE_FOR_AUTONOMOUS_MANUFACTURING = NO (non-negotiable; no code path exists)
```

---

## Minimum Viable Pilot Gate

The absolute minimum for a controlled pilot (not full checklist):

1. ✗ I-01: Always-on hosting
2. ✗ A-01: Multi-user auth implemented
3. ✗ A-03: Separate pilot JWT secret
4. ✗ A-04: Individual credentials for each pilot user
5. ✗ A-05: Demo credentials not usable in pilot
6. ✗ G-04: Pilot coordinator designated

All six must be ✓ before first pilot user is onboarded.
