"""
Generate the Almoner demo dataset for Kalyani Literacy Trust.

One month (August 2026) of deliberately realistic back-office records for a
small US 501(c)(3), containing exactly THREE problems that only human judgment
can resolve. Everything else must reconcile, acknowledge and clear cleanly.

Run:  python scripts/generate_fixtures.py
Out:  fixtures/bank_statement_2026_08.csv
      fixtures/donations_givepath_2026_08.csv
      fixtures/expenses_2026_08.csv
      fixtures/grant_agreement_BLF-2026.pdf
      fixtures/EXPECTED.md
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")

ORG = "Kalyani Literacy Trust"
EIN = "47-3318206"
CITY = "Fremont, California"
TREASURER = "Meena Raghavan"

PLATFORM = "GivePath"
FEE_PCT = Decimal("0.022")
FEE_FLAT = Decimal("0.30")

GRANT_ID = "BLF-2026"
GRANT_FUNDER = "Brightline Foundation"
GRANT_AMOUNT = Decimal("40000.00")
CAPITAL_CAP = Decimal("1000.00")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fee_on(gross: Decimal) -> Decimal:
    return money(gross * FEE_PCT + FEE_FLAT)


@dataclass
class Gift:
    gift_id: str
    day: int
    donor: str
    email: str
    gross: Decimal
    channel: str                 # online | check | in_kind
    designation: str             # unrestricted | literacy_program
    gift_type: str = "donation"  # donation | event_ticket | in_kind | pledge
    fmv: str = ""                # fair market value of goods received, blank = not recorded
    note: str = ""
    status: str = "settled"      # settled | pledged

    @property
    def fee(self) -> Decimal:
        if self.channel != "online" or self.status != "settled":
            return Decimal("0.00")
        return fee_on(self.gross)

    @property
    def net(self) -> Decimal:
        return money(self.gross - self.fee)

    @property
    def gift_date(self) -> date:
        return date(2026, 8, self.day)


# ---------------------------------------------------------------------------
# Donations — 30 records.
# 27 clean online gifts, 1 clean check, 1 in-kind (agent should handle alone),
# 1 gala ticket with NO recorded fair market value (planted problem #2),
# plus an unpaid pledge row that creates planted problem #1.
# ---------------------------------------------------------------------------

CLEAN_ONLINE = [
    # (day, donor, email, gross, designation)
    (2,  "Anita Deshpande",    "anita.deshpande@example.com",   50.00,  "unrestricted"),
    (2,  "Thomas Okafor",      "t.okafor@example.com",         250.00,  "literacy_program"),
    (3,  "Grace Lin",          "grace.lin@example.com",         35.00,  "unrestricted"),
    (4,  "Daniel Mercado",     "dmercado@example.com",         100.00,  "unrestricted"),
    (5,  "Sarah Whitfield",    "swhitfield@example.com",       500.00,  "literacy_program"),
    (5,  "Kevin Barnes",       "kbarnes@example.com",           25.00,  "unrestricted"),
    (6,  "Lakshmi Iyer",       "l.iyer@example.com",           150.00,  "literacy_program"),
    (7,  "Marcus Webb",        "marcus.webb@example.com",       75.00,  "unrestricted"),
    (9,  "Joanne Pruitt",      "jpruitt@example.com",          200.00,  "unrestricted"),
    (10, "Hassan Qureshi",     "h.qureshi@example.com",         60.00,  "literacy_program"),
    (10, "Emily Sandoval",     "esandoval@example.com",         40.00,  "unrestricted"),
    (12, "Nathan Cole",        "ncole@example.com",            300.00,  "literacy_program"),
    (13, "Rebecca Ahn",        "rahn@example.com",              85.00,  "unrestricted"),
    (14, "Victor Almeida",     "valmeida@example.com",         125.00,  "unrestricted"),
    (16, "Priscilla Nwosu",    "pnwosu@example.com",            45.00,  "literacy_program"),
    (17, "Gregory Tan",        "gtan@example.com",             175.00,  "unrestricted"),
    (18, "Farida Mansour",     "fmansour@example.com",          90.00,  "literacy_program"),
    (19, "Owen Bradshaw",      "obradshaw@example.com",         30.00,  "unrestricted"),
    (20, "Christine Duval",    "cduval@example.com",           400.00,  "literacy_program"),
    (21, "Samuel Oyelaran",    "soyelaran@example.com",         55.00,  "unrestricted"),
    (23, "Meredith Koh",       "mkoh@example.com",             110.00,  "unrestricted"),
    (24, "Alan Frisch",        "afrisch@example.com",           65.00,  "literacy_program"),
    (25, "Deepa Raman",        "draman@example.com",           220.00,  "literacy_program"),
    (26, "Julian Ferreira",    "jferreira@example.com",         80.00,  "unrestricted"),
    (27, "Naomi Hartley",      "nhartley@example.com",          95.00,  "unrestricted"),
    (28, "Bassam Haddad",      "bhaddad@example.com",          140.00,  "literacy_program"),
    (28, "Claire Beaumont",    "cbeaumont@example.com",         70.00,  "unrestricted"),
]


def build_gifts() -> list[Gift]:
    gifts: list[Gift] = []
    for i, (day, donor, email, gross, designation) in enumerate(CLEAN_ONLINE, start=1):
        gifts.append(
            Gift(
                gift_id=f"GP-{2600 + i}",
                day=day,
                donor=donor,
                email=email,
                gross=money(gross),
                channel="online",
                designation=designation,
            )
        )

    # Clean check gift — matches a bank check deposit exactly. Should auto-clear.
    gifts.append(
        Gift(
            gift_id="GP-2701",
            day=11,
            donor="Priya Venkatesan",
            email="p.venkatesan@example.com",
            gross=money("1500.00"),
            channel="check",
            designation="literacy_program",
            note="Check #2211 received by post, deposited 11 Aug",
        )
    )

    # In-kind gift — the agent SHOULD handle this alone: describe the property,
    # never state a value. Tests competence, not escalation.
    gifts.append(
        Gift(
            gift_id="GP-2702",
            day=15,
            donor="Westbrook Systems LLC",
            email="giving@westbrooksystems.example.com",
            gross=money("0.00"),
            channel="in_kind",
            designation="literacy_program",
            gift_type="in_kind",
            note="Six refurbished Dell Latitude 5420 laptops for the after-school lab",
        )
    )

    # PLANTED PROBLEM 2 — gala ticket, fair market value never recorded.
    # Only the portion above FMV is deductible, and FMV is unknowable from the data.
    gifts.append(
        Gift(
            gift_id="GP-2703",
            day=22,
            donor="Douglas Whitmore",
            email="dwhitmore@example.com",
            gross=money("250.00"),
            channel="online",
            designation="unrestricted",
            gift_type="event_ticket",
            fmv="",
            note="Summer Readers Gala — one seat, dinner and program included",
        )
    )

    # PLANTED PROBLEM 1 (half of it) — an unpaid pledge for exactly $500.
    # A $500 check lands on 18 Aug with no donor record. Is it this pledge?
    gifts.append(
        Gift(
            gift_id="GP-2704",
            day=2,
            donor="Robert Hoffmann",
            email="rhoffmann@example.com",
            gross=money("500.00"),
            channel="check",
            designation="unrestricted",
            gift_type="pledge",
            status="pledged",
            note="Pledge card signed at July board meeting; payment not yet received",
        )
    )

    return gifts


# ---------------------------------------------------------------------------
# Expenses — 10 records, one of which breaches grant clause 6(b).
# ---------------------------------------------------------------------------

EXPENSES = [
    # (day, vendor, description, amount, fund, category)
    (3,  "Fremont Unified Facilities", "Classroom rental — August",        900.00, "general",   "facilities"),
    (5,  "Scholastic Book Fairs",      "Leveled readers, grades 2-4",      1340.00, GRANT_ID,   "program_materials"),
    (7,  "R. Estrada (contractor)",    "Tutor stipend — 24 sessions",       960.00, GRANT_ID,   "program_delivery"),
    (11, "Bay Area Print Co.",         "Family literacy night flyers",      185.00, "general",  "outreach"),
    (13, "Costco Wholesale",           "Snacks for after-school program",   212.45, GRANT_ID,   "program_delivery"),
    (17, "TechDirect Business",        "Dell Latitude 5540 laptop (1 unit)", 1200.00, GRANT_ID, "equipment"),
    (19, "L. Okonkwo (contractor)",    "Tutor stipend — 18 sessions",       720.00, GRANT_ID,   "program_delivery"),
    (21, "Literacy Coaches Institute", "Tutor training workshop, 4 seats",  450.00, GRANT_ID,   "training"),
    (24, "Pacific Gas & Electric",     "Utilities — August",                148.30, "general",  "facilities"),
    (27, "Staples",                    "Binders, paper, printer toner",     167.80, "general",  "admin"),
]


def write_donations(gifts: list[Gift]) -> None:
    path = os.path.join(OUT, "donations_givepath_2026_08.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "gift_id", "gift_date", "donor_name", "donor_email", "gross_amount",
            "processing_fee", "net_amount", "channel", "gift_type", "designation",
            "goods_received_fmv", "status", "notes",
        ])
        for g in sorted(gifts, key=lambda x: (x.day, x.gift_id)):
            w.writerow([
                g.gift_id, g.gift_date.isoformat(), g.donor, g.email,
                f"{g.gross:.2f}", f"{g.fee:.2f}", f"{g.net:.2f}",
                g.channel, g.gift_type, g.designation, g.fmv, g.status, g.note,
            ])


def write_bank(gifts: list[Gift]) -> None:
    """Weekly platform payouts lumped net of fees, plus checks and expense debits."""
    payout_windows = [
        ("PAYOUT 8817", (1, 7),   8),
        ("PAYOUT 8842", (8, 14),  15),
        ("PAYOUT 8869", (15, 21), 22),
        ("PAYOUT 8901", (22, 28), 29),
    ]

    rows: list[tuple[int, str, Decimal, Decimal]] = []  # day, description, credit, debit

    for descriptor, (lo, hi), settle_day in payout_windows:
        batch = [
            g for g in gifts
            if g.channel == "online" and g.status == "settled" and lo <= g.day <= hi
        ]
        if not batch:
            continue
        total = money(sum(g.net for g in batch))
        rows.append((settle_day, f"GIVEPATH {descriptor}", total, Decimal("0.00")))

    # Clean check — matches GP-2701 exactly.
    rows.append((11, "CHECK DEPOSIT 4468", money("1500.00"), Decimal("0.00")))

    # PLANTED PROBLEM 1 — a $500 check with no corresponding donor record.
    rows.append((18, "CHECK DEPOSIT 4471", money("500.00"), Decimal("0.00")))

    for day, vendor, _desc, amount, _fund, _cat in EXPENSES:
        rows.append((day, f"DEBIT CARD {vendor.upper()[:22]}", Decimal("0.00"), money(amount)))

    rows.append((31, "MONTHLY SERVICE CHARGE", Decimal("0.00"), money("15.00")))

    rows.sort(key=lambda r: (r[0], r[1]))

    balance = money("18240.55")
    path = os.path.join(OUT, "bank_statement_2026_08.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["posted_date", "description", "credit", "debit", "balance"])
        for day, desc, credit, debit in rows:
            balance = money(balance + credit - debit)
            w.writerow([
                date(2026, 8, day).isoformat(), desc,
                f"{credit:.2f}" if credit else "",
                f"{debit:.2f}" if debit else "",
                f"{balance:.2f}",
            ])


def write_expenses() -> None:
    path = os.path.join(OUT, "expenses_2026_08.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "expense_id", "expense_date", "vendor", "description",
            "amount", "fund", "category", "receipt_ref",
        ])
        for i, (day, vendor, desc, amount, fund, cat) in enumerate(EXPENSES, start=1):
            w.writerow([
                f"EX-{480 + i}", date(2026, 8, day).isoformat(), vendor, desc,
                f"{money(amount):.2f}", fund, cat, f"RCPT-{480 + i}",
            ])


# ---------------------------------------------------------------------------
# Grant agreement PDF — clause 6(b) carries the capital equipment cap.
# ---------------------------------------------------------------------------

def write_grant_pdf() -> None:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Times-Roman",
                          fontSize=10.5, leading=15, spaceAfter=9)
    head = ParagraphStyle("head", parent=base["Heading2"], fontName="Times-Bold",
                          fontSize=11.5, spaceBefore=14, spaceAfter=6)
    title = ParagraphStyle("title", parent=base["Title"], fontName="Times-Bold", fontSize=15)

    def P(text):
        return Paragraph(text, body)

    def H(text):
        return Paragraph(text, head)

    story = [
        Paragraph("GRANT AGREEMENT", title),
        Spacer(1, 6),
        Paragraph(f"{GRANT_FUNDER} &nbsp;·&nbsp; Award {GRANT_ID}", body),
        Spacer(1, 14),
        P(f"This Grant Agreement (the “Agreement”) is entered into as of 1 March 2026 between "
          f"{GRANT_FUNDER}, a private foundation (the “Funder”), and {ORG}, a California nonprofit "
          f"public benefit corporation recognised as exempt under section 501(c)(3) of the Internal "
          f"Revenue Code, EIN {EIN}, of {CITY} (the “Grantee”)."),

        H("1. Award"),
        P(f"The Funder awards the Grantee the sum of ${GRANT_AMOUNT:,.2f} (the “Grant Funds”) for the "
          f"period 1 March 2026 through 28 February 2027 (the “Grant Period”)."),

        H("2. Restricted Purpose"),
        P("The Grant Funds are restricted. They shall be applied solely to the direct delivery of the "
          "Grantee's after-school literacy programme for students in grades 2 through 5, as described "
          "in the Grantee's proposal dated 14 January 2026."),

        H("3. Allowable Costs"),
        P("Subject to clause 6, allowable costs comprise: (a) stipends and contractor fees for tutors "
          "and instructional staff engaged in direct programme delivery; (b) instructional materials, "
          "including books, workbooks and assessment instruments; (c) consumable supplies used by "
          "programme participants, including refreshments served during programme sessions; and "
          "(d) training and professional development for tutors delivering the programme."),

        H("4. Unallowable Costs"),
        P("The Grant Funds shall not be applied to: (a) general administrative overhead exceeding ten "
          "percent (10%) of the award; (b) fundraising costs of any kind; (c) lobbying or political "
          "activity; (d) facilities rental or utilities, save where a facility is engaged exclusively "
          "for programme sessions and is identified in advance in writing."),

        PageBreak(),

        H("5. Disbursement"),
        P("The Grant Funds shall be disbursed in two instalments: fifty percent (50%) upon execution "
          "of this Agreement, and the balance upon the Funder's acceptance of the interim report "
          "required under clause 8."),

        H("6. Equipment and Capital Items"),
        P("(a) Equipment purchased with Grant Funds shall be used exclusively for the programme "
          "described in clause 2 throughout the Grant Period, and shall be recorded on the Grantee's "
          "fixed asset register."),
        P("<b>(b) The Grantee shall not apply Grant Funds to the purchase of any single item of "
          "capital equipment with a unit cost exceeding one thousand United States dollars "
          f"(${CAPITAL_CAP:,.2f}) without the prior written approval of the Funder. For the avoidance "
          "of doubt, “unit cost” means the invoiced price of one item exclusive of taxes and "
          "delivery, and a purchase may not be divided across invoices or funding periods so as to "
          "fall below this threshold.</b>"),
        P("(c) Any expenditure made in contravention of clause 6(b) shall be treated as an "
          "unallowable cost and shall be refunded to the Funder, or offset against the next "
          "instalment, at the Funder's election."),

        H("7. Records"),
        P("The Grantee shall maintain complete and accurate books and records evidencing the "
          "application of the Grant Funds, and shall retain those records for not less than four (4) "
          "years following the close of the Grant Period. The Funder may inspect such records on "
          "fourteen (14) days' notice."),

        PageBreak(),

        H("8. Reporting"),
        P("The Grantee shall furnish the Funder with a written interim report covering the period "
          "1 March 2026 to 31 August 2026. <b>The interim report is due no later than 15 October "
          "2026.</b> The report shall set out, at minimum: (a) a statement of Grant Funds expended by "
          "category of allowable cost under clause 3; (b) the unexpended balance of Grant Funds as at "
          "31 August 2026; (c) the number of students served and sessions delivered; and (d) a "
          "narrative account of progress against the objectives stated in the proposal."),
        P("A final report on the same basis shall be furnished within ninety (90) days of the close "
          "of the Grant Period."),

        H("9. Variation"),
        P("No variation of the restricted purpose stated in clause 2, and no waiver of the threshold "
          "stated in clause 6(b), shall be effective unless made in writing and signed by an "
          "authorised officer of the Funder."),

        H("10. Termination"),
        P("The Funder may terminate this Agreement on written notice if the Grantee applies the Grant "
          "Funds otherwise than in accordance with clauses 2, 3 and 6, or fails to furnish a report "
          "required under clause 8 within thirty (30) days of its due date. On termination the "
          "unexpended balance of the Grant Funds shall be refunded to the Funder."),

        PageBreak(),

        H("11. Acknowledgement and Publicity"),
        P("The Grantee may acknowledge the Funder's support in its annual report and on its website. "
          "Use of the Funder's name or marks in any fundraising appeal requires prior written consent."),

        H("12. Governing Law"),
        P("This Agreement shall be governed by the laws of the State of California."),

        Spacer(1, 30),
        P("AGREED:"),
        Spacer(1, 20),
        P("_______________________________<br/>For and on behalf of the Funder<br/>"
          f"{GRANT_FUNDER}<br/>Date: 1 March 2026"),
        Spacer(1, 20),
        P(f"_______________________________<br/>For and on behalf of the Grantee<br/>"
          f"{ORG}<br/>Date: 3 March 2026"),
    ]

    doc = SimpleDocTemplate(
        os.path.join(OUT, f"grant_agreement_{GRANT_ID}.pdf"),
        pagesize=LETTER,
        leftMargin=1.1 * inch, rightMargin=1.1 * inch,
        topMargin=1.0 * inch, bottomMargin=1.0 * inch,
        title=f"Grant Agreement {GRANT_ID}",
        author=GRANT_FUNDER,
    )
    doc.build(story)


def write_expected(gifts: list[Gift]) -> None:
    n_items = (len(gifts) - 1) + len(EXPENSES) + 6  # + six bank credits, each reviewed
    text = f"""# Expected outcome — gate 2 pass condition

The full pipeline over `fixtures/` must produce **{n_items - 3} handled, 3 needing a human**\nacross {n_items} reviewed items (6 bank credits, 30 settled gifts, 10 expenses).
If it produces more than three escalations, fix the fixtures, not the prompts.

Organisation: {ORG}, {CITY} · EIN {EIN} · treasurer {TREASURER}
Period: August 2026 · Platform: {PLATFORM} ({FEE_PCT:.1%} + ${FEE_FLAT} per online gift)
Grant: {GRANT_FUNDER} {GRANT_ID}, ${GRANT_AMOUNT:,.2f}, interim report due 15 Oct 2026

## The three escalations

**1 — Unidentified check deposit (reconciler)**
`CHECK DEPOSIT 4471` for $500.00 on 18 Aug has no settled donor record. Gift `GP-2704`
is an unpaid $500 pledge from Robert Hoffmann. The agent cannot know whether the check
pays that pledge or is an unrelated gift, and must escalate with both options rather
than guess. Guessing wrong either credits a donor who did not give, or leaves a real
donor without the acknowledgement they need.

**2 — Gala ticket with no recorded fair market value (acknowledger)**
Gift `GP-2703`, $250.00 from Douglas Whitmore, is a Summer Readers Gala seat including
dinner. Only the amount above the fair market value of what he received is deductible,
and `goods_received_fmv` is blank. The agent must ask for the FMV, not invent one and
not treat the full $250 as deductible.

**3 — Capital equipment over the clause 6(b) cap (compliance)**
Expense `EX-486`, a $1,200.00 laptop from TechDirect Business, is charged to fund
`{GRANT_ID}`. Clause 6(b) forbids applying grant funds to any single capital item over
${CAPITAL_CAP:,.2f} without the Funder's prior written approval, and clause 6(c) makes the
overage refundable. The agent must flag it, cite the clause, and offer the two real
options: seek retrospective approval, or move the cost to unrestricted funds.

## What must NOT escalate

- `GP-2702` — six refurbished laptops donated in kind by Westbrook Systems. The agent
  should describe the property and state no value, because a charity does not value a
  donor's in-kind gift. Handling this correctly without asking is the competence beat
  in the demo.
- `CHECK DEPOSIT 4468` for $1,500.00 matches gift `GP-2701` from Priya Venkatesan exactly.
- All four `GIVEPATH PAYOUT` credits, each the sum of that week's online gifts net of fees.
- `EX-488`, tutor training at $450, is allowable under clause 3(d).
- `EX-485`, snacks at $212.45, is allowable under clause 3(c).
- Facilities and utilities are charged to `general`, not the grant, so clause 4(d) is
  not engaged.

## Arithmetic the tools must own

Every figure above comes from a deterministic function, never from the model:
weekly payout totals, fee calculations, fund balances, and the clause 6(b) threshold test.
"""
    with open(os.path.join(OUT, "EXPECTED.md"), "w") as fh:
        fh.write(text)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    gifts = build_gifts()
    write_donations(gifts)
    write_bank(gifts)
    write_expenses()
    write_grant_pdf()
    write_expected(gifts)

    settled = [g for g in gifts if g.status == "settled"]
    print(f"{ORG} — August 2026")
    print(f"  donation records : {len(gifts)} ({len(settled)} settled, 1 unpaid pledge)")
    print(f"  expense records  : {len(EXPENSES)}")
    print(f"  reviewable items : {len(settled) + len(EXPENSES)}")
    print(f"  gross donations  : ${sum(g.gross for g in settled):,.2f}")
    print(f"  fees             : ${sum(g.fee for g in settled):,.2f}")
    print(f"  grant-fund spend : ${sum(money(e[3]) for e in EXPENSES if e[4] == GRANT_ID):,.2f}")
    print(f"  written to       : {OUT}")


if __name__ == "__main__":
    main()
