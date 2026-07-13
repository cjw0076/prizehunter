#!/usr/bin/env bash
# council.sh — heterogeneous second opinion for keystone calls.
# Polls the models/agents the operator actually has (Codex, Gemini, NIM, local
# ollama, Claude), in parallel, and lays their independent reads side by side.
# Same-weights agreement is fake consensus — a keystone decision gets a DIFFERENT
# model. The calling agent then synthesizes + verifies (they hallucinate differently).
#
# usage: council.sh "<question>" [--members codex,gemini,nim,ollama,claude]
# env:   PH_COUNCIL_MEMBERS (default list) · PH_OLLAMA_MODEL (default qwen3:8b)
set -uo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true

Q="${1:-}"; shift || true
[ -n "$Q" ] || { echo 'usage: council.sh "<question>" [--members codex,gemini,nim,ollama,claude]'; exit 2; }
members="${PH_COUNCIL_MEMBERS:-codex,gemini,nim,ollama}"
[ "${1:-}" = "--members" ] && members="${2:-$members}"

outdir="$(mktemp -d)"
ask() { local name="$1"; shift; ( "$@" >"$outdir/$name" 2>/dev/null ) & }

IFS=',' read -ra M <<<"$members"
for m in "${M[@]}"; do
  case "$m" in
    codex)  command -v codex  >/dev/null 2>&1 && ask codex  codex exec --skip-git-repo-check "$Q" ;;
    gemini) if command -v agy >/dev/null 2>&1; then ask gemini agy --dangerously-skip-permissions -p "$Q";
            elif command -v gemini >/dev/null 2>&1; then ask gemini gemini -p "$Q"; fi ;;
    nim)    command -v nv     >/dev/null 2>&1 && ask nim    nv ask "${PH_NIM_MODEL:-deepseek}" "$Q" ;;
    ollama) command -v ollama >/dev/null 2>&1 && ask ollama ollama run "${PH_OLLAMA_MODEL:-qwen3:8b}" "$Q" ;;
    claude) command -v claude >/dev/null 2>&1 && ask claude claude -p "$Q" ;;
  esac
done
wait

echo "## Council on: $Q"
got=0
for f in "$outdir"/*; do
  [ -s "$f" ] || continue
  echo; echo "### $(basename "$f")"; cat "$f"; got=$((got+1))
done
if [ "$got" -eq 0 ]; then
  echo; echo "(no council members available — install one of: codex · gemini/agy · nv(NIM) · ollama · claude,"
  echo " or set PH_COUNCIL_MEMBERS to what you have. A single-model system has no de-bias lane.)"
fi
echo; echo "→ Synthesize these INDEPENDENT reads; verify before accepting (each model hallucinates differently)."
rm -rf "$outdir"
