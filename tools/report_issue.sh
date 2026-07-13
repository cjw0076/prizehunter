#!/usr/bin/env bash
# report_issue.sh — agent-native GitHub issue filing (secrets scrubbed).
# The control plane calls this on an unrecoverable tool bug so a failure becomes
# fixable maintainer work instead of a silent dead-end.
#
# usage: report_issue.sh --title "T" [--body "B"] [--label L] [--repo owner/name]
#   repo resolution: --repo > $PH_ISSUE_REPO > the current git origin. Needs `gh auth`.
#   Set PH_ISSUE_REPO=owner/name to route issues to the maintainer repo.
set -uo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true

title=""; body=""; label="prizehunter-auto"; repo="${PH_ISSUE_REPO:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --title) title="${2:-}"; shift 2;;
    --body)  body="${2:-}";  shift 2;;
    --label) label="${2:-}"; shift 2;;
    --repo)  repo="${2:-}";  shift 2;;
    *) shift;;
  esac
done
[ -n "$title" ] || { echo "usage: report_issue.sh --title T [--body B] [--label L] [--repo owner/name]"; exit 2; }
command -v gh >/dev/null 2>&1 || { echo "gh CLI not found — install https://github.com/cli/cli and run 'gh auth login'"; exit 3; }

# secret scrub — never post keys/tokens to a public issue
scrub() {
  sed -E 's/(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]+|Bearer[[:space:]]+[A-Za-z0-9._-]{16,}|(api[_-]?key|token|secret|password)["'"'"'=: ]+[A-Za-z0-9._-]{12,})/[REDACTED]/gI'
}
title_s="$(printf '%s' "$title" | scrub)"
body_s="$(printf '%s\n\n---\n_filed by prizehunter `report_issue.sh` (secrets scrubbed)_\n' "$body" | scrub)"

args=(); [ -n "$repo" ] && args=(--repo "$repo")
out="$(gh issue create "${args[@]}" --title "$title_s" --body "$body_s" --label "$label" 2>&1)" || \
out="$(gh issue create "${args[@]}" --title "$title_s" --body "$body_s" 2>&1)"   # retry without label if it doesn't exist
echo "$out"
