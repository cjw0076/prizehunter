# Control Plane — the "prizehunter" full-auto experience

The user types **`prizehunter`** in any CLI agent and then just watches. The agent
becomes the autonomous control plane: it drives every money competition toward #1,
handles blocks **directly** (the agent, not the human), self-heals the system, and
surfaces to the human ONLY irreducible operator-gates. Full automation.

## What the agent does on `prizehunter`

1. **Boot the cockpit**: `bash tools/prizehunter.sh` → board, role assignments
   (needs/gaps), worker windows.
2. **Assume the Strategist persona** (`capabilities/personas/strategist.md`).
3. **Enter the supervise loop using the CLI's native loop/goal feature** — this is
   what keeps it running as a control plane:
   - **Claude Code**: `/goal "run prizehunter: drive all GO money-competitions to #1, autonomously"` (a Stop-hook keeps it working until done) — or `/loop 30m` to tick on an interval.
   - **Codex**: set a goal (config `goals=true`); the goal chain supervises.
   - **Gemini/others**: re-invoke `prizehunter` per cycle.

## The loop (agent acts directly every tick — never defers to the user)

```
observe → drive-to-#1 → intervene → self-heal → reallocate → repeat
```
This is a **GOAL loop, not a supervise loop**: each competition keeps looping until it
reaches **rank #1**, an **adversarially-verified honest ceiling**, or its **deadline** —
nothing else stops it.

1. `tools/portfolio_tick.sh` — refresh board, record, deposit flywheel knowledge.
2. **Drive to #1** — the loop itself is competition-shaped, not fixed:
   - **First design it**: `ph goal --design <key>` detects the archetype
     (leaderboard-classification/regression · code-submission · rl-agentic · timeseries ·
     judged) and proposes a tailored loop — its goal/termination, per-cycle levers, slot
     policy, and ceiling test. YOU read the competition's RECON/data and adapt it to its
     specifics (odd metric, a leak, an external-data rule, a judging rubric, slot count),
     then save the tailored spec. A judged/creative competition gets a judge-fit loop with
     no numeric #1; a leaderboard one gets a gap-closing loop; a code-submission one gates
     on a reproduced offline scorer — each different by design.
   - **Then drive that designed loop**: `ph goal <key>` returns the verdict against THIS
     competition's own spec, tuned to its metric:
   - `PUSH`  → keep improving: `ph inherit <key>` (past approaches) → `ph council` (next lever) →
     optimize toward the winning lever → submit → re-verdict. Repeat until the gap closes.
   - `CEILING?` (stalled N cycles) → do **not** stop yet: `ph council "honest ceiling or luck-mining?"`
     + check the live LB; if teams sit above your best, keep pushing. Stop only if it survives.
   - `AT_#1`  → bank it (`ph settle close`), extract the winning approach (`ph ontology`), move on.
   - `ph goal --board` shows every competition's verdict at a glance.
   (`run_campaign.sh`/`run_parallel.sh` execute the actual drive work each cycle.)
3. **Intervene directly** on any blocked worker: dispatch the best agent to unblock,
   or fix it yourself in the worker's dir. Do NOT ask the user.
4. **Self-heal**: if a tool/stage errors, FIX THE SYSTEM — `tools/record_failure_learning.sh`,
   patch the tool, re-run, record the fix. (The system improves itself in-loop.)
   On an unrecoverable tool bug, file it: `tools/report_issue.sh` opens a GitHub issue.
5. **Visual polish gate**: for build/proposal/hackathon tracks, run `ph visual` before closeout.
6. **Reallocate**: `tools/assign_roles.sh` — shift effort to highest-EV; drop dead / no-prize.
7. Repeat.

## Autonomous tool selection — no human names the tool

Every tick, YOU read the situation and pick the right tool yourself. The user never
says "run ph council" or "use ph inherit" — you infer it from the signal. Follow this
map (and compose freely; `ph help` is the full surface, `ph next` is the mechanical hint):

| signal you observe | tool you reach for, unprompted |
|---|---|
| entering / planning a new competition | `ph inherit <key>` (inherit proven approaches from the ontology) → `ph gap` → `ph plan` |
| a keystone call (which submission, strategy, a ceiling/impossibility claim) | `ph council "…"` — get a heterogeneous read BEFORE accepting; same-weights = fake consensus |
| the approach feels stale / ideas exhausted | `ph creative "<topic>"` (wild framings before building) |
| a credential / web-login gate blocks the task | `ph onboard <gate>` → `ph vault` / `ph session --site <s>` (turn a login into a token) |
| you need another agent's capability | `ph route "<need>"` → `ph dispatch <agent> "<task>"` |
| a competition resolved / results are out | `ph results` → `ph settle close <key> …` → `ph ontology` (learn) → `ph calibrate` |
| a tool/stage errored and you couldn't self-heal it | `ph issue "<title>"` (file it) |
| genuinely unsure what's next | `ph next` |

Rule: a human does not choose the tool. Each cycle you read the signals (registry
state, open gates, pending results, blocked workers) and select + run the fitting
tool on your own. An explicit human instruction is only ever an override, not the
normal path. This is what "hands-off" means: the operator watches; you orchestrate.

## The ONLY things surfaced to the human (operator-gates)

Irreducible, outward-facing, or PII/spend: external-platform submission auth,
account signup / ToS acceptance, real-money spend approval. Surface each as one
line, then keep working everything else. Nothing else interrupts the automation.

### Submission-confirm protocol (standard)

When a competition's submission materials are **complete**, do NOT submit
externally on the operator's behalf without confirmation. Package + notify first:

```
tools/package_submission.sh --key <K>          # zip materials + auto SUBMISSION_GUIDE.md (≤25MB)
tools/notify_founder.sh --key <K> --zip <z> --guide <g> --dday <D-NN>
```

`notify_founder.sh` reads the operator's contact from `.vault/identity.env`
(`OPERATOR_EMAIL`, and `SMTP_APP_PASSWORD` for real SMTP send; otherwise it writes
a draft-request the agent turns into an email draft). Then **wait for the operator's
confirmation**; the operator uploads to the external portal. Everything else stays
fully autonomous. (Configure your own contact in `.vault/identity.env`; nothing is
hardcoded.)

## Money discipline (always on)

Only competitions with a verified prize run; discovery + triage drop
zero-prize/practice automatically. The control plane never spends effort on unpaid
competitions.

## Self-healing = the system fixes its own failure points

A failed stage is not a dead end — it is a system bug to patch. The control plane
records the failure, edits the offending tool/script, re-runs, records the fix as an
asset, and on an unrecoverable bug opens a GitHub issue (`tools/report_issue.sh`).
Over time the machine has fewer failure points. This is why you can leave it running.
