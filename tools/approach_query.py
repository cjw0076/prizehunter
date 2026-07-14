"""approach_query.py — inherit + evolve approaches from the ontology for a NEW competition.

Given a new competition's context (domain/metric), query APPROACH_ONTOLOGY.tsv for
the approaches that WON in similar contexts (fitness-weighted `favors` edges),
crossover their techniques (fitness-weighted vote across the matched approaches),
and emit an INHERITED STRATEGY block for plan_campaign to seed the plan.

This is the "learns the approach + context" loop in use: selection = high-fitness
approaches in a matching context; crossover = union of their techniques weighted by
fitness; the weights themselves evolve as new outcomes are extracted each round.

usage: approach_query.py --metric log_loss [--domain leaderboard-classification]
       approach_query.py --key <registry-key>     (reads its lane/metric from registry)
"""
import argparse
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

ONTO = os.path.join(CT, "APPROACH_ONTOLOGY.tsv")


def load():
    triples = []
    if os.path.exists(ONTO):
        for line in open(ONTO, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) >= 3:
                triples.append(c + [""] * (5 - len(c)))
    return triples


def domain_of_metric(metric, direction):
    m = (metric or "").lower()
    if direction in ("max", "min"):
        if any(x in m for x in ("f1", "accuracy", "logloss", "log_loss")):
            return "leaderboard-classification"
        if any(x in m for x in ("mae", "mse", "spearman", "nmae")):
            return "leaderboard-regression"
        return "leaderboard-other"
    return "judged-or-hackathon"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metric", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--self", dest="self_key", default="", help="exclude this key from evidence (avoid self-priming)")
    a = ap.parse_args()

    metric, domain, exclude = a.metric, a.domain, a.self_key
    if a.key:
        r = next((x for x in P.parse_registry(with_extras=False) if x["key"] == a.key), None)
        if r:
            metric = metric or r.get("metric", "")
            domain = domain or domain_of_metric(r.get("metric", ""), r.get("direction", ""))
            exclude = exclude or a.key
    domain = domain or domain_of_metric(metric, "max")

    triples = load()
    if not triples:
        print("no ontology yet — run approach_extract.py after competitions settle."); return

    # selection: approaches favored by matching context/domain, fitness-weighted
    fav = defaultdict(float)       # approach -> summed fitness across matching context edges
    src = {}                       # approach -> source comp
    for s, p, o, w, sc in triples:
        if p != "favors":
            continue
        weight = float(w) if w else 0.0
        match = (s == f"domain:{domain}") or (metric and s == f"ctx:metric={metric}")
        if match and o.startswith("approach:") and sc != exclude:
            fav[o] += weight
            src[o] = sc
    if not fav:
        print(f"no prior approaches for domain='{domain}' metric='{metric}'. "
              f"This is a new context — the ontology will learn it once this competition settles.")
        return

    # crossover: union of techniques across the top approaches, fitness-weighted vote
    tech_by_ap = defaultdict(list)
    for s, p, o, w, sc in triples:
        if p == "composed_of" and s.startswith("approach:"):
            tech_by_ap[s].append(o.replace("tech:", ""))
    tech_vote = defaultdict(float)
    tech_evidence = defaultdict(set)
    for ap_id, f in fav.items():
        for tk in tech_by_ap.get(ap_id, []):
            tech_vote[tk] += f
            tech_evidence[tk].add(src.get(ap_id, "?"))

    top_ap = sorted(fav.items(), key=lambda kv: -kv[1])[:5]
    top_tech = sorted(tech_vote.items(), key=lambda kv: -kv[1])

    print(f"## INHERITED STRATEGY — domain={domain} metric={metric or 'any'}")
    print("_evolved from past outcomes; selection=fitness-weighted context match, crossover=technique union._\n")
    print("### Techniques that worked in this context (fitness-weighted)")
    if top_tech:
        for tk, v in top_tech:
            print(f"- **{tk}**  (weight {v:.2f}; evidence: {', '.join(sorted(tech_evidence[tk]))})")
    else:
        print("- (matched approaches carried no extracted techniques — fill their postmortems to enrich)")
    print("\n### Source approaches (highest fitness first)")
    for ap_id, f in top_ap:
        print(f"- {ap_id.replace('approach:','')}  fitness={f:.2f}  (from {src.get(ap_id,'?')})")
    print("\n→ Seed plan_campaign with these; mutate for this competition's specifics. "
          "Low-fitness contexts (all-loss) mean: do the OPPOSITE of what's here.")


if __name__ == "__main__":
    main()
