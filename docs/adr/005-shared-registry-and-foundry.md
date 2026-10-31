# ADR-005: The shared registry and Foundry account

Status: accepted (phase 6, recorded 2026-10-31)

## Context

A container registry bills by the day whatever it stores, and a Foundry account with model deployments is pay per use but carries quota. The portfolio's shared base (`rg-aiplatform-shared-swc`) already has the registry `craiplatformshared` (Basic) and the Foundry account `fdry-aiplatform-shared-swc` with `gpt-5-mini` and Document Intelligence.

## Decision

Share both, with separate identities: `id-elevant-stg` and `id-elevant-prod` get `AcrPull` and `Foundry User` there (from `02-app-identity.sh`), the staging CI principal gets `AcrPush`, the production CI principal only `AcrPull`. Images are built once per merge and promoted by digest, so production runs exactly the bytes staging tested. Everything with data (Cosmos DB, storage, Key Vault, Application Insights) is per environment.

## Consequences

- About €4.40 a month of registry and no idle model cost are paid once for P05 to P08.
- The 100K tokens-per-minute deployment is shared with other products: output caps, at most 5 production replicas and the API's clear `429` message bound Elevant's share.
- The production CI principal cannot read the Foundry account, so the endpoints reach Bicep as GitHub variables.

## Alternatives considered

A registry and deployments per environment (daily cost and quota for no isolation that matters, since data is separate).
