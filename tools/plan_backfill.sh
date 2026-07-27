#!/usr/bin/env bash
# plan_backfill.sh — 유입(discovery cron)은 자동인데 TRIAGE→PLAN 이 수동이라 생기던
# 정체 해소: registry 의 active-계열 행 중 PLAN.md 가 없는 대회에 plan_campaign.py 를
# 자동 실행해 최소 캠페인 플랜을 깔아준다. 템플릿 플랜 = floor 일 뿐, 전략(winning
# lever 도출)의 대체가 아니다 — Quality Gate 원칙 유지. portfolio_tick 이 호출.
set -u
CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
ROOT="$(cd -- "$CONTROL/../.." && pwd)"
made=0; already=0; failed=0
while IFS=$'\t' read -r key dir ledger metric direction best rank1 progress status blocker next_lever; do
  case "$key" in ''|'#'*|key) continue;; esac
  case "$status" in active|scaffold|recon) ;; *) continue;; esac
  d="$CONTROL/campaigns/$key"
  [ -n "$dir" ] && [ -d "$ROOT/$dir" ] && d="$ROOT/$dir"
  if [ -f "$d/PLAN.md" ] || [ -f "$CONTROL/campaigns/$key/PLAN.md" ]; then
    already=$((already+1)); continue
  fi
  if python3 "$CONTROL/tools/plan_campaign.py" --key "$key" --name "$key" --metric "${metric:-n/a}" >/dev/null 2>&1; then
    made=$((made+1)); echo "plan created: $key"
  else
    failed=$((failed+1)); echo "plan FAILED: $key"
  fi
done < "$CONTROL/portfolio_registry.tsv"
echo "plan backfill: created=$made already=$already failed=$failed"
