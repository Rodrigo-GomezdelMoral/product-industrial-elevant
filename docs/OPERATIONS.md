# Operations

Draft written in phase 6, before anything is deployed. Phase 7 adds the measured results (cold start, load tests, SLOs, the rollback
drill, Advisor and cost to date); prompt 04 adds the restore drill.

## Environments

| | Staging | Production |
|---|---|---|
| Group | `rg-elevant-stg-swc` | `rg-elevant-prod-swc` |
| App | `ca-elevant-stg`, single revision, 0 to 3 replicas | `ca-elevant-prod`, multiple revisions with labels `green` and `blue`, 0 to 5 replicas |
| Changed by | `deploy.yml` on every merge to `main` | `release.yml` on a published release, after the owner's approval |
| Data | 30 days | 730 days |
| Alerts | none; budget €5 | SLO alert to the owner; budget €20 |
| Human data access | the operator (export of recorded runs) | none |

Everything is defined in `infra/` and applied only by the workflows, each preceded by `what-if`.

## Promotion

1. A pull request runs `ci.yml` (lint, types, tests, budget, web walk-through with axe, Bicep build and lint, the image build) and,
   when it touches prompts, agents, the workflow, reference data or `eval/`, `eval.yml`.
2. The merge runs `deploy.yml`: one image, tagged `YYYYMMDD-main-<sha7>`, pushed to the shared registry, `what-if`, deployed to staging
   by digest, smoke-tested (`/healthz`, then `/api/version` must return that digest).
3. `load-test.yml` (manual, from `main`) checks that staging serves the image of the dispatched commit, switches staging to the
   doubles, runs the four scenarios, removes the doubles and runs the real-model scenario. It fails when a scenario other than stress
   misses the SLA (p95 of a draft over 60 s, or more than 0.5 % failed requests).
4. A release `vX.Y.Z` runs `release.yml`: it checks that the tag's commit has a successful merge deployment and a successful load test,
   waits for approval, deploys the same digest as a new revision at 0 % labelled `green`, smoke-tests it through the label address and
   then moves 100 % to it. The previous revision stays active at 0 % as `blue`; older ones are deactivated.

## Rollback

- **Production, emergency:** `az containerapp ingress traffic set -n ca-elevant-prod -g rg-elevant-prod-swc --label-weight blue=100 green=0`.
  Seconds, no build.
- **Production, planned:** run `release.yml` (`workflow_dispatch`) with the previous tag. It promotes that tag's image through the same
  smoke gate.
- **Staging:** run `deploy.yml` (`workflow_dispatch`) with the previous image tag.
- **Workflow graph changes:** a changed graph cannot resume old checkpoints. Before releasing one, let the quotes in review be approved
  or deleted, and bump `VERSION` in `app/workflow.py` (ADR-004).

## Load tests

Locust (`load/locustfile.py`) signs in with a token of the staging CI principal, which holds `Quote.Estimator`. Each upload is
`report-0134.pdf` with a unique trailer, so the idempotent upload drafts every time. Results go to the run's summary and artifact.

| Scenario | Users · duration | Purpose |
|---|---|---|
| Normal | 5 · 3 min | the business-hours baseline |
| Peak | 20 · 3 min | a Monday-morning burst; replicas scale out at 10 concurrent requests each |
| Stress | ramp to 100 · 5 min | the breaking point and how it fails (clear `429`/`503`, no data loss); not held to the SLA |
| Soak | 5 · 20 min | memory and error drift |
| Real model | 3 · 2 min, doubles off | the real matcher's and Document Intelligence's latency; about ten quotes, under €0.30 |

Results: pending, phase 7.

## Alerts and incidents

The production SLO alert (`alert-elevant-slo-prod`) runs every 15 minutes over the last hour and mails the owner through
`ag-elevant-prod-swc`, one alert per breached SLO: availability in business hours under 99.7 % (with at least 20 requests), draft p95
over 45 s (with at least 3 drafts), or failed drafts at 1 % of the hour's drafts or more (at Elevant's
volume, a single failure).

Incident procedure (OE:08, SE:12):
1. **Detect:** the alert mail, a budget mail, or a user report.
2. **Assess:** the workbook *Elevant: KPIs, SLOs and health (prod)*. The health model shows the draft flow (extract, match, price) and
   the issue flow (review, render, download) as healthy, degraded or unhealthy over the last hour.
3. **Mitigate:** if a release caused it, roll back with the `blue` label. For a model `429`, check the shared deployment's usage and
   lower the load or wait. For a dependency outage, the app answers a clear `503` and drafts can be retried.
4. **Communicate:** tell the estimators what is affected and when to retry.
5. **Review:** a short note in the repository with the timeline, the cause and the fix, and a hotfix if code changed.

**Hotfix path** (pre-approved, OE:11): a `hotfix/<what>` branch and a pull request with `ci.yml` (and `eval.yml` if it touches prompts or
agents), the merge, staging, then a patch release. The load test may be skipped only for a hotfix that touches neither the request
path nor the infrastructure, and the release notes say so.

## Starting and stopping

Everything scales to zero when idle. To stop serving production without deleting anything, deactivate its active revisions
(`az containerapp revision deactivate`); to stop deployments, prompt 06 pauses the workflows; to stop the only fixed charge, disable the
SLO alert rule. Staging ends every phase at zero replicas.

## Backup and restore

Cosmos DB has continuous backup for 7 days (RPO about 100 s for mutations); blobs have soft delete for 7 days. Recovery is cold: Bicep
rebuilds the group, Cosmos DB restores to a point in time into a new account, and the app is pointed at it (RTO target 4 h). A quote
deleted on request disappears from both backups within 7 days (REQ-10). Restore drill: pending, prompt 04, with the owner's approval.

## Cost, DORA and Advisor

- Cost per environment: [cost.md](cost.md); measured cost to date: pending, phase 7.
- DORA metrics (deployment frequency, lead time, change failure rate, time to restore) from `gh run list --json`: pending, phase 8.
- Azure Advisor (`az advisor recommendation list`, free) at the close of every phase that deploys: pending, phase 7.

## Model lifecycle

`gpt-5-mini` `2025-08-07` retires on **2027-02-09** and the shared deployment uses `NoAutoUpgrade`. When a replacement is named (90 to
120 days before), deploy it in the shared base (candidate today: `gpt-5.4-mini` `2026-03-17`, retiring 2027-09-21, if the subscription
has quota), point `ELEVANT_MODEL` at it on a branch, pass the evaluation gate against the baseline and release a minor version
(ADR-013).
