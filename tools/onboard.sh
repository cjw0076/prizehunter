#!/usr/bin/env bash
# onboard.sh — just-in-time credential elicitation. Detects which gate is blocking
# and prints a single structured NEED block the agent reads aloud to the operator —
# asking for ONLY the one credential that is actually required, nothing more.
# The agent then stores it via vault_set.sh and resumes autonomously.
#
# usage: onboard.sh [gate]     gate ∈ dacon|kaggle|council|gh|browser|memos|all
#   no arg / all → show every unfilled gate; a specific gate → just that NEED block.
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
have() { command -v "$1" >/dev/null 2>&1; }
gate="${1:-all}"

need_dacon() {
cat <<'EOF'
NEED: DACON API token  → unlocks fully-unattended DACON submission (token API, no login gate)
  why : without it the agent can build/validate but cannot submit to DACON on its own.
  get : log in at dacon.io → 마이페이지 → API → copy your submission token.
  give: paste it when asked; the agent stores it with
        tools/vault_set.sh DACON_TOKEN -   (or per-competition: DACON_TOKEN_<cptId>)
  after: `ph run <key> --exec` submits autonomously.
EOF
}
need_kaggle() {
cat <<'EOF'
NEED: Kaggle access (two parts)
  1) API token → get: kaggle.com → Account → API → "Create New Token" → save as ~/.kaggle/kaggle.json
  2) Per-competition RULES acceptance (one-time web click) → kaggle.com/competitions/<slug>/rules → "I Understand and Accept"
  why : the API token alone can't submit until that competition's rules are accepted (a web-login action).
  give: option A — accept the rules yourself once (30s); option B — hand the agent a logged-in browser
        session (see `browser` gate) so it accepts on your behalf.
  after: data download + submit run autonomously for that competition.
EOF
}
need_council() {
cat <<'EOF'
NEED: at least one heterogeneous model for the council (de-bias lane)
  why : a single model checking itself is a logic check, not a second opinion.
  get : install ANY one of — codex CLI · gemini/agy · nv (NVIDIA NIM) · ollama (local) · a 2nd `claude`.
  give: nothing to store; once the binary is on PATH, `ph council "..."` uses it automatically.
EOF
}
need_gh() {
cat <<'EOF'
NEED: GitHub CLI auth  → unlocks agent-native issue self-reporting (ph issue)
  get : install `gh`, run `gh auth login`.
  give: nothing to store; set PH_ISSUE_REPO=owner/name to route issues to a maintainer repo.
EOF
}
need_browser() {
cat <<'EOF'
NEED (optional, powerful): a logged-in browser session the agent can drive
  why : lets the agent clear WEB gates for you — accept Kaggle/Devpost rules, log into portals —
        instead of asking you each time. This is the closest thing to unattended for web platforms.
  get : a Playwright/gstack Chromium already signed in to your competition accounts (Google/Kaggle/etc.).
  give: `ph session --site <name> --headed` (log in once) or `--creds` (auto). The agent then
        extracts the API token from the browser and stores it — the platform's API becomes agent-driven.
  note: signup, 2FA, phone-SMS, and CAPTCHA still need YOU — those cannot be automated.
EOF
}
need_memos() {
cat <<'EOF'
NEED (optional): MemoryOS checkout for the knowledge flywheel
  get : clone a MemoryOS instance, then `export MEMOS_ROOT=/path/to/memoryOS` (or set in config.local.sh).
  give: nothing to store; empty MEMOS_ROOT just disables compounding memory — the machine still runs.
EOF
}

emit() { case "$1" in
  dacon) [ -n "${DACON_TOKEN:-}${DACON_API_TOKEN:-}" ] || ls "$PH_HOME"/campaigns/*/.env >/dev/null 2>&1 || { need_dacon; echo; } ;;
  kaggle) { have kaggle && kaggle competitions list >/dev/null 2>&1; } || { need_kaggle; echo; } ;;
  council) c=0; for b in codex agy gemini nv ollama claude; do have "$b" && c=$((c+1)); done; [ "$c" -ge 2 ] || { need_council; echo; } ;;
  gh) { have gh && gh auth status >/dev/null 2>&1; } || { need_gh; echo; } ;;
  browser) need_browser; echo ;;
  memos) [ -n "${MEMOS_ROOT:-}" ] && [ -d "${MEMOS_ROOT:-/x}" ] || { need_memos; echo; } ;;
esac; }

echo "── Onboarding — only what you actually need, nothing more ──"
echo "The agent asks for a credential ONLY when a gate blocks the work you asked for."
echo "Fill just those; everything else is already autonomous. Full guide: SETUP_GATES.md"
echo
if [ "$gate" = "all" ]; then
  for g in dacon kaggle council gh browser memos; do emit "$g"; done
else
  emit "$gate"
fi
echo "→ Give the value when asked; the agent stores it with tools/vault_set.sh and resumes."
