#!/usr/bin/env bash
# learn.sh — COMPOUNDING INTELLIGENCE (복리지능). founder 2026-07-23: "실서비스 배포 · General · 도메인/팀별로
# 점점 더 똑똑해지고 쉽게 #1을 달성하는 시스템."
#
# The system must get SMARTER each competition, not just run them. Mechanism: every validated lever (what moved
# the score, by how much, with what CV↔LB calibration) is captured into a TASK-TYPE-INDEXED library. A NEW
# competition of a similar task-type is PRIMED with the proven levers — so it starts higher and reaches #1 easier.
# General by construction: indexed by task_type (tabular-regression, time-series-changepoint, well-log-inversion,
# nlp-classification, …), not by a specific competition — so it transfers across users and domains.
#
#   learn.sh capture <task_type> <comp> <before> <after> <dir min|max> "<lever>" "<calib_note>"
#   learn.sh prime   <task_type>                 # print proven levers for that task-type (best delta first)
#   learn.sh list                                # whole library
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
# PH_LIB: per-tenant lever library (tenants keep their edge private; a commons can be opted into later)
LIB="${PH_LIB:-$CT/LEVER_LIBRARY.tsv}"
touch "$LIB"
[ -s "$LIB" ] || printf '# task_type\tcomp\tbefore\tafter\tdelta\tdir\tlever\tcalib\tdate\n' > "$LIB"

case "${1:-list}" in
  capture)
    tt="${2:?task_type}"; comp="${3:?comp}"; before="${4:?before}"; after="${5:?after}"; dir="${6:?dir}"; lever="${7:?lever}"; calib="${8:-}"
    delta="$(python3 -c "print(round(float('$after')-float('$before'),5))" 2>/dev/null || echo '?')"
    day="$(date -u +%F 2>/dev/null || echo NA)"   # NOTE: date may be unavailable in some sandboxes; pass a date arg upstream if so
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$tt" "$comp" "$before" "$after" "$delta" "$dir" "$lever" "$calib" "$day" >> "$LIB"
    echo "  ✓ captured [$tt] $comp: $before→$after (Δ$delta) — $lever"
    ;;
  prime)
    tt="${2:?task_type}"
    echo "== PRIMING for task_type='$tt' — proven levers (start here, don't re-derive) =="
    awk -F'\t' -v tt="$tt" 'NR>1 && $1==tt {print}' "$LIB" | \
      sort -t$'\t' -k5 -g $([ "$(awk -F'\t' -v tt="$tt" 'NR>1&&$1==tt{print $6;exit}' "$LIB")" = min ] && echo "" || echo "-r") | \
      awk -F'\t' '{printf "  • %s  (%s: %s→%s, Δ%s)  [%s]\n", $7, $2, $3, $4, $5, $8}' | head -12
    n="$(awk -F'\t' -v tt="$tt" 'NR>1 && $1==tt' "$LIB" | wc -l)"
    [ "$n" -eq 0 ] && echo "  (no levers yet for '$tt' — this competition will seed the library)"
    ;;
  list) column -t -s$'\t' "$LIB" 2>/dev/null | grep -viE libtinfo || cat "$LIB";;
  *) echo "usage: learn.sh capture <task_type> <comp> <before> <after> <min|max> \"<lever>\" \"<calib>\" | prime <task_type> | list";;
esac
