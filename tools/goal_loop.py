#!/usr/bin/env python3
"""goal_loop.py — a per-competition goal loop that the AGENT DESIGNS from the
competition's own characteristics, not a fixed one-size-fits-all cycle.

Two moves:
  --design <key>  Analyze the competition (metric, direction, submission type, judging,
                  daily slots, data/context from RECON) → pick an ARCHETYPE → emit a
                  proposed LOOP SPEC (termination, per-cycle levers, slot policy,
                  ceiling test). The agent reviews/customizes it for THIS competition's
                  specifics and saves it to .runs/loopspec_<key>.json.
  --key <key>     Run the verdict using that competition's own designed spec (falls back
                  to the archetype default, and tells the agent to design one).

Verdicts: AT_#1 / PUSH / CEILING? / NO_TARGET / DONE — each with the next lever taken
from THIS competition's spec, so the loop itself is competition-shaped.

usage: goal_loop.py --design <key>            # analyze + propose a tailored loop
       goal_loop.py --key <key> [--record B]  # verdict via the designed/archetype spec
       goal_loop.py --board                    # verdict for every live competition
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

STATE_DIR = os.path.join(CT, ".runs")
STALL_CYCLES = 3
REL_EPS = 0.002
LIVE = {"active", "submitted", "ready-gate", "polishing", "recon"}

# Archetype = the SHAPE of a good loop for that kind of competition. The agent tailors it.
ARCHETYPES = {
    "leaderboard-classification": {
        "goal": "rank #1 on the (private) leaderboard",
        "cycle": ["ph inherit <key> (domain approaches)", "leak-free CV anchored to a public point",
                  "feature-engineering", "encoder/GBDT tuning", "ensemble/blend",
                  "ph council: next highest-EV lever", "submit 1 golden candidate within the daily slot"],
        "ceiling_test": "N cycles <0.2% gain AND CV↔LB gap explained AND no team sits above our best on the live LB",
        "slots": "respect daily submission cap; no public-LB probing; one golden candidate per slot",
    },
    "leaderboard-regression": {
        "goal": "rank #1 (minimize/maximize the error metric)",
        "cycle": ["ph inherit <key>", "leak-free CV", "external/context features (lags, domain signals)",
                  "GBDT + robust target handling", "ph council: bias/variance lever", "submit within slot"],
        "ceiling_test": "N cycles <0.2% gain AND OOF↔LB transfer confirmed AND nobody above on live LB",
        "slots": "daily cap; validate offline before spending a slot",
    },
    "code-submission": {
        "goal": "rank #1 by the online score, gated by a reproduced offline eval",
        "cycle": ["reproduce the official offline scorer exactly", "improve until offline gate passes",
                  "ph council: is the gain real or overfit to offline?", "package + submit within slot"],
        "ceiling_test": "offline gain no longer transfers online for N cycles AND no team above",
        "slots": "offline-verify EVERY candidate before an online slot; slots are scarce",
    },
    "rl-agentic": {
        "goal": "rank #1 by the environment/agent score",
        "cycle": ["reproduce the official harness + score", "cluster environments/failure modes",
                  "world-model/search or policy improvement", "ph council: overfit-to-public check",
                  "submit; log traces to the ontology"],
        "ceiling_test": "public-game score plateaus AND held-out/ shuffled-goal eval confirms no headroom",
        "slots": "cost-cap the model tier; cheap baseline before expensive search",
    },
    "timeseries": {
        "goal": "rank #1 (minimize error / maximize settlement metric)",
        "cycle": ["ph inherit <key>", "legal external data (obs/NWP within the rules)",
                  "lag/persistence features", "conditional/decision layer for the payout metric",
                  "ph council: distribution-shift lever", "submit within slot"],
        "ceiling_test": "OOF gains stop transferring (CV-LB fold-sign flips) for N cycles AND nobody above",
        "slots": "daily cap; one hypothesis per slot with a recorded rationale",
    },
    "judged": {  # hackathon / creative / paper — NO numeric rank1; the loop is different
        "goal": "prize-winning JUDGE quality (not a number): the winning lever + 120% evidence",
        "cycle": ["ph gap <key> (mine hidden judge intent + our deficiencies)", "ph creative (diverge angles)",
                  "build the winning lever + reference-grade craft", "ph council: refute overclaim/eligibility",
                  "polish the deliverable (deck/demo/writeup) to product grade"],
        "ceiling_test": "judge-fit + originality + feasibility maxed; remaining work is polish, not a new lever",
        "slots": "no leaderboard; iterate on judge-fit until a separate reviewer pass says winning-quality",
    },
}


def num(v):
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group(0)) if m else None


def archetype_of(r):
    metric = (r.get("metric") or "").lower()
    d = r.get("direction")
    if d not in ("max", "min") or metric in ("n/a", "none", ""):
        return "judged"
    if any(x in metric for x in ("arc", "agent", "reward", "game")):
        return "rl-agentic"
    if any(x in metric for x in ("nmae", "정산", "forecast")) or "time" in metric:
        return "timeseries"
    if "macro_f1" in metric and _is_code(r):
        return "code-submission"
    if any(x in metric for x in ("f1", "accuracy", "logloss", "log_loss", "balanced")):
        return "leaderboard-classification"
    if any(x in metric for x in ("mae", "mse", "rmse", "spearman", "score")):
        return "leaderboard-regression"
    return "leaderboard-classification"


def _is_code(r):
    text = " ".join([r.get("blocker", ""), r.get("next_lever", "")]).lower()
    return any(x in text for x in ("code-submission", "code submission", "notebook", "offline", "kernel"))


def spec_path(key):
    return os.path.join(STATE_DIR, f"loopspec_{re.sub(r'[^a-zA-Z0-9_-]', '_', key)}.json")


def load_spec(key):
    try:
        return json.load(open(spec_path(key)))
    except Exception:
        return None


def state_path(key):
    return os.path.join(STATE_DIR, f"goal_{re.sub(r'[^a-zA-Z0-9_-]', '_', key)}.json")


def design(r):
    key = r["key"]
    arch = archetype_of(r)
    a = ARCHETYPES[arch]
    print(f"## Loop design — {key}")
    print(f"- detected archetype: **{arch}**  (metric={r.get('metric')} direction={r.get('direction')})")
    print(f"- goal / termination: {a['goal']}  (or a verified ceiling, or deadline)")
    print(f"- slot policy: {a['slots']}")
    print(f"- ceiling test (when to consider stopping): {a['ceiling_test']}")
    print("- proposed per-cycle levers (tailor to THIS competition's RECON/data):")
    for i, step in enumerate(a["cycle"], 1):
        print(f"    {i}. {step.replace('<key>', key)}")
    print("\n→ AGENT: read this competition's RECON/data, adjust the levers/ceiling-test to its"
          " specifics (unusual metric, leak, external-data rule, judging rubric, slot count),")
    print(f"   then save the tailored spec:  goal_loop writes it if you pass --save with a JSON, e.g.")
    print(f'   echo \'{{"archetype":"{arch}","cycle":[...],"ceiling_test":"...","goal":"..."}}\' '
          f"> {os.path.relpath(spec_path(key), CT)}")
    print("   The verdict (ph goal <key>) then drives THIS designed loop, not a generic one.")


def stalled(history, direction):
    if len(history) < STALL_CYCLES:
        return False
    recent = [h["best"] for h in history[-STALL_CYCLES:]]
    b0 = recent[0] or 1e-9
    return max((abs(x - b0) / (abs(b0) or 1e-9)) for x in recent) < REL_EPS


def next_lever(r):
    spec = load_spec(r["key"])
    arch = spec.get("archetype") if spec else archetype_of(r)
    cyc = (spec or ARCHETYPES.get(arch, {})).get("cycle", ARCHETYPES[arch]["cycle"])
    tag = "designed spec" if spec else f"{arch} archetype (run `ph goal --design {r['key']}` to tailor)"
    return f"[{tag}] " + " → ".join(s.replace("<key>", r["key"]) for s in cyc[:4]) + " → submit → re-verdict"


def verdict(r, record=None):
    key = r["key"]
    if r.get("status") in {"settled", "closed", "lapsed", "drop", "hold", "ceiling"}:
        return "DONE", f"{key}: status={r['status']} — loop closed."
    arch = (load_spec(key) or {}).get("archetype") or archetype_of(r)
    if arch == "judged":
        return "JUDGED", (f"{key}: no numeric #1 — loop = judge-fit. {next_lever(r)}. "
                          f"Stop only when a separate reviewer pass says winning-quality.")
    b, r1, d = num(r.get("best")), num(r.get("rank1")), r.get("direction")
    if b is None or r1 is None:
        return "NO_TARGET", f"{key}: no scored best/rank1 yet → get a first scored entry. {next_lever(r)}"
    st = json.load(open(state_path(key))) if os.path.exists(state_path(key)) else {"history": []}
    if record is not None and num(record) is not None:
        st["history"].append({"best": num(record)})
        os.makedirs(STATE_DIR, exist_ok=True); json.dump(st, open(state_path(key), "w"))
        b = num(record)
    g = (r1 - b) if d == "max" else (b - r1)
    if g <= 0:
        return "AT_#1", f"{key}: best {b} vs rank1 {r1} → AT/ABOVE #1. Bank (ph settle close) + ph ontology, move on."
    if stalled(st.get("history", []), d):
        ct = (load_spec(key) or ARCHETYPES[arch]).get("ceiling_test", "stalled")
        return "CEILING?", (f"{key}: gap {g:.4g} but stalled. Do NOT stop — verify: {ct}. "
                            f"ph council \"honest ceiling or luck-mining on {key}?\" + check live LB.")
    return "PUSH", f"{key}: gap {g:.4g} to #1 ({r.get('metric')}). {next_lever(r)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key"); ap.add_argument("--record")
    ap.add_argument("--design", metavar="KEY")
    ap.add_argument("--board", action="store_true")
    a = ap.parse_args()
    rows = P.parse_registry(with_extras=False)
    if a.design:
        r = next((x for x in rows if x["key"] == a.design), None)
        if not r:
            sys.exit(f"unknown key: {a.design}")
        design(r); return
    if a.board or not a.key:
        live = [r for r in rows if r.get("status") in LIVE]
        print(f"## Goal loop — {len(live)} live competitions, each driven by its OWN designed loop\n")
        order = {"PUSH": 0, "CEILING?": 1, "JUDGED": 2, "NO_TARGET": 3, "AT_#1": 4, "DONE": 5}
        for v, msg in sorted((verdict(r) for r in live), key=lambda t: order.get(t[0], 9)):
            print(f"- [{v}] {msg}")
        print("\n→ New competition? First `ph goal --design <key>` so the loop fits it, then drive that loop to #1.")
        return
    r = next((x for x in rows if x["key"] == a.key), None)
    if not r:
        sys.exit(f"unknown key: {a.key}")
    v, msg = verdict(r, a.record)
    print(f"[{v}] {msg}")


if __name__ == "__main__":
    main()
