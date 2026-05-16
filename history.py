#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
import os
from datetime import datetime, timedelta

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")
_RETENTION_DAYS = 30


def _conn() -> sqlite3.Connection:
    db = sqlite3.connect(_DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS history (
        ts    INTEGER PRIMARY KEY,
        score REAL,
        r     INTEGER,
        g     INTEGER,
        b     INTEGER
    )""")
    return db


def save(score: float, color: tuple):
    ts = int(datetime.now().timestamp())
    cutoff = int((datetime.now() - timedelta(days=_RETENTION_DAYS)).timestamp())
    with _conn() as db:
        db.execute("INSERT OR REPLACE INTO history VALUES (?,?,?,?,?)",
                   (ts, score, color[0], color[1], color[2]))
        db.execute("DELETE FROM history WHERE ts < ?", (cutoff,))


def load_last_24h() -> list[tuple[float, tuple]]:
    cutoff = int((datetime.now() - timedelta(hours=24)).timestamp())
    try:
        with _conn() as db:
            rows = db.execute(
                "SELECT score, r, g, b FROM history WHERE ts >= ? ORDER BY ts",
                (cutoff,)
            ).fetchall()
        return [(row[0], (row[1], row[2], row[3])) for row in rows]
    except Exception as e:
        print(f"[history] load failed: {e}")
        return []
