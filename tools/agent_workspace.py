#!/usr/bin/env python3
"""Prizehunter shared workspace for agent opinions, challenges, and decisions."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
WORKSPACE = CONTROL / "agent_workspace"
THREADS = WORKSPACE / "threads"
DECISIONS = WORKSPACE / "decisions"
INBOX = WORKSPACE / "inbox"
INDEX = WORKSPACE / "INDEX.tsv"
LATEST = WORKSPACE / "LATEST.md"
DECISION_LOG = WORKSPACE / "DECISIONS.md"
KST = timezone(timedelta(hours=9), "KST")

SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|"
    r"[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)[A-Z0-9_]*=)",
    re.IGNORECASE,
)


def now_stamp() -> str:
    return datetime.now(KST).strftime("%Y%m%dT%H%M%S%z")


def now_human() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9가-힣._-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-._")
    return slug[:96] or "thread"


def refuse_secrets(*values: str) -> None:
    for value in values:
        if value and SECRET_RE.search(value):
            raise SystemExit("refusing to write secret-looking value to agent workspace")


def mkdirs() -> None:
    for path in (WORKSPACE, THREADS, DECISIONS, INBOX):
        path.mkdir(parents=True, exist_ok=True)


def init_workspace(verbose: bool = True) -> None:
    mkdirs()
    readme = WORKSPACE / "README.md"
    if not readme.exists():
        readme.write_text(
            """# Prizehunter Agent Workspace

This is the global deliberation room for Codex, Claude, Gemini, local LLMs, and
future agents.

Use it for opinions that should survive beyond a single dispatch:

- proposals: candidate idea, route, build approach, visual direction
- critiques: why a proposal may lose, hidden judge intent, missing proof
- blockers: exact unresolved need and owner
- decisions: accepted route, parked route, founder gate, kill decision

Rules:

- no secrets, tokens, cookies, private raw exports, or account data
- no final external submission or ToS/account action without founder gate
- keep claims evidence-bound and link local artifacts when possible
- use campaign-local `COLLAB_WORKLOOP.md` for execution, this room for debate

Commands:

```bash
ph discuss init
ph discuss post --topic "motie-publicdata route" --kind proposal --agent codex --campaign 2026-motie-public-data --message "..."
ph discuss list
ph discuss show --topic "motie-publicdata route"
ph discuss decision --topic "motie-publicdata route" --agent codex --campaign 2026-motie-public-data --message "Accepted route: ..."
```
""",
            encoding="utf-8",
        )
    if not INDEX.exists():
        INDEX.write_text(
            "stamp\ttopic_slug\ttopic\tagent\tkind\tcampaign\tstatus\tthread\n",
            encoding="utf-8",
        )
    if not DECISION_LOG.exists():
        DECISION_LOG.write_text("# Agent Workspace Decisions\n", encoding="utf-8")
    if verbose:
        print(WORKSPACE)


def read_message(args: argparse.Namespace) -> str:
    if args.file:
        message = Path(args.file).read_text(encoding="utf-8").strip()
    else:
        message = (args.message or "").strip()
    if not message:
        raise SystemExit("missing --message or --file")
    return message


def append_index(stamp: str, slug: str, topic: str, agent: str, kind: str, campaign: str, status: str, thread: Path) -> None:
    rel = thread.relative_to(CONTROL)
    with INDEX.open("a", encoding="utf-8") as fh:
        fh.write(
            "\t".join(
                [
                    stamp,
                    slug,
                    topic.replace("\t", " "),
                    agent.replace("\t", " "),
                    kind,
                    campaign.replace("\t", " ") or "-",
                    status,
                    str(rel),
                ]
            )
            + "\n"
        )


def post(args: argparse.Namespace, decision: bool = False) -> None:
    init_workspace(verbose=False)
    topic = args.topic.strip()
    agent = args.agent.strip()
    campaign = (args.campaign or "").strip()
    kind = "decision" if decision else args.kind
    status = args.status
    message = read_message(args)
    refuse_secrets(topic, agent, campaign, kind, status, message)

    stamp = now_stamp()
    human = now_human()
    slug = safe_slug(topic)
    thread = THREADS / f"{slug}.md"
    if not thread.exists():
        thread.write_text(
            f"# Thread: {topic}\n\n- created: {human}\n- slug: `{slug}`\n\n",
            encoding="utf-8",
        )

    entry = f"""## {human} — {agent} — {kind}

- campaign: {campaign or "-"}
- status: {status}

{message}

"""
    with thread.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    LATEST.write_text(f"# Latest Agent Workspace Post\n\n{entry}", encoding="utf-8")
    append_index(stamp, slug, topic, agent, kind, campaign, status, thread)

    if decision:
        decision_file = DECISIONS / f"{stamp}_{slug}.md"
        decision_file.write_text(f"# Decision: {topic}\n\n{entry}", encoding="utf-8")
        with DECISION_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {human} — {topic}\n\n{entry}")

    print(thread.relative_to(CONTROL))


def list_posts(args: argparse.Namespace) -> None:
    init_workspace(verbose=False)
    rows = INDEX.read_text(encoding="utf-8").splitlines()[1:]
    rows = rows[-args.limit :]
    if not rows:
        print("no posts")
        return
    print("stamp\tkind\tstatus\tcampaign\tagent\ttopic\tthread")
    for row in reversed(rows):
        fields = row.split("\t")
        if len(fields) < 8:
            continue
        stamp, _slug, topic, agent, kind, campaign, status, thread = fields[:8]
        print(f"{stamp}\t{kind}\t{status}\t{campaign}\t{agent}\t{topic}\t{thread}")


def show(args: argparse.Namespace) -> None:
    init_workspace(verbose=False)
    slug = safe_slug(args.topic)
    thread = THREADS / f"{slug}.md"
    if not thread.exists():
        raise SystemExit(f"thread not found: {slug}")
    sys.stdout.write(thread.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    p_post = sub.add_parser("post")
    p_post.add_argument("--topic", required=True)
    p_post.add_argument("--agent", default="unknown")
    p_post.add_argument("--campaign", default="")
    p_post.add_argument("--kind", choices=["proposal", "critique", "blocker", "note", "vote"], default="note")
    p_post.add_argument("--status", choices=["open", "accepted", "rejected", "parked", "blocked", "done"], default="open")
    p_post.add_argument("--message", default="")
    p_post.add_argument("--file", default="")

    p_decision = sub.add_parser("decision")
    p_decision.add_argument("--topic", required=True)
    p_decision.add_argument("--agent", default="unknown")
    p_decision.add_argument("--campaign", default="")
    p_decision.add_argument("--status", choices=["accepted", "rejected", "parked", "blocked", "done"], default="accepted")
    p_decision.add_argument("--message", default="")
    p_decision.add_argument("--file", default="")

    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=20)

    p_show = sub.add_parser("show")
    p_show.add_argument("--topic", required=True)

    args = ap.parse_args()
    if args.cmd == "init":
        init_workspace()
    elif args.cmd == "post":
        post(args)
    elif args.cmd == "decision":
        post(args, decision=True)
    elif args.cmd == "list":
        list_posts(args)
    elif args.cmd == "show":
        show(args)


if __name__ == "__main__":
    main()
