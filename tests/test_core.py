"""The tests that stop the demo embarrassing you on camera.

Each one pins a number that appears on screen during the recording.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from almoner.core import (
    GrantRule,
    deductible_portion,
    fund_balance,
    match_deposits,
    evaluate_expense,
)
from almoner.loaders import load_bank, load_expenses, load_gifts
from almoner.money import compute_fee, money, net_of_fees

GRANT = GrantRule(
    grant_id="BLF-2026",
    capital_unit_cap=money("1000.00"),
    allowable_categories=[
        "program_delivery", "program_materials", "training",
    ],
)


@pytest.fixture(scope="module")
def data():
    return load_bank(), load_gifts(), load_expenses()


# --- money ----------------------------------------------------------------

def test_fee_is_percentage_plus_flat():
    assert compute_fee("100.00") == Decimal("2.50")   # 2.20 + 0.30
    assert net_of_fees("100.00") == Decimal("97.50")


def test_fee_rounds_half_up_not_bankers():
    # 25.00 * 0.022 = 0.55 exactly, + 0.30 -> 0.85
    assert compute_fee("25.00") == Decimal("0.85")


def test_money_never_takes_a_float_at_face_value():
    assert money(0.1 + 0.2) == Decimal("0.30")


# --- reconciliation -------------------------------------------------------

def test_every_payout_reconciles_exactly(data):
    bank, gifts, _ = data
    payouts = [m for m in match_deposits(bank, gifts) if "PAYOUT" in m.description]
    assert len(payouts) == 4
    assert all(m.status == "matched" for m in payouts), [
        (m.description, m.status) for m in payouts
    ]


def test_payouts_do_not_double_claim_gifts(data):
    bank, gifts, _ = data
    claimed = [gid for m in match_deposits(bank, gifts) for gid in m.gift_ids]
    assert len(claimed) == len(set(claimed))


def test_clean_check_matches_its_gift(data):
    bank, gifts, _ = data
    m = next(m for m in match_deposits(bank, gifts) if "4468" in m.description)
    assert m.status == "matched"
    assert m.gift_ids == ["GP-2701"]


def test_unidentified_check_escalates_with_the_pledge_as_candidate(data):
    """Planted problem 1. Must never be silently credited to Hoffmann."""
    bank, gifts, _ = data
    m = next(m for m in match_deposits(bank, gifts) if "4471" in m.description)
    assert m.status == "ambiguous"
    assert m.needs_human
    assert m.gift_ids == []
    assert "GP-2704" in m.candidates


def test_exactly_one_deposit_needs_a_human(data):
    bank, gifts, _ = data
    flagged = [m for m in match_deposits(bank, gifts) if m.needs_human]
    assert len(flagged) == 1


# --- acknowledgement ------------------------------------------------------

def test_plain_cash_gift_is_fully_deductible(data):
    _, gifts, _ = data
    g = next(g for g in gifts if g.gift_id == "GP-2601")
    d = deductible_portion(g)
    assert d.determinable and d.deductible == g.gross


def test_in_kind_gift_is_never_valued_by_the_charity(data):
    _, gifts, _ = data
    d = deductible_portion(next(g for g in gifts if g.gift_id == "GP-2702"))
    assert d.determinable          # handled, not escalated
    assert d.deductible is None    # but carries no amount


def test_gala_ticket_without_fmv_is_not_determinable(data):
    """Planted problem 2. The agent must ask, not assume $250 is deductible."""
    _, gifts, _ = data
    d = deductible_portion(next(g for g in gifts if g.gift_id == "GP-2703"))
    assert not d.determinable
    assert d.deductible is None


def test_gala_ticket_becomes_determinable_once_fmv_is_supplied(data):
    """What happens after the treasurer answers the escalation."""
    from dataclasses import replace

    _, gifts, _ = data
    g = replace(next(g for g in gifts if g.gift_id == "GP-2703"), goods_fmv="75.00")
    d = deductible_portion(g)
    assert d.determinable
    assert d.deductible == Decimal("175.00")


# --- grant compliance -----------------------------------------------------

def test_laptop_breaches_the_capital_cap(data):
    """Planted problem 3."""
    _, _, expenses = data
    f = evaluate_expense(next(e for e in expenses if e.expense_id == "EX-486"), GRANT)
    assert not f.compliant and f.needs_human
    assert f.clause == "6(b)"
    assert f.amount_over_cap == Decimal("200.00")


def test_allowable_grant_costs_clear(data):
    _, _, expenses = data
    for eid in ("EX-482", "EX-483", "EX-485", "EX-487", "EX-488"):
        f = evaluate_expense(next(e for e in expenses if e.expense_id == eid), GRANT)
        assert f.compliant, (eid, f.basis)


def test_general_fund_expenses_are_not_grant_governed(data):
    _, _, expenses = data
    for eid in ("EX-481", "EX-484", "EX-489", "EX-490"):
        assert evaluate_expense(next(e for e in expenses if e.expense_id == eid), GRANT).compliant


def test_exactly_one_expense_needs_a_human(data):
    _, _, expenses = data
    assert len([e for e in expenses if evaluate_expense(e, GRANT).needs_human]) == 1


# --- the number on screen -------------------------------------------------

def test_the_counter_reads_43_handled_3_for_you():
    """The single number the demo lands on. If this breaks, the pitch breaks.

    Counts the queue the product actually builds: six bank lines, thirty settled
    gifts and ten expenses, each of which the agent genuinely reviewed.
    """
    from almoner.run import build_queue

    items = build_queue()
    escalated = [i for i in items if i.disposition == "needs_your_decision"]

    assert len(items) == 46
    assert len(escalated) == 3
    assert len(items) - len(escalated) == 43
    assert {i.ref for i in escalated} == {"BANK-10", "GP-2703", "EX-486"}


def test_each_escalation_offers_real_choices():
    """An escalation with no options is just an error message."""
    from almoner.run import build_queue

    for item in build_queue():
        if item.disposition == "needs_your_decision":
            assert len(item.options) >= 2, item.ref
            assert all(o.consequence for o in item.options), item.ref


def test_nothing_is_ever_marked_sent():
    """Almoner drafts. The schema must not allow a queue item to claim otherwise."""
    from almoner.run import build_queue

    assert all(
        i.disposition in {"auto_cleared", "drafted_for_approval", "needs_your_decision"}
        for i in build_queue()
    )


def test_restricted_fund_balance(data):
    _, gifts, expenses = data
    bal = fund_balance(gifts, expenses, "literacy_program", "BLF-2026")
    assert bal["spend"] == Decimal("4882.45")
    assert bal["closing"] == money(bal["income"] - bal["spend"])


def test_a_second_close_does_not_inherit_the_first_close_s_answers(tmp_path):
    """Closing the month again must start from a clean queue."""
    from almoner import ledger

    db = str(tmp_path / "t.db")
    conn = ledger.connect(db)
    item = {"ref": "EX-486", "kind": "expense", "disposition": "needs_your_decision",
            "headline": "h", "reason": "r"}

    ledger.start_run(conn, "run-a", "August 2026")
    ledger.add_queue_item(conn, "run-a", item)
    ledger.record_decision(conn, "run-a", "EX-486", "Meena", "Move to unrestricted funds")

    ledger.start_run(conn, "run-b", "August 2026")
    ledger.add_queue_item(conn, "run-b", item)

    assert ledger.queue_for_run(conn, "run-a")[0]["decision"] is not None
    assert ledger.queue_for_run(conn, "run-b")[0]["decision"] is None
