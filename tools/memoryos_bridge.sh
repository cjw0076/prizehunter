#!/usr/bin/env bash
# memoryos_bridge.sh — the tacit->explicit knowledge flywheel.
# DEPOSIT: push the prize machine's distilled learnings (asset receipts, corpus)
#          into MemoryOS as DRAFT memory (draft-first; a human approves later).
#          Runs a privacy redaction scan before writing (privacy invariant).
# RECALL : pull accumulated expertise for a new competition's domain and emit a
#          priming block to inject into the agent's task prompt — so each new
#          campaign starts as an "expert". This is what makes MemoryOS/AIOS
#          structurally indispensable: the business runs on accumulated memory.
#
# Usage:
#   memoryos_bridge.sh recall  --task "AI data competition honest CV"
#   memoryos_bridge.sh deposit [--latest N | FILE...]
#   memoryos_bridge.sh status
set -euo pipefail
CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$CONTROL/config.sh" 2>/dev/null || true
MEMOS="${MEMOS_ROOT:-}"
RECEIPTS="$CONTROL/receipts"
# bare `python` doesn't exist on a cron PATH — prefer python3, overridable per install
mos() { ( cd "$MEMOS" && timeout 180 "${MEMOS_PYTHON:-python3}" -m memoryos --root . "$@" ); }
HERE="$(cd -- "$(dirname "$0")" && pwd)"

[ -d "$MEMOS" ] || { echo "MemoryOS not found at $MEMOS (set MEMOS_ROOT)"; exit 2; }
cmd="${1:-}"; shift || true

case "$cmd" in
  recall)
    task=""; [ "${1:-}" = "--task" ] && task="$2"
    [ -n "$task" ] || { echo "need --task" >&2; exit 2; }
    echo "# Accumulated expertise (MemoryOS recall) — task: $task"
    echo "# inject this as priming so the agent starts as an expert."
    mos context build --task "$task" --json 2>/dev/null \
      | python3 "$HERE/_recall_fmt.py" || echo "(recall failed)"
    ;;
  deposit)
    files=()
    if [ "${1:-}" = "--latest" ]; then
      n="${2:-5}"; while IFS= read -r f; do files+=("$f"); done < <(ls -t "$RECEIPTS"/*.md 2>/dev/null | head -"$n")
    else files=("$@"); fi
    [ "${#files[@]}" -gt 0 ] || { echo "no files to deposit" >&2; exit 2; }
    # absolutize (mos cd's into MEMOS, so relative paths would break)
    abs=(); for f in "${files[@]}"; do abs+=("$(readlink -f "$f")"); done; files=("${abs[@]}")
    echo "== privacy redaction scan (must pass before deposit) =="
    if ! mos import --redaction-preview "${files[@]}" 2>&1 | tail -5; then
      echo "redaction scan flagged content — NOT importing. Review first." >&2; exit 3; fi
    echo "== importing as DRAFT memory (draft-first; approve later via 'drafts approve') =="
    mos import "${files[@]}" 2>&1 | tail -8
    echo "deposited ${#files[@]} file(s) as drafts. Review: (cd $MEMOS && python -m memoryos drafts list)"
    ;;
  status)
    echo "MemoryOS: $MEMOS"; mos stats 2>&1 | head -15
    echo "--- pending drafts ---"; mos drafts list 2>&1 | head -8 ;;
  *) sed -n '2,16p' "$0"; exit 0;;
esac
