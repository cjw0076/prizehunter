#!/usr/bin/env bash
# assign_roles.sh — the Strategist's allocation function: assess NEEDS & GAPS per
# competition, then DISTRIBUTE ROLES (which agent/persona drives what). Reads the
# portfolio + capability registry; infers the dominant need from each campaign's
# next_lever; routes to the best AVAILABLE agent; flags shortfalls (founder-blocked,
# no capable agent installed, capacity over-subscription, missing expertise).
# Writes ROLE_ASSIGNMENTS.md. Read-only.
set -euo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
REG="$PH_HOME/portfolio_registry.tsv"
CAP="$PH_HOME/capabilities/_registry.tsv"
OUT="$PH_HOME/ROLE_ASSIGNMENTS.md"

# capacity = installed, non-founder agents available as workers
installed=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="agent"&&$4=="yes"{print $1}' "$CAP" | paste -sd, -)
ncap=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="agent"&&$4=="yes"{n++}END{print n+0}' "$CAP")

# infer need-type -> capability keyword from a next_lever / blocker string
need_of() { # $1 = lever text -> echoes "need|capkeyword"
  local t; t="$(printf '%s' "$1" | tr 'A-Z' 'a-z')"
  case "$t" in
    *recon*|*semantic*|*ceiling*|*honest*|*leak*|*analy*) echo "reasoning|reasoning";;
    *package*|*prototype*|*submission*|*writeup*|*deck*|*artifact*|*build*) echo "main-build|main build";;
    *implement*|*pipeline*|*deploy*|*baseline*|*optimi*|*code*) echo "implementation|implementation";;
    *idea*|*brainstorm*|*web*|*scout*|*research*|*reference*|*visual*|*brand*) echo "creative-research|creative direction";;
    *slide*|*video*|*present*|*script*|*writeup*|*design*) echo "media/writing|web";;
    *) echo "general|reasoning";;
  esac
}
# best installed agent for a capability keyword (via route_to text match)
route_to() { # $1 = capkeyword -> agent or ""
  awk -F'\t' -v k="$1" 'NR>1&&$1!~"^#"&&$1!="agent"&&$4=="yes"{ if(index(tolower($7),k)){print $1; exit} }' "$CAP"
}

{
  echo "# Role Assignments — Strategist allocation"
  echo "_$(date '+%Y-%m-%d %H:%M %Z')_  · capacity: $ncap agents [$installed]"
  echo ""
  echo "| competition | dominant need | assigned | gap / shortfall |"
  echo "|---|---|---|---|"
  nactive=0; gaps=0
  while IFS=$'\t' read -r key dir ledger metric direction best rank1 progress status blocker lever; do
    case "$key" in ''|'#'*|key) continue;; esac
    [ "$status" = "ceiling" ] && continue
    nd="$(need_of "$lever $blocker")"; need="${nd%%|*}"; ck="${nd##*|}"
    assigned="$(route_to "$ck")"; gap="—"
    if [ "$status" = "blocked" ] && printf '%s' "$blocker" | grep -q FOUNDER; then
      assigned="⛔ founder"; gap="founder credential/session"
    elif [ -z "$assigned" ]; then
      assigned="(none)"; gap="CAPABILITY GAP: no installed agent for '$ck' — add one (agent_dispatch.sh add)"
    fi
    [ "$status" = "active" ] && nactive=$((nactive+1))
    [ "$gap" != "—" ] && gaps=$((gaps+1))
    echo "| $key | $need | $assigned | $gap |"
  done < "$REG"
  echo ""
  echo "## Needs & gaps summary"
  echo "- active campaigns needing a worker: **$nactive**  vs  capacity **$ncap** agents → $([ "$nactive" -gt "$ncap" ] && echo "⚠ OVER-SUBSCRIBED: serialize or add agents" || echo "ok (parallelizable)")"
  echo "- flagged shortfalls: **$gaps** (founder gates + capability gaps above)"
  echo ""
  echo "## Act on the assignment"
  echo "- launch assigned workers in parallel:  tools/run_parallel.sh --keys <active keys> --agent <assigned>"
  echo "- fill a capability gap:                tools/agent_dispatch.sh add <name> --dispatch '<cli> -p {TASK}'"
  echo "- clear a founder gate:                 surface to founder (credential/session); keep status=blocked until cleared"
  echo "- record the allocation decision:       tools/record_asset_receipt.sh --type decision --asset 'allocation-...'"
} > "$OUT"
printf '%s\n' "$OUT"
echo "active=$nactive capacity=$ncap gaps=$gaps"
