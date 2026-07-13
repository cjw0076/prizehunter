# Council — heterogeneous second opinion

A single model has a single set of blind spots. Asking the *same* model (or a fork of
it) to check its own work is a logic check, not a de-bias — same weights, same blind
spots, fake consensus. For any **keystone call**, PrizeHunter gets an independent read
from a *different* model and synthesizes.

## Use it

```bash
./ph council "Should we submit v4 (compliant, 0.99) or v5 (0.997 but lookup-suspect)?"
./ph council "Is this 0.83 ceiling real, or are we luck-mining the public LB?"
```

`council.sh` polls, in parallel, whichever heterogeneous models you actually have and
lays their answers side by side. The calling agent then synthesizes — and **verifies**,
because each model hallucinates differently.

## Members (auto-detected; absent ones skip)

| member | invoked as | good for |
|---|---|---|
| `codex`  | `codex exec` | bold divergence, independent 2nd implementation |
| `gemini` | `agy -p` / `gemini -p` | current facts / grounded search / does-X-exist |
| `nim`    | `nv ask <model>` | strong frontier reasoning, free tier |
| `ollama` | `ollama run <model>` | cheap/offline/private local read |
| `claude` | `claude -p` | careful synthesis (use as a member only if it's not the caller) |

Configure with env:
- `PH_COUNCIL_MEMBERS=codex,gemini,nim,ollama` — which to poll (default).
- `PH_NIM_MODEL`, `PH_OLLAMA_MODEL` — pick the specific model per channel.

If you have only one model, you have no de-bias lane — install at least one other
(Codex, Gemini/agy, NIM's `nv`, or a local ollama) before trusting keystone calls.

## When to convene the council (not every decision)

- **Submission selection** — which file/version is the final pick.
- **Strategy / research direction** — the campaign's winning lever.
- **A ceiling or impossibility claim** — before you accept "this is as good as it gets",
  have a different model try to refute it. A verdict that would end an ambition earns
  one adversarial re-examination first.
- **"What exists / SOTA / current best"** — route to a grounded-search member (gemini),
  never to memory.

## The rule

Verify their output (they hallucinate differently than you), *then* synthesize. Never
pass a council answer through unchecked. Same-weights agreement proves nothing; a
surviving disagreement is where the real signal is.
