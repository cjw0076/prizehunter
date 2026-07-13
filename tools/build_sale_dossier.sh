#!/usr/bin/env bash
# build_sale_dossier.sh — assembles the buyer-facing exit dossier from live state.
# Concatenates the due-diligence one-pager, the unified portfolio leaderboard, the
# prize P&L, and an auto-counted audit-trail depth. Run before listing the asset.
set -euo pipefail

CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
EXIT_DIR="$CONTROL/EXIT"
OUT="$EXIT_DIR/SALE_DOSSIER.md"

# refresh the leaderboard first
"$CONTROL/tools/portfolio_scan.sh" >/dev/null 2>&1 || true

receipt_n="$(find "$CONTROL/receipts" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
packet_n="$(find "$CONTROL/aios_outbox" -maxdepth 1 -name '*.aios.md' 2>/dev/null | wc -l | tr -d ' ')"
when="$(date '+%Y-%m-%d %H:%M:%S %Z')"

{
  printf '# Sale Dossier — generated %s\n\n' "$when"
  printf '%s\n\n' "- audit trail depth: **$receipt_n receipts**, **$packet_n AIOS packets**"
  printf '%s\n\n' '---'
  cat "$EXIT_DIR/DUE_DILIGENCE.md"
  printf '\n\n---\n\n## Live Portfolio\n\n'
  cat "$CONTROL/PORTFOLIO_STATUS.md"
  printf '\n\n---\n\n## Prize P&L (raw)\n\n```\n'
  cat "$EXIT_DIR/PRIZE_LEDGER.tsv"
  printf '```\n'
} > "$OUT"

printf '%s\n' "$OUT"
printf 'receipts=%s packets=%s\n' "$receipt_n" "$packet_n"
