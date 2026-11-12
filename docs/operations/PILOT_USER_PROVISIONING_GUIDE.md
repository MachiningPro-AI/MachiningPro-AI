# MachiningPro AI — Pilot User Provisioning Guide

## Overview

This guide describes how to create, deploy, and manage individual pilot-user
credentials for MachiningPro AI in production-pilot mode.

**Pilot mode** is activated by setting the `MACHININGPRO_PILOT_USERS_FILE`
environment variable to the path of a JSON credential file.
When active, the shared demo account (`demo` / `A1234`) is **blocked**.

---

## Security Principles

- Passwords are **never stored in plaintext** — only bcrypt hashes (cost=12).
- The credential file must **never be committed to source control**.
- Each pilot user must have a **unique username and unique password**.
- The shared demo credential must **not** be used for pilot access.
- Passwords must be **rotated before first real pilot deployment**.

---

## Step 1 — Generate a User Record

Run the provisioning script interactively on a secure machine:

```bash
python scripts/provision_pilot_user.py \
    --username pilot-engineer-01 \
    --display-name "Pilot Engineer 01" \
    --role pilot_engineer
```

The script will:
1. Prompt for a password (min 12 characters, not echoed).
2. Prompt for password confirmation.
3. Generate a bcrypt hash (cost factor 12, random salt).
4. Print the JSON record to stdout.
5. **Discard** the plaintext password from memory.

**Available roles:**

| Role | Description |
|---|---|
| `pilot_engineer` | Upload CAD, run analysis, view recommendations, export results |
| `pilot_reviewer` | Review/confirm extracted data, approve engineering review steps |
| `pilot_admin` | Account management, environment access (no CNC dispatch) |

---

## Step 2 — Build the Credential File

Create a file (e.g. `pilot_users.json`) with the following structure:

```json
{
  "users": [
    {
      "username": "pilot-engineer-01",
      "password_hash": "<output from provision script>",
      "display_name": "Pilot Engineer 01",
      "role": "pilot_engineer",
      "active": true
    }
  ]
}
```

Repeat for each pilot user. See `backend/auth/pilot_users.json.example` for the
full schema.

**This file must NOT be committed to source control.** It is listed in `.gitignore`.

---

## Step 3 — Deploy the Credential File

### On Render (recommended)

1. In the Render dashboard, go to **Secret Files** for your pilot service.
2. Upload `pilot_users.json` as a secret file at path `/etc/secrets/pilot_users.json`.
3. Set environment variables:

```
MACHININGPRO_PILOT_USERS_FILE=/etc/secrets/pilot_users.json
MACHININGPRO_PILOT_JWT_SECRET=<new independent secret — min 32 random chars>
```

4. Redeploy the service.

### On other platforms

Set `MACHININGPRO_PILOT_USERS_FILE` to the absolute path of the credential file
and ensure it is readable by the application process and not world-readable.

---

## Step 4 — Verify

After deployment, confirm:

```bash
curl https://<your-pilot-host>/api/health
# Expected: {"status":"ok",...} — no version exposed
```

Attempt login with a pilot credential:
```bash
curl -X POST https://<your-pilot-host>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"pilot-engineer-01","password":"<password>"}'
# Expected: {"access_token": "..."}
```

Confirm demo credential is blocked:
```bash
curl -X POST https://<your-pilot-host>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"A1234"}'
# Expected: 401 Unauthorized
```

---

## Password Rotation

To rotate a user's password:

1. Run `scripts/provision_pilot_user.py` with the same username to generate a
   new hash.
2. Replace the `password_hash` field for that user in the credential file.
3. Redeploy the credential file (upload new secret file on Render).
4. The old password is immediately invalid on next request.

---

## Disabling a User

Set `"active": false` for the user record in the credential file and redeploy.
Inactive users receive `401 Unauthorized` even with a valid password.

---

## Revoking a User

Remove the user's record from the credential file entirely and redeploy.

---

## Placeholder Credentials (Pre-Pilot Demo)

The file `backend/auth/pilot_users.json` (git-ignored) may contain placeholder
records generated for provisioning flow demonstration. These use randomly
generated passwords that were immediately discarded — they cannot be used for
real access.

**All placeholder passwords must be rotated before actual pilot deployment.**

---

## Environment Variable Reference

| Variable | Purpose |
|---|---|
| `MACHININGPRO_PILOT_USERS_FILE` | Absolute path to credential JSON file. Activates pilot mode. |
| `MACHININGPRO_PILOT_JWT_SECRET` | Independent JWT signing secret for pilot environment. Must differ from demo secret. |

See `docs/operations/SECRETS_INVENTORY.md` for the full secrets list.
