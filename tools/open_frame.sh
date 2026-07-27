#!/usr/bin/env bash
# open_frame.sh — the ENFORCED OPENING FRAME. Entry state decides everything downstream.
#
# founder 2026-07-26: "처음 진입할 때 만들어지는 환경·init·생각들이 이후 진행에 굉장히 큰 지분을 계속 끼친다.
# 첫 시작이 가장 중요하고, 많이 열려있는 마인드로 접근해야." + "헤드 agent가 보수적 해석하지 않게 만들어."
#
# This session proved it: every expensive failure was an ENTRY-FRAME artifact that then got inherited by every
# later cycle — rogii entered with status=ceiling and a self-referential rank1 (its own score) so the loop closed
# itself; ADIA entered with an EMPTY rank1 so every drive aimed at nothing; ARC entered with my unexamined
# "near-impossible" prior so a $700-850k competition was unwired; and my drive briefs entered with a PRESCRIBED
# lever list that capped the agent at my imagination.
#
# playbook/COMPETITION_ONBOARDING.md already specifies the 8-stage opening (TRIAGE→RECON→host-digging→research→
# strategy→adversarial→organise→fallbacks). What was missing was ENFORCEMENT: nothing checked that a competition
# actually opened that way, and nothing stopped a NARROWED or PESSIMISTIC frame from being inherited forever.
#
#   open_frame.sh check <key>            machine-check the frame (exit 0 = drivable, 1 = must (re)frame)
#   open_frame.sh make  <key> <dir>      run the OPENING agent -> <dir>/FRAME.md (widen, never narrow)
#
# HARD RULES the frame must satisfy (checked, not trusted):
#   1. VERIFIED TARGET   — the real #1/frontier with HOW it was measured (a target we invented is worse than none)
#   2. HARNESS TRUST     — whether local validation is known to track the leaderboard, with the anchor evidence
#   3. >=3 FRAMINGS      — three genuinely different formulations enumerated BEFORE committing to any
#   4. TAGGED PRIORS     — every assumption written as "PRIOR: <claim> | FALSIFY: <cheap test>"
#   5. NO VERDICTS       — the words ceiling/impossible/hopeless/무리/불가능 are FORBIDDEN in an entry frame
#   6. FRESH             — frames go stale (default 14 days); a stale frame must be reopened
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
MAXAGE="${PH_FRAME_MAXAGE_DAYS:-14}"
AGENT="${PH_AGENT_CMD:-codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}}"

frame_path(){ echo "$1/FRAME.md"; }

check(){ # check <key> <dir>
  local key="$1" dir="$2" f; f="$(frame_path "$dir")"
  [ -f "$f" ] || { echo "  ✗ $key: no FRAME.md — entry frame missing (drives would inherit an unexamined frame)"; return 1; }
  local age; age="$(python3 -c "
import os,time,sys
try: print(int((time.time()-os.path.getmtime('$f'))/86400))
except Exception: print(999)" 2>/dev/null)"
  local bad=0
  [ "${age:-999}" -gt "$MAXAGE" ] 2>/dev/null && { echo "  ✗ $key: FRAME.md is ${age}d old (> ${MAXAGE}d) — reopen it"; bad=1; }
  grep -qiE '^\s*#{0,3}\s*[-*]?\s*(VERIFIED TARGET|검증된 목표)' "$f"   # BUGFIX: the prompt mandates "## VERIFIED TARGET"; the old regex forbade the '#' and deadlocked every row || { echo "  ✗ $key: frame has no VERIFIED TARGET section"; bad=1; }
  grep -qiE 'HARNESS TRUST|검증 신뢰' "$f" || { echo "  ✗ $key: frame does not state harness trust"; bad=1; }
  local nf; nf="$(grep -ciE '^\s*#{0,4}\s*FRAMING\s*[0-9]' "$f" 2>/dev/null || echo 0)"
  [ "$nf" -lt 3 ] 2>/dev/null && { echo "  ✗ $key: only $nf framing(s) — need >=3 before committing"; bad=1; }
  grep -q 'PRIOR:' "$f" || { echo "  ✗ $key: no tagged PRIOR: ... | FALSIFY: ... assumptions"; bad=1; }
  if grep -qiE '\b(ceiling|impossible|hopeless|near-impossible|불가능|무리|천장)\b' "$f"; then
    echo "  ✗ $key: frame contains a VERDICT word — an entry frame may not close doors (anti-conservative rule)"; bad=1; fi
  [ "$bad" = 0 ] && echo "  ✓ $key: frame OK (${age}d old, $nf framings)"
  return "$bad"
}

make_frame(){ # make_frame <key> <dir>
  local key="$1" dir="$2" rel="${2#$ROOT/}" lg="$R/frame_${1}.log"
  mkdir -p "$dir"
  local tgt; tgt="$(awk -F'\t' -v k="$key" '$1==k{print "registry: best="$6" rank1="$7" metric="$4" dir="$5; exit}' "$CT/portfolio_registry.tsv" 2>/dev/null)"
  local P="You are OPENING the frame for the competition '$key' (dir: $rel). $tgt

This is the ENTRY FRAME. Everything downstream inherits it, so your job is to make it WIDE and FACTUAL — not to
decide anything. Follow playbook/COMPETITION_ONBOARDING.md stages 2-4 (RECON/사실확정 · 주최측 DIGGING · 다방면
자료조사). Write $rel/FRAME.md with EXACTLY these sections:

## VERIFIED TARGET
The real #1 / frontier score AND how you measured it (leaderboard fetch, writeup, forum post — cite the source and
the date). If you could not measure it, say so and list the exact next fetch path to try (CLI → platform API →
browser read → browser in-page fetch → MCP). Never invent a target: an invented target is worse than none, and a
target equal to our own score silently closes the loop.

## HARNESS TRUST
Is our local validation known to track this leaderboard? Cite the anchor evidence (a point where local and LB
scores were compared). If unknown, say UNKNOWN and state the cheapest experiment that would establish it. A
tournament run on an untrusted harness optimises noise.

## FACTS (with sources)
Rules, deadline, submission mechanics + limits, allowed external data/models, evaluation split (public/private
sizes, grouping, temporal order), and anything that constrains approaches. Every line needs a source. Mark
unverified items explicitly as 확인필요.

## HOST & JUDGE DIG
Who runs and judges this, what they fund/brag about, what past winners looked like. What stops this judge/metric.

## FRAMING 1 / FRAMING 2 / FRAMING 3 (at least three, genuinely different)
Three fundamentally different formulations of this task — different unit of prediction, different information
flow, different model class, different objective, or a different reading of what the metric rewards. For each:
the core idea, why it could beat the public approach, its cheapest decisive test, and its main risk. Do NOT rank
them and do NOT pick one — the point of the frame is to keep options open for the tournament that follows.

## PRIORS (tagged, falsifiable)
Every assumption you or the record is carrying, in the form:
  PRIOR: <claim> | FALSIFY: <cheap concrete test that would kill it>
Include the uncomfortable ones (e.g. 'PRIOR: the public solution's validation is correct | FALSIFY: ...').

## OPENINGS
Where the public/best-known approach is implicitly WRONG or incomplete, and what is NOT public yet. This is the
only place a #1 can come from — following a public solution caps us mid-pack.

## FALLBACKS
If the main data/approach/tool/schedule fails, what replaces it (playbook stage 7).

FORBIDDEN in this document: the words ceiling / impossible / hopeless / 불가능 / 무리 / 천장, and any verdict that
a direction is not worth trying. Difficulty is not evidence; if something looks hard, write the cheap PROBE that
would settle it. no-launder in BOTH directions: do not dress a loss as a win, and do not dress a reachable thing
as unreachable."
  echo "  🔓 open_frame [$key]: opening (wide) …"
  cd "$ROOT" || return 1
  printf '%s' "$P" > "$R/.prompt_frame_$key"; bash "$CT/tools/agent_run.sh" "$lg" "$R/.prompt_frame_$key"
  check "$key" "$dir"
}

key="${2:-}"; dir="${3:-}"
[ -z "$dir" ] && [ -n "$key" ] && dir="$(ls -d "$CT/campaigns/"*"${key%%-*}"* 2>/dev/null | head -1)"
case "${1:-check}" in
  check) [ -z "$key" ] && { echo "usage: open_frame.sh check <key> [dir]"; exit 2; }; check "$key" "$dir";;
  make)  [ -z "$dir" ] && { echo "usage: open_frame.sh make <key> <dir>"; exit 2; }; make_frame "$key" "$dir";;
  *) echo "usage: open_frame.sh check|make <key> [campaign_dir]";;
esac
