# MachiningPro AI — Environment Strategy

**Status:** DRAFT — Operational reference for pilot preparation  
**Last updated:** 2026-11-12  
**Applies to:** main branch @ edd73c4+

---

## Overview

Three environments are defined. Each has distinct hosting, authentication,
data retention, and access rules. They must never share credentials or
JWT signing secrets.

---

## DEMO Environment

| Property | Value |
|---|---|
| **Purpose** | Public reference / engineering showcase |
| **Hosted at** | machiningpro-ai-demo.onrender.com (Render Free) |
| **Hosting plan** | Render Free tier |
| **SLA** | NONE — ephemeral, cold-starts up to 30s, no uptime guarantee |
| **Auth mode** | Single shared demo account (`demo` / public credential in bundle) |
| **User type** | Unauthenticated public visitors; engineers evaluating the demo |
| **CAD data** | Synthetic/sample only; ephemeral; no customer CAD |
| **Data retention** | NONE — lost on restart/redeploy |
| **Logging** | Application logs via Render dashboard; no audit trail required |
| **Secrets handling** | JWT secret and credentials in Render env vars; public prefill in JS bundle |
| **Backup** | NONE — intentional; no persistent state |
| **Label** | Must display "DEMO / REFERENCE ONLY" in UI |

**Demo credentials are public by design** (`demo` / `A1234` prefilled in login).  
They must **never** be used for production pilot access.

---

## PILOT Environment

| Property | Value |
|---|---|
| **Purpose** | Controlled production pilot — real engineering evaluation with selected users |
| **Hosted at** | Separate deployment (see PILOT_HOSTING_OPTIONS.md) |
| **Hosting plan** | Always-on paid instance — no cold-start dependency |
| **SLA** | Minimum 99.5% uptime for pilot duration |
| **Auth mode** | Individual per-user credentials (see MULTI_USER_AUTH_EXTENSION_PLAN.md) |
| **User type** | Pilot engineers, reviewers, and pilot admins (see PILOT_USER_MODEL.md) |
| **CAD data** | Synthetic pilot fixtures; customer CAD only under explicit data policy |
| **Data retention** | Persistent disk or equivalent; documented retention period |
| **Logging** | Full audit log: login, upload, analysis, export, review actions |
| **Secrets handling** | Separate JWT secret; no shared demo secret; set in hosting env vars only |
| **Backup** | Regular automated backup of pilot artifacts and audit log |
| **Label** | "PILOT — CONTROLLED EVALUATION" |

**Pilot environment must not reuse any demo credential or JWT secret.**

### CAD Storage Policy

- Synthetic test fixtures: permitted, ephemeral
- Customer/OEM proprietary CAD: requires explicit written data handling policy before enabling
- No persistent customer CAD without explicit policy, legal review, and user consent

### Deployment Rollback

- Blue/green or previous-version deployment must be available
- Rollback procedure documented in PILOT_READINESS_CHECKLIST.md

---

## FUTURE_PRODUCTION Environment

| Property | Value |
|---|---|
| **Purpose** | Full production deployment to paying / contracted customers |
| **Hosting plan** | Dedicated infrastructure; regional redundancy as required |
| **SLA** | Per contractual terms |
| **Auth mode** | Full identity management system (OAuth2 / SSO / per-org accounts) |
| **User type** | Production customers, operators, admins |
| **CAD data** | Per-customer data isolation; full retention policy; legal compliance required |
| **Logging** | Full audit trail; tamper-evident; compliance-grade where required |
| **Secrets handling** | Secrets management service (Vault, AWS Secrets Manager, or equivalent) |
| **Backup** | Automated, tested, documented RTO/RPO |

**FUTURE_PRODUCTION is out of scope for the current pilot phase.**  
It requires a full identity management design, compliance review, and data handling agreement.

---

## Environment Separation Checklist

| Check | DEMO | PILOT | FUTURE_PRODUCTION |
|---|---|---|---|
| Separate JWT secret | shared public | required | required |
| Separate credentials | shared public | required | required |
| No cross-environment token reuse | N/A | REQUIRED | REQUIRED |
| Separate deployment URL | demo | pilot | production |
| CAD data isolation | ephemeral | controlled | full isolation |
| Audit logging | none | required | required |

---

## Current Status

```
DEMO_ENVIRONMENT_DEPLOYED   = YES  (machiningpro-ai-demo.onrender.com)
PILOT_ENVIRONMENT_DEPLOYED  = NO   (pending hosting selection and credential provisioning)
PRODUCTION_ENVIRONMENT       = NOT STARTED
```
