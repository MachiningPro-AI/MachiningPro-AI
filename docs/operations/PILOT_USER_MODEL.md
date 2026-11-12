# MachiningPro AI — Pilot User Model

**Status:** DRAFT  
**Last updated:** 2026-11-12

---

## Roles

Three roles are defined for the production pilot phase.
No role permits CNC dispatch or autonomous manufacturing.

### pilot_engineer

Default role for pilot participants performing engineering evaluation.

| Permission | Allowed |
|---|---|
| Upload synthetic/pilot CAD files | YES |
| Run drawing analysis | YES |
| Run CAD feature recognition | YES |
| View process planning recommendations | YES |
| View process route recommendations | YES |
| View machine/tool selection recommendations | YES |
| View cutting data recommendations | YES |
| View cycle time estimates | YES |
| View cost/RFQ estimates | YES |
| Export analysis results (JSON, HTML, CSV) | YES |
| Confirm/reject drawing extraction | YES (review gate) |
| View workflow history (own sessions) | YES |
| View recommendations for manufacturing | YES (PROPOSED_ONLY) |
| Approve manufacturing plan for execution | NO |
| Dispatch NC program | NO |
| Write to CNC machine | NO |
| Administer user accounts | NO |
| View other users' sessions | NO |

### pilot_reviewer

Senior role for reviewing and approving extracted engineering data and plans.

| Permission | Allowed |
|---|---|
| All pilot_engineer permissions | YES |
| Approve/reject drawing extraction review steps | YES |
| Approve/reject process route selection | YES |
| Approve/reject manufacturing plan (for record only — no machine dispatch) | YES |
| View all sessions in own pilot group | YES |
| Dispatch NC program to CNC | NO |
| Write to CNC machine | NO |
| Administer user accounts | NO |

### pilot_admin

Administrative role for managing the pilot environment and user accounts.
Does not grant manufacturing execution rights.

| Permission | Allowed |
|---|---|
| All pilot_reviewer permissions | YES |
| Create/deactivate pilot user accounts | YES |
| Reset passwords | YES |
| View audit log | YES |
| Configure environment settings | YES |
| Approve manufacturing plan for execution | NO |
| Dispatch NC program | NO |
| Write to CNC machine | NO |

---

## Assignment Rules

- Every pilot user receives exactly one role.
- Default assignment for new users: `pilot_engineer`.
- `pilot_admin` is assigned manually by the pilot coordinator.
- No shared accounts. Each participant has individual credentials.
- Demo account (`demo` / `A1234`) must NOT be assigned to any pilot user.

---

## User Lifecycle

```
PROVISIONED → ACTIVE → SUSPENDED → REVOKED
```

| State | Can login | Can run analysis | Can export |
|---|---|---|---|
| PROVISIONED | NO (pending password set) | NO | NO |
| ACTIVE | YES | YES | YES |
| SUSPENDED | NO | NO | NO |
| REVOKED | NO | NO | NO |

---

## Credential Requirements

- Username: unique, no personal email required during pilot
- Password: minimum 12 characters (see SECRETS_INVENTORY.md for policy)
- Role: explicitly assigned, not inferred
- Status: explicitly set to ACTIVE before first login
- No shared/group accounts

---

## Current Auth Architecture Limitation

The current system is a single env-var credential. See:
`docs/operations/MULTI_USER_AUTH_EXTENSION_PLAN.md`

**MULTI_USER_AUTH_SUPPORTED = NO (current)**

This must be resolved before pilot go-live.
