#!/usr/bin/env bash
# memory_router.sh — retrieves past competition patterns for a given domain/metric
# Usage: ./memory_router.sh [--domain DOMAIN] [--metric METRIC] [--key KEY]
# Output: $CT/context/prior_art.md (injected into RECON/BUILD prompts)
# Run automatically at RECON stage entry.

set -euo pipefail
CT="$(cd "$(dirname "$0")/.." && pwd)"
CONTEXT_DIR="$CT/context"
mkdir -p "$CONTEXT_DIR"

DOMAIN=""
METRIC=""
KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --metric) METRIC="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    *) shift ;;
  esac
done

OUT="$CONTEXT_DIR/prior_art.md"
{
  echo "# Prior Art — $(date '+%Y-%m-%d %H:%M KST')"
  echo "# domain=$DOMAIN metric=$METRIC key=$KEY"
  echo ""

  # 1. Mine session corpus for domain patterns
  if [[ -f "$CT/session_corpus/CORPUS_REPORT.md" ]]; then
    echo "## Session Corpus Patterns"
    if [[ -n "$DOMAIN" ]]; then
      grep -i "$DOMAIN" "$CT/session_corpus/CORPUS_REPORT.md" | head -20 || true
    fi
    if [[ -n "$METRIC" ]]; then
      grep -i "$METRIC" "$CT/session_corpus/CORPUS_REPORT.md" | head -10 || true
    fi
    echo ""
  fi

  # 2. Portfolio registry — similar domain past results
  echo "## Past Competition Results (similar domain)"
  if [[ -n "$DOMAIN" ]]; then
    grep -i "$DOMAIN" "$CT/portfolio_registry.tsv" 2>/dev/null || true
  fi
  echo ""

  # 3. Per-campaign worklogs — grep for domain keywords
  echo "## Relevant Campaign Patterns"
  for wl in "$CT/campaigns/"*/WORKLOG.md "$CT/campaigns/"*/AGENT_WORKLOG.md; do
    [[ -f "$wl" ]] || continue
    hits=""
    [[ -n "$DOMAIN" ]] && hits=$(grep -i "$DOMAIN" "$wl" 2>/dev/null | head -5)
    [[ -n "$METRIC" ]] && hits="$hits"$'\n'"$(grep -i "$METRIC" "$wl" 2>/dev/null | head -3)"
    if [[ -n "${hits// /}" ]]; then
      echo "### $(basename "$(dirname "$wl")")"
      echo "$hits"
      echo ""
    fi
  done

  # 4. run mine_sessions.py if domain given
  if [[ -n "$DOMAIN" ]] && [[ -f "$CT/tools/mine_sessions.py" ]]; then
    echo "## Mined Session Insights"
    python3 "$CT/tools/mine_sessions.py" --filter "$DOMAIN" 2>/dev/null | head -40 || true
    echo ""
  fi

} > "$OUT"

echo "prior_art.md written → $OUT ($(wc -l < "$OUT") lines)"
cat "$OUT" | head -30
