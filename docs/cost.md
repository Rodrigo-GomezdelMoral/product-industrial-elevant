# Cost

Retail Prices API, EUR, `swedencentral`, checked on 2026-10-30 (build prompt), plus the model cost measured by the evaluation on
2026-10-31. Assumptions: 300 quotes a month, 3 pages each, one matcher call per quote. Phase 7 compares these
estimates with Cost Management, per environment (below).

## Prices

| Meter | Price |
|---|---|
| Document Intelligence layout (`S0 Pre-built Pages`) | €8.7997 per 1,000 pages; no free tier on an AIServices account |
| `gpt-5-mini` Global: input · cached input · output | €0.22 · €0.022 · €1.7599 per 1M tokens |
| Container Apps: vCPU active · idle; memory; requests | €0.0000211 · €0.00000264 per vCPU-s; €0.00000264 per GiB-s; €0.352 per 1M; monthly grant per subscription of 180k vCPU-s, 360k GiB-s and 2M requests, shared with P06 to P08 |
| Cosmos DB serverless | €0.2684 per 1M RU; €0.22 per GB-month; continuous 7-day backup storage free; restore €0.132 per GB |
| Blob hot LRS | €0.0162 per GB-month; writes €0.044 and reads €0.0035 per 10k |
| Key Vault | €0.0264 per 10k operations (none in v1) |
| Log Analytics | €2.6311 per GB after 5 GB a month per billing account, shared with P06 to P08; 31 days included |
| Log alert, 15-minute frequency | €0.44 per rule a month, from the build prompt, kept as the estimate. On 2026-11-01 the Retail Prices API listed for Azure Monitor only *Alerts Resource Monitored at 15 Minute Frequency* (€0.044 per resource a month) and the 1-minute *System Log* meter, none matching this rule; it exists only in production, so Cost Management confirms it after the release (prompt 04) |
| Inter-region data transfer (production's app in Spain Central to its data in Sweden Central, ADR-014) | €0.0176 per GB (`spaincentral`, *Standard Inter-Region Data Transfer*, 2026-11-01); Container Apps in `spaincentral` lists the same meters, requests at €0.352 per 1M |

## Per quote

| Part | Cost | Source |
|---|---|---|
| Document Intelligence, 3 pages | €0.026 | price × pages |
| Matcher | €0.0027 cached, €0.0034 cold | measured: 3,312 input (3,206 cached) and 1,504 output tokens a draft |
| Corrector, about one correction | under €0.002 | output cap 2,000 tokens |
| Cosmos DB, Blob, requests | under €0.001 | a few hundred RU and two blobs |
| Compute and logs, shared over 300 quotes | €0 to €0.013 | depends on the subscription grant |
| **Total** | **about €0.04** | NFR: €0.05 or less per approved quote |

The workbook's unit-cost tile shows the model tokens and their cost per approved quote from telemetry (cached input counted at the full
price, so an upper bound).

## Per environment

| | Staging | Production |
|---|---|---|
| At rest | about €0.01: stored data only | about €0.50: the SLO alert rule plus stored data |
| In use | under €1 (about 30 test quotes, load tests with doubles, one short real-model scenario under €0.30) | €9 to €15 a month: Document Intelligence about €7.90, models about €1.20, compute €0 to €4 depending on the grant, logs €0 to €1.30, cross-region transfer under €0.75 (quotes under €0.03, image pulls on cold starts under €0.70) |
| Budget | €5 a month | €20 a month |
| Daily log cap | 0.1 GB | 0.5 GB |
| Maximum replicas | 3 | 5 |

Shared, and paid by the base whatever Elevant does: the registry (Basic, €0.1466 a day, about €4.40 a month) and the Foundry account
(per use). Budgets notify at 50, 80 and 100 % of actual cost and at 100 % of forecast; they alert and do not stop spending.

## Bringing an environment to zero

- It already scales to zero replicas when idle; nothing in Elevant's groups bills by the hour.
- To stop production's only fixed charge, disable the SLO alert rule.
- To stop deployments, prompt 06 pauses the workflows.
- Learn deletes Container Apps environments idle for more than 90 days with no apps; each environment always has its app, so it stays.

## Cost to date

Cost Management, actual cost from 2026-10-30 to 2026-11-01, read on 2026-11-01 (it can lag a day):

| | Staging | Production |
|---|---|---|
| Deployed | since 2026-10-31: the app, Cosmos DB, storage, Key Vault, monitoring, the workbook | the app identity only |
| Cost | €0.16: Cosmos DB serverless €0.16 (the 4,478 drafts of the load test), storage under €0.01, logs €0 (inside the free 5 GB), Container Apps €0 (inside the grant) | €0 |
| Model and Document Intelligence | billed to the shared base with the other products; staging's share from telemetry, 7 real drafts at about €0.03, about €0.21 | none |

The staging estimate (under €1 in use) holds. The measured model cost of a draft (€0.0032) matches the per-quote estimate.

