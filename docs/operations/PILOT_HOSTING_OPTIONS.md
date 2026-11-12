# MachiningPro AI — Pilot Hosting Options

**Status:** DRAFT — Decision pending  
**Last updated:** 2026-11-12  
**Current demo:** Render Free (machiningpro-ai-demo.onrender.com)

---

## Why Render Free is NOT Suitable for Production Pilot

| Limitation | Impact |
|---|---|
| Cold-start delay up to 30s | Unacceptable for pilot user experience |
| No SLA | Cannot commit uptime to pilot users |
| Ephemeral filesystem | Workflow state and artifacts lost on restart/redeploy |
| Shared infrastructure | Resource contention possible |
| No persistent disk | Audit log and pilot data cannot survive restarts |

**Verdict: Render Free MUST NOT be used as the pilot deployment host.**

---

## Option A — Render Starter (Paid Web Service)

| Property | Value |
|---|---|
| **Plan** | Starter (approx. $7/month per service) |
| **Cold start** | NONE — always-on |
| **Persistent disk** | Available as add-on ($0.25/GB/month) |
| **SLA** | Render provides 99.95% uptime SLA on paid plans |
| **Deployment** | Same render.yaml workflow; add `plan: starter` |
| **Env vars** | Same Render dashboard env var mechanism |
| **Logs** | Log stream + persistent log retention |
| **Region** | US-West (Oregon) or US-East (Ohio) or EU-West (Frankfurt) |
| **Rollback** | Manual redeploy to previous commit via Render dashboard |
| **Estimated cost** | ~$7–$15/month (service + disk) |

**Migration from Free to Starter:**  
1. Create new Render service: `machiningpro-ai-pilot`  
2. Set `plan: starter` in a pilot-specific render.yaml or in the dashboard  
3. Add persistent disk (1 GB minimum recommended)  
4. Set separate env vars: new `MACHININGPRO_PILOT_JWT_SECRET`, individual pilot credentials  
5. Do NOT copy demo credentials  
6. Update CORS_ORIGINS to pilot URL  
7. Verify health/readiness endpoints respond without cold-start  
8. Run smoke tests from PILOT_READINESS_CHECKLIST.md  

---

## Option B — Render Standard (Higher Traffic)

| Property | Value |
|---|---|
| **Plan** | Standard (approx. $25/month) |
| **Cold start** | NONE |
| **Persistent disk** | Available |
| **Auto-scaling** | Yes (up to configured instances) |
| **Estimated cost** | ~$25–$35/month |

Recommended only if pilot involves more than ~10 concurrent users or high upload frequency.

---

## Option C — Railway (Alternative PaaS)

| Property | Value |
|---|---|
| **Plan** | Hobby/Pro (usage-based, approx. $5–$20/month) |
| **Cold start** | None on paid |
| **Persistent volumes** | Available |
| **Deployment** | Dockerfile or Nixpacks auto-detect |
| **Env vars** | Dashboard + CLI |
| **Logs** | Log stream |
| **Estimated cost** | ~$5–$20/month depending on usage |

Railway is a viable alternative if the team has existing familiarity with it.

---

## Option D — Fly.io

| Property | Value |
|---|---|
| **Plan** | Pay-as-you-go (approx. $3–$15/month for a small VM) |
| **Cold start** | None with auto-stop disabled |
| **Persistent volumes** | Available |
| **Deployment** | Dockerfile + flyctl CLI |
| **Env vars** | flyctl secrets set |
| **Region** | Multiple global regions |
| **Estimated cost** | ~$3–$15/month |

Fly.io requires Dockerfile and flyctl familiarity. Good for multi-region if needed.

---

## Recommendation

**Render Starter** (Option A) is the lowest-friction path:
- Same codebase, same render.yaml mechanism
- Simply change `plan: free` → `plan: starter` in a pilot service
- Persistent disk available
- No new tooling required

Create a **separate** Render service (`machiningpro-ai-pilot`) rather than
upgrading the demo service, to maintain demo/pilot isolation.

---

## Decision Record

```
DECISION         : PENDING
RECOMMENDED      : Render Starter — machiningpro-ai-pilot
ESTIMATED_COST   : ~$7–$15/month
BLOCKER          : Non-demo credentials must be provisioned before go-live
AUTHORIZED_BY    : (pending)
TARGET_DATE      : (pending)
```
