#!/usr/bin/env python3
"""calibration.py — the self-correction half of compounding intelligence.

settle.py records, for every resolved competition, the win% the system PREDICTED
at registration (an immutable snapshot) next to the ACTUAL outcome. This tool reads
that ledger (OUTCOMES.tsv) and measures how well-calibrated the triage predictions
were — so the system's judgement improves with every finished competition instead
of repeating the same optimism/pessimism.

Outputs CALIBRATION_REPORT.md: Brier score, over/under-confidence, and a concrete
nudge for triage_competition.py weights. Read-only on OUTCOMES; writes one report.

usage: calibration.py [--outcomes OUTCOMES.tsv] [--out CALIBRATION_REPORT.md]
"""
import argparse
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OCOLS = ["key", "lane", "first_seen", "expected_announce", "resolved_date",
         "predicted_win", "judge_quality", "outcome", "placement",
         "prize_won_krw", "evidence", "postmortem"]
WON = {"won": 1.0, "placed": 1.0}
LOST = {"lost": 0.0, "no_award": 0.0}


def load(path):
    rows = []
    if not os.path.exists(path):
        return rows
    hdr = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split("\t")
        if hdr is None and p[0] == "key":
            hdr = p
            continue
        rows.append(dict(zip(hdr or OCOLS, p + [""] * (len(OCOLS) - len(p)))))
    return rows


def num(v):
    try:
        return float(str(v).strip().rstrip("%")) / (100 if float(str(v).strip().rstrip("%")) > 1 else 1)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcomes", default=os.path.join(ROOT, "OUTCOMES.tsv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "CALIBRATION_REPORT.md"))
    a = ap.parse_args()
    rows = load(a.outcomes)
    # only rows with both a prediction and a binary-resolvable outcome
    pairs = []
    for r in rows:
        oc = (r.get("outcome") or "").strip()
        p = num(r.get("predicted_win"))
        y = WON.get(oc, LOST.get(oc))
        if p is not None and y is not None:
            pairs.append((r["key"], p, y))

    L = [f"# Calibration Report — {datetime.now():%Y-%m-%d %H:%M}", "",
         "How well the triage win% predictions matched reality. This is the signal that",
         "makes the system *smarter over time* — not just busier.", ""]
    if not pairs:
        L += ["No resolved competitions with both a prediction and a win/loss outcome yet.",
              "Run `ph settle close <key> --outcome won|placed|lost|no_award --evidence …` on",
              "finished competitions to accumulate calibration data.", ""]
        _write(a.out, L)
        print(f"calibration: 0 resolved pairs → {os.path.basename(a.out)}")
        return

    n = len(pairs)
    brier = sum((p - y) ** 2 for _, p, y in pairs) / n
    mean_pred = sum(p for _, p, y in pairs) / n
    base_rate = sum(y for _, p, y in pairs) / n
    bias = mean_pred - base_rate  # >0 overconfident, <0 underconfident
    L += [f"- resolved pairs: **{n}**",
          f"- Brier score: **{brier:.3f}** (0 = perfect, 0.25 = coin-flip; lower is better)",
          f"- mean predicted win%: {mean_pred*100:.0f}%  ·  actual win rate: {base_rate*100:.0f}%",
          f"- confidence bias: **{bias*100:+.0f} pp** "
          f"({'OVER-confident — triage should discount win% ' if bias > 0.05 else 'UNDER-confident — triage may raise win% ' if bias < -0.05 else 'well-calibrated'})", "",
          "## Per-competition (predicted → actual)", "",
          "| key | predicted win% | actual | miss |", "|---|---:|---|---:|"]
    for k, p, y in sorted(pairs, key=lambda t: abs(t[1] - t[2]), reverse=True):
        L.append(f"| {k} | {p*100:.0f}% | {'WON' if y else 'lost'} | {abs(p-y)*100:.0f}pp |")
    nudge = ("Discount triage win_prob by ~{:.0f}% until bias closes.".format(abs(bias)*100)
             if abs(bias) > 0.05 else "Weights are well-calibrated — hold.")
    L += ["", "## Triage nudge", "", f"- {nudge}",
          "- Feed this back into `triage_competition.py` win-probability priors (the",
          "  self-correction loop). Re-run after each new batch of resolved competitions.", ""]
    _write(a.out, L)
    print(f"calibration: n={n} brier={brier:.3f} bias={bias*100:+.0f}pp → {os.path.basename(a.out)}")


def _write(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)


if __name__ == "__main__":
    main()
