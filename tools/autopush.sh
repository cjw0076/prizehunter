#!/usr/bin/env bash
# autopush.sh — TYPE-AWARE SELF-PUSH driver (founder 2026-07-23: "전부 자동으로 밀고, 점수 올리고, 제출물 컨펌,
# 무의미한 반복 없이 스스로 푸시" + "대회 종류별로 어떻게 관리할지부터 분리").
#
# 대회는 타입마다 관리 방식이 다르다 — autopush는 타입별로 다르게 행동한다:
#   • leaderboard : 마감까지 CONTINUOUS. idle+headroom이면 다음-레버 워커 실행 → CV검증 → 개선시 제출-스테이징.
#                   "끝"이 없다(마감까지 계속 climb). submit_action=KAGGLE/CRUNCH(토큰) 또는 GATE(founder).
#   • submission  : ONE-SHOT craft. 산출물 없으면 1회 생성 워커 → QC → 컨펌요청 → DONE(재실행 안 함). 반복 금지.
#   • agentic     : 빌드형. 시스템/데모 준비 워커 1회 → verify → 컨펌 → DONE.
#
# Board $BOARD (TSV): key \t type \t dir(min|max) \t best \t target \t worker_cmd \t submit_action \t status
#   status: '' | driving | ready(제출물 준비됨/컨펌대기) | confirmed | done. worker writes $R/drive_<key>.score (a number)
#   or $R/drive_<key>.ready (submission/agentic 산출물 준비 신호).
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
# multi-tenant: every state path is env-overridable so one daemon can serve isolated tenants
R="${PH_RUNS:-$CT/.runs}"; mkdir -p "$R"
# refuse to start a NEW push cycle under disk pressure (disk_guard prints why)
bash "$CT/tools/disk_guard.sh" || exit 3
BOARD="${PH_BOARD:-$R/autopush_board.tsv}"; WF="${PH_WORKERS:-$R/fleet_workers.tsv}"
ROOT="$(cd "$CT/.." && pwd)"; cd "$ROOT" || exit 1
touch "$BOARD" "$WF"
NCORES="$(nproc 2>/dev/null || echo 8)"; L="$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 0)"
MAXLOAD="${AUTOPUSH_MAXLOAD:-$(python3 -c "print(int($NCORES*1.2))" 2>/dev/null || echo 60)}"
alive(){ while IFS=$'\t' read -r n p o; do [ "$n" = "drive:$1" ] && kill -0 "$p" 2>/dev/null && return 0; done < "$WF"; return 1; }
improved(){ python3 -c "import sys;n,b,d='$1','$2','$3'
sys.exit(0 if b not in('','-') and ((float(n)<float(b)) if d=='min' else (float(n)>float(b))) else 1)" 2>/dev/null; }

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
echo "== autopush @ $(date -u +%FT%TZ) | load $L/$NCORES (cap $MAXLOAD) =="
[ -s "$BOARD" ] || { echo "  (board empty)"; exit 0; }
launched=0; confirm=0; tmp="$BOARD.tmp"; : > "$tmp"

while IFS=$'\t' read -r key type dir best target wcmd submit status; do
  [ -z "$key" ] || [ "${key:0:1}" = "#" ] && { [ -n "$key" ] && echo -e "$key\t$type\t$dir\t$best\t$target\t$wcmd\t$submit\t${status:-}" >> "$tmp"; continue; }
  nstatus="${status:-}"
  if alive "$key"; then echo "  ▶ $key [$type]: LIVE"; nstatus="driving";
  else
    case "$type" in
      leaderboard)
        sf="$R/drive_${key}.score"
        if [ -f "$sf" ]; then
          new="$(tr -dc '0-9.\-' < "$sf")"
          if [ -n "$new" ] && improved "$new" "$best" "$dir"; then
            # TRANSFER GATE: a local gain is a HYPOTHESIS about the leaderboard. It may not open the founder
            # submit gate unless the shipped artifact is provably the validated one (rogii shipped a kernel with
            # WARP removed, 17% of rows and 8% of PF particles — local 8.565 landed as LB 10.781).
            if bash "$CT/tools/transfer_gate.sh" gate "$key" "$new" "$R/submission_manifest_${key}.json" >"$R/transfer_${key}.log" 2>&1; then
              printf '%s\t%s\t%s\n' "$new" "$submit" "$(date -u +%FT%TZ 2>/dev/null)" > "$R/confirm_${key}.pending"
            else
              printf '%s\t%s\t%s\n' "$new" "TRANSFER-BLOCKED: $submit" "$(date -u +%FT%TZ 2>/dev/null)" > "$R/confirm_${key}.blocked"
              echo "     ⛔ transfer gate BLOCKED this improvement (see .runs/transfer_${key}.log) — no founder gate opened"
            fi
            # AUTO-FEEDBACK (SYSTEM_GAP_REPORT #1): record the round into goal_loop's history so stall_level
            # accumulates and REFUTE / HARD_PIVOT can fire WITHOUT a human. This was the loop's missing input.
            # SCALE GUARD: a drive reports its LOCAL score. goal_loop history is LB-scale, so recording the local
            # number there manufactures fictitious progress. Unless the drive tags itself lb-scale, we record the
            # UNCHANGED LB best — an honest FLAT round, which is exactly what should arm REFUTE.
            rec="$best"; [ -f "$R/drive_${key}.scale" ] && grep -qi '^lb' "$R/drive_${key}.scale" && rec="$new"
            timeout 60 python3 "$CT/tools/goal_loop.py" --key "$key" --record "$rec" >/dev/null 2>&1 || true
            echo "  ✅ $key: NEW BEST $new (was $best) → $submit — CONFIRM"; best="$new"; confirm=$((confirm+1))
          else
            echo "  ▬ $key: done, no improvement ($new vs $best) — recording a FLAT round (this is what makes REFUTE/HARD_PIVOT fire)"
            timeout 60 python3 "$CT/tools/goal_loop.py" --key "$key" --record "$best" >/dev/null 2>&1 || true
          fi
          nstatus=""; mv "$sf" "$sf.done" 2>/dev/null
        fi
        # leaderboard = CONTINUOUS: 컨펌 대기와 무관하게 target 미달이면 계속 다음-레버 실행
        if [ "$best" != "$target" ] && [ -n "$wcmd" ] && [ "$wcmd" != "-" ] && ! disk_block && awk "BEGIN{exit !($L<$MAXLOAD)}"; then
          log="$R/drive_${key}.log"; eval "PYTHONUNBUFFERED=1 nohup $wcmd > '$log' 2>&1 &"; pid=$!
          echo -e "drive:$key\t$pid\t$log" >> "$WF"; echo "  🚀 $key: next-lever PID $pid (best $best→$target)"; launched=$((launched+1)); nstatus="driving"
        elif [ "$best" = "$target" ]; then echo "  ✔ $key [leaderboard]: target 도달 ($best)"
        else echo "  ⏸ $key [leaderboard]: idle — best $best→$target, next-lever(worker_cmd) 미배선"; fi
        [ -f "$R/confirm_${key}.pending" ] && echo "     ↳ 컨펌대기: $(cut -f1 "$R/confirm_${key}.pending") → $submit" ;;
      submission|agentic)
        # ONE-SHOT: 산출물 ready 신호 있으면 컨펌대기 후 DONE. 없고 아직 안 만들었으면 1회 생성.
        if [ -f "$R/drive_${key}.ready" ]; then echo "  ✅ $key [$type]: 산출물 준비됨 → $submit CONFIRM"; confirm=$((confirm+1)); nstatus="ready"
          printf 'ready\t%s\t%s\n' "$submit" "$(date -u +%FT%TZ 2>/dev/null)" > "$R/confirm_${key}.pending"; mv "$R/drive_${key}.ready" "$R/drive_${key}.ready.done" 2>/dev/null
        elif [ -z "$nstatus" ] && [ -n "$wcmd" ] && [ "$wcmd" != "-" ] && awk "BEGIN{exit !($L<$MAXLOAD)}"; then
          log="$R/drive_${key}.log"; eval "PYTHONUNBUFFERED=1 nohup $wcmd > '$log' 2>&1 &"; pid=$!
          echo -e "drive:$key\t$pid\t$log" >> "$WF"; echo "  🚀 $key [$type]: 산출물 1회 생성 PID $pid"; launched=$((launched+1)); nstatus="driving"
        elif [ "$nstatus" = "ready" ]; then echo "  ⏸ $key [$type]: 컨펌대기 (재실행 안 함)";
        else echo "  ✔ $key [$type]: $nstatus"; fi ;;
      blocked) echo "  🔒 $key [blocked]: $submit — founder 1회 언락시 leaderboard로 승격" ;;
      *) echo "  ? $key: unknown type '$type'" ;;
    esac
  fi
  echo -e "$key\t$type\t$dir\t$best\t$target\t$wcmd\t$submit\t$nstatus" >> "$tmp"
done < "$BOARD"
mv "$tmp" "$BOARD"
echo "== launched=$launched · needs-confirm=$confirm =="
[ "$confirm" -gt 0 ] && echo "  ⚠ 컨펌 필요: notify_founder.sh 태우거나 founder에 surface"
exit 0
