import json
from pathlib import Path
from typing import Any, cast

import pytest
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.exceptions import HttpResponseError, ODataV4Format

from app.extraction import Layout, Pair, RejectedFileError, analyze, layout, read, read_header

DATASETS = Path(__file__).resolve().parent.parent / "eval" / "datasets"
TRUTH = [json.loads(line) for line in (DATASETS / "truth.jsonl").read_text(encoding="utf-8").splitlines()]


class Analyzer:
    def __init__(self, pages: int, inner: str | None) -> None:
        self.pages, self.inner, self.asked = pages, inner, dict[str, Any]()

    async def begin_analyze_document(self, *args: Any, **kwargs: Any) -> "Analyzer":
        self.asked = kwargs
        if self.inner:
            error = HttpResponseError("refused by the service")
            error.error = ODataV4Format({"code": "InvalidRequest", "innererror": {"code": self.inner}})
            raise error
        return self

    async def result(self) -> AnalyzeResult:
        return AnalyzeResult({"pages": [{"pageNumber": page} for page in range(1, self.pages + 1)]})


@pytest.mark.parametrize("truth", TRUTH, ids=[truth["report"] for truth in TRUTH])
def test_reads_the_header_and_every_defect_of_each_layout(truth: dict[str, Any]) -> None:
    recorded = (DATASETS / "extracted" / truth["report"].replace(".pdf", ".json")).read_text(encoding="utf-8")
    report = read(Layout.model_validate_json(recorded))
    assert (report.header.model_dump(), report.flags) == (truth["header"], {})
    assert [(defect.page, defect.row) for defect in report.defects] == [(d["page"], d["row"]) for d in truth["defects"]]
    for defect, expected in zip(report.defects, truth["defects"], strict=True):
        assert expected["component"].split()[0].strip(",").lower() in defect.text.lower()


def test_flags_unsure_header_fields_and_leaves_missing_ones_empty() -> None:
    pairs = [
        Pair(key="Lift ID:", value="LFT-10001", confidence=0.5),
        Pair(key="Date of visit", value="31/31/2026", confidence=0.99),
        Pair(key="Engineer", value=None, confidence=0.99),
        Pair(key="Location", value="floor 2\npit", confidence=0.95),
    ]
    header, flags = read_header(pairs)
    assert header.model_dump(exclude_none=True) == {"lift_id": "LFT-10001", "inspection_date": "31/31/2026"}
    assert flags == {"lift_id": "low_confidence", "inspection_date": "low_confidence"}


def test_keeps_the_page_of_every_row_and_skips_header_rows() -> None:
    rows = [("Ref", "Finding", 1), ("F-01", "pit: Brake coil worn (qty 1)", 1), ("F-02", "car: Fan noisy (qty 2)", 2)]
    cells = [
        {"rowIndex": row, "columnIndex": column, "content": text, "kind": "columnHeader" if row == 0 else "content"}
        | {"boundingRegions": [{"pageNumber": page, "polygon": []}]}
        for row, (*texts, page) in enumerate(rows)
        for column, text in enumerate(texts)
    ]
    found = layout(AnalyzeResult({"pages": [{}, {}], "tables": [{"rowCount": 3, "columnCount": 2, "cells": cells}]}))
    assert found.tables[0].model_dump() == {"header": 1, "rows": [list(row[:2]) for row in rows], "pages": [1, 1, 2]}
    assert [(d.page, d.row, d.text) for d in read(found).defects] == [(1, 1, rows[1][1]), (2, 1, rows[2][1])]


@pytest.mark.parametrize(
    ("pdf", "pages", "inner", "refused", "message"),
    [
        (b"PK\x03\x04", 1, None, RejectedFileError, "not a PDF"),
        (b"%PDF-" + bytes(10 * 1024 * 1024), 1, None, RejectedFileError, "over 10 MB"),
        (b"%PDF-1.7", 11, None, RejectedFileError, "over 10 pages"),
        (b"%PDF-1.7", 1, "InvalidContent", RejectedFileError, "could not be read"),
        (b"%PDF-1.7", 1, "ModelNotFound", HttpResponseError, "refused by the service"),
    ],
)
async def test_rejects_files_it_does_not_read(
    pdf: bytes, pages: int, inner: str | None, refused: type[Exception], message: str
) -> None:
    analyzer = Analyzer(pages, inner)
    with pytest.raises(refused, match=message):
        await analyze(cast(DocumentIntelligenceClient, analyzer), pdf)
    assert analyzer.asked.get("pages", "1-11") == "1-11"
