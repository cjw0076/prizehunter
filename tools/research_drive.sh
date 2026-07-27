#!/usr/bin/env bash
# research_drive.sh — DIVERGENT RESEARCH TOURNAMENT for a leaderboard competition.
#
# founder 2026-07-25: "leaderboard형/해외 대회는 단순한 방법으로 안 된다. 토큰만 낭비. agent는 능력이 있는데
# 그 능력을 100% 못 쓰는 지능적 제약이 있다. 재귀적 개선루프·아이디어 발산·시스템적 진화가 있는가?"
#
# DIAGNOSED CONSTRAINTS this replaces (evidence in INTELLIGENCE_CONSTRAINT.md):
#   1. our only real gain came from COPYING a public solution -> following caps us mid-pack, never #1
#   2. drives explored variants INSIDE an exhausted paradigm (ADIA two-sample: 2 drives, 0 gain)
#   3. the brief PRESCRIBED the levers -> the agent's ceiling was the brief author's imagination
#   4. one agent, one framing, no divergence, no tournament, no adversarial refutation
#   5. only domain knowledge compounded; the PROCESS never improved
#
# The fix — 4 phases, each a real agent job (the agent RESEARCHES, it is not handed a lever list):
#   SCOUT   : outside-view first. What is the field's frontier, what do winners do, where is the GAP,
#             and crucially WHAT IS NOT PUBLIC yet (the only place #1 can come from).
#   DIVERGE : N agents, each assigned a distinct RESEARCH LENS (a way of re-seeing the problem, NOT a
#             prescribed lever). Each invents + validates its own hypothesis on the competition harness.
#   REFUTE  : an adversarial skeptic tries to KILL each claimed gain (leakage, non-nested selection, grid
#             artifact, fold luck). Only survivors count. (ADIA's own 0.581 artifact proves this is needed.)
#   PROMOTE : best survivor -> .runs/drive_<key>.score (autopush harvests) + a PROCESS_LOG row per lens so
#             meta_learn.sh can learn WHICH LENSES PAY per task-type = recursive process improvement.
#
# usage: research_drive.sh <key> <campaign_dir> <task_type> [n_lenses] [--phase scout|diverge|refute|all]
#        PH_AGENT_CMD='<cli with {PROMPT}>'  (default codex; any vendor works)
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
KEY="${1:?key}"; DIR="${2:?campaign_dir}"; TT="${3:?task_type}"; NL="${4:-4}"
PHASE="${PH_PHASE:-all}"
PLOG="${PH_PLOG:-$CT/PROCESS_LOG.tsv}"; LIB="${PH_LIB:-$CT/LEVER_LIBRARY.tsv}"
AGENT="${PH_AGENT_CMD:-codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}}"
# TARGET LOOKUP — the REGISTRY is the single source of truth (direction/best/rank1); the legacy board is only
# a fallback. This kills the fragmentation where a drive could not find its own numbers and died instantly.
lookup_target(){ python3 - "$1" "$CT/portfolio_registry.tsv" "${PH_BOARD:-$R/autopush_board.tsv}" <<'PYEOF'
import sys
key, reg, board = sys.argv[1], sys.argv[2], sys.argv[3]
cols=[]
try:
    for l in open(reg):
        if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1: cols.append(l.split()[1])
        elif not l.startswith("#"): break
    for l in open(reg):
        if l.startswith(key+"\t"):
            f=l.rstrip("\n").split("\t"); g=lambda n: f[cols.index(n)] if n in cols and cols.index(n)<len(f) else ""
            print("\t".join([g("direction") or "max", g("best") or "-", g("rank1") or "-"])); sys.exit()
except Exception: pass
try:
    for l in open(board):
        if l.startswith(key+"\t"):
            f=l.rstrip("\n").split("\t")
            print("\t".join([f[2] if len(f)>2 else "max", f[3] if len(f)>3 else "-", f[4] if len(f)>4 else "-"])); sys.exit()
except Exception: pass
print("max\t-\t-")
PYEOF
}
tgt="$(lookup_target "$KEY")"
dir_="$(printf '%s' "$tgt" | cut -f1)"; best="$(printf '%s' "$tgt" | cut -f2)"; target="$(printf '%s' "$tgt" | cut -f3)"
better="lower"; [ "$dir_" = "max" ] && better="higher"
REL="${DIR#$ROOT/}"
[ -s "$PLOG" ] || printf '# ts\tkey\ttask_type\tphase\tlens\tbefore\tafter\tgain\tcost_s\tverdict\tnote\n' > "$PLOG"

run_agent(){ # run_agent <logfile> <prompt> — via the substrate CHAIN, never a single vendor
  local lg="$1"; shift; local pr="$1"; local pf="$R/.prompt_$(basename "$lg" .log)"
  printf '%s' "$pr" > "$pf"; bash "$CT/tools/agent_run.sh" "$lg" "$pf"
}
plog(){ printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(date -u +%FT%TZ 2>/dev/null)" "$KEY" "$TT" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >> "$PLOG"; }

# ---- RESEARCH LENSES: ways of RE-SEEING the problem (task-agnostic). The agent invents the lever itself. ----
# Ordered by meta-learned prior when available (meta_learn.sh priors <task_type>), else this default order.
LENS_NAMES=(
 "problem-reformulation"
 "validation-structure-exploitation"
 "data-generating-process"
 "representation-expansion"
 "ensemble-decorrelation"
 "metric-exploitation"
 "legal-side-information"
 "external-transfer"
 "constraint-projection-postprocessing"
 "paradigm-shift"
 # ↓ promoted from IDEATION_BRAINDUMP.md — killer ideas become LIVE lenses instead of a dead document
 "metric-hacker"
 "cross-domain-pollination"
 "community-intel-sniper"
 "synthetic-hard-examples"
 "compute-brute-force"
 "runtime-squeeze"
)
lens_brief(){ case "$1" in
 problem-reformulation) echo "Re-parameterise WHAT is predicted (target transform, relative/differenced/hierarchical target, per-group normalisation, decomposition into easier sub-predictions, changing the loss to match the metric's geometry). Ask: is the quantity we regress the RIGHT quantity?";;
 validation-structure-exploitation) echo "Exploit how the LEADERBOARD/scoring is actually computed (public vs private split, grouping, temporal order, per-row weighting, checkpoint/row density, resampling). Build a local harness that provably matches it, then optimise what the score actually rewards. Also look for scoring-structure leverage others ignore.";;
 data-generating-process) echo "Model the PROCESS that generated the data (physics, simulation, mechanism, agent behaviour), not just the correlations. A generative/forward model + inversion, or a simulator-augmented prior, can beat any amount of feature engineering.";;
 representation-expansion) echo "Change the INPUT SPACE: new signal sources in the provided data, multi-scale/spectral/topological transforms, cross-entity relational features, learned embeddings, sequence context that current features throw away.";;
 ensemble-decorrelation) echo "Attack VARIANCE and correlation structure: deliberately mis-specified/stiffer variants, diverse seeds/objectives/horizons, stacking topology, disagreement features, out-of-fold blending geometry. Cheap and reliably underexploited.";;
 metric-exploitation) echo "Optimise the METRIC, not the fit: calibration, thresholding, risk-asymmetry, tail behaviour, per-segment optimisation, prediction shrinkage toward the base rate where the metric punishes confidence.";;
 legal-side-information) echo "Find signal that is ALLOWED but unused: look-ahead legal under the task's causality rules, cross-entity/global structure, metadata, ordering artefacts, auxiliary columns, public reference data permitted by the rules. State the rule that makes it legal.";;
 external-transfer) echo "Bring in outside capability where rules permit: pretrained models, external datasets, published domain constants/structures, transfer from a related task. Verify licence/rule compliance explicitly.";;
 constraint-projection-postprocessing) echo "Impose domain truth AFTER the model: physical/monotonic/continuity constraints, smoothing with the right kernel, projection onto feasible sets, isotonic/quantile mapping, per-entity drift correction.";;
 metric-hacker) echo "IGNORE the data at first and attack the METRIC ITSELF (IDEATION_BRAINDUMP #2): read the scoring code, compute what a constant/degenerate prediction scores, find non-linearity, per-class weighting, tail sensitivity, threshold effects. Prove mathematically where post-processing alone (distribution shift, threshold, shrinkage, calibration) buys rank without touching the model.";;
 cross-domain-pollination) echo "FORCE a method from a DIFFERENT field onto this task (IDEATION_BRAINDUMP #3): treat the data as if it came from another domain (finance quant on a bio series, NLP transformer on structure, control theory on a forecast) and import that field's SOTA. Competitors in this domain will not have tried it. Name the source field and the exact transplanted method.";;
 community-intel-sniper) echo "HARVEST the community's collective intelligence (IDEATION_BRAINDUMP #1): mine the competition's discussions/forums/notebooks/GitHub for what others report working, suspected leaks, and unspoken tricks; verify each claim on OUR harness before adopting. Free baseline uplift — but treat every claim as a hypothesis, not a fact.";;
 synthetic-hard-examples) echo "MANUFACTURE data where we are weak (IDEATION_BRAINDUMP #4): identify the hard/edge regions from the error budget, then synthesise/augment examples matching the train distribution but concentrated in those regions (physics simulation, generative model, targeted augmentation). Prove the gain on held-out real data, not on synthetic.";;
 compute-brute-force) echo "WIN BY VOLUME where the search space allows (IDEATION_BRAINDUMP #5): train many diverse models (seeds/features/objectives/horizons) and EVOLVE the ensemble weights (genetic/CMA-ES) against the honest harness rather than picking one best model. State the compute budget and the variance-reduction achieved.";;
 runtime-squeeze) echo "BUY MODEL CAPACITY WITH SPEED (IDEATION_BRAINDUMP #6): for a runtime/memory-limited code competition, profile the bottleneck and rewrite it (vectorisation, Numba/Cython, better algorithm) so a heavier ensemble fits inside the limit. Report the before/after wall-clock and what extra capacity it bought.";;
 paradigm-shift) echo "ASSUME THE CURRENT FRAMING IS EXHAUSTED. Enumerate 3 fundamentally different formulations of this task (different model class, different information flow, different objective, different unit of prediction), pick the one with the best evidence-to-cost ratio, and prototype it. Do NOT produce a variant of the incumbent.";;
esac }

mkdir -p "$R"
SCOUT_MD="$DIR/FIELD_SCOUT.md"
CTX="$(head -c 2500 "$DIR/WORKLOG.md" 2>/dev/null || head -c 2500 "$DIR/RECON.md" 2>/dev/null)"
PRIME="$(bash "$CT/tools/learn.sh" prime "$TT" 2>/dev/null | sed 's/^/    /')"
BRIEF="$(PH_CAMP_DIR="$DIR" bash "$CT/tools/brief_render.sh" "$KEY" "$TT" 2>"$R/.var_$KEY")"
VARIANT="$(grep -oE 'VARIANT=[A-Za-z0-9_-]+' "$R/.var_$KEY" 2>/dev/null | head -1 | cut -d= -f2)"; VARIANT="${VARIANT:-default}"

# ---------------- PHASE 1: SCOUT (outside view) ----------------
if [ "$PHASE" = "all" ] || [ "$PHASE" = "scout" ]; then
  t0=$SECONDS
  echo "  🔭 SCOUT: outside-view for $KEY"
  P="You are the SCOUT for the competition '$KEY' (dir: $REL). Metric: $better is better. Our validated best: $best. Target: $target.
Do NOT model anything yet. Your ONE job: establish the OUTSIDE VIEW, because our biggest past gain came from adopting a public solution and that only ever gets us mid-pack.
1) Read the competition's own record: $REL/WORKLOG.md, RECON.md.
2) Find the FIELD FRONTIER using every tool you have (web search, the competition's public notebooks/discussion/writeups, the leaderboard distribution, published papers on this task type). What score do the top teams have? What techniques are PUBLIC (so table-stakes, we must at least match) and what did prize winners describe doing BEYOND the public baseline?
3) Characterise the GAP: what specifically separates the top of the LB from the best public solution? Is it variance reduction, a different signal source, a different problem formulation, engineering scale, or exploiting the scoring structure?
4) THE HIGHEST-LEVERAGE QUESTION (grounded: winner writeups say the gap is framing/validation/search, not model choice): **where is the best PUBLIC solution implicitly WRONG or incomplete?** Inspect its assumptions — its validation scheme vs how the private LB is actually computed, its failure cases, its treatment of temporal/group dependence, whether it optimises what the metric truly rewards (ranking vs calibration vs tails vs robustness). A public baseline's hidden error is the cheapest original edge there is.
5) Then: **what is NOT public yet** — where could an original contribution come from? List 3-6 concrete unexplored directions with the evidence that makes each plausible.
6) Note any RULE-relevant facts (allowed external data, runtime limits, submission mechanics) that constrain or enable approaches.
7) VALIDATION TRUST: state explicitly whether our local harness is known to track the leaderboard (cite the evidence in WORKLOG, e.g. an anchor whose local and LB scores match). If it is NOT established, say so — a tournament run on an untrustworthy harness optimises noise, and fixing the harness becomes the round's real work.
Write all of it to $REL/FIELD_SCOUT.md (markdown, cite URLs/sources for every claim; say plainly where you could not verify). no-launder: do not invent leaderboard numbers or writeup contents.
Then print a 10-line summary."
  run_agent "$R/research_${KEY}_scout.log" "$P"
  plog scout "-" "$best" "-" "-" "$((SECONDS-t0))" "done" "FIELD_SCOUT.md"
  echo "  🔭 SCOUT done ($((SECONDS-t0))s) → $SCOUT_MD"
fi

SCOUT="$(head -c 3500 "$SCOUT_MD" 2>/dev/null)"
[ -z "$SCOUT" ] && SCOUT="(no scout report — proceed but state that the outside view is missing)"

# ---------------- PHASE 2: DIVERGE (N lenses in parallel) ----------------
if [ "$PHASE" = "all" ] || [ "$PHASE" = "diverge" ]; then
  # meta-learned lens order (recursive process improvement); fall back to default order
  mapfile -t ORDER < <(bash "$CT/tools/meta_learn.sh" priors "$TT" 2>/dev/null | grep -oE '^[a-z-]+' | head -"$NL")
  [ "${#ORDER[@]}" -lt 1 ] && ORDER=("${LENS_NAMES[@]:0:$NL}")
  # PARADIGM-EXHAUSTION OVERRIDE: if the last rounds on this task-type produced nothing confirmed, polishing
  # the incumbent framing is exactly the token-waste this engine exists to stop — force the paradigm-shift lens.
  if [ "${PH_FORCE_PARADIGM:-0}" = "1" ] || bash "$CT/tools/meta_learn.sh" exhausted "$TT" 2 2>/dev/null | grep -q '^EXHAUSTED'; then
    if ! printf '%s\n' "${ORDER[@]}" | grep -qx "paradigm-shift"; then
      ORDER=("paradigm-shift" "${ORDER[@]:0:$((NL-1))}")
    fi
    echo "  ⚠ task-type '$TT' EXHAUSTED → paradigm-shift lens forced into the tournament"
  fi
  echo "  🌱 DIVERGE: ${#ORDER[@]} lenses → ${ORDER[*]}"
  pids=()
  for ln in "${ORDER[@]}"; do
    lb="$(lens_brief "$ln")"; [ -z "$lb" ] && continue
    lg="$R/research_${KEY}_${ln}.log"; sf="$R/research_${KEY}_${ln}.score"; rm -f "$sf"
    P="You are ONE competing researcher in a divergent tournament on the competition '$KEY' (dir: $REL). Metric: $better is better. Incumbent validated best: $best. Target: $target.

YOUR ASSIGNED RESEARCH LENS: **$ln**
$lb

RULES OF THE TOURNAMENT:
- You must INVENT the hypothesis yourself within your lens. Nobody is handing you a lever list — the point of this tournament is to exceed what the orchestrator could think of. Other researchers are working other lenses in parallel; do NOT drift into theirs.
- Validate on the competition's OWN harness (same rows/folds/metric as its WORKLOG describes). Never invent a new comparator to look good.
- Report per-fold numbers and the honest pooled score, even if worse than $best. An honest negative is a real result and gets recorded as a dead-end for this lens.
- Beware artefacts: non-nested selection, leakage via target-derived features, grid/row-density sensitivity, single-fold luck. Assume a skeptic will try to refute your gain next.
- Do NOT submit externally.

$BRIEF

=== OUTSIDE VIEW (scout report head) ===
$SCOUT

=== WHAT THIS SYSTEM ALREADY LEARNED for task-type '$TT' (do not re-derive, do not repeat dead-ends) ===
$PRIME

=== THIS COMPETITION'S OWN RECORD (head) ===
$CTX

DELIVERABLES: (a) your hypothesis in 3 sentences and WHY the lens makes it plausible, (b) the implementation, (c) honest per-fold + pooled score, (d) an explicit statement of what would falsify your gain. FINALLY write ONLY the bare pooled score number to '$sf'."
    ( t0=$SECONDS; run_agent "$lg" "$P"
      sc="$(tr -dc '0-9.\-' < "$sf" 2>/dev/null | head -c 20)"
      gain="-"; [ -n "$sc" ] && gain="$(python3 -c "
b,a,d='$best','$sc','$dir_'
try: print(round((float(b)-float(a)) if d=='min' else (float(a)-float(b)),5))
except Exception: print('-')" 2>/dev/null)"
      plog diverge "$ln" "$best" "${sc:--}" "$gain" "$((SECONDS-t0))" "reported" "variant=$VARIANT $(basename "$lg")" ) &
    pids+=($!)
    sleep 2
  done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  echo "  🌱 DIVERGE done"
fi

# ---------------- PHASE 3: REFUTE (adversarial) + PROMOTE ----------------
if [ "$PHASE" = "all" ] || [ "$PHASE" = "refute" ]; then
  # collect claimed gains
  claims=""
  for f in "$R/research_${KEY}"_*.score; do
    [ -e "$f" ] || continue
    ln="$(basename "$f" .score)"; ln="${ln#research_${KEY}_}"
    sc="$(tr -dc '0-9.\-' < "$f" | head -c 20)"; [ -z "$sc" ] && continue
    if python3 -c "
import sys;b,a,d='$best','$sc','$dir_'
sys.exit(0 if ((float(a)<float(b)) if d=='min' else (float(a)>float(b))) else 1)" 2>/dev/null; then
      claims="$claims\n  - lens '$ln' claims $sc (incumbent $best); its log: .runs/research_${KEY}_${ln}.log"
    fi
  done
  if [ -z "$claims" ]; then
    echo "  ⚖ REFUTE: no lens beat $best — honest negative round (recorded per-lens in PROCESS_LOG)"
    plog refute "-" "$best" "$best" "0" "0" "no-claim" "no lens beat incumbent"
  else
    t0=$SECONDS
    echo -e "  ⚖ REFUTE: adversarially verifying claims:$claims"
    P="You are the ADVERSARIAL VERIFIER for competition '$KEY' (dir: $REL). Researchers claim these improvements over the incumbent $best (metric: $better is better):$claims

Your job is to REFUTE, not to be nice. Default to rejection when uncertain. For each claim:
1) Re-derive the score yourself on the competition's authoritative harness (same rows/folds/metric). Does it reproduce EXACTLY?
2) Hunt the standard killers: leakage (target-derived features, cross-fold contamination), non-nested hyperparameter/epoch selection, grid or row-density sensitivity, single-fold luck (check per-fold, flag any fold regressing badly), comparator drift (did they change the harness?), and train/test distribution assumptions that will not hold on the hidden test set.
3) Verdict per claim: CONFIRMED (reproduces + survives the checks) or REFUTED (state the exact defect).
4) Among CONFIRMED claims, say which single one is the best promotion candidate and whether combining any two is safe (check they are not the same signal twice).
Then: if there is a CONFIRMED winner, make it the promoted candidate — update the campaign's submission artifact and write ONLY its bare score to '$R/drive_$KEY.score' (the autopush harvester reads that). If everything is refuted, write nothing to that file and say so plainly.
Finally append a short verdict table to $REL/RESEARCH_ROUND.md. no-launder: refuting our own gain is a success, not a failure."
    # the adversarial verifier decides whether a gain is real; a hallucination-prone local model must not hold
    # that authority (see judge120's note). Restrict to judge-qualified substrates.
    PH_AGENT_CHAIN="${PH_JUDGE_CHAIN:-codex,agy,claude}" run_agent "$R/research_${KEY}_refute.log" "$P"
    prom="$(tr -dc '0-9.\-' < "$R/drive_$KEY.score" 2>/dev/null | head -c 20)"
    # SCALE DECLARATION (doctor: SCALE MIXING). A drive can only ever produce a LOCAL score — it has no
    # leaderboard access. Writing the sidecar makes that explicit so the harvester cannot record a local
    # number as leaderboard progress. Proof it matters: a live drive wrote 0.9536709504 for playground-s6e7,
    # which is ABOVE that row's rank1 0.95306 — undeclared, that reads as "we are #1".
    [ -n "$prom" ] && printf 'local\n' > "$R/drive_$KEY.scale"
    plog refute "-" "$best" "${prom:--}" "-" "$((SECONDS-t0))" "$([ -n "$prom" ] && echo confirmed || echo all-refuted)" "adversarial pass"
    echo "  ⚖ REFUTE done ($((SECONDS-t0))s) promoted=${prom:-none}"
  fi
fi
echo "== research_drive '$KEY' complete — PROCESS_LOG rows appended (meta_learn.sh reads them) =="
