import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from app.domain import (
    REFERENCE,
    Catalogue,
    Defect,
    DomainError,
    Edit,
    Match,
    Quote,
    approve,
    draft,
    load_catalogue,
    new_quote,
    review,
)

DEFECT = Defect(page=1, row=1, text="Landing door roller worn")
NAN, INF = float("nan"), float("inf")
DOORS = ("DOR-101", "DOR-102", "DOR-103")


def test_amounts_vat_and_totals_round_half_up_in_code(drafted: Quote, catalogue: Catalogue) -> None:
    assert [line.amount for line in drafted.lines] == [Decimal("93.63"), Decimal("18.87"), None, Decimal("43.40")]
    quote = review(drafted, [Edit(action="remove", line=4)], "estimator-1", catalogue)
    assert (quote.subtotal, quote.vat, quote.total) == (Decimal("112.50"), Decimal("23.63"), Decimal("136.13"))


@pytest.mark.parametrize(
    ("given", "flag", "candidates", "priced"),
    [
        ({"code": "ZZZ-001"}, "invalid_code", [], False),
        ({"code": "DOR-104", "candidates": (*DOORS, "DOR-104")}, "invalid_code", list(DOORS), False),
        ({"code": None, "candidates": ("DOR-101", "DOR-101", "MAC-999", "DOR-102")}, "ambiguous", DOORS[:2], False),
        ({"code": None}, "no_match", [], False),
        ({"code": "DOR-102", "confidence": NAN}, "low_confidence", [], True),
        ({"code": "DOR-102", "confidence": 0.5, "candidates": DOORS[1::-1]}, "ambiguous", list(DOORS[1::-1]), False),
        ({"code": "DOR-102", "quantity": 50, "confidence": 0.2}, "low_confidence", [], False),
        ({"code": "DOR-102", "quantity": INF}, "invalid_quantity", [], False),
        ({"code": "DOR-102", "quantity": 2.5}, "invalid_quantity", [], False),
    ],
)
def test_model_output_is_checked_against_the_catalogue(
    given: dict[str, Any],
    flag: str,
    candidates: list[str],
    priced: bool,
    match: Callable[..., Match],
    catalogue: Catalogue,
) -> None:
    line = draft(new_quote("q-0002"), [(DEFECT, match(**given))], catalogue).lines[0]
    assert (line.flag, line.candidates, line.amount is not None) == (flag, list(candidates), priced)


def test_review_updates_totals_and_records_who_and_when(
    drafted: Quote, catalogue: Catalogue, match: Callable[..., Match]
) -> None:
    edits = [Edit(action="item", line=3, code="ELE-106"), Edit(action="quantity", line=1, quantity=3)]
    quote = review(drafted, [*edits, Edit(action="add", code="LAB-102", quantity=1)], "estimator-1", catalogue)
    assert [line.amount for line in quote.lines] == [Decimal(n) for n in ("112.35", "18.87", "17.60", "43.40", "56.20")]
    assert quote.subtotal == Decimal("248.42")
    assert [(e.by, e.action) for e in quote.events] == [("estimator-1", a) for a in ("item", "quantity", "add")]
    assert [line.outcome for line in quote.lines] == ["changed", "proposed", "changed", "proposed", "added"]
    assert (drafted.subtotal, drafted.events) == (Decimal("155.90"), [])
    risky = draft(new_quote("q-0005"), [(DEFECT, match("DOR-102", 50, 0.2))], catalogue)
    lowered = review(risky, [Edit(action="quantity", line=1, quantity=2)], "e", catalogue)
    assert lowered.lines[0].flag == "low_confidence"
    wrong = [Edit(action="accept", line=3), Edit(action="item", line=1, code="X"), Edit(action="remove", line=9)]
    wrong += [Edit(action="quantity", line=1, quantity=NAN), Edit(action="header", field="location", value="  ")]
    messages = ("needs an item", "X is not", "line 9", "greater than zero", "needs a value")
    for edit, message in zip(wrong, messages, strict=True):
        with pytest.raises(DomainError, match=message):
            review(drafted, [edit], "estimator-1", catalogue)


def test_approval_waits_for_every_flag_then_the_quote_is_read_only(drafted: Quote, catalogue: Catalogue) -> None:
    drafted.header.lift_id = None
    with pytest.raises(DomainError, match="lift_id: missing; line 3: ambiguous; line 4: low_confidence"):
        approve(drafted, "estimator-1", catalogue)
    with pytest.raises(DomainError, match="the quote has no lines"):
        approve(review(drafted, [Edit(action="remove", line=n) for n in range(1, 5)], "e", catalogue), "e", catalogue)
    edits = [Edit(action="header", field="lift_id", value="LFT-41732"), Edit(action="item", line=3, code="ELE-105")]
    edits.append(Edit(action="item", line=4, code="DOR-102"))
    approved = approve(review(drafted, edits, "e", catalogue), "e", catalogue)
    assert (approved.state, approved.approved_by, approved.approved_at is not None) == ("approved", "e", True)
    assert [line.outcome for line in approved.lines] == ["accepted", "accepted", "changed", "accepted"]
    with pytest.raises(DomainError, match="approved and can no longer change"):
        review(approved, [Edit(action="remove", line=1)], "e", catalogue)
    with pytest.raises(DomainError, match="approved and already has a draft"):
        draft(approved, [], catalogue)


def test_drafts_in_review_keep_their_catalogue_version(tmp_path: Path, match: Callable[..., Match]) -> None:
    for name in ("catalogue-v1.xlsx", "quote-template-v1.docx"):
        shutil.copy(REFERENCE / name, tmp_path)
    in_review = draft(new_quote("q-0003", tmp_path), [(DEFECT, match("DOR-101"))], load_catalogue(folder=tmp_path))
    workbook = load_workbook(tmp_path / "catalogue-v1.xlsx")
    workbook["items"]["E2"] = 20
    workbook.save(tmp_path / "catalogue-v2.xlsx")
    workbook.save(tmp_path / "catalogue-v3 (copy).xlsx")
    fresh = draft(new_quote("q-0004", tmp_path), [(DEFECT, match("DOR-101"))], load_catalogue(folder=tmp_path))
    pinned = load_catalogue(in_review.catalogue, tmp_path)
    kept = review(in_review, [Edit(action="quantity", line=1, quantity=2)], "e", pinned)
    assert (fresh.catalogue.name, fresh.template.name) == ("catalogue-v2", "quote-template-v1")
    assert [fresh.lines[0].amount, kept.lines[0].amount] == [Decimal("20.00"), Decimal("36.80")]
    assert kept.catalogue.name == "catalogue-v1"
    with pytest.raises(DomainError, match="priced with catalogue-v1, not catalogue-v2"):
        review(in_review, [], "e", load_catalogue(folder=tmp_path))
    workbook.save(tmp_path / "catalogue-v1.xlsx")
    with pytest.raises(DomainError, match="catalogue-v1 changed after this quote used it"):
        load_catalogue(in_review.catalogue, tmp_path)
