# Expected outcome — gate 2 pass condition

The full pipeline over `fixtures/` must produce **43 handled, 3 needing a human**
across 46 reviewed items (6 bank credits, 30 settled gifts, 10 expenses).
If it produces more than three escalations, fix the fixtures, not the prompts.

Organisation: Kalyani Literacy Trust, Fremont, California · EIN 47-3318206 · treasurer Meena Raghavan
Period: August 2026 · Platform: GivePath (2.2% + $0.30 per online gift)
Grant: Brightline Foundation BLF-2026, $40,000.00, interim report due 15 Oct 2026

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
`BLF-2026`. Clause 6(b) forbids applying grant funds to any single capital item over
$1,000.00 without the Funder's prior written approval, and clause 6(c) makes the
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
