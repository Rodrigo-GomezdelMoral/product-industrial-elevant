# ADR-016: One Container Apps environment for staging and production

Status: accepted (decided by the owner on 2026-11-02); supersedes ADR-014. Its region is superseded by ADR-017 on 2026-11-03: the environment and both apps run in Spain Central, the rest of this record holds.

## Context

Each environment had its own Container Apps environment: `cae-elevant-stg-swc` in Sweden Central and, for quota, `cae-elevant-prod-spc` in Spain Central with its data in Sweden Central (ADR-014). Read on 2026-11-02, the subscription has two limits on managed environments:

- **5 per subscription.** ARM preflight of a bare `Microsoft.App/managedEnvironments` resource with concrete values, in a region with a free slot, answers *cannot have more than 5 Container App Environments* (`MaxNumberOfGlobalEnvironmentsInSubExceeded`). The subscription holds 5, two of them Elevant's. The usages API and the quotas page do not show this limit.
- **1 per region in Sweden Central.** The `Microsoft.App` usages API reports `ManagedEnvironmentCount` 1 of 1 in `swedencentral`, taken by `cae-elevant-stg-swc`; preflight of `cae-elevant-env` there answers `MaxNumberOfRegionalEnvironmentsInSubExceeded`. Other regions read a limit of 2 that day.

`az deployment group validate` and `what-if` of a template that passes runtime values to a module may not reach the provider's check, so the limits are verified by validating the environment module alone with concrete values.

## Decision

One environment for the product, **`cae-elevant-env`**, with no environment or region suffix, in **Sweden Central**, in the existing production group `rg-elevant-prod-swc`, tagged `environment: shared`. `infra/modules/environment.bicep` declares it with the properties the previous environments had: the `Consumption` workload profile, no zone redundancy, logs to Azure Monitor and the diagnostic setting `to-workspace` to production's workspace. Only the production deployment declares it; staging refers to it as `existing` in the production group and never writes it. Both apps keep their names and groups: `ca-elevant-stg` in `rg-elevant-stg-swc` and `ca-elevant-prod` in `rg-elevant-prod-swc`, both in Sweden Central. No new resource group.

The staging CI principal gets a custom role on the environment alone, *Elevant environment join*: `Microsoft.App/managedEnvironments/read` and `Microsoft.App/managedEnvironments/join/action`, enough to create its app in the environment and nothing else. `08-environment.sh` works in two modes, so that no step exceeds either limit and production keeps serving until its release. `staging`, before the merge, deletes `ca-elevant-stg` and `cae-elevant-stg-swc` (5 to 4 in the subscription, 0 of 1 in Sweden Central), creates `cae-elevant-env` from the same module (5, and 1 of 1) and grants that role. `production` runs once the v1.0.3 release run waits for its approval: the deployment recreates `ca-elevant-prod`, and an app cannot change its environment or region, so the script deletes the old app first, then `cae-elevant-prod-spc` (4) while the approved release deploys. The product then uses 1 of the subscription's 5 environments and leaves Spain Central.

## Consequences

- **Shared environment settings.** Staging and production share the environment's log destination (container and system logs of both apps reach production's workspace and its 0.5 GB daily cap; staging's data is test data), its network and default domain, its platform updates and its availability. Staging's container logs, the load test's included, count against production's daily cap, which production's Application Insights and SLO alert also use; the first load test after this change checks how much it ingests. The apps, identities, data, Easy Auth registrations, secrets, scale rules and revisions stay per environment, so a staging release still cannot reach production's data or sign-in.
- **Change control.** The environment changes only through `release.yml`, after approval, so staging does not rehearse an environment change first; the release's `what-if` shows it.
- **Removal and rebuild.** Deleting production's group deletes the environment and stops staging; removing staging deletes only its app and data. A cold rebuild (ADR-012) recreates the environment from production first, without the staging CI principal's role, so `08-environment.sh staging` runs again before staging deploys; staging can no longer be rebuilt before production.
- **One region again.** Production's compute returns to Sweden Central with its data: no cross-region latency, no inter-region transfer and no cross-region image pull, so staging's latency and cold start measure production's again.
- **New addresses.** A container app cannot change its environment, so both apps are recreated and get new host names: `03-auth-redirect.sh staging` and `production` run after each one's first deployment and keep only the app's current callback, removing the old environments' ones. The identities are user-assigned and their roles stay; `02-app-identity.sh` does not run again.
- **Rollback.** The recreated `ca-elevant-prod` starts with one revision, labelled `green`, so the label rollback is unavailable until the next release keeps it as `blue`. The planned rollback cannot cross this change either: `release.yml` deploys the tag's own Bicep, and v1.0.2 or earlier declares the two old environments. Until the next release, recovery in production is a fix-forward patch release; staging's rollback (`deploy.yml` with an earlier image) is unaffected.
- **Outage.** Production is down from the deletion of `ca-elevant-prod` until the approved v1.0.3 passes its smoke test, about 5 to 10 minutes; staging is down from its app's deletion until the merge redeploys it.

## Alternatives considered

- **A quota increase**: a support request with no date for both limits, and the release waits.
- **Production in the staging environment**: no quota needed, but production would run in an environment whose name, owner and teardown say staging.
- **Container Apps Express environments**: no built-in authentication, no own KEDA scalers and no revision labels, which Easy Auth (ADR-010), scale to zero (ADR-008) and blue/green (ADR-009) need.
