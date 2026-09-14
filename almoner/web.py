"""The review queue.

This is the product. The treasurer opens one page, sees how much was handled
without her, answers the few things that need her, and closes the tab.

Nothing here can send anything to anyone.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import ledger, loaders
from .run import PERIOD, build_queue, persist

BASE = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

app = FastAPI(title="Almoner", docs_url=None, redoc_url=None)

TREASURER = "Meena Raghavan"
ORG = "Kalyani Literacy Trust"


def latest_run(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    return row["run_id"] if row else None


def ensure_run(conn: sqlite3.Connection) -> str:
    """A first visit should show a working queue, not an empty shell."""
    run_id = latest_run(conn)
    if run_id:
        return run_id
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    persist(build_queue(), run_id)
    return run_id


def _counts(items: list[dict]) -> dict:
    escalated = [i for i in items if i["disposition"] == "needs_your_decision"]
    answered = [i for i in escalated if i["decision"]]
    return {
        "total": len(items),
        "handled": len(items) - len(escalated),
        "escalated": len(escalated),
        "outstanding": len(escalated) - len(answered),
    }


@app.get("/", response_class=HTMLResponse)
def queue(request: Request):
    conn = ledger.connect()
    run_id = ensure_run(conn)
    items = ledger.queue_for_run(conn, run_id)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    letters = conn.execute(
        "SELECT COUNT(*) c FROM letters WHERE run_id=?", (run_id,)
    ).fetchone()["c"]
    conn.close()

    needs = [i for i in items if i["disposition"] == "needs_your_decision"]
    handled = [i for i in items if i["disposition"] != "needs_your_decision"]
    return templates.TemplateResponse(request, "queue.html", {
        "org": ORG, "period": PERIOD, "run_id": run_id,
        "started": run["started_at"] if run else "",
        "needs": needs, "handled": handled, "letters": letters,
        "counts": _counts(items), "treasurer": TREASURER,
    })


@app.post("/decide/{ref}", response_class=HTMLResponse)
def decide(request: Request, ref: str, choice: str = Form(...), note: str = Form("")):
    """Record the treasurer's answer. Appends to the ledger; overwrites nothing."""
    conn = ledger.connect()
    run_id = latest_run(conn)
    ledger.record_decision(conn, run_id, ref, TREASURER, choice, note)
    items = ledger.queue_for_run(conn, run_id)
    item = next(i for i in items if i["ref"] == ref)
    conn.close()

    # htmx swaps the single row; a plain browser gets the whole page back.
    if request.headers.get("HX-Request") != "true":
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "_item.html", {
        "i": item, "counts": _counts(items), "swap_counter": True,
    })


@app.get("/letters", response_class=HTMLResponse)
def letters(request: Request):
    conn = ledger.connect()
    run_id = latest_run(conn)
    rows = conn.execute(
        "SELECT * FROM letters WHERE run_id=? ORDER BY id", (run_id,)
    ).fetchall()
    conn.close()
    return templates.TemplateResponse(request, "letters.html", {
        "org": ORG, "period": PERIOD, "letters": [dict(r) for r in rows],
    })


@app.get("/item/{ref}", response_class=HTMLResponse)
def item_detail(request: Request, ref: str):
    """The trace: which node produced this row, from which record, on what basis."""
    conn = ledger.connect()
    run_id = latest_run(conn)
    item = next((i for i in ledger.queue_for_run(conn, run_id) if i["ref"] == ref), None)
    traces = conn.execute(
        "SELECT * FROM traces WHERE run_id=? ORDER BY id", (run_id,)
    ).fetchall()
    conn.close()

    source = None
    if item and item["kind"] == "gift":
        g = next((g for g in loaders.load_gifts() if g.gift_id == ref), None)
        source = g.__dict__ if g else None
    elif item and item["kind"] == "expense":
        e = next((e for e in loaders.load_expenses() if e.expense_id == ref), None)
        source = e.__dict__ if e else None
    elif item and item["kind"] == "deposit":
        n = int(ref.split("-")[1])
        b = next((b for b in loaders.load_bank() if b.line_no == n), None)
        source = b.__dict__ if b else None

    return templates.TemplateResponse(request, "detail.html", {
        "i": item, "source": source, "org": ORG,
        "traces": [dict(t) for t in traces],
    })


@app.post("/rerun")
def rerun():
    """Close the month again from scratch. Deterministic pass only."""
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    persist(build_queue(), run_id)
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health():
    return {"ok": True, "org": ORG, "period": PERIOD}
