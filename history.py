#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
import os
from datetime import datetime, timedelta
import log_buffer

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")
_RETENTION_DAYS = 30


def _conn() -> sqlite3.Connection:
    db = sqlite3.connect(_DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS history (
        ts      INTEGER,
        station TEXT,
        score   REAL,
        r       INTEGER,
        g       INTEGER,
        b       INTEGER,
        PRIMARY KEY (ts, station)
    )""")
    return db


def save(station_key: str, data_ts: "datetime", score: float, color: tuple):
    """1 row per (RSQA hour, station). Restarts and duplicate fetches are idempotent."""
    ts = int(data_ts.timestamp())
    cutoff = int((datetime.now() - timedelta(days=_RETENTION_DAYS)).timestamp())
    with _conn() as db:
        db.execute("INSERT OR REPLACE INTO history VALUES (?,?,?,?,?,?)",
                   (ts, station_key, score, color[0], color[1], color[2]))
        db.execute("DELETE FROM history WHERE ts < ?", (cutoff,))


def load_last_24h(station_key: str) -> list[tuple["datetime", float, tuple]]:
    """Returns [(data_ts, score, color), ...] for one station, oldest → newest."""
    cutoff = int((datetime.now() - timedelta(hours=24)).timestamp())
    try:
        with _conn() as db:
            rows = db.execute(
                "SELECT ts, score, r, g, b FROM history "
                "WHERE ts >= ? AND station = ? ORDER BY ts",
                (cutoff, station_key)
            ).fetchall()
        return [(datetime.fromtimestamp(r[0]), r[1], (r[2], r[3], r[4])) for r in rows]
    except Exception as e:
        log_buffer.error(f"[history] load failed: {e}")
        return []


def clear():
    try:
        with _conn() as db:
            db.execute("DELETE FROM history")
        log_buffer.info("[history] historique effacé")
    except Exception as e:
        log_buffer.error(f"[history] clear failed: {e}")
