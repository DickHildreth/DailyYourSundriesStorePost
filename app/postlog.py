"""Append-only post log for repeat avoidance and category cooldowns.

Stored as JSON Lines at POST_LOG_PATH (default /data/post-log.jsonl) so it can live
on a persistent volume. Each line includes the original fields plus optional
`product_type` and `theme` metadata for category cooldowns.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile

LOG_PATH = os.environ.get("POST_LOG_PATH", "/data/post-log.jsonl")
REPEAT_WINDOW_DAYS = 14
CATEGORY_COOLDOWN_DAYS = 10


def _resolve_log_path() -> str:
    """Prefer the configured persistent path but fall back to a writable temp path
    for local/test runs where /data is unavailable or read-only.
    """
    candidate = os.environ.get("POST_LOG_PATH", "/data/post-log.jsonl")
    pdir = os.path.dirname(candidate) or "."
    try:
        os.makedirs(pdir, exist_ok=True)
        probe = os.path.join(pdir, ".write_probe")
        with open(probe, "a", encoding="utf-8"):
            pass
        os.remove(probe)
        return candidate
    except OSError:
        fallback = os.path.join(tempfile.gettempdir(), "sundries-post-log.jsonl")
        os.makedirs(os.path.dirname(fallback), exist_ok=True)
        return fallback


LOG_PATH = _resolve_log_path()


def _normalize_category_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(text.split())


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
                handle = rec.get("handle")
                if handle:
                    handles.add(str(handle))
    return handles


def recent_category_signals(window_days: int = CATEGORY_COOLDOWN_DAYS,
                           today: dt.date | None = None) -> tuple[set[str], set[str]]:
    """Return normalized recent product types and theme keys for cooldown checks.

    Old log entries do not have the new fields and are treated as unknown.
    """
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=window_days)
    types: set[str] = set()
    themes: set[str] = set()
    if not os.path.exists(LOG_PATH):
        return types, themes
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
            if d < cutoff:
                continue
            product_type = _normalize_category_key(rec.get("product_type"))
            if product_type:
                types.add(product_type)
            theme = _normalize_category_key(rec.get("theme"))
            if theme:
                themes.add(theme)
    return types, themes


def append(handle: str, title: str, tier: int,
           today: dt.date | None = None,
           product_type: str | None = None,
           theme: str | None = None) -> None:
    today = today or dt.date.today()
    path = _resolve_log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rec = {
        "date": today.isoformat(),
        "handle": handle,
        "title": title,
        "tier": tier,
        "product_type": product_type,
        "theme": theme,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
