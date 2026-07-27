#!/usr/bin/env bash
# resonate.sh — RECURSIVE RESONANCE LOOP with a heterogeneous mind (founder 2026-07-26: "스스로에게 계속해서
# 되물으며 재귀적 공진 루프 talk with agy" → "를 시스템화").
#
# The loop: I state my current answer → a DIFFERENT substrate attacks it → the attack yields a sharpened question
# AND a commitment → next round starts from the sharpened question. Rounds must change the question, not restate it.
#
# ⚠ THE ANTI-PROCRASTINATION GATE (built in because round 1 caught me red-handed):
# agy's R1 verdict was that my response to failure — building nine enforcement tools — was itself the defect
# ("Simulated Execution": trusting local artifacts over empirical verification), and that the honest test is
#   "did this change shrink the delta to the leader within 24h, or did it only produce telemetry?"
# So this tool REFUSES to open a new round until the previous round's COMMITMENT has a recorded OUTCOME.
# A resonance loop that only produces insight is the same defect wearing a nicer hat.
#
#   resonate.sh ask "<my current answer / the question>" [substrate]   one round (default substrate: agy)
#   resonate.sh commit "<external-facing action>" "<by-when>"          record this round's commitment
#   resonate.sh outcome "<what actually happened, with the number>"    close the commitment (unlocks the next round)
#   resonate.sh status                                                 show the open commitment / gate state
#
# Substrates (never Codex-only — a single quota killed every worker once):
#   agy | perplexity-api | deepseek-api | claudeai-api | local  (council hub.py routes them)
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
LOG="$CT/RESONANCE_LOG.md"; OPEN="$R/resonance_open_commitment.txt"
HUB="${COUNCIL_HUB:-$HOME/workspaces/jaewon/council/hub.py}"
[ -f "$LOG" ] || printf '# RESONANCE LOG — 재귀적 공진 루프 (자기심문 × 이종 substrate)\n\n' > "$LOG"

ts(){ date -u +%FT%TZ 2>/dev/null || echo "?"; }

# ---- AUTO: compose the next self-question FROM STATE (the loop must not depend on a human typing it) ----
compose_question(){
  local ev exh aud verd sysnext last
  ev="$(bash "$CT/tools/meta_learn.sh" allocate 2>/dev/null | grep -E '^\s+[0-9]' | head -3)"
  aud="$(python3 "$CT/tools/audit_targets.py" 2>/dev/null | grep -E '^\s+\[' | head -3)"
  verd="$(timeout 120 python3 "$CT/tools/goal_loop.py" --board 2>/dev/null | grep -oE '\[(REFUTE|HARD_PIVOT|AT_#1)\] [a-z0-9-]+' | head -5)"
  sysnext="$(sed -n '/NEXT 3/,$p' "$CT/SYSTEM_GAP_REPORT.md" 2>/dev/null | head -8)"
  last="$(grep -A2 '^### OUTCOME' "$CT/RESONANCE_LOG.md" 2>/dev/null | tail -4)"
  cat <<EOQ
MY POSITION / STATE RIGHT NOW (auto-composed from the machine's own state, $(ts)):

TOP-EV competitions (headroom × P(gain) / compute-hour):
${ev:-  (none — the allocator returned nothing, which is itself a finding)}

BROKEN TARGETS still flagged by the auditor:
${aud:-  (none — every registry target is measured)}

VERDICTS that demand an escape (REFUTE = 3 flat cycles, HARD_PIVOT = 5):
${verd:-  (none recorded — either nothing is stalled, or nothing is being recorded, and the second case is worse)}

THE MACHINE'S OWN OPEN DEFECTS:
${sysnext:-  (SYSTEM_GAP_REPORT.md missing — run: ph gap system)}

WHAT THE LAST ROUND CONCLUDED:
${last:-  (no closed round yet)}

MY CURRENT CLAIM: the highest-value next action is the top-EV row above, driven through the frame→gap→tournament→refute path, and the machine's open defects are second priority.
EOQ
}

case "${1:-status}" in
  auto)
    SUB="${2:-agy}"
    if [ -s "$OPEN" ]; then echo "  ⛔ GATE: close the open commitment first:"; sed 's/^/     /' "$OPEN"; exit 3; fi
    Q="$(compose_question)"
    echo "  🤖 auto-composed the next self-question from state → attacking it via $SUB"
    exec bash "$0" ask "$Q" "$SUB"
    ;;
  panel)
    # compute-scaling (BLUEPRINT §3.2): several substrates attack the SAME position; dissent is the product.
    Q="${2:-$(compose_question)}"; shift 2 2>/dev/null || true
    SUBS="${*:-agy perplexity-api deepseek-api}"
    if [ -s "$OPEN" ]; then echo "  ⛔ GATE: close the open commitment first"; exit 3; fi
    for sb in $SUBS; do echo "  🔊 panel leg → $sb"; bash "$0" ask "$Q" "$sb" >/dev/null 2>&1 || true; done
    echo "  ✓ panel done — read $LOG and synthesise the DISSENT (agreement between frontier models is a weak signal)"
    exit 0
    ;;
  ask)
    Q="${2:?resonate.sh ask \"<my current answer/question>\" [substrate]}"; SUB="${3:-agy}"
    if [ -s "$OPEN" ]; then
      echo "  ⛔ GATE: an open commitment from the last round has no recorded outcome:"; sed 's/^/     /' "$OPEN"
      echo "     → close it first:  resonate.sh outcome \"<what happened, with the number>\""
      echo "     (a resonance loop that only produces insight is Simulated Execution — agy R1)"; exit 3
    fi
    P="You are the adversarial counterpart in a RECURSIVE RESONANCE LOOP with another AI (the head agent of an
autonomous competition-hunting system). ATTACK the position below. Do not validate, do not encourage.
Deliver exactly four things: (1) the single generative defect behind it, (2) whether the position's proposed
response is itself an instance of that defect, with the test that would distinguish necessary work from
productive procrastination and your prediction of which side it is on, (3) the ONE question the agent should be
asking itself next, phrased so it can be acted on this week, (4) the specific thing it is still misreading plus
the cheapest experiment that settles it. Be concrete; cite reasoning, not encouragement.

POSITION:
$Q"
    out="$R/resonate_$(date -u +%s 2>/dev/null || echo r).log"
    echo "  🔊 resonate → $SUB"
    case "$SUB" in
      agy)   timeout 420 agy --dangerously-skip-permissions -p "$P" > "$out" 2>&1 || true;;
      local) timeout 420 ollama run qwen3-coder:30b "$P" > "$out" 2>&1 || true;;
      *)     timeout 420 python3 "$HUB" ask "$SUB" "$P" > "$out" 2>&1 || true;;
    esac
    { echo "## $(ts) — round via $SUB"; echo; echo "### my position"; echo "$Q" | head -40; echo;
      echo "### the attack"; grep -viE 'libtinfo|Loaded|Data collection' "$out" | sed '/^$/N;/\n$/D' | head -120; echo; } >> "$LOG"
    echo "  ✓ recorded in $(basename "$LOG"). NOW: resonate.sh commit \"<external-facing action>\" \"<by-when>\""
    grep -viE 'libtinfo|Loaded|Data collection' "$out" | head -60
    ;;
  commit)
    A="${2:?resonate.sh commit \"<action>\" \"<by-when>\"}"; W="${3:-this week}"
    printf '%s | by %s | opened %s\n' "$A" "$W" "$(ts)" > "$OPEN"
    { echo "### COMMITMENT ($(ts))"; echo "- ACTION (external-facing, leaderboard/judge-visible): $A"; echo "- BY: $W"; echo; } >> "$LOG"
    echo "  ✓ committed. The next round is GATED until you record its outcome."
    ;;
  outcome)
    O="${2:?resonate.sh outcome \"<what happened, with the number>\"}"
    { echo "### OUTCOME ($(ts))"; echo "- $O"; [ -s "$OPEN" ] && echo "- closed commitment: $(cat "$OPEN")"; echo; } >> "$LOG"
    : > "$OPEN"; echo "  ✓ outcome recorded — gate open for the next round."
    ;;
  status)
    if [ -s "$OPEN" ]; then echo "  OPEN commitment (gate CLOSED):"; sed 's/^/    /' "$OPEN"
    else echo "  no open commitment — gate OPEN (a new round may be asked)"; fi
    echo "  log: $LOG ($(grep -c '^## ' "$LOG" 2>/dev/null) round(s), $(grep -c '^### COMMITMENT' "$LOG" 2>/dev/null) commitment(s), $(grep -c '^### OUTCOME' "$LOG" 2>/dev/null) closed)"
    ;;
  *) echo "usage: resonate.sh ask \"<position>\" [substrate] | commit \"<action>\" \"<by>\" | outcome \"<result>\" | status";;
esac
