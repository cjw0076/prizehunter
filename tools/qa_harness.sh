#!/usr/bin/env bash
# qa_harness.sh — the release gate, runnable BY the agent itself (agile QA).
# Run before every push/release: `ph qa`. Exit 0 = shippable; non-zero = fix first.
# Gates: fresh-clone smoke · tool parse · trigger parity · template presence · secret scan.
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d /tmp/ph_qa.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
FAIL=0
say() { printf '%s\n' "$*"; }
gate() { # gate <name> <0|nonzero> [detail]
  if [ "$2" -eq 0 ]; then say "  ✅ $1"; else say "  ❌ $1${3:+ — $3}"; FAIL=$((FAIL+1)); fi
}

say "== ph qa — release gate =="

# 1. Fresh-copy smoke: setup.sh must succeed from a clean checkout (git-tracked files only)
SMOKE="$WORK/clone"
mkdir -p "$SMOKE"
if git -C "$PH_HOME" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$PH_HOME" archive HEAD 2>/dev/null | tar -x -C "$SMOKE" 2>/dev/null
else
  cp -r "$PH_HOME"/. "$SMOKE"/ 2>/dev/null
fi
( cd "$SMOKE" && bash setup.sh ) > "$WORK/setup.log" 2>&1
gate "fresh-clone setup.sh" $? "$(grep -m1 -iE 'error|cannot|No such' "$WORK/setup.log" || true)"
( cd "$SMOKE" && bash ph next ) > "$WORK/next.log" 2>&1
gate "ph next on fresh clone" $? "$(tail -1 "$WORK/next.log")"

# 2. Every tool parses (syntax)
BROKEN=""
for f in "$PH_HOME"/tools/*.sh "$PH_HOME"/ph "$PH_HOME"/setup.sh; do
  bash -n "$f" 2>/dev/null || BROKEN="$BROKEN $(basename "$f")"
done
for f in "$PH_HOME"/tools/*.py; do
  python3 -m py_compile "$f" 2>/dev/null || BROKEN="$BROKEN $(basename "$f")"
done
[ -z "$BROKEN" ]; gate "all tools parse (sh -n / py_compile)" $? "$BROKEN"

# 3. ph verbs reference tools that exist
MISSING=""
while read -r t; do
  [ -e "$PH_HOME/tools/$t" ] || MISSING="$MISSING $t"
done < <(grep -oE '\$T/[a-z_0-9]+\.(sh|py)' "$PH_HOME/ph" | sed 's|\$T/||' | sort -u)
[ -z "$MISSING" ]; gate "ph verbs → tools all present" $? "$MISSING"

# 4. Trigger entrypoints identical up to the one host-specific "> <Host> note:" line
strip_note() { grep -vE '^> (Claude|Codex|Gemini) note:' "$1"; }
if [ "$(strip_note "$PH_HOME/CLAUDE.md")" = "$(strip_note "$PH_HOME/AGENTS.md")" ] \
   && [ "$(strip_note "$PH_HOME/AGENTS.md")" = "$(strip_note "$PH_HOME/GEMINI.md")" ]; then
  gate "trigger files identical (minus host note)" 0
else
  gate "trigger files identical (minus host note)" 1 "CLAUDE/AGENTS/GEMINI.md diverged beyond host notes"
fi

# 5. Shipped seeds present (a fresh user must be able to boot)
SEEDS=0
for f in templates/portfolio_registry.tsv templates/RECON.md.template config.sh CONTROL_PLANE.md; do
  [ -e "$PH_HOME/$f" ] || { SEEDS=1; say "     missing seed: $f"; }
done
gate "seed files shipped" $SEEDS

# 6. Secret / PII scan on tracked files (never ship a credential)
LEAK="$(cd "$SMOKE" && grep -rInE '(api[_-]?key|token|password|secret)[\"'"'"']?\s*[:=]\s*[\"'"'"'][A-Za-z0-9_\-]{16,}|eyJ[A-Za-z0-9_-]{20,}\.' \
  --include='*.sh' --include='*.py' --include='*.md' --include='*.tsv' . 2>/dev/null \
  | grep -vE '(example|template|placeholder|YOUR_|<[A-Z_]+>|regex|pattern)' | head -5 || true)"
[ -z "$LEAK" ]; gate "no secrets in tracked files" $? "$(echo "$LEAK" | head -1)"

say ""
if [ "$FAIL" -eq 0 ]; then
  say "SHIPPABLE — all gates green. next → git push (or ph issue if a gate keeps failing)"
else
  say "$FAIL gate(s) failing — fix before release. Unfixable? → ph issue \"qa: <gate>\""
fi
exit "$FAIL"
