# MachiningPro AI — Pilot Final Deployment Runbook

**Status:** ACTIVE  
**Last updated:** 2026-11-12  
**Rule:** This document contains no passwords, secrets, or credential values.

---

## Prerequisites

- Render account with billing enabled (Starter plan or higher — Free tier is NOT SLA-suitable)
- Pilot credential store file created (`pilot_users.json` — see `PILOT_USER_PROVISIONING_RUNBOOK.md`)
- A strong pilot JWT secret (min 32 chars) generated and stored securely outside source control
- Pilot coordinator designated
- Current codebase: `main @ ff209ce` or later

---

## Deployment Sequence

### Step 1 — Create the Pilot Service

In the Render Dashboard:
1. Click **New → Web Service**
2. Connect the same GitHub repository (`MachiningPro_AI_NEXT`)
3. Name: `machiningpro-ai-pilot` (keep this separate from `machiningpro-ai-demo`)
4. Branch: `main`
5. Plan: **Starter** (or higher — do NOT use Free)
6. Build command: `cd frontend/app && npm ci && npm run build && cd ../.. && pip install .`
7. Start command: `uvicorn backend.api.app --host 0.0.0.0 --port $PORT`
8. Health check path: `/api/health`

### Step 2 — Select Always-On Hosting

Confirm the plan is **Starter** or higher:
- Always-on (no sleep)
- No cold-start
- Render Free is NOT suitable for pilot (23s cold-start, no SLA)

### Step 3 — Set `MACHININGPRO_ENV=pilot`

In Environment → Environment Variables, add:
```
Key:   MACHININGPRO_ENV
Value: pilot
```

> Note: The pilot authentication mode is activated by setting `MACHININGPRO_PILOT_USERS_FILE` (see Step 5). `MACHININGPRO_ENV` is an additional signal for observability and future environment-scoped behavior.

### Step 4 — Add the Pilot JWT Secret

In Environment → Environment Variables, add:
```
Key:   MACHININGPRO_DEV_JWT_SECRET
Value: <your-pilot-specific-jwt-secret — min 32 chars — NOT the demo secret>
```

This must be a NEW secret value, different from the demo service's `MACHININGPRO_DEV_JWT_SECRET`.

### Step 5 — Add the Pilot Credential Store as a Secret File

In Environment → **Secret Files**, add:
1. Click **Add Secret File**
2. File path: `/etc/secrets/pilot_users.json`
3. Contents: paste the entire contents of your `pilot_users.json` credential store (bcrypt hashes only — no plaintext passwords)
4. Click **Save**

Then set the environment variable pointing to it:
```
Key:   MACHININGPRO_PILOT_USERS_FILE
Value: /etc/secrets/pilot_users.json
```

### Step 6 — Configure CORS for the Pilot Origin

In Environment → Environment Variables, set:
```
Key:   CORS_ORIGINS
Value: https://machiningpro-ai-pilot.onrender.com
```

(Replace with actual pilot service URL once it's created.)

### Step 7 — Deploy

Click **Deploy**. Render builds and starts the service. Monitor the deploy log for errors.

### Step 8 — Check Health

After deploy:
```
GET https://machiningpro-ai-pilot.onrender.com/api/health
```
Expected: HTTP 200, `{"status": "ok", ...}`

### Step 9 — Check Readiness

```
GET https://machiningpro-ai-pilot.onrender.com/api/ready
```
Expected: HTTP 200

### Step 10 — Test Pilot Login

Using a pilot credential (NOT demo/A1234):
```
POST /api/login
{"username": "pilot-engineer-01", "password": "<pilot-password>"}
```
Expected: HTTP 200 with `token`, `role: "pilot_engineer"`

### Step 11 — Verify Demo Login is Rejected

```
POST /api/login
{"username": "demo", "password": "A1234"}
```
Expected: HTTP 401 — demo credentials must be rejected in pilot mode.

### Step 12 — Test Role Authorization

Log in as `pilot-admin-01` and call:
```
GET /api/pilot/users
Authorization: Bearer <admin-token>
```
Expected: HTTP 200 with user list (no password hashes).

Log in as `pilot-engineer-01` and call the same endpoint:
Expected: HTTP 403.

### Step 13 — Upload Synthetic DXF

Upload a test DXF file (use fixtures from `tests/qualification/fixtures/`):
```
POST /api/cad/upload
Authorization: Bearer <pilot-engineer-token>
```
Expected: HTTP 200, session ID returned.

### Step 14 — Run Drawing/CAD Workflow

Using the session from Step 13:
- `POST /api/drawing-parser/analyze`
- `GET /api/drawing-parser/{session_id}/detections`
- `POST /api/cad/features/{session_id}`
Expected: Drawing and feature results returned, review_required maintained.

### Step 15 — Verify Exports

```
GET /api/export/{workflow_id}/plan.json
Authorization: Bearer <pilot-engineer-token>
```
Expected: Valid JSON export, no server paths, no secrets.

### Step 16 — Verify No CNC Dispatch

Confirm that no endpoint exists or responds to auto-dispatch commands:
- NC output must remain `OFFLINE_CANDIDATE`
- No `/api/dispatch` or equivalent should trigger real machine action

### Step 17 — Verify Logging

Check Render service logs:
- Login success/failure events should appear (username, timestamp)
- No passwords, JWT secrets, or hashes in logs
- No server filesystem paths in error responses

### Step 18 — Verify Rollback

Test that a rollback is possible:
1. In Render Dashboard → pilot service → Deploys
2. Identify the previous deploy
3. Confirm "Roll Back" option exists
4. (Optional) Perform a test rollback and re-deploy to confirm it works

---

## Post-Deployment Security Checklist

- [ ] Security headers present on all responses (X-Frame-Options, CSP, nosniff, HSTS)
- [ ] Demo credentials rejected (Step 11)
- [ ] Role authorization enforced (Step 12)
- [ ] No server paths in API error responses
- [ ] No stack traces in API error responses
- [ ] JWT does not contain password or hash
- [ ] NC outputs remain offline candidates

---

## Important Notes

### Render Free vs Pilot Service
The public demo (`machiningpro-ai-demo`) may remain on the Free tier. The pilot service (`machiningpro-ai-pilot`) MUST be on a paid plan. Never upgrade the demo service to serve pilot traffic — keep them separate.

### Ephemeral Storage
On Render, workflow and CAD artifact data is ephemeral unless a persistent disk is attached. The pilot credential store is durable (it lives in the Secret File). Pilot users should be informed that workflow history does not persist across redeployments unless a persistent disk is configured.

### JWT Secret
The pilot JWT secret must differ from the demo secret. If they are the same, a demo session token would be valid in the pilot service. Use `secrets.token_hex(32)` to generate a fresh secret.

### Credential Rotation Before Go-Live
If placeholder users were created during provisioning testing (e.g., `pilot-engineer-01` with a placeholder password), rotate ALL passwords using `scripts/provision_pilot_user.py` before onboarding real pilot users.
