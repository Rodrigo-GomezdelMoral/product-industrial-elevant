# ADR-010: Built-in auth with ID tokens and no client secret, app roles in the API, an empty vault

Status: accepted (phase 6, recorded 2026-10-31)

## Context

Every path except `/healthz` and `/api/version` needs a signed-in employee with a role (SE:08). Learn advises the authorization code flow where possible, which needs a client secret or certificate to store and rotate. Elevant signs users in and calls no downstream API on their behalf.

## Decision

Container Apps built-in auth with Microsoft Entra ID, the `elevant-web-<env>` registration and no client secret: "When the client secret isn't set, implicit flow is used and only an ID token is returned" (Learn `container-apps/authentication-entra`). Unauthenticated browsers are redirected to sign in; `/healthz` and `/api/version` are excluded (version and digest only, no customer data; the release smoke test needs them without a session). The API reads `X-MS-CLIENT-PRINCIPAL`, which external requests cannot set, and checks the app roles `Quote.Estimator` and `Quote.Manager`, since the platform does not. Assignment is required. Bearer tokens for the same registration (v2, audience the client id or `api://<client id>`) are accepted, which the load test uses with the staging CI principal. Key Vault exists per environment, RBAC only, soft delete and purge protection, with no secret and no role assignment: it is where a secret would go if a downstream API ever needs one.

## Consequences

- Nothing to rotate and no secret anywhere.
- The redirect URI depends on the app's address, so `03-auth-redirect.sh` adds it after the first deployment.
- Moving to the code flow later is a secret in the vault and a Bicep change, no code change.

## Alternatives considered

Authentication in code with MSAL (reimplements the platform); the code flow with a secret (rotation for no requirement).
