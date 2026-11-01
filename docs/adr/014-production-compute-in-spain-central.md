# ADR-014: Production compute in Spain Central, data in Sweden Central

Status: accepted (phase 7, recorded 2026-11-01)

## Context

Each environment has its own Container Apps environment (SE:04, ADR-009). When production was prepared, the subscription's `Microsoft.App` usages allowed one managed environment in `swedencentral` (`ManagedEnvironmentCount`), and `cae-elevant-stg-swc` uses it. In `spaincentral` the limit is 5, none in use on 2026-11-01; Folium will take two of them. The owner decided to keep production on schedule rather than wait for a quota increase.

## Decision

Production's Container Apps environment and app run in **Spain Central**: `cae-elevant-prod-spc` and `ca-elevant-prod`, both in `rg-elevant-prod-swc` (a group's location is only where its metadata lives). The environment name keeps the convention `cae-<workload>-<env>-<region>` with `spc`, the code Folium uses for Spain Central, so the name does not claim Sweden. Everything else of production stays in **Sweden Central**: Cosmos DB, storage, Key Vault, Log Analytics and Application Insights, the identity, and the shared registry and Foundry account. `infra/main.bicep` takes `appLocation` (default: the group's location) and `main.production.bicepparam` sets `spaincentral`; staging keeps everything in Sweden Central.

## Consequences

- **Latency.** Every dependency call of production crosses Spain Central to Sweden Central: 50 ms P50 round trip (Learn, *Azure network round-trip latency statistics*, 30 days to 2026-07-30). A draft makes on the order of twenty such calls (checkpoints, the quote, the blob, Document Intelligence and its polling, the model), about 1 s against the 45 s SLO, where the matcher's 12 to 19 s dominates. This is an estimate: prompt 04 measures `quote_drafted` p95 in production.
- **Egress.** Inter-region transfer is billed at €0.0176 per GB (Retail Prices API, `spaincentral`, *Standard Inter-Region Data Transfer*, 2026-11-01). A quote moves a few MB across (the PDF, the layout, the document, telemetry): under €0.03 a month at 300 quotes. A cold start may pull the 89 MB image from the registry in Sweden Central, €0.0016 a pull: under €0.70 a month even at 20 cold starts a business day.
- **Staging is not production's twin in region.** Staging's load tests and cold starts run next to their dependencies, so they understate production's draft latency by the cross-region calls and its cold start by the cross-region image pull. The release smoke test and prompt 04's live run measure production itself.
- **Data residency is unchanged.** Data at rest stays in Sweden Central; production processes reports in memory in Spain Central. Both are in the EU, so the data table of `PRODUCT.md` holds.
- **Logs.** The production environment's diagnostic setting sends container logs to its workspace in Sweden Central; a Log Analytics destination may be in another region.
- **Resilience.** Still no failover (ADR-012): an outage of either region stops production.
- **Container Apps prices.** The Retail Prices API lists the same Consumption meters for both regions on 2026-11-01, requests at €0.352 per million in both.

## Alternatives considered

- **A quota increase in `swedencentral`**: free, but a support request with no date. It remains the way back, but not in place: a container app cannot change its location or environment, so it means deleting `ca-elevant-prod` and `cae-elevant-prod-spc`, setting `appLocation` to `swedencentral`, releasing with no `blue` revision to keep, and running `03-auth-redirect.sh production` again for the new address.
- **One environment shared by staging and production**: breaks the per-environment separation (SE:04) and makes staging's changes reach production's platform.
- **All of production in Spain Central**: the data would sit next to the app, but Foundry and the registry stay in Sweden Central, the groups are already created for Sweden, and the owner decided to keep the data there.
