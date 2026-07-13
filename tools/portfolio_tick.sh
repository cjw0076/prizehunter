#!/usr/bin/env bash
# portfolio_tick.sh — the self-sustaining heartbeat of the prize-hunt system.
# 1) aios_autocapture: records any unrecorded ledger work as AIOS receipts+packets
# 2) portfolio_scan: refreshes the unified leaderboard PORTFOLIO_STATUS.md
# 3) memoryos deposit: push fresh receipts into MemoryOS as DRAFT knowledge
#    (tacit->explicit flywheel; draft-first, privacy-scanned). MEMOOS_DEPOSIT=0 to skip.
# Runs from cron so the record-asset loop never freezes, regardless of which
# agent/session did the work. Append-only + read-only; no submissions, no secrets.
set -euo pipefail

CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
LOG="$CONTROL/portfolio_tick.log"

# cron runs with a bare PATH — expose miniconda so children resolve the same
# interpreters as interactive runs (memoryos `python`, playwright renders, kaggle CLI)
[ -d "$HOME/miniconda3/bin" ] && export PATH="$HOME/miniconda3/bin:$PATH"

{
  printf '\n===== portfolio_tick %s =====\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
  "$CONTROL/tools/aios_autocapture.sh" 2>&1 || printf 'autocapture error\n'
  python3 "$CONTROL/tools/deadline_watchdog.py" 2>&1 | tail -4 || printf 'deadline watchdog error\n'
  "$CONTROL/tools/portfolio_scan.sh" 2>&1 || printf 'scan error\n'
  # keep every strict-status source in step with the (possibly watchdog-mutated) registry
  bash "$CONTROL/tools/strategist_brief.sh" >/dev/null 2>&1 || printf 'brief regen error\n'
  python3 "$CONTROL/tools/quality_gate.py" >/dev/null 2>&1 || printf 'quality gate regen error\n'
  python3 "$CONTROL/tools/pnl_sync.py" 2>&1 | tail -1 || printf 'pnl sync error\n'
  bash "$CONTROL/tools/plan_backfill.sh" 2>&1 | tail -1 || printf 'plan backfill error\n'
  # posterior stage (playbook/POSTERIOR.md): outcomes radar + result auto-check + influence drafts
  python3 "$CONTROL/tools/settle.py" watch 2>&1 | tail -1 || printf 'settle watch error\n'
  python3 "$CONTROL/tools/result_check.py" 2>&1 | tail -1 || printf 'result check error\n'
  python3 "$CONTROL/tools/influence_tick.py" 2>&1 | tail -1 || printf 'influence tick error\n'
  # weekly lane — LEARN/EXIT freshness: corpus re-mine, learning digest, influence digest, portfolio, sale dossier
  WSTAMP="$CONTROL/.runs/weekly.stamp"
  if [ ! -f "$WSTAMP" ] || [ "$(( $(date +%s) - $(stat -c %Y "$WSTAMP") ))" -gt 518400 ]; then
    timeout 900 python3 "$CONTROL/tools/mine_sessions.py" --filter dacon >/dev/null 2>&1 && printf 'corpus re-mined\n' || printf 'corpus mine error/timeout\n'
    python3 "$CONTROL/tools/learning_digest.py" 2>&1 | tail -1 || printf 'learning digest error\n'
    python3 "$CONTROL/tools/influence_tick.py" --weekly 2>&1 | tail -1 || printf 'influence weekly error\n'
    python3 "$CONTROL/tools/build_portfolio.py" 2>&1 | tail -1 || printf 'portfolio error\n'
    bash "$CONTROL/tools/build_sale_dossier.sh" >/dev/null 2>&1 && printf 'sale dossier refreshed\n' || printf 'sale dossier error\n'
    touch "$WSTAMP"
  fi
  if [ "${MEMOOS_DEPOSIT:-1}" = "1" ]; then
    # deposit receipts touched in the last ~4h (covers this tick's new learnings)
    mapfile -t fresh < <(find "$CONTROL/receipts" -name '*.md' -mmin -240 2>/dev/null)
    if [ "${#fresh[@]}" -gt 0 ]; then
      printf 'memoryos deposit: %s fresh receipt(s)\n' "${#fresh[@]}"
      "$CONTROL/tools/memoryos_bridge.sh" deposit "${fresh[@]}" 2>&1 | tail -3 || printf 'memoryos deposit skipped\n'
    else printf 'memoryos deposit: no fresh receipts\n'; fi
  fi
  if python3 "$CONTROL/tools/submission_board.py" --check >/dev/null 2>&1; then
    printf 'submission board: strict status audit ok\n'
  else
    printf 'submission board: strict status audit FAILED — run `ph submitted --check`\n'
  fi
} >>"$LOG" 2>&1

tail -6 "$LOG"
