"""An append-only ledger.

Nothing is ever updated in place. A treasurer's approval is a new row that
supersedes an earlier one, so the queue can always answer "who decided this,
and when" - which is the whole point of a book of account.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.environ.get(
    "ALMONER_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "almoner.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    period      TEXT NOT NULL,
    handled     INTEGER DEFAULT 0,
    escalated   INTEGER DEFAULT 0,
    notes       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    ref         TEXT NOT NULL,
    kind        TEXT NOT NULL,
    disposition TEXT NOT NULL,
    headline    TEXT NOT NULL,
    reason      TEXT NOT NULL,
    citation    TEXT DEFAULT '',
    options     TEXT DEFAULT '[]',
    node        TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

-- Append-only. A later row for the same ref supersedes an earlier one.
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    ref         TEXT NOT NULL,
    decided_by  TEXT NOT NULL,
    choice      TEXT NOT NULL,
    note        TEXT DEFAULT '',
    decided_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS letters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    gift_id     TEXT NOT NULL,
    donor       TEXT NOT NULL,
    body        TEXT NOT NULL,
    sent        INTEGER DEFAULT 0,   -- always 0. Almoner drafts; it never sends.
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    node        TEXT NOT NULL,
    event       TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_queue_run ON queue(run_id);
CREATE INDEX IF NOT EXISTS idx_decisions_ref ON decisions(ref);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def start_run(conn: sqlite3.Connection, run_id: str, period: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO runs (run_id, started_at, period) VALUES (?, ?, ?)",
        (run_id, now(), period),
    )
    conn.commit()


def add_queue_item(conn: sqlite3.Connection, run_id: str, item: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO queue (run_id, ref, kind, disposition, headline, reason,
                              citation, options, node, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, item["ref"], item["kind"], item["disposition"], item["headline"],
            item["reason"], item.get("citation", ""),
            json.dumps(item.get("options", [])), item.get("node", ""), now(),
        ),
    )
    conn.commit()


def add_letter(conn: sqlite3.Connection, run_id: str, gift_id: str, donor: str, body: str) -> None:
    conn.execute(
        "INSERT INTO letters (run_id, gift_id, donor, body, sent, created_at) VALUES (?,?,?,?,0,?)",
        (run_id, gift_id, donor, body, now()),
    )
    conn.commit()


def trace(conn: sqlite3.Connection, run_id: str, node: str, event: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO traces (run_id, node, event, detail, at) VALUES (?,?,?,?,?)",
        (run_id, node, event, detail[:2000], now()),
    )
    conn.commit()


def record_decision(conn: sqlite3.Connection, run_id: str, ref: str,
                    decided_by: str, choice: str, note: str = "") -> None:
    """The treasurer answers an escalation. Appends; never overwrites."""
    conn.execute(
        "INSERT INTO decisions (run_id, ref, decided_by, choice, note, decided_at) VALUES (?,?,?,?,?,?)",
        (run_id, ref, decided_by, choice, note, now()),
    )
    conn.commit()


def finalise_run(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    row = conn.execute(
        """SELECT
             SUM(disposition != 'needs_your_decision') AS handled,
             SUM(disposition  = 'needs_your_decision') AS escalated
           FROM queue WHERE run_id = ?""",
        (run_id,),
    ).fetchone()
    handled, escalated = int(row["handled"] or 0), int(row["escalated"] or 0)
    conn.execute("UPDATE runs SET handled=?, escalated=? WHERE run_id=?",
                 (handled, escalated, run_id))
    conn.commit()
    return {"handled": handled, "escalated": escalated}


def queue_for_run(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """The queue, with any answered escalations resolved by the latest decision."""
    rows = conn.execute(
        "SELECT * FROM queue WHERE run_id = ? ORDER BY disposition = 'needs_your_decision' DESC, id",
        (run_id,),
    ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["options"] = json.loads(item["options"] or "[]")
        # Scoped to this run: closing the month again must start from a clean
        # queue, not inherit answers given to a previous close.
        latest = conn.execute(
            "SELECT choice, decided_by, decided_at FROM decisions "
            "WHERE run_id=? AND ref=? ORDER BY id DESC LIMIT 1",
            (run_id, r["ref"]),
        ).fetchone()
        item["decision"] = dict(latest) if latest else None
        out.append(item)
    return out
