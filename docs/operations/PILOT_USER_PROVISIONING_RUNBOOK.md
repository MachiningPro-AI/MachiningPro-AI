# MachiningPro AI — Pilot User Provisioning Runbook

**Status:** ACTIVE  
**Last updated:** 2026-11-12  
**Rule:** This document contains no passwords, hashes, secrets, or credential values.

---

## Prerequisites

- Python 3.11+ with `bcrypt>=4.0` installed (`pip install bcrypt`)
- Access to the pilot credential store file location
- The credential store file must NOT be committed to source control

---

## 1. Create a New Pilot User

Run the provisioning script. It prompts for a password interactively — plaintext is never stored or logged.

```
python scripts/provision_pilot_user.py \
    --username <unique-username> \
    --display-name "<Display Name>" \
    --role pilot_engineer|pilot_reviewer|pilot_admin
```

**Requirements:**
- Username: lowercase, no spaces, unique
- Password: minimum 12 characters
- Role: exactly one of `pilot_engineer`, `pilot_reviewer`, `pilot_admin`

**The script outputs a JSON record.** Add this record to the pilot credential store file (`pilot_users.json`). Do NOT commit that file.

**Example record structure (no real values):**
```json
{
  "username": "pilot-engineer-01",
  "password_hash": "$2b$12$<bcrypt-hash>",
  "display_name": "Pilot Engineer 01",
  "role": "pilot_engineer",
  "active": true
}
```

The credential store file has the top-level structure:
```json
{
  "users": [
    { ... },
    { ... }
  ]
}
```

---

## 2. Choose a Role

| Role | Permissions | Notes |
|---|---|---|
| `pilot_engineer` | Upload CAD, run analysis, view results, export | No user administration |
| `pilot_reviewer` | Review/confirm extracted data, approve review steps | No upload, no machine dispatch |
| `pilot_admin` | User listing (`GET /api/pilot/users`), all engineer permissions | No CNC dispatch; still requires human review for manufacturing steps |

**Default for new users: `pilot_engineer`** (least privilege).  
`pilot_admin` must be explicitly assigned and justified.

---

## 3. Generate a Password

Use a password manager or the system's secure random generator.

Minimum requirements:
- At least 12 characters
- Not guessable, not reused from demo
- Not the demo password (`A1234` or any trivial variant)

Communicate the password to the user via a secure channel (not email plaintext, not Slack plaintext).

---

## 4. Provision the Hash

Run step 1 above. The script:
1. Prompts for the password via `getpass` (not echoed to terminal)
2. Generates a bcrypt hash (cost factor 12, random salt)
3. Immediately discards the plaintext from memory
4. Outputs only the JSON record (hash, role, metadata)

---

## 5. Disable an Account

Set `"active": false` in the user's record in the credential store file. Redeploy the pilot service. The user will receive 401 on next login attempt.

```json
{
  "username": "pilot-engineer-01",
  "password_hash": "...",
  "role": "pilot_engineer",
  "active": false
}
```

---

## 6. Enable an Account

Set `"active": true` in the user's record. Redeploy.

---

## 7. Reset a Password

1. Run `scripts/provision_pilot_user.py` for the same username with a new password.
2. Replace the `password_hash` field for that user in the credential store.
3. Redeploy the pilot service.
4. All existing sessions for that user will remain valid until their JWT expires (default 24h). If immediate invalidation is required, rotate `MACHININGPRO_DEV_JWT_SECRET` as well.

---

## 8. Revoke Access

Immediate revocation:
1. Set `"active": false` for the user AND redeploy.
2. If a JWT is already issued and must be invalidated immediately, also rotate `MACHININGPRO_DEV_JWT_SECRET` (this invalidates ALL sessions for all users).

Permanent removal:
1. Remove the user's record from the credential store file entirely.
2. Redeploy.

---

## Security Reminders

- The credential store file (`pilot_users.json`) is git-ignored — do NOT commit it.
- Never put the credential store file in a Docker image layer.
- Deploy as a Render secret file (see `PILOT_FINAL_DEPLOYMENT_RUNBOOK.md`).
- Never log or print passwords or bcrypt hashes.
- Rotate all pilot credentials before go-live if placeholder passwords were used during provisioning testing.
