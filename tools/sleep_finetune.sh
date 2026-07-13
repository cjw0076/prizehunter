#!/usr/bin/env bash
# sleep_finetune.sh — nightly idle-detect → format pairs → LoRA finetune → Ollama reload
# Cron: 0 2 * * * /path/to/sleep_finetune.sh >> /path/to/sleep.log 2>&1
#
# Requires: pip install peft trl bitsandbytes accelerate
# GPU: RTX 5090 (~15-25 min per run on Qwen3-8B with LoRA rank=16)
#
# Architecture:
#   session logs (episodic) → training pairs → LoRA finetune → GGUF → Ollama model
#   "prizehunter-instinct" served at localhost:11434 for fast TRIAGE/RECON priming

set -euo pipefail
# cron PATH lacks miniconda — without this `conda` never resolves and the finetune
# silently fell back to system python3 (no trl) every night
[ -d "$HOME/miniconda3/bin" ] && export PATH="$HOME/miniconda3/bin:$PATH"
CT="$(cd "$(dirname "$0")/.." && pwd)"
SLEEP_DIR="$CT/sleep"
LOG="$SLEEP_DIR/sleep.log"
ADAPTER_DIR="$SLEEP_DIR/adapters"
BASE_MODEL="Qwen/Qwen3-8B"
OLLAMA_MODEL_NAME="prizehunter-instinct"
CONDA_ENV="dacon_vlm"
PYTHON="$(conda run -n $CONDA_ENV which python 2>/dev/null || echo python3)"
mkdir -p "$SLEEP_DIR" "$ADAPTER_DIR"

log() { echo "[$(TZ=Asia/Seoul date '+%H:%M KST')] $*" | tee -a "$LOG"; }

# 1. Idle check: no nohup jobs writing to logs in last 10 min
is_idle() {
  local recent
  recent=$(find "$CT" -name "run_*.log" -newer "$CT/sleep/.idle_stamp" 2>/dev/null | wc -l)
  touch "$CT/sleep/.idle_stamp"
  [[ "$recent" -eq 0 ]]
}

if ! is_idle; then
  log "System busy — skip sleep finetune"
  exit 0
fi

log "=== Sleep finetune start ==="

# 2. Format training pairs
log "Formatting training pairs..."
$PYTHON "$CT/tools/format_finetune_pairs.py" --out "$SLEEP_DIR/training_pairs.jsonl" --min-pairs 10
PAIR_COUNT=$(wc -l < "$SLEEP_DIR/training_pairs.jsonl" 2>/dev/null || echo 0)
if [[ "$PAIR_COUNT" -lt 10 ]]; then
  log "Not enough pairs ($PAIR_COUNT) — abort"
  exit 0
fi
log "Pairs: $PAIR_COUNT"

# 3. LoRA fine-tune (requires peft + trl) — must run in the conda env, not bare python3
"$PYTHON" - <<'PYEOF'
import sys
try:
    from trl import SFTTrainer, SFTConfig
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    import torch, json
    from datasets import Dataset
    from pathlib import Path
except ImportError as e:
    print(f"Missing deps: {e}\nRun: pip install peft trl bitsandbytes datasets")
    sys.exit(1)

CT = Path(__file__).parent.parent  # called from sleep dir context
SLEEP_DIR = Path(__file__).parent.parent / "sleep"
BASE_MODEL = "Qwen/Qwen3-8B"
ADAPTER_OUT = SLEEP_DIR / "adapters" / "latest"

pairs_path = SLEEP_DIR / "training_pairs.jsonl"
data = [json.loads(l) for l in pairs_path.read_text().splitlines() if l.strip()]
dataset = Dataset.from_list(data)

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
print(f"Loading {BASE_MODEL}...")
model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, quantization_config=bnb, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

lora_cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32, lora_dropout=0.05,
                      target_modules=["q_proj", "v_proj"])
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    args=SFTConfig(output_dir=str(ADAPTER_OUT), num_train_epochs=2, per_device_train_batch_size=2,
                   gradient_accumulation_steps=4, learning_rate=2e-4, fp16=False, bf16=True,
                   logging_steps=10, save_strategy="epoch", report_to="none"),
)
trainer.train()
model.save_pretrained(str(ADAPTER_OUT))
tokenizer.save_pretrained(str(ADAPTER_OUT))
print(f"Adapter saved → {ADAPTER_OUT}")
PYEOF

log "LoRA adapter saved → $ADAPTER_DIR/latest"

# 4. Convert LoRA → GGUF → refresh the Ollama model (guarded: skips with a log if
#    the convert script / gguf pkg / ollama base model are missing — never blocks step 5)
LLAMA_CPP="${LLAMA_CPP:-$HOME/tools/llama.cpp}"
if [ -f "$LLAMA_CPP/convert_lora_to_gguf.py" ] && ollama list 2>/dev/null | grep -q '^qwen3:8b'; then
  if "$PYTHON" "$LLAMA_CPP/convert_lora_to_gguf.py" "$ADAPTER_DIR/latest" \
        --base "$BASE_MODEL" --outfile "$SLEEP_DIR/adapter.gguf" --outtype f16 >>"$LOG" 2>&1; then
    printf 'FROM qwen3:8b\nADAPTER %s\n' "$SLEEP_DIR/adapter.gguf" > "$SLEEP_DIR/Modelfile"
    if ollama create "$OLLAMA_MODEL_NAME" -f "$SLEEP_DIR/Modelfile" >>"$LOG" 2>&1; then
      log "Ollama model refreshed: $OLLAMA_MODEL_NAME (adapter.gguf)"
    else
      log "ollama create failed — adapter still usable via transformers"
    fi
  else
    log "LoRA→GGUF conversion failed — adapter still usable via transformers"
  fi
else
  log "GGUF step skipped (need $LLAMA_CPP/convert_lora_to_gguf.py + ollama qwen3:8b)"
fi

# 5. Register adapter path for TRIAGE/RECON to use
echo "$ADAPTER_DIR/latest" > "$SLEEP_DIR/current_adapter.txt"
log "=== Sleep finetune complete ==="
log "Adapter registered for TRIAGE/RECON use via: cat $SLEEP_DIR/current_adapter.txt"
