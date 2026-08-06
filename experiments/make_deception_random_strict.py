"""Unplanted deception under strict_leading=True (encoding ablation contrast).

Same seed schedule as experiments/run_deception.py unplanted sweep.
Writes:
  results/deception_random_strict.csv
  results/deception_random_strict_summary.json
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from revspec.core import revision_spectrum

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
SLACK, N_MIN = 2, 6


def rand_periodic(period: int, alphabet: int, seed: int, n: int) -> list[int]:
    rng = random.Random(seed)
    block = [rng.randrange(alphabet) for _ in range(period)]
    if len(set(block)) == 1:
        block[0] = (block[0] + 1) % alphabet
    return [block[i % period] for i in range(n)]


def main() -> None:
    rows = []
    for p in range(2, 13):
        for seed in range(40):
            seq = rand_periodic(p, 2, seed * 7919 + 13, n=3 * p + 12)
            res = revision_spectrum(
                seq,
                n_min=N_MIN,
                max_order=p + 3,
                max_degree=1,
                slack=SLACK,
                strict_leading=True,
            )
            rows.append(
                {
                    "period": p,
                    "seed": seed,
                    "struct_rev": res.n_structural_revisions(),
                }
            )
    rdf = pd.DataFrame(rows)
    rdf.to_csv(RES / "deception_random_strict.csv", index=False)
    n_pos = int((rdf.struct_rev > 0).sum())
    n = len(rdf)
    rate = 100 * n_pos / n
    by_p = {
        int(p): f"{int((g.struct_rev > 0).sum())}/{len(g)}"
        for p, g in rdf.groupby("period")
    }
    summary = {
        "strict_leading": True,
        "n": n,
        "n_struct_rev_positive": n_pos,
        "rate": n_pos / n,
        "rate_pct_1dp": round(rate, 1),
        "rate_str": f"{n_pos}/{n} ({rate:.4f}%)",
        "by_period": by_p,
        "script": "experiments/make_deception_random_strict.py",
    }
    (RES / "deception_random_strict_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("STRICT RATE", summary["rate_str"])
    print("by_period", by_p)


if __name__ == "__main__":
    main()
