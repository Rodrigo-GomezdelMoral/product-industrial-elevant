# Operations

Written in phase 6 and completed in phase 7 with what staging measured (cold start, load tests, SLOs, the rollback drill, Advisor
and cost to date); prompt 04 adds the restore drill and repeats the measurements in production.

## Environments

| | Staging | Production |
|---|---|---|
| Group | `rg-elevant-stg-swc` | `rg-elevant-prod-swc` |
| Region | apps in Spain Central, data in Sweden Central (ADR-017) | the same |
| Container Apps environment | `cae-elevant-env`, shared, owned by production (ADR-016) | `cae-elevant-env`, declared in `rg-elevant-prod-swc` |
| App | `ca-elevant-stg`, single revision, 0 to 3 replicas | `ca-elevant-prod`, multiple revisions with labels `green` and `blue`, 0 to 5 replicas |
| Changed by | `deploy.yml` on every merge to `main` | `release.yml` on a published release, after the owner's approval |
| Data | 30 days | 730 days |
| Alerts | none; budget €5 | SLO alert to the owner; budget €20 |
| Human data access | the operator (export of recorded runs) | none |

Everything is defined in `infra/` and applied only by the workflows, each preceded by `what-if`.

## Promotion

1. A pull request runs `ci.yml` (lint, types, tests, budget, web walk-through with axe, Bicep build and lint, the image build) and,
   `eval.yml`, which evaluates when the change touches prompts, agents, the workflow, the domain rules, reference data or `eval/`.
   `protect-main` requires the `ci.yml` jobs, the `changes` and `eval` checks and CodeQL before a merge (from v1.0.1).
2. The merge runs `deploy.yml`: one image, tagged `YYYYMMDD-main-<sha7>`, pushed to the shared registry, `what-if`, deployed to staging
   by digest, smoke-tested (`/healthz`, then `/api/version` must return that digest).
3. `load-test.yml` (manual, from `main`) checks that staging serves the image of the dispatched commit, switches staging to the
   doubles, runs the four scenarios, removes the doubles and runs the real-model scenario. It fails when a scenario other than stress
   misses the SLA (p95 of a draft over 60 s, or more than 0.5 % failed requests).
4. A release `vX.Y.Z` runs `release.yml`: it checks that the tag's commit has a successful merge deployment and a successful load test,
   the load test being waived only when every path changed since the previous release that reached production (a successful `release.yml` run) is under `web/`, `docs/` or
   `.github/`, or is Markdown (ADR-015: the load test measures the API, which those paths do not change at runtime); the job log
   lists the paths and the decision. It then waits for approval, deploys the same digest as a new revision at 0 % labelled `green`, smoke-tests it through the label address and
   then moves 100 % to it. The previous revision stays active at 0 % as `blue`; older ones are deactivated.

## Rollback

- **Production, emergency:** `az containerapp ingress traffic set -n ca-elevant-prod -g rg-elevant-prod-swc --label-weight blue=100 green=0`.
  Seconds, no build. It works from the second release on: v1.0.0 was the first and had no `blue` (checked 2026-11-01). Since v1.0.1
  production keeps the previous release on `blue` at 0 %; on 2026-11-02 after v1.0.2, `green` is v1.0.2 at 100 % and `blue` is v1.0.1.
  v1.0.3 moved both apps to the shared environment `cae-elevant-env` (ADR-016), so `08-environment.sh production` deleted
  `ca-elevant-prod` and the release recreated it with one revision and only `green`: between v1.0.3 and v1.0.4 there was no label
  rollback and recovery was a fix-forward patch release. **Available again since v1.0.4:** after its release (2026-11-06, 12:48 UTC)
  `green` is v1.0.4 at 100 % and `blue` is v1.0.3 at 0 %, and production serves the digest staging serves. The last drill is the one
  of 2026-11-02 below; it was not repeated, to leave production unchanged. The planned path below cannot go back past v1.0.3:
  `release.yml` deploys the tag's own Bicep, and v1.0.2 or earlier declares the two old environments.
- **Production, planned:** run `release.yml` (`workflow_dispatch`) with the previous tag. It promotes that tag's image through the same
  smoke gate.
- **Staging:** run `deploy.yml` (`workflow_dispatch`) with the previous image tag; it deploys `main`'s Bicep, so any earlier image works.
- **Environment change (ADR-016, ADR-017, once):** `08-environment.sh staging` replaces staging's environment with `cae-elevant-env`, in Spain Central,
  before the merge, which redeploys staging; the load test runs (an infrastructure change is not exempt, ADR-015). When the v1.0.3
  release run waits for approval, `08-environment.sh production` deletes `ca-elevant-prod`, the approval recreates it, and the old
  environment is deleted meanwhile: production is down about 5 to 10 minutes. `03-auth-redirect.sh staging` and `production` then
  keep only each app's current callback. After any rebuild of production's group, run `08-environment.sh staging` again before
  staging deploys: the staging CI principal's role on the environment is not in Bicep.
- **Drill on staging** (2026-10-31): `deploy.yml` dispatched with the tag `20261031-main-3fd4c18` resolved the tag to its digest, ran
  `what-if`, deployed a new revision and passed the smoke gate (`/api/version` returned the digest) in 2 min 27 s, after waiting its
  turn behind the load test. It was the only image of `main` then, so the drill redeployed the same digest.
- **Drill between two images, staging, planned** (v1.0.1 validation): `deploy.yml` dispatched with an earlier tag of a different digest,
  `/api/version` checked, then the current tag redeployed. Result (2026-11-02, UTC): v1.0.0's tag dispatched at 10:41:50, the run
  succeeded in 155 s and `/api/version` returned v1.0.0's digest at 10:44:33, **166 s from dispatch**; v1.0.1's tag dispatched at
  10:45:05, run 168 s, v1.0.1's digest served at 10:48:05, **182 s from dispatch**.
- **Drill in production, emergency** (after v1.0.1): `blue=100 green=0`, `/api/version` returns v1.0.0's digest, then `green=100 blue=0`
  and v1.0.1's digest. Result (2026-11-02, UTC): `blue=100` at 10:49:31, command 18 s, v1.0.0's digest served at 10:50:22, **50 s in
  all** (the `blue` revision was at 0 replicas, so this includes its cold start; three further requests, all v1.0.0); `green=100` at
  10:50:22, command 17 s, v1.0.1's digest served at 10:50:40, **18 s in all** (five further requests, all v1.0.1). No deployment and no
  `release.yml` run; production ended on `green` 100 %.
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

Results of v1.0.4's release commit, 2026-11-06, 11:39 to 12:13 UTC, on the image of `96fb763` that staging served and v1.0.4
promoted (run 42211816475, from its `load-test-results` artifact; Locust's percentiles are approximated to two figures; n is the
number of drafts, and a draft's time is the client's time from upload to draft ready):

| Scenario | Drafts · failures | Draft p50 | Draft p95 | Draft p99 | Requests/s | Verdict |
|---|---|---|---|---|---|---|
| Normal | 127 · 0 | 0.74 s | 1.2 s | 15 s (max 16.3 s) | 0.99 | meets the SLA |
| Peak | 574 · 0 | 0.76 s | 1.1 s | 1.9 s | 4.3 | meets the SLA |
| Stress | 2,459 · 0 (3,262 requests) | 0.83 s | 1.3 s | 1.6 s | 10.9 | no breaking point at 100 users: 3 replicas (the maximum), at most 0.41 vCPU and 440 MB a replica |
| Soak | 937 · 0 | 0.74 s | 0.91 s | 1.0 s | 1.1 | meets the SLA; no drift |
| Real model | 10 · 0 | 18 s | 20 s | 20 s | 0.11 | meets the SLA and the SLO |

5,499 requests in all, none failed. Normal's p99 comes from its first four drafts, 12.7 to 15.3 s at 11:40 UTC on the revision
that the switch to the doubles had just started (staging's `requests`, read on 2026-11-10); the rest stayed under 2 s. Replicas
(`Replicas`, maximum per minute, read on 2026-11-10): 1 until 11:43, 2 at 11:44, 3 from 11:45 to 11:59, 2 until 12:04 and 1 from
12:05 UTC.

Earlier run on a release commit, 2026-11-01, 12:13 to 12:48 UTC, on the image `20261101-main-aaab8e4` that v1.0.0 promoted
(recomputed from the run's `load-test-results` artifact; n is the number of drafts; p95 is the client's time from upload to draft ready):

| Scenario | Drafts · failures | Draft p95 | Verdict |
|---|---|---|---|
| Normal | 164 · 0 | 0.91 s | meets the SLA |
| Peak | 625 · 0 | 1.1 s | meets the SLA |
| Stress | 2,619 · 0 (3,416 requests) | 1.4 s | no breaking point at 100 users: 3 replicas (the maximum), at most 0.49 vCPU and 500 MB a replica |
| Soak | 1,056 · 0 | 0.51 s | meets the SLA; no drift |
| Real model | 9 · 0 | 17 s (max 17.1 s) | meets the SLA and the SLO |

Earlier run, 2026-10-31, on the image `20261031-main-3fd4c18`:

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

**Cold start** (2026-11-01, `/healthz` from zero replicas): staging 24.1 s and 27.8 s; production 27.9 s (n = 1, after the
release); warm, 0.2 to 0.3 s. In the web the page and the
sign-in wake the replica before the upload. The worst case, an upload from a page left open past the 5-minute scale-in, adds a start
to the slowest real draft, estimated at 46 s (not measured end to end), about 1 s over the 45 s SLO and under the 60 s SLA; the `quote_drafted` duration starts when the app
receives the upload, so the SLI does not show it. Accepted trade-off, no cron replica (ADR-008); production's one measurement, taken while it ran in Spain Central (ADR-014), is within staging's range; since ADR-017 both apps run there, away from their registry and data.

**SLOs measured** with the workbook's queries on staging's telemetry (2026-11-01): the health model shows the draft flow healthy (4,478
drafts, p95 0.7 s with the doubles, no failure) and the issue flow without traffic; drafts with the real model, all of staging's to
2026-11-01 (n = 20): 11.9 to 24.5 s, p50 15.7 s, p95 23.2 s against the 45 s SLO; failed drafts 0 % (0 of 8,986 drafts to 2026-11-01, load tests included); no `5xx` among the requests recorded. The availability SLI counts business hours only and the run was
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

### Production walk-through

`06-production-walkthrough.sh` runs the same test against production after v1.0.1, with the screenshots in the gitignored
`web/test-results/production/`; the owner then deletes one quote as manager (REQ-10) and keeps one approved quote for the recordings.
2026-11-02, 17:40 to 17:41 UTC, v1.0.1, the owner signed in with `Quote.Estimator` and `Quote.Manager`: the test passed and every Must
was shown on production:

| Step | Must | Outcome |
|---|---|---|
| Signed in | | the empty chat with its three starters; the signed-in name is masked |
| A JSON file | REQ-01 | refused, listed as Failed |
| The sample scanned report | REQ-01, REQ-02, REQ-05 | a fresh draft: LFT-25448, 20 lines priced from the catalogue, 5 flagged, total €3,427.69, in 48.9 s |
| `report-0106.pdf` | REQ-01, REQ-02, REQ-05 | a fresh draft in 17.6 s: Lift ID flagged missing, 13 lines, 1 flagged, total €3,502.83 |
| Flags resolved, correction, rating, approval | REQ-03, REQ-08, REQ-09 | Lift ID set to ELV-0106, a correction in plain words proposed and confirmed, 👍 recorded; approved and read-only: 13 lines reviewed (11 accepted, 1 changed, 1 removed), €2,835.90 + €595.54 VAT = €3,431.44, catalogue and template hashes, 4 recorded changes |
| Word download | REQ-04 | the `.docx` of the approved quote downloaded |
| Deletion as manager | REQ-10 | the LFT-25448 quote deleted in the web at 18:38 UTC; ELV-0106 kept, approved, for the recordings |

KPI events in production's `AppEvents` (all of production's history, 2026-11-01 to 2026-11-02): `quote_drafted` 2, `line_reviewed`
13 (11 accepted, 1 changed, 1 removed), `feedback` 1 (up), `quote_approved` 1 (`elapsed_s` 24), `quote_deleted` 1 at 18:38:03 UTC,
`quote_failed` 0. An earlier delete by mistake went to staging at 18:11 UTC, not to production. The screenshots stay local in the
gitignored `web/test-results/production/` and are not committed.

Production SLIs and KPIs read on 2026-11-02 at about 19:30 UTC, window 30 days (production's whole life), one walk-through, so these
are test values, not business figures:

| Measure | Value | n | Target |
|---|---|---|---|
| Availability in business hours (no probe, no 4xx) | 100 % | 40 requests (47 in all hours, 0 `5xx`) | SLO 99.7 %, SLA 99.5 % over a calendar month: not yet measurable |
| Draft p95 | 48.9 s | 2 drafts (48.9 s and 17.6 s) | SLO 45 s, SLA 60 s; the alert needs at least 3 drafts in its hour, so it did not fire |
| Failed drafts | 0 % | 2 | < 1 % |
| KPI-1 turnaround | 24 s | 1 approval | ≤ 15 min (an automated walk-through, not office time) |
| KPI-2 lines accepted unchanged | 84.6 % | 13 lines | ≥ 85 % |
| KPI-3 positive feedback | 100 % | 1 rating | ≥ 80 % |

The 48.9 s draft is the 20-line scanned report on a cold path; it is above the SLO and inside the SLA. Two drafts do not make a p95;
the SLO is read again once production has real use.

Read again after the recording with v1.0.4, window 30 days to 2026-11-06: the SLO tiles of the production workbook that day, and
the KPI events in `AppEvents` on 2026-11-10, none after 2026-11-06 13:16 UTC. Synthetic use (the walk-through, the prepared scenario
and the recorded takes), so still test values:

| Measure | Value | n | Target |
|---|---|---|---|
| Availability in business hours (no probe, no 4xx) | 100 % | 185 requests, no server error | SLO 99.7 %, SLA 99.5 % over a calendar month: not yet measurable |
| Draft p95 | 48.9 s | 12 drafts | SLO 45 s, SLA 60 s |
| Failed drafts | 0 % | 12 | < 1 % |
| KPI-1 turnaround (median) | 30 s | 9 approvals | ≤ 15 min (walk-throughs and takes, not office time) |
| KPI-2 lines accepted unchanged | 78.4 % | 109 of 139 lines | ≥ 85 %, not met: choosing a candidate or removing an unmatched line counts as a change |
| KPI-3 positive feedback | 87.5 % | 7 of 8 ratings | ≥ 80 % |

## Alerts and incidents

The production SLO alert (`alert-elevant-slo-prod`) runs every 15 minutes over the last hour and mails the owner through
`ag-elevant-prod-swc`, one alert per breached SLO: availability in business hours under 99.7 % (with at least 20 requests), draft p95
over 45 s (with at least 3 drafts), or failed drafts at 1 % of the hour's drafts or more (at Elevant's
volume, a single failure).

**Alert drill** (v1.0.1 validation): a test notification from `ag-elevant-prod-swc`, confirmed by the owner, and a temporary copy of the
rule in staging with its own action group and a lowered latency threshold that real staging data breaches, both deleted afterwards.
Result (2026-11-02, UTC): the production test notification was requested at about 10:38:48 and Azure reported it complete at
10:41:59 (about 3 min 11 s); the staging copy (threshold 0.5 s instead of 45 s, frequency 5 min, window 1 day) was created at 10:41:10
and **fired at 10:46:02, 4 min 52 s later**. The owner confirmed both mails. The temporary rule and action group were deleted at
10:48:27 and none is left; the production rule is unchanged.

Incident procedure (OE:08, SE:12):
1. **Detect:** the alert mail, a budget mail, or a user report.
2. **Assess:** the workbook *Elevant: KPIs, SLOs and health (prod)*. The health model shows the draft flow (extract, match, price) and
   the issue flow (review, render, download) as healthy, degraded or unhealthy over the last hour.
3. **Mitigate:** if a release caused it, roll back with the `blue` label. For a model `429`, check the shared deployment's usage and
   lower the load or wait. For a dependency outage, the app answers a clear `503` and drafts can be retried.
4. **Communicate:** tell the estimators what is affected and when to retry.
5. **Review:** a short note in the repository with the timeline, the cause and the fix, and a hotfix if code changed.

**Hotfix path** (pre-approved, OE:11): a `hotfix/<what>` branch and a pull request with `ci.yml` and `eval.yml` (which evaluates if it touches
prompts or agents), the merge, staging, then a patch release. The load test is required unless every changed path is web, docs, Markdown or
workflows (ADR-015); `release.yml` decides it from the diff against the previous release, not from the release notes.

## Starting and stopping

Everything scales to zero when idle. To stop serving production without deleting anything, deactivate its active revisions
(`az containerapp revision deactivate`); to stop deployments, prompt 06 pauses the workflows; to stop the only fixed charge, disable the
SLO alert rule. Staging ends every phase at zero replicas.

## Backup and restore

Cosmos DB has continuous backup for 7 days (RPO about 100 s for mutations); blobs have soft delete for 7 days. Recovery is cold: Bicep
rebuilds the group, Cosmos DB restores to a point in time into a new account, and the app is pointed at it (RTO target 4 h). A quote
deleted on request disappears from both backups within 7 days (REQ-10).

Restore drill, staging only: a point-in-time restore of `cosmos-elevant-stg-swc` into a new account, timed to `Succeeded`, its data
checked, a soft-deleted report blob recovered, the restored account deleted. Result (2026-11-02, UTC): restore point 10:27:00, after
the last known write at 10:24:51; the restore with TTL disabled ran from 10:54:58 to `Succeeded` at 11:04:41, **583 s** for about
322 MB. Item counts in Azure Monitor equal the source (`quotes` 13,389, `checkpoints` 66,975); no data-plane read, because data-plane
role assignments are not restored and none was granted. **RTO 767 s, about 13 min, against 4 h** (restore 583 s plus a 184 s
`deploy.yml` run), not counting the identity script that points the app at a restored account and grants its data role, which a real
recovery adds. **RPO ≤ 100 s against 5 min** (the restore held the last write; continuous backup granularity 100 s). A soft-deleted
report blob was undeleted in 8 s with the same size and MD5. The restored account was deleted (741 s) and nothing is left. Production is not rehearsed on purpose: no human holds a data-plane role there (only
the app's identity), so a restore check would need a temporary grant that the design avoids; the backup policy and the procedure are
the same in both environments, and the staging drill stands for both.

## Cost, DORA and Advisor

- Cost per environment: [cost.md](cost.md), with the cost to date from Cost Management.
- DORA metrics, read on 2026-11-10 with `gh run list --workflow deploy.yml --json event,status,conclusion,createdAt,updatedAt,headSha`
  (`--workflow release.yml` for production) and `gh pr list --state merged --json number,createdAt,mergedAt`; the earlier readings, of
  2026-11-01 and 2026-11-02, covered up to v1.0.2. Staging, 2026-10-31 to 2026-11-03:

  | Metric | Value | How |
  |---|---|---|
  | Deployment frequency | 13 staging deployments in 4 days (10 merges, 3 redeploys by tag), 12 successful | `deploy.yml` runs, `push` and `workflow_dispatch` |
  | Lead time for changes | 3 min 4 s to 9 min 19 s from merge to staging serving the new digest, median 3 min 19 s (n = 9) | merge time of PRs #9, #12 to #16 and #18 to #20 to the end of their `deploy.yml` run |
  | Change failure rate | 8 % (1 of 13): PR #17's run (2026-11-02, 20:32 UTC) stopped in its deployment step with `LinkedAuthorizationFailed`, because the shared environment needed a role the staging CI principal did not hold yet; the smoke gate did not run | `deploy.yml` runs that failed their deployment or smoke gate, or needed a rollback |
  | Time to restore | 11 h 55 min, overnight, until PR #18 (the environment in Spain Central, ADR-017) deployed at 08:30 UTC; the rollback drill redeployed an earlier tag and passed the smoke gate in 2 min 27 s | `deploy.yml` runs; phase 7 drill |

  Production, v1.0.0 to v1.0.4 (2026-11-01 to 2026-11-06):

  | Metric | Value | How |
  |---|---|---|
  | Deployment frequency | 5 production deployments in 6 days (v1.0.0 to v1.0.4) | `release.yml` runs |
  | Lead time for changes | v1.0.0: 5 h 28 min from the merge of PR #13, gated by the load test and the approval; v1.0.1: 46 min 27 s from the merge of PR #14; v1.0.2: 7 min 4 s from the merge of PR #15, a web and docs release without a load test (ADR-015); v1.0.3: 53 min 29 s from the merge of PR #19, through the load test, the approval and the environment change; v1.0.4: 3 days 2 h 14 min from the merge of PR #20, held for the recording, where it was load tested, released and approved | merge time to the end of the promoting `release.yml` run |
  | Change failure rate | 0 % (0 of 5): no release was rolled back or fixed. Two attempts failed before their revision existed: v1.0.0's attempt 1 stopped in `verify` because the commit had no load test yet; v1.0.3's attempt 1 stopped in `promote` with `ContainerAppEnvironmentMismatch`, the app still being in its old environment, and attempt 2 deployed it 4 min 46 s later, inside the planned environment change | `release.yml` attempts |
  | Time to restore | no failure to restore; the emergency rollback drill by label served the previous digest in 50 s and returned in 18 s (2026-11-02) | rollback drill |
- Azure Advisor (`az advisor recommendation list`, free) at the close of every phase that deploys. 2026-11-01: staging has one,
  *Enable zone redundancy for the managed environment* (high availability), not applied: it needs a virtual network and a new
  environment, and pays off only with replicas always running in two zones (ADR-012). By the release a second one had appeared,
  *Enable zone redundancy for storage accounts* (high), not applied: ZRS costs more than LRS and the design is single-region (ADR-012).
  Production, after the release (2026-11-01): none.

## Model lifecycle

`gpt-5-mini` `2025-08-07` retires on **2027-07-13** (Learn model retirement schedule, updated 2026-09-21, and the Models API's
`deprecation.inference`, read 2026-11-01; v1.0.0 said 2027-02-09, the date of `gpt-5` and `gpt-5-nano`) and the shared deployment uses `NoAutoUpgrade`. When a replacement is named (90 to
120 days before), deploy it in the shared base (candidate today: `gpt-5.4-mini` `2026-03-17`, retiring 2027-09-21, if the subscription
has quota), point `ELEVANT_MODEL` at it on a branch, pass the evaluation gate against the baseline and release a minor version
(ADR-013).
