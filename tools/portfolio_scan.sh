#!/usr/bin/env bash
# portfolio_scan.sh — single unified view of every competition in this repo.
# Reads control_tower/portfolio_registry.tsv, computes gap-to-rank-1 and AIOS
# recording freshness (is the ledger newer than the last AIOS receipt for it?),
# and renders control_tower/PORTFOLIO_STATUS.md.
# Read-only except for the one status file it writes. No secrets, no submissions.
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")/../../.." && pwd)"
CONTROL="$ROOT/competitions/control_tower"
REGISTRY="$CONTROL/portfolio_registry.tsv"
RECEIPTS="$CONTROL/receipts"
OUT="$CONTROL/PORTFOLIO_STATUS.md"

[ -f "$REGISTRY" ] || { printf 'missing registry: %s\n' "$REGISTRY" >&2; exit 2; }

now_human="$(date '+%Y-%m-%d %H:%M:%S %Z')"

# newest mtime (epoch) of any receipt file whose name contains the key; 0 if none.
newest_receipt_epoch() {
  local key="$1" f newest=0 m
  for f in "$RECEIPTS"/*"$key"*.md; do
    [ -e "$f" ] || continue
    m="$(stat -c %Y "$f" 2>/dev/null || echo 0)"
    [ "$m" -gt "$newest" ] && newest="$m"
  done
  printf '%s' "$newest"
}

stale_rows=0
unrecorded_list=""
table=""

while IFS=$'\t' read -r key dir ledger metric direction best rank1 progress status blocker next_lever; do
  case "$key" in ''|'#'*|key) continue;; esac

  # gap to rank-1
  gap="-"
  if [ "$direction" = "max" ] && [ "$best" != "-" ] && [ "$rank1" != "-" ]; then
    gap="$(awk -v b="$best" -v r="$rank1" 'BEGIN{printf "%.4f", r-b}')"
  elif [ "$direction" = "min" ] && [ "$best" != "-" ] && [ "$rank1" != "-" ]; then
    gap="$(awk -v b="$best" -v r="$rank1" 'BEGIN{printf "%.4f", b-r}')"
  fi

  # AIOS freshness: ledger mtime vs newest receipt for this key
  aios="—"
  if [ -f "$ROOT/$ledger" ]; then
    lm="$(stat -c %Y "$ROOT/$ledger" 2>/dev/null || echo 0)"
    rm="$(newest_receipt_epoch "$key")"
    if [ "$rm" -eq 0 ]; then
      aios="🔴 NEVER"
      stale_rows=$((stale_rows+1)); unrecorded_list="$unrecorded_list $key"
    elif [ "$lm" -gt "$rm" ]; then
      age_h="$(awk -v a="$lm" -v b="$rm" 'BEGIN{printf "%.0f", (a-b)/3600}')"
      aios="🟠 STALE (+${age_h}h)"
      stale_rows=$((stale_rows+1)); unrecorded_list="$unrecorded_list $key"
    else
      aios="🟢 fresh"
    fi
  else
    aios="? no-ledger"
  fi

  table="${table}| ${key} | ${progress} | ${status} | ${best} | ${rank1} | ${gap} | ${aios} | ${blocker} | ${next_lever} |
"
done < "$REGISTRY"

action_block=""
if [ "$stale_rows" -gt 0 ]; then
  action_block="## ⚠️ AIOS recording action needed

These competitions have work not yet captured as AIOS receipts:$unrecorded_list

Run: \`./control_tower/tools/aios_autocapture.sh\` to record ledger deltas as receipts + AIOS packets.
"
fi

cat > "$OUT" <<EOF
# Portfolio Status — Unified Leaderboard (all competitions)

- generated: $now_human
- source: control_tower/portfolio_registry.tsv (single source of truth)
- AIOS recording gaps (ledger newer than last receipt, or never recorded): **$stale_rows**

## Leaderboard

| Competition | Prog% | Status | Best | Rank-1 | Gap→#1 | AIOS rec | Blocker | Next lever |
|---|---:|---|---|---|---:|---|---|---|
$table
$action_block
## Legend

- **Gap→#1**: distance to public rank-1 in the metric direction (lower gap = closer; "-" = no numeric metric).
- **AIOS rec**: 🟢 ledger work is recorded; 🟠 STALE = work happened after last receipt; 🔴 NEVER = no receipt yet.
- **FOUNDER:** blockers need operator credentials/sessions; agents correctly stop and wait.
EOF

printf '%s\n' "$OUT"
printf 'aios_recording_gaps=%s\n' "$stale_rows"
