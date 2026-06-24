#!/usr/bin/env python3
"""triage_competition.py — stage-2 go/no-go scorer for the prize machine.

Scores a competition candidate for AGENT-winnability so the loop only spends
compute on competitions an autonomous agent can realistically dominate. Reads a
candidates TSV (or single --json candidate) and emits a ranked verdict.

Winnability heuristics (transparent, tunable):
  + high prize, + leaderboard-with-metric (automatable), + agent-friendly modality
  (tabular/text/vision/code), + open external-data policy, + we have a matching
  case study; - physical-hardware requirement (agent can't act), - subjective-only
  judging, - deadline too close for a build, - institutional/eligibility gates.

Usage:
  triage_competition.py --candidates candidates.tsv
  triage_competition.py --json '{"name":"X","domain":"finance","prize":50000,...}'
"""
import json, sys, argparse, os

AGENT_FRIENDLY = {'tabular', 'text', 'nlp', 'vision', 'image', 'timeseries',
                  'code', 'audio', 'multimodal', 'graph'}
HARD_NOGO = {'physical', 'hardware', 'robot', 'embodied', 'wetlab', 'onsite'}

def score(c):
    s, reasons = 50, []
    # MONEY GATE ("돈 되는 것만"): no verified prize -> NO-GO regardless of winnability
    pr = str(c.get('prize', '')).strip().lower()
    if pr in ('', '0', 'none', 'false', 'null', '-1', 'tbd'):
        return 0, 'NO-GO', 'no prize (practice/zero) — drop per money-only policy'
    # prize
    try: prize = float(str(c.get('prize', 0)).replace('$', '').replace(',', '') or 0)
    except Exception: prize = 0
    if prize >= 50000: s += 20; reasons.append(f'high prize ${prize:.0f}')
    elif prize >= 10000: s += 12; reasons.append(f'prize ${prize:.0f}')
    elif prize > 0: s += 5; reasons.append(f'small prize ${prize:.0f}')
    else: reasons.append('prize unknown/none')

    # automatable: has a numeric leaderboard metric
    metric = str(c.get('metric', '')).strip().lower()
    if metric and metric not in ('n/a', 'none', 'subjective', 'judged'):
        s += 15; reasons.append(f'metric={metric} (automatable)')
    elif metric in ('subjective', 'judged'):
        s -= 15; reasons.append('subjective judging (hard to automate)')

    # modality
    mod = str(c.get('data_modality', '')).strip().lower()
    if mod in AGENT_FRIENDLY: s += 12; reasons.append(f'{mod} (agent-friendly)')
    if any(h in (mod + ' ' + str(c.get('hardware_required', ''))).lower() for h in HARD_NOGO):
        s -= 40; reasons.append('NO-GO: physical/hardware required')

    # external data
    if str(c.get('external_data_policy', '')).lower() in ('open', 'allowed', 'yes'):
        s += 8; reasons.append('external data open (leverage)')

    # deadline runway (days)
    try: days = int(c.get('days_to_deadline', 9999))
    except Exception: days = 9999
    if days < 3: s -= 20; reasons.append(f'only {days}d runway')
    elif days < 7: s -= 5; reasons.append(f'{days}d runway (tight)')

    # eligibility gates
    if str(c.get('eligibility', '')).lower() in ('institutional', 'invite', 'team-required'):
        s -= 15; reasons.append('eligibility-gated')

    # our edge: matching case study / mined pattern
    if str(c.get('we_have_edge', '')).lower() in ('yes', 'true', '1'):
        s += 15; reasons.append('we have a matching case study/pattern')

    s = max(0, min(100, s))
    verdict = 'GO' if s >= 70 else ('CONSIDER' if s >= 50 else 'NO-GO')
    return s, verdict, '; '.join(reasons)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates')
    ap.add_argument('--json')
    a = ap.parse_args()

    rows = []
    if a.json:
        rows = [json.loads(a.json)]
    elif a.candidates and os.path.exists(a.candidates):
        with open(a.candidates) as f:
            header = None
            for line in f:
                line = line.rstrip('\n')
                if not line or line.startswith('#'): continue
                cells = line.split('\t')
                if header is None: header = cells; continue
                rows.append(dict(zip(header, cells)))
    else:
        print('provide --candidates TSV or --json candidate', file=sys.stderr); sys.exit(2)

    scored = []
    for c in rows:
        sc, v, why = score(c)
        scored.append((sc, v, c.get('name', '?'), c.get('domain', '?'), why))
    scored.sort(reverse=True)

    print(f'{"SCORE":>5} {"VERDICT":<9} {"DOMAIN":<12} NAME')
    for sc, v, name, dom, why in scored:
        print(f'{sc:>5} {v:<9} {dom:<12} {name}')
        print(f'        └─ {why}')

if __name__ == '__main__':
    main()
