# Setup Gates — how much runs unattended, and what each credential unlocks

PrizeHunter's principle: **the agent does everything it can on its own, and asks
you for a credential ONLY at the moment a gate actually blocks the work you
requested — just that one thing, nothing more.** No upfront wall of forms.

```
./ph gates            # honest self-diagnosis: what's autonomous right now
./ph onboard [gate]   # the agent asks for only the needed credential(s)
./ph vault KEY VALUE  # store one supplied credential (gitignored, chmod 600)
```

## Always autonomous (no credential, ever)

`BUILD · RECORD · SETTLE · CALIBRATE · council synthesis · RESULT-check on public
pages (Devpost winners, public leaderboards)`. This is the bulk of the work.

## Gates you can fill to widen autonomy

| gate | fill it with | then autonomous |
|---|---|---|
| **DACON submit** | your DACON API token → `ph vault DACON_TOKEN <t>` | ✅ fully unattended (token API, no login gate) |
| **Kaggle submit** | `~/.kaggle/kaggle.json` + accept each comp's rules once (web) | ✅ per accepted competition |
| **Council (de-bias)** | install any 1+ of: codex · gemini/agy · nv(NIM) · ollama · claude | ✅ heterogeneous 2nd opinion |
| **Web token capture** | `ph session --site <s>` — log in once, agent extracts the API token from the browser network/dev-tools layer | ✅ that platform's API becomes agent-driven (token stored in vault) |
| **Issue self-report** | `gh auth login` (+ `PH_ISSUE_REPO`) | ✅ `ph issue` files bugs |
| **MemoryOS flywheel** | `export MEMOS_ROOT=/path` (optional) | ✅ compounding memory |

**Rule of thumb:** token-API platforms (DACON) can be *fully unattended*. Web-login
platforms (Kaggle, Devpost) become autonomous only once you either accept the
rules yourself once, or hand the agent a logged-in browser session.

## Web token capture — collapsing the login gate

Web platforms (DACON, Kaggle, portals) gate submission behind a browser login. `ph session`
collapses that to a single human login: you log in once (`--headed`) or supply creds
(`--creds`), and the agent reads the auth token off the browser's network/dev-tools layer
(the `Authorization: Bearer <JWT>` an XHR sends, or a JWT in localStorage/cookies), stores it
in `.vault`, and verifies it against the API. After that, the platform's API is agent-driven —
DACON-style token APIs then run fully unattended. Add your own site by extending `SITES` in
`tools/session_capture.py`.

## Structurally cannot be automated — always you

⛔ **account signup · 2FA / phone-SMS verification · CAPTCHA · the final approval of
an external submission · real-money spend.** These exist specifically to require a
human; the agent surfaces them as one-line gates and keeps working everything else.
This is by design, and honest — a product that claims to automate these is lying.

## How the just-in-time ask works

1. You run something (`ph run <comp>`, or just type `prizehunter`).
2. The agent hits a gate — say, DACON submit with no token.
3. It runs `ph onboard dacon`, reads you the single NEED block (what · why · how to
   get it · where it goes), and asks for that one value.
4. You paste it once. The agent stores it with `ph vault` (gitignored, 600) and
   **resumes autonomously** — it won't ask again, and it never asked for anything
   you didn't need.

The goal is not "zero human" — it's "human touches the irreducible minimum, once."
