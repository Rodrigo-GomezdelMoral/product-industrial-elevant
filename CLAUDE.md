# CLAUDE.md, working agreement

`product-industrial-elevant` is **Elevant**: lift inspection reports turned into reviewed, traceable repair quotes in Word, for a
mid-sized lift maintenance company. A staff engineer and a product lead will read this repository for ten minutes and must conclude
that the author ships products a company would put in front of its customers: a client with requirements, metrics that prove the
value, and a safe way to change it.

Three rules govern every choice:

> **If Azure, GitHub or Microsoft Agent Framework already does it, do not reimplement it.**
>
> **The model never decides money.** It reads defect text and chooses catalogue codes from a closed list; prices, amounts, VAT and
> totals are computed in code from the catalogue, and a person approves before anything is issued.
>
> **Every product practice exists because a `REQ` or a non-functional requirement asks for it, and it shows in the demo.**

**Re-read this file at the start of every phase** and reason the plan before touching code: which `REQ` the phase closes (see
`docs/PRODUCT.md`) and how it will be shown.

## Process

- The build prompt is `../_prompts/V5-CC-P05-product-industrial-elevant.md`, executed phase by phase with
  `../_00_MASTER_PROMPTS_PRODUCT/02_EJECUTAR_PROMPT_POR_FASES.md`. Both are read in full; this file does not replace them.
- **Trunk-based.** One short branch per phase, created with `git switch -c` from `main` updated with `git pull --ff-only`:
  `feature/setup`, `domain`, `agents`, `eval`, `api`, `web`, `infra`, `staging`, `release`. No environment branches.
- **Commits, pushes, PRs, merges and releases are the user's.** Never run `git add`, `git commit`, `git push`, `gh pr create`, a merge
  or a release. No `Co-Authored-By` of Claude and no Claude Code line anywhere: the user is the only author.
- **Closing a phase, in this order:** ruff, mypy, pytest and the budget, plus the phase's own checks; conformance with its
  `Guidance map` sections; the block below; the publish script `../_scripts/product-industrial-elevant/publish-<branch>.sh` (template
  7.3 of `../_00_MASTER_PROMPTS_PRODUCT/_setup/CONFIGURACION_INICIAL.md`: only the phase's paths, commits in English, the PR body with
  the block); `git status --short`; stop until the user merges and says "continue".

  ```
  ── PHASE n COMPLETE ──
  Counts: files <n>/80 · Python app <n>/1,400 · tests <n>/600 · Bicep <n>/490 · TypeScript <n> (< 800) · comments <n>/5
  Verified: ruff ✓ mypy ✓ pytest ✓ budget ✓ <phase checks ✓>
  Requirements: REQ-nn <test> + <live check> · …
  Guidance: <syllabus sections and Well-Architected codes checked>
  Publish: ../_scripts/product-industrial-elevant/publish-<branch without feature/>.sh
  ```

  The counts come from `python -c "from tests.test_budget import budget_counts; print(budget_counts())"`.
- **Identity is the user's.** Roles, federated credentials, app registrations, managed identities and role assignments to people go in
  `../_scripts/product-industrial-elevant/<nn>-<what>.sh`; write the script and stop. `02-app-identity.sh` and `03-auth-redirect.sh`
  are written in phase 6.
- **Azure only in phases 7 and 8.** Until then: local, the Azurite and Cosmos DB emulators, Bicep `what-if`, and the shared model
  deployments (pay per use) with the user's own identity. Before creating anything that bills by the hour, state its price and how it
  is switched off. Staging ends every phase at zero replicas.
- **Verify, then write.** Every Agent Framework and Azure SDK name against the installed wheel; every Bicep API version, CLI flag and
  GA or preview status against Microsoft Learn. Never claim what was not checked: say whether a thing is implemented, tested, deployed
  to staging, deployed to production or pending.
- **English** in everything generated. The user is spoken to in Spanish.

## Non-negotiable constraints

1. **No identifiers anywhere:** no GUIDs, e-mail addresses, `*.azurecontainerapps.io` hostnames, public IPs, `C:\Users` paths or
   portal URLs that encode a subscription, in files, fixtures, recorded runs, commits or documentation. `tests/test_budget.py` scans
   every file and reports only the file and the kind of identifier, never the value.
2. **Zero secrets.** Managed identity and `DefaultAzureCredential` everywhere; local and shared-key auth disabled on Cosmos DB, Storage
   and Application Insights ingestion. GitHub holds only the identifiers set by the setup scripts.
3. **Size budget, enforced by `tests/test_budget.py`:** at most 80 files (excluding `docs/`, `data/`, `eval/datasets/`,
   `web/fixtures/`, `web/public/`, lock files and `node_modules/`); Python in `app/ eval/ load/ ops/` at most 1,400 non-blank lines;
   tests at most 600; Bicep at most 490; TypeScript under 800; Python functions at most 35 lines.
4. **Comments:** at most 5 `#` comments in all the Python. The why goes in the ADRs and the README.
5. **No bare `except Exception`.** Catch the SDK's exception types and turn them into a clear message.
6. **Pinned dependencies:** `==` in both requirements files, `package-lock.json` committed, GitHub Actions pinned to a full commit SHA
   with the tag in a trailing comment. Never the `agent-framework` metapackage.
7. **Nothing unfinished:** no to-do markers (ruff `FIX` enforces it in Python), no placeholder text, no dead code.
8. **Authorship only in the README:** the byline and buttons under the title and `## Author` at the end. `LICENSE` stays the unfilled
   Apache-2.0 template; no author in `pyproject.toml`; never an e-mail.
9. **README** with the common structure of `../_00_MASTER_PROMPTS_PRODUCT/07_README_FINAL.md`: no quick start, no local-run
   instructions, no status badges, no em dashes. The product is tried through the published demo.
10. **`targetScope = 'resourceGroup'`.** `rg-elevant-stg-swc` and `rg-elevant-prod-swc` exist; Bicep never creates them.

## Estate checked in phase 0 (2026-10-30, names only)

- **Shared base** in `rg-aiplatform-shared-swc` (read, never changed from here): Foundry account `fdry-aiplatform-shared-swc` (AIServices,
  local auth off) with project `proj-aiplatform-shared`; deployments `gpt-5-mini` (`2025-08-07`, Global Standard, `NoAutoUpgrade`,
  guardrail `guardrail-chat`) and `text-embedding-3-small`; no `gpt-5-nano`; registry `craiplatformshared` (Basic, admin user off);
  workspace `log-aiplatform-shared-swc`.
- **Elevant's groups** `rg-elevant-stg-swc` and `rg-elevant-prod-swc` in `swedencentral`, tagged `project`, `environment`, `owner`,
  empty. CI principals `gh-product-industrial-elevant-staging` (Contributor and conditioned RBAC Administrator on its group, `AcrPush`,
  `Foundry User`) and `-production` (the same on its group, `AcrPull`), with federated credentials and no client secrets.
- **Quotas:** `gpt-5-mini` Global Standard 500K TPM in the region, 100K used by the shared deployment; `gpt-5-nano` 0 and no quota will be
  requested, so it is not deployed and every agent uses `gpt-5-mini`. The subscription was upgraded from free trial to pay-as-you-go on 2026-10-30 (no spending
  limit: budgets alert, they do not stop spending). Container Apps managed environments: limit 15 in `swedencentral`, so the two
  environments of the `Environments` table fit as designed.

## Decisions taken in phase 0

- **Dependencies.** `requirements.txt` holds what the image runs; `requirements-dev.txt` adds lint, types, tests, load tests and the
  synthetic-data tools. The whole set was installed together on Python 3.12 and `pip check` passed.
- **Dependabot** watches `pip` (the `agent-framework-*` packages grouped, because `agent-framework-core` is pinned exactly and the
  integrations require it) and `github-actions`. `npm` is added in phase 5 and `docker` in phase 6, with the manifests they watch.
- **CI** runs one Python job through `make check`; the web and Bicep jobs skip their steps until `web/package.json` and
  `infra/main.bicep` exist.

## Decisions taken in phase 1

- **Reference data is the client's, not code.** `catalogue-v1.xlsx` and `quote-template-v1.docx` were made once and are maintained
  as files; no script regenerates them. A quote pins both versions (name and SHA-256) when it is created and keeps them through
  review; a pinned file whose hash changed is refused, and the `reference` job of `ci.yml` fails a pull request that modifies or
  deletes a released file. The VAT rate lives in the catalogue (`terms!B1`), versioned with the prices it applies to.
- **Fail closed.** A proposed code outside the catalogue version, or outside its own first three candidates, is `invalid_code`;
  a confidence below 0.6 or not a number is `low_confidence`; a quantity outside (0, max], with more than two decimals, or
  fractional for a counted unit is `invalid_quantity`, without hiding a review flag. Missing header fields and a quote with no
  lines block approval like any flag.
- **Pure changes.** `draft`, `review` and `approve` return a new quote; a refused batch leaves the stored one untouched. `approve`
  re-checks the pinned catalogue and template, so an approved quote always has its document.
- **KPI-2 from the lines.** A line is `proposed` until the estimator acts; `changed` only when its item or quantity really differ;
  `accepted` at approval when untouched.
- **The Word quote** numbers the kept lines 1 to n for the customer and traces each one by code, catalogue version and report page
  and row. The approver stays on the record, not on the document. The date is the UTC approval date, which equals the Madrid date
  inside business hours; `tzdata` is not added for the hours outside them.
- **Types.** `types-openpyxl` and `types-reportlab` stubs are pinned for mypy strict; `docxtpl` and `pypdfium2` have none and are
  declared `ignore_missing_imports`.
- **Dataset.** Seed 2081 was chosen because its 40 reports contain the cases of simulations S1 to S5; `data/README.md` maps them.

## Verified names (installed wheels, 2026-10-30)

| Package | Name |
|---|---|
| `agent-framework-core` 1.23.0 · `agent-framework-foundry` 1.15.0 | `agent_framework.foundry.FoundryChatClient` |
| `agent-framework-azure-cosmos` 1.0.0b261015 | `agent_framework_azure_cosmos.CosmosCheckpointStorage` (not `agent_framework.azure_cosmos`) |
| `docxtpl` 0.20.2 | `DocxTemplate(file).render(context, autoescape=True)`; table rows repeat with `{%tr for %}` and `{%tr endfor %}` |
| `openpyxl` 3.1.5 | `load_workbook(file, data_only=True)`; `types-openpyxl` 3.1.5.20261017 |
| `reportlab` 5.1.0 | `SimpleDocTemplate(..., invariant=1)` writes byte-identical PDFs; `types-reportlab` 5.0.0.20261008 |
| `pillow` 13.0.0 | PDF `creationDate` and `modDate` take a `time.struct_time` |
