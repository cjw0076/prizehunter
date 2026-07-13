#!/usr/bin/env bash
# strategist_brief.sh — the big-picture war-room view for the Strategist persona.
# Assembles the WHOLE board into one brief so a conductor agent can decide
# allocation (commit / drop / reallocate), spot ROI shifts and deadline risk, and
# direct the per-competition worker windows. Read-only; writes STRATEGIST_BRIEF.md.
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
REG="$PH_HOME/portfolio_registry.tsv"
OUT="$PH_HOME/STRATEGIST_BRIEF.md"
when="$(date '+%Y-%m-%d %H:%M:%S %Z')"

# refresh inputs (best-effort)
bash "$PH_HOME/tools/portfolio_scan.sh" >/dev/null 2>&1 || true

active=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"&&$9=="active"{n++}END{print n+0}' "$REG")
blocked=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"&&$9=="blocked"{n++}END{print n+0}' "$REG")
ceiling=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"&&$9=="ceiling"{n++}END{print n+0}' "$REG")
total=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"{n++}END{print n+0}' "$REG")
recv=$(ls "$PH_HOME/receipts"/*.md 2>/dev/null | wc -l | tr -d ' ')

{
  echo "# Strategist Brief — portfolio war room"
  echo "_generated: ${when}  ·  read PERSONA: capabilities/personas/strategist.md"
  echo ""
  echo "## Board at a glance"
  echo "- competitions: **$total** (active $active · blocked $blocked · ceiling $ceiling)"
  echo "- audit depth: $recv receipts  ·  flywheel: $([ -n "${MEMOS_ROOT:-}" ] && echo "MemoryOS ON" || echo "off")"
  echo ""
  echo "## Portfolio (gap-to-#1 + next lever)"
  if [ -f "$PH_HOME/PORTFOLIO_STATUS.md" ]; then sed -n '/^| Competition/,/^$/p' "$PH_HOME/PORTFOLIO_STATUS.md" | head -20; fi
  echo ""
  echo "## 💰 Top ROI opportunities (commit candidates — \"돈 되는 것만\")"
  if [ -f "$PH_HOME/ROI_REPORT.md" ]; then grep -E '^\| ' "$PH_HOME/ROI_REPORT.md" | head -8; else echo "_run prize_roi.py --fetch_"; fi
  echo ""
  echo "## ⏰ Deadline radar (newly discovered, by D-day)"
  if [ -f "$PH_HOME/DISCOVERY_REPORT.md" ]; then grep -oE 'D- [0-9]+ .*' "$PH_HOME/DISCOVERY_REPORT.md" 2>/dev/null | sort -t- -k2 -n | head -6 || echo "_run discover_all.sh_"; else echo "_run discover_all.sh_"; fi
  echo ""
  echo "## 🎛 Strategist decisions to make this cycle"
  echo "1. **Commit/Drop**: which active campaigns keep effort, which drop (low ROI / stalled / ceiling reached)?"
  echo "2. **Reallocate**: shift worker windows toward highest EV; open new windows for top untried ROI picks."
  echo "3. **Deadline triage**: anything closing soon that must jump the queue?"
  echo "4. **Gate watch**: external-submit / new-domain / spend decisions → escalate to founder."
  echo "5. **Flywheel**: approve high-value MemoryOS drafts so workers inherit fresh expertise."
  echo ""
  echo "## Levers (act, don't just observe)"
  echo "- open/realloc workers:  tools/run_parallel.sh --keys K1,K2 [--execute]"
  echo "- commit a new pick:     tools/plan_campaign.py --key K --name '...'  then add to portfolio_registry.tsv"
  echo "- drop:                  set status=dropped in portfolio_registry.tsv (+ note why)"
  echo "- record the call:       tools/record_asset_receipt.sh --type decision --asset 'strategy-...'"
} > "$OUT"
printf '%s\n' "$OUT"
echo "board: $total comps ($active active / $blocked blocked / $ceiling ceiling)"
