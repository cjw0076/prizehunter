#!/usr/bin/env python3
"""Team-mode commands for Prizehunter.

This tool keeps team coordination append-only and dashboard-friendly. It writes
only non-secret operational metadata and comms messages.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
ROSTER = CONTROL / "TEAM_ROSTER.tsv"
TEAM_DOC = CONTROL / "TEAM_OPERATING_SYSTEM.md"
KST = timezone(timedelta(hours=9), "KST")

SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|"
    r"[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)[A-Z0-9_]*=|"
    r"010[- ]?\d{4}[- ]?\d{4})",
    re.IGNORECASE,
)


def now_stamp() -> str:
    return datetime.now(KST).strftime("%Y-%m-%dT%H%M")


def now_human() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower()).strip("-")
    return slug[:64] or "message"


def refuse_secrets(*values: str) -> None:
    for value in values:
        if value and SECRET_RE.search(value):
            raise SystemExit("refusing to write secret-looking value to team ledger")


def default_target() -> Path | None:
    env = os.environ.get("PH_TEAM_TARGET")
    candidates = [
        Path(env).expanduser() if env else None,
        ROOT.parent / "Dacon",
        ROOT.parent / "dacon-dashboard",
    ]
    for c in candidates:
        if c and (c / "site").exists() and (c / "comms").exists():
            return c.resolve()
    return None


def target_from(args: argparse.Namespace) -> Path:
    target = Path(args.target).expanduser().resolve() if args.target else default_target()
    if not target:
        raise SystemExit("No team dashboard checkout found. Set PH_TEAM_TARGET=/path/to/dashboard.")
    return target


def ensure_roster() -> None:
    if ROSTER.exists():
        return
    ROSTER.write_text(
        "agent\thuman_label\trole\troute_to\tstatus\tnotes\n"
        "prizehunter\tcontrol-plane\tstrategist\tportfolio routing and quality gates\tactive\tcreated by team_ops\n",
        encoding="utf-8",
    )


def read_roster() -> list[dict[str, str]]:
    ensure_roster()
    with ROSTER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write_roster(rows: list[dict[str, str]]) -> None:
    ensure_roster()
    fields = ["agent", "human_label", "role", "route_to", "status", "notes"]
    with ROSTER.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_message(
    target: Path,
    *,
    sender: str,
    to: str,
    competition: str,
    msg_type: str,
    topic: str,
    body: str,
) -> Path:
    refuse_secrets(sender, to, competition, msg_type, topic, body)
    sender_slug = slugify(sender)
    path = target / "comms" / sender_slug / f"{now_stamp()}-{slugify(topic)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"from: {sender_slug}\n"
        f"to: {to}\n"
        f"competition: {competition}\n"
        f"type: {msg_type}\n"
        f"ts: {datetime.now(KST).strftime('%Y-%m-%dT%H:%M')}\n"
        "---\n"
        f"{body.strip()}\n",
        encoding="utf-8",
    )
    return path


def mirror_discuss(kind: str, agent: str, campaign: str, topic: str, message: str, status: str = "open") -> None:
    cmd = [
        str(CONTROL / "ph"),
        "discuss",
        "post",
        "--topic",
        topic,
        "--kind",
        kind,
        "--agent",
        agent,
        "--campaign",
        campaign,
        "--status",
        status,
        "--message",
        message,
    ]
    try:
        subprocess.run(cmd, cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def cmd_init(args: argparse.Namespace) -> int:
    ensure_roster()
    target = target_from(args)
    for row in read_roster():
        agent = row.get("agent", "").strip()
        if agent:
            (target / "comms" / slugify(agent)).mkdir(parents=True, exist_ok=True)
            keep = target / "comms" / slugify(agent) / ".gitkeep"
            keep.touch(exist_ok=True)
    if args.message:
        body = (
            "Team-mode Prizehunter initialized.\n\n"
            f"- rules: `{TEAM_DOC.relative_to(ROOT)}`\n"
            "- each teammate writes only their own comms folder and run file\n"
            "- reviews must include evidence, counterargument, validation, and kill rule\n"
        )
        path = write_message(
            target,
            sender="prizehunter",
            to="all",
            competition="portfolio",
            msg_type="status",
            topic="team-mode-initialized",
            body=body,
        )
        print(path)
    print(TEAM_DOC)
    print("next -> ph team onboard/checkin/review/idea")
    return 0


def cmd_onboard(args: argparse.Namespace) -> int:
    values = [args.agent, args.human_label, args.role, args.route_to, args.status, args.notes]
    refuse_secrets(*values)
    rows = read_roster()
    updated = False
    for row in rows:
        if row.get("agent") == args.agent:
            row.update(
                {
                    "human_label": args.human_label,
                    "role": args.role,
                    "route_to": args.route_to,
                    "status": args.status,
                    "notes": args.notes,
                }
            )
            updated = True
            break
    if not updated:
        rows.append(
            {
                "agent": args.agent,
                "human_label": args.human_label,
                "role": args.role,
                "route_to": args.route_to,
                "status": args.status,
                "notes": args.notes,
            }
        )
    write_roster(rows)
    target = target_from(args)
    (target / "comms" / slugify(args.agent)).mkdir(parents=True, exist_ok=True)
    path = write_message(
        target,
        sender="prizehunter",
        to=args.agent,
        competition="portfolio",
        msg_type="handoff",
        topic=f"onboard-{args.agent}",
        body=(
            f"Onboarded `{args.agent}` as `{args.role}`.\n\n"
            f"- human_label: {args.human_label}\n"
            f"- best route: {args.route_to}\n"
            "- first loop: pull, read AGENTS.md, run `ph status`, then post `ph team checkin`.\n"
            "- write only your own comms folder and owned experiment files.\n"
        ),
    )
    print(ROSTER)
    print(path)
    print("next -> ph team review")
    return 0


def cmd_checkin(args: argparse.Namespace) -> int:
    body = (
        f"Cycle check-in by `{args.sender}` at {now_human()}.\n\n"
        f"Done: {args.done}\n\n"
        f"Next: {args.next}\n\n"
        f"Blocker: {args.blocker or 'none'}\n"
    )
    target = target_from(args)
    path = write_message(
        target,
        sender=args.sender,
        to=args.to,
        competition=args.competition,
        msg_type="status",
        topic=args.topic or f"{args.competition}-checkin",
        body=body,
    )
    print(path)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    refuse_secrets(args.body)
    body = (
        f"Review verdict: {args.verdict}\n\n"
        f"{args.body.strip()}\n\n"
        "Required shape: evidence, counterargument, cheapest validation, kill/park criterion.\n"
    )
    target = target_from(args)
    path = write_message(
        target,
        sender=args.sender,
        to=args.to,
        competition=args.competition,
        msg_type="challenge" if args.verdict == "challenge" else "review",
        topic=args.topic or f"{args.competition}-{args.verdict}-review",
        body=body,
    )
    mirror_discuss(
        "critique" if args.verdict == "challenge" else "note",
        args.sender,
        args.competition,
        args.topic or f"{args.competition} peer review",
        body,
        "open",
    )
    print(path)
    print("next -> addressed agent replies with ph team checkin or ph team review")
    return 0


def cmd_idea(args: argparse.Namespace) -> int:
    body = (
        f"Idea: {args.topic}\n\n"
        f"{args.body.strip()}\n\n"
        "Challenge request: attack this idea from another domain, define proof, and name the kill criterion.\n"
    )
    target = target_from(args)
    path = write_message(
        target,
        sender=args.sender,
        to=args.to,
        competition=args.competition,
        msg_type="idea",
        topic=args.topic,
        body=body,
    )
    mirror_discuss("proposal", args.sender, args.competition, args.topic, body, "open")
    print(path)
    print("next -> ph team review --verdict challenge")
    return 0


def cmd_message(args: argparse.Namespace) -> int:
    target = target_from(args)
    path = write_message(
        target,
        sender=args.sender,
        to=args.to,
        competition=args.competition,
        msg_type=args.type,
        topic=args.topic,
        body=args.body,
    )
    print(path)
    print("next -> commit/push in your team dashboard repo")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("init")
    p.add_argument("--target", default="")
    p.add_argument("--message", action="store_true", help="Also write a dashboard status message.")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("onboard")
    p.add_argument("--target", default="")
    p.add_argument("--agent", required=True)
    p.add_argument("--human-label", required=True, help="Non-private label only, not contact details.")
    p.add_argument("--role", required=True)
    p.add_argument("--route-to", required=True)
    p.add_argument("--status", default="active")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_onboard)

    p = sub.add_parser("checkin")
    p.add_argument("--target", default="")
    p.add_argument("--from", dest="sender", default=os.environ.get("AGENT", "prizehunter"))
    p.add_argument("--to", default="all")
    p.add_argument("--competition", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--done", required=True)
    p.add_argument("--next", required=True)
    p.add_argument("--blocker", default="")
    p.set_defaults(func=cmd_checkin)

    p = sub.add_parser("review")
    p.add_argument("--target", default="")
    p.add_argument("--from", dest="sender", default=os.environ.get("AGENT", "prizehunter"))
    p.add_argument("--to", default="all")
    p.add_argument("--competition", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--verdict", choices=["challenge", "approve", "park", "reject"], default="challenge")
    p.add_argument("--body", required=True)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("idea")
    p.add_argument("--target", default="")
    p.add_argument("--from", dest="sender", default=os.environ.get("AGENT", "prizehunter"))
    p.add_argument("--to", default="all")
    p.add_argument("--competition", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--body", required=True)
    p.set_defaults(func=cmd_idea)

    p = sub.add_parser("message")
    p.add_argument("--target", default="")
    p.add_argument("--from", dest="sender", default=os.environ.get("AGENT", "prizehunter"))
    p.add_argument("--to", default="all")
    p.add_argument("--competition", default="portfolio")
    p.add_argument("--type", default="status", choices=["result", "question", "decision", "status", "handoff", "challenge", "idea", "review"])
    p.add_argument("--topic", required=True)
    p.add_argument("--body", required=True)
    p.set_defaults(func=cmd_message)
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
