import os
import uuid
from pathlib import Path

from locust import HttpUser, between, events, task
from locust.env import Environment

REPORT = (Path(__file__).resolve().parent.parent / "data" / "reports" / "report-0134.pdf").read_bytes()
SCENARIO = os.environ.get("LOAD_SCENARIO", "normal")
SLA_P95_MS, SLA_FAILURE_RATIO = 60_000, 0.005


class Estimator(HttpUser):
    """Uploads reports and opens the list as the staging CI principal, which holds Quote.Estimator."""

    wait_time = between(15, 25) if SCENARIO == "real" else between(2, 6)

    def on_start(self) -> None:
        self.client.headers["Authorization"] = f"Bearer {os.environ['LOAD_TOKEN']}"

    @task(3)
    def upload(self) -> None:
        pdf = REPORT + f"\n%{uuid.uuid4().hex}\n".encode()
        headers, name = {"Content-Type": "application/pdf"}, "upload and draft"
        with self.client.post("/api/quotes", data=pdf, headers=headers, name=name, catch_response=True) as answer:
            if "event: quote" not in answer.text:
                answer.failure("the stream ended without a draft")

    @task(1)
    def browse(self) -> None:
        self.client.get("/api/quotes", name="list quotes")


def hold_to_the_sla(environment: Environment, **_: object) -> None:
    drafts, total = environment.stats.get("upload and draft", "POST"), environment.stats.total
    missed = total.fail_ratio > SLA_FAILURE_RATIO or drafts.get_response_time_percentile(0.95) > SLA_P95_MS
    environment.process_exit_code = int(missed and SCENARIO != "stress")


events.quitting.add_listener(hold_to_the_sla)
