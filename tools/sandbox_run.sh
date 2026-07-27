#!/usr/bin/env bash
# sandbox_run.sh — execute agent-generated campaign code inside the MINIMUM council-approved
# sandbox (DEPLOYMENT_READINESS.md step 4): container + non-root + default seccomp +
# no network + memory/pids caps. NEVER silently downgrades to bare host execution —
# a sandbox that quietly stops sandboxing is worse than none.
#
#   sandbox_run.sh [--rw DIR] [--net] [--mem 4g] [--timeout 3600] -- CMD [ARGS...]
#
# Three environments, three honest behaviors:
#   1. inside the prizehunter container (PH_DOCKER=1): the container IS the sandbox
#      (non-root uid 10001, default seccomp) → exec directly with a note.
#   2. host with docker: docker run with --network none, caps, non-root, read-only root.
#   3. host without docker: REFUSE with the exact command to get the sandbox.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
RW="$PWD"; NET=0; MEM="4g"; TMOUT="3600"
while [ $# -gt 0 ]; do
  case "$1" in
    --rw) RW="$2"; shift 2 ;;
    --net) NET=1; shift ;;
    --mem) MEM="$2"; shift 2 ;;
    --timeout) TMOUT="$2"; shift 2 ;;
    --) shift; break ;;
    *) echo "usage: sandbox_run.sh [--rw DIR] [--net] [--mem 4g] [--timeout S] -- CMD..." >&2; exit 2 ;;
  esac
done
[ $# -gt 0 ] || { echo "sandbox_run.sh: no command given" >&2; exit 2; }

if [ "${PH_DOCKER:-}" = "1" ]; then
  echo "[sandbox] already inside the worker container (non-root + seccomp) — executing directly" >&2
  exec timeout "$TMOUT" "$@"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  NETFLAG="--network none"; [ "$NET" = "1" ] && NETFLAG=""
  IMG="${PH_SANDBOX_IMAGE:-prizehunter:local}"
  docker image inspect "$IMG" >/dev/null 2>&1 || {
    echo "⛔ sandbox image '$IMG' not built. Run: docker compose build   (from the prizehunter repo)" >&2
    exit 3
  }
  exec timeout "$TMOUT" docker run --rm $NETFLAG \
    --memory "$MEM" --pids-limit 256 --cpus "${PH_SANDBOX_CPUS:-2}" \
    --security-opt no-new-privileges --user 10001:10001 \
    --read-only --tmpfs /tmp:size=1g \
    -v "$(cd "$RW" && pwd)":/work:rw -w /work \
    "$IMG" "$@"
fi

echo "⛔ SANDBOX UNAVAILABLE: docker is not usable on this host, and agent-generated code must not" >&2
echo "   run unsandboxed (council step-4). Install docker, or run inside the worker container:" >&2
echo "     docker compose run --rm worker ...   (repo: docker-compose.yml)" >&2
exit 3
