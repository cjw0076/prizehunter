#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")/../.." && pwd)"
CONTROL="$ROOT/control_tower"
RECEIPTS="$CONTROL/receipts"
OUTBOX="$CONTROL/aios_outbox"
MYWORLD_LEDGER="${AIOS_LEDGER:-${MEMOS_ROOT:-}/../myworld/docs/AIOS_AGENT_LEDGER.md}"

receipt=""
append_ledger=0

usage() {
  cat <<'EOF'
Usage:
  export_aios_packet.sh [--receipt PATH] [--append-myworld-ledger]

Creates an AIOS-ready packet from a sanitized local receipt. By default it only
writes competitions/control_tower/aios_outbox/*.md. With --append-myworld-ledger,
it appends a short cross-repo summary to MyWorld's AIOS agent ledger.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --receipt)
      receipt="${2:?missing --receipt value}"
      shift 2
      ;;
    --append-myworld-ledger)
      append_ledger=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$receipt" ]; then
  receipt="$(find "$RECEIPTS" -maxdepth 1 -type f -name '*.md' | sort | tail -n 1)"
fi

[ -n "$receipt" ] || { printf 'no receipt found\n' >&2; exit 2; }
case "$receipt" in
  /*) ;;
  *) receipt="$(pwd)/$receipt" ;;
esac
[ -f "$receipt" ] || { printf 'receipt not found: %s\n' "$receipt" >&2; exit 2; }

rel_to_workspace() {
  case "$1" in
    "$ROOT"/*)
      printf 'competitions/%s' "${1#"$ROOT"/}"
      ;;
    *)
      printf '%s' "$1"
      ;;
  esac
}

if grep -Eq '(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)[A-Z0-9_]*=)' "$receipt"; then
  printf 'refusing to export receipt containing secret-looking value\n' >&2
  exit 3
fi

mkdir -p "$OUTBOX"

base="$(basename "$receipt" .md)"
packet="$OUTBOX/${base}.aios.md"
human_when="$(date '+%Y-%m-%d %H:%M:%S %Z')"
title="$(sed -n '1s/^# Asset Receipt: //p' "$receipt")"
summary="$(sed -n 's/^- summary: //p' "$receipt" | head -n 1)"
evidence="$(sed -n 's/^- evidence: //p' "$receipt" | head -n 1)"
next="$(sed -n 's/^- next: //p' "$receipt" | head -n 1)"
status="$(sed -n 's/^- status: //p' "$receipt" | head -n 1)"
type="$(sed -n 's/^- type: //p' "$receipt" | head -n 1)"

cat >"$packet" <<EOF
# AIOS Packet: ${title}

- when: ${human_when}
- source_repo: ${ROOT}
- source_receipt: $(rel_to_workspace "$receipt")
- target: MyWorld AIOS Agent Ledger; MemoryOS/CapabilityOS draft as applicable
- type: ${type:-receipt}
- status: ${status:-proposed}

## Summary

${summary:-not provided}

## Evidence

${evidence:-not provided}

## AIOS Classification

- MyWorld: cross-repo ledger/checkpoint summary
- MemoryOS: draft-only learning candidate
- CapabilityOS: route/capability observation if tool/model/provider behavior is included
- Hive/Hermes: execution receipt only when scheduling, watcher, or GitHub memory behavior changes

## Privacy Boundary

This packet is sanitized. It does not include secrets, auth files, raw private logs, or account exports.

## Next

${next:-operator review}
EOF

if [ "$append_ledger" -eq 1 ]; then
  [ -f "$MYWORLD_LEDGER" ] || { printf 'MyWorld ledger not found: %s\n' "$MYWORLD_LEDGER" >&2; exit 2; }
  cat >>"$MYWORLD_LEDGER" <<EOF

## ${human_when} — codex@dacon — ${title}

- repo: ${ROOT}
- role: prize-hunt control_tower / AIOS asset bridge
- goal: ${summary:-not provided}
- changed: $(rel_to_workspace "$receipt"), $(rel_to_workspace "$packet")
- evidence: ${evidence:-not provided}
- decision: dacon prize-hunting work now exports sanitized receipts and AIOS-ready packets before any MemoryOS/CapabilityOS promotion.
- risk: global ledger must only receive sanitized summaries; accepted memory remains MemoryOS-reviewed, not automatic.
- next: ${next:-operator review}
- status: ${status:-proposed}
EOF
fi

printf '%s\n' "$packet"
