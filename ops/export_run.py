import argparse
import asyncio
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_framework import WorkflowCheckpoint
from agent_framework_azure_cosmos import CosmosCheckpointStorage
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import AzureCliCredential
from azure.storage.blob.aio import BlobServiceClient

from app.domain import Edit, Quote, load_catalogue
from app.workflow import STATUS, VERSION

WEB, STAGING = Path("web"), ("cosmos-elevant-stg-swc", "stelevantstgswc", "appi-elevant-stg-swc", "rg-elevant-stg-swc")
REQUESTS = (
    "requests | where url has '{id}' and success == true and name has_any ('/review', '/corrections')"
    " | order by timestamp asc | project tostring(split(name, '/')[-1]), tostring(timestamp), duration"
)
Step = dict[str, Any]


def ms(start: datetime, end: datetime | None) -> int:
    return round(((end or start) - start).total_seconds() * 1000)


def at(value: str) -> datetime:
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00"))


def scrubbed(quote: Quote) -> Step:
    quote.approved_by = quote.approved_by and "Staging manager"
    for event in quote.events:
        event.by = "Staging manager" if event.action == "approve" else "Staging estimator"
    return quote.model_dump(mode="json", exclude={"request_id", "checkpoint_id"})


def statuses(draft: Quote, checkpoints: list[WorkflowCheckpoint]) -> list[tuple[str, int]]:
    first: dict[int, datetime] = {}
    for checkpoint in checkpoints:
        first.setdefault(checkpoint.iteration_count, at(checkpoint.timestamp))
    marks = [draft.created_at, first[1], first[2], draft.drafted_at or first[2]]
    texts = ["Reading the report", STATUS["match"].format(n=sum(1 for line in draft.lines if line.defect))]
    return [(t, ms(a, b)) for t, a, b in zip([*texts, STATUS["price"]], marks, marks[1:], strict=False)]


def steps(final: Quote, paused: list[WorkflowCheckpoint]) -> list[Step]:
    pauses = [(at(c.timestamp), next(iter(c.pending_request_info_events.values())).data) for c in paused]
    events, result = [event for event in final.events if event.action != "approve"], list[Step]()
    for stamp, data in pauses[1:]:
        taken, events = [e for e in events if e.at <= stamp], [e for e in events if e.at > stamp]
        if not taken:
            raise SystemExit("a refused review answer cannot be replayed: record the run again without it")
        edits = [Edit.model_validate_json(e.detail).model_dump(mode="json", exclude_none=True) for e in taken]
        quote, waited = scrubbed(Quote.model_validate(data["quote"])), ms(taken[0].at, stamp)
        result.append({"edits": edits, "approve": False, "ms": waited, "quote": quote, "error": data["error"]})
    if final.state == "approved":
        result.append({"edits": [], "approve": True, "ms": 0, "quote": scrubbed(final), "error": None})
    return result


def timed(quote_id: str, recorded: list[Step], text: str | None) -> list[Step]:
    command = [shutil.which("az") or "az", "monitor", "app-insights", "query", "--app", STAGING[2], "-g", STAGING[3]]
    tail = "tables[0].rows", "--offset", "30d", "-o", "json"
    query = [*command, "--analytics-query", REQUESTS.format(id=quote_id), "--query", *tail]
    rows = [(kind, at(when), round(took)) for kind, when, took in json.loads(subprocess.check_output(query, text=True))]
    reviews, asked = [row for row in rows if row[0] == "review"], [row for row in rows if row[0] == "corrections"]
    for step in recorded:
        before = [row for row in reviews if row[1] <= at(step["quote"]["events"][-1]["at"])]
        step["ms"], reviews = (before[-1][2] if before else step["ms"]), reviews[len(before) :]
    if text and not asked:
        raise SystemExit("the correction is not in Application Insights yet: export again in a few minutes")
    later = [s for s in recorded if s["edits"] and asked and at(s["quote"]["events"][-1]["at"]) > asked[-1][1]]
    if text and not later:
        raise SystemExit("no confirmed edit follows the correction: record the run again and confirm the proposal")
    return [{"text": text, "edits": later[0]["edits"], "ms": asked[-1][2]}] if text else []


async def export(args: argparse.Namespace) -> Step:
    credential = AzureCliCredential()
    async with credential, CosmosClient(f"https://{STAGING[0]}.documents.azure.com:443/", credential) as cosmos:
        database = cosmos.get_database_client("elevant")
        item = await database.get_container_client("quotes").read_item(args.quote, partition_key=args.quote)
        final = Quote.model_validate(item)
        storage = CosmosCheckpointStorage(container_client=database.get_container_client("checkpoints"))
        found = await storage.list_checkpoints(workflow_name=f"{VERSION}-{final.id}")
        if final.state == "approved":
            async with BlobServiceClient(f"https://{STAGING[1]}.blob.core.windows.net", credential) as blobs:
                document = await (await blobs.get_blob_client("quotes", f"{final.id}.docx").download_blob()).readall()
            (WEB / "public" / "demo" / f"{args.simulation}.docx").write_bytes(document)
    checkpoints = sorted(found, key=lambda checkpoint: checkpoint.timestamp)
    paused = [checkpoint for checkpoint in checkpoints if checkpoint.pending_request_info_events]
    if not paused:
        raise SystemExit(f"no checkpoints for {final.id}: expired or deleted")
    draft = Quote.model_validate(next(iter(paused[0].pending_request_info_events.values())).data["quote"])
    recorded, items = steps(final, paused), load_catalogue(final.catalogue).items.values()
    catalogue = [item.model_dump(mode="json", include={"code", "description", "unit", "unit_price"}) for item in items]
    corrections = timed(final.id, recorded, args.correction) if recorded else []
    head = {"title": args.title, "file": args.file} | ({"suggestion": args.suggestion} if args.suggestion else {})
    body = {"status": statuses(draft, checkpoints), "draft": scrubbed(draft), "catalogue": catalogue}
    return head | body | {"document": f"{args.simulation}.docx", "steps": recorded, "corrections": corrections}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export one staging run as a demo recording (operator access).")
    for name in ("quote", "simulation", "title", "file", "--suggestion", "--correction"):
        parser.add_argument(name)
    args = parser.parse_args()
    (WEB / "public" / "demo").mkdir(parents=True, exist_ok=True)
    recording = asyncio.run(export(args))
    (WEB / "fixtures").mkdir(exist_ok=True)
    (WEB / "fixtures" / f"{args.simulation}.json").write_text(json.dumps(recording, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
