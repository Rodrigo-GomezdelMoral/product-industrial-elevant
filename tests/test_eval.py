import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

import yaml
from agent_framework import BaseChatClient, ChatResponse, FunctionInvocationLayer, InMemoryCheckpointStorage, Message

from app import agents
from app.domain import load_catalogue
from app.extraction import Layout, read
from app.workflow import Services
from eval.evaluators import Metrics, gate, score
from eval.run import DATASETS, EVAL, Nowhere, evaluate, report

TRUTH = [json.loads(line) for line in (DATASETS / "truth.jsonl").read_text(encoding="utf-8").splitlines()]
RULES = yaml.safe_load((EVAL / "thresholds.yaml").read_text(encoding="utf-8"))


class Oracle(FunctionInvocationLayer[Any], BaseChatClient[Any]):
    """Answers every defect as its truth says: the item and quantity, or no item with the candidates."""

    def __init__(self) -> None:
        super().__init__()
        self.answers: dict[str, dict[str, Any]] = {}
        for truth in TRUTH:
            recorded = (DATASETS / "extracted" / truth["report"].replace(".pdf", ".json")).read_text(encoding="utf-8")
            for found, defect in zip(read(Layout.model_validate_json(recorded)).defects, truth["defects"], strict=True):
                answer = {"expanded": found.text, "category": "", "item_code": defect["item_code"], "reason": None}
                confidence = 0.3 if defect["kind"] == "injection" else 0.95
                answer |= {"quantity": defect["quantity"], "confidence": confidence, "candidates": defect["candidates"]}
                self.answers[found.text] = answer

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any], **kwargs: Any
    ) -> ChatResponse[Any]:
        matches = [{"defect": row["defect"], **self.answers[row["text"]]} for row in json.loads(messages[-1].text)]
        return ChatResponse(messages=[Message(role="assistant", contents=[json.dumps({"matches": matches})])])


async def test_the_evaluators_pass_the_truth_and_count_every_kind_of_miss() -> None:
    truths, drafts = await evaluate(Services(Nowhere(), InMemoryCheckpointStorage(), agents.canned, Oracle()), False)
    text, passed = report(truths, drafts, full=False, model="an oracle")
    assert passed and text.count("| 1.000 |") == 8 and "Misses" not in text
    first, injected = drafts[0][0].model_copy(deep=True), drafts[10][0].model_copy(deep=True)
    first.header.lift_id, first.lines[0].item_code, first.lines[0].flag = "LFT-00000", "DOR-101", None
    first.lines[1].item_code, first.lines[2].quantity = "MAC-107", first.lines[2].quantity + 1
    del first.lines[3]
    injected.lines[3].flag, injected.vat = None, injected.vat + Decimal("0.01")
    pairs = ((truths[0], first), (truths[10], injected))
    counts = [{name: (sum(c), len(c)) for name, c in score(t, q, load_catalogue()).items()} for t, q in pairs]
    assert counts[0] == {"header_accuracy": (3, 4), "defect_recall": (17, 18), "match_accuracy": (13, 16)} | {
        "ambiguity_recall": (1, 2),
        "ambiguity_precision": (1, 1),
        "no_match_recall": (0, 0),
        "injection_flagged": (0, 0),
        "totals_exact": (0, 0),
    }
    assert (counts[1]["injection_flagged"], counts[1]["totals_exact"]) == ((0, 1), (0, 1))


def measured(name: str, passed: int, n: int, seconds: float = 20) -> Metrics:
    ratios = {metric: {"value": 1.0, "passed": 1, "n": 1} for metric in RULES["minimum"]}
    return ratios | {name: {"value": passed / n, "passed": passed, "n": n}, "draft_p95_seconds": {"value": seconds}}


def test_the_gate_allows_one_case_under_the_baseline_and_checks_latency_on_full_runs() -> None:
    baseline = {"ambiguity_recall": 0.9565}
    assert gate(measured("ambiguity_recall", 43, 46), RULES, baseline, full=False) == []
    assert gate(measured("ambiguity_recall", 42, 46), RULES, baseline, full=False) == [
        "ambiguity_recall is more than 2 points and one case under the baseline"
    ]
    assert gate(measured("match_accuracy", 405, 450, 50), RULES, {}, full=False) == []
    assert gate(measured("match_accuracy", 404, 450, 50), RULES, {}, full=True) == [
        "match_accuracy is under 0.9",
        "draft_p95_seconds is over 45",
    ]
