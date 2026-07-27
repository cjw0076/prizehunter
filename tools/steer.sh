#!/usr/bin/env bash
# steer.sh — the founder's 5% steering, injected into the drive brief in one line.
#
# playbook/THE_PATH_TO_NUMBER_ONE.md concludes the winning shape is the CENTAUR: the agent does 95% of the
# grunt work, a human contributes the 5% that is intuition — "look at the images", "the metric rewards the
# tail, chase that", "stop tuning, the split is wrong". Until now that 5% could only enter the system by ME
# hand-editing BRIEF_BANK.md, which means it entered late, partially, or never. This makes it one command.
#
#   ph steer "<한 줄>"                 → applies to EVERY drive (## STEER:GLOBAL)
#   ph steer <key> "<한 줄>"           → applies to that competition only (## STEER:<key>)
#   ph steer list                      → active steers, newest first, with age
#   ph steer clear <key|GLOBAL>        → retire that scope's steers (kept in the file, struck through)
#
# Semantics the drive sees (brief_render.sh puts these LAST, under FOUNDER STEER — HIGHEST AUTHORITY):
#   · newest first, and the newest wins when two steers conflict
#   · retired lines are prefixed `~~` and are NOT rendered (record kept: append-only invariant)
#   · a steer is a DIRECTIVE, not a hint — the drive is told to obey it or state in writing why it cannot
# Every write also appends to STEER_LOG.jsonl so "what was the human told to look at, and when" survives
# resets and can be correlated with score movement later.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
BANK="${PH_BRIEF_BANK:-$CT/BRIEF_BANK.md}"
LOG="$CT/STEER_LOG.jsonl"
MAX_ACTIVE=8   # more than this per scope means contradictory steering; we warn rather than silently pile up

now(){ date -u +%FT%TZ 2>/dev/null || echo "unknown"; }

# add a line to section "## STEER:<scope>", creating the section if absent
add(){
  local scope="$1" text="$2" ts; ts="$(now)"
  [ -f "$BANK" ] || printf '# BRIEF_BANK — drive briefs + steers (created on first steer)\n' > "$BANK"
  case "$text" in *$'\n'*) echo "⛔ steer must be ONE line"; return 1;; esac
  if ! grep -q "^## STEER:$scope\$" "$BANK"; then
    printf '\n## STEER:%s\n' "$scope" >> "$BANK"
  fi
  # insert directly under the header so newest is first
  python3 - "$BANK" "$scope" "- [$ts] $text" <<'PY'
import sys
path, scope, line = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path, encoding="utf-8").read().split("\n")
hdr = "## STEER:%s" % scope
out, done = [], False
for ln in src:
    out.append(ln)
    if not done and ln.strip() == hdr:
        out.append(line)
        done = True
open(path, "w", encoding="utf-8").write("\n".join(out))
PY
  printf '{"at":"%s","scope":"%s","text":%s,"action":"add"}\n' "$ts" "$scope" \
    "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$text")" >> "$LOG"
  local n; n="$(active_count "$scope")"
  echo "  ✓ steer recorded → $scope  ($n active)"
  echo "    \"$text\""
  [ "$n" -gt "$MAX_ACTIVE" ] && echo "  ⚠ $n active steers on $scope — contradictory steering dilutes all of them. ph steer clear $scope"
  echo "  다음 드라이브부터 즉시 반영됩니다 (확인: ph brief <key> <task_type> | head -40)"
}

active_count(){ awk -v h="## STEER:$1" '
  /^## /{cur=$0; next}
  { if (cur==h && $0 ~ /^- \[/) n++ } END{print n+0}' "$BANK" 2>/dev/null; }

list(){
  echo "== active steers (newest first; newest wins on conflict) =="
  awk '
    /^## STEER:/{cur=substr($0,10); print "\n["cur"]"; next}
    /^## /{cur=""; next}
    { if (cur!="" && $0 ~ /^- \[/) print "  "$0
      else if (cur!="" && $0 ~ /^~~/) print "  (retired) "$0 }' "$BANK" 2>/dev/null
  echo
  echo "add: ph steer \"<한 줄>\"  |  ph steer <key> \"<한 줄>\"     retire: ph steer clear <key|GLOBAL>"
}

clear_scope(){
  local scope="$1" ts; ts="$(now)"
  grep -q "^## STEER:$scope\$" "$BANK" || { echo "  no steers on $scope"; return 0; }
  python3 - "$BANK" "$scope" <<'PY'
import sys
path, scope = sys.argv[1], sys.argv[2]
src = open(path, encoding="utf-8").read().split("\n")
hdr, cur, n = "## STEER:%s" % scope, "", 0
out = []
for ln in src:
    if ln.startswith("## "):
        cur = ln.strip()
    elif cur == hdr and ln.startswith("- ["):
        ln = "~~" + ln          # struck through: record kept (append-only), injection stopped
        n += 1
    out.append(ln)
open(path, "w", encoding="utf-8").write("\n".join(out))
print("  ✓ retired %d steer(s) on %s (kept in the file, struck through)" % (n, scope))
PY
  printf '{"at":"%s","scope":"%s","action":"clear"}\n' "$ts" "$scope" >> "$LOG"
}

case "${1:-}" in
  ""|-h|--help)
    echo "ph steer \"<한 줄>\"            모든 드라이브에 즉시 반영되는 지시 (GLOBAL)"
    echo "ph steer <key> \"<한 줄>\"      그 대회에만"
    echo "ph steer list                   활성 지시 보기"
    echo "ph steer clear <key|GLOBAL>     회수 (기록은 남고 주입만 중단)"
    ;;
  list)  list ;;
  clear) clear_scope "${2:?ph steer clear <key|GLOBAL>}" ;;
  *)
    if [ "$#" -ge 2 ]; then add "$1" "$2"; else add "GLOBAL" "$1"; fi
    ;;
esac
