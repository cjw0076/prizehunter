#!/usr/bin/env bash
# qa_team.sh — the standing QA TEAM: a panel of role-specialized reviewers, each
# run on a DIFFERENT model, over a bounded review target. Complements `ph qa`
# (mechanical gates): this is the human-style review a company runs each sprint.
#
# Roles (each a distinct lens; a single pass misses what a panel catches):
#   correctness  — does it work? fresh-clone breakage, logic bugs, wrong outputs
#   security     — credential/shell/abuse surface, secrets, sandbox escapes
#   product      — onboarding/UX, docs that overpromise, first-run friction
#   honesty      — no-launder: any claim that overstates evidence (both directions)
#
# Findings feed R&D: run `ph rnd harvest` after to turn confirmed findings into
# experiments. Roles are round-robined across the operator's council members so
# the review is heterogeneous (same-weights review is a logic check, not QA).
#
# usage: qa_team.sh [--scope <path|diff>] [--members codex,gemini,nim,ollama]
set -uo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
T="$PH_HOME/tools"
REPORT="$PH_HOME/QA_TEAM_REPORT.md"

scope="diff"; members="${PH_COUNCIL_MEMBERS:-codex,gemini,nim,ollama}"
while [ $# -gt 0 ]; do
  case "$1" in
    --scope) scope="${2:-diff}"; shift 2 ;;
    --members) members="${2:-$members}"; shift 2 ;;
    *) shift ;;
  esac
done

# ---- build a bounded review target ----
tgt="$(mktemp)"
if [ "$scope" = "diff" ]; then
  { echo "# Review target: last commit + working diff"; echo;
    git -C "$PH_HOME" log -1 --stat 2>/dev/null | head -60;
    echo; echo "## diff (capped)"; git -C "$PH_HOME" diff HEAD~1 2>/dev/null | head -400;
  } > "$tgt"
elif [ -f "$PH_HOME/$scope" ] || [ -f "$scope" ]; then
  p="$PH_HOME/$scope"; [ -f "$p" ] || p="$scope"
  { echo "# Review target: $scope"; echo; head -400 "$p"; } > "$tgt"
else
  { echo "# Review target: repo structure + key entrypoints"; echo;
    git -C "$PH_HOME" ls-files 2>/dev/null | head -80;
    echo; echo "## ph (front door)"; head -120 "$PH_HOME/ph";
  } > "$tgt"
fi

declare -A ROLE
ROLE[correctness]="You are the CORRECTNESS reviewer. Find real defects: things that break on a fresh clone, logic bugs, wrong outputs, missing files/imports, unhandled failures. Be concrete: file + what fails + the input that triggers it. Ignore style."
ROLE[security]="You are the SECURITY reviewer. This is a PUBLIC repo whose instructions make CLI agents run shell and handle credentials. Find abuse vectors, secret leakage, unsafe shell/eval, credential-in-argv, missing sandbox/limits. Rank by blast radius."
ROLE[product]="You are the PRODUCT reviewer. A brand-new user just cloned this. Find onboarding friction, docs that overpromise vs. what the code does, confusing verbs, missing first-run guidance. What makes them quit in 5 minutes?"
ROLE[honesty]="You are the HONESTY reviewer (no-launder, both directions). Find any claim in code/docs that overstates evidence — 'autonomous', 'gets smarter', 'rank #1' — where the code doesn't back it. Also flag genuine strengths sold as weaknesses. Quote the claim + the gap."

roles=(correctness security product honesty)
IFS=',' read -ra M <<<"$members"
avail=()
for m in "${M[@]}"; do
  case "$m" in
    codex)  command -v codex  >/dev/null 2>&1 && avail+=(codex) ;;
    gemini) { command -v agy >/dev/null 2>&1 || command -v gemini >/dev/null 2>&1; } && avail+=(gemini) ;;
    nim)    command -v nv     >/dev/null 2>&1 && avail+=(nim) ;;
    ollama) command -v ollama >/dev/null 2>&1 && avail+=(ollama) ;;
    claude) command -v claude >/dev/null 2>&1 && avail+=(claude) ;;
  esac
done

outdir="$(mktemp -d)"
target_text="$(cat "$tgt")"
run_member() { # run_member <member> <prompt> <outfile>
  local m="$1" p="$2" o="$3"
  case "$m" in
    codex)  codex exec --skip-git-repo-check "$p" >"$o" 2>/dev/null ;;
    gemini) if command -v agy >/dev/null 2>&1; then agy --dangerously-skip-permissions -p "$p" >"$o" 2>/dev/null;
            else gemini -p "$p" >"$o" 2>/dev/null; fi ;;
    nim)    nv ask "${PH_NIM_MODEL:-deepseek-ai/deepseek-v4-flash}" "$p" >"$o" 2>/dev/null ;;
    ollama) ollama run "${PH_OLLAMA_MODEL:-qwen3:8b}" "$p" >"$o" 2>/dev/null ;;
    claude) claude -p "$p" >"$o" 2>/dev/null ;;
  esac
}

if [ "${#avail[@]}" -eq 0 ]; then
  echo "No council members available for the QA team. Install one of: codex · agy/gemini · nv(NIM) · ollama."
  echo "Fallback: the calling agent should self-run the four roles above (correctness/security/product/honesty)"
  echo "as separate focused passes — but note a single-model self-review is a logic check, not heterogeneous QA."
  rm -rf "$outdir" "$tgt"; exit 0
fi

i=0
for role in "${roles[@]}"; do
  m="${avail[$((i % ${#avail[@]}))]}"; i=$((i+1))
  prompt="${ROLE[$role]}

Return AT MOST 5 findings, each: [SEVERITY P0/P1/P2] one-line title — file:where — why it's real. If none, say 'no findings'.

===== REVIEW TARGET =====
${target_text}"
  ( run_member "$m" "$prompt" "$outdir/${role}__${m}" ) &
done
wait

{
  echo "# QA Team Report — $(git -C "$PH_HOME" rev-parse --short HEAD 2>/dev/null)"
  echo "_scope: ${scope} · panel: ${avail[*]} · roles round-robined for heterogeneity_"
  echo
  got=0
  for role in "${roles[@]}"; do
    f="$(ls "$outdir/${role}__"* 2>/dev/null | head -1)"
    echo "## ${role}  (${f##*__})"
    if [ -s "$f" ]; then sed 's/^/  /' "$f" | head -40; got=$((got+1)); else echo "  (no response)"; fi
    echo
  done
  echo "---"
  echo "→ AGENT: synthesize + VERIFY each finding against the code before acting (models hallucinate"
  echo "  differently). Confirmed P0/P1 → \`ph issue \"<title>\"\`. Then \`ph rnd harvest\` turns the"
  echo "  systemic ones into R&D experiments. ${got}/4 roles responded."
} | tee "$REPORT"
rm -rf "$outdir" "$tgt"
