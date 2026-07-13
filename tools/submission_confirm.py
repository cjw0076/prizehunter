#!/usr/bin/env python3
"""Submission confirmation system checks.

This tool separates public-safe submission routes from private login material.
It never prints stored secret values.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
RUNBOOK = CONTROL / "SUBMISSION_CONFIRMATION_RUNBOOK.md"
BOARD = CONTROL / "SUBMISSION_BOARD.md"
VAULT = Path(os.environ.get("PH_LOGIN_VAULT", "~/.config/prizehunter/secrets/LOGIN_VAULT.md")).expanduser()

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9._-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.I),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|secret|token|api[_-]?key|cookie)\s*[:=]\s*\S{8,}"),
]

REQUIRED_SECTIONS = [
    "Devpost",
    "Gmail",
    "Culture.go.kr / Digicon",
    "AI Software / AI Case",
    "Kaggle",
    "AIcrowd",
    "DACON",
    "NYPC / Nexon",
    "Numerai",
    "Datacontest.kr",
]

VAULT_TEMPLATE = """# Prizehunter Private Login Vault

_local-only, chmod 600_

This file is intentionally outside the repo. It may contain sensitive login
material if the founder explicitly chooses to store it here. Do not copy this
file into GitHub, AIOS receipts, MemoryOS public packets, issue reports, or
prompt artifacts.

Recommended use:

- Store exact values here only if the founder approves local plaintext storage.
- Otherwise store `password_manager_item` names and keep the real secret in a
  password manager.
- Keep screenshots, receipt ids, and non-secret confirmation steps in the repo
  runbook: `control_tower/SUBMISSION_CONFIRMATION_RUNBOOK.md`.

## Portal Entries

### Devpost

- purpose: rapid / find-evil / splunk / uipath / qwen submissions
- login_url: `https://devpost.com/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- recovery_email_or_phone_hint:
- confirmation_route:
  - open relevant hackathon manage page
  - confirm target project title shows `SUBMITTED`
- notes:

### Gmail

- purpose: Devpost confirmation email lookup, organizer notices
- login_url: `https://mail.google.com/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- confirmation_route:
  - search by message id or subject from repo runbook
- notes:

### Culture.go.kr / Digicon

- purpose: MOCT receipt lookup and AIC/Digicon contests
- login_url: `https://www.culture.go.kr/digicon/pages/contest_3.do`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- receipt_lookup_fields:
  - participant_mode:
  - founder_name:
  - phone_last4:
  - receipt_password:
- confirmation_route:
  - open receipt lookup
  - select the correct participant/team mode
  - confirm title and submitted zip filename
- notes:

### AI Software / AI Case

- purpose: AI Case Contest submitted package verification
- login_url: `https://ai.software.kr/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- confirmation_route:
  - open contest application/completion area
  - confirm completion page and attached PDF/package
- notes:

### Kaggle

- purpose: Orbit Wars; future ARC/NeuroGolf/other Kaggle submissions only after rules/access gates
- login_url: `https://www.kaggle.com/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- kaggle_cli_credentials_path:
- confirmation_route:
  - `kaggle competitions submissions -c orbit-wars`
  - confirm submission ids and public scores from repo runbook
- notes:

### AIcrowd

- purpose: ARC White-Box submission monitoring
- login_url: `https://www.aicrowd.com/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- api_key_path:
- confirmation_route:
  - open challenge submissions page
  - confirm submission id from repo runbook
- notes:

### DACON

- purpose: <competition key> score and submission monitoring
- login_url: `https://dacon.io/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- dacon_token_path:
- confirmation_route:
  - open relevant competition submissions/leaderboard pages
  - compare with campaign ledger and artifact ids
- notes:

### NYPC / Nexon

- purpose: NYPC Master registration, Arena team, practice assets, future submit/replay upload
- login_url: `https://new.nypc.co.kr/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- eligibility_fields:
  - nationality:
  - birthdate_or_age_band:
  - university_or_unaffiliated_status:
  - final_round_attendance_available:
- confirmation_route:
  - confirm application status
  - confirm Arena team
  - download practice/QR assets for private local harness
- notes:

### Numerai

- purpose: future Numerai upload only after explicit approval
- login_url: `https://numer.ai/`
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- api_key_path:
- model_id:
- confirmation_route:
  - confirm model id and upload history
- notes:

### Datacontest.kr

- purpose: MOTIE public data final submit after founder walkthrough and form gate
- login_url:
- account_id:
- password_manager_item:
- password:
- two_factor_method:
- identity_or_team_fields:
- confirmation_route:
  - open contest submission page
  - confirm uploaded final HWP/PDF/zip and receipt status
- notes:
"""


@dataclass
class CheckResult:
    ok: bool
    label: str
    detail: str


def ensure_vault() -> CheckResult:
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    if not VAULT.exists() or VAULT.stat().st_size == 0:
        VAULT.write_text(VAULT_TEMPLATE, encoding="utf-8")
    os.chmod(VAULT, 0o600)
    return CheckResult(True, "vault-init", f"{VAULT} mode=600")


def vault_mode_check() -> CheckResult:
    if not VAULT.exists():
        return CheckResult(False, "vault-mode", f"missing {VAULT}; run `ph confirm --init`")
    mode = stat.S_IMODE(VAULT.stat().st_mode)
    ok = mode == 0o600
    return CheckResult(ok, "vault-mode", f"{VAULT} mode={mode:o}")


def section_check() -> CheckResult:
    if not VAULT.exists():
        return CheckResult(False, "vault-sections", "vault missing")
    text = VAULT.read_text(encoding="utf-8", errors="ignore")
    missing = [name for name in REQUIRED_SECTIONS if f"### {name}" not in text]
    ok = not missing
    return CheckResult(ok, "vault-sections", "all required portal sections present" if ok else f"missing: {', '.join(missing)}")


def runbook_check() -> CheckResult:
    if not RUNBOOK.exists():
        return CheckResult(False, "runbook", f"missing {RUNBOOK}")
    text = RUNBOOK.read_text(encoding="utf-8", errors="ignore")
    required = [
        "Submission Confirmation Runbook",
        str(VAULT),
        "Submitted / Monitor",
        "Score-Tracked / Not Final External Submit",
        "Founder-Gated / Not Submitted",
    ]
    missing = [item for item in required if item not in text]
    ok = not missing
    return CheckResult(ok, "runbook", "required sections present" if ok else f"missing: {', '.join(missing)}")


def board_link_check() -> CheckResult:
    if not BOARD.exists():
        return CheckResult(False, "board-link", f"missing {BOARD}")
    text = BOARD.read_text(encoding="utf-8", errors="ignore")
    ok = "SUBMISSION_CONFIRMATION_RUNBOOK.md" in text
    return CheckResult(ok, "board-link", "submission board links runbook" if ok else "submission board does not link runbook")


def public_secret_scan() -> CheckResult:
    paths = [RUNBOOK, BOARD]
    hits: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(str(path.relative_to(CONTROL.parent)))
                break
    ok = not hits
    return CheckResult(ok, "public-secret-scan", "no secret-looking values in public confirmation docs" if ok else f"secret-looking values in: {', '.join(hits)}")


def vault_fill_summary() -> CheckResult:
    if not VAULT.exists():
        return CheckResult(False, "vault-fill", "vault missing")
    filled = 0
    blank = 0
    for raw in VAULT.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        if key in {"purpose", "login_url", "confirmation_route", "notes"}:
            continue
        if value.strip():
            filled += 1
        else:
            blank += 1
    return CheckResult(True, "vault-fill", f"sensitive field slots filled={filled} blank={blank}; values not printed")


def checks() -> list[CheckResult]:
    return [
        vault_mode_check(),
        section_check(),
        runbook_check(),
        board_link_check(),
        public_secret_scan(),
        vault_fill_summary(),
    ]


def print_results(results: list[CheckResult]) -> int:
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"{status}\t{result.label}\t{result.detail}")
    return 0 if all(r.ok for r in results) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", action="store_true", help="create/update the private vault template and chmod 600")
    parser.add_argument("--check", action="store_true", help="run system checks")
    parser.add_argument("--path", action="store_true", help="print private vault path")
    args = parser.parse_args()

    if args.path:
        print(VAULT)
        return 0
    results: list[CheckResult] = []
    if args.init:
        results.append(ensure_vault())
    if args.check or not args.init:
        results.extend(checks())
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
