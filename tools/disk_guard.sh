#!/usr/bin/env bash
# disk_guard.sh — REFUSE to start NEW drives under disk pressure (council step-4 requirement,
# DEPLOYMENT_READINESS.md). A full disk corrupts state mid-run; the cheapest prevention is to
# not start what cannot finish. In-flight work and bookkeeping are never killed by this guard.
#
# Trip rule (deliberate deviation from the council's raw ">85% used" — recorded, not silent):
#   HARD refuse : free space < PH_DISK_MIN_FREE_GB   (default 20 GB, compared in KiB — no
#                 unit rounding: df -BG rounds 19.1G up to 20G, which would leak past the floor)
#   WARN only   : used%     > PH_DISK_WARN_PCT       (default 85)
# Rationale: on a large disk, percent alone is a false alarm (this box: 90% used but ~180 GB
# free — plenty to finish any campaign). Free space is what predicts mid-run corruption.
# Operators who want the strict council rule: PH_DISK_MAX_PCT=85 makes percent a hard trip too.
#
# Checks the ENGINE filesystem and, when different, the PH_RUNS filesystem and any extra
# target paths given as arguments — work can write to a mount other than the repo's.
#
# Usage (at the TOP of any tool that starts a new drive):
#   bash "$T/disk_guard.sh" [extra_target_dir ...] || exit 3
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"

# config must be sane integers; a malformed threshold silently becoming 0 would fail OPEN
int_or_die(){ case "$1" in ''|*[!0-9]*) echo "⛔ DISK GUARD: $2='$1' is not a non-negative integer — refusing (fail-closed)." >&2; exit 3;; esac; }
MIN_GB="${PH_DISK_MIN_FREE_GB:-20}";  int_or_die "$MIN_GB"  PH_DISK_MIN_FREE_GB
WARN_PCT="${PH_DISK_WARN_PCT:-85}";   int_or_die "$WARN_PCT" PH_DISK_WARN_PCT
MAX_PCT="${PH_DISK_MAX_PCT:-0}";      int_or_die "$MAX_PCT"  PH_DISK_MAX_PCT
MIN_KB=$(( MIN_GB * 1024 * 1024 ))

check_target(){
  local target="$1" free_kb used_pct
  free_kb="$(df -Pk "$target" 2>/dev/null | awk 'NR==2{print $4+0}')"
  used_pct="$(df -Pk "$target" 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5+0}')"
  # a guard that cannot measure must say so and fail CLOSED for new work (silence is not a finding)
  if [ -z "$free_kb" ] || [ -z "$used_pct" ]; then
    echo "⛔ DISK GUARD: cannot measure disk usage for $target — refusing to start a new drive (fail-closed)." >&2
    return 3
  fi
  local free_gb=$(( free_kb / 1024 / 1024 ))
  if [ "$free_kb" -lt "$MIN_KB" ]; then
    echo "⛔ DISK GUARD [$target]: ${free_gb}GB free < ${MIN_GB}GB floor (${used_pct}% used) — NEW drive refused." >&2
    echo "   Free space or raise PH_DISK_MIN_FREE_GB deliberately. In-flight work is unaffected." >&2
    return 3
  fi
  if [ "$MAX_PCT" -gt 0 ] && [ "$used_pct" -gt "$MAX_PCT" ]; then
    echo "⛔ DISK GUARD [$target]: ${used_pct}% used > PH_DISK_MAX_PCT=${MAX_PCT} — NEW drive refused (strict mode)." >&2
    return 3
  fi
  if [ "$used_pct" -gt "$WARN_PCT" ]; then
    echo "⚠ disk [$target] ${used_pct}% used (${free_gb}GB free) — above ${WARN_PCT}% warn line; plan cleanup." >&2
  fi
  return 0
}

# distinct filesystems only: CT always; PH_RUNS and extra args when they resolve elsewhere
seen=""
for target in "$CT" "${PH_RUNS:-}" "$@"; do
  [ -n "$target" ] && [ -d "$target" ] || continue
  fsid="$(df -Pk "$target" 2>/dev/null | awk 'NR==2{print $1}')"
  case " $seen " in *" $fsid "*) continue;; esac
  seen="$seen $fsid"
  check_target "$target" || exit 3
done
exit 0
