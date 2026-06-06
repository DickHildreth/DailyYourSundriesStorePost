"""Append-only post log for 14-day repeat avoidance.

Stored as JSON Lines at POST_LOG_PATH (default /data/post-log.jsonl) so it can live
on a persistent volume. Each line: {"date","handle","title","tier"}.
"""
from __future__ import annotations

import datetime as dt
import json
import os

LOG_PATH = os.environ.get("POST_LOG_PATH", "/data/post-log.jsonl")
REPEAT_WINDOW_DAYS = 14


def recent_handles(window_days: int = REPEAT_WINDOW_DAYS,
                   today: dt.date | None = None) -> set[str]:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=window_days)
    handles: set[str] = set()
    if not os.path.exists(LOG_PATH):
        return handles
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                d = dt.date.fromisoformat(rec["date"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            if d >= cutoff:
                handles.add(rec.get("handle"))
    return handles


def append(handle: str, title: str, tier: int, today: dt.date | None = None) -> None:
    today = today or dt.date.today()
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    rec = {"date": today.isoformat(), "handle": handle, "title": title, "tier": tier}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
