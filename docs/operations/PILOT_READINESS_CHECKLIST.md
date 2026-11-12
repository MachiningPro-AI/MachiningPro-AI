# MachiningPro AI — Production Pilot Readiness Checklist

**Status:** PARTIAL — Engineering + Auth complete; Infrastructure + Governance pending  
**Last updated:** 2026-11-12  
**Qualification baseline:** main @ 836719c

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

## Authentication & Credentials (Dev — Complete; Ops — Partial)

| # | Check | Status | Evidence |
|---|---|---|---|
| A-01 | Multi-user auth implemented | ✓ DONE | commit 836719c — backend/auth/pilot_users.py |
| A-02 | Bcrypt password hashing in use | ✓ DONE | bcrypt cost=12, constant-time checkpw |
| A-03 | Pilot JWT secret separate from demo JWT secret | ✗ PENDING (ops) | Set MACHININGPRO_PILOT_JWT_SECRET in pilot env vars |
| A-04 | Individual credentials provisioned for each pilot user | ✓ DEMONSTRATED | 3 placeholder users generated (pilot_users.json.example + pilot_users.json); real passwords must be set before go-live — see PILOT_USER_PROVISIONING_GUIDE.md |
| A-05 | Demo credentials (demo/A1234) NOT usable in pilot env | ✓ DONE | Enforced in auth.py; 33 tests confirm |
| A-06 | No shared pilot account | ✓ DONE | Per-user bcrypt records enforced by design |
| A-07 | Auth regression tests PASS with new multi-user code | ✓ DONE | 33 pilot auth tests PASS, 307 total PASS, commit 836719c |

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
AUTH_CODE_READY                = YES   (A-01, A-02, A-05, A-06, A-07 complete)
AUTH_OPS_READY                 = NO    (A-03 pending: set MACHININGPRO_PILOT_JWT_SECRET)
PROVISIONING_DEMONSTRATED      = YES   (A-04: placeholder users generated, guide written)
INFRASTRUCTURE_READY           = NO    (I-01 through I-05 pending)
AUDIT_READY                    = NO    (O-01 through O-05 pending)
GOVERNANCE_READY               = NO    (G-01 through G-06 pending)

SAFE_FOR_PRODUCTION_PILOT      = CONDITIONAL
  Remaining minimum viable gate items:
  → [OPS]   I-01: Upgrade to always-on hosting
  → [OPS]   A-03: Set MACHININGPRO_PILOT_JWT_SECRET in pilot env
  → [OPS]   A-04: Provision real user credentials (rotate placeholder passwords)
  → [OPS]   G-04: Designate pilot coordinator
SAFE_FOR_AUTONOMOUS_MANUFACTURING = NO (non-negotiable; no code path exists)
```

---

## Minimum Viable Pilot Gate

The absolute minimum for a controlled pilot (not full checklist):

1. ✓ A-01/A-02: Multi-user bcrypt auth implemented
2. ✗ I-01: Always-on hosting (Render Starter or equivalent)
3. ✗ A-03: Separate pilot JWT secret set in env
4. ✗ A-04: Real user credentials provisioned (placeholder passwords rotated)
5. ✓ A-05: Demo credentials blocked in pilot mode
6. ✗ G-04: Pilot coordinator designated

Items 2, 3, 4, 6 must be ✓ before first pilot user is onboarded.
