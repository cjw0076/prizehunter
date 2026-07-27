#!/usr/bin/env bash
# meta_learn.sh — RECURSIVE PROCESS IMPROVEMENT (the loop that was missing).
#
# learn.sh compounds WHAT worked (domain levers). This compounds HOW TO DRIVE:
#   • priors <task_type>  — rank research LENSES by measured gain-per-compute on that task-type, so the next
#                           tournament spends its budget on strategies that actually pay (research_drive reads this).
#   • allocate            — EV ranking across the board: headroom × prize-ish weight × P(gain|history) / cost.
#                           This is the direct fix for "천장 대회에 토큰만 낭비" — exhausted tasks fall to the bottom.
#   • exhausted <tt>      — paradigm-exhaustion flag: if the last K rounds on a task-type produced no confirmed
#                           gain, the next tournament MUST include the paradigm-shift lens (stop polishing a dead
#                           framing; ADIA's two-sample plateau is the textbook case).
#   • report              — the process scoreboard (what the system has learned about its own searching).
#
# Source of truth: PROCESS_LOG.tsv (appended by research_drive.sh):
#   ts key task_type phase lens before after gain cost_s verdict note
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"
PLOG="${PH_PLOG:-$CT/PROCESS_LOG.tsv}"; BOARD="${PH_BOARD:-$R/autopush_board.tsv}"
mkdir -p "$R"; touch "$PLOG" "$BOARD"   # fresh install: state files may not exist yet
PY=python3

case "${1:-report}" in
  priors)
    TT="${2:?task_type}"
    $PY - "$PLOG" "$TT" <<'EOF'
import sys, collections
plog, tt = sys.argv[1], sys.argv[2]
agg = collections.defaultdict(lambda: {"gain": 0.0, "cost": 0.0, "n": 0, "wins": 0})
rows = 0
for line in open(plog):
    if line.startswith("#") or not line.strip(): continue
    f = line.rstrip("\n").split("\t")
    if len(f) < 10 or f[3] != "diverge": continue
    if f[2] != tt: continue
    lens = f[4]
    try: g = float(f[7])
    except Exception: g = 0.0
    try: c = float(f[8])
    except Exception: c = 0.0
    a = agg[lens]; a["gain"] += max(g, 0.0); a["cost"] += c; a["n"] += 1; a["wins"] += (1 if g > 0 else 0)
    rows += 1
# default order when we have no evidence yet: cheap-and-reliable first, paradigm-shift held for exhaustion
DEFAULT = ["validation-structure-exploitation","problem-reformulation","ensemble-decorrelation",
           "representation-expansion","data-generating-process","metric-exploitation",
           "legal-side-information","constraint-projection-postprocessing","external-transfer","paradigm-shift"]
if not rows:
    for l in DEFAULT: print(f"{l}\t(no evidence yet — default prior)")
    sys.exit()
# score = gain per 1000 compute-seconds, with a win-rate prior so a single lucky run doesn't dominate
scored = []
for l, a in agg.items():
    gpc = a["gain"] / max(a["cost"], 1.0) * 1000
    wr = (a["wins"] + 1) / (a["n"] + 2)          # Laplace-smoothed
    scored.append((gpc * wr, l, a, gpc, wr))
scored.sort(reverse=True)
seen = set()
for s, l, a, gpc, wr in scored:
    seen.add(l)
    print(f"{l}\tscore={s:.4f} gain/1ks={gpc:.4f} win={wr:.2f} n={a['n']}")
for l in DEFAULT:                                # untried lenses stay in the pool (exploration)
    if l not in seen: print(f"{l}\t(untried — exploration slot)")
EOF
    ;;

  exhausted)
    TT="${2:?task_type}"; K="${3:-2}"
    $PY - "$PLOG" "$TT" "$K" <<'EOF'
import sys
plog, tt, K = sys.argv[1], sys.argv[2], int(sys.argv[3])
rounds = [f for f in (l.rstrip("\n").split("\t") for l in open(plog)
          if not l.startswith("#") and l.strip())
          if len(f) >= 10 and f[3] == "refute" and f[2] == tt]
last = rounds[-K:]
if len(last) < K:
    print(f"UNKNOWN\tonly {len(last)} refute round(s) recorded for '{tt}' (need {K})"); sys.exit()
dead = all(r[9] in ("all-refuted", "no-claim") for r in last)
print(("EXHAUSTED" if dead else "ALIVE") +
      f"\tlast {K} rounds: " + ", ".join(r[9] for r in last) +
      ("\t→ next tournament MUST include the paradigm-shift lens" if dead else ""))
EOF
    ;;

  allocate)
    $PY - "$PLOG" "$BOARD" "$CT/portfolio_registry.tsv" <<'EOF'
import sys, collections, os, re, math
plog, board = sys.argv[1], sys.argv[2]
reg = sys.argv[3] if len(sys.argv) > 3 else ""
hist = collections.defaultdict(lambda: {"g": 0.0, "c": 0.0, "n": 0, "w": 0})
for line in open(plog):
    if line.startswith("#") or not line.strip(): continue
    f = line.rstrip("\n").split("\t")
    if len(f) < 10 or f[3] != "diverge": continue
    h = hist[f[1]]
    try: g = float(f[7])
    except Exception: g = 0.0
    try: c = float(f[8])
    except Exception: c = 0.0
    h["g"] += max(g, 0.0); h["c"] += c; h["n"] += 1; h["w"] += (1 if g > 0 else 0)
def rows_from_registry(path):
    """SINGLE SOURCE OF TRUTH: the registry (62 rows), not the legacy 12-row board. Reading only the board is why
    50 competitions were invisible to EV allocation and to the cockpit (SYSTEM_GAP_REPORT #2)."""
    cols = []
    out = []
    try:
        for l in open(path):
            if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1: cols.append(l.split()[1])
            elif not l.startswith("#"): break
        g = lambda f, n: f[cols.index(n)] if n in cols and cols.index(n) < len(f) else ""
        for l in open(path):
            if l.startswith("#") or not l.strip(): continue
            f = l.rstrip("\n").split("\t")
            if g(f, "key") in ("key", ""): continue      # literal header row, not a competition
            st = g(f, "status")
            if st in ("lapsed", "settled", "dropped"): continue
            metric = g(f, "metric")
            if metric in ("n/a", "", "-"): continue          # judged rows are not EV-allocated here
            out.append((g(f, "key"), "leaderboard", g(f, "direction") or "max", g(f, "best"), g(f, "rank1")))
    except Exception:
        pass
    return out
src = rows_from_registry(reg) if reg and os.path.exists(reg) else []
if not src:                                                   # fallback: legacy board
    for line in open(board):
        if line.startswith("#") or not line.strip(): continue
        f = (line.rstrip("\n").split("\t") + [""] * 8)[:8]
        src.append((f[0], f[1], f[2], f[3], f[4]))
# ── PORTFOLIO BASE RATE: what fraction of our drives have EVER produced a gain? An untried competition must
# inherit THIS, not an optimistic 0.5. The flat 0.5 prior was an ESCAPE VALVE: the moment a real competition hit
# REFUTE, a zero-history row got a manufactured high EV and justified jumping domains instead of fixing the stall
# (resonance R2 attack, 2026-07-26).
tot_n = sum(h["n"] for h in hist.values())
tot_w = sum(h["w"] for h in hist.values())
BASE = (tot_w + 1) / (tot_n + 2) if tot_n else 0.20      # measured; falls back to a deliberately sober 0.20

# ── STALL STATE: escaping a stall is the highest-value work the machine can do, and it is exactly what the
# evolution machinery exists for. A REFUTE/HARD_PIVOT row therefore OUTRANKS a fresh row, it does not lose to it.
stall = {}
try:
    import subprocess
    board_txt = subprocess.run(["python3", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(reg))),
                                "competitions/control_tower/tools/goal_loop.py") if False else
                                os.path.join(os.path.dirname(reg), "tools", "goal_loop.py"), "--board"],
                               capture_output=True, text=True, timeout=180).stdout
    for line in board_txt.splitlines():
        m = re.search(r"\[(REFUTE|HARD_PIVOT|AT_#1|DONE)\]\s+([A-Za-z0-9._-]+)", line)
        if m:
            stall[m.group(2)] = m.group(1)
except Exception:
    pass

out = []
for key, typ, d, best, target in src:
    if typ != "leaderboard": continue
    def num(x):
        """Lenient numeric parse. A stray suffix ("0.5636val", "1.8%") used to make float() fail and silently
        ZERO the EV of a stalled $100k competition — the same defect class as prose in rank1 (2026-07-26)."""
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(x) or "")
        return float(m.group(0)) if m else None
    b, t = num(best), num(target)
    raw_hr = (abs(t - b) / max(abs(b), 1e-9)) if (b is not None and t is not None) else 0.0
    # COMPRESSED headroom: a huge relative gap usually means "we are nowhere near", not "easy points".
    # sqrt-compression stops a 1.7 headroom from dominating a 0.35 one by 5x.
    headroom = math.sqrt(raw_hr) if raw_hr > 0 else 0.0
    h = hist[key]
    # evidence-weighted P(gain): our own record on THIS competition, shrunk toward the portfolio base rate
    k_shrink = 3.0
    p_gain = (h["w"] + BASE * k_shrink) / (h["n"] + k_shrink) if (h["n"] or True) else BASE
    cost = max(h["c"] / max(h["n"], 1), 600.0)
    # TRACTABILITY: do we even have the instruments to work this row? An unframed, ungapped competition is a
    # research project, not a scoring opportunity — discount it instead of letting novelty inflate it.
    cdir = None
    try:
        camp = os.path.join(os.path.dirname(reg), "campaigns")
        stem = re.split(r"[-_]", key)[0][:6].lower()
        for dd in os.listdir(camp):
            if stem and stem in dd.lower():
                cdir = os.path.join(camp, dd); break
    except Exception:
        pass
    tract = 1.0
    if cdir:
        if not os.path.exists(os.path.join(cdir, "FRAME.md")): tract *= 0.75
        if not os.path.exists(os.path.join(cdir, "GAP_REPORT.md")): tract *= 0.75
    else:
        tract *= 0.5                                        # no campaign dir at all = least ready
    st = stall.get(key, "")
    smul = {"HARD_PIVOT": 1.6, "REFUTE": 1.4}.get(st, 1.0)  # stalled work first — that is what REFUTE is FOR
    if st in ("AT_#1", "DONE"): smul = 0.0
    ev = headroom * p_gain * tract * smul / (cost / 3600.0)
    out.append((ev, key, best, target, headroom, p_gain, round(cost), h["n"], tract, st or "-"))
out.sort(reverse=True)
print(f"# EV ranking — √headroom × P(gain|evidence) × tractability × stall-priority / compute-hour")
print(f"#   portfolio base rate P(gain)={BASE:.3f} from {tot_w}/{tot_n} drives  (a fresh row inherits THIS, not 0.5)")
for ev, k, b, t, hr, p, c, n, tr, st in out:
    print(f"  {ev:8.3f}  {k:<26} best={b:<10} target={t:<10} √hr={hr:.2f} P={p:.2f} tract={tr:.2f} stall={st:<10} n={n}")
if out and out[0][0] <= 0:
    print("  (nothing allocatable — every row is at target, done, or has no measurable headroom)")
EOF
    ;;

  variants)
    # rank BRIEF_BANK variants by measured gain-per-compute (recorded as 'variant=<id>' in the note column)
    $PY - "$PLOG" <<'EOF'
import sys, re, collections
plog=sys.argv[1]
agg=collections.defaultdict(lambda:{"g":0.0,"c":0.0,"n":0,"w":0})
for line in open(plog):
    if line.startswith("#") or not line.strip(): continue
    f=line.rstrip("\n").split("\t")
    if len(f)<11 or f[3]!="diverge": continue
    m=re.search(r"variant=([A-Za-z0-9_-]+)", f[10] or "")
    if not m: continue
    a=agg[m.group(1)]
    try: g=float(f[7])
    except Exception: g=0.0
    try: c=float(f[8])
    except Exception: c=0.0
    a["g"]+=max(g,0.0); a["c"]+=c; a["n"]+=1; a["w"]+=(1 if g>0 else 0)
if not agg:
    print("default\t(no variant evidence yet)"); sys.exit()
out=[]
for v,a in agg.items():
    gpc=a["g"]/max(a["c"],1.0)*1000; wr=(a["w"]+1)/(a["n"]+2)
    out.append((gpc*wr, v, gpc, wr, a["n"]))
out.sort(reverse=True)
for s_,v,gpc,wr,n in out: print(f"{v}\tscore={s_:.4f} gain/1ks={gpc:.4f} win={wr:.2f} n={n}")
EOF
    ;;
  report)
    echo "== PROCESS scoreboard (how the system searches, not what it found) =="
    $PY - "$PLOG" <<'EOF'
import sys, collections
plog = sys.argv[1]
rows = [l.rstrip("\n").split("\t") for l in open(plog) if not l.startswith("#") and l.strip()]
div = [r for r in rows if len(r) >= 10 and r[3] == "diverge"]
ref = [r for r in rows if len(r) >= 10 and r[3] == "refute"]
print(f"  tournaments: {len(ref)} refute round(s) · {len(div)} lens-run(s)")
if div:
    tot_c = sum(float(r[8]) for r in div if r[8].replace('.','',1).replace('-','',1).isdigit())
    wins = sum(1 for r in div if r[7] not in ("-", "") and r[7].lstrip('-').replace('.','',1).isdigit() and float(r[7]) > 0)
    print(f"  lens win-rate: {wins}/{len(div)} · total lens compute: {tot_c/3600:.2f} h")
    by = collections.Counter(r[4] for r in div)
    print("  lens usage:", ", ".join(f"{k}×{v}" for k, v in by.most_common()))
conf = sum(1 for r in ref if r[9] == "confirmed")
print(f"  confirmed promotions: {conf}/{len(ref)} rounds" + ("  ← adversarial pass is doing its job" if len(ref) > conf else ""))
EOF
    ;;
  *) echo "usage: meta_learn.sh priors <task_type> | exhausted <task_type> [K] | allocate | report";;
esac
