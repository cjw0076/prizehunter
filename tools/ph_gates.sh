#!/usr/bin/env bash
# ph_gates.sh — autonomy self-diagnosis. Detects which credentials/agents the
# operator has filled and prints exactly how much is autonomous RIGHT NOW vs what
# each unfilled gate would unlock. Honest: no gate faked as "done".
# Run by setup.sh and via `ph gates-check`. Read-only; prints nothing secret.
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true

have() { command -v "$1" >/dev/null 2>&1; }
YES="✅"; NO="⬜"; PART="🟡"

# ---- detect ----
# DACON token (any per-competition .env or env var)
dacon="$NO"; dacon_note="fill a DACON API token → set DACON_TOKEN / put in campaigns/<key>/.env"
if [ -n "${DACON_TOKEN:-}${DACON_API_TOKEN:-}" ] || ls "$PH_HOME"/campaigns/*/.env >/dev/null 2>&1 || [ -f "$PH_HOME/.vault/identity.env" ]; then
  dacon="$YES"; dacon_note="token detected → DACON submit is autonomous (token API, no login gate)"
fi
# Kaggle
kaggle="$NO"; kaggle_note="run 'kaggle competitions list' (needs ~/.kaggle/kaggle.json) + accept each comp's rules in the browser once"
if have kaggle; then
  if kaggle competitions list >/dev/null 2>&1; then kaggle="$PART"; kaggle_note="CLI authed → download/submit works AFTER you accept each competition's rules (web login, once per comp)";
  else kaggle="$PART"; kaggle_note="CLI present but not authed → add ~/.kaggle/kaggle.json"; fi
fi
# heterogeneous council members
members=(); seen=""; for m in codex "agy:gemini" gemini "nv:nim" ollama claude; do
  bin="${m%%:*}"; label="${m##*:}"; case " $seen " in *" $label "*) continue;; esac
  have "$bin" && { members+=("$label"); seen="$seen $label"; }
done
council="$NO"; council_note="install at least one of: codex · gemini/agy · nv(NIM) · ollama · claude → real de-bias lane"
if [ "${#members[@]}" -ge 2 ]; then council="$YES"; council_note="council members: ${members[*]} → heterogeneous 2nd opinion works";
elif [ "${#members[@]}" -eq 1 ]; then council="$PART"; council_note="only '${members[*]}' — one model is a logic check, not de-bias; add another"; fi
# browser (gate-bypass for web logins/rules)
browser="$NO"; browser_note="a logged-in browser (e.g. gstack/Playwright with your session) lets the agent accept web rules/logins for you"
if have chromium || have chromium-browser || have google-chrome || [ -n "${GSTACK_CHROMIUM_NO_SANDBOX:-}" ]; then
  browser="$PART"; browser_note="browser present → can drive web rules/login IF you provide a logged-in session"
fi
# MemoryOS flywheel
memos="$NO"; memos_note="set MEMOS_ROOT to a MemoryOS checkout → tacit→explicit knowledge compounding (optional)"
[ -n "${MEMOS_ROOT:-}" ] && [ -d "${MEMOS_ROOT:-/nonexistent}" ] && { memos="$YES"; memos_note="MEMOS_ROOT set → flywheel on"; }
# gh (issue self-reporting)
gh_s="$NO"; gh_note="install gh + 'gh auth login' → ph issue self-reports bugs"
have gh && { gh auth status >/dev/null 2>&1 && { gh_s="$YES"; gh_note="gh authed → ph issue works"; } || { gh_s="$PART"; gh_note="gh present, run 'gh auth login'"; }; }

# ---- render ----
cat <<EOF
── PrizeHunter autonomy self-check ──────────────────────────────
What runs unattended today vs what each gate unlocks. Honest — a gate you
haven't filled is not "done"; it just needs your one-time credential.

BUILD / RECORD / SETTLE / CALIBRATE / COUNCIL synthesis   ✅ always autonomous (agent-only)
RESULT check on PUBLIC pages (Devpost/leaderboards)       ✅ autonomous

$dacon  DACON submit           $dacon_note
$kaggle  Kaggle submit          $kaggle_note
$council  Council (de-bias)      $council_note
$browser  Web gate-bypass        $browser_note
$gh_s  Issue self-reporting   $gh_note
$memos  MemoryOS flywheel      $memos_note

ALWAYS operator-gated (structurally cannot be automated):
  ⛔ account signup · 2FA / phone SMS · CAPTCHA · final external-submit approval · real-money spend

→ Fill the ⬜/🟡 rows to widen autonomy. Full guide: SETUP_GATES.md
   Rule of thumb: token-API platforms (DACON) can be fully unattended; web-login
   platforms (Kaggle/Devpost) are autonomous only once you supply a session.
─────────────────────────────────────────────────────────────────
EOF
