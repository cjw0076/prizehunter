#!/usr/bin/env python3
"""gap_view.py — RENDER the train↔test geometry a human can actually see (cure for Geometry Blindness).

founder: the plateau diagnosis in playbook/THE_PATH_TO_NUMBER_ONE.md names three causes; the only one a
system can fix cheaply is that **nobody ever looks at a picture**. `ph gap` runs seven probes and returns
scalars; a scalar cannot tell you "test has a second mode train does not have", and it cannot tell you
"the public leaderboard is estimated on 3 entities while your CV averages 773". This does both.

  ph view <key>                 → <campaign>/VIEW/index.html + VIEW/FINDINGS.md + VIEW/findings.json
  ph view <key> --top 16        → how many drifted columns to plot per family (ranked by KS)
  ph view <key> --dir D         → point at data living outside the campaign dir

Per shared numeric column (train vs test):
  KS  two-sample Kolmogorov–Smirnov distance  (0 = identical shape, 1 = disjoint)
  PSI population stability index on train deciles (drift convention: >0.10 minor, >0.25 major)
  mean shift in train-sigma units
Plus the structural facts that actually break submissions: ENTITY COUNT per side (a 3-well public test
cannot be compared to a 773-well CV), columns only in train (targets/leaks), columns only in test (schema
mismatch), and unread visual assets in the data dir.

FILE FAMILIES: a data dir often holds several different tables (rogii: `<well>__horizontal_well.csv` and
`<well>__typewell.csv` — different columns, different meaning). Pooling them would compare a column named
`GR` in one schema against `GR` in another, so files are grouped by family and each family is compared
against its own counterpart. Never pool schemas.

Stdlib only — this must run in the shipping container, which has zero pip deps (see Dockerfile).
Pure read + render: no registry write, no agent dispatch, no network call.
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from svgchart import PAGE_CSS, bars, overlay_hist, scatter  # noqa: E402

MAX_VALS = 60000          # per column per side; deterministic stride sampling keeps it reproducible
MAX_FILES = 60            # per family per side when the dir holds one file per entity
MAX_SCAN_ROWS = 400000    # hard cap per family per side so a 5M-row file cannot wedge the render
MAX_PQ_COLS = 160         # wide-parquet column cap (numerai: 2,789 features) — reported, never silent
MAX_ROW_GROUPS = 8        # row groups read per parquet file, spread evenly across the file
COL_CAP_NOTE = ""         # set when a column cap was applied, surfaced in the report


def pick_cols(names, cap):
    """Keep anything that looks like a target/label/id, then an even spread of the rest — a contiguous head
    slice of a wide feature table is a slice of one feature FAMILY, not a sample of the table."""
    key = [n for n in names if re.search(r"target|label|era|id$|^id|date|time|weight", str(n), re.I)][:cap // 3]
    rest = [n for n in names if n not in key]
    room = max(1, cap - len(key))
    if len(rest) > room:
        st = len(rest) / room
        rest = [rest[int(k * st)] for k in range(room)]
    return key + rest


def resolve_dir(key):
    """exact → REGISTRY dir column → evolve_map → longest-token fuzzy. Registry beats fuzzy because keys
    and directory names diverge here by design (key `rogii-wellbore-geology` → dir `campaigns/rogii_wellbore`),
    and a view built from the wrong campaign is worse than no view: plain fuzzy resolved that key to
    `rogii-wellbore-geology/`, an empty sibling. Same class preflight.sh guards (202604180003 mis-routing)."""
    # REGISTRY FIRST — before the same-named directory. A dir named exactly like the key can exist and still be
    # the wrong one: `campaigns/rogii-wellbore-geology/` is an empty leftover while the registry row for that key
    # points at `campaigns/rogii_wellbore/` where all the work is. Trusting the name over the registry is how the
    # cockpit showed a blank record for the most active competition in the portfolio.
    # Registry dir paths are repo-root-relative ("competitions/control_tower/campaigns/x"); the repo root is two
    # levels above CT. Anchoring one level up silently made every row isdir()=False — dead code.
    roots = [os.path.dirname(os.path.dirname(CT)), os.path.dirname(CT), CT]
    reg = os.path.join(CT, "portfolio_registry.tsv")
    if os.path.isfile(reg):
        best = None
        for line in open(reg, encoding="utf-8", errors="replace"):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 2 or not f[1]:
                continue
            cand = ""
            for rt in ([""] if os.path.isabs(f[1]) else roots):
                c = f[1] if os.path.isabs(f[1]) else os.path.join(rt, f[1])
                if os.path.isdir(c):
                    cand = c
                    break
            if not cand:
                continue
            if f[0] == key:
                return cand
            if best is None and (key in f[0] or f[0] in key):
                best = cand
        if best:
            return best
    d = os.path.join(CT, "campaigns", key)
    if os.path.isdir(d):
        return d
    em = os.path.join(os.environ.get("PH_RUNS", os.path.join(CT, ".runs")), "evolve_map.tsv")
    if os.path.isfile(em):
        for line in open(em, encoding="utf-8", errors="replace"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2 and f[0] == key and os.path.isdir(f[1]):
                return f[1]
    toks = [t for t in key.replace("_", "-").split("-") if not t.isdigit()]
    toks.sort(key=len, reverse=True)
    for t in toks:
        hits = [h for h in sorted(glob.glob(os.path.join(CT, "campaigns", "*%s*" % t))) if os.path.isdir(h)]
        if hits:
            return hits[0]
    return None


def family_of(path):
    """`<entity>__horizontal_well.csv` → 'horizontal_well'; `train_features.csv` → 'train_features';
    plain `train.csv` → '' (single table)."""
    b = os.path.basename(path)
    stem = b[:-4] if b.lower().endswith(".csv") else b
    if "__" in stem:
        return stem.rsplit("__", 1)[1]
    return stem


def stride(seq, cap):
    if len(seq) <= cap:
        return seq
    st = len(seq) // cap + 1
    return seq[::st][:cap]


def _pandas():
    """parquet support is OPTIONAL: used when pandas is importable (numerai ships v5.2/*.parquet), absent in
    the shipping container. Never a hard dependency — the CSV path is stdlib and always works."""
    try:
        import pandas  # noqa: F401
        return pandas
    except Exception:
        return None


def _exts():
    return ("csv", "parquet") if _pandas() else ("csv",)


def search_bases(d):
    """d, d/data, and one level of subdirectories under each — covers `open/`, `v5.2/`, `dataset/` layouts
    without walking a 49G campaign tree."""
    bases, seen = [], set()
    for b in (d, os.path.join(d, "data")):
        if not os.path.isdir(b):
            continue
        for cand in [b] + sorted(p for p in glob.glob(os.path.join(b, "*")) if os.path.isdir(p))[:24]:
            rp = os.path.realpath(cand)
            if rp not in seen:
                seen.add(rp)
                bases.append(cand)
    return bases


def find_families(d):
    """Return (how, [(family, train_files, test_files, n_train_entities, n_test_entities)])."""
    for base in search_bases(d):
        for tn, sn in (("train", "test"), ("train", "valid"), ("train", "public"), ("train", "live")):
            for ext in _exts():
                d1, d2 = os.path.join(base, tn), os.path.join(base, sn)
                g1 = sorted(glob.glob(os.path.join(d1, "*." + ext))) if os.path.isdir(d1) else []
                g2 = sorted(glob.glob(os.path.join(d2, "*." + ext))) if os.path.isdir(d2) else []
                if g1 and g2:
                    fams, out = {}, []
                    for side, g in (("a", g1), ("b", g2)):
                        for p in g:
                            fams.setdefault(family_of(p), {"a": [], "b": []})[side].append(p)
                    for fam, s in sorted(fams.items()):
                        if s["a"] and s["b"]:
                            out.append((fam, stride(s["a"], MAX_FILES), stride(s["b"], MAX_FILES),
                                        len(s["a"]), len(s["b"]),
                                        {entity_of(p) for p in s["a"]}, {entity_of(p) for p in s["b"]}))
                    if out:
                        return "%s/{%s,%s}/*.%s" % (os.path.basename(base) or ".", tn, sn, ext), out
                f1 = sorted(glob.glob(os.path.join(base, tn + "*." + ext)))
                f2 = sorted(glob.glob(os.path.join(base, sn + "*." + ext)))
                if f1 and f2:
                    out = []
                    for p1 in f1:
                        suf = os.path.basename(p1)[len(tn):]
                        m = [p for p in f2 if os.path.basename(p)[len(sn):] == suf]
                        if m:
                            out.append((family_of(p1) or "main", [p1], m[:1], 1, 1,
                                        {entity_of(p1)}, {entity_of(m[0])}))
                    if not out:
                        out = [("main", f1[:1], f2[:1], 1, 1, {entity_of(f1[0])}, {entity_of(f2[0])})]
                    return "%s/%s*.%s" % (os.path.basename(base) or ".", tn, ext), out
    return "", []


# SAMPLING DISCIPLINE — read the WHOLE file at a stride, never the head.
# Caught the hard way: capping at the first 400k rows of numerai's train.parquet returned a *single* value
# for every feature (the earliest eras are neutral-filled), which made 1,140 of 2,789 features look like
# MAJOR train↔test shifts. A head sample of an ordered file (by era, by well, by date) is not a sample of
# the file — it is a sample of its beginning, and every dataset that matters here is ordered.
def read_parquet(files):
    """MEMORY-BOUNDED. `pd.read_parquet(whole_file)` on numerai's train.parquet (2.75M rows × 2,789 int8
    columns) reached 30 GB RSS on this box before it was killed — a "just read it" tool that can OOM the
    machine other drives are running on is not shippable. So: read a spread of ROW GROUPS, and cap the
    column count (reported, never silent). Falls back to a column-capped full read when pyarrow is absent."""
    pd = _pandas()
    vals, seen, nonnum, sampled, total = {}, [], set(), 0, 0
    budget = max(2000, MAX_VALS // max(1, len(files)))
    try:
        import pyarrow.parquet as pq
    except Exception:
        pq = None
    for fp in files:
        df = None
        if pq is not None:
            try:
                pf = pq.ParquetFile(fp)
                names = list(pf.schema_arrow.names)
                cols = names if len(names) <= MAX_PQ_COLS else pick_cols(names, MAX_PQ_COLS)
                ng = pf.num_row_groups
                groups = list(range(ng)) if ng <= MAX_ROW_GROUPS else \
                    [int(round(k * (ng - 1) / (MAX_ROW_GROUPS - 1))) for k in range(MAX_ROW_GROUPS)]
                total += pf.metadata.num_rows
                for c in names:                                # header order = FULL schema, not the sample
                    if str(c) not in seen:
                        seen.append(str(c))
                parts = []
                for g in sorted(set(groups)):
                    t = pf.read_row_group(g, columns=cols)
                    d = t.to_pandas()
                    st = max(1, len(d) // max(1, budget // max(1, len(set(groups)))))
                    parts.append(d.iloc[::st])
                    del t, d
                df = pd.concat(parts, ignore_index=True) if parts else None
                del parts
                if df is not None:
                    sampled += len(df)
                    if len(names) > MAX_PQ_COLS:
                        global COL_CAP_NOTE
                        COL_CAP_NOTE = "sampled %d of %d columns (cap MAX_PQ_COLS=%d)" % (
                            len(cols), len(names), MAX_PQ_COLS)
            except Exception:
                df = None
        if df is None:
            try:
                df = pd.read_parquet(fp)
            except Exception:
                continue
            for c in df.columns:
                if str(c) not in seen:
                    seen.append(str(c))
            n = len(df)
            total += n
            st = max(1, n // budget)
            df = df.iloc[::st]
            sampled += len(df)
        for c in df.columns:
            name = str(c)
            s = df[c]
            if str(s.dtype) == "object" or str(s.dtype).startswith("categor"):
                nonnum.add(name)
                continue
            try:
                v = [float(x) for x in s.dropna().tolist()]
            except (TypeError, ValueError):
                nonnum.add(name)
                continue
            v = [x for x in v if not math.isnan(x) and not math.isinf(x)]
            if v:
                vals.setdefault(name, []).extend(v[:MAX_VALS])
    numeric = {k: v for k, v in vals.items() if k not in nonnum and len(v) >= 20}
    return numeric, seen, sampled, sorted(nonnum), total


def count_rows(fp):
    try:
        with open(fp, "rb") as fh:
            n = 0
            while True:
                blk = fh.read(1 << 20)
                if not blk:
                    break
                n += blk.count(b"\n")
        return max(0, n - 1)                                   # minus header
    except OSError:
        return 0


def read_cols(files):
    """{col: [values]} for numeric columns + header order + (rows sampled, non-numeric cols, total rows).
    Two passes per CSV: count rows, then take every st-th row so the sample spans the whole file."""
    if files and files[0].lower().endswith(".parquet"):
        return read_parquet(files)
    vals, seen, nonnum, sampled, total = {}, [], set(), 0, 0
    budget = max(2000, MAX_SCAN_ROWS // max(1, len(files)))
    for fp in files:
        n = count_rows(fp)
        total += n
        st = max(1, n // budget) if n else 1
        try:
            with open(fp, newline="", encoding="utf-8", errors="replace") as fh:
                rd = csv.reader(fh)
                try:
                    hdr = [h.strip() for h in next(rd)]
                except StopIteration:
                    continue
                for h in hdr:
                    if h and h not in seen:
                        seen.append(h)
                for i, row in enumerate(rd):
                    if st > 1 and i % st:
                        continue
                    sampled += 1
                    for h, cell in zip(hdr, row):
                        if not h:
                            continue
                        cell = cell.strip()
                        if cell == "" or cell.lower() in ("nan", "na", "null", "none"):
                            continue
                        try:
                            v = float(cell)
                        except ValueError:
                            nonnum.add(h)
                            continue
                        if math.isnan(v) or math.isinf(v):
                            continue
                        b = vals.setdefault(h, [])
                        if len(b) < MAX_VALS:
                            b.append(v)
        except OSError:
            continue
    numeric = {k: v for k, v in vals.items() if k not in nonnum and len(v) >= 20}
    return numeric, seen, sampled, sorted(nonnum), total


def ks(a, b):
    """Two-sample KS distance, TIE-CORRECT: the CDFs may only be compared at distinct values. Advancing one
    pointer per step (the naive form) reported KS≈1.0 for every one of numerai's 2,789 quantised features —
    a five-level feature is nearly all ties, so the walk drifted the two CDFs apart. Caught because PSI said
    0.0 on the same columns; two instruments disagreeing is the signal that one of them is broken."""
    if not a or not b:
        return None
    a, b = sorted(a), sorted(b)
    na, nb, i, j, d = len(a), len(b), 0, 0, 0.0
    while i < na and j < nb:
        v = a[i] if a[i] < b[j] else b[j]
        while i < na and a[i] == v:
            i += 1
        while j < nb and b[j] == v:
            j += 1
        d = max(d, abs(i / na - j / nb))
    return d


def psi(a, b, bins=10):
    """PSI on train quantiles, with a DISCRETE branch: a quantised column (≤20 distinct values, e.g. numerai's
    {0,.25,.5,.75,1}) collapses every decile edge onto the same value, so quantile-PSI reports 0.0 no matter
    how different the two samples are. For those, compare the value distributions directly."""
    if not a or not b or len(a) < 20:
        return None
    uniq = sorted(set(a))
    if len(uniq) <= 20:
        ub = set(b)
        keys = sorted(set(uniq) | ub)
        na, nb = len(a), len(b)
        ca = {k: 0 for k in keys}
        cb = {k: 0 for k in keys}
        for v in a:
            ca[v] += 1
        for v in b:
            if v in cb:
                cb[v] += 1
        tot = 0.0
        for k in keys:
            pa_ = max(ca[k] / na, 1e-6)
            pb_ = max(cb[k] / nb, 1e-6)
            tot += (pb_ - pa_) * math.log(pb_ / pa_)
        return tot
    if len(a) < bins * 2:
        return None
    s = sorted(a)
    edges = sorted(set(s[int(k * (len(s) - 1) / bins)] for k in range(1, bins)))
    nb_ = len(edges) + 1

    def dist(x):
        c = [0] * nb_
        for v in x:
            k = 0
            while k < nb_ - 1 and v > edges[k]:
                k += 1
            c[k] += 1
        n = max(1, len(x))
        return [max(ci / n, 1e-6) for ci in c]

    pa, pb = dist(a), dist(b)
    return sum((pb[k] - pa[k]) * math.log(pb[k] / pa[k]) for k in range(nb_))


def stats(v):
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(max(0.0, sum((x - m) ** 2 for x in v) / max(1, n - 1)))
    s = sorted(v)
    return {"n": n, "mean": m, "std": sd, "min": s[0], "max": s[-1], "p50": s[n // 2],
            "p01": s[int(0.01 * (n - 1))], "p99": s[int(0.99 * (n - 1))]}


def verdict(k, p):
    if k is None:
        return "—", 0
    if (p is not None and p > 0.25) or k > 0.20:
        return "MAJOR SHIFT", 3
    if (p is not None and p > 0.10) or k > 0.10:
        return "shifted", 2
    if k > 0.05:
        return "minor", 1
    return "aligned", 0


def images(d):
    out = []
    for pat in ("*.png", "*.jpg", "*.jpeg", "*.svg"):
        for base in ("data/train", "data/test", "data", ""):
            out += glob.glob(os.path.join(d, base, pat))
    return sorted(set(out))


def entity_of(path):
    """`<entity>__horizontal_well.csv` → '<entity>'; otherwise the stem."""
    b = os.path.basename(path)
    stem = re.sub(r"\.(csv|parquet)$", "", b, flags=re.I)
    return stem.split("__", 1)[0] if "__" in stem else stem


def placeholder_test(a, b):
    """Is the local 'test' folder actually EXAMPLE data — copies of train entities, replaced at rerun?

    Learned from being wrong: this tool reported rogii's 3 local test wells as the scored test set and produced
    a drift table for them. The drive worker refuted it with a decisive check — all 3 wells also exist in
    train/, identical on every shared column, and the train copies still carry the target, so an exact lookup
    would score 0.000 while public #1 is 4.859. The graded set is ~200 hidden wells swapped in at rerun.
    Comparing train against copies of train is a *guaranteed* null: it manufactures 'shift' out of sampling
    noise and hides that no drift measurement is available at all. So detect it and say so loudly."""
    if not b:
        return None
    inter = a & b
    frac = len(inter) / len(b)
    if frac >= 0.5:
        return {"shared_entities": len(inter), "test_entities": len(b), "frac": frac,
                "examples": sorted(inter)[:5]}
    return None


def analyse(fam, tr_f, te_f, n_tr_ent, n_te_ent, tr_ents, te_ents):
    tr, tr_hdr, tr_rows, tr_nn, tr_tot = read_cols(tr_f)
    te, te_hdr, te_rows, te_nn, te_tot = read_cols(te_f)
    placeholder = placeholder_test(tr_ents, te_ents)
    shared = [c for c in tr if c in te]
    rows = []
    for c in shared:
        k, p = ks(tr[c], te[c]), psi(tr[c], te[c])
        st, sv = stats(tr[c]), stats(te[c])
        vd, sev = verdict(k, p)
        rows.append({"col": c, "ks": k, "psi": p, "verdict": vd, "sev": sev,
                     "shift_sd": (sv["mean"] - st["mean"]) / st["std"] if st["std"] > 0 else 0.0,
                     "train": st, "test": sv})
    rows.sort(key=lambda r: (-(r["ks"] or 0), -(r["psi"] or 0)))
    if placeholder:                      # train-vs-copies-of-train is a guaranteed null: void the verdicts
        for r in rows:
            r["verdict"], r["sev"] = "n/a (same population)", 0
    return {"family": fam, "placeholder_test": placeholder, "train_files": len(tr_f), "test_files": len(te_f),
            "train_entities": n_tr_ent, "test_entities": n_te_ent,
            "train_rows": tr_rows, "test_rows": te_rows,
            "train_rows_total": tr_tot, "test_rows_total": te_tot, "columns": rows,
            "only_in_train": [c for c in tr_hdr if c and c not in te_hdr],
            "only_in_test": [c for c in te_hdr if c and c not in tr_hdr],
            "non_numeric": sorted(set(tr_nn) | set(te_nn))[:12],
            "_tr": tr, "_te": te}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    d = a.dir or resolve_dir(a.key)
    if not d or not os.path.isdir(d):
        print("campaign dir not found for '%s'" % a.key)
        return 1
    how, fams = find_families(d)
    if not fams:
        print("== ph view [%s] ==\n  no train/test CSV pair found under %s" % (a.key, d))
        print("  looked for: {train,test}*.csv and {train,test}/*.csv under ./ and ./data/")
        print("  → itself a finding: this drive has no local structure to compare. Fetch the data into the")
        print("    campaign dir, or pass --dir where it lives.")
        return 1

    res = [analyse(*f) for f in fams]
    imgs = images(d)
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outdir = a.out or os.path.join(d, "VIEW")
    os.makedirs(outdir, exist_ok=True)

    # ---------- numbers (machine lane: gap_hunt → BRIEF_BANK) ----------
    with open(os.path.join(outdir, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"key": a.key, "dir": d, "at": at, "how": how, "images_unread": len(imgs),
                   "families": [{k: v for k, v in r.items() if not k.startswith("_")} for r in res]},
                  fh, indent=1)

    md = ["# VIEW — train↔test geometry [%s]" % a.key, "",
          "generated %s · source `%s` · %d file family/families · %d unread image(s) in the data dir%s"
          % (at, how, len(res), len(imgs), (" · " + COL_CAP_NOTE) if COL_CAP_NOTE else ""), ""]
    imbalance = []
    for r in res:
        major = [c for c in r["columns"] if c["sev"] == 3]
        md += ["## family `%s`" % (r["family"] or "main"), ""]
        if r.get("placeholder_test"):
            ph = r["placeholder_test"]
            md += ["> ⛔ **THE LOCAL TEST FILES ARE EXAMPLE DATA, NOT THE GRADED SET.** %d of %d test entities"
                   " also exist in train (%.0f%%; e.g. %s). A rerun-style competition swaps the real test set"
                   " in at scoring time, so everything below compares train against copies of train: the drift"
                   " numbers are sampling noise, not shift, and **no train↔graded-set drift measurement is"
                   " obtainable from local files**. Treat the absence of that measurement as the finding."
                   % (ph["shared_entities"], ph["test_entities"], 100 * ph["frac"], ", ".join(ph["examples"])),
                   ""]
        md += [
               "- entities: **train %d · test %d**%s" % (
                   r["train_entities"], r["test_entities"],
                   "  ⚠ scored on %d — a CV averaged over %d units is a different estimator than this"
                   " leaderboard" % (r["test_entities"], r["train_entities"])
                   if r["test_entities"] and r["train_entities"] / max(1, r["test_entities"]) >= 10 else ""),
               "- rows: train %d sampled of %d · test %d of %d (strided across whole files, never the head)"
               " · files sampled %d / %d" % (
                   r["train_rows"], r["train_rows_total"], r["test_rows"], r["test_rows_total"],
                   r["train_files"], r["test_files"]),
               "- shared numeric columns: %d · MAJOR shifts: %d" % (len(r["columns"]), len(major)),
               "- only in TRAIN (targets / potential leaks): %s" % (
                   ", ".join("`%s`" % c for c in r["only_in_train"][:12]) or "none"),
               "- only in TEST (schema mismatch — a submission built on train columns will break): %s" % (
                   ", ".join("`%s`" % c for c in r["only_in_test"][:12]) or "none"), "",
               "| column | KS | PSI | mean shift (train σ) | verdict |", "|---|---|---|---|---|"]
        for c in r["columns"][:30]:
            md.append("| `%s` | %s | %s | %+.2f | %s |" % (
                c["col"], "%.4f" % c["ks"] if c["ks"] is not None else "—",
                "%.4f" % c["psi"] if c["psi"] is not None else "—", c["shift_sd"], c["verdict"]))
        md.append("")
        if (not r.get("placeholder_test")) and r["test_entities"] \
           and r["train_entities"] / max(1, r["test_entities"]) >= 10:
            imbalance.append(r)
    if imbalance:
        md += ["## the entity-count fact (read this before trusting any local gain)", ""]
        for r in imbalance:
            md.append("- `%s`: %d train entities vs **%d** test entities. A gain measured as a mean over"
                      " %d units can be invisible — or reversed — on %d. Before shipping, score the"
                      " candidate on %d-entity subsamples and report the spread, not the mean."
                      % (r["family"] or "main", r["train_entities"], r["test_entities"],
                         r["train_entities"], r["test_entities"], r["test_entities"]))
        md.append("")
    if imgs:
        md += ["## unread visual assets", "",
               "- **%d** image(s) sit in the data directory and no lens has opened them. If the signal is"
               " geometric, it is there. (`ph view` lists them; a vision-capable lens can read them.)" % len(imgs), ""]
    if any(c["sev"] == 3 for r in res for c in r["columns"] if not r.get("placeholder_test")):
        md += ["## what this means for the next drive", "",
               "Where test does not look like train, a model tuned on train CV is being scored on a different",
               "distribution in exactly those coordinates — comparator mismatch, not a modelling ceiling.",
               "Levers: reweight train toward the test marginal · robustify/drop the worst-shifted features ·",
               "build the validation split to *reproduce* the shift (adversarial validation) before trusting",
               "any local gain · check whether the shift is nuisance (e.g. absolute coordinates differ per",
               "entity by construction) rather than signal — a picture separates those two in seconds."]
    with open(os.path.join(outdir, "FINDINGS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    # ---------- picture (human lane: founder's 5% steering) ----------
    sections = []
    for r in res:
        cols = r["columns"]
        charts = []
        for c in cols[:max(1, a.top)]:
            charts.append('<figure class="c"><figcaption class="vd v%d">%s — %s</figcaption>%s</figure>'
                          % (c["sev"], c["col"], c["verdict"],
                             overlay_hist(r["_tr"][c["col"]], r["_te"][c["col"]], c["col"], "train", "test",
                                          note="KS %.3f · PSI %s" % (
                                              c["ks"] or 0,
                                              "%.3f" % c["psi"] if c["psi"] is not None else "—"))))
        drift = bars([c["col"][:14] for c in cols[:14]], [c["ks"] or 0 for c in cols[:14]],
                     "drift by column (KS, worst first)") if cols else ""
        sc = ""
        if len(cols) >= 2:
            c1, c2 = cols[0]["col"], cols[1]["col"]
            n = min(len(r["_tr"][c1]), len(r["_tr"][c2]), 4000)
            sc = ('<figure class="c"><figcaption>2D geometry — two most-shifted columns (train)</figcaption>%s</figure>'
                  % scatter(r["_tr"][c1][:n], r["_tr"][c2][:n], "%s × %s" % (c1, c2), xlab=c1, ylab=c2))
        ent = ""
        if r.get("placeholder_test"):
            ph = r["placeholder_test"]
            ent = ('<div class="warn"><b>The local test files are EXAMPLE data, not the graded set.</b> %d of %d '
                   'test entities also exist in train (%.0f%%). A rerun-style competition swaps the real test '
                   'set in at scoring time — the charts below compare train against copies of train, so they '
                   'show sampling noise, not shift. No train↔graded-set drift measurement is obtainable from '
                   'local files.</div>' % (ph["shared_entities"], ph["test_entities"], 100 * ph["frac"]))
        elif r["test_entities"] and r["train_entities"] / max(1, r["test_entities"]) >= 10:
            ent = ('<div class="warn"><b>%d train entities vs %d test entities.</b> A CV mean over %d units'
                   ' and a leaderboard over %d are different estimators — report the spread over %d-entity'
                   ' subsamples, not the mean.</div>'
                   % (r["train_entities"], r["test_entities"], r["train_entities"],
                      r["test_entities"], r["test_entities"]))
        sections.append(
            '<section><h2>family <code>%s</code></h2><div class="meta">train %d entities · %d of %d rows '
            'sampled · test %d entities · %d of %d rows · %d shared numeric columns</div>%s%s'
            '<div class="grid">%s%s</div>'
            '<ul class="lb"><li>only in TRAIN: %s</li><li>only in TEST: %s</li></ul></section>'
            % (r["family"] or "main", r["train_entities"], r["train_rows"], r["train_rows_total"],
               r["test_entities"], r["test_rows"], r["test_rows_total"], len(cols), ent, drift,
               "".join(charts), sc,
               ", ".join("<code>%s</code>" % c for c in r["only_in_train"][:12]) or "none",
               ", ".join("<code>%s</code>" % c for c in r["only_in_test"][:12]) or "none"))
    imglist = ""
    if imgs:
        imglist = ('<section><h2>unread visual assets (%d)</h2><p class="lb">These sit in the data directory'
                   ' and no lens has opened them. If the signal is geometric, it is here.</p>'
                   '<ul class="files">%s</ul></section>'
                   % (len(imgs), "".join('<li><a href="file://%s">%s</a></li>'
                                         % (p, os.path.relpath(p, d)) for p in imgs[:36])))
    html = """<!doctype html><meta charset="utf-8"><title>VIEW %s</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light dark}
body{font:14px/1.55 ui-sans-serif,system-ui,-apple-system,sans-serif;margin:0;padding:28px 22px 64px;
 color:#16181d;background:#fbfbfc;max-width:1180px}
@media(prefers-color-scheme:dark){body{color:#e6e7ea;background:#0f1115}}
:root[data-theme=dark] body{color:#e6e7ea;background:#0f1115}
:root[data-theme=light] body{color:#16181d;background:#fbfbfc}
h1{font-size:19px;margin:0 0 4px}h2{font-size:14px;margin:34px 0 8px;letter-spacing:.02em}
.meta{font:11.5px ui-monospace,monospace;opacity:.62;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:20px;margin-top:14px}
figure.c{margin:0;padding:12px 12px 8px;border:1px solid color-mix(in srgb,currentColor 14%%,transparent);
 border-radius:10px;background:color-mix(in srgb,currentColor 3%%,transparent);overflow-x:auto}
figcaption{font:600 12px ui-monospace,monospace;margin-bottom:6px}
.vd.v3{color:#ef4444}.vd.v2{color:#f59e0b}.vd.v1{opacity:.8}.vd.v0{opacity:.55}
.lb{font-size:12px;opacity:.72}code{font:11.5px ui-monospace,monospace}
.files{font:11.5px ui-monospace,monospace;columns:3;opacity:.8}
.warn{border-left:3px solid #ef4444;padding:8px 12px;margin:12px 0;
 background:color-mix(in srgb,#ef4444 8%%,transparent);border-radius:0 6px 6px 0;font-size:13px}
%s</style>
<h1>VIEW — train ↔ test geometry · %s</h1>
<div class="meta">%s · source <code>%s</code> · %d family/families · %d unread image(s)</div>
%s
%s
<div class="meta">numbers for the machine lane: VIEW/FINDINGS.md · VIEW/findings.json</div>
""" % (a.key, PAGE_CSS, a.key, at, how, len(res), len(imgs), "".join(sections), imglist)
    idx = os.path.join(outdir, "index.html")
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write(html)

    print("== ph view [%s] ==" % a.key)
    print("  source: %s · %d family/families · %d unread image(s)%s"
          % (how, len(res), len(imgs), (" · " + COL_CAP_NOTE) if COL_CAP_NOTE else ""))
    for r in res:
        major = [c for c in r["columns"] if c["sev"] == 3]
        print("  ── family %-18s entities train %d / test %d · rows sampled %d/%d vs %d/%d · shared %d · MAJOR %d"
              % (r["family"] or "main", r["train_entities"], r["test_entities"],
                 r["train_rows"], r["train_rows_total"], r["test_rows"], r["test_rows_total"],
                 len(r["columns"]), len(major)))
        for c in r["columns"][:5]:
            print("       %-22s KS %s  PSI %s  %+.2fσ  %s" % (
                c["col"][:22], "%.4f" % c["ks"] if c["ks"] is not None else "  —  ",
                "%.4f" % c["psi"] if c["psi"] is not None else "  —  ", c["shift_sd"], c["verdict"]))
        if r.get("placeholder_test"):
            ph = r["placeholder_test"]
            print("       ⛔ local test = EXAMPLE data (%d/%d test entities are also train entities) —"
                  " rerun-style competition; drift numbers above are train-vs-train noise"
                  % (ph["shared_entities"], ph["test_entities"]))
        if r["only_in_test"]:
            print("       ⚠ only in TEST (schema mismatch): %s" % ", ".join(r["only_in_test"][:8]))
        if (not r.get("placeholder_test")) and r["test_entities"] \
           and r["train_entities"] / max(1, r["test_entities"]) >= 10:
            print("       ⚠ %d train entities vs %d test — CV mean and LB are different estimators"
                  % (r["train_entities"], r["test_entities"]))
    print("  → picture: %s" % idx)
    print("  → numbers: %s/FINDINGS.md   (fold into the drive brief: ph gap comp %s)" % (outdir, a.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
