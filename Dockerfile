# syntax=docker/dockerfile:1
# PrizeHunter runtime — the engine is Python-stdlib-only by design (see requirements.txt
# rationale), so this image is a pinned interpreter + the small set of CLI tools the
# shell layer expects. Campaign-specific ML deps belong in per-campaign environments,
# never here.
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash git curl ca-certificates jq tmux rsync \
    && rm -rf /var/lib/apt/lists/*

# non-root: agent-generated campaign code must never run as root (council step-4 requirement)
RUN useradd -m -u 10001 hunter

WORKDIR /app
COPY --chown=hunter:hunter . .
USER hunter

ENV PH_DOCKER=1
# cockpit daemon (tools/prizehunterd.py) — tokened, tenant-isolated
EXPOSE 8787

ENTRYPOINT ["/app/ph"]
CMD ["help"]
