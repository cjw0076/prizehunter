#!/usr/bin/env bash
# session_agent.sh — AGENT INVOKER with PERSISTENT SESSIONS. The piece that lets a daemon, not a chat window,
# own the reasoning loop.
#
# founder 2026-07-27: "cli를 열어서 세션 유지하며 프롬프트를 쓰고 이종 혹은 세션 혼은 서브에이전트로 검증 및
# 공격이 된다면 어느정도 완성이 될 것같은데 … 네가 cli의 능력을 어느정도인지 파악을 못하고있으니까."
# That was right: I had been using every CLI as a one-shot `-p` call and therefore re-primed context from
# scratch every round. MEASURED capabilities (probed 2026-07-27, not read from docs):
#
#   claude  --session-id <uuid> creates · --resume <id> continues · --fork-session branches · --agents <json>
#           defines custom subagents · --bg background · --output-format stream-json · --effort
#           VERIFIED: wrote a canary in one invocation, `--resume` recalled it in a separate process.
#   agy     -p creates · -c continues · --conversation <id> resumes by id · --model/--effort per session
#           VERIFIED: same canary test passed.
#   codex   exec resume [--last] · --output-schema <jsonschema> forces a machine-checkable final answer ·
#           --json event stream · -o <file> writes the last message
#           STATUS 2026-07-27: usage limit hit, unavailable until 2026-08-02 — so the roster must degrade
#           instead of failing, and that is why `roster` probes rather than assumes.
#
# WHY SESSIONS MATTER HERE (not a nicety): a one-shot call cannot remember what it already refuted. Six weeks
# of this campaign produced eight variants of one idea partly because every dispatch started from zero context
# and re-derived the same framing. A per-competition session accumulates "we tried X, it was refuted by Y".
#
#   session_agent.sh roster                          probe which substrates can actually answer right now
#   session_agent.sh ask <key> <role> "<prompt>"     create-or-resume the (key,role) session and ask
#   session_agent.sh attack <key> "<claim>"          adversarial pass on a DIFFERENT substrate, structured verdict
#   session_agent.sh sessions                        list live sessions and their substrate
#
# Roles are just names (driver / critic / theorist). Two roles on the same key are two separate accumulating
# minds, which is what makes `attack` more than talking to yourself.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
R="${PH_RUNS:-$CT/.runs}"
SESS="$R/sessions.tsv"
mkdir -p "$R"
[ -f "$SESS" ] || printf '# key\trole\tsubstrate\tsession_id\tcreated\tlast_used\tturns\n' > "$SESS"
now(){ date -u +%FT%TZ; }
uuid(){ python3 -c "import uuid;print(uuid.uuid4())"; }

sess_get(){ awk -F'\t' -v k="$1" -v r="$2" '$1==k && $2==r {print $3"\t"$4; exit}' "$SESS" 2>/dev/null; }
sess_put(){ # key role substrate id
  python3 - "$SESS" "$1" "$2" "$3" "$4" "$(now)" <<'PY'
import sys
p,k,r,sub,sid,ts=sys.argv[1:7]
lines=open(p,encoding="utf-8").read().split("\n")
out=[];hit=False
for l in lines:
    f=l.split("\t")
    if len(f)>=7 and f[0]==k and f[1]==r:
        turns=int(f[6] or 0)+1
        out.append("\t".join([k,r,sub,sid,f[4],ts,str(turns)])); hit=True
    else: out.append(l)
if not hit:
    if out and out[-1]=="": out.pop()
    out.append("\t".join([k,r,sub,sid,ts,ts,"1"])); out.append("")
open(p,"w",encoding="utf-8").write("\n".join(out))
PY
}

# ── roster: probe, never assume. A substrate that answers a 1-token question is available; one that prints a
# quota error is not, and the loop must know the difference before it plans a round around it.
cmd_roster(){
  echo "== substrate roster $(now) =="
  local ok=""
  if command -v claude >/dev/null 2>&1; then
    if out="$(cd /tmp && timeout 120 claude -p --allow-dangerously-skip-permissions "Reply with the single word READY." 2>&1 | tail -1)"; then
      case "$out" in *READY*) echo "  ✓ claude   sessions=yes (--session-id/--resume/--fork-session)"; ok="$ok claude";;
        *) echo "  ⚠ claude   answered but not as asked: $(printf '%s' "$out" | cut -c1-60)";; esac
    else echo "  ✗ claude   no answer"; fi
  else echo "  - claude   not installed"; fi
  if command -v agy >/dev/null 2>&1; then
    if out="$(cd /tmp && timeout 150 agy --dangerously-skip-permissions -p "Reply with the single word READY." 2>&1 | grep -v libtinfo | tail -1)"; then
      case "$out" in *READY*) echo "  ✓ agy      sessions=yes (-c/--conversation), model=${PH_AGY_MODEL:-gemini-3.1-pro-high}"; ok="$ok agy";;
        *) echo "  ⚠ agy      answered but not as asked: $(printf '%s' "$out" | cut -c1-60)";; esac
    else echo "  ✗ agy      no answer"; fi
  else echo "  - agy      not installed"; fi
  if command -v codex >/dev/null 2>&1; then
    out="$(cd /tmp && timeout 150 codex exec --skip-git-repo-check "Reply READY" 2>&1 | tail -2 | tr '\n' ' ')"
    case "$out" in
      *"usage limit"*) echo "  ✗ codex    QUOTA EXHAUSTED — $(printf '%s' "$out" | grep -oE 'try again at [^.]*' | head -1)";;
      *READY*) echo "  ✓ codex    sessions=yes (exec resume --last), structured=yes (--output-schema)"; ok="$ok codex";;
      *) echo "  ⚠ codex    unclear: $(printf '%s' "$out" | cut -c1-70)";;
    esac
  else echo "  - codex    not installed"; fi
  echo "  available:${ok:- none}"
  printf '%s\n' "${ok# }" > "$R/.substrate_roster"
}

pick_substrate(){ # prefer an explicitly requested one, else the first available that is not $1 (the exclude)
  local exclude="${1:-}" avail
  avail="$(cat "$R/.substrate_roster" 2>/dev/null || echo "claude agy")"
  for s in $avail; do [ "$s" != "$exclude" ] && { echo "$s"; return; }; done
  for s in $avail; do echo "$s"; return; done
  echo claude
}

run_in_session(){ # substrate session_id prompt_file -> stdout ; echoes NEW_SESSION=<id> when it created one
  local sub="$1" sid="$2" pf="$3"
  case "$sub" in
    claude)
      if [ -n "$sid" ]; then
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" claude -p --resume "$sid" --allow-dangerously-skip-permissions "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      else
        sid="$(uuid)"; echo "NEW_SESSION=$sid" >&2
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" claude -p --session-id "$sid" --allow-dangerously-skip-permissions "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      fi ;;
    agy)
      if [ -n "$sid" ]; then
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" agy --dangerously-skip-permissions --model "${PH_AGY_MODEL:-gemini-3.1-pro-high}" --effort "${PH_AGY_EFFORT:-high}" -c -p "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      else
        echo "NEW_SESSION=agy-continue" >&2
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" agy --dangerously-skip-permissions --model "${PH_AGY_MODEL:-gemini-3.1-pro-high}" --effort "${PH_AGY_EFFORT:-high}" -p "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      fi ;;
    codex)
      if [ -n "$sid" ] && [ "$sid" != "codex-last" ]; then
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" codex exec resume "$sid" --skip-git-repo-check "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      else
        echo "NEW_SESSION=codex-last" >&2
        (cd /tmp && timeout "${PH_SESS_TIMEOUT:-900}" codex exec --skip-git-repo-check "$(cat "$pf")" 2>&1 | grep -v libtinfo)
      fi ;;
    *) echo "unknown substrate $sub"; return 1 ;;
  esac
}

cmd_ask(){
  local key="${1:?key}" role="${2:?role}" prompt="${3:?prompt}"
  local sub sid pair; pair="$(sess_get "$key" "$role")"
  sub="$(printf '%s' "$pair" | cut -f1)"; sid="$(printf '%s' "$pair" | cut -f2)"
  [ -z "$sub" ] && sub="${PH_SUBSTRATE:-$(pick_substrate)}"
  local pf="$R/.sess_prompt_${key}_${role}"; printf '%s' "$prompt" > "$pf"
  local out log="$R/session_${key}_${role}.log"
  echo "  ▶ [$sub] $key/$role $([ -n "$sid" ] && echo "resume ${sid:0:8}" || echo "NEW session")"
  out="$(run_in_session "$sub" "$sid" "$pf" 2> "$R/.sess_err")"
  local newsid; newsid="$(grep -oE 'NEW_SESSION=[^ ]+' "$R/.sess_err" 2>/dev/null | head -1 | cut -d= -f2)"
  [ -n "$newsid" ] && sid="$newsid"
  sess_put "$key" "$role" "$sub" "${sid:-unknown}"
  { printf '\n===== %s [%s] %s/%s =====\n' "$(now)" "$sub" "$key" "$role"; printf '%s\n' "$out"; } >> "$log"
  printf '%s\n' "$out"
  echo "  → $log (session ${sid:0:12}, turn $(awk -F'\t' -v k="$key" -v r="$role" '$1==k && $2==r{print $7}' "$SESS"))" >&2
}

# ── attack: the same claim, judged by a DIFFERENT substrate in its own session, answer shape enforced.
# Same-weights self-review is a logic check, not a de-bias, so the exclusion is the point of the verb.
cmd_attack(){
  local key="${1:?key}" claim="${2:?claim}"
  local proposer sub
  proposer="$(awk -F'\t' -v k="$key" '$1==k && $2=="driver"{print $3; exit}' "$SESS" 2>/dev/null)"
  sub="$(pick_substrate "${proposer:-claude}")"
  local p="Judge this claim from our competition work. Do the arithmetic or the algebra yourself; do not defer.

CLAIM: $claim

Answer with EXACTLY these four lines and nothing else:
VERDICT: CONFIRMED|REFUTED|UNTESTABLE
REASON: <one sentence, name the specific step that holds or breaks>
CHECK: <the cheapest measurement that would settle it, runnable in under an hour>
CONFIDENCE: <0.0-1.0>

Default to REFUTED when you cannot verify a step — a false CONFIRMED costs us a submission and a wrong belief."
  echo "  ⚔ attack on [$sub] (proposer was ${proposer:-unknown}) — different substrate by construction"
  PH_SUBSTRATE="$sub" cmd_ask "$key" "critic" "$p" | tee "$R/attack_${key}.txt"
  # enforce the answer shape: an unparseable verdict is a failed attack, not a pass
  if ! grep -qE '^VERDICT: (CONFIRMED|REFUTED|UNTESTABLE)' "$R/attack_${key}.txt"; then
    echo "  ⛔ attack produced no parseable VERDICT line → treat as UNTESTABLE, never as CONFIRMED" >&2
    return 65
  fi
  grep -E '^(VERDICT|REASON|CHECK|CONFIDENCE):' "$R/attack_${key}.txt" | head -4
}

cmd_sessions(){
  echo "== live agent sessions =="
  awk -F'\t' '!/^#/ && NF>=7 {printf "  %-24s %-9s %-8s %s  turns=%s  last=%s\n",$1,$2,$3,substr($4,1,12),$7,$6}' "$SESS" 2>/dev/null \
    || echo "  none yet"
}

case "${1:-roster}" in
  roster)   cmd_roster ;;
  ask)      shift; cmd_ask "$@" ;;
  attack)   shift; cmd_attack "$@" ;;
  sessions) cmd_sessions ;;
  *) echo "usage: session_agent.sh roster|ask <key> <role> \"<prompt>\"|attack <key> \"<claim>\"|sessions" ;;
esac
