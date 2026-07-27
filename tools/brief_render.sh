#!/usr/bin/env bash
# brief_render.sh <key> <task_type> [variant] — assemble a drive brief from the MUTABLE prompt layer.
#
# founder 2026-07-26: "프롬프트는 claude가 계속 변형해서 넣어줄 수 있도록. 유기적이고 동적인 시스템."
# Briefs are no longer hardcoded in the drive tools. They are composed at drive time from:
#   BRIEF_BANK.md ## GLOBAL          — always-on discipline (no-launder both ways, anti-pessimism, harness rules)
#   BRIEF_BANK.md ## VARIANT:<id>    — the mutable framing the head agent keeps editing/adding/retiring
#   BRIEF_BANK.md ## COMP:<key>      — competition directives (gap_hunt appends its findings here)
#   learn.sh prime <task_type>       — proven levers + recorded dead-ends from OTHER competitions
#   <campaign>/GAP_REPORT.md         — measured structural gaps (train↔test, CV↔LB, public↔private, error budget)
#   <campaign>/FRAME.md PRIORS       — the tagged, falsifiable assumptions from the entry frame
# The chosen variant id is echoed to stderr as "VARIANT=<id>" so the caller can record it in PROCESS_LOG and
# meta_learn can rank variants by measured gain (prompt evolution, measured rather than assumed).
#
#   PH_VARIANT=<id>  pick a variant explicitly; default = meta_learn's best-paying variant, else 'default'
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$CT/.." && pwd)"
KEY="${1:?key}"; TT="${2:-}"; VAR="${3:-${PH_VARIANT:-}}"
BANK="${PH_BRIEF_BANK:-$CT/BRIEF_BANK.md}"
DIR="${PH_CAMP_DIR:-$(ls -d "$CT/campaigns/"*"${KEY%%-*}"* 2>/dev/null | head -1)}"

sect(){ awk -v want="$1" '
  /^## /{cur=substr($0,4); next}
  { if (cur==want) print }' "$BANK" 2>/dev/null; }

# variant choice: explicit > meta-learned best > default
if [ -z "$VAR" ]; then
  VAR="$(bash "$CT/tools/meta_learn.sh" variants 2>/dev/null | awk 'NR==1{print $1}')"
  [ -z "$VAR" ] && VAR="default"
fi
grep -q "^## VARIANT:$VAR" "$BANK" 2>/dev/null || VAR="default"
echo "VARIANT=$VAR" >&2

{
  sect "GLOBAL"
  echo
  echo "=== FRAMING FOR THIS ROUND (variant '$VAR') ==="
  sect "VARIANT:$VAR"
  cs="$(sect "COMP:$KEY")"
  if [ -n "$cs" ]; then echo; echo "=== DIRECTIVES FOR THIS COMPETITION ==="; printf '%s\n' "$cs"; fi
  if [ -n "$TT" ]; then
    pr="$(bash "$CT/tools/learn.sh" prime "$TT" 2>/dev/null)"
    [ -n "$pr" ] && { echo; echo "=== ALREADY LEARNED for task-type '$TT' (do not re-derive; do not repeat dead-ends) ==="; printf '%s\n' "$pr"; }
  fi
  if [ -n "$DIR" ] && [ -f "$DIR/GAP_REPORT.md" ]; then
    echo; echo "=== MEASURED STRUCTURAL GAPS (from gap_hunt — these are where the score actually leaks) ==="
    head -c 2500 "$DIR/GAP_REPORT.md"
  fi
  if [ -n "$DIR" ] && [ -f "$DIR/FRAME.md" ]; then
    p="$(awk '/^## PRIORS/{f=1;next} /^## /{f=0} f' "$DIR/FRAME.md" 2>/dev/null | head -c 1200)"
    [ -n "$p" ] && { echo; echo "=== TAGGED PRIORS from the entry frame (any of these may be wrong) ==="; printf '%s\n' "$p"; }
  fi
  # RENDERED GEOMETRY — the picture's numbers (ph view). A drive that never sees these keeps tuning a
  # model against a distribution it has not looked at (Geometry Blindness, THE_PATH_TO_NUMBER_ONE.md).
  if [ -n "$DIR" ] && [ -f "$DIR/VIEW/FINDINGS.md" ]; then
    echo; echo "=== RENDERED train↔test GEOMETRY (ph view — entity counts, KS/PSI drift, schema mismatch) ==="
    head -c 2600 "$DIR/VIEW/FINDINGS.md"
  fi
  # FOUNDER STEER goes LAST and outranks everything above it. Human intuition is the scarce input
  # (5% of the work, most of the direction) — it must not be buried in the middle of a long brief.
  st="$( { sect "STEER:GLOBAL"; sect "STEER:$KEY"; } | grep '^- \[' || true )"
  if [ -n "$st" ]; then
    echo; echo "=== FOUNDER STEER — HIGHEST AUTHORITY (overrides every framing above; newest first) ==="
    printf '%s\n' "$st"
    echo "(이 지시는 힌트가 아니라 지시다. 따르라. 기술적으로 불가능하면 무시하지 말고 '왜 불가능한지'를 산출물에 한 줄로 적어라.)"
  fi
} 2>/dev/null
