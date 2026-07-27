#!/usr/bin/env bash
# kaggle_auth.sh — make the kaggle CLI use the credential saved in the LOCAL vault.
# Nothing is exfiltrated; the token stays in .vault (gitignored, chmod 600).
# Resolution: kaggle reads KAGGLE_API_TOKEN as a FILE PATH (kagglesdk get_access_token_from_env).
#   usage:  source tools/kaggle_auth.sh        # export for the current shell
#           tools/kaggle_auth.sh restore        # rewrite ~/.kaggle/access_token from the vault copy
set -u
PH_HOME="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VTOK="$PH_HOME/.vault/access_token"
if [ "${1:-}" = "restore" ]; then
  mkdir -p "$HOME/.kaggle" && cp -p "$VTOK" "$HOME/.kaggle/access_token" && chmod 600 "$HOME/.kaggle/access_token"
  echo "restored ~/.kaggle/access_token from vault"
else
  export KAGGLE_API_TOKEN="$VTOK"        # CLI reads token from this vault path
fi
