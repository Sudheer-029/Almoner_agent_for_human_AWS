"""The tools the agents are allowed to call.

Every one of these is a thin wrapper over a pure function in core.py. The
system prompts tell each agent, in terms, that it may not compute a figure
itself - if it needs a number it calls a tool, and if no tool provides it,
that is a question for a human.
"""

from __future__ import annotations

import json
from decimal import Decimal

from strands import tool

from . import core, loaders
from .money import compute_fee as _compute_fee
from .money import money, net_of_fees as _net_of_fees


def _json(obj) -> str:
    def default(o):
        if isinstance(o, Decimal):
            return f"{o:.2f}"
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, default=default, indent=None)


# --- data access ----------------------------------------------------------

@tool
def list_bank_credits() -> str:
    """Every credit on the bank statement for the period, as JSON."""
    return _json([
        {"line_no": b.line_no, "posted": b.posted, "description": b.description,
         "amount": b.credit}
        for b in loaders.load_bank() if b.is_credit
    ])


@tool
def list_gifts() -> str:
    """Every donation record for the period, as JSON, including unpaid pledges."""
    return _json([
        {"gift_id": g.gift_id, "date": g.gift_date, "donor": g.donor_name,
         "gross": g.gross, "net": g.net, "channel": g.channel, "type": g.gift_type,
         "designation": g.designation, "goods_fmv": g.goods_fmv or None,
         "status": g.status, "notes": g.notes}
        for g in loaders.load_gifts()
    ])


@tool
def list_expenses() -> str:
    """Every expense for the period, as JSON, with the fund each is charged to."""
    return _json([
        {"expense_id": e.expense_id, "date": e.expense_date, "vendor": e.vendor,
         "description": e.description, "amount": e.amount, "fund": e.fund,
         "category": e.category}
        for e in loaders.load_expenses()
    ])


@tool
def read_grant_agreement() -> str:
    """Full text of the grant agreement. Read the clauses; do not summarise them away."""
    return loaders.read_grant_agreement()


# --- arithmetic the model is forbidden to do itself -----------------------

@tool
def compute_fee(gross_amount: str) -> str:
    """Processing fee on an online gift of `gross_amount` (decimal string)."""
    return f"{_compute_fee(gross_amount):.2f}"


@tool
def net_of_fees(gross_amount: str) -> str:
    """What lands in the bank for an online gift of `gross_amount` (decimal string)."""
    return f"{_net_of_fees(gross_amount):.2f}"


@tool
def match_deposits() -> str:
    """Reconcile every bank credit against the donation records.

    Returns one row per credit with status 'matched', 'ambiguous' (a plausible
    candidate exists but cannot be confirmed from the records) or 'unmatched'.
    An ambiguous row is never to be resolved by guessing: escalate it.
    """
    matches = core.match_deposits(loaders.load_bank(), loaders.load_gifts())
    return _json([
        {"line_no": m.line_no, "posted": m.posted, "description": m.description,
         "amount": m.amount, "status": m.status, "gift_ids": m.gift_ids,
         "candidates": m.candidates, "basis": m.basis}
        for m in matches
    ])


@tool
def deductible_portion(gift_id: str) -> str:
    """How much of one gift the donor may deduct.

    `determinable: false` means the figure cannot be computed from the records -
    that is an escalation, not an invitation to estimate.
    """
    gift = next((g for g in loaders.load_gifts() if g.gift_id == gift_id), None)
    if gift is None:
        return _json({"error": f"No gift {gift_id}"})
    d = core.deductible_portion(gift)
    return _json({
        "gift_id": d.gift_id, "gross": d.gross, "fmv_received": d.fmv_received,
        "deductible": d.deductible, "determinable": d.determinable, "basis": d.basis,
    })


@tool
def test_expense_against_grant(
    expense_id: str,
    grant_id: str,
    capital_unit_cap: str,
    allowable_categories: list[str],
    cap_clause: str = "6(b)",
    breach_clause: str = "6(c)",
) -> str:
    """Test one expense against the grant rule you extracted from the agreement.

    You supply the rule because reading the agreement is your job. Comparing an
    amount to a threshold is not - this tool does that, exactly, every time.
    """
    expense = next((e for e in loaders.load_expenses() if e.expense_id == expense_id), None)
    if expense is None:
        return _json({"error": f"No expense {expense_id}"})
    rule = core.GrantRule(
        grant_id=grant_id,
        capital_unit_cap=money(capital_unit_cap),
        allowable_categories=list(allowable_categories),
        cap_clause=cap_clause,
        breach_clause=breach_clause,
    )
    f = core.evaluate_expense(expense, rule)
    return _json({
        "expense_id": f.expense_id, "fund": f.fund, "amount": f.amount,
        "compliant": f.compliant, "needs_human": f.needs_human, "clause": f.clause,
        "amount_over_cap": f.amount_over_cap, "basis": f.basis,
    })


@tool
def fund_balance(designation: str, fund_id: str = "") -> str:
    """Income, spend and closing balance for one fund."""
    return _json(core.fund_balance(
        loaders.load_gifts(), loaders.load_expenses(), designation, fund_id or None,
    ))


RECONCILER_TOOLS = [list_bank_credits, list_gifts, match_deposits, net_of_fees, compute_fee]
ACKNOWLEDGER_TOOLS = [list_gifts, deductible_portion]
COMPLIANCE_TOOLS = [read_grant_agreement, list_expenses, test_expense_against_grant, fund_balance]
