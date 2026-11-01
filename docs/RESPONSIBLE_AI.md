# Responsible AI impact assessment

Elevant's impact assessment, with the five sections of Microsoft's Responsible AI Impact Assessment Template (June 2022): system
information, intended uses, adverse impact, data requirements and summary of impact. It follows the map, measure, mitigate and manage
stages of AI-103 (learning path 1, module 6). Assessed on 2026-10-31, at the end of phase 3. Each mitigation says whether it is
**implemented and tested** in this repository or **planned** for a later phase.

## 1. System information

| | |
|---|---|
| System | Elevant: lift inspection reports turned into reviewed, traceable repair quotes in Word |
| Lifecycle stage | In development: domain, agents, workflow and evaluation done; API, web, infrastructure, staging and release to come |
| Deployment | One Azure Container App per environment (staging in Sweden Central; production in Spain Central with its data in Sweden Central, ADR-014), used by the client's office staff through a web browser after Microsoft Entra ID sign-in |
| Users | One client: three estimators and one technical and commercial manager (`docs/PRODUCT.md`) |
| Languages | English reports, catalogue, interface and quotes |
| AI components | Azure AI Document Intelligence `prebuilt-layout` reads the PDF. Two Agent Framework agents on `gpt-5-mini` (`2025-08-07`, Global Standard): the **matcher** chooses catalogue codes for the defects, the **corrector** turns a sentence into proposed line edits. Neither agent has tools |
| Deterministic components | Header and defect extraction from the layout, validation of every model answer against the catalogue version, pricing, VAT and totals in `Decimal`, approval rules, the Word document |

**Purpose.** Remove the office work between an inspection report and a repair quote (33 to 65 minutes per quote today) while keeping
a person responsible for every quote that leaves the company.

**What the AI decides and what it does not.** The model proposes, per defect, one catalogue code and a quantity, or no code with up to
three candidates and a reason. It never sees a price, an address, a lift ID or a technician's name, and it never decides an amount.
Code rejects any code outside the catalogue version or outside the defect's candidates, flags low confidence, leaves a
low-confidence choice among several candidates unpriced as ambiguous, and computes every amount. An estimator resolves every flag and approves before a document can be produced.

## 2. Intended uses

### Intended use 1: drafting a quote from an inspection report

**Fitness for purpose.** Measured on 40 synthetic reports in the client's three layouts, 10 of them scanned, with 535 defects whose
truth is known by construction (`docs/evaluation.md`). Full run with Document Intelligence on 2026-10-31: every header field and every
defect read with its page and row; the right item and quantity for 450 of 450 unambiguous defects; 45 of 46 ambiguous defects
flagged; 37 of 37 defects with no catalogue item left without one; both injection attempts flagged; draft p95 25.4 s. Results are
in-sample: the matcher prompt was tuned on the same 40 reports, so a fresh set from another seed was also measured (see
`docs/evaluation.md`).

**Stakeholders, benefits and harms.**

| Stakeholder | Benefit | Potential harm |
|---|---|---|
| Estimator | Reviews instead of searching and calculating; 5 to 10 minutes per quote instead of 33 to 65 | Over-trust in a confident draft; a wrong line accepted without reading it |
| Manager | Consistent quotes, KPIs instead of reading every quote | Quality problems hidden behind good averages |
| End customer (building owner or community) | Faster quotes, each line traceable to the inspection | Charged for the wrong part or quantity, or a needed repair missing from the quote |
| Technician | Unchanged way of writing reports | None identified |
| The client company | Office time back, fewer pricing errors | Commercial loss or dispute from a wrong quote |

**Responsible AI Standard goals that apply.**

| Goal | How it applies |
|---|---|
| A1 Impact assessment | This document, reviewed at each phase that changes the AI components |
| A2 Oversight of significant adverse impacts | The evaluation gate on every pull request that changes prompts, agents, the workflow, the domain rules or the reference data |
| A3 Fit for purpose | The thresholds of `docs/evaluation.md`, met before a change merges |
| A5 Human oversight and control | Mandatory review and approval; approval refused while any flag is open; an approved quote is read-only |
| T1 System intelligibility for decision making | Every line shows its source page and row, the catalogue code and version, the flag and the model's reason |
| T2 Communication to stakeholders | This document, `docs/PRODUCT.md` and the README |
| T3 Disclosure of AI interaction | The interface labels proposals and flags as Elevant's (planned, phase 5) |
| F1 Quality of service | Quality measured per layout and for scanned reports; no personal attribute is used |
| RS1 to RS3 Reliability and safety | Thresholds, failure handling (an unusable answer flags every line), and monitoring through KPI-2 and KPI-3 in production |
| PS1, PS2 Privacy and security | Data minimisation towards the model, managed identities, no secrets; `docs/THREAT_MODEL.md` (phase 6) |
| I1 Accessibility | WCAG 2.2 AA with axe-core in CI (planned, phase 5) |

F2 (allocation of resources and opportunities) and F3 (stereotyping, demeaning and erasing outputs) do not apply: Elevant allocates
nothing to people and produces no text about people.

**Task complexity and role of humans.** Narrow and well defined: choose among about 120 catalogue items for short, abbreviated rows.
The estimator decides; Elevant proposes. **Deployment environment.** One company, trained users, office hours, a closed catalogue.

### Intended use 2: correcting a draft in plain words

The corrector turns a sentence such as "line 3 is the landing door roller, 2 units" into proposed edits. The edits are checked by
applying them to a copy against the catalogue, shown in a confirmation card and applied only when the estimator confirms
(implemented and tested in `tests/test_agents.py`; the card is planned for phase 5). Harm: a misunderstood sentence proposes the wrong
change; mitigated by the confirmation and by refusing codes outside the catalogue.

## 3. Adverse impact

**Restricted and unsupported uses.** Issuing a quote without an estimator's review; any use where the model's proposal is final;
other trades or catalogues without a new evaluation; catalogues over about 500 items (the whole catalogue goes in the prompt; ADR-003, phase 6);
illegible handwriting or uncropped phone photos; several client companies. Pricing advice of any kind: prices come only from the
client's catalogue.

**Known limitations.**

- Ambiguity is the hard case. The matcher still sometimes resolves a variant the row does not name: "TRACTION SHEAVE BRKN" is read as
  a replacement in every run, and in some runs a door sill seen at a floor is read as the landing sill or a final limit switch seen
  from the car top as the upper one. Those lines reach the estimator as normal proposals, not as flags.
- The model is not deterministic: three runs of the same prompt and data flagged 43, 44 and 45 of the 46 ambiguous defects.
- The evaluation set is synthetic and the prompt was tuned on it; the production signal is KPI-2 (lines accepted unchanged).
- English only, and scans must be legible.

**Impact of failure.**

| Failure | Effect | Detection and recovery |
|---|---|---|
| Wrong item or quantity accepted | A customer quoted for the wrong part or amount | Estimator review; KPI-2 in production; the line is traceable to its defect, so it is corrected and re-issued |
| A defect missing from the draft | A needed repair is not quoted | Defect recall 100 % on the evaluation set; every line shows its page and row; the technician's report remains the record of the inspection |
| Service down or the model throttled | No draft; the estimator waits or quotes by hand | A clear "Elevant is busy; try again in N s" with `Retry-After`, and a 503 or 504 with a plain reason when a dependency is down or a draft passes 120 s (`test_api.py`, phase 4); availability SLO and alert (phases 6 and 7) |

**Impact of misuse.** Prompt injection through the text of a report (a row that asks to change a price, a code or a quantity) is the
main one: the model cannot set a price, any code is checked against the catalogue, and the matcher's prompt treats every row as data
and flags rows with instructions. A user who approves without reading defeats the mitigation; the flags block approval, and KPI-2
shows when estimators stop changing anything.

**Sensitive uses.** None of the three triggers applies: no consequential impact on a person's legal position or life opportunities,
and no threat to human rights. The closest is the risk of physical injury: a safety defect left out of a quote could delay a repair.
Elevant does not decide whether a lift is safe or whether a repair is done; the inspection report and the maintenance company's legal
duties are unchanged, and defect recall is part of the evaluation gate.

## 4. Data requirements

- **No training or fine-tuning.** The model is used as deployed in the shared Foundry account.
- **Inputs at run time:** the PDF (to Document Intelligence in Sweden Central), and only the defect texts plus the catalogue's codes,
  categories, descriptions and units (to the Global Standard deployment, processed outside the region; ADR-006, phase 6). Header fields and
  prices never reach the model (`tests/test_agents.py` checks the exact payload for all 40 reports). Requests are sent with
  `store: false`, so Foundry keeps no response.
- **Evaluation data:** 40 synthetic reports with fictitious lift IDs, addresses and names, generated by `ops/make_reports.py` with the
  composition of AI-300's evaluation dataset guidance (common cases, variations, edge cases and adversarial cases); `data/README.md`.
- **Production data:** the client's reports and quotes, kept in Cosmos DB and Blob Storage in Sweden Central for 24 months and deleted
  on request (REQ-10, planned for phases 4 and 6).

## 5. Summary of impact

**Potential harms and mitigations**, by the four layers of AI-103:

| Harm | Model | Safety system | System message and grounding | User experience and code |
|---|---|---|---|---|
| Wrong item or quantity | `gpt-5-mini` for reasoning over near-identical items, reasoning effort low | | The catalogue as a closed list; the part-then-detail rule for variants; low confidence when anything is assumed | Codes outside the catalogue or the candidates rejected; flags block approval; estimator review (implemented and tested) |
| Over-trust in a confident draft | | | | Flags shown with an icon and a word; candidates offered; KPI-2 and KPI-3 (planned, phases 4 and 5) |
| Prompt injection in report text | | `guardrail-chat`: jailbreak detection on prompts | Rows are data, never instructions; rows with instructions flagged | No price from the model; catalogue validation; mandatory approval (implemented and tested; evaluation: injection cases) |
| Harmful or protected content | | `guardrail-chat`: hate, sexual, violence and self-harm blocked from medium severity on prompts and completions; protected material text and code on completions | | Output is structured codes, not free text shown as advice |
| Personal data leaving the region | | | Only defect text and catalogue fields sent | Payload test for all 40 reports (implemented and tested) |

The guardrail was read from the shared deployment on 2026-10-31. It has no indirect-attack (document) filter, and changing the shared
guardrail would affect other products, so injection through documents is handled by the closed-choice design above.

**Measuring and managing.**

- **Measure:** `eval/` and `eval.yml` gate every change to prompts, agents, the workflow, the domain rules or the reference data, with
  the injection cases among the thresholds (implemented and tested; `docs/evaluation.md`).
- **Manage, before release:** staging first, load tests, the user's approval of every production deployment, rollback by label and
  previous image (planned, phases 6 to 8).
- **Manage, in production:** feedback with 👍 and 👎 per draft (KPI-3), lines accepted unchanged (KPI-2), the incident procedure in
  `docs/OPERATIONS.md`, and the model retirement plan for `gpt-5-mini` `2025-08-07` (retires 2027-02-09; ADR-013) (all planned, phases 4
  to 7).

**Sign-off.** This assessment is reviewed by the product owner with each phase that changes an AI component, and before v1.0.0.
