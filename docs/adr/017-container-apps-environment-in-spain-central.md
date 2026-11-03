# ADR-017: The Container Apps environment and both apps in Spain Central

Status: accepted (decided by the owner on 2026-11-03); supersedes the region of ADR-016, whose single shared environment holds

## Context

ADR-016 placed the one environment, `cae-elevant-env`, in Sweden Central. On 2026-11-03 `08-environment.sh staging` deleted `ca-elevant-stg` and `cae-elevant-stg-swc`, and the creation of `cae-elevant-env` in `swedencentral` then failed ARM preflight with `MaxNumberOfGlobalEnvironmentsInSubExceeded` (*cannot have more than 1 Container App Environments*), although the `Microsoft.App` usages API read `ManagedEnvironmentCount` 0 of 1 in `swedencentral`. The subscription held 4 environments. Validating `infra/modules/environment.bicep` alone with concrete values succeeded in `spaincentral` (usage 1 of 2, held by `cae-elevant-prod-spc`) and in `northeurope` (0 of 2). The usages API and preflight disagree on Sweden Central, and neither Learn nor the quotas page explains the difference; a support request has no date.

Production already runs its app in Spain Central against its data in Sweden Central (ADR-014), so the cross-region path is measured and accepted.

## Decision

`cae-elevant-env` and both apps, `ca-elevant-stg` and `ca-elevant-prod`, run in **Spain Central**. `infra/main.bicep` takes `appLocation` (default: the group's location), both `.bicepparam` files set `spaincentral`, and only the environment module and the app module receive it. Everything else stays in **Sweden Central** and in its current group: Cosmos DB, storage, Key Vault, Log Analytics, Application Insights, the workbook, the SLO alert, the identities, and the shared registry and Foundry account. Resource groups and names do not change: `cae-elevant-env` has no region suffix, and the groups keep `-swc`, since a group's location is only where its metadata lives. The rest of ADR-016 holds: one environment declared by production in `rg-elevant-prod-swc`, staging joining it as `existing` with the join role, and `08-environment.sh` in two modes, now with `LOCATION=spaincentral` and a check that the production group is still in Sweden Central.

Nothing else had to move with the environment. An app must be in its environment's region, so both take `appLocation`; Easy Auth (`authConfigs`) is a child of the app. There is no virtual network, subnet, custom domain or managed certificate (ADR-012). The diagnostic setting may send logs to a workspace in another region, as production's did since ADR-014. User-assigned identities and the registry work across regions. The workbook and the SLO alert query Application Insights and filter by request, event and time, never by region.

## Consequences

- **Ceded: one region.** ADR-016's "one region again" no longer holds for either environment. Every dependency call crosses Spain Central to Sweden Central: 50 ms P50 round trip (Learn, *Azure network round-trip latency statistics*, as read for ADR-014), about 1 s per draft against the 45 s SLO, where the matcher's 12 to 19 s dominates.
- **Staging measures production again.** Both apps share the topology, so staging's load tests and cold starts include the cross-region calls and image pull that ADR-014 left unmeasured in staging. Measurements taken in staging before v1.0.3 ran next to the data and understate the new path slightly.
- **Egress.** Inter-region transfer at €0.0176 per GB (Retail Prices API, `spaincentral`, 2026-11-01): a few MB a quote, under €0.03 a month at 300 quotes, and up to €0.0016 per cold-start pull of the 89 MB image, under €0.70 a month at 20 cold starts a business day; staging adds its load tests' traffic, cents a run.
- **Data residency is unchanged.** Data at rest stays in Sweden Central; reports are processed in memory in Spain Central; both are in the EU, so `PRODUCT.md`'s data table holds.
- **Resilience.** An outage of either region stops both environments; still no failover (ADR-012).
- **Quota.** Spain Central goes from 1 of 2 to 2 of 2 when `08-environment.sh staging` creates the environment, and back to 1 of 2 when `production` mode deletes `cae-elevant-prod-spc`; the subscription goes 4, 5, 4.
- **Way back.** If Sweden Central accepts an environment later, the move is ADR-016's again: delete both apps and the environment, set `appLocation` to `swedencentral`, redeploy, and run `03-auth-redirect.sh` for both apps' new addresses.

## Alternatives considered

- **North Europe** (0 of 2, validates): a third region in the path, with no measurement behind it.
- **A support request for Sweden Central**: no date, and v1.0.3 and staging wait for it.
- **Staging in its old environment**: already deleted, and it would bring back two environments against ADR-016.
