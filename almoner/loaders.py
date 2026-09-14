"""Read the month's records off disk into typed rows.

Deliberately dumb: no interpretation happens here, only parsing.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .money import money

FIXTURES = os.environ.get(
    "ALMONER_FIXTURES",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures"),
)


def _d(value: str) -> date:
    return date.fromisoformat(value)


@dataclass(frozen=True)
class Gift:
    gift_id: str
    gift_date: date
    donor_name: str
    donor_email: str
    gross: Decimal
    fee: Decimal
    net: Decimal
    channel: str           # online | check | in_kind
    gift_type: str         # donation | event_ticket | in_kind | pledge
    designation: str       # unrestricted | literacy_program
    goods_fmv: str         # blank means never recorded - not the same as zero
    status: str            # settled | pledged
    notes: str

    @property
    def is_settled(self) -> bool:
        return self.status == "settled"


@dataclass(frozen=True)
class BankLine:
    line_no: int
    posted: date
    description: str
    credit: Decimal
    debit: Decimal
    balance: Decimal

    @property
    def is_credit(self) -> bool:
        return self.credit > 0


@dataclass(frozen=True)
class Expense:
    expense_id: str
    expense_date: date
    vendor: str
    description: str
    amount: Decimal
    fund: str              # general | <grant id>
    category: str
    receipt_ref: str


def load_gifts(path: str | None = None) -> list[Gift]:
    path = path or os.path.join(FIXTURES, "donations_givepath_2026_08.csv")
    with open(path, newline="") as fh:
        return [
            Gift(
                gift_id=r["gift_id"],
                gift_date=_d(r["gift_date"]),
                donor_name=r["donor_name"],
                donor_email=r["donor_email"],
                gross=money(r["gross_amount"]),
                fee=money(r["processing_fee"]),
                net=money(r["net_amount"]),
                channel=r["channel"],
                gift_type=r["gift_type"],
                designation=r["designation"],
                goods_fmv=r["goods_received_fmv"].strip(),
                status=r["status"],
                notes=r["notes"],
            )
            for r in csv.DictReader(fh)
        ]


def load_bank(path: str | None = None) -> list[BankLine]:
    path = path or os.path.join(FIXTURES, "bank_statement_2026_08.csv")
    with open(path, newline="") as fh:
        return [
            BankLine(
                line_no=i,
                posted=_d(r["posted_date"]),
                description=r["description"],
                credit=money(r["credit"]),
                debit=money(r["debit"]),
                balance=money(r["balance"]),
            )
            for i, r in enumerate(csv.DictReader(fh), start=1)
        ]


def load_expenses(path: str | None = None) -> list[Expense]:
    path = path or os.path.join(FIXTURES, "expenses_2026_08.csv")
    with open(path, newline="") as fh:
        return [
            Expense(
                expense_id=r["expense_id"],
                expense_date=_d(r["expense_date"]),
                vendor=r["vendor"],
                description=r["description"],
                amount=money(r["amount"]),
                fund=r["fund"],
                category=r["category"],
                receipt_ref=r["receipt_ref"],
            )
            for r in csv.DictReader(fh)
        ]


def read_grant_agreement(path: str | None = None) -> str:
    """Full text of the grant agreement.

    The agent reads this and decides what the clauses mean. Extracting the
    rules is judgment; testing an expense against them is arithmetic, and
    that happens in core.py.
    """
    path = path or os.path.join(FIXTURES, "grant_agreement_BLF-2026.pdf")
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
