#!/usr/bin/env python3
"""Small Prizehunter REST client for agents.

Environment:
  PH_API_BASE_URL  Deployment origin, defaults to the Cloudflare Worker URL.
  PH_API_KEY       Sent as x-ph-key for agent read/write endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://prizehunter.cjw070690.workers.dev"


class PrizehunterApiError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"Prizehunter API returned HTTP {status}: {body}")
        self.status = status
        self.body = body


def base_url() -> str:
    return os.environ.get("PH_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _key_from_config() -> str | None:
    # `ph api` and cron call this client without sourcing the env file first,
    # which silently downgraded every agent read to anonymous 401.
    cfg = os.path.expanduser("~/.config/prizehunter/ph_api.env")
    try:
        with open(cfg, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("PH_API_KEY="):
                    return line.split("=", 1)[1].strip() or None
    except OSError:
        return None
    return None


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    path = path if path.startswith("/") else f"/api/{path.lstrip('/')}"
    if not path.startswith("/api/"):
        path = f"/api{path}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "prizehunter-agent/1.0",
    }
    api_key = os.environ.get("PH_API_KEY") or _key_from_config()
    if api_key:
        headers["x-ph-key"] = api_key

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{base_url()}{path}",
        data=data,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PrizehunterApiError(exc.code, body) from exc


def get(path: str) -> Any:
    return request("GET", path)


def post(path: str, payload: dict[str, Any]) -> Any:
    return request("POST", path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prizehunter REST API client")
    parser.add_argument("method", choices=["get", "post"])
    parser.add_argument("path", help="Endpoint path, e.g. board or /api/event")
    parser.add_argument(
        "json_body",
        nargs="?",
        help="JSON object for POST, e.g. '{\"type\":\"note\",\"message\":\"done\"}'",
    )
    args = parser.parse_args()

    try:
        if args.method == "get":
            result = get(args.path)
        else:
            if not args.json_body:
                parser.error("post requires a JSON object body")
            payload = json.loads(args.json_body)
            if not isinstance(payload, dict):
                parser.error("post body must be a JSON object")
            result = post(args.path, payload)
    except (json.JSONDecodeError, PrizehunterApiError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
