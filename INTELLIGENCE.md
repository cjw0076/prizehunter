# Compounding Intelligence — how PrizeHunter gets *smarter*, not just busier

A plain automation loop starts every cycle from zero: it re-derives, re-guesses,
repeats the same mistakes. PrizeHunter is built so that **each finished competition
raises the quality of the next one's inputs**. That is the difference between a loop
and a system that compounds.

## The closed learning loop

```
        ┌────────────────────────────────────────────────────────────┐
        │                                                            ▼
   run a competition ──▶ SETTLE (postmortem + lessons + calibration data)
        ▲                         │
        │                         ▼
   EXPERT PRIMING          knowledge store: results/LESSONS.md · OUTCOMES.tsv
   (next campaign          · memoryOS deposit · LEARNING_INDEX.md
    starts as an expert)          │
        │                         ▼
        └──────────  CALIBRATION self-correction (triage weights)  ◀──┘
```

## The three mechanisms

### 1. Knowledge accumulation (record, don't hold)
`ph settle close <key> --outcome … --evidence …` turns a finished competition into:
- a **postmortem** (why it won/lost — the binding constraint, not a safe excuse),
- a one-line **lesson** appended to `results/LESSONS.md`,
- an immutable **prediction-vs-actual** row in `OUTCOMES.tsv` (the calibration substrate),
- a **memoryOS deposit** (if `MEMOS_ROOT` set) so tacit knowledge becomes retrievable.

### 2. Expert priming (the next campaign starts smart)
A new campaign should never start blank. Before building, inject accumulated
expertise up front:
- `run_campaign.sh` already pulls `memoryos_bridge.sh recall` into an `EXPERTISE.md`
  priming block ("you are an expert") for each sub-objective.
- Extend `plan_campaign.py` to also fold in `results/LESSONS.md` and the outcomes of
  **similar past competitions** (same lane/metric) so the plan inherits what worked.
- The effect: the baseline *starting point* of each new competition rises over time.

### 3. Calibration self-correction (judgement improves)
`tools/calibration.py` reads `OUTCOMES.tsv` and measures how well the triage win%
predictions matched reality (Brier score, over/under-confidence). It emits a concrete
nudge for `triage_competition.py`'s win-probability priors. Feed it back each round →
the system's *judgement* gets measurably better, not just its throughput.

### 4. Parametric memory (optional, GPU)
`tools/sleep_finetune.sh` distills episodic logs into a LoRA adapter on a local model
nightly — turning experience into model weights. Optional (needs a GPU); the software
loop above compounds without it.

## How you know it's working (measurable)
- **Brier score** in `CALIBRATION_REPORT.md` trends down (predictions match outcomes).
- New competitions reach a **higher first-submission score** than earlier ones in the
  same lane (priming lifts the floor).
- `results/LESSONS.md` stops repeating the same lesson (a repeated lesson = friction =
  the priming isn't being read; fix the loop, not the model).

## Status in this build
Working now: `settle` → OUTCOMES/postmortem/lessons, `calibration.py`, memoryOS
deposit/recall, `sleep_finetune` scaffold. Deeper tuning (automatic priming injection
into every plan, closed-loop triage weight updates) is intentionally left as the first
thing to grow with real usage — the hooks are in place.
