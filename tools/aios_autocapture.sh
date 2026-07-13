#!/usr/bin/env bash
# aios_autocapture.sh — closes the AIOS recording gap automatically.
# For every competition in portfolio_registry.tsv whose ledger is newer than its
# last AIOS receipt, extract the latest ledger section and record it as an asset
# receipt + AIOS packet (via the existing sanitizing tools). This is what makes
# "agents use AIOS" automatic instead of a manual step they forget.
#
# Usage: aios_autocapture.sh [--dry-run]
# Safe: read-only on ledgers; append-only receipts; secrets are blocked by
# record_asset_receipt.sh. No submissions, no compute.
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")/../../.." && pwd)"
CONTROL="$ROOT/competitions/control_tower"
REGISTRY="$CONTROL/portfolio_registry.tsv"
RECEIPTS="$CONTROL/receipts"
REC="$CONTROL/tools/record_asset_receipt.sh"
EXP="$CONTROL/tools/export_aios_packet.sh"

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

[ -f "$REGISTRY" ] || { printf 'missing registry: %s\n' "$REGISTRY" >&2; exit 2; }

newest_receipt_epoch() {
  local key="$1" f newest=0 m
  for f in "$RECEIPTS"/*"$key"*.md; do
    [ -e "$f" ] || continue
    m="$(stat -c %Y "$f" 2>/dev/null || echo 0)"
    [ "$m" -gt "$newest" ] && newest="$m"
  done
  printf '%s' "$newest"
}

# latest "## " or "### " section of a ledger, collapsed to a single sanitized line.
latest_section() {
  local file="$1" ln
  ln="$(grep -nE '^#{2,3} ' "$file" | tail -1 | cut -d: -f1 || true)"
  [ -n "$ln" ] || { tail -8 "$file"; return; }
  sed -n "${ln},\$p" "$file"
}

captured=0
skipped=0

while IFS=$'\t' read -r key dir ledger metric direction best rank1 progress status blocker next_lever; do
  case "$key" in ''|'#'*|key) continue;; esac
  [ -f "$ROOT/$ledger" ] || { skipped=$((skipped+1)); continue; }

  lm="$(stat -c %Y "$ROOT/$ledger" 2>/dev/null || echo 0)"
  rm="$(newest_receipt_epoch "$key")"
  if [ "$rm" -ne 0 ] && [ "$lm" -le "$rm" ]; then
    skipped=$((skipped+1)); continue
  fi

  section="$(latest_section "$ROOT/$ledger")"
  # collapse to one line, strip markdown bullets/heading marks, cap length
  summary="$(printf '%s' "$section" | tr '\n' ' ' | sed -E 's/#+ //g; s/[[:space:]]+/ /g; s/^ //; s/ $//' | cut -c1-700)"
  [ -n "$summary" ] || { skipped=$((skipped+1)); continue; }

  # map registry status -> receipt status vocabulary
  case "$status" in
    ceiling) rstatus="done" ;;
    active|polishing) rstatus="in_progress" ;;
    blocked) rstatus="blocked" ;;
    scaffold) rstatus="proposed" ;;
    *) rstatus="in_progress" ;;
  esac

  asset="${key}-ledger-autocapture"
  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] would capture %s: %s...\n' "$key" "$(printf '%s' "$summary" | cut -c1-90)"
    captured=$((captured+1)); continue
  fi

  r="$("$REC" --contest control_tower --asset "$asset" --type asset --status "$rstatus" \
        --summary "Auto-captured ledger delta [$key]: $summary" \
        --evidence "$ledger (mtime newer than last AIOS receipt for $key)" \
        --next "${next_lever:--}")" || { printf 'capture failed for %s\n' "$key" >&2; continue; }
        # ${next_lever:--}: bash `read` collapses consecutive tabs (IFS whitespace),
        # so an empty registry field shifts columns and leaves next_lever null
  "$EXP" --receipt "$r" >/dev/null
  printf 'captured %s -> %s\n' "$key" "$(basename "$r")"
  captured=$((captured+1))
done < "$REGISTRY"

printf 'autocapture: captured=%s skipped=%s dry_run=%s\n' "$captured" "$skipped" "$DRY"
