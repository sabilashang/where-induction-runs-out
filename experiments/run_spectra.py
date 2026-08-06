"""
Experiment 1 -- compute the revision spectrum of every sequence in the corpus.

Outputs
-------
results/spectra.json      full L(n), lambda(n), R(n), rho(n) curves per sequence
results/features.csv      scalar spectrum features + ground-truth class
results/lcp.json          linear-complexity-profile baseline (Berlekamp-Massey)
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import linear_complexity_profile, revision_spectrum
from revspec.corpus import build_corpus

N_TERMS = 34
N_MIN = 6
MAX_ORDER = 6
MAX_DEGREE = 4
SLACK = 2

OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


def main() -> None:
    corpus = build_corpus(N_TERMS)
    print(f"corpus: {len(corpus)} sequences x {N_TERMS} terms\n")

    spectra, rows, lcps = {}, [], {}
    t_start = time.time()

    for i, item in enumerate(corpus, 1):
        t0 = time.time()
        res = revision_spectrum(
            item["seq"],
            name=item["name"],
            anum=item["anum"],
            true_class=item["true_class"],
            n_min=N_MIN,
            max_order=MAX_ORDER,
            max_degree=MAX_DEGREE,
            slack=SLACK,
        )
        dt = time.time() - t0

        spectra[item["anum"]] = {
            "name": res.name,
            "anum": res.anum,
            "true_class": res.true_class,
            "n": res.n_values,
            "L": res.L,
            "L_lit": res.L_lit,
            "lambda": [a / b for a, b in zip(res.L, res.L_lit)],
            "R": res.R,
            "rho": res.rho,
            "labels": res.labels,
            "sig": res.sig,
            "discovery": res.discovery_point(),
            "stabilisation": res.stabilisation_point(),
            "seq_head": item["seq"][:12],
        }
        lcps[item["anum"]] = linear_complexity_profile([x % 2 for x in item["seq"]])

        feats = res.features()
        rows.append({"anum": item["anum"], "name": item["name"],
                     "true_class": item["true_class"], **feats})

        print(f"[{i:2d}/{len(corpus)}] {item['anum']:10s} {item['name'][:26]:26s} "
              f"{item['true_class']}  lam={feats['final_lambda']:.4f} "
              f"n_d={str(res.discovery_point()):>4s} revs={feats['n_revisions']:2d}"
              f"  ({dt:.2f}s)")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "features.csv"), index=False)
    with open(os.path.join(OUT, "spectra.json"), "w") as f:
        json.dump(spectra, f, indent=1)
    with open(os.path.join(OUT, "lcp.json"), "w") as f:
        json.dump(lcps, f, indent=1)

    print(f"\ntotal wall time: {time.time() - t_start:.1f}s")
    print(f"wrote {OUT}/features.csv, spectra.json, lcp.json")


if __name__ == "__main__":
    main()
