#!/usr/bin/env bash
# PrizeHunter — setup script
# Sets up the environment for autonomous AI competition hunting

set -euo pipefail
PKGDIR="$(cd "$(dirname "$0")" && pwd)"
export CT="$PKGDIR"

echo "=== PrizeHunter Setup ==="
echo "Package root: $CT"

# 1. Required dirs
mkdir -p "$CT/campaigns" "$CT/context" "$CT/sleep" "$CT/sleep/adapters" \
         "$CT/session_corpus" "$CT/receipts" "$CT/EXIT/packages"

# 2. portfolio_registry.tsv
if [[ ! -f "$CT/portfolio_registry.tsv" ]]; then
  cp "$CT/templates/portfolio_registry.tsv" "$CT/portfolio_registry.tsv"
  echo "Created portfolio_registry.tsv from template"
fi

# 3. Python deps (core)
echo "Checking Python dependencies..."
python3 -c "import requests" 2>/dev/null || pip install requests -q
python3 -c "import anthropic" 2>/dev/null || echo "  Note: pip install anthropic for LLM features"

# 4. Sleep fine-tuning deps (optional, needs GPU)
echo ""
echo "Optional (sleep fine-tuning, needs NVIDIA GPU):"
echo "  pip install peft trl bitsandbytes accelerate datasets transformers"

# 5. Ollama check
echo ""
if command -v ollama &>/dev/null; then
  echo "Ollama: $(ollama --version 2>/dev/null || echo 'found')"
  echo "  Recommended model: ollama pull qwen3:8b"
else
  echo "Ollama not found. Install from https://ollama.ai for local LLM features."
fi

# 6. ph CLI symlink
chmod +x "$CT/ph" "$CT/tools/"*.sh 2>/dev/null || true
chmod +x "$CT/tools/"*.py 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo "Next: export CT=$CT && ./ph help"
echo ""
bash "$CT/tools/ph_gates.sh" 2>/dev/null || true
