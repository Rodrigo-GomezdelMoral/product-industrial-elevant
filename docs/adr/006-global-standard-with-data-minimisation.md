# ADR-006: Global Standard with data minimisation

Status: accepted (phase 2, recorded 2026-10-31)

## Context

The shared `gpt-5-mini` deployment is Global Standard: requests may be processed outside Sweden Central. Inspection reports carry premises addresses and technician names, and quotes carry commercial prices.

## Decision

Send the model only what it needs to choose an item: each defect's text and the catalogue's codes, descriptions and units. No header field, no price and no file leave the region. Document Intelligence runs regionally on the same account. A unit test asserts the exact model payload.

## Consequences

- Data at rest (Cosmos DB, Blob, Application Insights) stays in Sweden Central.
- `store: false` keeps no response in Foundry.
- A client that requires in-region processing would need a Data Zone or Regional deployment, at a higher price per token.

## Alternatives considered

A regional deployment (higher price and its own quota for data the design already keeps out).
