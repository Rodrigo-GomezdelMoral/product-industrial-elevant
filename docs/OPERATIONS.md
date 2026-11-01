# Operations

Written in phase 6 and completed in phase 7 with what staging measured (cold start, load tests, SLOs, the rollback drill, Advisor
and cost to date); prompt 04 adds the restore drill and repeats the measurements in production.

## Environments

| | Staging | Production |
|---|---|---|
| Group | `rg-elevant-stg-swc` | `rg-elevant-prod-swc` |
| Region | Sweden Central | the Container Apps environment `cae-elevant-prod-spc` and the app in Spain Central; data, identity and monitoring in Sweden Central (ADR-014) |
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
- **Drill on staging** (2026-10-31): `deploy.yml` dispatched with the tag `20261031-main-3fd4c18` resolved the tag to its digest, ran
  `what-if`, deployed a new revision and passed the smoke gate (`/api/version` returned the digest) in 2 min 27 s, after waiting its
  turn behind the load test. It was the only image of `main` then, so the drill redeployed the same digest; prompt 04 rolls back
  between two different images.
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

Results, run of 2026-10-31 on the image `20261031-main-3fd4c18` (Locust p95 is the client's time from upload to draft ready):

| Scenario | Requests · failures | Draft p95 (max) | List p95 | Rate | Verdict |
|---|---|---|---|---|---|
| Normal | 199 · 0 | 0.59 s (4.2 s) | 0.32 s | 1.1/s | meets the SLA |
| Peak | 805 · 0 | 0.98 s (5.1 s) | 0.34 s | 4.5/s | meets the SLA; the slowest drafts are the first ones on a new replica |
| Stress | 3,508 · 0 | 1.0 s (1.8 s) | 0.45 s | 11.7/s | no breaking point at 100 users: 3 replicas (the maximum), at most 0.44 vCPU and 434 MB a replica, no `429` or `503` |
| Soak | 1,392 · 0 | 0.45 s (0.65 s) | 0.25 s | 1.2/s | meets the SLA; no drift, lower than normal |
| Real model | 13 · 0 | 18 s (18.4 s) | 0.62 s | 0.1/s | meets the SLA and the SLO: 7 drafts, 15.2 to 18.5 s on the server |

The doubles answer in milliseconds, so the first four scenarios measure the app, Cosmos DB and the platform; the real-model scenario
measures Document Intelligence and `gpt-5-mini`. One real draft used 3,296 input and 1,387 output tokens, €0.0032 of model cost,
as `docs/cost.md` estimates.

**Cold start** (2026-11-01, `/healthz` from zero replicas): 24.1 s and 27.8 s; warm, 0.2 to 0.3 s. In the web the page and the
sign-in wake the replica before the upload. The worst case, an upload from a page left open past the 5-minute scale-in, adds a start
to the slowest real draft, estimated at 46 s (not measured end to end), about 1 s over the 45 s SLO and under the 60 s SLA; the `quote_drafted` duration starts when the app
receives the upload, so the SLI does not show it. Accepted trade-off, no cron replica (ADR-008); production pulls the image across regions (ADR-014), so prompt 04 measures its cold start
again.

**SLOs measured** with the workbook's queries on staging's telemetry (2026-11-01): the health model shows the draft flow healthy (4,478
drafts, p95 0.7 s with the doubles, no failure) and the issue flow without traffic; draft p95 with the real model 18.5 s against the
45 s SLO; failed drafts 0 %; no `5xx` among the requests recorded. The availability SLI counts business hours only and the run was
on a Saturday night, so its tile is empty until weekday traffic. The SLO alert's query, run on the same data, returns no breach.

The Azure Monitor distro samples traces at 5 a second by default, so under load the `requests` and dependency tables are a sample
(2,380 of 5,917 requests recorded); KPI events are logs and arrived complete (4,478). At Elevant's volume, a few requests a minute,
nothing is sampled.

## Live walk-through

2026-11-01, 09:49 to 09:51 UTC, staging, the owner signed in with `Quote.Estimator` and `Quote.Manager`: `04-staging-walkthrough.sh`
runs `web/tests/live.spec.ts` in a headed Chromium and it passed. Every Must was shown on the deployed service:

| Step | Must | Outcome |
|---|---|---|
| Signed in | | the empty chat with its three starters; the signed-in name is masked |
| A JSON file | REQ-01 | refused, "the file is not a PDF", listed as Failed |
| The sample scanned report | REQ-01, REQ-02 | LFT-25448: 20 lines priced from the catalogue, 5 flagged, total €3,427.69 (stored from the first run, so no new draft) |
| `report-0106.pdf` | REQ-01, REQ-02, REQ-05 | a fresh draft: Lift ID flagged missing, 13 lines, 1 flagged, total €3,502.83 |
| Flags resolved | REQ-03 | Lift ID set to ELV-0106, the unmatched line removed, Approve enabled ("Every flag is resolved") |
| Correction in plain words | REQ-03 | "line 1, 1 units" proposed "Line 1: quantity 1"; confirmed, the quantity changed |
| Rating and approval | REQ-03 | "Good draft" recorded; approved, read-only, total €3,431.44, catalogue and template hashes, 4 recorded changes; the approver is masked |
| Word download | REQ-04 | `live-quote.docx` holds ELV-0106, its lines and the totals €2,835.90, €595.54 VAT, €3,431.44 |

KPI events in `AppEvents` from 09:00 UTC (both runs; the first, at 09:34, was the same flow): `quote_drafted` 3, `line_reviewed`
26, `feedback` 2, `quote_approved` 2, `quote_failed` 0. The two runs cost about €0.20 (three drafts and two corrections), and staging
was back at zero replicas at 09:59:53 UTC. The screenshots stay local in the gitignored `web/test-results/staging/`, checked for
names and identifiers, and are not committed.

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

- Cost per environment: [cost.md](cost.md), with the cost to date from Cost Management.
- DORA metrics, read on 2026-11-01 with `gh run list --workflow deploy.yml --json event,status,conclusion,createdAt,updatedAt,headSha`
  and `gh pr list --state merged --json number,createdAt,mergedAt`. Production has no deployment until v1.0.0, so these are
  staging's figures, and prompt 04 adds production's:

  | Metric | Value | How |
  |---|---|---|
  | Deployment frequency | 3 staging deployments in 2 days (2 merges, 1 redeploy by tag) | `deploy.yml` runs, `push` and `workflow_dispatch` |
  | Lead time for changes | 7 min 28 s and 3 min 8 s from merge to staging serving the new digest | merge time of PRs #9 and #12 to the end of their `deploy.yml` run |
  | Change failure rate | 0 % (0 of 3) | `deploy.yml` runs that failed their smoke gate or needed a rollback |
  | Time to restore | no failure to restore; the rollback drill redeployed an earlier tag and passed the smoke gate in 2 min 27 s | phase 7 drill |
- Azure Advisor (`az advisor recommendation list`, free) at the close of every phase that deploys. 2026-11-01: staging has one,
  *Enable zone redundancy for the managed environment* (high availability), not applied: it needs a virtual network and a new
  environment, and pays off only with replicas always running in two zones (ADR-012). Production has none (its group holds only the identity; nothing else is deployed).

## Model lifecycle

`gpt-5-mini` `2025-08-07` retires on **2027-02-09** and the shared deployment uses `NoAutoUpgrade`. When a replacement is named (90 to
120 days before), deploy it in the shared base (candidate today: `gpt-5.4-mini` `2026-03-17`, retiring 2027-09-21, if the subscription
has quota), point `ELEVANT_MODEL` at it on a branch, pass the evaluation gate against the baseline and release a minor version
(ADR-013).
