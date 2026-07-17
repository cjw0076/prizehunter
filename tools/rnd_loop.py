#!/usr/bin/env python3
"""rnd_loop.py — evolutionary R&D on the SYSTEM itself (not on a competition).

The approach ontology (ph ontology/inherit) evolves how we ATTACK competitions.
This loop evolves the system's OWN methods — verbs, gates, archetypes, QA — by the
same variation → selection → retention cycle, scored on the north-star metrics.

  variation   proposals from QA findings, council, calibration gaps, open issues
  selection   an experiment is KEPT only if its result beat baseline on its target
              metric (activation / brier / uplift / endurance / qa-findings)
  retention   kept experiments become system heuristics; dropped ones become a
              recorded lesson so the same dead end isn't re-proposed

Ledger: RND_EXPERIMENTS.tsv (append-only). Each row is one system-improvement bet.

usage:
  rnd_loop.py board                      show the experiment ledger + selection state
  rnd_loop.py propose                    emit candidate experiments (variation step)
  rnd_loop.py harvest                    turn QA_TEAM_REPORT findings into experiments
  rnd_loop.py add "<hyp>" --metric M --source S
  rnd_loop.py result <id> --value V --baseline B [--note ...]
  rnd_loop.py select                     apply the selection rule (keep/drop) + record
"""
import argparse
import os
import re
import sys
import time

PH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LEDGER = os.path.join(PH, "RND_EXPERIMENTS.tsv")
COLS = ["id", "date", "source", "metric", "hypothesis", "baseline", "result", "status", "note"]
METRICS = {
    "activation": "clone→first-competition without human help (↑)",
    "brier": "triage prediction calibration, lower is better (↓)",
    "uplift": "score vs. raw host-agent baseline on unseen challenges (↑)",
    "endurance": "autonomous cycles per competition before a human is needed (↑)",
    "qa-findings": "P0/P1 findings escaping to a release, lower is better (↓)",
    "coverage": "new competitions inheriting a non-empty strategy (↑)",
}
LOWER_BETTER = {"brier", "qa-findings"}


def rows():
    out = []
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if c[0] == "id":
                continue
            out.append({COLS[i]: (c[i] if i < len(c) else "") for i in range(len(COLS))})
    return out


def write(all_rows):
    with open(LEDGER, "w", encoding="utf-8") as f:
        f.write("# R&D experiments — evolutionary development of the system itself.\n")
        f.write("# variation(propose/harvest) → result → select(keep/drop). Append-only in spirit.\n")
        f.write("\t".join(COLS) + "\n")
        for r in all_rows:
            f.write("\t".join(str(r.get(c, "")) for c in COLS) + "\n")


def next_id(all_rows):
    n = 0
    for r in all_rows:
        m = re.match(r"E(\d+)", r["id"])
        if m:
            n = max(n, int(m.group(1)))
    return f"E{n+1:03d}"


def add(hyp, metric, source, baseline="", note=""):
    all_rows = rows()
    rid = next_id(all_rows)
    all_rows.append({"id": rid, "date": time.strftime("%Y-%m-%d"), "source": source,
                     "metric": metric, "hypothesis": hyp, "baseline": baseline,
                     "result": "", "status": "proposed", "note": note})
    write(all_rows)
    return rid


def cmd_board(_):
    rs = rows()
    if not rs:
        print("no experiments yet. `rnd_loop.py propose` (variation) or `harvest` from QA findings.")
        return
    by = {}
    for r in rs:
        by.setdefault(r["status"], []).append(r)
    order = ["running", "proposed", "kept", "dropped"]
    print("## R&D ledger — evolving the system (variation → selection → retention)\n")
    for st in order + [k for k in by if k not in order]:
        for r in by.get(st, []):
            tag = {"kept": "✅ KEEP", "dropped": "✗ drop", "running": "▶ running",
                   "proposed": "· proposed"}.get(st, st)
            res = f"  [{r['baseline']}→{r['result']}]" if r["result"] else ""
            print(f"- {tag} {r['id']} ({r['metric']}, {r['source']}){res}: {r['hypothesis']}")
    kept = len(by.get("kept", []))
    print(f"\n{len(rs)} experiments · {kept} kept (retained heuristics) · "
          f"{len(by.get('proposed', []))} awaiting a run. next → run one, then `rnd_loop.py result <id> ...`")


def cmd_propose(_):
    # variation: seed candidate experiments from where the system is weakest.
    seeds = [
        ("Auto-inject `ph inherit` output into every plan_campaign run (priming lift)", "uplift", "calibration"),
        ("Add a held-out proxy so ph goal CEILING? is verified offline before stopping", "uplift", "council"),
        ("Endurance counter in settle: cycles-without-human, surfaced in ph status", "endurance", "council"),
        ("Council role-fitness: track which member's review catches the most confirmed P0s", "qa-findings", "qa"),
        ("ChallengeContract compiler so ph goal --design reads structured rules not freeform RECON", "coverage", "council"),
        ("Independent verifier pass before an outcome feeds the ontology (no self-grading)", "uplift", "council"),
    ]
    existing = {r["hypothesis"] for r in rows()}
    print("## Proposed experiments (variation step) — add the ones worth betting on:\n")
    n = 0
    for hyp, metric, src in seeds:
        if hyp in existing:
            continue
        n += 1
        print(f"  ph rnd add \"{hyp}\" --metric {metric} --source {src}")
    if n == 0:
        print("  (all standard seeds already in the ledger — harvest QA findings or add your own)")
    print("\nEach targets a north-star metric. Selection keeps only those that measurably move it.")


def cmd_harvest(_):
    report = os.path.join(PH, "QA_TEAM_REPORT.md")
    if not os.path.exists(report):
        print("no QA_TEAM_REPORT.md — run `ph qa-team` first, then harvest its confirmed findings.")
        return
    text = open(report, encoding="utf-8").read()
    hits = re.findall(r"\[?SEVERITY\s*(P[012])\]?\s*(.+)", text) or re.findall(r"\b(P[012])\b[:\-\s]+(.+)", text)
    if not hits:
        print("QA_TEAM_REPORT.md has no P0/P1/P2-tagged findings to harvest. "
              "Confirm findings manually, then `ph rnd add`.")
        return
    print("## Harvest QA findings → experiments (add the confirmed ones):\n")
    seen = set()
    for sev, title in hits:
        title = title.strip().strip("—-• ")[:110]
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        metric = "qa-findings"
        print(f"  ph rnd add \"{title}\" --metric {metric} --source qa   # {sev}")
    print("\n→ only add findings you VERIFIED against the code; a hallucinated finding poisons the ledger.")


def cmd_add(a):
    if a.metric not in METRICS:
        sys.exit(f"metric must be one of: {', '.join(METRICS)}")
    rid = add(a.hypothesis, a.metric, a.source, note=a.note or "")
    print(f"added {rid} ({a.metric}): {a.hypothesis}\n  → run it, then: rnd_loop.py result {rid} --value V --baseline B")


def cmd_result(a):
    all_rows = rows()
    for r in all_rows:
        if r["id"] == a.id:
            r["result"] = str(a.value)
            if a.baseline != "":
                r["baseline"] = str(a.baseline)
            r["status"] = "running"
            if a.note:
                r["note"] = a.note
            write(all_rows)
            print(f"{a.id}: baseline={r['baseline']} result={r['result']} → run `rnd_loop.py select`")
            return
    sys.exit(f"unknown id: {a.id}")


def cmd_select(_):
    all_rows = rows()
    changed = 0
    for r in all_rows:
        if r["status"] != "running" or r["result"] == "" or r["baseline"] == "":
            continue
        try:
            res, base = float(r["result"]), float(r["baseline"])
        except ValueError:
            continue
        better = (res < base) if r["metric"] in LOWER_BETTER else (res > base)
        r["status"] = "kept" if better else "dropped"
        r["note"] = (r.get("note", "") + f" | selected {r['status']} ({base}->{res})").strip(" |")
        changed += 1
    write(all_rows)
    kept = [r for r in all_rows if r["status"] == "kept"]
    print(f"selection applied to {changed} experiment(s). "
          f"{len(kept)} kept as retained system heuristics.")
    for r in kept:
        print(f"  ✅ {r['id']}: {r['hypothesis']}  ({r['baseline']}→{r['result']} on {r['metric']})")
    if changed == 0:
        print("  (nothing to select — set results first: rnd_loop.py result <id> --value V --baseline B)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("board"); sub.add_parser("propose"); sub.add_parser("harvest"); sub.add_parser("select")
    pa = sub.add_parser("add"); pa.add_argument("hypothesis"); pa.add_argument("--metric", required=True)
    pa.add_argument("--source", default="manual"); pa.add_argument("--note", default="")
    pr = sub.add_parser("result"); pr.add_argument("id"); pr.add_argument("--value", required=True)
    pr.add_argument("--baseline", default=""); pr.add_argument("--note", default="")
    a = ap.parse_args()
    {"board": cmd_board, "propose": cmd_propose, "harvest": cmd_harvest,
     "add": cmd_add, "result": cmd_result, "select": cmd_select}.get(a.cmd, cmd_board)(a)


if __name__ == "__main__":
    main()
