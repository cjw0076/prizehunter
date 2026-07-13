#!/usr/bin/env bash
# config.sh — single config for the Prize Hunter package. Source this; never hardcode paths.
#   source "$(dirname "$0")/../config.sh"   (from a tool in tools/)
# All values auto-detect with sane defaults and can be overridden by env or
# control_tower/config.local.sh (gitignored, per-install).

# PH_HOME = the control_tower package dir (this file's dir). Portable: works wherever copied.
PH_HOME="${PH_HOME:-$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
# PH_REPO = host repo root. Robust across layouts:
#   git toplevel if available; else nested (<repo>/competitions/control_tower -> ../..);
#   else standalone (control_tower == repo root -> ..).
if [ -z "${PH_REPO:-}" ]; then
  # nested package convention wins (<repo>/competitions/control_tower) even when the
  # host sits inside a larger git repo; else git toplevel (standalone repo); else parent.
  if [ "$(basename "$(dirname "$PH_HOME")")" = "competitions" ]; then PH_REPO="$(cd -- "$PH_HOME/../.." && pwd)";
  elif PH_REPO="$(cd "$PH_HOME" && git rev-parse --show-toplevel 2>/dev/null)"; then :;
  else PH_REPO="$(cd -- "$PH_HOME/.." && pwd)"; fi
fi

# Instance data dirs (created by install.sh; NOT shipped with the package)
PH_RECEIPTS="${PH_RECEIPTS:-$PH_HOME/receipts}"
PH_OUTBOX="${PH_OUTBOX:-$PH_HOME/aios_outbox}"
PH_CAMPAIGNS="${PH_CAMPAIGNS:-$PH_HOME/campaigns}"

# MemoryOS (knowledge flywheel). Optional: empty = flywheel disabled, machine still runs.
# Auto-detect a sibling AIOS checkout; override in config.local.sh or via env.
if [ -z "${MEMOS_ROOT:-}" ]; then
  for c in "$HOME/memoryOS" "$PH_REPO/memoryOS" "$PH_REPO/../memoryOS"; do
    [ -d "$c" ] && { MEMOS_ROOT="$(cd "$c" && pwd)"; break; }
  done
fi
export MEMOS_ROOT="${MEMOS_ROOT:-}"

# Org/identity stamped into receipts (was hardcoded). Override per install.
PH_ORG="${PH_ORG:-$(basename "$PH_REPO")}"

# Per-install overrides (gitignored)
[ -f "$PH_HOME/config.local.sh" ] && . "$PH_HOME/config.local.sh"

export PH_HOME PH_REPO PH_RECEIPTS PH_OUTBOX PH_CAMPAIGNS PH_ORG
