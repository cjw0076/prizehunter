#!/usr/bin/env bash
# watch.sh — the HEAD AGENT'S SUPERVISION SCREEN. One command, five questions, every cycle.
#
# founder 2026-07-26: "너도 loop형태로 subagent 죽으면 계속 띄우고, 대회 제대로 진행하고있는지, Ideation이나
# 자원 부족하지 않은지, Prizehunter가 제대로 돌아가는지를 확인해줘."
#
# The head agent is the only thing that can spawn Claude subagents, so respawning is a JUDGMENT the head makes —
# but the FACTS it needs must not come from memory. This prints them:
#   1) WORKERS   — which drives/agents are alive, which died, and what each left behind (a dead worker that wrote
#                  nothing is a failed worker, not a finished one; that distinction was invisible until now)
#   2) MOVEMENT  — did any competition actually move since the last cycle (recorded history, not vibes)
#   3) RESOURCES — substrate availability/cooling, box load, disk, and whether the free substrates are exhausted
#   4) IDEATION  — lens coverage and prompt-variant usage: is the search still diverging or repeating itself
#   5) GATES     — what is waiting on the founder, and what is blocked by the transfer gate
# Ends with the doctor headline, because a structural defect voids everything above it.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"
REG="$CT/portfolio_registry.tsv"; PLOG="$CT/PROCESS_LOG.tsv"; WF="$R/fleet_workers.tsv"
ROOT="$(cd "$CT/.." && pwd)"
echo "== ph watch @ $(date -u +%FT%TZ 2>/dev/null) =="

echo; echo "1) WORKERS"
alive=0; dead_empty=0
if [ -f "$WF" ]; then
  # last registration per key wins
  awk -F'\t' '$1!="" {a[$1]=$2"\t"$3} END{for(k in a) print k"\t"a[k]}' "$WF" | sort | while IFS=$'\t' read -r name pid log; do
    st="dead"; kill -0 "$pid" 2>/dev/null && st="ALIVE"
    # resolve relative paths against the repo root — the first version reported every relative artifact as "0B
    # FAILED" (a false alarm is the same disease as a silent no-op: it destroys the signal)
    lp="$log"; [ -n "$lp" ] && [ "${lp#/}" = "$lp" ] && lp="$ROOT/$lp"
    sz=-1; [ -n "$lp" ] && [ -f "$lp" ] && sz="$(wc -c < "$lp" 2>/dev/null || echo 0)"
    note=""
    if [ "$st" = "dead" ]; then
      if [ "${sz}" = "-1" ]; then note="  (artifact path not found — stale registration, ignore)"
      elif [ "${sz:-0}" -lt 200 ]; then note="  ⚠ wrote ${sz}B — FAILED, not finished (respawn or fix)"
      else note="  (left ${sz}B)"; fi
    fi
    printf "   %-34s %-6s %s%s\n" "$name" "$st" "$(basename "${log:-–}")" "$note"
  done
else echo "   (no worker registry)"; fi
echo "   note: Claude subagents are NOT in this list — only the head agent can see/respawn those (check its own task list)."

echo; echo "2) MOVEMENT (recorded rounds per competition; flat rounds are what arm REFUTE)"
found=0
for f in "$R"/goal_*.json; do
  [ -e "$f" ] || continue
  k="$(basename "$f" .json)"; k="${k#goal_}"
  python3 - "$f" "$k" <<'PY'
import json, sys
f, k = sys.argv[1], sys.argv[2]
try: h = json.load(open(f)).get("history", [])
except Exception: h = []
if not h: print(f"   {k:<34} (no rounds recorded)"); raise SystemExit
vals = [x.get("best") for x in h]
moved = len({str(v) for v in vals}) > 1
print(f"   {k:<34} rounds={len(h):<3} best_trace={vals[-4:]}  {'moved' if moved else 'FLAT (stall accumulating)'}")
PY
  found=1
done
[ "$found" = 0 ] && echo "   (nothing recorded yet — if drives are running, their outcomes are not being fed back)"

echo; echo "3) RESOURCES"
echo "   box load: $(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null) / $(nproc 2>/dev/null || echo '?') cores"
echo "   disk:     $(df -h "$CT" 2>/dev/null | awk 'NR==2{print $4" free ("$5" used)"}')"
for s in codex agy claude ollama; do
  have="missing"; command -v "$s" >/dev/null 2>&1 && have="present"
  cool=""; [ -f "$R/.substrate_backoff.$s" ] && cool=" COOLING($(python3 -c "
import os,time
try: print(int(time.time()-os.path.getmtime('$R/.substrate_backoff.$s')))
except Exception: print('?')" 2>/dev/null)s)"
  printf "   substrate %-7s %s%s\n" "$s" "$have" "$cool"
done
q="$(grep -rl 'usage limit\|quota' "$R"/*.log 2>/dev/null | wc -l)"
[ "${q:-0}" -gt 0 ] && echo "   ⚠ $q log(s) contain a quota wall — free substrates may be exhausted; chain order is codex→agy→local→claude (claude last on purpose)"

echo; echo "4) IDEATION (is the search still diverging, or repeating itself?)"
if [ -f "$PLOG" ]; then
  tot="$(awk -F'\t' '$4=="diverge"' "$PLOG" 2>/dev/null | wc -l)"
  used="$(awk -F'\t' '$4=="diverge"{print $5}' "$PLOG" 2>/dev/null | sort -u | wc -l)"
  all="$(grep -cE '^ "[a-z-]+"$' "$CT/tools/research_drive.sh" 2>/dev/null | head -1)"
  all="${all:-0}"
  echo "   lens runs=$tot · distinct lenses used=$used / $all available"
  [ "$used" -le 2 ] && [ "$tot" -gt 5 ] && echo "   ⚠ the search is repeating a couple of lenses — force breadth (ph meta priors <task_type>, or run research_drive with more lenses)"
  awk -F'\t' '$4=="diverge"{print $5}' "$PLOG" 2>/dev/null | sort | uniq -c | sort -rn | head -4 | sed 's/^/     /'
  bank_age="$(python3 -c "
import os,time
try: print(int((time.time()-os.path.getmtime('$CT/BRIEF_BANK.md'))/3600))
except Exception: print('?')" 2>/dev/null)"
  echo "   BRIEF_BANK last mutated ${bank_age}h ago (the head agent is supposed to keep injecting/retiring variants)"
else echo "   (no PROCESS_LOG — no tournament has run)"; fi

echo; echo "5) GATES"
np=0
for f in "$R"/confirm_*.pending; do [ -e "$f" ] || continue
  k="$(basename "$f" .pending)"; k="${k#confirm_}"
  printf "   ⏸ founder-confirm  %-30s %s\n" "$k" "$(cut -f1,2 "$f" | tr '\t' ' ')"; np=$((np+1)); done
for f in "$R"/confirm_*.blocked; do [ -e "$f" ] || continue
  k="$(basename "$f" .blocked)"; k="${k#confirm_}"
  printf "   ⛔ transfer-blocked %-30s %s\n" "$k" "$(cut -f1,2 "$f" | tr '\t' ' ')"; done
[ "$np" = 0 ] && echo "   (nothing awaiting the founder)"
res="$(bash "$CT/tools/resonate.sh" status 2>/dev/null | head -1)"; echo "   resonance: ${res:-?}"

echo; bash "$CT/tools/doctor.sh" --brief 2>/dev/null
echo "== end watch — respawn any worker marked FAILED, then act on the highest-EV row (ph meta allocate) =="
