"""The deterministic half of Almoner.

Every number the treasurer ever sees is produced here, by ordinary Python, and
is reproducible. The agent's job is to decide what the numbers *mean* and when
a human has to be asked. It is never asked to calculate.

Nothing in this module imports Strands or calls a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Literal

from .loaders import BankLine, Expense, Gift
from .money import ZERO, money, net_of_fees

MatchStatus = Literal["matched", "ambiguous", "unmatched"]

# How far back a payout may sweep gifts, and how far a check may drift from its
# recorded gift date before we stop believing they are the same thing.
PAYOUT_MAX_WINDOW_DAYS = 14
CHECK_DATE_TOLERANCE_DAYS = 7


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@dataclass
class DepositMatch:
    line_no: int
    posted: date
    description: str
    amount: Decimal
    status: MatchStatus
    gift_ids: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    basis: str = ""

    @property
    def needs_human(self) -> bool:
        return self.status != "matched"


def _sum_net(gifts: Iterable[Gift]) -> Decimal:
    return money(sum((g.net for g in gifts), ZERO))


def match_deposits(bank: list[BankLine], gifts: list[Gift]) -> list[DepositMatch]:
    """Match every bank credit to the gifts that produced it.

    Two shapes of credit exist. A platform payout is the summed net of a batch
    of online gifts, so we look for a trailing date window whose nets total the
    credit exactly. A check deposit is a single gift, matched on amount and date
    proximity. Anything we cannot tie to a settled gift is reported as ambiguous
    (there is a plausible candidate) or unmatched (there is not) - never guessed.
    """
    consumed: set[str] = set()
    online = [g for g in gifts if g.channel == "online" and g.is_settled]
    checks = [g for g in gifts if g.channel == "check" and g.is_settled]
    pledges = [g for g in gifts if g.status == "pledged"]

    results: list[DepositMatch] = []

    for line in sorted((b for b in bank if b.is_credit), key=lambda b: (b.posted, b.line_no)):
        amount = line.credit
        desc = line.description.upper()

        if "PAYOUT" in desc:
            match = _match_payout(line, amount, online, consumed)
        elif "CHECK" in desc or "CHEQUE" in desc:
            match = _match_check(line, amount, checks, pledges, consumed)
        else:
            match = DepositMatch(
                line_no=line.line_no, posted=line.posted, description=line.description,
                amount=amount, status="unmatched",
                basis="Credit is neither a platform payout nor a check deposit.",
            )
        results.append(match)

    return results


def _match_payout(line: BankLine, amount: Decimal, online: list[Gift],
                  consumed: set[str]) -> DepositMatch:
    # Widest window first, so a payout claims the whole week rather than a
    # coincidental subset of it. A gift made on the posting day itself cannot
    # have settled into that payout, so the window is open at the top.
    for window in range(PAYOUT_MAX_WINDOW_DAYS, 0, -1):
        start = line.posted - timedelta(days=window)
        batch = [
            g for g in online
            if g.gift_id not in consumed and start < g.gift_date < line.posted
        ]
        if batch and _sum_net(batch) == amount:
            consumed.update(g.gift_id for g in batch)
            return DepositMatch(
                line_no=line.line_no, posted=line.posted, description=line.description,
                amount=amount, status="matched",
                gift_ids=[g.gift_id for g in batch],
                basis=(
                    f"{len(batch)} online gifts dated "
                    f"{min(g.gift_date for g in batch)} to {max(g.gift_date for g in batch)}, "
                    f"net of fees, total exactly {amount}."
                ),
            )

    return DepositMatch(
        line_no=line.line_no, posted=line.posted, description=line.description,
        amount=amount, status="unmatched",
        basis="No trailing window of unmatched online gifts nets to this amount.",
    )


def _match_check(line: BankLine, amount: Decimal, checks: list[Gift],
                 pledges: list[Gift], consumed: set[str]) -> DepositMatch:
    exact = [
        g for g in checks
        if g.gift_id not in consumed
        and g.gross == amount
        and abs((g.gift_date - line.posted).days) <= CHECK_DATE_TOLERANCE_DAYS
    ]
    if len(exact) == 1:
        g = exact[0]
        consumed.add(g.gift_id)
        return DepositMatch(
            line_no=line.line_no, posted=line.posted, description=line.description,
            amount=amount, status="matched", gift_ids=[g.gift_id],
            basis=f"Amount and date match recorded check gift {g.gift_id} from {g.donor_name}.",
        )
    if len(exact) > 1:
        return DepositMatch(
            line_no=line.line_no, posted=line.posted, description=line.description,
            amount=amount, status="ambiguous",
            candidates=[g.gift_id for g in exact],
            basis=f"{len(exact)} recorded check gifts share this amount and date range.",
        )

    # No settled gift. An unpaid pledge for the same amount is a candidate, not
    # an answer: only the physical check says whose money this is.
    near = [g for g in pledges if g.gross == amount]
    if near:
        return DepositMatch(
            line_no=line.line_no, posted=line.posted, description=line.description,
            amount=amount, status="ambiguous",
            candidates=[g.gift_id for g in near],
            basis=(
                f"No settled gift matches. {len(near)} unpaid pledge(s) are recorded for "
                f"exactly this amount, so this deposit may or may not be that pledge being paid."
            ),
        )

    return DepositMatch(
        line_no=line.line_no, posted=line.posted, description=line.description,
        amount=amount, status="unmatched",
        basis="No recorded gift or pledge matches this amount.",
    )


# ---------------------------------------------------------------------------
# Acknowledgement arithmetic
# ---------------------------------------------------------------------------

@dataclass
class Deductible:
    gift_id: str
    gross: Decimal
    fmv_received: Decimal | None
    deductible: Decimal | None
    determinable: bool
    basis: str


def deductible_portion(gift: Gift) -> Deductible:
    """How much of a gift the donor may actually deduct.

    A plain cash gift is fully deductible. Where the donor received something in
    return, only the excess over its fair market value is - and if that value was
    never recorded, the answer is not a number, it is a question for a human.
    An in-kind gift has no deductible amount at all from the charity's side: the
    charity describes the property and the donor values it.
    """
    if gift.gift_type == "in_kind":
        return Deductible(
            gift.gift_id, gift.gross, None, None, True,
            "In-kind gift. The charity describes the property and states no value; "
            "valuing a donated item is the donor's responsibility, not the charity's.",
        )

    if gift.gift_type == "event_ticket" or gift.goods_fmv:
        if not gift.goods_fmv:
            return Deductible(
                gift.gift_id, gift.gross, None, None, False,
                "Donor received goods or services in exchange, but their fair market "
                "value was never recorded, so the deductible portion cannot be computed.",
            )
        fmv = money(gift.goods_fmv)
        return Deductible(
            gift.gift_id, gift.gross, fmv, money(gift.gross - fmv), True,
            f"Quid pro quo gift: {gift.gross} paid less {fmv} fair market value received.",
        )

    return Deductible(
        gift.gift_id, gift.gross, ZERO, gift.gross, True,
        "Cash gift with no goods or services received in return; fully deductible.",
    )


# ---------------------------------------------------------------------------
# Restricted fund compliance
# ---------------------------------------------------------------------------

@dataclass
class GrantRule:
    """What the agent understood the grant agreement to require.

    The agent fills this in after reading the PDF. Testing expenses against it
    is arithmetic and happens below.
    """
    grant_id: str
    capital_unit_cap: Decimal
    allowable_categories: list[str]
    capital_categories: list[str] = field(default_factory=lambda: ["equipment", "capital"])
    cap_clause: str = "6(b)"
    breach_clause: str = "6(c)"


@dataclass
class ComplianceFinding:
    expense_id: str
    fund: str
    amount: Decimal
    compliant: bool
    needs_human: bool
    clause: str = ""
    amount_over_cap: Decimal = ZERO
    basis: str = ""


def evaluate_expense(expense: Expense, rule: GrantRule) -> ComplianceFinding:
    """Test one expense against one grant rule. Pure comparison, no judgment."""
    if expense.fund != rule.grant_id:
        return ComplianceFinding(
            expense.expense_id, expense.fund, expense.amount,
            compliant=True, needs_human=False,
            basis=f"Charged to {expense.fund}, not to restricted grant {rule.grant_id}.",
        )

    if expense.category in rule.capital_categories and expense.amount > rule.capital_unit_cap:
        return ComplianceFinding(
            expense.expense_id, expense.fund, expense.amount,
            compliant=False, needs_human=True,
            clause=rule.cap_clause,
            amount_over_cap=money(expense.amount - rule.capital_unit_cap),
            basis=(
                f"Single capital item at {expense.amount} exceeds the "
                f"{rule.capital_unit_cap} per-unit cap in clause {rule.cap_clause}, "
                f"which requires the funder's prior written approval. Under clause "
                f"{rule.breach_clause} the expenditure is refundable to the funder."
            ),
        )

    if expense.category not in rule.allowable_categories:
        return ComplianceFinding(
            expense.expense_id, expense.fund, expense.amount,
            compliant=False, needs_human=True,
            basis=f"Category '{expense.category}' is not among the grant's allowable costs.",
        )

    return ComplianceFinding(
        expense.expense_id, expense.fund, expense.amount,
        compliant=True, needs_human=False,
        basis=f"Category '{expense.category}' is an allowable cost under the grant.",
    )


def fund_balance(gifts: list[Gift], expenses: list[Expense], designation: str,
                 fund_id: str | None = None, opening: Decimal = ZERO) -> dict:
    """Money in, money out, and what is left, for one fund.

    `designation` is what the donor restricted the gift to; `fund_id` is what
    the grant agreement calls the fund the spending is booked against. They
    are different namespaces and conflating them silently reports zero spend.
    """
    fund_id = fund_id or designation
    income = money(sum((g.net for g in gifts if g.is_settled and g.designation == designation), ZERO))
    spend = money(sum((e.amount for e in expenses if e.fund == fund_id), ZERO))
    return {
        "fund": designation,
        "fund_id": fund_id,
        "opening": money(opening),
        "income": income,
        "spend": spend,
        "closing": money(money(opening) + income - spend),
    }
