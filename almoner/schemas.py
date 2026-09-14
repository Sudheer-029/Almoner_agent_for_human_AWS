"""Every agent decision comes back as one of these.

No node is allowed to answer in prose. A decision that cannot be expressed as
one of these models is a decision Almoner does not make - and `reason` is what
the treasurer actually reads in the review queue, so it is written for her,
not for a log file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Disposition = Literal["auto_cleared", "drafted_for_approval", "needs_your_decision"]


class Option(BaseModel):
    """One thing the treasurer could choose. Never more than a sentence."""
    label: str = Field(description="The choice, phrased as an action, e.g. 'Credit to Robert Hoffmann'")
    consequence: str = Field(description="What happens to the books if she picks this")


class Escalation(BaseModel):
    item_ref: str = Field(description="The gift, expense or bank line this concerns")
    question: str = Field(description="The single question for the treasurer, in plain English")
    why_i_cannot_decide: str = Field(description="What information is missing, specifically")
    options: list[Option] = Field(min_length=2, max_length=4)
    citation: str = Field(default="", description="Grant clause or rule this rests on, if any")


class DepositDecision(BaseModel):
    bank_line: int
    disposition: Disposition
    gift_ids: list[str] = Field(default_factory=list)
    reason: str


class ReconcileReport(BaseModel):
    decisions: list[DepositDecision]
    escalations: list[Escalation] = Field(default_factory=list)
    summary: str = Field(description="One sentence for the queue header")


class LetterTemplates(BaseModel):
    """Written once by the model; filled per donor by a deterministic renderer.

    The model supplies language. The tools supply every number.
    """
    cash: str = Field(description="Template for a plain cash gift. Placeholders: {donor}, {amount}, {date}, {org}")
    in_kind: str = Field(description="Template describing donated property WITHOUT stating any value. Placeholders: {donor}, {description}, {date}, {org}")
    quid_pro_quo: str = Field(description="Template where goods were received. Placeholders: {donor}, {amount}, {fmv}, {deductible}, {date}, {org}")


class GiftClassification(BaseModel):
    gift_id: str
    template: Literal["cash", "in_kind", "quid_pro_quo"]
    disposition: Disposition
    reason: str


class AcknowledgementReport(BaseModel):
    templates: LetterTemplates
    classifications: list[GiftClassification]
    escalations: list[Escalation] = Field(default_factory=list)
    summary: str


class ExtractedGrantRule(BaseModel):
    """What the agent understood the grant agreement to require.

    Reading the agreement is judgment. Testing an expense against what it says
    is arithmetic, and happens in core.py.
    """
    grant_id: str
    capital_unit_cap: str = Field(description="Per-item capital cap as a decimal string, e.g. '1000.00'")
    cap_clause: str = Field(description="Clause number imposing the cap, e.g. '6(b)'")
    breach_clause: str = Field(default="", description="Clause stating the consequence of breach")
    allowable_categories: list[str] = Field(description="Cost categories the grant permits")
    report_due: str = Field(description="Interim report due date, ISO format")


class ComplianceReport(BaseModel):
    rule: ExtractedGrantRule
    cleared_expense_ids: list[str]
    escalations: list[Escalation] = Field(default_factory=list)
    funder_report_draft: str = Field(description="Draft interim report body for the funder")
    summary: str


class QueueItem(BaseModel):
    """One row in what the treasurer actually sees."""
    ref: str
    kind: Literal["deposit", "gift", "expense"]
    disposition: Disposition
    headline: str
    reason: str
    citation: str = ""
    options: list[Option] = Field(default_factory=list)
    node: str = ""
