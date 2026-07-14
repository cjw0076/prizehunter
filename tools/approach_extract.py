#!/usr/bin/env python3
"""approach_extract.py — build the APPROACH ONTOLOGY from finished competitions.

The compounding-intelligence core: instead of storing flat "lessons", we represent
*how a competition was approached and in what context* as a concept graph — an
ontology — so a new competition can query it, inherit similar-context approaches,
and evolve them (crossover = merging approach subgraphs; fitness = real outcomes).

Ontology (lightweight triples: subject \t predicate \t object \t weight \t source):
  node types (prefix): comp:  domain:  ctx:  approach:  tech:  outcome:  lesson:
  relations:
    comp:<k>      has_domain     domain:<lane>
    comp:<k>      has_context    ctx:<facet>=<value>      (metric, direction, deadline-shape)
    comp:<k>      used_approach  approach:<k>
    approach:<k>  composed_of    tech:<keyword>           (extracted technique)
    approach:<k>  produced       outcome:<result>         weight = fitness(0..1)
    ctx:<facet>   favors         approach:<k>             weight = fitness   ← the LEARNED/evolving edge
    outcome:<k>   yields_lesson  lesson:<k>

`ctx … favors … approach` weighted by fitness is what evolves: high-fitness approaches
in a given context float up; a new competition in a similar context inherits them.

usage: approach_extract.py [--out APPROACH_ONTOLOGY.tsv] [--ttl approach.ttl]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

OUTCOMES = os.path.join(CT, "OUTCOMES.tsv")
LESSONS = os.path.join(CT, "results", "LESSONS.md")
OUT = os.path.join(CT, "APPROACH_ONTOLOGY.tsv")

FITNESS = {"won": 1.0, "placed": 0.8, "no_award": 0.25, "lost": 0.2, "withdrawn": 0.1, "lapsed": 0.0}

# technique vocabulary — matched against next_lever / blocker / lessons text
TECH = {
    "gbdt": r"gbdt|lightgbm|catboost|xgboost|gradient boost|tree",
    "encoder-finetune": r"encoder|deberta|roberta|klue|bert|minilm|kanana|xlm",
    "ensemble": r"ensembl|blend|soup|stack|weighted avg|bagging",
    "feature-engineering": r"feature|피처|source_prefix|prefix|lag|band|persistence|외부관측|asos|nwp",
    "calibration": r"calibrat|캘리브|threshold|temperature|logit.?adjust",
    "augmentation": r"augment|증강|aug\d|sessau|tta|test.?time",
    "distillation": r"distil|증류|teacher|self.?distill|lora",
    "leak-detection": r"leak|누수|oof|held.?out|cv|winner.?s.?curse|과적합|overfit",
    "search-planning": r"mcts|search|planning|go.?explore|map.?elites|world.?model",
    "oracle-reverse": r"oracle|reverse|역설계|deterministic|정산|scorer",
    "prompt-strategy": r"prompt|프롬프트|persona|rubric|judge intent",
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40] or "x"


def techs(text):
    t = (text or "").lower()
    return [k for k, pat in TECH.items() if re.search(pat, t)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--ttl", default="")
    a = ap.parse_args()

    reg = {r["key"]: r for r in P.parse_registry(with_extras=False)}
    outs = {}
    if os.path.exists(OUTCOMES):
        hdr = None
        for line in open(OUTCOMES, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            c = line.split("\t")
            if hdr is None:
                hdr = c
                continue
            d = dict(zip(hdr, c))
            outs[d["key"]] = d
    lessons = {}
    if os.path.exists(LESSONS):
        for ln in open(LESSONS, encoding="utf-8"):
            m = re.match(r"- \[([^\]]+)\]\s*\w+.*?교훈:\s*(.+?)(?:\s*←|\s*\()", ln)
            if m:
                lessons[m.group(1)] = m.group(2).strip()

    triples = []  # (subj, pred, obj, weight, source)
    def add(s, p, o, w="", src=""):
        triples.append((s, p, o, str(w), src))

    for key, r in reg.items():
        lane = r.get("status") and (r.get("metric") or "n/a")
        dom = _domain(r)
        o = outs.get(key, {})
        outcome = (o.get("outcome") or "").split("-")[0] or "pending"
        fit = FITNESS.get(outcome)
        # nodes/edges
        add(f"comp:{key}", "has_domain", f"domain:{dom}", src=key)
        add(f"comp:{key}", "has_context", f"ctx:metric={r.get('metric','n/a')}", src=key)
        add(f"comp:{key}", "has_context", f"ctx:direction={r.get('direction','none')}", src=key)
        ap_id = f"approach:{key}"
        add(f"comp:{key}", "used_approach", ap_id, src=key)
        text = " ".join([r.get("next_lever", ""), r.get("blocker", ""), lessons.get(key, "")])
        for tk in techs(text):
            add(ap_id, "composed_of", f"tech:{tk}", src=key)
        if fit is not None:
            add(ap_id, "produced", f"outcome:{outcome}", w=fit, src=key)
            # the evolving edges: this context favors this approach, weighted by fitness
            add(f"ctx:metric={r.get('metric','n/a')}", "favors", ap_id, w=fit, src=key)
            add(f"domain:{dom}", "favors", ap_id, w=fit, src=key)
        if key in lessons and not lessons[key].startswith("TBD"):
            add(f"outcome:{outcome}", "yields_lesson", f"lesson:{slug(key)}", src=key)
            add(f"lesson:{slug(key)}", "text", lessons[key][:200], src=key)

    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Approach Ontology — subject\tpredicate\tobject\tweight\tsource\n")
        f.write("# ctx/domain 'favors' edges are fitness-weighted and evolve (approach_evolve.py).\n")
        for t in triples:
            f.write("\t".join(t) + "\n")
    os.replace(tmp, a.out)

    if a.ttl:
        _write_ttl(triples, a.ttl)

    n_comp = len({t[0] for t in triples if t[0].startswith("comp:")})
    n_tech = len({t[2] for t in triples if t[2].startswith("tech:")})
    n_fav = sum(1 for t in triples if t[1] == "favors")
    print(f"approach_extract: {len(triples)} triples · {n_comp} competitions · "
          f"{n_tech} techniques · {n_fav} fitness-weighted favors edges → {os.path.basename(a.out)}")


def _domain(r):
    lane_hint = (r.get("metric", "") + " " + r.get("dir", "")).lower()
    if r.get("direction") in ("max", "min"):
        if "f1" in lane_hint or "accuracy" in lane_hint or "logloss" in lane_hint or "log_loss" in lane_hint:
            return "leaderboard-classification"
        if "mae" in lane_hint or "mse" in lane_hint or "spearman" in lane_hint or "nmae" in lane_hint:
            return "leaderboard-regression"
        return "leaderboard-other"
    return "judged-or-hackathon"


def _write_ttl(triples, path):
    # minimal Turtle export for standard-ontology tooling (rdflib etc.)
    def uri(n):
        pre, _, rest = n.partition(":")
        return f"ph:{pre}_{slug(rest)}"
    lines = ["@prefix ph: <https://prizehunter/ontology#> .", ""]
    for s, p, o, w, src in triples:
        if p == "text":
            lines.append(f'{uri(s)} ph:text "{o}" .')
        else:
            wl = f' ph:weight {w} ;' if w else ""
            lines.append(f'{uri(s)} ph:{p}{wl} {uri(o)} .')
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
