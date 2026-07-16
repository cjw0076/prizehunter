#!/usr/bin/env python3
"""activation.py — measure the activation funnel (north-star #1).

Derives each stage from durable artifacts (no self-report):
  setup     .runs/setup_stamp            (touched by setup.sh)
  discover  MASTER_CATALOG.md exists     (ph discover ran)
  register  portfolio_registry.tsv has >=1 data row (first competition entered)
  submit    any submission evidence      (submission logs / board)

Appends stage transitions to .runs/activation.jsonl (append-only, timestamped)
and prints the funnel. `ph status` shows the one-liner; `ph qa` stays separate.
"""
import json
import os
import sys
import time

PH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOG = os.path.join(PH, ".runs", "activation.jsonl")


def registry_rows():
    p = os.path.join(PH, "portfolio_registry.tsv")
    if not os.path.exists(p):
        return 0
    rows = [l for l in open(p, encoding="utf-8")
            if l.strip() and not l.startswith("#") and not l.startswith("key\t")]
    return len(rows)


def has_submission():
    board = os.path.join(PH, "SUBMISSION_BOARD.tsv")
    if os.path.exists(board) and len(open(board, encoding="utf-8").read().strip().splitlines()) > 1:
        return True
    camp = os.path.join(PH, "campaigns")
    if os.path.isdir(camp):
        for root, _, files in os.walk(camp):
            if "submission_log.jsonl" in files:
                return True
    return False


def stages():
    return {
        "setup": os.path.exists(os.path.join(PH, ".runs", "setup_stamp")),
        "discover": os.path.exists(os.path.join(PH, "MASTER_CATALOG.md")),
        "register": registry_rows() > 0,
        "submit": has_submission(),
    }


def recorded():
    done = set()
    if os.path.exists(LOG):
        for line in open(LOG, encoding="utf-8"):
            try:
                done.add(json.loads(line)["stage"])
            except Exception:
                pass
    return done


def main():
    st, seen = stages(), recorded()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        for stage, hit in st.items():
            if hit and stage not in seen:
                f.write(json.dumps({"stage": stage, "ts": int(time.time())}) + "\n")
    order = ["setup", "discover", "register", "submit"]
    bar = " → ".join(("✅" if st[s] else "◻️") + s for s in order)
    reached = sum(st[s] for s in order)
    if "--line" in sys.argv:
        print(f"activation: {bar}  ({reached}/4)")
        return
    print(f"## Activation funnel  ({reached}/4)")
    print(bar)
    nxt = next((s for s in order if not st[s]), None)
    hint = {"setup": "bash setup.sh", "discover": "ph discover",
            "register": "add your first competition row (ph money → ph plan)",
            "submit": "drive it: ph run <key> → submit within the gate"}
    if nxt:
        print(f"next stage → {hint[nxt]}")
    else:
        print("fully activated — the loop is live. next → ph goal --board")


if __name__ == "__main__":
    main()
