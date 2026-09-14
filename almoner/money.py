"""Money handling. Every figure in Almoner passes through here.

The model is never asked to do arithmetic; it asks these functions instead.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# GivePath processing fee: 2.2% of gross plus a 30c flat charge per transaction.
FEE_PCT = Decimal("0.022")
FEE_FLAT = Decimal("0.30")

ZERO = Decimal("0.00")


def money(value) -> Decimal:
    """Coerce anything money-shaped to a 2dp Decimal. Never use float for money."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, float):  # guard against silent binary-float drift
        value = repr(value)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_fee(gross) -> Decimal:
    """Processing fee charged on an online gift."""
    return money(money(gross) * FEE_PCT + FEE_FLAT)


def net_of_fees(gross) -> Decimal:
    """What actually lands in the bank for an online gift of `gross`."""
    gross = money(gross)
    return money(gross - compute_fee(gross))


def usd(value) -> str:
    return f"${money(value):,.2f}"
