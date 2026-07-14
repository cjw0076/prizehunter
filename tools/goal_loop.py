#!/usr/bin/env python3
"""goal_loop.py — the per-competition #1-or-ceiling verdict.

Makes the control plane a GOAL loop, not just a supervise loop: keep pushing a
competition until it hits rank #1, an adversarially-verified honest ceiling, or its
deadline. Each tick, call this per GO competition; it reads the registry gap and the
best-score history, and returns a verdict + the next lever tuned to that competition.

verdicts:
  AT_#1     — best >= rank1: bank it, mark settled, move to the next competition.
  PUSH      — gap>0 and still improving: here is the next lever for THIS comp's metric.
  CEILING?  — gap>0 but stalled N cycles: do NOT stop yet — adversarially verify
              (ph council) and check the live LB; only stop if the ceiling survives.
  NO_TARGET — no scored submission / no rank1 known yet: get a first scored entry.

State per competition in .runs/goal_<key>.json (best history) drives stall detection.

usage: goal_loop.py --key <key> [--record <best>]   # --record appends a new best then verdicts
       goal_loop.py --board                          # verdict for every active/submitted comp
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

STATE_DIR = os.path.join(CT, ".runs")
STALL_CYCLES = 3          # N cycles with < REL_EPS improvement → ceiling candidate
REL_EPS = 0.002           # 0.2% relative improvement counts as progress
LIVE = {"active", "submitted", "ready-gate", "polishing", "recon"}


def num(v):
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group(0)) if m else None


def gap_of(r):
    b, r1, d = num(r.get("best")), num(r.get("rank1")), r.get("direction")
    if b is None or r1 is None:
        return None, b, r1
    return (r1 - b if d == "max" else b - r1), b, r1


def state_path(key):
    return os.path.join(STATE_DIR, f"goal_{re.sub(r'[^a-zA-Z0-9_-]', '_', key)}.json")


def load_state(key):
    try:
        return json.load(open(state_path(key)))
    except Exception:
        return {"history": []}


def save_state(key, st):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st, open(state_path(key), "w"))


def stalled(history, direction):
    if len(history) < STALL_CYCLES:
        return False
    recent = [h["best"] for h in history[-STALL_CYCLES:]]
    best0 = recent[0] or 1e-9
    improved = max((abs(x - best0) / (abs(best0) or 1e-9)) for x in recent)
    return improved < REL_EPS


def lever(r):
    key, metric, d = r["key"], r.get("metric", "?"), r.get("direction", "?")
    return (f"ph inherit {key}  (inherit proven approaches for this domain/metric) "
            f"→ ph council \"best next lever for {metric} on {key}?\" "
            f"→ optimize toward the winning lever → submit → re-verdict")


def verdict(r, record=None):
    key = r["key"]
    if r.get("status") in {"settled", "closed", "lapsed", "drop", "hold", "ceiling"}:
        return "DONE", f"{key}: status={r['status']} — loop closed."
    g, b, r1 = gap_of(r)
    if b is None or r1 is None:
        return "NO_TARGET", f"{key}: no scored best / rank1 yet → get one scored submission first ({lever(r)})."
    st = load_state(key)
    if record is not None:
        rn = num(record)
        if rn is not None:
            st["history"].append({"best": rn, "at": None})
            save_state(key, st)
            b = rn
            g = (r1 - b if r.get("direction") == "max" else b - r1)
    if g <= 0:
        return "AT_#1", f"{key}: best {b} vs rank1 {r1} → AT/ABOVE #1. Bank it (ph settle close), move on."
    if stalled(st.get("history", []), r.get("direction")):
        return "CEILING?", (f"{key}: gap {g:.4g} but stalled {STALL_CYCLES} cycles. Do NOT stop — "
                            f"adversarially verify: ph council \"is {key} at an honest ceiling or luck-mining?\" "
                            f"+ check live LB (if teams sit above our best, keep pushing). Only stop if it survives.")
    return "PUSH", f"{key}: gap {g:.4g} to #1 ({r.get('metric')}). Keep going → {lever(r)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key")
    ap.add_argument("--record")
    ap.add_argument("--board", action="store_true")
    a = ap.parse_args()
    rows = P.parse_registry(with_extras=False)
    if a.board or not a.key:
        live = [r for r in rows if r.get("status") in LIVE]
        print(f"## Goal loop — {len(live)} live competitions, target = rank #1 each\n")
        order = {"PUSH": 0, "CEILING?": 1, "NO_TARGET": 2, "AT_#1": 3, "DONE": 4}
        out = [(verdict(r)) for r in live]
        for v, msg in sorted(out, key=lambda t: order.get(t[0], 9)):
            print(f"- [{v}] {msg}")
        print("\n→ Each tick: drive every PUSH toward #1; verify every CEILING? before stopping; "
              "bank every AT_#1. The loop ends per-competition only at #1, a verified ceiling, or deadline.")
        return
    r = next((x for x in rows if x["key"] == a.key), None)
    if not r:
        sys.exit(f"unknown key: {a.key}")
    v, msg = verdict(r, a.record)
    print(f"[{v}] {msg}")


if __name__ == "__main__":
    main()
