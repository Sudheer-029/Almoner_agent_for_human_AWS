"""Almoner on Amazon Bedrock AgentCore Runtime."""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("ALMONER_DB", "/tmp/almoner.db")
os.environ.setdefault("ALMONER_PROVIDER", "mantle")
os.environ.setdefault("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from almoner.run import PERIOD, build_queue, persist  # noqa: E402

app = BedrockAgentCoreApp()


def _serialise(items):
    return [
        {
            "ref": i.ref, "kind": i.kind, "disposition": i.disposition,
            "headline": i.headline, "reason": i.reason, "citation": i.citation,
            "options": [{"label": o.label, "consequence": o.consequence} for o in i.options],
        }
        for i in items
    ]


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Close one month's books and return the review queue."""
    period = payload.get("period", PERIOD)
    dry_run = bool(payload.get("dry_run", False))
    run_id = f"run-{uuid.uuid4().hex[:8]}"

    items = build_queue()
    summaries = {}
    templates = None

    if not dry_run:
        from almoner.run import run_graph
        reports = asyncio.run(run_graph(run_id))
        for node, report in reports.items():
            summaries[node] = getattr(report, "summary", "")
        ack = reports.get("acknowledger")
        if ack is not None:
            templates = ack.templates.model_dump()

    counts = persist(items, run_id, templates)
    needs = [i for i in items if i.disposition == "needs_your_decision"]

    return {
        "run_id": run_id, "period": period,
        "organisation": "Kalyani Literacy Trust",
        "reviewed": len(items),
        "handled": counts["handled"],
        "needs_your_decision": counts["escalated"],
        "sent_to_anyone": 0,
        "node_summaries": summaries,
        "escalations": _serialise(needs),
        "mode": "deterministic-only" if dry_run else "full graph",
    }


if __name__ == "__main__":
    app.run()
