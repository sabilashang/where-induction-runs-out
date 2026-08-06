"""Build the frozen 60-sequence LLM evaluation sample (20 per stratum).

STRATUM 1 clean      : holonomic, 0 structural revisions  (from oeis_fixed30)
STRATUM 2 revising   : holonomic, >=1 structural revision (from oeis_fixed30)
STRATUM 3 wilderness : prefix-only fit, >=40 terms
                       (from results/truncation_1887.csv class==genuine_spurious)

Writes results/llm_sample.txt (A-numbers, one per line, with stratum tags in
results/llm_sample.json).
"""
from __future__ import annotations

import json
import os
import random

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

SEED = 0
N_PER = 20


def main():
    fixed = pd.read_csv("results/oeis_fixed30.csv")
    hol = fixed[
        fixed["order"].notna() & fixed["degree"].notna() & fixed["n_id"].notna()
    ].copy()
    clean = hol.loc[hol["n_struct_rev"] == 0, "anum"].astype(str).tolist()
    revising = hol.loc[hol["n_struct_rev"] >= 1, "anum"].astype(str).tolist()

    trunc = pd.read_csv("results/truncation_1887.csv")
    wild = trunc.loc[
        (trunc["class"] == "genuine_spurious") & (trunc["n_terms"] >= 40),
        "anum",
    ].astype(str).tolist()

    rng = random.Random(SEED)
    assert len(clean) >= N_PER, len(clean)
    assert len(revising) >= N_PER, len(revising)
    assert len(wild) >= N_PER, len(wild)

    s1 = sorted(rng.sample(clean, N_PER))
    s2 = sorted(rng.sample(revising, N_PER))
    s3 = sorted(rng.sample(wild, N_PER))

    rows = (
        [{"anum": a, "stratum": "clean", "stratum_id": 1} for a in s1]
        + [{"anum": a, "stratum": "revising", "stratum_id": 2} for a in s2]
        + [{"anum": a, "stratum": "wilderness", "stratum_id": 3} for a in s3]
    )
    assert len(rows) == 60
    anums = [r["anum"] for r in rows]
    assert len(set(anums)) == 60, "duplicate A-numbers across strata"

    with open("results/llm_sample.txt", "w", encoding="utf-8") as fh:
        for a in anums:
            fh.write(a + "\n")
    meta = {
        "seed": SEED,
        "n_per_stratum": N_PER,
        "n_total": 60,
        "sources": {
            "clean": "results/oeis_fixed30.csv holonomic & n_struct_rev==0",
            "revising": "results/oeis_fixed30.csv holonomic & n_struct_rev>=1",
            "wilderness": "results/truncation_1887.csv class==genuine_spurious & n_terms>=40",
        },
        "pool_sizes": {
            "clean": len(clean),
            "revising": len(revising),
            "wilderness": len(wild),
        },
        "rows": rows,
    }
    with open("results/llm_sample.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"wrote results/llm_sample.txt ({len(anums)} A-numbers)")
    print(f"wrote results/llm_sample.json")
    print(f"pool sizes: clean={len(clean)} revising={len(revising)} wilderness={len(wild)}")
    for sid, label in [(1, "clean"), (2, "revising"), (3, "wilderness")]:
        xs = [r["anum"] for r in rows if r["stratum_id"] == sid]
        print(f"  stratum {sid} {label}: {xs[0]} .. {xs[-1]} (n={len(xs)})")


if __name__ == "__main__":
    main()
