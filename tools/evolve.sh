#!/usr/bin/env bash
# evolve.sh — THE UNIFIER. goal_loop is the VERDICT authority; the research engine is its EXECUTION ARM.
#
# Why this exists (found 2026-07-25, founder pointed at playbook/EVOLUTIONARY_RECIPE.md):
# the recipe's evolution mechanism was ALREADY designed AND implemented in tools/goal_loop.py
# (stall_level: 3 flat cycles -> REFUTE, 5 -> HARD_PIVOT; archetype-aware per-competition loops; gap-to-#1
# over the registry's 21 live competitions). The failure was NOT a missing mechanism — it was
#   FRAGMENTATION: autopush/next_lever drove a second hand-made board (12 rows) instead of the registry, and
#   BYPASS:        drive results were never recorded through goal_loop, so stall_level never accumulated and
#                  REFUTE / HARD_PIVOT could never fire — the system kept polishing exhausted framings.
# evolve.sh closes that loop: read the verdict, dispatch the matching arm, RECORD the outcome back.
#
#   VERDICT      -> ACTION
#   PUSH         -> next_lever.sh          (cheap incremental drive)
#   REFUTE       -> research_drive.sh      (divergent tournament + adversarial refutation)
#   HARD_PIVOT   -> research_drive.sh with the paradigm-shift lens FORCED (clean slate, failure memory injected)
#   JUDGED       -> judged path: craft + the recipe's Phase-4 120% adversarial judge before any founder gate
#   AT_#1/DONE/NO_TARGET -> no drive (bank / nothing to chase)
#
# usage: evolve.sh [--execute] [--key KEY] [--max N]
#        (dry by default — prints the dispatch plan; --execute actually launches)
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
MAP="$R/evolve_map.tsv"          # key \t campaign_dir \t task_type   (auto-guessed when absent)
WF="${PH_WORKERS:-$R/fleet_workers.tsv}"
EXEC=0; ONLY=""; MAX=2
while [ $# -gt 0 ]; do case "$1" in --execute) EXEC=1;; --key) ONLY="${2:-}"; shift;; --max) MAX="${2:-2}"; shift;; esac; shift; done
NCORES="$(nproc 2>/dev/null || echo 8)"; L="$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 0)"
MAXLOAD="${AUTOPUSH_MAXLOAD:-$(python3 -c "print(int($NCORES*1.2))" 2>/dev/null || echo 60)}"
touch "$MAP" "$WF"
cd "$ROOT" || exit 1

guess_dir(){ ls -d "$CT/campaigns/"*"${1%%-*}"* 2>/dev/null | head -1; }
guess_tt(){ # crude archetype -> task_type; the map file overrides it
  case "$1" in *baram*|*wind*) echo "time-series-forecast";; *structural-break*|*changepoint*) echo "time-series-changepoint";;
  *rogii*|*wellbore*) echo "well-log-inversion";; *arc-*) echo "abstract-reasoning";;
  *class*|*s6e7*|*aiswuniv*) echo "tabular-classification";; *) echo "tabular-regression";; esac }
lookup(){ awk -F'\t' -v k="$1" '$1==k{print $2"\t"$3; found=1} END{if(!found) print ""}' "$MAP" 2>/dev/null | head -1; }
alive(){ while IFS=$'\t' read -r n p o; do [ "$n" = "drive:$1" ] && kill -0 "$p" 2>/dev/null && return 0; done < "$WF"; return 1; }
# EVOLUTIONARY_RECIPE Phase 2 — SUBMISSION ECONOMY: risk tolerance is a function of runway, not of mood.
#   >14d  ANCHOR   : build an honest CV; spend submissions only to anchor CV<->LB
#   4-14d OPTIMIZE : spend a slot only on a confident local gain (>=0.5%)
#   <=3d  EXPLOIT  : take the bold high-variance hypothesis — a safe entry at the deadline is a lost entry
risk_mode(){ # risk_mode <key> -> "MODE|days"
  local key="$1" dl days
  dl="$(grep -F "| $key |" "$CT/DEADLINE_RADAR.md" 2>/dev/null | grep -oE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' | head -1)"
  [ -z "$dl" ] && dl="$(grep -rhoE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' "$CT/campaigns/$key/RECON.md" 2>/dev/null | sort | tail -1)"
  if [ -z "$dl" ]; then echo "UNKNOWN|?"; return; fi
  days="$(python3 -c "
import datetime,sys
try:
    d=(datetime.date.fromisoformat('$dl')-datetime.datetime.utcnow().date()).days; print(d)
except Exception: print('?')" 2>/dev/null)"
  case "$days" in ''|'?') echo "UNKNOWN|?";;
    *) if [ "$days" -gt 14 ] 2>/dev/null; then echo "ANCHOR|$days"
       elif [ "$days" -gt 3 ] 2>/dev/null; then echo "OPTIMIZE|$days"
       elif [ "$days" -ge 0 ] 2>/dev/null; then echo "EXPLOIT|$days"
       else echo "PASSED|$days"; fi;;
  esac }

# DISK GUARD (council 2026-07-26, corrected 2026-07-26): a drive that fills the disk corrupts state mid-run.
# NOTE the correction — the first version used PERCENT USED (>=85%) and immediately blocked everything on a disk
# that was 90% used but had 194 GB free. On a large shared disk, percent is the wrong instrument: ABSOLUTE FREE
# SPACE is what a drive consumes. Percent is kept only as a last-ditch signal (>=97%).
disk_free_gb(){ df -PBG "$CT" 2>/dev/null | awk 'NR==2{gsub("G","",$4); print $4+0}'; }
disk_pct(){ df -P "$CT" 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5+0}'; }
disk_block(){ local g p; g="$(disk_free_gb)"; p="$(disk_pct)"
  local ming="${PH_DISK_MIN_FREE_GB:-20}" maxp="${PH_DISK_MAX_PCT:-97}"
  if [ -n "$g" ] && [ "$g" -lt "$ming" ]; then
    echo "  ⛔ DISK only ${g}GB free (< ${ming}GB) — refusing new drives"; return 0; fi
  if [ -n "$p" ] && [ "$p" -ge "$maxp" ]; then
    echo "  ⛔ DISK ${p}% used (>= ${maxp}%) — refusing new drives"; return 0; fi
  return 1; }
echo "== evolve @ $(date -u +%FT%TZ 2>/dev/null) | load $L/$NCORES (cap $MAXLOAD) | $([ $EXEC = 1 ] && echo EXECUTE || echo DRY) =="
launched=0
# goal_loop is the single source of truth (registry-driven, archetype-aware, stall-based)
while IFS= read -r line; do
  line="${line#- }"; line="${line#"${line%%[![:space:]]*}"}"   # goal_loop prints "- [VERDICT] key: ..."
  case "$line" in \[*\]*) ;; *) continue;; esac
  v="${line%%]*}"; v="${v#[}"                       # verdict
  rest="${line#*] }"; key="${rest%%:*}"; key="${key# }"
  [ -n "$ONLY" ] && [ "$key" != "$ONLY" ] && continue
  if alive "$key"; then echo "  ▶ $key [$v]: drive LIVE — skip"; continue; fi
  m="$(lookup "$key")"; d="$(printf '%s' "$m" | cut -f1)"; tt="$(printf '%s' "$m" | cut -f2)"
  [ -z "$d" ] && d="$(guess_dir "$key")"; [ -z "$tt" ] && tt="$(guess_tt "$key")"
  # ENTRY FRAME FIRST (founder 2026-07-26: 진입 프레임이 이후 전부를 상속한다). A competition with a missing,
  # stale, verdict-poisoned or target-less frame gets FRAMED — not driven. Driving on a bad frame is how rogii
  # closed itself as AT_#1 and ADIA aimed at nothing for two rounds.
  if [ -n "$d" ] && ! bash "$CT/tools/open_frame.sh" check "$key" "$d" >/dev/null 2>&1; then
    if [ "$launched" -lt "$MAX" ] && awk "BEGIN{exit !($L<$MAXLOAD)}"; then
      echo "  🔓 $key [$v]: entry frame missing/stale/closed → OPENING FRAME first (no drive on a bad frame)"
      launched=$((launched+1))
      if [ "$EXEC" = 1 ]; then
        lg="$R/frame_${key}.log"
        eval "nohup env PYTHONUNBUFFERED=1 bash '$CT/tools/open_frame.sh' make '$key' '$d' > '$lg' 2>&1 &"
        printf 'drive:%s\t%s\t%s\n' "$key" "$!" "$lg" >> "$WF"
      fi
    else echo "  ⏭ $key [$v]: needs a frame — next cycle"; fi
    continue
  fi
  # GAP GATE: a competition with no (or stale) measured gaps gets HUNTED first — our biggest movements came from
  # structural facts (mis-set target, untrusted harness, distribution shift), not from tuning.
  if [ -n "$d" ] && [ ! -f "$d/GAP_REPORT.md" ] && [ "$v" != "JUDGED" ]; then
    if [ "$launched" -lt "$MAX" ] && awk "BEGIN{exit !($L<$MAXLOAD)}"; then
      echo "  🔍 $key [$v]: no measured gaps → GAP HUNT first (findings become the next brief's directives)"
      launched=$((launched+1))
      if [ "$EXEC" = 1 ]; then
        lg="$R/gap_${key}.log"
        eval "nohup env PYTHONUNBUFFERED=1 bash '$CT/tools/gap_hunt.sh' comp '$key' '$d' '$tt' > '$lg' 2>&1 &"
        printf 'drive:%s\t%s\t%s\n' "$key" "$!" "$lg" >> "$WF"
      fi
    else echo "  ⏭ $key [$v]: needs a gap hunt — next cycle"; fi
    continue
  fi
  rm_out="$(risk_mode "$key")"; RMODE="${rm_out%%|*}"; RDAYS="${rm_out##*|}"
  # Phase-2 economy hard rule: a passed deadline earns ZERO compute (this was silently burning tokens)
  if [ "$RMODE" = "PASSED" ]; then echo "  ⛔ $key [$v]: deadline passed (D-$RDAYS) — no compute; settle or relist the row"; continue; fi
  case "$v" in
    PUSH)       act="PH_RISK_MODE=$RMODE bash $CT/tools/next_lever.sh $key $d $tt"; why="incremental · economy=$RMODE (D-$RDAYS)";;
    REFUTE)     act="PH_RISK_MODE=$RMODE bash $CT/tools/research_drive.sh $key $d $tt 3"; why="stalled 3 cycles → divergent tournament + adversarial refutation · economy=$RMODE (D-$RDAYS)";;
    HARD_PIVOT) act="PH_FORCE_PARADIGM=1 PH_RISK_MODE=$RMODE bash $CT/tools/research_drive.sh $key $d $tt 3"; why="stalled 5 cycles → CLEAN SLATE (paradigm-shift forced) · economy=$RMODE (D-$RDAYS)";;
    JUDGED)     if [ -f "$R/confirm_${key}.pending" ]; then act=""; why="judged: 산출물 컨펌대기 (재실행 안 함)"
                elif [ -f "$R/judge120_${key}.verdict" ] && grep -q '^FAIL' "$R/judge120_${key}.verdict" 2>/dev/null; then
                     act=""; why="judged: judge120 FAIL — 결함 수정 필요 (게이트 닫힘, $(basename "$d")/JUDGE120_REJECTION.md)"
                else act="bash $CT/tools/judge120.sh $key $d"; why="judged → Phase-4 120% 적대심사 게이트 (통과시에만 founder 컨펌 열림) · economy=$RMODE (D-$RDAYS)"; fi;;
    AT_#1|DONE|NO_TARGET) act=""; why="nothing to chase (bank)";;
    *)          act=""; why="verdict '$v' has no arm yet";;
  esac
  if [ -z "$act" ]; then echo "  ⏸ $key [$v]: $why"; continue; fi
  if disk_block; then continue; fi
  if [ -z "$d" ]; then echo "  ⚠ $key [$v]: campaign dir not found — add a row to $(basename "$MAP")"; continue; fi
  if ! awk "BEGIN{exit !($L<$MAXLOAD)}"; then echo "  ⛔ $key [$v]: load $L ≥ cap — defer"; continue; fi
  [ "$launched" -ge "$MAX" ] && { echo "  ⏭ $key [$v]: per-run launch cap ($MAX) reached — next cycle"; continue; }
  echo "  🚀 $key [$v]: $why"
  launched=$((launched+1))          # count in dry too, so the printed plan respects --max honestly
  if [ "$EXEC" = 1 ]; then
    lg="$R/evolve_${key}.log"
    eval "nohup env PYTHONUNBUFFERED=1 $act > '$lg' 2>&1 &"   # env: $act may carry VAR=val prefixes
    printf 'drive:%s\t%s\t%s\n' "$key" "$!" "$lg" >> "$WF"
  fi
done < <(timeout 120 python3 "$CT/tools/goal_loop.py" --board 2>/dev/null | grep -viE libtinfo)
echo "== launched=$launched ($([ $EXEC = 1 ] && echo real || echo dry)) =="
# AUTO-FEEDBACK (SYSTEM_GAP_REPORT #1): any drive that left a score file gets recorded into goal_loop history
for sf in "$R"/drive_*.score; do
  [ -e "$sf" ] || continue
  k="$(basename "$sf" .score)"; k="${k#drive_}"
  v="$(tr -dc '0-9.\-' < "$sf" | head -c 24)"
  # SCALE GUARD (see autopush): only an lb-tagged score enters LB-scale history; otherwise record a FLAT round
  rec="$v"; if [ ! -f "$R/drive_${k}.scale" ] || ! grep -qi '^lb' "$R/drive_${k}.scale" 2>/dev/null; then
    rec="$(awk -F'\t' -v kk="$k" '$1==kk{print $6; exit}' "$CT/portfolio_registry.tsv" 2>/dev/null)"; [ -z "$rec" ] && rec="$v"
  fi
  [ -n "$rec" ] && { timeout 60 python3 "$CT/tools/goal_loop.py" --key "$k" --record "$rec" >/dev/null 2>&1 && \
    echo "  ↺ recorded $k=$v into goal_loop history (stall_level accumulates → REFUTE/HARD_PIVOT can fire)"; }
  mv "$sf" "$sf.recorded" 2>/dev/null
done
