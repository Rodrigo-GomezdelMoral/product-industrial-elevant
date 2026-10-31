import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app import agents
from app.domain import Catalogue, DomainError, Quote
from app.extraction import Layout, read
from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
PDF, EXTRACTED = ROOT / "data" / "reports" / "report-0134.pdf", ROOT / "eval" / "datasets" / "extracted"


@pytest.mark.parametrize("name", sorted(path.name for path in EXTRACTED.glob("*.json")))
async def test_the_matcher_sees_only_defect_text_and_codes(name: str, catalogue: Catalogue, scripted: Any) -> None:
    report = read(Layout.model_validate_json((EXTRACTED / name).read_text(encoding="utf-8")))
    client = scripted('{"matches": [')
    matches = await agents.match(client, report.defects, catalogue)
    instructions, rows = client.requests[0]
    listing = "".join(f"{i.code} | {i.category} | {i.description} | {i.unit}\n" for i in catalogue.items.values())
    assert instructions.endswith(f"## Catalogue catalogue-v1\n\ncode | category | description | unit\n{listing}")
    assert json.loads(rows) == [{"defect": number, "text": d.text} for number, d in enumerate(report.defects, 1)]
    assert not [value for value in report.header.model_dump().values() if value and value in instructions + rows]
    assert {match.reason for match in matches} == {"the matcher gave no usable answer for this defect"}


async def test_the_corrector_proposes_and_never_applies(drafted: Quote, catalogue: Catalogue, scripted: Any) -> None:
    item = {"action": "item", "line": 4, "code": "DOR-103", "quantity": None}
    quantity = {"action": "quantity", "line": 4, "code": None, "quantity": 3}
    invented = {"action": "add", "line": None, "code": "DOR-999", "quantity": 1}
    answers = [{"edits": [item, quantity]}, {"edits": [invented]}, {"edits": []}]
    client = scripted(*map(json.dumps, answers))
    proposed = await agents.correct(client, drafted, "line 4 is the 80 mm roller, 3 units", catalogue)
    assert [(e.action, e.code, e.quantity) for e in proposed] == [("item", "DOR-103", None), ("quantity", None, 3)]
    assert drafted.lines[3].model_dump(include={"item_code", "quantity"}) == {"item_code": "DOR-102", "quantity": 2}
    for message in ("DOR-999 is not in catalogue-v1", "no change found"):
        with pytest.raises(DomainError, match=message):
            await agents.correct(client, drafted, "add a mystery part", catalogue)
    sent = json.loads(client.requests[0][1])
    assert {key for line in sent["lines"] for key in line} == {"number", "expanded", "item_code", "quantity"}


async def test_doubles_are_deterministic_and_refused_in_production(catalogue: Catalogue) -> None:
    report = read(await agents.canned(PDF.read_bytes()))
    first = await agents.match(agents.Double(catalogue), report.defects, catalogue)
    assert first == await agents.match(agents.Double(catalogue), report.defects, catalogue)
    assert all(match.item_code in catalogue.items for match in first)
    with pytest.raises(ValidationError, match="refused"):
        Settings(env="production", doubles=True)
