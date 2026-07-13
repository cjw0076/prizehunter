#!/usr/bin/env bash
# check_capabilities.sh — scan TOOL_REGISTRY.tsv, test availability, report gaps.
# Usage: bash check_capabilities.sh [task_type_filter]
# Outputs: CAPABILITY_REPORT.md in PH_HOME
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
REG="$PH_HOME/capabilities/TOOL_REGISTRY.tsv"
FILTER="${1:-}"
OUT="$PH_HOME/CAPABILITY_REPORT.md"

echo "# Prizehunter Capability Report" > "$OUT"
echo "Generated: $(date -u +%Y-%m-%dT%H:%MZ)" >> "$OUT"
echo "" >> "$OUT"
echo "| Task | Status | Gap / Install | Priority |" >> "$OUT"
echo "|---|---|---|---|" >> "$OUT"

missing=0; ok=0; total=0

while IFS=$'\t' read -r task tools check install prio; do
  [[ "$task" == \#* ]] && continue
  [[ -z "$task" ]] && continue
  [[ -n "$FILTER" && "$task" != *"$FILTER"* ]] && continue
  total=$((total+1))
  # Gate rows (check_cmd is literally `echo "FOUNDER_GATE"`/`echo "AUTH_NEEDED"`) are
  # decided by the check_cmd TEXT itself, decoupled from execution — decide this first
  # so it doesn't depend on whatever the command happens to print to stdout.
  if echo "$check" | grep -q "FOUNDER_GATE\|AUTH_NEEDED"; then
    gate_type=$(echo "$check" | grep -o 'FOUNDER_GATE\|AUTH_NEEDED')
    echo "| \`$task\` | 🔒 $gate_type | $install | $prio |" >> "$OUT"
    ok=$((ok+1))  # not a blocker, just gated
    continue
  fi
  # Run check (set +u: check_cmd entries are user-authored data and may reference
  # unset env vars like $DACON_TOKEN — under nounset that aborts the subshell
  # silently, producing an empty $result instead of falling through to "MISSING".
  # stdout is also suppressed: a check like `which kaggle` prints its match path,
  # which would otherwise pollute the "OK" string comparison below.)
  result=$(set +u; eval "$check" >/dev/null 2>/dev/null && echo "OK" || echo "MISSING")
  if [ "$result" = "OK" ]; then
    echo "| \`$task\` | ✅ available | — | $prio |" >> "$OUT"
    ok=$((ok+1))
  else
    echo "| \`$task\` | ❌ MISSING | \`$install\` | $prio |" >> "$OUT"
    missing=$((missing+1))
  fi
done < "$REG"

echo "" >> "$OUT"
echo "**Summary**: $ok/$total available, $missing missing" >> "$OUT"
if [ "$missing" -gt 0 ]; then
  echo "" >> "$OUT"
  echo "## Install Missing Tools" >> "$OUT"
  echo "Run the install commands above. For MCP discovery: \`npx @smithery/cli search <need>\`" >> "$OUT"
  echo "Marketplaces: [Smithery](https://smithery.ai) · [mcp.so](https://mcp.so) · [glama.ai/mcp](https://glama.ai/mcp) · [PulseMCP](https://www.pulsemcp.com)" >> "$OUT"
fi

cat "$OUT"
