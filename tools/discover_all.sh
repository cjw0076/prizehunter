#!/usr/bin/env bash
# discover_all.sh — stage-1 runner: fetch live competitions from each configured
# platform adapter, triage them, write a dated discovery report. Read-only on the
# web; writes only the candidates files + report. Pluggable: add an adapter call
# per platform. Platforms needing API keys are skipped with a logged note (no
# silent gaps). Cron-friendly (no auto-entry; triage recommends, human/loop decides).
set -euo pipefail

CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
# cron PATH lacks miniconda — needed for playwright (render adapters) + kaggle CLI
[ -d "$HOME/miniconda3/bin" ] && export PATH="$HOME/miniconda3/bin:$PATH"
REPORT="$CONTROL/DISCOVERY_REPORT.md"
when="$(date '+%Y-%m-%d %H:%M:%S %Z')"

{
  printf '# Discovery Report — %s\n\n' "$when"
  printf 'Stage-1 of the autonomous prize machine. Triage recommends; entry is decided by the loop/operator.\n\n'

  printf '## DACON (live, no auth) — full discover->submit automatable\n\n```\n'
  if python3 "$CONTROL/tools/discover_dacon.py" --out "$CONTROL/candidates_dacon.tsv" >/dev/null 2>&1; then
    python3 "$CONTROL/tools/triage_competition.py" --candidates "$CONTROL/candidates_dacon.tsv" 2>&1
  else
    printf 'DACON discovery failed (page structure changed or network down)\n'
  fi
  printf '```\n\n'

  printf '## AI Challenge for All (live render, umbrella AI competitions)\n\n```\n'
  if python3 "$CONTROL/tools/discover_aichallenge.py" --out "$CONTROL/candidates_aic.tsv" 2>&1; then
    printf 'AIC discovery refreshed.\n'
  else
    printf 'AIC discovery failed (render/page structure changed or network down)\n'
  fi
  printf '```\n\n'

  printf '## Generic contest platforms (wevity / contestkorea / devpost — scrape)\n\n```\n'
  # No --platform => aggregate ALL rows of contest_sources.tsv into candidates_contests.tsv
  # (per-platform calls overwrite the file; the aggregating call is the correct pipeline path).
  if python3 "$CONTROL/tools/discover_contests.py" --max 40 2>&1; then
    printf 'generic contest discovery refreshed.\n'
  else
    printf 'generic contest discovery failed (page structure changed or network down)\n'
  fi
  printf '```\n\n'

  printf '## Skipped / keyed adapters (no silent gaps)\n\n'
  printf "### Kaggle (keyed — our ML core)\n\`\`\`\n"
  bash "$CONTROL/tools/discover_kaggle.sh" 2>&1 | head -3 || true
  printf "\`\`\`\n\n"
  printf -- '%s\n' "- Kaggle/Numerai: keyed adapters; add API key -> full discover->submit auto."
  printf -- '%s\n' "- Devpost/AIcrowd/Zindi: scrape-only; submission human-gated (forms/video)."
  printf -- '%s\n' "- culture.go.kr/qhackathon/kaggle-web: JS-rendered; need headless-render adapter or API."

  printf '\n## Next Pool (cross-domain, 120%% quality policy)\n\n```\n'
  python3 "$CONTROL/tools/build_next_pool.py" 2>&1
  printf '```\n'
} > "$REPORT"

printf '%s\n' "$REPORT"
