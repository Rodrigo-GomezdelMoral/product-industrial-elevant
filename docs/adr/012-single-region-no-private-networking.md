# ADR-012: Single region, no private networking

Status: accepted (phase 6, recorded 2026-10-31; storage recommendation added 2026-11-02)

## Context

Zone redundancy in Container Apps needs a virtual network and at least two replicas; private endpoints for Cosmos DB, storage, Key Vault and the shared Foundry account need a virtual network, DNS zones and an hourly charge per endpoint. Defender plans bill per resource. The client works in one country, and REQ-06 is 99.5 % in business hours.

## Decision

One region per environment and no failover (Sweden Central; production's Container Apps environment runs in Spain Central for quota, with its data in Sweden Central, ADR-014), no zone redundancy, public endpoints with Entra ID only: local and shared-key authentication off on Cosmos DB, storage, Log Analytics and Application Insights, HTTPS only, TLS 1.2 or later. Recovery is cold: Bicep rebuilds the group and Cosmos DB restores to a point in time (continuous 7-day backup) with blob soft delete for 7 days; the restore drill measures the RTO against 4 h.

## Consequences

- No cost at rest for networking, and scale to zero stays possible.
- A regional outage takes Elevant down until the region returns or the cold rebuild finishes.
- A client requirement for private access would add a virtual network to the environment and endpoints per service.
- Azure Advisor's two high-availability recommendations in staging stay open on purpose (read 2026-11-01): *Enable zone redundancy for the managed environment* (above) and *Enable zone redundancy for storage accounts*. Zone-redundant storage (ZRS) costs more than the locally redundant (LRS) account per GB and per write, and with one region and the 7-day soft delete it would only add zone resilience to the reports and quotes while the compute stays zonal; it is revisited with the zone-redundant environment, if a client asks for it.

## Alternatives considered

Zone-redundant environment with two minimum replicas (always-on compute); private endpoints (an hourly charge per endpoint, plus private DNS zones).
