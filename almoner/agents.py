"""Three agents, one Strands graph.

Each node is a narrow specialist with its own system prompt, its own tool
subset and its own Pydantic output model. There is no general-purpose
"do the bookkeeping" prompt anywhere in this file, on purpose: a graph is
inspectable, and each node can be reasoned about and tested alone.
"""

from __future__ import annotations

import os

from strands import Agent
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import tools
from .schemas import AcknowledgementReport, ComplianceReport, ReconcileReport

REGION = os.environ.get("AWS_REGION", "us-west-2")

# Which model provider to run against. Strands is model-portable, so this is the
# only place the choice appears: "bedrock" (default) or "anthropic".
PROVIDER = os.environ.get("ALMONER_PROVIDER", "bedrock").lower()

# Bedrock defaults are cross-region INFERENCE PROFILE ids, not bare model names.
# Many accounts expose no on-demand foundation models at all, and a bare id like
# "anthropic.claude-sonnet-5" is then rejected as an invalid model identifier.
# The "global." profiles route across all regions for availability.
BEDROCK_JUDGMENT = "global.anthropic.claude-sonnet-5"
BEDROCK_ROUTINE = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

ANTHROPIC_JUDGMENT = "claude-sonnet-5"
ANTHROPIC_ROUTINE = "claude-haiku-4-5"

_defaults = (
    (BEDROCK_JUDGMENT, BEDROCK_ROUTINE) if PROVIDER == "bedrock"
    else (ANTHROPIC_JUDGMENT, ANTHROPIC_ROUTINE)
)

# Judgment nodes get the stronger model; the mechanical node does not need it.
JUDGMENT_MODEL = os.environ.get("ALMONER_JUDGMENT_MODEL", _defaults[0])
ROUTINE_MODEL = os.environ.get("ALMONER_ROUTINE_MODEL", _defaults[1])

ORG = "Kalyani Literacy Trust"

# The rule every node inherits. It is stated as a prohibition rather than a
# preference because that is what it is.
HOUSE_RULES = f"""
You are part of Almoner, which does the monthly back-office work of {ORG},
a small 501(c)(3). Its treasurer is a volunteer with a day job.

Three rules bind you absolutely:

1. You do not calculate. Every figure you report must come from a tool call.
   If you need a number no tool gives you, that is an escalation, not an
   estimate. Never round, total, or infer an amount yourself.

2. You do not guess about money that belongs to someone. Where the records
   admit more than one honest reading, you escalate with the real options and
   say plainly what you could not determine. A wrong guess costs a donor their
   deduction or costs the charity a grant.

3. You draft; you never send. Nothing you produce goes to a donor or a funder
   without the treasurer approving it.

Escalate sparingly. An escalation is a claim on a volunteer's evening, so raise
one only where a human genuinely holds information you do not. Most months,
almost everything should clear on its own.

Write every `reason` for the treasurer to read: one or two plain sentences,
no jargon, naming the specific record and the specific problem.
""".strip()


def _model(model_id: str, temperature: float = 0.2):
    """One model, from whichever provider is configured.

    The nodes below never know which it is. That is the point of building on
    Strands: the same graph, tools and structured outputs run unchanged against
    Bedrock or the Anthropic API, so a provider outage or an account still under
    verification costs a single environment variable, not a rewrite.
    """
    if PROVIDER == "anthropic":
        from strands.models.anthropic import AnthropicModel  # needs strands-agents[anthropic]

        return AnthropicModel(
            model_id=model_id,
            params={"temperature": temperature, "max_tokens": 8000},
        )

    return BedrockModel(
        region_name=REGION,
        model_id=model_id,
        temperature=temperature,
        max_tokens=8000,
    )


def build_reconciler() -> Agent:
    return Agent(
        name="reconciler",
        model=_model(ROUTINE_MODEL),
        tools=tools.RECONCILER_TOOLS,
        structured_output_model=ReconcileReport,
        system_prompt=HOUSE_RULES + """

YOUR JOB: tie every credit on the bank statement to the gifts that produced it.

Call match_deposits first. It returns one row per credit, already reconciled
arithmetically, with a status:

- "matched": the credit is fully accounted for. Mark it auto_cleared and move on.
- "ambiguous": a candidate exists but the records cannot confirm it. This is
  exactly the case you must escalate. Put the candidate in the options along
  with the honest alternative, and say what evidence would settle it.
- "unmatched": nothing plausible. Escalate.

Emit one DepositDecision per credit, and one Escalation per credit that needs
the treasurer. Do not invent bank lines and do not merge two credits into one.
""")


def build_acknowledger() -> Agent:
    return Agent(
        name="acknowledger",
        model=_model(JUDGMENT_MODEL, temperature=0.3),
        tools=tools.ACKNOWLEDGER_TOOLS,
        structured_output_model=AcknowledgementReport,
        system_prompt=HOUSE_RULES + f"""

YOUR JOB: make sure every donor gets the written acknowledgement they are owed,
and classify the gifts that need special treatment.

You write the LANGUAGE once, as three templates. A renderer fills in each
donor's figures afterwards, so your templates must use only these placeholders
and must contain no amounts of your own: {{donor}}, {{amount}}, {{date}}, {{org}},
{{description}}, {{fmv}}, {{deductible}}.

The three templates:

- cash: a plain gift. Must state the amount, the date, and that no goods or
  services were provided in return.
- in_kind: donated property. Describe what was received. State NO value: a
  charity does not value a donor's in-kind gift, the donor does. Getting this
  right matters - putting a number here would be wrong.
- quid_pro_quo: the donor received something back. Must state the amount paid,
  the fair market value received, and that only the difference is deductible.

Then call deductible_portion for each gift and classify it. When
`determinable` is false, the fair market value was never recorded: you cannot
compute the deductible portion, so escalate that gift and ask the treasurer for
the value. Do not assume the whole payment is deductible and do not invent a
fair market value, however obvious it seems.
""")


def build_compliance() -> Agent:
    return Agent(
        name="compliance",
        model=_model(JUDGMENT_MODEL),
        tools=tools.COMPLIANCE_TOOLS,
        structured_output_model=ComplianceReport,
        system_prompt=HOUSE_RULES + """

YOUR JOB: make sure restricted money was spent only as the grant permits, and
draft the interim report to the funder.

Work in this order:

1. read_grant_agreement, and read the clauses properly. Extract the per-item
   capital equipment cap, the clause number that imposes it, the clause that
   says what happens when it is breached, the allowable cost categories, and
   the date the interim report is due.

2. list_expenses, then call test_expense_against_grant for EVERY expense,
   passing the rule you extracted. Do not compare amounts yourself - that tool
   exists so the comparison is exact, and you must use it even where the answer
   looks obvious.

3. Escalate any expense the tool flags, citing the clause number by hand
   (e.g. "clause 6(b)") and giving the treasurer the real options: seek the
   funder's retrospective approval, or move the cost off the restricted fund.
   Say what the agreement says happens if neither is done.

4. Call fund_balance and draft the interim report body using only figures the
   tools returned. Include what the agreement asks for: spend by category,
   the unexpended balance, and the reporting period.
""")


def build_graph():
    """reconciler -> acknowledger -> compliance.

    Sequential because the order is the treasurer's own: money must be tied to
    donors before letters can be written, and letters precede the funder report.
    """
    b = GraphBuilder()
    b.set_graph_id("almoner-month-close")
    b.set_max_node_executions(6)          # three nodes, no cycles; a cheap guard rail
    b.set_execution_timeout(600)
    b.add_node(build_reconciler(), "reconciler")
    b.add_node(build_acknowledger(), "acknowledger")
    b.add_node(build_compliance(), "compliance")
    b.add_edge("reconciler", "acknowledger")
    b.add_edge("acknowledger", "compliance")
    b.set_entry_point("reconciler")
    return b.build()


TASK = """
Close the books for {org} for {period}.

Reconcile the month's bank credits, prepare the donor acknowledgements, and
check restricted-fund spending against the grant agreement. Escalate only what
genuinely needs the treasurer.
"""


def month_close_task(period: str = "August 2026", org: str = ORG) -> str:
    return TASK.format(org=org, period=period).strip()
