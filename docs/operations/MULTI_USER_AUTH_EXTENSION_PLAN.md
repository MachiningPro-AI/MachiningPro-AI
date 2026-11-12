# MachiningPro AI — Multi-User Auth Extension Plan

**Status:** PLAN — Implementation required before pilot go-live  
**Last updated:** 2026-11-12  
**Trigger:** MULTI_USER_AUTH_SUPPORTED=NO (current architecture is single env-var credential)

---

## Current Architecture

`backend/api/auth.py` authenticates against three environment variables:

```
MACHININGPRO_DEV_JWT_SECRET   — JWT signing secret (min 32 chars)
MACHININGPRO_DEV_USERNAME     — single username
MACHININGPRO_DEV_PASSWORD     — single plaintext password compared at runtime
```

This is explicitly labeled "local development authentication" in the source.
It supports exactly one user. It does not hash passwords.

**This architecture must not be used for pilot user management.**

---

## Extension Approach — Minimal Credential Store

Do not build a full identity management system.
Implement the minimum required to support individual pilot users.

### Design

A flat JSON credential store loaded at startup:

```
backend/auth/pilot_users.json.example  (example schema — no real values)
```

Actual credential file:
- NOT committed to source control
- Deployed via Render env var or mounted secret file
- Or: individual credentials loaded from environment using a fixed naming pattern

### User Record Schema

```json
{
  "users": [
    {
      "username": "pilot-user-001",
      "password_hash": "<bcrypt hash>",
      "display_name": "Pilot Engineer 1",
      "role": "pilot_engineer",
      "active": true
    }
  ]
}
```

Fields:
- `username` — unique, lowercase, no spaces
- `password_hash` — bcrypt hash (cost factor ≥ 12); never plaintext
- `display_name` — shown in UI; not used for auth
- `role` — one of: `pilot_engineer`, `pilot_reviewer`, `pilot_admin`
- `active` — boolean; inactive users are rejected at login

### Password Hashing

Use `passlib[bcrypt]` (already a viable dependency for a FastAPI project):

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash (during provisioning)
hashed = pwd_context.hash(plaintext_password)

# Verify (during login)
valid = pwd_context.verify(plaintext_password, stored_hash)
```

### Provisioning Script

Create `scripts/provision_pilot_user.py` (run locally by pilot admin):
- Accepts username, role, generates bcrypt hash
- Outputs a JSON user record for addition to the credential store
- Never stores plaintext password
- Never commits output to git

### Auth Flow Change

Replace `get_configured_credentials()` in `auth.py` with:
1. Load credential store (env var path or mounted file)
2. Find user by username
3. Verify bcrypt hash
4. Check `active == true`
5. Return `LoginResponse` with role from credential store

### JWT Token

No change to JWT structure. JWT secret remains in env var.
Pilot environment uses a separate `MACHININGPRO_PILOT_JWT_SECRET`.

### Backward Compatibility

The existing env-var single-user path (`MACHININGPRO_DEV_USERNAME` / `MACHININGPRO_DEV_PASSWORD`)
should be preserved as a fallback for local development only.

If `MACHININGPRO_PILOT_USERS_FILE` env var is set → use credential store.
If not set → fall back to existing dev env-var auth.

---

## Files to Create/Modify

| File | Action | Note |
|---|---|---|
| `backend/api/auth.py` | Modify | Add credential-store auth path |
| `backend/auth/pilot_users.json.example` | Create | Schema example only, no real users |
| `scripts/provision_pilot_user.py` | Create | Provisioning helper |
| `tests/unit/api/test_pilot_auth.py` | Create | Tests for multi-user auth |
| `docs/operations/SECRETS_INVENTORY.md` | Update | Add new env var name |

---

## Effort Estimate

Small, isolated change. Estimated 2–4 hours implementation + tests.

---

## Implementation Gate

This plan must be implemented and tested before:
- `SAFE_FOR_PRODUCTION_PILOT` can be set to YES
- Any pilot user is provisioned
- Pilot environment is launched

---

## Current Status

```
MULTI_USER_AUTH_SUPPORTED  = NO
IMPLEMENTATION_STATUS      = PLANNED (not started)
BLOCKING_PILOT_GO_LIVE     = YES
```
