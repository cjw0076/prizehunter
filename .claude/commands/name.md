---
description: NAMING ORGAN — escape a stuck framing by NAMING it (name the rut → heterogeneous voices name the residual → witness gate → orthogonal frame). Args: <competition-key>
allowed-tools: Bash(*), Read(*), Edit(*)
---

# /name — the naming organ, as a slash function across claude + codex + agy

Founder axiom (2026-08-01): *"새로운 것을 창발해내는 데에는 '명명(naming)'과 의미부여에 있어. 단순히 데이터
속에만 매몰되지 않도록."* Emergence comes through **naming and meaning-attribution**, not immersion in the data.
This command is that organ, invoked as one token. It composes three heterogeneous surfaces — and their
heterogeneity is the whole point: a same-weights fork shares our blind spots and can only RENAME.

- **codex** and **agy** are the naming VOICES (stage 2): each proposes, from its own prior, a NAME for the
  phenomenon living in the residual — the thing the data shows that the current framing cannot see.
- **claude (you, main context)** is the witness JUDGE (stage 3): judgment does not delegate. You apply the
  anti-renaming gate yourself, because the voices proposed and the judge must be a different context.

## Run it — `$ARGUMENTS` is the competition key (e.g. `arc-whitebox-2026`)

1. **Fan out to the heterogeneous voices** (this also names the rut mechanically from our own record, which
   cannot fail even if every substrate is down):

   ```
   ./ph name $ARGUMENTS propose
   ```

   Then Read the produced `…/.runs/naming_$ARGUMENTS_r*.md`. If the PANEL HEALTH line says a voice DEGRADED
   (codex quota, agy rc≠0), say so plainly — a single-substrate name is a weak hypothesis, not a consensus.
   Never treat a silent lane as "no idea"; the mechanical RUT still stands.

2. **Judge — apply the witness gate yourself** (do NOT delegate this). For each named residual, rule it:
   - **RENAMING (reject, loudly)** if it reduces to one of the 3 nearest framings *we have already tried*
     (check the round file's attempt list) with nothing left over. Name which framing it collapses into.
   - **WITNESSED (keep)** only if it survives that reduction, leaves a residual invariant, AND carries ONE
     falsifiable predicted consequence with a <1h/one-box measurement. A name with no predicted consequence
     is a vibe — reject it.
   Rank survivors by (score explained × cheapness of the decisive test).

3. **Adopt the orthogonal frame** — write the #1 survivor so the next generation round reads it as a NEW
   framing, not a parameter:

   ```
   ./ph name $ARGUMENTS frame "<name>: <the falsifiable predicted consequence + its cheap decisive test>"
   ```

4. Report: the rut you were trapped in (named), the witnessed name adopted, the renamings you rejected and
   why, and the single cheap experiment that now settles it. If every candidate was a renaming, say that —
   an honest "still trapped, here is the name of the trap" beats a laundered new label.

Manual cross-check (optional): to hear one voice in isolation before trusting the panel, hit its own surface —
`codex exec --skip-git-repo-check "<the naming prompt>" </dev/null` or
`agy --dangerously-skip-permissions --model gemini-3.1-pro --effort high -p "<the naming prompt>"`.
