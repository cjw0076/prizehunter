#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname "$0")/../.." && pwd)"
CONTROL="$ROOT/control_tower"
REPORTS="$CONTROL/failure_reports"
LEDGER="$CONTROL/LEARNING_LEDGER.md"

contest="control_tower"
failure_class=""
summary=""
evidence=""
root_cause=""
lesson=""
next=""
other_agents=""
cross_domain=""
past_evidence=""
dont_repeat=""
exit_state="retry"
owner="next-agent"

usage() {
  cat <<'EOF'
Usage:
  record_failure_learning.sh --summary TEXT --class CLASS [options]

Options:
  --contest NAME
  --evidence TEXT
  --root-cause TEXT
  --lesson TEXT
  --next TEXT
  --other-agents TEXT
  --cross-domain TEXT
  --past-evidence TEXT
  --dont-repeat TEXT
  --exit-state retry|operator_gate|park|kill
  --owner TEXT

Records a failure/blocker as a learning event, then writes a normal asset
receipt so the event can be promoted to AIOS/Notion if useful.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --contest)
      contest="${2:?missing --contest value}"
      shift 2
      ;;
    --class)
      failure_class="${2:?missing --class value}"
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
    --root-cause)
      root_cause="${2:?missing --root-cause value}"
      shift 2
      ;;
    --lesson)
      lesson="${2:?missing --lesson value}"
      shift 2
      ;;
    --next)
      next="${2:?missing --next value}"
      shift 2
      ;;
    --other-agents)
      other_agents="${2:?missing --other-agents value}"
      shift 2
      ;;
    --cross-domain)
      cross_domain="${2:?missing --cross-domain value}"
      shift 2
      ;;
    --past-evidence)
      past_evidence="${2:?missing --past-evidence value}"
      shift 2
      ;;
    --dont-repeat)
      dont_repeat="${2:?missing --dont-repeat value}"
      shift 2
      ;;
    --exit-state)
      exit_state="${2:?missing --exit-state value}"
      shift 2
      ;;
    --owner)
      owner="${2:?missing --owner value}"
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

[ -n "$summary" ] || { printf 'missing --summary\n' >&2; usage >&2; exit 2; }
[ -n "$failure_class" ] || { printf 'missing --class\n' >&2; usage >&2; exit 2; }

case "$exit_state" in
  retry|operator_gate|park|kill) ;;
  *)
    printf 'invalid --exit-state: %s\n' "$exit_state" >&2
    exit 2
    ;;
esac

for value in "$summary" "$evidence" "$root_cause" "$lesson" "$next" "$other_agents" "$cross_domain" "$past_evidence" "$dont_repeat" "$owner"; do
  if printf '%s' "$value" | grep -Eq '(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)[A-Z0-9_]*=)'; then
    printf 'refusing to write failure report containing secret-looking value\n' >&2
    exit 3
  fi
done

mkdir -p "$REPORTS"
stamp="$(date '+%Y%m%dT%H%M%S%z')"
human_when="$(date '+%Y-%m-%d %H:%M:%S %Z')"
slug="$(printf '%s-%s' "$failure_class" "$contest" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
report="$REPORTS/${stamp}_${slug}.md"

cat >"$report" <<EOF
# Failure Learning: ${failure_class}

- when: ${human_when}
- contest: ${contest}
- class: ${failure_class}
- summary: ${summary}
- evidence: ${evidence:-not provided}
- root_cause: ${root_cause:-not provided}
- lesson: ${lesson:-not provided}
- next: ${next:-not provided}
- other_agents: ${other_agents:-not provided}
- cross_domain: ${cross_domain:-not provided}
- past_evidence: ${past_evidence:-not provided}
- dont_repeat: ${dont_repeat:-not provided}
- owner: ${owner}
- exit_state: ${exit_state}

## Diagnosis

- why_not: ${root_cause:-not provided}
- make_it_work: ${next:-not provided}
- other_agents: ${other_agents:-not provided}
- cross_domain: ${cross_domain:-not provided}
- data_or_past_records: ${past_evidence:-not provided}
- do_not_repeat: ${dont_repeat:-not provided}

## Memory Candidate

${lesson:-This blocker should be treated as a learning event and not retried unchanged.}
EOF

receipt="$("$CONTROL/tools/record_asset_receipt.sh" \
  --contest "$contest" \
  --asset "failure-learning-${failure_class}-${contest}" \
  --type memory_draft \
  --summary "$summary" \
  --evidence "control_tower/failure_reports/$(basename "$report"); ${evidence:-not provided}" \
  --next "${next:-not provided}" \
  --status done)"

cat >>"$LEDGER" <<EOF

### Failure learning detail — ${human_when}

- report: control_tower/failure_reports/$(basename "$report")
- receipt: control_tower/receipts/$(basename "$receipt")
- class: ${failure_class}
- exit_state: ${exit_state}
- owner: ${owner}
EOF

printf '%s\n' "$report"
printf '%s\n' "$receipt"
