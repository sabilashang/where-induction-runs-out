"""Task 1: truncation confound on the 1887 'genuine' prefix-only cohort.

For each A-number in results/list_1887.txt, load FULL terms from stripped.gz
and run guess_prec(strict_leading=False). Classify:
  (i)   operator found at full length      -> truncation_artifact
  (ii)  none, n_terms >= 40                -> genuine_spurious
  (iii) none, n_terms < 40                 -> undetermined
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import guess_prec, literal_cost

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)


def load_full(path, anums):
    want = set(anums)
    out = {}
    with gzip.open(path, "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            anum = parts[0].strip()
            if anum not in want:
                continue
            vals = []
            for tok in parts[1:]:
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    vals.append(int(tok))
                except ValueError:
                    break
            out[anum] = vals
            if len(out) == len(want):
                break
    return out


def process(job):
    anum, seq = job
    try:
        lit = literal_cost(seq)
        hyp = guess_prec(
            seq, max_order=6, max_degree=4, slack=2,
            best_bits=lit, strict_leading=False,
        )
        found = hyp is not None and hyp.description_length() < lit
        n = len(seq)
        if found:
            cls = "truncation_artifact"
        elif n >= 40:
            cls = "genuine_spurious"
        else:
            cls = "undetermined"
        return {
            "anum": anum,
            "n_terms": n,
            "found": bool(found),
            "class": cls,
            "order": hyp.order if found else None,
            "degree": hyp.degree if found else None,
            "L_H": hyp.description_length() if found else None,
            "n_singular": len(hyp.singular_terms) if found else None,
            "error": None,
        }
    except Exception as exc:
        return {"anum": anum, "error": repr(exc)[:200], "class": "error"}


def term_dist(series):
    s = series.dropna().astype(int)
    if len(s) == 0:
        return {"n": 0}
    return {
        "n": int(len(s)),
        "min": int(s.min()),
        "median": float(s.median()),
        "mean": float(s.mean()),
        "max": int(s.max()),
    }


def main():
    anums = [ln.strip() for ln in open("results/list_1887.txt") if ln.strip()]
    print(f"list_1887 size: {len(anums)}")
    assert len(anums) == 1887, len(anums)
    seqs = load_full("stripped.gz", anums)
    print(f"loaded: {len(seqs)}")
    jobs = [(a, seqs[a]) for a in anums if a in seqs]
    assert len(jobs) == 1887, len(jobs)

    rows = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        for i, row in enumerate(ex.map(process, jobs, chunksize=8), 1):
            rows.append(row)
            if i % 200 == 0:
                print(f"  {i}/{len(jobs)}")

    df = pd.DataFrame(rows)
    df.to_csv("results/truncation_1887.csv", index=False)

    # conservation
    vc = df["class"].value_counts()
    n_i = int(vc.get("truncation_artifact", 0))
    n_ii = int(vc.get("genuine_spurious", 0))
    n_iii = int(vc.get("undetermined", 0))
    n_err = int(vc.get("error", 0))
    total = n_i + n_ii + n_iii + n_err
    print(f"(i) truncation_artifact : {n_i}/{1887} ({100*n_i/1887:.4f}%)")
    print(f"(ii) genuine_spurious   : {n_ii}/{1887} ({100*n_ii/1887:.4f}%)")
    print(f"(iii) undetermined      : {n_iii}/{1887} ({100*n_iii/1887:.4f}%)")
    print(f"errors                  : {n_err}/{1887}")
    print(f"sum                     : {total} (must be 1887)")
    if total != 1887:
        print("STOP: conservation failed")
        sys.exit(3)
    if n_i > n_ii and n_i > n_iii:
        print("PLAIN: (i) truncation artifacts DOMINATE")

    summary = {
        "n": 1887,
        "truncation_artifact": n_i,
        "genuine_spurious": n_ii,
        "undetermined": n_iii,
        "error": n_err,
        "pct_truncation_artifact": 100 * n_i / 1887,
        "pct_genuine_spurious": 100 * n_ii / 1887,
        "pct_undetermined": 100 * n_iii / 1887,
        "terms_dist_by_class": {
            cls: term_dist(df.loc[df["class"] == cls, "n_terms"])
            for cls in ["truncation_artifact", "genuine_spurious", "undetermined"]
        },
    }
    with open("results/truncation_1887_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    print("wrote results/truncation_1887.csv")
    print("wrote results/truncation_1887_summary.json")


if __name__ == "__main__":
    main()
