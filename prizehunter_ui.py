#!/usr/bin/env python3
"""prizehunter_ui — the registry data core shared by the ph tools.

This module is the single reader for portfolio_registry.tsv: row parsing,
gap math, deadline extraction, and portfolio summary. Tools import it as
`import prizehunter_ui as P` (they sys.path-insert the repo root first).

The name is historic: the original operator instance also serves a local
showcase UI from this module. The shipped product needs only the data core;
a UI can layer on top of these functions without changing any tool.
"""
import json
import os
import re
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(ROOT, "portfolio_registry.tsv")
RECEIPTS = os.path.join(ROOT, "receipts")
OUTBOX = os.path.join(ROOT, "aios_outbox")
NOTES = os.path.join(ROOT, "ui_notes.json")

COLS = ["key", "dir", "ledger", "metric", "direction", "best",
        "rank1", "progress", "status", "blocker", "next_lever"]
MONTHS = {m.lower(): i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_notes():
    if os.path.exists(NOTES):
        try:
            return json.load(open(NOTES, encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def extract_deadline(*texts):
    today = datetime.now().date()
    yr = today.year
    dates = []
    text = " ".join(t or "" for t in texts)
    # YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD (optional time)
    for m in re.finditer(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})(?:\s+\d{1,2}:\d{2})?\b", text):
        try:
            dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date())
        except ValueError:
            pass
    # English month + day (assume current year)
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})\b", text, re.I):
        try:
            dates.append(datetime(yr, MONTHS[m.group(1).lower()[:3]], int(m.group(2))).date())
        except ValueError:
            pass
    # Korean: [YYYY년] M월 D일
    for m in re.finditer(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일", text):
        try:
            dates.append(datetime(int(m.group(1)) if m.group(1) else yr,
                                  int(m.group(2)), int(m.group(3))).date())
        except ValueError:
            pass
    # bare M/D slash (assume current year) — heuristic, may catch a stray ratio
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})\b", text):
        mo, dy = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= dy <= 31:
            try:
                dates.append(datetime(yr, mo, dy).date())
            except ValueError:
                pass
    # D-N is relative to WRITE time, not read time — a stale "D-1" left in the
    # registry would otherwise read as "due tomorrow" forever and mask a lapsed
    # deadline. Trust D-N only when the text carries no absolute date.
    relative = []
    for m in re.finditer(r"\bD-(\d+)\b", text, re.I):
        relative.append(today + timedelta(days=int(m.group(1))))
    if not dates:
        dates = relative
    if not dates:
        return None, None
    future = [d for d in dates if d >= today]
    # all-past: report the LATEST past date (the deadline), not the earliest mention
    deadline = min(future) if future else max(dates)
    return deadline.isoformat(), (deadline - today).days


# generic tokens that match almost every receipt → useless for attribution
SIG_STOP = {"2024", "2025", "2026", "2027", "video", "media", "challenge", "dacon",
            "kaggle", "prize", "data", "contest", "design", "film", "korea", "korean",
            "ledger", "autocapture", "agent", "ai"}


def signal_count(key):
    """How many agent receipts/outbox files distinctively reference this competition."""
    toks = [t for t in re.split(r"[-_]", key.lower())
            if t not in SIG_STOP and len(t) >= 4 and not (t.isdigit() and len(t) == 4)]
    if not toks:
        return 0
    n = 0
    for d in (RECEIPTS, OUTBOX):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            low = fn.lower()
            if any(t in low for t in toks):
                n += 1
    return n


def parse_registry(with_extras=True):
    rows = []
    notes = load_notes() if with_extras else {}
    if not os.path.exists(REGISTRY):
        return rows
    for line in open(REGISTRY, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0] == "key":
            continue
        row = {COLS[i]: (parts[i] if i < len(parts) else "") for i in range(len(COLS))}
        best, rank1 = _num(row["best"]), _num(row["rank1"])
        gap = None
        if best is not None and rank1 is not None:
            if row["direction"] == "max":
                gap = round(best - rank1, 4)
            elif row["direction"] == "min":
                gap = round(rank1 - best, 4)
        row["progress_n"] = int(_num(row["progress"]) or 0)
        row["gap"] = gap
        row["founder_gate"] = "FOUNDER" in (row["blocker"] or "").upper()
        row["deadline"], row["dday"] = extract_deadline(row["blocker"], row["next_lever"])
        if with_extras:
            row["notes"] = notes.get(row["key"], [])
            row["signals"] = signal_count(row["key"])
        rows.append(row)
    return rows


def summary(rows):
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    return {"total": len(rows), "by_status": by,
            "submitted": by.get("submitted", 0), "active": by.get("active", 0),
            "founder_gates": sum(1 for r in rows if r["founder_gate"]),
            "avg_progress": round(sum(r["progress_n"] for r in rows) / len(rows)) if rows else 0}
