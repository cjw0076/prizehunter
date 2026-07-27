#!/usr/bin/env bash
# drive_board.sh — the SENSOR half of the continuous prize loop.
# For every Kaggle competition we're entered in, fetch our best public score vs the
# current #1, compute the gap, and append a timestamped row to .runs/drive_board.tsv.
# Deterministic + safe (no submissions). The driver loop reads this to know where to push.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
PY="$HOME/miniconda3/bin/python"
KAGGLE="$HOME/miniconda3/bin/kaggle"
OUT="$CT/.runs/drive_board.tsv"
mkdir -p "$CT/.runs"
[ -f "$OUT" ] || echo -e "ts\tcomp\tour_best\trank1\tgap\tstatus" > "$OUT"

# Kaggle competitions we drive (CSV/agent submittable). Extend as we enter more.
COMPS="playground-series-s6e7 autonomous-agent-prediction-beta rogii-wellbore-geology-prediction"
TS="$(date -u +%Y-%m-%dT%H:%MZ)"

for c in $COMPS; do
  # metric direction: min = lower better (RMSE/MSE/logloss), max = higher better.
  # Kaggle slug ≠ registry key, so infer from the slug (extend as new comps are added).
  case "$c" in
    *rogii*|*mse*|*rmse*|*logloss*|*error*) dir="min" ;;
    *) dir="max" ;;
  esac
  sortflag="-gr"; [ "$dir" = "min" ] && sortflag="-g"   # min → best is the lowest score
  # our best public score from submissions (any decimal in the publicScore column)
  ours="$($KAGGLE competitions submissions -c "$c" -v 2>/dev/null | tr -d '\r' | awk -F',' 'NR>1 {for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.[0-9]+$/){print $i; break}}' | sort $sortflag | head -1)"
  # leaderboard #1 (strip CRLF, skip token+header; first data row IS #1 regardless of direction)
  top="$($KAGGLE competitions leaderboard -c "$c" -s --csv 2>/dev/null | tr -d '\r' | awk -F',' 'NR>1 && $NF ~ /^[0-9]+\.[0-9]+$/ {print $NF; exit}')"
  ours="${ours:-NA}"; top="${top:-NA}"
  gap="NA"
  if [ "$ours" != "NA" ] && [ "$top" != "NA" ]; then
    gap="$($PY -c "print(round(abs(float('$top')-float('$ours')),5))" 2>/dev/null || echo NA)"
  fi
  st="tracking"
  echo -e "$TS\t$c\t$ours\t$top\t$gap\t$st" >> "$OUT"
done

# ── NUMERAI leg (not Kaggle: public GraphQL, no auth needed for the leaderboard) ─────────────────────────────
# numerai-main was invisible to this sensor because the loop only knows Kaggle slugs. Its rank-1 target must be
# refreshed from the live board or it rots into the stale-target defect audit_targets.py exists to catch.
# IMPORTANT: gap is written NA on purpose. Our best is an OFFLINE payout proxy over validation eras; the board's
# numbers are LIVE reputation over the platform's own window. Subtracting them would manufacture a ghost gap —
# the exact error that produced a phantom 1.065 on rogii. Same axis or no number.
if command -v curl >/dev/null 2>&1; then
  nq='{"query":"query { v2Leaderboard(limit: 1) { username rank corr20V2Rep mmcRep } }"}'
  nres="$(timeout 60 curl -s -X POST https://api-tournament.numer.ai/ -H "Content-Type: application/json" -d "$nq" 2>/dev/null)"
  ntop="$(printf '%s' "$nres" | "$PY" -c "
import json,sys
try:
    r=json.load(sys.stdin)['data']['v2Leaderboard'][0]
    c=r.get('corr20V2Rep') or 0; m=r.get('mmcRep') or 0
    print('%.5f\t%s\t%.5f\t%.5f' % (0.75*c+2.25*m, r['username'], c, m))
except Exception: pass" 2>/dev/null)"
  if [ -n "$ntop" ]; then
    top1="$(printf '%s' "$ntop" | cut -f1)"; who="$(printf '%s' "$ntop" | cut -f2)"
    ours="$(awk -F'\t' '$1=="numerai-main"{print $6}' "$CT/portfolio_registry.tsv" 2>/dev/null | head -1)"
    echo -e "$TS\tnumerai-main\t${ours:-NA}\t$top1\tNA\taxis-mismatch(offline-proxy-vs-live-rep;#1=$who)" >> "$OUT"
    if [ "${1:-}" = "--sync-rank1" ]; then
      "$PY" - "$CT/portfolio_registry.tsv" "$top1" <<'PYS'
import sys
path, new = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().split("\n")
for i, l in enumerate(lines):
    f = l.split("\t")
    if f and f[0] == "numerai-main" and len(f) > 6 and f[6] != new:
        old = f[6]; f[6] = new; lines[i] = "\t".join(f)
        open(path, "w", encoding="utf-8").write("\n".join(lines))
        print("  rank1 refreshed: %s -> %s (live leaderboard #1, same payout formula)" % (old, new))
        break
else:
    print("  rank1 unchanged")
PYS
    else
      echo "  numerai live #1 payout-proxy=$top1 ($who) — run with --sync-rank1 to write it into the registry"
    fi
  fi
fi

# keep the board readable: last 200 rows
tail -n 200 "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
echo "drive_board updated $TS"
tail -n "$(echo "$COMPS" | wc -w)" "$OUT"
