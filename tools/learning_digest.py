#!/usr/bin/env python3
"""learning_digest.py — LEARNING_LEDGER.md(수백 엔트리, 아무도 안 읽던 663KB)를
기계 파싱해 ① LEARNING_INDEX.md(최근/키별/빈출 색인) ② 신규 엔트리 다이제스트를
memoryOS 에 예금(draft-first). LEARN 스테이지의 '환류 없음' 갭을 막는 주간 도구.

엔트리 포맷: `## YYYY-MM-DD HH:MM KST — agent@repo — slug`
"""
import json
import os
import re
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
LEDGER = os.path.join(CT, "LEARNING_LEDGER.md")
INDEX = os.path.join(CT, "LEARNING_INDEX.md")
STATE = os.path.join(CT, ".runs", "learning_digest.state")
DIGEST_DIR = os.path.join(CT, "session_corpus")
HDR = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}[^—]*)—\s*([^—]+)—\s*(.+)$")


def parse_entries(text):
    entries = []
    cur = None
    for line in text.splitlines():
        m = HDR.match(line)
        if m:
            cur = {"date": m.group(1).strip(), "agent": m.group(2).strip(),
                   "slug": m.group(3).strip(), "body": []}
            entries.append(cur)
        elif cur is not None:
            cur["body"].append(line)
    return entries


def main():
    if not os.path.exists(LEDGER):
        print("learning_digest: no LEARNING_LEDGER.md")
        return
    text = open(LEDGER, encoding="utf-8", errors="ignore").read()
    entries = parse_entries(text)
    st = {}
    try:
        st = json.load(open(STATE))
    except Exception:
        pass
    seen = st.get("count", 0)
    new = entries[seen:]

    # ① index
    slug_words = {}
    for e in entries:
        for w in re.split(r"[-_\s]", e["slug"].lower()):
            if len(w) >= 4:
                slug_words[w] = slug_words.get(w, 0) + 1
    top = sorted(slug_words.items(), key=lambda x: -x[1])[:20]
    L = [f"# Learning Index — {datetime.now():%Y-%m-%d %H:%M} (자동, learning_digest.py)", "",
         f"- 총 엔트리 **{len(entries)}** · 이번 신규 {len(new)} · 원본 LEARNING_LEDGER.md",
         "", "## 최근 15", ""]
    for e in entries[-15:][::-1]:
        first = next((l.strip() for l in e["body"] if l.strip()), "")[:110]
        L.append(f"- `{e['date'][:16]}` **{e['slug']}** ({e['agent']}) — {first}")
    L += ["", "## 빈출 주제 (slug)", "",
          " · ".join(f"{w}×{n}" for w, n in top), "",
          "> 정제 교훈은 results/LESSONS.md — 이 색인은 원장 접근용 지도.", ""]
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, INDEX)

    # ② digest of NEW entries → memoryOS (draft-first, best-effort)
    deposited = 0
    if new:
        os.makedirs(DIGEST_DIR, exist_ok=True)
        dpath = os.path.join(DIGEST_DIR, f"learning_digest_{datetime.now():%Y%m%d}.md")
        with open(dpath, "w", encoding="utf-8") as f:
            f.write(f"# Learning digest {datetime.now():%Y-%m-%d} — LEARNING_LEDGER 신규 {len(new)}건 요약\n\n")
            for e in new:
                first = next((l.strip() for l in e["body"] if l.strip()), "")[:200]
                f.write(f"- [{e['date'][:16]}] {e['slug']} ({e['agent']}): {first}\n")
        r = subprocess.run(["bash", os.path.join(HERE, "memoryos_bridge.sh"), "deposit", dpath],
                           capture_output=True, text=True, timeout=200)
        deposited = 1 if r.returncode == 0 else 0
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({"count": len(entries), "last_run": datetime.now().isoformat()}, open(STATE, "w"))
    print(f"learning_digest: entries={len(entries)} new={len(new)} deposited={deposited} → LEARNING_INDEX.md")


if __name__ == "__main__":
    main()
