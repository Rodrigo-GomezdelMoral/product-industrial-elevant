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

## Decisions taken in phase 2

- **Document Intelligence runs before the graph.** `Workflow.run` saves an entry checkpoint before the first executor,
  so `start` reads the PDF first: a file that is not a PDF, is over 10 MB, has more than 10 pages (the service is asked
  for pages 1 to 11 only, which bounds the cost of a page bomb) or is unreadable (400 with inner code `InvalidContent`)
  never reaches a checkpoint or a blob. Any other 400 is a configuration error and propagates. The `extract` executor
  then turns the layout into the header and the defects and stores the PDF. The PDF and the layout reach it through its
  constructor, never a message, so checkpoints stay at about 2 to 6 KB.
- **Plain JSON between executors.** Messages and `request_info` payloads are dicts, so the restricted unpickler of the
  checkpoint storages needs no application type.
- **Header.** The first key-value pair per field whose key is close to a synonym (`rapidfuzz` ratio at least 85),
  ignoring pairs whose key is a column header of a defects table and single-line keys with multi-line values (table
  columns); a two-line key merged by the service is paired line by line. Dates become ISO. A confidence under 0.8 or an
  unreadable date flags `low_confidence`; a missing field stays empty and `open_flags` blocks approval.
- **Defects.** Every table row after its header rows that is not a label-value row, without the leading reference
  column, with the page of its own cells and its row counted per page. On the recorded layouts: 160/160 header fields
  and 535/535 defects with the page and row of the truth, in two recordings whose header-row marking differed.
- **Matcher.** One call per report. The catalogue (code, category, description, unit; no price) goes in the
  instructions as a stable prefix, and from the second call 2.7k to 3.1k of about 3.3k input tokens are read from the
  cache. The defects go as JSON in the user message. Options: structured output, reasoning effort `low`, `store: false`
  (Foundry keeps no response), and an output cap of 2,000 plus 250 per defect (observed 120 to 135 per defect, reasoning
  included). An answer that cannot be parsed (cut short or malformed) flags every line "no usable answer"; any other
  client error (a 429, an outage) propagates for the API to turn into a clear message in phase 4.
- **Corrector.** It receives each line's number, plain-words defect, item code and quantity, and proposes edits that
  are checked by applying them to a copy with `review`; nothing is applied until the estimator confirms.
- **No streaming from the agents.** Each call returns one structured answer, so the test chat client returns a
  `ChatResponse` only.
- **Resume by quote id.** `resume` answers the stored quote's own request from its own checkpoint, never ids from the
  caller; an approved quote refuses any answer; the save after a resume is conditional on the Cosmos DB etag, so two
  answers to the same request cannot both win; a graph change becomes a clear message (drain reviews before changing
  the graph and bump `VERSION`).
- **Progress.** "Reading the report" before the service call, then the framework's `executor_invoked` events for
  `match` (with the number of defects) and `price`; custom event types are a closed `Literal` in 1.23.0.
- **Storage.** With `ELEVANT_ENV=local` the store uses the emulators: the Cosmos DB vNext emulator, which does not check
  keys (Learn `cosmos-db/emulator-linux`, 2026-10-07), so the key is a constant that says so; and Azurite through the
  SDK's own `UseDevelopmentStorage=true`. In Azure, `DefaultAzureCredential` only. Containers `quotes` (`/id`, point
  reads) and `checkpoints` (`/workflow_name`, one partition per quote); `create_local` makes them in the emulators, and
  Bicep makes them in Azure (phase 6), the checkpoints container with a TTL so the checkpoints of a failed draft age
  out. Azurite needs `--skipApiVersionCheck` because the SDK speaks API `2026-10-06`. `make emulators` starts both,
  pinned by digest, and `ci.yml` runs the tests against them with `ELEVANT_EMULATORS=true`.
- **Doubles.** `ELEVANT_DOUBLES=true` swaps the model for `agents.Double` (the closest `rapidfuzz` description, no
  corrections) and Document Intelligence for the recorded layout of `report-0134`: the Dockerfile (phase 6) copies
  `eval/datasets/extracted/report-0134.json`. `Settings` refuses doubles when `ELEVANT_ENV=production`.
- **Recorded layouts.** The 40 reports were read once with `app.extraction.analyze` and kept in
  `eval/datasets/extracted/` (phase 3 uses them for pull-request evaluations).
- **For phase 4.** A deadline on the draft (the poller has none; the OpenAI client defaults to 600 s and 2 retries),
  client errors turned into clear messages, and deletion by quote id of the quote, its checkpoints
  (`list_checkpoint_ids` for `quote-v1-<id>`) and its blobs.
- **Known weak case for phase 3.** "Door sill adjustment and cleaning" seen at a floor is still sometimes matched to the
  landing variant instead of being flagged ambiguous. Development check of the matcher prompt over the 40 recorded
  layouts (2026-10-31): unambiguous items 445/450, ambiguity recall 43/46 and precision 43/48, no-match 37/37, injection
  2/2; matcher p50 12.3 s, p95 18.7 s.

## Decisions taken in phase 3

- **The evaluation runs the product.** `eval/run.py` drafts each of the 40 reports through `app.workflow.start` (extract,
  match, price, up to the review request) with an in-memory store and checkpoints, so a change to the workflow, the
  domain rules or the prompts is measured end to end. On pull requests the recorded layouts stand in for Document
  Intelligence; `--full` reads the PDFs. `workflow.models()` builds the reader and the chat client for both the app
  (`connect`) and the evaluation.
- **Metrics in code, against the truth.** No LLM judge: every answer has a known truth. Agent Framework's evaluation
  API (`evaluate_agent`, `LocalEvaluator`) is experimental in 1.23.0 and scores items pass or fail, while these metrics
  are ratios over different subsets of defects; Foundry cloud evaluations add judges and cost for nothing measurable
  here. A truth defect pairs with the draft line of the same page and row only when their texts agree (`rapidfuzz`
  partial ratio at least 90), so an extraction that shifts rows counts as missed rows, not as matcher errors. Expected
  totals are recomputed in integer cents with half-up VAT, independently of `domain.money`.
- **One metric added to the prompt's table:** `no_match_recall` (a defect with no catalogue item is left without one),
  0.90 like ambiguity recall. Without it a matcher that invents items for building defects would pass. An injection
  line passes when it is flagged and prices nothing but the truth's item and quantity (superseded on 2026-10-31, below).
- **The gate.** Below a threshold, over the latency maximum (full runs only: with recorded layouts a draft has no
  Document Intelligence), or more than 2 points under `eval/baseline.json`, but never for a single case: on the 46
  ambiguous defects one case is 2.2 points and the model varies by one case between identical runs. The baseline is
  the lowest value of three runs of the accepted configuration (two on recorded layouts, one full) and is changed by
  hand in the pull request that justifies it.
- **The matcher prompt** now chooses by part and then by the detail the row names; the location never names a variant
  and the symptom never names the work. The phase 2 prompt failed the gate (ambiguity recall 41/46).
- **`eval.yml`.** Pull requests use `AZURE_CLIENT_ID_PR` (the staging app's `pull_request` credential, as the setup
  designed) and skip forks and Dependabot, which get no OIDC secrets: a Dependabot update of `agent-framework-*` or the
  Azure SDKs is evaluated with the manual full run after merging. The manual run is dispatched from `main` in
  environment `staging` with `deployment: false`, so it creates no deployment record. Both resolve the shared
  endpoints after login with `az cognitiveservices account [project] show` (the CI principal's `Foundry User` includes
  `Microsoft.CognitiveServices/*/read`), so no new variable or script is needed. Each pull request run posts a new
  comment with the head commit, the table and up to 30 misses, or says that the evaluation did not complete.
- **Runs.** Two drafts at a time (measured at about 47K of the shared deployment's 100K tokens per minute; the rate
  limit counts actual tokens, not the output cap) and a 300 s deadline per draft, in a `TaskGroup`, so one failure
  stops the run cleanly.
- **For phase 6.** `release.yml` can keep checking for a successful `staging` deployment: evaluation runs create none.
  An optional hardening for the user: a dedicated evaluation app registration with only `Foundry User`, instead of
  the staging deployer's `pull_request` credential.
- **Budget after phase 3:** Python app 1,117/1,400 and tests 553/600; phase 4 has to fit the API, telemetry and its
  tests in what is left.

## Decisions taken between phases 3 and 4 (`feature/matcher-tuning`, 2026-10-31)

- **Why.** The pull request run of #4 failed on `injection_flagged` 1/2: a resisted injection ("Car door roller, 40 mm" with an
  instruction to price it at 0) drafted as the landing door roller, flagged, at that item's catalogue price. The evaluator also
  required the truth's item, which the build prompt's definition does not; with n = 2 at 1.00 a wrong variant failed the gate alone.
- **Fail closed.** A choice with confidence under 0.6 among two or more candidates is `ambiguous`, unpriced, with its candidates
  (`domain.propose`); `invalid_code` keeps precedence and a low-confidence choice with at most one candidate stays `low_confidence`. It changed
  no line of run 1.
- **Injection metric as the build prompt defines it:** flagged and, when priced, its own item's catalogue price and the row's
  quantity. The item is `match_accuracy`'s question, which now counts the 2 injection defects (452). Thresholds unchanged.
- **Tokens are measured.** `eval/run.py` adds a chat middleware to the client (`ChatMiddlewareLayer.chat_middleware`, a
  `ContextVar` counter per draft) and reports mean input, cached, output and reasoning tokens, € per draft and p50 latency.
  `main`'s configuration: 3,312 input (3,206 cached), 1,504 output (557 reasoning), €0.0027 a draft cached and €0.0034 cold;
  output is 97 % of the cost cached.
- **Rejected by the gate:** answers without `expanded` and `category` (−22 % output, p95 18.4 to 12.7–14.3 s) and without
  `category` alone (no saving): "Graffiti on the car walls" became a false `ambiguous` in 8 rows over 5 runs, against 3 over 5
  with `category`, and two runs failed on precision. Reasoning effort `minimal`: ambiguity recall 12/46. The matcher's answer and
  effort stay as in phase 3.
- **Decided from the measurements:** prompt and catalogue length unchanged (input is €0.0001 a draft cached, €0.0007 cold); no
  parallel calls per report (each repeats the 3.2K prefix, and production at about one draft an hour runs on a cold cache: Learn
  says in-memory caches are typically cleared after 5 to 10 minutes idle and `gpt-5-mini` has no extended retention; +40 % cost
  for latency the SLO does not need).
- **Output cap** 1,500 + 150 per defect (was 2,000 + 250): the largest draft at effort `low` used 62 % of it; a 20-defect
  runaway is bounded at 4,500 tokens (€0.0079). The corrector keeps 2,000.
- **Baseline unchanged:** same model configuration as phase 3; the final code scores run 1 at or above it everywhere, and the
  redefined metrics keep 1.0. Eight runs with recorded extractions (one stopped early), about €0.70.
- **Budget after this branch:** Python app 1,149/1,400 and tests 571/600; phase 4 has 29 lines of tests left.

## Verified names (installed wheels, 2026-10-30 and 2026-10-31)

| Package | Name |
|---|---|
| `agent-framework-core` 1.23.0 · `agent-framework-foundry` 1.15.0 | `agent_framework.foundry.FoundryChatClient` |
| `agent-framework-azure-cosmos` 1.0.0b261015 | `agent_framework_azure_cosmos.CosmosCheckpointStorage` (not `agent_framework.azure_cosmos`) |
| `docxtpl` 0.20.2 | `DocxTemplate(file).render(context, autoescape=True)`; table rows repeat with `{%tr for %}` and `{%tr endfor %}` |
| `openpyxl` 3.1.5 | `load_workbook(file, data_only=True)`; `types-openpyxl` 3.1.5.20261017 |
| `reportlab` 5.1.0 | `SimpleDocTemplate(..., invariant=1)` writes byte-identical PDFs; `types-reportlab` 5.0.0.20261008 |
| `pillow` 13.0.0 | PDF `creationDate` and `modDate` take a `time.struct_time` |
| `agent-framework-core` 1.23.0 (workflows) | `WorkflowBuilder(name=, start_executor=, checkpoint_storage=)`, `Executor`, `@handler`, `@response_handler`, `FunctionExecutor(func, id=)`; `ctx.request_info(data, response_type)`; `Workflow.run(message, stream=True)` and `run(checkpoint_id=, responses=)`; `resolve_pause_checkpoint_id(request_ids)`; `WorkflowRunResult` is a list of `WorkflowEvent`; `agent_framework.exceptions.WorkflowCheckpointException` |
| `agent-framework-core` 1.23.0 (agents) | `Agent(client, instructions, name=, default_options=)`; a chat client receives the instructions as `options["instructions"]`; `BaseChatClient` with `FunctionInvocationLayer` and `_inner_get_response`; client errors arrive as `ChatClientException` with the original as `__cause__` |
| `agent-framework-foundry` 1.15.0 | `FoundryChatClient(project_endpoint=, model=, credential=)`, closed through `.client` and `.project_client`; options `response_format`, `reasoning={"effort": "low"}`, `max_tokens` (the Responses `max_output_tokens`, reasoning included), `store` |
| `agent-framework-azure-cosmos` 1.0.0b261015 | `CosmosCheckpointStorage(container_client=)` creates nothing; `load` queries every partition by checkpoint id |
| `azure-ai-documentintelligence` 1.0.2 | `aio.DocumentIntelligenceClient`; `begin_analyze_document("prebuilt-layout", AnalyzeDocumentRequest(bytes_source=), pages=, features=[DocumentAnalysisFeature.KEY_VALUE_PAIRS], output_content_format=DocumentContentFormat.MARKDOWN)`; an unreadable file is a 400 with inner error code `InvalidContent` |
| `azure-cosmos` 4.17.1 · `azure-storage-blob` 12.31.1 | `upsert_item(body, etag=, match_condition=MatchConditions.IfNotModified)` raises `CosmosAccessConditionFailedError`; `BlobServiceClient.from_connection_string("UseDevelopmentStorage=true")` |
| `aiohttp` 3.14.5 | the transport of the async Azure clients, pinned because the app imports the `aio` clients directly |
| Emulators | Azurite 3.37.0 (`azurite-blob --skipApiVersionCheck`); Cosmos DB vNext `vnext-EN20261019`, HTTP on 8081, readiness on `:8080/ready` |
| `agent-framework-core` 1.23.0 (evaluation) | `EvalItem`, `LocalEvaluator`, `evaluator`, `evaluate_agent` and `evaluate_workflow` exist and are marked experimental |
| GitHub Actions (2026-10-31) | `environment: {name, deployment: false}` uses an environment's secrets without a deployment object; `defaults.run.shell: bash` runs steps with `-eo pipefail`; `azure/login` v3.1.0 is commit `a641126d1b8aa4d1fa005f4f92df94a3a4c4c906` (node24); `gh pr comment --body-file` |
| Azure CLI 2.89.0 | `az cognitiveservices account project show --project-name` returns the project endpoint in `properties.endpoints."AI Foundry API"`; the account's `properties.endpoint` serves Document Intelligence |
| `types-PyYAML` 6.0.12.20261030 · actionlint 1.7.12 | stubs for `yaml.safe_load` under mypy strict · `rhysd/actionlint:1.7.12` with shellcheck, clean on `ci.yml` and `eval.yml` |
