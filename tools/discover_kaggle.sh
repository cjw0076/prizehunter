#!/usr/bin/env bash
# discover_kaggle.sh — keyed discovery adapter for Kaggle (our ML core).
# Kaggle's web listing is JS-rendered (not scrapeable); use the official API.
# Gated on credentials: needs `pip install kaggle` + ~/.kaggle/kaggle.json.
# When present, lists prize competitions sorted by reward into the candidate schema.
# Submission is also programmatic (kaggle competitions submit) -> full auto loop.
#
# Usage: discover_kaggle.sh [--out candidates_kaggle.tsv] [--sort prize]
set -euo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
OUT="${2:-$PH_HOME/candidates_kaggle.tsv}"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "SKIP kaggle: CLI not installed. Enable with:" >&2
  echo "  pip install kaggle && mkdir -p ~/.kaggle && cp <kaggle.json> ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json" >&2
  exit 9
fi
# accept either legacy kaggle.json or the newer access_token (KAGGLE_API_TOKEN)
if [ -f "$HOME/.kaggle/access_token" ] && [ -z "${KAGGLE_API_TOKEN:-}" ]; then
  export KAGGLE_API_TOKEN="$(cat "$HOME/.kaggle/access_token")"
fi
if [ ! -f "$HOME/.kaggle/kaggle.json" ] && [ -z "${KAGGLE_KEY:-}" ] && [ -z "${KAGGLE_API_TOKEN:-}" ]; then
  echo "SKIP kaggle: no ~/.kaggle/kaggle.json, access_token, or KAGGLE_API_TOKEN. Add one to enable." >&2
  exit 9
fi

# pull reward-bearing competitions (CSV), map into the contest candidate schema
cols="platform\tid\tname\turl\tprize\tdeadline\tcategory"
kaggle competitions list --csv -s prize 2>/dev/null | python3 -c '
import csv,sys
w=open("'"$OUT"'","w"); w.write("platform\tid\tname\turl\tprize\tdeadline\tcategory\n")
r=csv.DictReader(sys.stdin)
for row in r:
    ref=row.get("ref","");
    if not ref: continue
    slug=ref.rstrip("/").split("/")[-1]
    w.write("\t".join(["kaggle",slug,slug,"https://www.kaggle.com/competitions/"+slug,row.get("reward",""),row.get("deadline",""),row.get("category","ml")])+"\n")
w.close()'  
n=$(($(wc -l < "$OUT") - 1))
echo "$OUT"
echo "discovered=$n kaggle competitions (via API). Submission also programmatic: kaggle competitions submit."
