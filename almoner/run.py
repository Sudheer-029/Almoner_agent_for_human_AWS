"""Close the month.

    python -m almoner.run                 # run the graph against Bedrock
    python -m almoner.run --dry-run       # deterministic layer only, no model calls

The dry run exists so the pipeline can be exercised - and demonstrated - without
a single token, and so the tests can assert the queue shape offline.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from decimal import Decimal

from . import core, ledger, loaders
from .money import usd
from .schemas import QueueItem

PERIOD = "August 2026"
ORG = "Kalyani Literacy Trust"


# ---------------------------------------------------------------------------
# Letter rendering: the model writes the language once, this fills the numbers.
# ---------------------------------------------------------------------------

FALLBACK_TEMPLATES = {
    "cash": (
        "Dear {donor},\n\nThank you for your gift of {amount}, received on {date}. "
        "No goods or services were provided to you in return for this contribution.\n\n"
        "With gratitude,\n{org}"
    ),
    "in_kind": (
        "Dear {donor},\n\nThank you for your donation of {description}, received on {date}. "
        "In accordance with IRS requirements we describe the property received but do not "
        "assign it a value; determining its fair market value is your responsibility.\n\n"
        "With gratitude,\n{org}"
    ),
    "quid_pro_quo": (
        "Dear {donor},\n\nThank you for your payment of {amount} on {date}. "
        "You received goods or services with a fair market value of {fmv}. "
        "Only {deductible} of your payment is deductible as a charitable contribution.\n\n"
        "With gratitude,\n{org}"
    ),
}


def render_letter(gift: loaders.Gift, template: str) -> str:
    d = core.deductible_portion(gift)
    return template.format(
        donor=gift.donor_name,
        amount=usd(gift.gross),
        date=gift.gift_date.strftime("%d %B %Y"),
        org=ORG,
        description=gift.notes or "donated property",
        fmv=usd(d.fmv_received) if d.fmv_received is not None else "[to be confirmed]",
        deductible=usd(d.deductible) if d.deductible is not None else "[to be confirmed]",
    )


def template_for(gift: loaders.Gift) -> str:
    if gift.gift_type == "in_kind":
        return "in_kind"
    if gift.gift_type == "event_ticket" or gift.goods_fmv:
        return "quid_pro_quo"
    return "cash"


# ---------------------------------------------------------------------------
# The deterministic pass. This is what decides the counter.
# ---------------------------------------------------------------------------

GRANT = core.GrantRule(
    grant_id="BLF-2026",
    capital_unit_cap=Decimal("1000.00"),
    allowable_categories=["program_delivery", "program_materials", "training"],
)


def build_queue(rule: core.GrantRule = GRANT) -> list[QueueItem]:
    bank, gifts, expenses = loaders.load_bank(), loaders.load_gifts(), loaders.load_expenses()
    items: list[QueueItem] = []

    for m in core.match_deposits(bank, gifts):
        if m.needs_human:
            cands = ", ".join(m.candidates) or "none"
            items.append(QueueItem(
                ref=f"BANK-{m.line_no}", kind="deposit", disposition="needs_your_decision",
                headline=f"{m.description} for {usd(m.amount)} on {m.posted} is unidentified",
                reason=m.basis, node="reconciler",
                options=[
                    {"label": f"Credit it to pledge {cands}",
                     "consequence": "That donor is acknowledged and the pledge is marked paid."},
                    {"label": "Record as an unidentified gift",
                     "consequence": "The deposit is booked but no acknowledgement is issued."},
                ],
            ))
        else:
            items.append(QueueItem(
                ref=f"BANK-{m.line_no}", kind="deposit", disposition="auto_cleared",
                headline=f"{m.description} for {usd(m.amount)} reconciled",
                reason=m.basis, node="reconciler",
            ))

    for g in (g for g in gifts if g.is_settled):
        d = core.deductible_portion(g)
        if not d.determinable:
            items.append(QueueItem(
                ref=g.gift_id, kind="gift", disposition="needs_your_decision",
                headline=f"{g.donor_name}: {usd(g.gross)} — deductible portion unknown",
                reason=d.basis, node="acknowledger",
                options=[
                    {"label": "Supply the fair market value received",
                     "consequence": "The letter states the deductible portion correctly."},
                    {"label": "Treat as a purchase, not a gift",
                     "consequence": "No acknowledgement is issued for this payment."},
                ],
            ))
        else:
            items.append(QueueItem(
                ref=g.gift_id, kind="gift", disposition="drafted_for_approval",
                headline=f"{g.donor_name}: acknowledgement drafted",
                reason=d.basis, node="acknowledger",
            ))

    for e in expenses:
        f = core.evaluate_expense(e, rule)
        if f.needs_human:
            items.append(QueueItem(
                ref=e.expense_id, kind="expense", disposition="needs_your_decision",
                headline=f"{e.vendor}: {usd(e.amount)} breaches clause {f.clause}",
                reason=f.basis, citation=f"Clause {f.clause}", node="compliance",
                options=[
                    {"label": "Seek the funder's retrospective approval",
                     "consequence": "The cost stays on the grant if the funder agrees in writing."},
                    {"label": f"Move {usd(e.amount)} to unrestricted funds",
                     "consequence": "The grant is clean; general funds absorb the cost."},
                ],
            ))
        else:
            items.append(QueueItem(
                ref=e.expense_id, kind="expense", disposition="auto_cleared",
                headline=f"{e.vendor}: {usd(e.amount)} cleared",
                reason=f.basis, node="compliance",
            ))

    return items


def persist(items: list[QueueItem], run_id: str, templates: dict | None = None) -> dict:
    conn = ledger.connect()
    ledger.start_run(conn, run_id, PERIOD)
    for it in items:
        ledger.add_queue_item(conn, run_id, it.model_dump())

    tpl = templates or FALLBACK_TEMPLATES
    for g in loaders.load_gifts():
        if g.is_settled and core.deductible_portion(g).determinable:
            ledger.add_letter(conn, run_id, g.gift_id, g.donor_name,
                              render_letter(g, tpl[template_for(g)]))

    counts = ledger.finalise_run(conn, run_id)
    conn.close()
    return counts


# ---------------------------------------------------------------------------
# The agent pass.
# ---------------------------------------------------------------------------

async def run_graph(run_id: str) -> dict:
    from .agents import build_graph, month_close_task

    conn = ledger.connect()
    ledger.start_run(conn, run_id, PERIOD)

    graph = build_graph()
    result = await graph.invoke_async(month_close_task(PERIOD))

    reports: dict = {}
    for node_id, node_result in result.results.items():
        inner = getattr(node_result, "result", None)
        structured = getattr(inner, "structured_output", None)
        if structured is not None:
            reports[node_id] = structured
        ledger.trace(conn, run_id, node_id, "completed",
                     structured.summary if structured and hasattr(structured, "summary") else "")

    ledger.trace(conn, run_id, "graph", "usage", str(result.accumulated_usage))
    conn.close()
    return reports


def main() -> None:
    ap = argparse.ArgumentParser(description="Close the month for " + ORG)
    ap.add_argument("--dry-run", action="store_true",
                    help="deterministic layer only; no model calls, no cost")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or f"run-{uuid.uuid4().hex[:8]}"
    items = build_queue()

    templates = None
    if not args.dry_run:
        reports = asyncio.run(run_graph(run_id))
        ack = reports.get("acknowledger")
        if ack is not None:
            templates = ack.templates.model_dump()
        for node, report in reports.items():
            print(f"  [{node}] {getattr(report, 'summary', '')}")

    counts = persist(items, run_id, templates)

    print(f"\n{ORG} — {PERIOD}   run {run_id}")
    print(f"  {counts['handled']} handled, {counts['escalated']} need you\n")
    for it in items:
        if it.disposition == "needs_your_decision":
            print(f"  ! {it.ref:9} {it.headline}")
            print(f"    {it.reason}")


if __name__ == "__main__":
    main()
