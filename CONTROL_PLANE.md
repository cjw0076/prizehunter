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
observe → drive → intervene → self-heal → reallocate → repeat
```
1. `tools/portfolio_tick.sh` — refresh board, record, deposit flywheel knowledge.
2. **Drive**: `tools/run_campaign.sh --key <K> --execute` for each GO money-comp (parallel via `tools/run_parallel.sh`).
3. **Intervene directly** on any blocked worker: dispatch the best agent to unblock,
   or fix it yourself in the worker's dir. Do NOT ask the user.
4. **Self-heal**: if a tool/stage errors, FIX THE SYSTEM — `tools/record_failure_learning.sh`,
   patch the tool, re-run, record the fix. (The system improves itself in-loop.)
   On an unrecoverable tool bug, file it: `tools/report_issue.sh` opens a GitHub issue.
5. **Visual polish gate**: for build/proposal/hackathon tracks, run `ph visual` before closeout.
6. **Reallocate**: `tools/assign_roles.sh` — shift effort to highest-EV; drop dead / no-prize.
7. Repeat.

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
