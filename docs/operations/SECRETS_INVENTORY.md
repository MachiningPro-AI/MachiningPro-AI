# MachiningPro AI — Secrets Inventory

**Status:** ACTIVE  
**Last updated:** 2026-11-12  
**Rule:** This file lists variable NAMES and PURPOSES only. No values, no hashes, no tokens.

---

## Demo Environment Secrets

| Variable Name | Purpose | Storage | Notes |
|---|---|---|---|
| `MACHININGPRO_DEV_JWT_SECRET` | JWT signing secret for demo deployment | Render env var (sync: false) | Min 32 chars; auth fails closed if absent |
| `MACHININGPRO_DEV_USERNAME` | Demo login username (backend check) | Render env var (sync: false) | Single user; dev/demo only |
| `MACHININGPRO_DEV_PASSWORD` | Demo login password (backend check) | Render env var (sync: false) | Compared at runtime; demo/dev only |
| `VITE_DEMO_USERNAME` | Demo prefill username in JS bundle | Render env var (build-time) | Public — embedded in frontend bundle by design |
| `VITE_DEMO_PASSWORD` | Demo prefill password in JS bundle | Render env var (build-time) | Public — embedded in frontend bundle by design |

**Note:** `VITE_DEMO_USERNAME` and `VITE_DEMO_PASSWORD` are intentionally public (they prefill the demo login form). They must never be used as pilot credentials.

---

## Pilot Environment Secrets (Implemented — pending provisioning)

| Variable Name | Purpose | Storage | Notes |
|---|---|---|---|
| `MACHININGPRO_DEV_JWT_SECRET` | JWT signing secret for pilot deployment | Render env var (sync: false) | The pilot service must set this to a NEW value, different from the demo service's secret; min 32 chars. The name is shared with the dev mode variable but the value must be independent. |
| `MACHININGPRO_PILOT_USERS_FILE` | Path to pilot credential store JSON | Render env var or mounted secret | Points to bcrypt-hashed user credential file; activates pilot mode when set |

**Important:** `MACHININGPRO_DEV_JWT_SECRET` is the actual env var read by the auth code (`backend/api/auth.py`) for JWT signing in both dev and pilot modes. For the pilot service, this must be a fresh, independent secret value — never reuse the demo service's value. The name `MACHININGPRO_PILOT_JWT_SECRET` used in some earlier documentation described the intent; `MACHININGPRO_DEV_JWT_SECRET` is the implementation.

Pilot credential store file (not committed to git):
- Contains bcrypt-hashed passwords, usernames, roles, active flags
- Provisioned via `scripts/provision_pilot_user.py`
- Deployed as a Render secret file or mounted volume

---

## Password Policy (Pilot)

- Minimum length: 12 characters
- Storage: bcrypt hash (cost factor ≥ 12)
- Plaintext: never stored, never logged, never committed
- Reset: re-provision via `scripts/provision_pilot_user.py`; deactivate old entry
- Revocation: set `active: false` in credential store; redeploy

---

## Optional / External Service Secrets

| Variable Name | Purpose | Storage | Notes |
|---|---|---|---|
| `MACHININGPRO_TOOLLIFE968_SOURCE_PATH` | Path to external tool life dataset | Env var | Optional; omitted on Render |
| `MACHININGPRO_CUTTING_PARAM_REF_PATH` | Path to cutting parameter reference | Env var | Optional; omitted on Render |

---

## Rotation Policy

| Secret | Rotation Trigger | Procedure |
|---|---|---|
| `MACHININGPRO_DEV_JWT_SECRET` | Suspected compromise or annually | Update Render env var; redeploy; existing tokens invalidated |
| `MACHININGPRO_PILOT_JWT_SECRET` | Suspected compromise, user revocation, or quarterly | Update Render env var; redeploy; all pilot sessions invalidated |
| Individual pilot user passwords | User request, suspected compromise, or quarterly | Re-provision via script; update credential store; redeploy |

---

## What is NOT in this File

- Actual secret values
- Password hashes
- API keys
- Tokens
- Database connection strings (not applicable — SQLite at current scale)
