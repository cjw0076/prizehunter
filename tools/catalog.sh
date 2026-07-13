#!/usr/bin/env bash
# catalog.sh — pull EVERY configured source (domestic + international, curl + browser
# + keyed API) into ONE organized master catalog. Dedupes, groups by region, and
# (where prizes are known) ROI-ranks. This is the "정리해둬야지" deliverable:
# a single living index of all competitions/hackathons/공모전 worth hunting.
# Read-only on the web; writes MASTER_CATALOG.md (+ merged candidates files).
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
# cron PATH lacks miniconda — needed for playwright (render adapters) + kaggle CLI
[ -d "$HOME/miniconda3/bin" ] && export PATH="$HOME/miniconda3/bin:$PATH"
OUT="$PH_HOME/MASTER_CATALOG.md"
when="$(date '+%Y-%m-%d %H:%M %Z')"

echo "gathering sources (this fetches live; browser sources take longer)..." >&2
# 1. DACON (live API-shaped, open+paying gated)
python3 "$PH_HOME/tools/discover_dacon.py" >/dev/null 2>&1 || true
# 2. Korean + intl contest platforms (curl + browser per source)
python3 "$PH_HOME/tools/discover_contests.py" >/dev/null 2>&1 || true
# 3. AI Challenge for All umbrella (rendered, high-prize AI tracks)
python3 "$PH_HOME/tools/discover_aichallenge.py" >/dev/null 2>&1 || true
# 4. Kaggle (keyed; skips gracefully without key)
kag_note="$(bash "$PH_HOME/tools/discover_kaggle.sh" 2>&1 | head -1)"

dacon_n=$(($(wc -l < "$PH_HOME/candidates_dacon.tsv" 2>/dev/null || echo 1)-1)); dacon_n=$((dacon_n<0?0:dacon_n))
cont_n=$(($(wc -l < "$PH_HOME/candidates_contests.tsv" 2>/dev/null || echo 1)-1)); cont_n=$((cont_n<0?0:cont_n))
aic_n=$(($(grep -vc '^#' "$PH_HOME/candidates_aic.tsv" 2>/dev/null || echo 1)-1)); aic_n=$((aic_n<0?0:aic_n))
kag_n=0; [ -f "$PH_HOME/candidates_kaggle.tsv" ] && kag_n=$(($(wc -l < "$PH_HOME/candidates_kaggle.tsv")-1))

{
  echo "# Master Competition Catalog"
  echo "_generated: ${when}  ·  policy: \"돈 되는 것만\" — verify prize before committing"
  echo ""
  echo "- sources: DACON(open+paying) **$dacon_n** · contest platforms **$cont_n** · AIC **$aic_n** · Kaggle **$kag_n**"
  echo "- live: $(grep -c . "$PH_HOME"/candidates_*.tsv 2>/dev/null | awk -F: '{s+=$2}END{print s+0}') rows · kaggle: $kag_note"
  echo ""
  echo "## 🇰🇷 Domestic — DACON (open + paying, our core, API-submit)"
  echo "| cpt | competition | prize | d-day |"
  echo "|---|---|---:|---:|"
  awk -F'\t' 'NR>1{printf "| %s | %s | %s | %s |\n",$11,$1,$3,$8}' "$PH_HOME/candidates_dacon.tsv" 2>/dev/null | head -30
  echo ""
  echo "## 🇰🇷 Domestic — contest platforms (wevity/contestkorea/…)"
  echo "| platform | competition | detail |"
  echo "|---|---|---|"
  awk -F'\t' 'NR>1{printf "| %s | %s | %s |\n",$1,$3,$4}' "$PH_HOME/candidates_contests.tsv" 2>/dev/null | grep -iE 'kr|wevity|contest|devpost|.' | head -40
  echo ""
  echo "## 🇰🇷 AI Challenge for All (aichallenge4all.or.kr)"
  echo "| track | prize | schedule/status | edge |"
  echo "|---|---:|---|---|"
  awk -F'\t' 'NR>1 && $1 !~ /^#/{printf "| %s | %s | %s | %s |\n",$1,$3,$11,$10}' "$PH_HOME/candidates_aic.tsv" 2>/dev/null | head -30
  echo ""
  echo "## 🌐 International"
  if [ "$kag_n" -gt 0 ]; then
    echo "### Kaggle"; echo "| competition | prize | deadline |"; echo "|---|---:|---|"
    awk -F'\t' 'NR>1{printf "| %s | %s | %s |\n",$3,$5,$6}' "$PH_HOME/candidates_kaggle.tsv" 2>/dev/null | head -20
  else
    echo "- Kaggle: $kag_note  (add ~/.kaggle/kaggle.json to populate — our ML core, programmatic submit)"
  fi
  echo "- Devpost: browser source (configured); other intl (Zindi/AIcrowd/DrivenData): add rows to contest_sources.tsv"
  echo ""
  echo "## How to use"
  echo "- ROI-rank the money:  tools/prize_roi.py --fetch   → ROI_REPORT.md (\"돈 되는 것만\")"
  echo "- commit a target:     tools/plan_campaign.py --key K --name '...'  → run_parallel.sh --keys K"
  echo "- add a platform:      one row in contest_sources.tsv (render=curl|browser)"
  echo "- refresh this catalog: tools/catalog.sh  (cron it for a living index)"
} > "$OUT"
printf '%s\n' "$OUT"
echo "catalog: dacon=$dacon_n contests=$cont_n kaggle=$kag_n"
