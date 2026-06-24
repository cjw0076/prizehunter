#!/usr/bin/env python3
"""mine_sessions.py — reverse-engineer the prize-hunting process from agent logs.

Reads Claude Code transcripts (JSONL under ~/.claude|cli-profiles .../projects/)
and optional Codex rollout logs, and distills a structured *process corpus*:
per session — which competition, models used, actions taken (bash/edits), scores
observed, decisions, and failures. This is the substrate for systematizing the
winning loop (and a buyer's proof-of-work). Read-only. No secrets are emitted
(tool inputs are summarized, not dumped verbatim).

Usage:
  mine_sessions.py [--projects-glob GLOB] [--filter SUBSTR] [--out DIR] [--json]
"""
import json, re, sys, glob, os, collections, argparse

SCORE_RE = re.compile(r'\b0\.\d{3,4}\b')
RANK_RE = re.compile(r'(rank[- ]?1|리더보드|leaderboard|\d+\s*위|#\s*\d+)', re.I)
DECISION_RE = re.compile(r'(결론|확정|decision|결정|chose|선택|천장|ceiling|best=|new best|승인)', re.I)
FAIL_RE = re.compile(r'(net-zero|실패|failed|열위|OOM|blocked|막힘|error|오답|leak|누수)', re.I)

def blocks(rec):
    m = rec.get('message') or {}
    c = m.get('content')
    return c if isinstance(c, list) else []

def text_of(rec):
    out = []
    for b in blocks(rec):
        if not isinstance(b, dict): continue
        if b.get('type') == 'text': out.append(b.get('text', ''))
        elif b.get('type') == 'thinking': out.append(b.get('thinking', '') or '')
    return '\n'.join(out)

def mine_file(path):
    comp = collections.Counter(); models = collections.Counter()
    tools = collections.Counter(); bash_cmds = []
    scores = collections.Counter(); decisions = []; fails = []
    n_turns = 0; first_ts = last_ts = None; git = collections.Counter()
    for line in open(path, errors='ignore'):
        line = line.strip()
        if not line: continue
        try: r = json.loads(line)
        except Exception: continue
        ts = r.get('timestamp')
        if ts:
            first_ts = first_ts or ts; last_ts = ts
        if r.get('cwd'): comp[r['cwd']] += 1
        if r.get('gitBranch'): git[r['gitBranch']] += 1
        t = r.get('type')
        if t == 'assistant':
            n_turns += 1
            m = r.get('message') or {}
            if m.get('model'): models[m['model']] += 1
            for b in blocks(r):
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    name = b.get('name', '?'); tools[name] += 1
                    if name == 'Bash':
                        cmd = (b.get('input') or {}).get('command', '')
                        head = cmd.strip().split('\n')[0][:80]
                        if head: bash_cmds.append(head)
        txt = text_of(r)
        if txt:
            for s in SCORE_RE.findall(txt): scores[s] += 1
            for ln in txt.split('\n'):
                if DECISION_RE.search(ln) and len(ln.strip()) > 12:
                    decisions.append(ln.strip()[:160])
                if FAIL_RE.search(ln) and len(ln.strip()) > 12:
                    fails.append(ln.strip()[:160])
    cwd = comp.most_common(1)[0][0] if comp else '?'
    return {
        'file': path, 'cwd': cwd, 'gitBranch': (git.most_common(1)[0][0] if git else '?'),
        'turns': n_turns, 'first_ts': first_ts, 'last_ts': last_ts,
        'models': dict(models), 'tools': dict(tools.most_common(8)),
        'top_bash': [c for c, _ in collections.Counter(bash_cmds).most_common(10)],
        'top_scores': [s for s, _ in scores.most_common(8)],
        'decisions': decisions[:12], 'fails': fails[:12],
    }

def main():
    ap = argparse.ArgumentParser()
    home = os.path.expanduser('~')
    default = f'{home}/cli-profiles/*/claude/projects/**/*.jsonl'
    ap.add_argument('--projects-glob', default=default)
    ap.add_argument('--filter', default='dacon', help='only sessions whose path contains this')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'session_corpus'))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    files = [f for f in glob.glob(a.projects_glob, recursive=True)
             if a.filter in f and '/subagents/' not in f]
    files.sort()
    results = []
    for f in files:
        try: results.append(mine_file(f))
        except Exception as e: print(f'skip {f}: {e}', file=sys.stderr)

    os.makedirs(a.out, exist_ok=True)
    if a.json:
        jp = os.path.join(a.out, 'corpus.json')
        json.dump(results, open(jp, 'w'), ensure_ascii=False, indent=1)
        print(jp)

    # aggregate report
    allmodels = collections.Counter(); alltools = collections.Counter()
    for r in results:
        allmodels.update(r['models']); alltools.update(r['tools'])
    mp = os.path.join(a.out, 'CORPUS_REPORT.md')
    with open(mp, 'w') as o:
        o.write(f'# Session Corpus — reverse-engineered process\n\n')
        o.write(f'- sessions analyzed: **{len(results)}** (filter="{a.filter}")\n')
        o.write(f'- model usage (turns): {dict(allmodels)}\n')
        o.write(f'- tool usage: {dict(alltools.most_common(10))}\n\n')
        for r in sorted(results, key=lambda x: x.get('turns', 0), reverse=True):
            o.write(f'## {os.path.basename(r["file"])[:18]} — {r["cwd"]}\n')
            o.write(f'- turns={r["turns"]} branch={r["gitBranch"]} models={list(r["models"])}\n')
            o.write(f'- window: {r["first_ts"]} → {r["last_ts"]}\n')
            if r['top_scores']: o.write(f'- scores seen: {r["top_scores"]}\n')
            if r['top_bash']: o.write(f'- top commands: {r["top_bash"][:6]}\n')
            if r['decisions']:
                o.write('- decisions:\n')
                for d in r['decisions'][:6]: o.write(f'  - {d}\n')
            if r['fails']:
                o.write('- failures/levers-exhausted:\n')
                for d in r['fails'][:5]: o.write(f'  - {d}\n')
            o.write('\n')
    print(mp)
    print(f'sessions={len(results)} models={dict(allmodels)}')

if __name__ == '__main__':
    main()
