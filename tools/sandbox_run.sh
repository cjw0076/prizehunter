#!/usr/bin/env bash
# sandbox_run.sh — execute agent-generated campaign code inside the MINIMUM council-approved
# sandbox (DEPLOYMENT_READINESS.md step 4): container + non-root + default seccomp +
# no network + memory/pids caps + hard-kill timeout. NEVER silently downgrades —
# a sandbox that quietly stops sandboxing is worse than none.
#
#   sandbox_run.sh [--rw DIR] [--net] [--mem 4g] [--timeout 3600] -- CMD [ARGS...]
#
# Threat model (QA 2026-07-28, codex+NIM adversarial review): the CALLER may itself be
# agent-generated. Therefore no flag or env var alone may weaken isolation:
#   • --net requires operator env PH_ALLOW_NET=1
#   • --rw must resolve INSIDE $CT/campaigns (the only tree agent code may rewrite);
#     anything else requires operator env PH_SANDBOX_RW_ANY=1
#   • PH_DOCKER=1 is a claim, not proof — container evidence (/.dockerenv etc.) is required,
#     AND the in-container direct path must be explicitly accepted with
#     PH_SANDBOX_ACCEPT_CONTAINER=1, because the worker container still has network and a
#     read-write repo mount — it is weaker than the docker-run sandbox. The compose `sandbox`
#     service sets this env with network disabled and a campaigns-only mount.
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
case "$TMOUT" in ''|*[!0-9]*) echo "⛔ --timeout must be integer seconds" >&2; exit 2;; esac

in_container(){ [ -f /.dockerenv ] || [ -f /run/.containerenv ] || grep -qE 'docker|containerd|kubepods' /proc/1/cgroup 2>/dev/null; }

if [ "${PH_DOCKER:-}" = "1" ]; then
  if ! in_container; then
    echo "⛔ PH_DOCKER=1 is set but this is NOT a container (no /.dockerenv, no container cgroup)." >&2
    echo "   Refusing the unsandboxed path — unset PH_DOCKER or run inside docker compose." >&2
    exit 3
  fi
  if [ "${PH_SANDBOX_ACCEPT_CONTAINER:-}" != "1" ]; then
    echo "⛔ inside a container, but direct execution here still has NETWORK and a rw repo mount." >&2
    echo "   Use the dedicated service:  docker compose run --rm sandbox -- CMD…" >&2
    echo "   (or set PH_SANDBOX_ACCEPT_CONTAINER=1 to accept the reduced isolation deliberately)" >&2
    exit 3
  fi
  echo "[sandbox] container path accepted (non-root + seccomp; isolation reduced vs docker-run)" >&2
  exec timeout --kill-after=10 "$TMOUT" "$@"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  # --net is caller-supplied and callers can be agent-generated: require an operator-set
  # env (PH_ALLOW_NET=1) before honoring it, so code cannot grant itself exfiltration
  NETFLAG="--network none"
  if [ "$NET" = "1" ]; then
    [ "${PH_ALLOW_NET:-}" = "1" ] || { echo "⛔ --net requires operator env PH_ALLOW_NET=1" >&2; exit 3; }
    NETFLAG=""
  fi
  RW_REAL="$(cd "$RW" 2>/dev/null && pwd -P)" || { echo "⛔ --rw dir not found: $RW" >&2; exit 2; }
  RW_REAL="${RW_REAL%/}"
  # the ONLY tree agent code may rewrite is a campaign dir; the engine root, $HOME, /etc …
  # all need an explicit operator override (host-file exposure = orchestrator/credential rewrite)
  case "$RW_REAL/" in
    "$CT"/campaigns/*) : ;;
    *) if [ "${PH_SANDBOX_RW_ANY:-}" != "1" ]; then
         echo "⛔ --rw $RW_REAL is outside $CT/campaigns — refuse (mount a campaign subdir, or set PH_SANDBOX_RW_ANY=1 deliberately)" >&2
         exit 3
       fi ;;
  esac
  case "$CT/" in "$RW_REAL"/*) echo "⛔ --rw $RW_REAL contains the engine root $CT — refuse" >&2; exit 3;; esac
  IMG="${PH_SANDBOX_IMAGE:-prizehunter:local}"
  docker image inspect "$IMG" >/dev/null 2>&1 || {
    echo "⛔ sandbox image '$IMG' not built. Run: docker compose build   (from the prizehunter repo)" >&2
    exit 3
  }
  # no exec: keep a trap so a timed-out docker CLIENT cannot leave the container running
  CIDFILE="$(mktemp -u "${TMPDIR:-/tmp}/ph_sandbox_XXXXXX.cid")"
  cleanup(){ [ -f "$CIDFILE" ] && { docker rm -f "$(cat "$CIDFILE" 2>/dev/null)" >/dev/null 2>&1 || true; rm -f "$CIDFILE"; }; }
  trap cleanup EXIT INT TERM
  timeout --kill-after=10 "$TMOUT" docker run --rm --cidfile "$CIDFILE" $NETFLAG \
    --memory "$MEM" --pids-limit 256 --cpus "${PH_SANDBOX_CPUS:-2}" \
    --security-opt no-new-privileges --user 10001:10001 \
    --read-only --tmpfs /tmp:size=1g \
    -v "$RW_REAL":/work:rw -w /work \
    "$IMG" "$@"
  rc=$?
  cleanup; trap - EXIT INT TERM
  [ $rc -eq 124 ] || [ $rc -eq 137 ] && echo "⛔ sandbox timeout after ${TMOUT}s — container force-removed" >&2
  exit $rc
fi

echo "⛔ SANDBOX UNAVAILABLE: docker is not usable on this host, and agent-generated code must not" >&2
echo "   run unsandboxed (council step-4). Install docker, or run inside the worker container:" >&2
echo "     docker compose run --rm sandbox -- CMD…   (repo: docker-compose.yml)" >&2
exit 3
