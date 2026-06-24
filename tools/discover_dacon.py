#!/usr/bin/env python3
"""discover_dacon.py — stage-1 discovery adapter for DACON (no auth needed).

DACON embeds its full competition list in the /competitions page as a JS
`compData:[{...}]` array. This adapter fetches + parses it into the candidate
schema the triage scorer consumes, inferring domain/modality from the (Korean)
title. DACON is the platform where the full discover->...->submit loop is
actually automatable (programmatic submit via src/dacon_submit.py).

Usage:
  discover_dacon.py [--html FILE] [--out candidates_dacon.tsv]
  (omit --html to fetch live)
"""
import re, sys, json, subprocess, argparse, os

DACON_URL = "https://dacon.io/competitions"

# (keyword -> (domain, modality)) inferred from Korean/English titles
KW = [
    (r'이미지|비전|영상|사진|vision|image|얼굴|객체', ('vision', 'image')),
    (r'음성|소리|오디오|audio|speech|sound', ('audio', 'audio')),
    (r'언어|텍스트|자연어|nlp|언어모델|llm|챗|리뷰|감정|bias|질의|문서', ('nlp', 'text')),
    (r'궤적|예측|수요|가격|금융|주가|신용|finance|forecast|시계열', ('tabular', 'timeseries')),
    (r'분류|회귀|정형|테이블|tabular|구매|이탈', ('tabular', 'tabular')),
    (r'추천|recommend', ('recsys', 'tabular')),
    (r'그래프|graph|분자|화합물|단백질|bio|유전|의료|질병', ('bio', 'graph')),
]

def infer(name):
    n = name.lower()
    for pat, (dom, mod) in KW:
        if re.search(pat, n):
            return dom, mod
    return 'ml', 'tabular'

def build_varmap(html):
    # DACON minifies repeated literals into the IIFE's positional params (a,b,c,...).
    # Resolve them so prize:/practice: flags can be read (e.g. prize:f, f="0").
    i = html.find('compData:')
    if i < 0:
        return {}
    fstart = html.rfind('function(', 0, i)
    if fstart < 0:
        return {}
    params = [p.strip() for p in html[fstart+9: html.find(')', fstart)].split(',')]
    m = re.search(r'\}\((.*?)\)\s*[,;\]]', html[i:i+300000], re.S)
    if not m:
        return {}
    args = re.split(r',(?![^\[]*\])', m.group(1))
    vm = {}
    for name, val in zip(params, args):
        vm[name] = val.strip().strip('"')
    return vm

def resolve(seg, field, vm):
    m = re.search(field + r':([A-Za-z_]\w*|"[^"]*"|-?\d+)', seg)
    if not m:
        return None
    v = m.group(1).strip('"')
    return vm.get(v, v)  # map minified var -> literal, else the literal itself

def parse(html, include_practice=False):
    out = {}
    vm = build_varmap(html)
    for m in re.finditer(r'cpt_id:(\d+)(.*?)(?=cpt_id:\d+|\]\s*,?\s*$|compStatus|landingData)', html, re.S):
        cid = m.group(1); seg = m.group(2)[:1200]
        nm = re.search(r'name:"((?:[^"\\]|\\.)*)"', seg)
        ptot = re.search(r'period_total:(\d+)', seg)
        users = re.search(r'user_count:(\d+)', seg)
        if not nm:
            continue
        # period_dday may be a literal int OR a minified var (e.g. "h"->29, "e"->-1),
        # so resolve through the varmap before reading it (digit-only regex missed vars).
        dday_tok = resolve(seg, 'period_dday', vm)
        try:
            ddv = int(dday_tok)
        except (TypeError, ValueError):
            ddv = -999
        # MONEY GATE ("돈 되는 것만"): drop zero-prize competitions.
        # NOTE: the DACON `practice` field resolves unreliably (minified to 1 for LIVE
        # comps too — gating on it dropped everything), so gate on prize + deadline only.
        # Genuine practice comps carry prize 0 and are still dropped by the money gate.
        prize_raw = resolve(seg, 'prize', vm)
        no_prize = prize_raw in (None, '', '0', 0, 'false', 'null', '-1')
        if no_prize and not include_practice:
            continue
        # DEADLINE GATE: drop closed comps (no positive days-to-deadline)
        if ddv < 0 and not include_practice:
            continue
        # decode ONLY \uXXXX escapes; leave raw UTF-8 intact (avoids mojibake)
        name = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), nm.group(1))
        if cid in out:
            continue
        dom, mod = infer(name)
        # honest edge flag: only domains we have a proven case study / ceiling for
        edge = 'yes' if re.search(r'bias|휴먼이해|lifelog|sleep|수면|감정|emotion', name.lower()) else 'no'
        out[cid] = {
            'name': f'DACON {cid} {name[:40]}',
            'domain': dom, 'data_modality': mod,
            'metric': 'accuracy',                 # DACON comps are leaderboard-scored (automatable); refine from detail page
            'prize': str(prize_raw),              # resolved from listing; gate already dropped zero/practice
            'hardware_required': 'none',
            'external_data_policy': 'unknown',
            'days_to_deadline': str(ddv) if ddv > -999 else '9999',
            'eligibility': 'open',
            'we_have_edge': edge,                 # only domains with a proven case study
            'cpt_id': cid, 'users': users.group(1) if users else '0',
            'period_total': ptot.group(1) if ptot else '',
        }
    return list(out.values())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html')
    ap.add_argument('--include-practice', action='store_true', help='keep zero-prize/practice comps (default: drop)')
    here = os.path.dirname(__file__)
    ap.add_argument('--out', default=os.path.join(here, '..', 'candidates_dacon.tsv'))
    a = ap.parse_args()

    if a.html:
        html = open(a.html, errors='ignore').read()
    else:
        try:
            html = subprocess.check_output(
                ['curl', '-L', '--connect-timeout', '10', '--max-time', '30', '-s', DACON_URL],
                text=True)
        except Exception as e:
            print(f'fetch failed: {e}', file=sys.stderr); sys.exit(1)

    cands = parse(html, include_practice=a.include_practice)
    if not cands:
        print('no competitions parsed (page structure may have changed)', file=sys.stderr); sys.exit(1)

    cols = ['name', 'domain', 'prize', 'metric', 'data_modality', 'hardware_required',
            'external_data_policy', 'days_to_deadline', 'eligibility', 'we_have_edge', 'cpt_id', 'users']
    with open(a.out, 'w') as f:
        f.write('\t'.join(cols) + '\n')
        for c in cands:
            f.write('\t'.join(str(c.get(k, '')) for k in cols) + '\n')
    print(a.out)
    print(f'discovered={len(cands)} dacon competitions')

if __name__ == '__main__':
    main()
