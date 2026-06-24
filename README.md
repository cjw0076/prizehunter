# PrizeHunter 🏆

**AI가 혼자 경진대회에 나가는 자율 시스템**

An autonomous AI competition hunting system. It discovers competitions, triages them for winnability, drives campaigns toward leaderboard #1, and learns from its own history — all without human intervention for most tasks.

> "새벽 3시에 자동으로 제출되는 AI" — 이게 브랜드다.

---

## What it does

- **Discovers** AI/data competitions across platforms (DACON, Kaggle, wevity...)
- **Triages** candidates by prize size, agent-winnability, deadline, eligibility
- **Drives campaigns** from RECON → BUILD → OPTIMIZE → SUBMIT
- **Routes** memory from past wins into new competition contexts
- **Sleeps and fine-tunes** — nightly LoRA training converts episodic logs into parametric memory
- **Influences** — publishes community posts, drafts social content per competition

---

## Quick start

```bash
git clone https://github.com/cjw0076/prizehunter
cd prizehunter
export CT=$(pwd)
bash setup.sh
./ph help
```

**First run:**
```bash
./ph next        # what to do right now
./ph status      # board overview
./ph discover    # find new competitions
```

---

## Architecture: 9-stage loop

```
DISCOVER → TRIAGE → RECON → BUILD → OPTIMIZE → SUBMIT → RECORD → LEARN → INFLUENCE ↺
```

See [`AUTONOMOUS_PRIZE_MACHINE.md`](AUTONOMOUS_PRIZE_MACHINE.md) for full spec.

---

## Tools

| Tool | Purpose |
|---|---|
| `ph` | Main CLI — 12 verbs covering all stages |
| `tools/discover_dacon.py` | Live DACON competition discovery |
| `tools/triage_competition.py` | Score + go/no-go verdict |
| `tools/plan_campaign.py` | Decompose competition → phases → objectives |
| `tools/run_campaign.sh` | One-touch campaign dispatch loop |
| `tools/memory_router.sh` | Retrieve past patterns for new RECON |
| `tools/format_finetune_pairs.py` | Format competition logs → LoRA training pairs |
| `tools/sleep_finetune.sh` | Nightly idle-detect → finetune → Ollama reload |
| `tools/mine_sessions.py` | Extract winning patterns from session logs |
| `tools/agent_dispatch.sh` | Route tasks to claude/codex/gemini/local agents |

---

## Memory system

**Three layers:**

1. **Episodic** — per-campaign `WORKLOG.md` + `RECON.md` (created during runs)
2. **Retrieval** — `tools/memory_router.sh --domain tabular --metric log_loss` pulls relevant past patterns before each new RECON
3. **Parametric (sleep)** — nightly LoRA fine-tune on Qwen3-8B converts logs into model weights

```
Campaign runs (episodic logs)
    ↓ [format_finetune_pairs.py]
Training pairs (JSONL)
    ↓ [sleep_finetune.sh — 2am cron, RTX GPU]
LoRA adapter (Qwen3-8B + peft)
    ↓ [Ollama]
prizehunter-instinct model → fast TRIAGE / RECON priming
```

Setup sleep fine-tuning cron:
```bash
pip install peft trl bitsandbytes accelerate datasets
# Add to crontab (2am daily):
0 2 * * * CT=/path/to/prizehunter bash tools/sleep_finetune.sh >> sleep/sleep.log 2>&1
```

---

## Design principles

**Prizehunter vs Influencer — different aesthetics:**

| Context | Target | Design |
|---|---|---|
| SNS / community posts | General audience | AI aesthetic OK — terminal, logs, weird is the brand |
| Competition submissions | Human judges | Must be human-centered — polished, warm, beautiful |

Judges are people. Treat every submission like a real product.

**Safety gates (never bypass):**
- External submission → founder-gated (prepare + notify, human triggers)
- No auto account signup / ToS acceptance
- Credentials in `.env` never committed

---

## Multi-agent routing

Works with any AI agent CLI:

```bash
# Route a task to the best available agent
bash tools/agent_dispatch.sh route --need "heavy NLP implementation"

# Hand off to another agent with fallback
AGENT=claude bash tools/agent_dispatch.sh --to codex --task "optimize the model" --escalate gemini,claude
```

See `capabilities/ORCHESTRATION.md` for full routing rules.

---

## License

MIT — use freely, attribution appreciated.

---

*Built by [@cjw0076](https://github.com/cjw0076) · "튀어나온 돌 전략" — Liquid Death for AI competitions*
