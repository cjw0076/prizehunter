#!/usr/bin/env python3
"""_registry_atomic.py — atomic + shrink-guarded writes for the portfolio registry (single source of truth).

Why (measured, not asserted): a plain open(path,"w") TRUNCATES the file before writing, so a concurrent reader
can observe 0 bytes in that window. On 2026-08-01 exactly this race — compounded by a read-empty → write-empty
in one process — truncated portfolio_registry.tsv to 0 bytes, and the freshest on-disk backup was 6 days old.

Two guarantees, both cheap:
  1. ATOMIC: write a temp file in the same directory, fsync, then os.replace() (atomic rename on one
     filesystem). Every reader sees the whole OLD file or the whole NEW file — never empty, never partial.
     Once every writer goes through here, the truncation race the readers used to lose is impossible.
  2. SHRINK GUARD: refuse (by default) a write that would drop most data rows, so even a
     read-empty → modify → write-empty inside a single process cannot destroy the file. An intentional large
     shrink passes force=True; a refused write preserves the old file and shouts on stderr (silence ≠ safety).
"""
import os
import sys


def _data_rows(text):
    return sum(1 for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#"))


def write_registry_atomic(path, text, *, min_keep_frac=0.5, force=False):
    """Atomically write `text` to `path`. Returns rows written, or None if the shrink guard skipped the write
    (old file preserved). Set force=True for a deliberate large shrink."""
    if not text.endswith("\n"):
        text += "\n"
    new_n = _data_rows(text)
    if not force and os.path.exists(path):
        try:
            cur_n = _data_rows(open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            cur_n = 0
        if cur_n >= 10 and new_n < cur_n * min_keep_frac:
            print(f"[registry-guard] REFUSING to write {new_n} data rows over {cur_n} "
                  f"(< {min_keep_frac:.0%}); old file preserved. Pass force=True for an intentional shrink.",
                  file=sys.stderr, flush=True)
            return None
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on the same filesystem
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass
    return new_n
