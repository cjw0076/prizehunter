#!/usr/bin/env bash
# vault_set.sh — store one credential the operator supplies, into a gitignored vault.
# The agent calls this AFTER eliciting exactly one needed value from the operator,
# so autonomy can resume. Never printed back, never committed (.vault/ is gitignored).
#
# usage: vault_set.sh KEY VALUE          # store literal
#        printf '%s' "$SECRET" | vault_set.sh KEY -   # store from stdin (no shell history)
#        vault_set.sh --list             # names only, never values
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
VAULT_DIR="$PH_HOME/.vault"; VAULT="$VAULT_DIR/identity.env"

if [ "${1:-}" = "--list" ]; then
  [ -f "$VAULT" ] && grep -oE '^[A-Za-z_][A-Za-z0-9_]*' "$VAULT" | sort -u || echo "(vault empty)"
  exit 0
fi
key="${1:-}"; val="${2:-}"
[ -n "$key" ] || { echo "usage: vault_set.sh KEY VALUE | KEY - (stdin) | --list"; exit 2; }
[ "$val" = "-" ] && val="$(cat)"
[ -n "$val" ] || { echo "no value given for $key"; exit 2; }

mkdir -p "$VAULT_DIR"; chmod 700 "$VAULT_DIR"
touch "$VAULT"; chmod 600 "$VAULT"
# upsert KEY=... (value never echoed)
tmp="$(mktemp)"; grep -v "^${key}=" "$VAULT" 2>/dev/null > "$tmp" || true
printf '%s=%s\n' "$key" "$val" >> "$tmp"
mv "$tmp" "$VAULT"; chmod 600 "$VAULT"
echo "stored $key in .vault/identity.env (600, gitignored) — value not shown. Autonomy for its gate can now resume."
