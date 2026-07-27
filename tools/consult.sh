#!/usr/bin/env bash
# consult.sh — HETEROGENEOUS CONSULT with a verify step: ask agy (Gemini 3.1 Pro, high effort) the
# high-dimensional question, then REFUTE its answer mechanically before any of it becomes a directive.
#
# founder 2026-07-27: "prizehunter에 claude가 agy 활용할 수 있게 만들어. agy에게 고차원적인 문제 인식과
# 파훼법을 계속 질문하고 조언을 얻을 수 있게. 네가 직접 써보면서 built in 해보는것도 좋은 방법일 듯."
#
# Built by dogfooding: the first consult (arc-whitebox, 2026-07-27) produced a genuinely load-bearing
# diagnosis — "the Gaussian closure error SATURATES with depth, so a pure analytical closure floors near
# 1e-6; the leaders at 2.5e-8 must be sample-assisted" — which explains why eight closure variants never
# moved. It ALSO contained a fatal algebra error: its control-variate code reduced to
#     mu + mean(a - mu) == mean(a)
# i.e. the control variate cancelled and the estimator collapsed to plain Monte Carlo, so its headline
# "this will take you to 2e-8" was false as written. Both facts arrived in the same answer. That is the
# whole design requirement: capture the insight, catch the error, never pass either through unchecked.
#
#   consult.sh ask <key> "<question>"   compose context from OUR measured record + ask agy → round file
#   consult.sh panel <key> "<question>" same context fanned to agy + council (perplexity/deepseek/claude.ai)
#   consult.sh diverge <key>            where substrates DISAGREE — the payload, not the consensus
#   consult.sh claims <key>             extract checkable claims (numbers, formulas, code) from the last round
#   consult.sh push <key> "<refutation>"  send the refutation back and demand a repair (the dialogue)
#   consult.sh adopt <key>              write SURVIVING findings into BRIEF_BANK ## COMP:<key>
#   consult.sh log <key>                the dialogue so far
#
# WHY context composition matters more than the question: the useful answer came from stuffing the prompt
# with OUR numbers (2.10e-6 vs 2.46e-8, the architecture, the metric, the eight approaches already tried).
# A generic "how do I improve" gets a generic listicle. This tool assembles that context automatically.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$CT/../.." && pwd)"
R="${PH_RUNS:-$CT/.runs}"
MODEL="${PH_AGY_MODEL:-gemini-3.1-pro-high}"
EFFORT="${PH_AGY_EFFORT:-high}"
mkdir -p "$R"
CMD="${1:-}"; KEY="${2:-}"
[ -z "$CMD" ] && { echo "usage: consult.sh ask|claims|push|adopt|log <key> [text]"; exit 2; }
[ -z "$KEY" ] && { echo "need a competition key (registry key)"; exit 2; }
command -v agy >/dev/null 2>&1 || { echo "⛔ agy not on PATH (~/.local/bin/agy)"; exit 2; }

camp_dir(){ python3 - "$KEY" <<'PY'
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)) if False else "", "."))
sys.path.insert(0, os.environ.get("PH_TOOLS",""))
try:
    from gap_view import resolve_dir
    print(resolve_dir(sys.argv[1]) or "")
except Exception:
    print("")
PY
}
DIR="$(PH_TOOLS="$CT/tools" camp_dir)"
LOG="${DIR:-$CT}/CONSULT_LOG.md"
round(){ ls "$R/consult_${KEY}_r"*.md 2>/dev/null | wc -l; }

# ── context: only measured facts from our own record. No invention, no vibes. ────────────────────────────────
context(){
  python3 - "$CT" "$KEY" "${DIR:-}" <<'PY'
import os,sys,glob,json
CT,key,d = sys.argv[1], sys.argv[2], sys.argv[3]
out=[]
# registry row → metric, direction, our best, the #1 target, and the honest ratio
cols=[]
reg=os.path.join(CT,"portfolio_registry.tsv")
row=None
if os.path.exists(reg):
    for l in open(reg,encoding="utf-8",errors="replace"):
        if l.startswith("#   ") and l[4:5].isalpha() and len(l.split())>1: cols.append(l.split()[1])
        elif not l.startswith("#"): break
    for l in open(reg,encoding="utf-8",errors="replace"):
        if l.startswith("#") or not l.strip(): continue
        f=l.rstrip("\n").split("\t")
        if f and f[0]==key: row=dict(zip(cols,f)); break
if row:
    g=lambda k: (row.get(k) or "").strip()
    out.append("OUR MEASURED POSITION (from the portfolio registry, single source of truth):")
    out.append("  metric=%s direction=%s  our best=%s  leaderboard #1=%s"%(g("metric"),g("direction"),g("best"),g("rank1")))
    try:
        b,r1=float(g("best")),float(g("rank1"))
        if b and r1:
            ratio=(b/r1) if g("direction")=="min" else (r1/b)
            out.append("  → we are %.3gx away from #1 on the SAME axis (both graded by the platform)"%ratio)
    except ValueError: pass
    if g("blocker"): out.append("  standing blocker: %s"%g("blocker")[:400])
    if g("next_lever"): out.append("  current next lever: %s"%g("next_lever")[:600])
# what has already been tried, so the consult cannot hand back what we did last week
if d and os.path.isdir(d):
    tried=[os.path.basename(p) for p in sorted(glob.glob(os.path.join(d,"**","experiments","*.py"),recursive=True))][:20]
    if tried: out.append("APPROACHES ALREADY IMPLEMENTED (do not propose these again): "+", ".join(tried))
    for name in ("VIEW/FINDINGS.md","GAP_REPORT.md","FRAME.md"):
        p=os.path.join(d,name)
        if os.path.exists(p):
            out.append("FROM OUR OWN %s (measured):\n%s"%(name, open(p,encoding="utf-8",errors="replace").read()[:1200]))
    led=os.path.join(d,"iterate_ledger.tsv")
    if os.path.exists(led):
        ls=[l.rstrip("\n").split("\t") for l in open(led,encoding="utf-8") if not l.startswith("#") and l.strip()]
        if ls:
            out.append("RECENT LOCAL/GRADED SCORES (scale column matters — local and graded are different axes):")
            for f in ls[-8:]: out.append("  "+" | ".join(f[:6]))
# levers proven elsewhere in the portfolio for this task type
lev=os.path.join(CT,"LEVER_LIBRARY.tsv")
if os.path.exists(lev):
    for l in open(lev,encoding="utf-8",errors="replace"):
        f=l.rstrip("\n").split("\t")
        if len(f)>6 and key.split("-")[0] in l:
            out.append("A LEVER WE ALREADY PROVED HERE: "+f[6][:300]); break
print("\n".join(out))
PY
}

DEMAND='HOW TO ANSWER (this is a working session, not a briefing):
- RANK the error terms / causes by magnitude with scaling laws. Do not hand me a list of options.
- NAME the mathematical object or mechanism. "Try regularisation" is not an answer; "the closure error
  saturates at kappa4* = 15/(w(1-rho))" is.
- Give the COST scaling (FLOPs / time / memory) of anything you propose, because our budget is binding.
- State, for your top proposal, WHAT WOULD FALSIFY IT and the experiment that settles it in under an hour
  of CPU on one box. We will run it and hold you to the result.
- Distinguish what you KNOW from what you are inferring. If your number is a guess, label it a guess.
- If our framing itself is wrong (wrong metric, wrong target, a dataset artefact, a noise floor we are
  already near), say that first and loudly — that is the most valuable answer you can give.'

cmd_ask(){
  local q="${1:?need a question}" n; n="$(( $(round) + 1 ))"
  local f="$R/consult_${KEY}_r${n}.md"
  local P; P="$(printf '%s\n\n%s\n\n%s\n\nTHE QUESTION:\n%s\n' \
      "You are advising on a live competition where we are measurably behind and want to know WHERE the gap actually lives. Be quantitative and specific; we implement and measure everything you say, so a wrong-but-checkable answer beats a hedge." \
      "$(context)" "$DEMAND" "$q")"
  printf '%s' "$P" > "$R/.consult_prompt_${KEY}"
  echo "  🧠 consult round $n → $MODEL (effort $EFFORT), $(printf '%s' "$P" | wc -c) chars of OUR measured context"
  {
    printf '## ROUND %s — %s (%s)\n\n### QUESTION\n%s\n\n### ANSWER\n' "$n" "$(date -u +%FT%TZ)" "$MODEL" "$q"
    agy --dangerously-skip-permissions --model "$MODEL" --effort "$EFFORT" -p "$P" 2>&1 | grep -v "libtinfo.so.6"
  } > "$f"
  echo "  → $f ($(wc -c < "$f") bytes)"
  { echo; cat "$f"; } >> "$LOG"
  echo "  → appended to $LOG"
  echo "  NEXT: consult.sh claims $KEY   (never adopt an answer before its checkable claims are checked)"
}

cmd_claims(){
  local f; f="$(ls -t "$R/consult_${KEY}_r"*.md 2>/dev/null | head -1)"
  [ -z "$f" ] && { echo "no consult rounds yet"; exit 1; }
  echo "== CHECKABLE CLAIMS from $(basename "$f") =="
  python3 - "$f" <<'PY'
import re,sys
t=open(sys.argv[1],encoding="utf-8",errors="replace").read()
nums=re.findall(r'([^\n]{0,110}?(?:\d\.?\d*\s*[eE][-+]?\d+|\d+(?:\.\d+)?\s*x\b)[^\n]{0,60})', t)
seen=set(); n=0
print("\n-- numeric claims (each must be reproduced or refuted on our harness):")
for s in nums:
    s=" ".join(s.split())
    if s in seen or len(s)<24: continue
    seen.add(s); n+=1
    if n>14: break
    print("  [%2d] %s"%(n,s[:150]))
code=re.findall(r'```(?:python)?\n(.*?)```', t, re.S)
print("\n-- code blocks: %d (run each; an answer whose code does not run is not evidence)"%len(code))
for i,c in enumerate(code[:3],1):
    print("  [%d] %d lines, first line: %s"%(i,len(c.splitlines()),c.strip().splitlines()[0][:80] if c.strip() else ""))
    # the cheapest possible check: does the arithmetic collapse? (the failure we actually hit)
    if re.search(r'mean\(\s*(\w+)\s*-\s*(\w+)\s*[,)]', c) and re.search(r'(\w+)\s*\+\s*np\.mean', c):
        print("      ⚠ ALGEBRA SMELL: `mu + mean(a - mu)` collapses to `mean(a)` — the control variate cancels.")
print("\n-- verdict template (fill in, then `consult.sh push <key> \"<refutation>\"`):")
print("   CONFIRMED: ...   REFUTED: ...   UNTESTED: ...")
PY
}

cmd_push(){
  local ref="${1:?need the refutation text}" n; n="$(( $(round) + 1 ))"
  local prev; prev="$(ls -t "$R/consult_${KEY}_r"*.md 2>/dev/null | head -1)"
  local f="$R/consult_${KEY}_r${n}.md"
  local P; P="$(printf 'You advised us on this competition and we CHECKED your answer against our own harness. Below is your previous answer, then what survived and what did not. Repair your position: keep what held, retract what broke, and give the corrected construction in full detail. Do not restate the parts we confirmed — spend the whole answer on the repair and on what to do next.\n\n=== YOUR PREVIOUS ANSWER ===\n%s\n\n=== OUR VERIFICATION ===\n%s\n\n%s\n' \
      "$( [ -n "$prev" ] && head -c 9000 "$prev" )" "$ref" "$DEMAND")"
  echo "  🔁 push-back round $n → $MODEL"
  {
    printf '## ROUND %s (PUSH-BACK) — %s\n\n### OUR VERIFICATION\n%s\n\n### REPAIRED ANSWER\n' "$n" "$(date -u +%FT%TZ)" "$ref"
    agy --dangerously-skip-permissions --model "$MODEL" --effort "$EFFORT" -p "$P" 2>&1 | grep -v "libtinfo.so.6"
  } > "$f"
  echo "  → $f ($(wc -c < "$f") bytes)"
  { echo; cat "$f"; } >> "$LOG"
}

# ── COUNCIL PANEL ─────────────────────────────────────────────────────────────────────────────────────
# founder 2026-07-27: "agy가 council과 함께 진짜 hit한 아이디어를 주입해주는 것 같은데. prizehunter에 내장되었나?"
# It was not — only the agy lane existed. This adds the council fan-out with the discipline that matters:
# a panel is NOT a vote. Measured ceiling: 9 judges from 7 families ≈ 2.18 effective independent votes, so
# agreement is a WEAK signal and unanimity can be shared hallucination. The panel earns its cost through
# DISAGREEMENT — where substrates diverge is where the information is, and that is what gets verified first.
cmd_panel(){
  local q="${1:?need a question}" n; n="$(( $(round) + 1 ))"
  local f="$R/consult_${KEY}_r${n}_panel.md"
  local P; P="$(printf '%s\n\n%s\n\n%s\n\nTHE QUESTION:\n%s\n' \
      "You are one of several independent advisors on a live competition where we are measurably behind. Answer from your own reasoning; do not hedge toward a consensus you cannot see." \
      "$(context)" "$DEMAND" "$q")"
  local HUB="$ROOT/council/hub.py"
  {
    printf '## ROUND %s (PANEL) — %s\n\n### QUESTION\n%s\n' "$n" "$(date -u +%FT%TZ)" "$q"
    printf '\n### agy (%s)\n' "$MODEL"
    agy --dangerously-skip-permissions --model "$MODEL" --effort "$EFFORT" -p "$P" 2>&1 | grep -v "libtinfo.so.6"
    if [ -f "$HUB" ]; then
      for sub in ${PH_COUNCIL_SET:-perplexity-api deepseek-api claudeai-api}; do
        printf '\n### council:%s\n' "$sub"
        timeout "${PH_COUNCIL_TIMEOUT:-420}" python3 "$HUB" ask "$sub" "$P" 2>&1 \
          | grep -v "libtinfo.so.6" | tail -100 \
          || echo "(no answer from $sub — one substrate failing is transient, not a broken council)"
      done
    else
      printf '\n(council hub not found at %s — agy lane only)\n' "$HUB"
    fi
  } > "$f"
  echo "  → $f ($(wc -c < "$f") bytes)"
  { echo; cat "$f"; } >> "$LOG"
  echo "  NEXT: ph consult diverge $KEY   — read the DISAGREEMENTS first; agreement is the weak signal"
}

cmd_diverge(){
  local f; f="$(ls -t "$R/consult_${KEY}_r"*_panel.md 2>/dev/null | head -1)"
  [ -z "$f" ] && { echo "no panel round yet — run: ph consult panel $KEY \"<question>\""; return 1; }
  python3 "$CT/tools/consult_diverge.py" "$f"
}

cmd_adopt(){
  local bank="${PH_BRIEF_BANK:-$CT/BRIEF_BANK.md}"
  local f; f="$(ls -t "$R/consult_${KEY}_r"*.md 2>/dev/null | head -1)"
  [ -z "$f" ] && { echo "nothing to adopt"; exit 1; }
  echo "Paste the SURVIVING findings (what verification confirmed), one per line. End with a lone '.' :"
  local lines=""
  while IFS= read -r l; do [ "$l" = "." ] && break; lines="$lines- $l\n"; done
  [ -z "$lines" ] && { echo "nothing entered"; exit 0; }
  grep -q "^## COMP:$KEY\$" "$bank" || printf '\n## COMP:%s\n' "$KEY" >> "$bank"
  python3 - "$bank" "$KEY" "$(printf "$lines")" "$(date -u +%F)" "$(basename "$f")" <<'PY'
import sys
bank,key,lines,day,src=sys.argv[1:6]
src_note="- (from a heterogeneous consult, %s, %s — VERIFIED locally before adoption; unverified claims were dropped)"%(day,src)
txt=open(bank,encoding="utf-8").read().split("\n")
out=[]; hdr="## COMP:%s"%key; done=False
for l in txt:
    out.append(l)
    if not done and l.strip()==hdr:
        out.extend(lines.rstrip("\n").split("\n")); out.append(src_note); done=True
open(bank,"w",encoding="utf-8").write("\n".join(out))
print("  ✓ adopted into %s under %s"%(bank,hdr))
PY
}

case "$CMD" in
  ask)    shift 2; cmd_ask "${1:-}" ;;
  panel)  shift 2; cmd_panel "${1:-}" ;;
  diverge) cmd_diverge ;;
  claims) cmd_claims ;;
  push)   shift 2; cmd_push "${1:-}" ;;
  adopt)  cmd_adopt ;;
  log)    [ -f "$LOG" ] && sed -n '1,200p' "$LOG" || echo "no dialogue yet for $KEY" ;;
  *)      echo "usage: consult.sh ask|claims|push|adopt|log <key> [text]" ;;
esac
