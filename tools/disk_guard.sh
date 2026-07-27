#!/usr/bin/env bash
# disk_guard.sh — REFUSE to start NEW drives under disk pressure (council step-4 requirement,
# DEPLOYMENT_READINESS.md). A full disk corrupts state mid-run; the cheapest prevention is to
# not start what cannot finish. In-flight work is never killed by this guard.
#
# Trip rule (deliberate deviation from the council's raw ">85% used" — recorded, not silent):
#   HARD refuse : free space < PH_DISK_MIN_FREE_GB   (default 20 GB)
#   WARN only   : used%     > PH_DISK_WARN_PCT       (default 85)
# Rationale: on a large disk, percent alone is a false alarm (this box: 90% used but 183 GB
# free — plenty to finish any campaign). Free-GB is what actually predicts mid-run corruption.
# Operators who want the strict council rule: PH_DISK_MAX_PCT=85 makes percent a hard trip too.
#
# Usage (at the TOP of any tool that starts a new drive):
#   bash "$T/disk_guard.sh" || exit 3          # prints its own refusal message
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
MIN_GB="${PH_DISK_MIN_FREE_GB:-20}"
WARN_PCT="${PH_DISK_WARN_PCT:-85}"
MAX_PCT="${PH_DISK_MAX_PCT:-0}"   # 0 = percent is warn-only (default)

free_gb="$(df -PBG "$CT" 2>/dev/null | awk 'NR==2{gsub("G","",$4); print $4+0}')"
used_pct="$(df -P "$CT" 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5+0}')"

# a guard that cannot measure must say so and fail CLOSED for new work (silence is not a finding)
if [ -z "$free_gb" ] || [ -z "$used_pct" ]; then
  echo "⛔ DISK GUARD: cannot measure disk usage for $CT — refusing to start a new drive (fail-closed)." >&2
  exit 3
fi

if [ "$free_gb" -lt "$MIN_GB" ]; then
  echo "⛔ DISK GUARD: ${free_gb}GB free < ${MIN_GB}GB floor (${used_pct}% used) — NEW drive refused." >&2
  echo "   Free space or raise PH_DISK_MIN_FREE_GB deliberately. In-flight work is unaffected." >&2
  exit 3
fi
if [ "$MAX_PCT" -gt 0 ] && [ "$used_pct" -gt "$MAX_PCT" ]; then
  echo "⛔ DISK GUARD: ${used_pct}% used > PH_DISK_MAX_PCT=${MAX_PCT} — NEW drive refused (strict mode)." >&2
  exit 3
fi
if [ "$used_pct" -gt "$WARN_PCT" ]; then
  echo "⚠ disk ${used_pct}% used (${free_gb}GB free) — above ${WARN_PCT}% warn line; plan cleanup." >&2
fi
exit 0
