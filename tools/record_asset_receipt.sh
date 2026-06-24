#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")/../.." && pwd)"
CONTROL="$ROOT/control_tower"
RECEIPTS="$CONTROL/receipts"
LEDGER="$CONTROL/LEARNING_LEDGER.md"

contest=""
asset=""
type="asset"
summary=""
evidence=""
next=""
status="done"

usage() {
  cat <<'EOF'
Usage:
  record_asset_receipt.sh --asset NAME --summary TEXT [options]

Options:
  --contest NAME     contest folder name or control_tower
  --type TYPE        asset|capability|memory_draft|decision|receipt
  --evidence TEXT    sanitized evidence summary or source path
  --next TEXT        next owner/action
  --status STATUS    done|blocked|proposed|in_progress

This command writes a sanitized local receipt and appends LEARNING_LEDGER.md.
Do not include secrets, tokens, raw private logs, or auth file contents.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --contest)
      contest="${2:?missing --contest value}"
      shift 2
      ;;
    --asset)
      asset="${2:?missing --asset value}"
      shift 2
      ;;
    --type)
      type="${2:?missing --type value}"
      shift 2
      ;;
    --summary)
      summary="${2:?missing --summary value}"
      shift 2
      ;;
    --evidence)
      evidence="${2:?missing --evidence value}"
      shift 2
      ;;
    --next)
      next="${2:?missing --next value}"
      shift 2
      ;;
    --status)
      status="${2:?missing --status value}"
      shift 2
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

[ -n "$asset" ] || { printf 'missing --asset\n' >&2; usage >&2; exit 2; }
[ -n "$summary" ] || { printf 'missing --summary\n' >&2; usage >&2; exit 2; }

case "$type" in
  asset|capability|memory_draft|decision|receipt) ;;
  *)
    printf 'invalid --type: %s\n' "$type" >&2
    exit 2
    ;;
esac

case "$status" in
  done|blocked|proposed|in_progress|superseded|rejected) ;;
  *)
    printf 'invalid --status: %s\n' "$status" >&2
    exit 2
    ;;
esac

for value in "$asset" "$summary" "$evidence" "$next"; do
  if printf '%s' "$value" | grep -Eq '(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)[A-Z0-9_]*=)'; then
    printf 'refusing to write receipt containing secret-looking value\n' >&2
    exit 3
  fi
done

mkdir -p "$RECEIPTS"

stamp="$(date '+%Y%m%dT%H%M%S%z')"
human_when="$(date '+%Y-%m-%d %H:%M:%S %Z')"
slug="$(printf '%s' "$asset" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
[ -n "$slug" ] || slug="asset"
receipt="$RECEIPTS/${stamp}_${slug}.md"

cat >"$receipt" <<EOF
# Asset Receipt: ${asset}

- when: ${human_when}
- repo: ${ROOT}
- contest: ${contest:-control_tower}
- agent: codex@dacon
- type: ${type}
- status: ${status}
- summary: ${summary}
- evidence: ${evidence:-not provided}
- next: ${next:-not provided}

## Privacy Boundary

- secrets: not included
- raw private logs: not included
- auth/provider files: not included
- public-safe: review required before publication
EOF

cat >>"$LEDGER" <<EOF

## ${human_when} — codex@dacon — ${asset}

- repo: ${ROOT}
- contest: ${contest:-control_tower}
- role: ${type}
- goal: ${summary}
- changed: ${receipt#$ROOT/}
- evidence: ${evidence:-not provided}
- decision: record as reusable prize-hunt asset/learning candidate.
- risk: sanitize before GitHub/Hermes/AIOS promotion.
- next: ${next:-not provided}
- status: ${status}
EOF

if [ -n "$contest" ] && [ "$contest" != "control_tower" ] && [ -f "$ROOT/$contest/docs/AGENT_WORKLOG.md" ]; then
  cat >>"$ROOT/$contest/docs/AGENT_WORKLOG.md" <<EOF

### ${human_when} asset receipt

- asset: ${asset}
- receipt: control_tower/receipts/$(basename "$receipt")
- summary: ${summary}
- evidence: ${evidence:-not provided}
- next: ${next:-not provided}
- status: ${status}
EOF
fi

printf '%s\n' "$receipt"
