# Autonomous Multi-Domain Prize Machine

The end-state system: a self-running loop that **discovers** competitions across
any domain (bio, industrial, finance, vision, NLP, ...), **triages** them for
agent-winnability, **enters and drives** each toward leaderboard #1, **prepares
submission**, and **records** everything as AIOS assets — while continuously
**learning from its own session logs**. **Agent-agnostic**: any CLI agent
(claude/codex/gemini/qwen/kimi/local) can be the conductor and dispatch to the
others via the capability registry + dispatch bus (`capabilities/` +
`tools/agent_dispatch.sh`). No single vendor is assumed to orchestrate — whoever
the buyer/user runs as "main" drives it.

This is the asset a buyer of the operation underwrites (see `EXIT/`). The loop's
value compounds because every run mines its own logs into better priming.

## The 9-stage loop (INFLUENCE added)

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  (9) INFLUENCE ◄── 튀어나온 돌 전략: 시각+감성 콘텐츠 → 커뮤니티 존재감  │
 │      ▲  daker.ai/DACON 포스트·YouTube·X·Instagram·Threads 자동화         │
 │  (8) LEARN  ◄── mine_sessions.py distills winning patterns ─────────┐   │
 │      ▲                                                              │   │
 │  (1) DISCOVER → (2) TRIAGE → (3) GAP+RECON → (4) BUILD → (5) OPTIMIZE│ │
 │   scheduled     go/no-go      data        agents     to rank-1      │   │
 │   multi-domain  scorer        semantics   build      campaign       │   │
 │   fetch                                                             ▼   │
 │                          (7) RECORD ◄── (6) SUBMIT [⛔ founder-gated]  │
 │                          AIOS auto-capture    prepare, then approve     │
 └──────────────────────────────────────────────────────────────────────────┘
```

**Stage 9 (INFLUENCE)** — 인플루언서 파이프라인:
- **핵심 전략**: "튀어나온 돌" — 남들과 다름 + 노력 가시화 (Liquid Death 방식)
- **브랜드 컨셉**: "AI가 혼자 경진대회에 나가는 시스템" — 이상하고, 따라하기 어렵고, 숫자로 증명됨
- **자동화**: daker.ai·DACON API로 대회 참가 즉시 커뮤니티 포스팅
- **시각 자산**: 점수 올라가는 순간, 터미널 미학, 1.0000 달성 순간
- **Founder 채널**: YouTube·X·Instagram·Threads 초안 생성 → Founder 게시
- 상세 전략: `campaigns/influencer/BRAND_STRATEGY.md`

| # | Stage | Runs on | Input → Output | Plugs into |
|---|---|---|---|---|
| 1 | **Discover** | scheduler (cron) | domain sources → `candidates.tsv` | extends `monitoring/check_prizes_weekly.sh`, `NEXT_RADAR.md` |
| 2 | **Triage** | Claude (cheap/scout) | candidate → go/no-go score + track | `tools/triage_competition.py` (built) → `portfolio_registry.tsv` intake |
| 3 | **Gap + Recon** | Codex creative + Claude recon | comp page + data → `PRIZE_GAP_LOOP.md` + `competition_brief.md` | `ph gap`, `playbook/METHODOLOGY.md` Phase 0 |
| 4 | **Build** | Claude main builder + Codex fallback | brief/gap loop → working artifact package | `MODEL_ROUTING.md`, `ph collab`, goal loops |
| 5 | **Optimize** | Claude+Codex+sidecars | artifact/pipeline → rank-1 or prize-winning package | honest-CV, signal-ceiling, deficiency closure |
| 6 | **Submit** | ⛔ **founder-gated** | best file → platform submission | `SUBMISSION_AUTOMATION.md`; auto-prepare, **manual approve** |
| 7 | **Record** | automatic | actions → receipts + AIOS packets | `portfolio_tick.sh` (cron + SessionEnd) |
| 8 | **Learn** | scheduler | logs+receipts → **MemoryOS** (tacit→explicit) → recall as expert priming | `mine_sessions.py` + `memoryos_bridge.sh` (deposit/recall); flywheel makes AIOS indispensable |

## Domain → discovery sources (stage 1)

| Domain | Platforms | Access |
|---|---|---|
| ML/data (general) | Kaggle, DACON, Zindi, AIcrowd, DrivenData, CodaLab | APIs / scrape; Kaggle+DACON have CLIs |
| Bio / medical | Grand Challenge, DREAM Challenges, biendata, Kaggle-health | mostly web; some need institutional signup |
| Finance | Numerai, Kaggle-finance, QuantConnect, CrunchDAO | Numerai has API; others scrape |
| Industrial / robotics | PHM Society, AIcrowd, ATEC, ICRA challenges | web; hardware-gated ones flagged no-go in triage |
| Hackathons / agents | Devpost, lablab.ai, MLH | Devpost has search; web |

Stage-1 fetcher writes one row per candidate: `name, platform, domain, url,
prize, deadline, metric, data_modality, external_data_policy, hardware_required`.
Network/API-key-bound fetchers are pluggable adapters; the loop runs whatever
adapters are configured and logs which were skipped (no silent gaps).

## How it plugs into Claude and Codex

- **Routing** (`MODEL_ROUTING.md`): Codex leads creative direction, hidden-intent
  mining, references, and deficiency discovery; Claude leads main artifact
  build/completion; Gemini/local/other agents challenge assumptions and unblock
  subproblems.
- **Gap loop** (`ph gap`): every serious campaign gets a contest-specific
  `PRIZE_GAP_LOOP.md` covering what judges/leaderboards actually need, how our
  approach is deficient, and what 120%+ evidence must be produced.
- **Dispatch form**: each stage is a prompt packet (`start_goal_loop.sh` already
  generates scout/diverge/builder/reviewer/ledger packets). A stage runs via
  `claude -p "<packet>"` or `codex exec "<packet>"`; output is captured, the
  registry row is updated, `portfolio_tick.sh` records it.
- **Self-improvement (stage 8)**: `mine_sessions.py` turns past transcripts into
  a winning-pattern corpus (decisions that moved score, failures that wasted
  time). The distilled corpus is injected as a preamble into stage 3–5 packets,
  so the machine gets better at each new competition. This is the moat — the
  logs are proprietary and compounding.

## Safety gates (DNA invariants — do not bypass)

1. **Auto-submit to external platforms is founder-gated.** Submitting is
   outward-facing and irreversible (counts against daily limits, public record).
   The loop *prepares* a submission + a one-line approval request; a human (or an
   explicit per-competition `AUTO_SUBMIT=1` flag the founder sets) triggers it.
   DACON daily-submit cron is the one pre-approved exception (founder enabled it).
2. **Recommendation-only** elsewhere: triage recommends, never auto-registers an
   account or accepts ToS on the founder's behalf.
3. **No silent caps**: every skipped adapter / dropped candidate is logged.
4. **Provenance**: every entered competition has a brief + receipts before build.
5. **Privacy**: no secrets in candidates/receipts; credential procedures only.

## Build sequence (what to implement, in order)

- [x] Stage 7 Record — `portfolio_tick.sh` (cron + SessionEnd hook). DONE.
- [x] Stage 8 Learn — `mine_sessions.py` corpus extractor. DONE (prototype).
- [x] Stage 2 Triage — `triage_competition.py` scorer. DONE (prototype).
- [x] Stage 1 Discover — `discover_dacon.py` (live, no auth) + `discover_all.sh` runner → triaged `DISCOVERY_REPORT.md`. DONE for DACON; Kaggle/Numerai pluggable (need keys).
- [x] Stage 3–5 campaign engine — `prize_gap_loop.py` (judge intent→deficiency→120% backlog) + `plan_campaign.py` (decompose→phases→sub-objectives→deliverables) + `run_campaign.sh` (loop-dispatch each to routed agent, dry-run default) + `make_presentation_kit.py` (slides/script/video-storyboard). DONE.
- [ ] Stage 6 Submit-prepare + approval queue (founder GO required to arm).
- [ ] Stage 8 feedback — inject mined corpus into stage 3–5 packets.
