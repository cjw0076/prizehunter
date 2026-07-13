# Portfolio Control Loop

Updated: 2026-06-08 KST

The self-sustaining system that (1) keeps **every** competition in one ranked
view, (2) drives each toward leaderboard rank-1 via an explicit "next lever",
and (3) guarantees all work becomes durable AIOS record assets — automatically,
even when an agent forgets to record.

This is the reusable backbone of the prize-hunting package. It sits above the
six-contest command tower and also pulls in the standalone DACON competitions
that previously lived outside the asset system.

## Why it exists (the two gaps it closes)

Audit 2026-06-08 found two structural leaks in the record-asset system:

1. **Coverage gap** — the most-advanced competitions
   can record work only in local ledgers
   and never enter the control-tower receipt /
   AIOS pipeline. Their IP (signal-ceiling proof, honest-CV, leak detection)
   was not being captured as a sellable asset.
2. **Freshness gap** — the AIOS asset loop only ran when someone manually
   invoked `autonomous_tick --record`. It froze at 2026-06-07 01:34 while real
   work (qwen polish, rapid deploy, ceiling campaigns) continued for ~2 days
   with zero receipts emitted.

The control loop makes recording a property of the system, not a step an agent
must remember.

## Components

| File | Role |
|---|---|
| `portfolio_registry.tsv` | **Single source of truth.** One row per competition: key, dir, ledger, metric, direction, best, rank1, progress, status, blocker, next_lever. |
| `tools/portfolio_scan.sh` | Renders `PORTFOLIO_STATUS.md`: unified leaderboard with **gap-to-#1** and **AIOS recording freshness** per competition. |
| `tools/aios_autocapture.sh` | For each competition whose ledger is newer than its last AIOS receipt, extracts the latest ledger section and records it as an asset receipt + AIOS packet (via the sanitizing `record_asset_receipt.sh` / `export_aios_packet.sh`). This is the "receipt-to-aios-packet for all contests" asset, now built. |
| `tools/portfolio_tick.sh` | Heartbeat: autocapture → scan. **Two triggers** so it never freezes: cron `0 */3 * * *` (time-based) AND a `SessionEnd` hook in `dacon/.claude/settings.json` (fires the instant any agent session in this repo ends). |
| `PORTFOLIO_STATUS.md` | Generated unified leaderboard (do not hand-edit). |

## Operating rules

1. **Registry is the contract.** After any work session on a competition, an
   agent updates that competition's row in `portfolio_registry.tsv`
   (`best`, `progress`, `status`, `blocker`, `next_lever`). Nothing else is
   required to be recorded by hand — AIOS capture is automatic.
2. **AIOS capture is automatic.** `portfolio_tick.sh` runs every 3h and on
   demand. Any ledger delta becomes a receipt + `aios_outbox/*.aios.md` packet.
   Agents *may* still record bespoke high-value assets manually; the loop only
   guarantees nothing is silently lost.
3. **Rank-1 is the objective.** `next_lever` is the single highest-leverage
   action toward public rank-1. The leaderboard sorts attention by `gap→#1`
   (numeric metrics) and `progress` (build-stage contests).
4. **Selection and pivot beat polishing.** Prizehunter naturally reuses existing
   artifacts and makes small edits, so it must guard against improving the
   wrong base. Before more polish, each active row's `next_lever` should state
   one of: why the current base is still the right base, what evidence would
   force a pivot, or the kill rule that stops further reuse. A tiny metric
   improvement is not enough when stability, eligibility, judge fit, or live
   transfer evidence gets worse.
5. **FOUNDER blockers stop cleanly.** Rows blocked on operator credentials are
   prefixed `FOUNDER:` — agents record the blocker and wait; they do not spin.
6. **Promotion to an external AIOS ledger is deliberate.** The loop writes to the local
   `aios_outbox/` staging only. Promoting a packet to a cross-repo AIOS
   ledger is a manual `export_aios_packet.sh --append-aios-ledger` step
   (draft-first / operator-override invariants).

## Daily / resume flow

```bash
cd <repo-root>
# see where everything stands + any recording gaps
cat competitions/control_tower/PORTFOLIO_STATUS.md
# force a refresh (also runs automatically every 3h)
./competitions/control_tower/tools/portfolio_tick.sh
# after working a competition, update its registry row, then tick
$EDITOR competitions/control_tower/portfolio_registry.tsv
```

## Adding a new competition

Append one row to `portfolio_registry.tsv` with a unique single-token `key`
(used to match AIOS receipts), the path to its ledger, and its metric/target.
The loop picks it up on the next tick — no code change needed. This is how the
package scales to the NEXT_RADAR queue.
