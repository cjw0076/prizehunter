# PrizeHunter

**An agent-agnostic autonomous system for AI/data competitions.** It discovers
competitions, drives them toward leaderboard #1, records everything as auditable
assets, gets a second opinion from a heterogeneous council, files its own bug
reports, and **gets smarter every round** — the learning from each competition
primes the next.

Whatever agent you drive it with — **Claude Code, Codex, or Gemini** — you are the
conductor. Everything is plain shell + files; no vendor is assumed.

## Quickstart

```bash
git clone https://github.com/cjw0076/prizehunter
cd prizehunter
bash setup.sh          # deps + config + registry from template
./ph help              # the whole control surface
./ph next              # ← the single next action when unsure
```

Then, in any agent, type the one word:

```
prizehunter
```

The agent boots the cockpit (`tools/prizehunter.sh`), becomes the **Strategist
control plane**, and runs the supervise loop with your CLI's native goal/loop
feature (Claude `/goal` or `/loop`, Codex goals, Gemini re-invoke). You watch; it
drives — surfacing only operator-gates (external submit / account ToS / spend).
Full protocol: [`CONTROL_PLANE.md`](CONTROL_PLANE.md).

## The `ph` front door (learn ~12 verbs, not 40 tools)

| verb | what it does |
|---|---|
| `ph discover` | refresh the competition catalog (KR + intl adapters) |
| `ph money` | ROI-rank — only competitions with real prizes |
| `ph plan <key> "<name>"` | decompose a competition into a campaign plan |
| `ph run <key> [--exec]` | drive one competition (dry-run unless `--exec`) |
| `ph submitted` | submission board + evidence audit |
| `ph tick` | the heartbeat: record + refresh + flywheel deposit |
| `ph settle close <key> …` | resolve a finished competition → postmortem + P&L + lessons |
| `ph council "<q>"` | heterogeneous second opinion (your claude/codex/gemini/local) |
| `ph issue "<title>"` | file a GitHub issue (agent-native self-reporting) |
| `ph doctor` | health-check the tools |

Every verb prints the suggested next step. `ph status` is the one dashboard.

## The loop

```
DISCOVER → TRIAGE → RECON → BUILD → OPTIMIZE → SUBMIT → RECORD → RESOLVE → SETTLE → LEARN ↺
```

## Three things that make it more than a loop

- **Council** — before a keystone call (which submission, which strategy), poll a
  *different* model and synthesize. Same-weights agreement is fake consensus.
  See [`COUNCIL.md`](COUNCIL.md).
- **Compounding intelligence** — every competition's postmortem, lessons, and
  predicted-vs-actual calibration feed the next one as **expert priming**, and
  triage weights **self-correct** from accumulated outcomes. It gets smarter, not
  just busier. See [`INTELLIGENCE.md`](INTELLIGENCE.md).
- **Self-reporting** — on an unrecoverable tool bug the control plane opens a
  GitHub issue itself (secrets auto-scrubbed), so the system's failures become
  fixable work instead of silent dead-ends.

## Optional power-ups (degrade gracefully if absent)

- **MemoryOS** knowledge flywheel — set `MEMOS_ROOT` to enable tacit→explicit
  memory deposit/recall; without it the machine still runs, just without the moat.
- **Local models** (ollama) for cheap/offline council members and nightly LoRA
  distillation of episodic logs into parametric memory (`tools/sleep_finetune.sh`).
- **`ph api`** — point `PH_API_BASE_URL` at your own deployed dashboard endpoint.

## Layout

```
ph, ph_next.sh, config.sh, setup.sh      # front door + config
CLAUDE.md / AGENTS.md / GEMINI.md        # the "prizehunter" trigger (per agent)
CONTROL_PLANE.md                         # full-auto protocol
tools/                                   # the engine (~60 tools)
templates/                               # registry + RECON templates
capabilities/                            # personas + orchestration
```

## Safety

Outward-facing/irreversible actions are **operator-gated**: external submission,
account signup, ToS acceptance, real-money spend. The agent recommends and
prepares; a human triggers. Every decision is recorded; secrets never land in
cards, receipts, or issues (tools scrub them).

---

Licensed for evaluation — see `LICENSE`.
