# Data

Everything in this folder is synthetic. Lift IDs, addresses, technicians and the company name (Fairholm Lifts) are fictitious.

## Reference data: the client's catalogue and quote template

`reference/` holds the files the client owns and changes without code (REQ-07). Each file is a version: its name gives the
version and its SHA-256 identifies the exact content.

| File | What it is |
|---|---|
| `catalogue-v1.xlsx` | 123 repair items in eight categories. Sheet `items`: `Code`, `Description`, `Category`, `Unit`, `Unit price (EUR)`, `Max quantity`. Sheet `terms`: the VAT rate in `B1` (21 %). |
| `quote-template-v1.docx` | The Word quote, filled with [docxtpl](https://docxtpl.readthedocs.io/). |

**How a version is used.** A new quote pins the highest version of each file when it is uploaded, and keeps it until it is approved:
a draft already in review keeps the catalogue and template it started with, and the Word document shows both. A file changed in
place under the same name is refused by its SHA-256, and the `reference` job of `ci.yml` fails any pull request that modifies or
deletes a released file. A change is always a new file, `catalogue-v2.xlsx` or `quote-template-v2.docx`, and it passes the
evaluation gate like a prompt change.

**Catalogue rules**, checked by `tests/test_data.py` for every version: unique codes without surrounding spaces, a description,
prices greater than zero in whole cents, a whole maximum quantity per quote and a VAT rate between 0 and 1. Quantities of items
measured in `m`, `m2`, `l` or `h` may have two decimals; every other unit is counted in whole numbers.

**Template fields**, for whoever edits the Word template:

| Field | Content |
|---|---|
| `quote`, `approved_on` | Quote ID and approval date |
| `header.lift_id`, `header.location`, `header.inspection_date`, `header.technician` | Report header, as reviewed |
| `lines`, inside `{%tr for line in lines %}` and `{%tr endfor %}` | One table row per kept line |
| `line.number`, `line.description`, `line.quantity`, `line.unit_price`, `line.amount` | The line as the customer reads it |
| `line.trace` | Catalogue code, catalogue version and the report page and row, or "added in review" |
| `subtotal`, `vat_rate`, `vat`, `total` | Amounts computed in code |
| `catalogue`, `catalogue_sha256`, `template` | The versions the quote used |

**How they were made.** Both files were prepared once for this repository with openpyxl and python-docx. From version 1 on they are
maintained as files in Excel and Word. No script regenerates them, because a regenerated file has a new SHA-256 and would no longer
match the quotes that used it.

## Inspection reports

`reports/` holds 40 synthetic inspection reports, and `../eval/datasets/truth.jsonl` holds what each one says, known by construction.
Both come from `ops/make_reports.py`, run from the repository root with the development requirements installed:

```
python -m ops.make_reports
```

The script reads the latest catalogue, uses a fixed seed (2081) and writes the same bytes on every run. It never touches
`reference/`.

**Composition**, following the evaluation dataset guidance of AI-300 (common cases, variations, edge cases and adversarial cases):

| | Count |
|---|---|
| Reports | 40: 14 grid table, 13 list form, 13 two-column branch form |
| Scanned | 10 (4 grid, 3 list, 3 branch): rendered at 150 dpi, rotated by up to 1.5 degrees, with noise and blur |
| Pages | 1 to 3; 5 to 20 defects per report |
| Defects | 535 |
| Common | 312: the catalogue description with a symptom and a location |
| Variations | 138 abbreviated in the technicians' shorthand (`LDG DR RLR 60 MM WRN`), plus three header vocabularies and three date formats |
| Edge cases | 46 ambiguous (the variant is missing, so two or three items fit) and 37 with no catalogue item: 15.5 % |
| Adversarial | 2 defects whose text tries to change the price or the code (`report-0111`, `report-0125`) |
| Incomplete headers | `report-0106` has no lift ID; `report-0131` has no technician |

**Truth format.** One JSON object per report: `report`, `layout`, `scanned`, `header` (ISO date; `null` for a missing field) and
`defects`. Each defect has `page` and `row` (the data row within that page's table, from 1), `number`, `text`, `component`,
`symptom`, `location`, `quantity`, `quantity_text`, `kind` (`common`, `abbreviated`, `ambiguous`, `no_match` or `injection`),
`item_code` (`null` when ambiguous or unmatched) and `candidates` (the items that fit).

**Recorded extractions.** `../eval/datasets/extracted/` holds what Document Intelligence (`prebuilt-layout`, API
`2024-11-30`, with key-value pairs) returned for each report, as `app/extraction.py` keeps it: the page count, the
key-value pairs with their confidence, and every table with its header rows and the page of each row. They were recorded
on 2026-10-31 from the shared Foundry account with `app.extraction.analyze`, so the tests and the evaluation on pull
requests read them without calling the service. Reading them back gives every header field and every defect's page and
row of the truth. `report-0134.json` is also the canned extraction the doubles return (`ELEVANT_DOUBLES=true`).

**Reports for the demo simulations:**

| Simulation | Report |
|---|---|
| S1 `clean-digital` | `report-0134`: grid table, digital, 12 defects, all with a catalogue item |
| S2 `scanned-abbreviations` | `report-0108`: list form, scanned, with abbreviations |
| S3 `ambiguous-resolved` | `report-0101`: two ambiguous defects |
| S4 `missing-header-no-match` | `report-0106`: no lift ID and one defect with no catalogue item |
| S5 `injection-flagged` | `report-0111`: a defect that tries to change its price |
| S6 `correct-approve-download` | `report-0110`: grid table, digital, 6 defects, corrected in plain words, approved and downloaded |
