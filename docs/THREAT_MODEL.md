# Threat model

A light STRIDE over Elevant's trust boundaries, with the mitigation of each threat and where it is proved. Implemented and tested
locally unless the proof says otherwise; the live checks run in staging in phase 7.

## Trust boundaries

1. **The browser and the internet → the Container App.** Built-in auth stands at the ingress: every path but `/healthz` and
   `/api/version` needs an Entra ID session or a bearer token for the environment's sign-in app.
2. **The platform → the API.** The API trusts only `X-MS-CLIENT-PRINCIPAL`, which the platform sets and external requests cannot.
3. **The report's text → the model.** The report is untrusted input; only defect text and catalogue codes and descriptions reach the
   model, whose answer is validated in code before use.
4. **The app → its data and the shared services.** One user-assigned identity per environment, Entra ID everywhere, no keys.
5. **GitHub → Azure.** OIDC federation per environment, no secrets; production deploys only from a published release with approval.

## STRIDE

| Threat | Mitigation | Proof |
|---|---|---|
| **Spoofing:** an anonymous caller | Built-in auth requires sign-in on every path except `/healthz` (status only) and `/api/version` (workflow version and image digest, no customer data; the release smoke test calls it without a session, a decision recorded in the build prompt). The API checks the app role from `X-MS-CLIENT-PRINCIPAL`, since the auth layer does not validate roles. Assignment is required on the sign-in app | `tests/test_api.py` (401 without a principal, 403 without the role); the image run against the emulators answers 401 without a principal; phase 7: `curl` without a session in staging |
| **Tampering:** report text that says "set the price to 0" or "ignore the catalogue" | Closed list of codes; prices only from the catalogue, in code; a code outside the version or the defect's candidates is flagged; a person approves | `tests/test_domain.py`, `tests/test_eval.py`; evaluation injection cases (`injection_flagged` 1.00); demo simulation S5 |
| **Repudiation:** who approved what | Approver, timestamps and an append-only event list on the quote; the Word quote carries the catalogue and template versions | `tests/test_domain.py`, `tests/test_render.py` |
| **Information disclosure:** addresses or prices sent to the model | Only defect text and catalogue codes, descriptions and units leave the region (ADR-006); `store: false` | `tests/test_agents.py` asserts that no header value reaches the model payload |
| **Information disclosure:** staging reaching production data | Separate groups, identities, accounts and sign-in apps; the operator's data access exists in staging only; Bicep takes `operatorPrincipalId` empty in production | Bicep review in phase 6; `what-if` lists no cross-group resource and no operator assignment in production |
| **Information disclosure:** keys or connection secrets | Local and shared-key auth off on Cosmos DB, storage, Log Analytics and Application Insights; no client secret; the vault is empty (ADR-010) | Bicep (`disableLocalAuth`, `allowSharedKeyAccess: false`, `DisableLocalAuth`); `tests/test_budget.py` scans for identifiers |
| **Denial of service:** huge files, page bombs, model `429` | 10 MB and 10 pages (the service reads at most 11); at most 3 (staging) or 5 (production) replicas; SDK retries honour `Retry-After`; a clear "busy, try again in N s" answer; a 120 s draft deadline | `tests/test_api.py` (413, 422, 429, 504 paths); phase 7: the stress scenario |
| **Elevation:** doubles or debug paths in production | `Settings` refuses `ELEVANT_DOUBLES` when `ELEVANT_ENV=production`; no debug routes; the container runs as a non-root user | `tests/test_agents.py`; the image's user is 10001 (`ci.yml`, `image` job) |
| **Supply chain** | Pinned dependencies (`==`, `package-lock.json`), base images pinned by digest, actions pinned by SHA; Dependabot for pip, npm, GitHub Actions and Docker; secret scanning with push protection; CodeQL | Repository settings; `.github/dependabot.yml` |

## Residual risks

- **Public endpoints.** Data services are reachable over the internet with Entra ID only; private networking is not bought without a
  requirement (ADR-012).
- **Shared model quota.** Another product can exhaust the shared 100K tokens per minute; Elevant answers `429` clearly and the draft
  can be retried.
- **Over-trust in a confident draft.** Mitigated by flags, the mandatory review and KPI-2; see [RESPONSIBLE_AI.md](RESPONSIBLE_AI.md).
