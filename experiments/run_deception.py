"""
Experiment 4 -- deceptive prefixes: a controlled generator of revisions.

A sequence has a DECEPTIVE PREFIX of depth m if its first m terms are
consistent with a strictly shorter recurrence than the one that governs the
whole sequence.  We construct such sequences exactly:

    pattern D_j = (0 1)^j 0      -- period p = 2j + 1
    s = D_j repeated

The first 2j terms alternate, so a period-2 recurrence fits them; the term at
index 2j breaks it.  The true operator has order p = 2j+1 and cannot be
identified until n ~ 2p + 3.  Sweeping j sweeps the deception depth.

We also sweep random periodic sequences to estimate how often deception occurs
without being planted.

Outputs: results/deception.csv, results/deception_random.csv
"""

from __future__ import annotations

import os
import random
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import revision_spectrum

SLACK, N_MIN = 2, 6
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


def deceptive(j, n):
    """(0 1)^j 0  repeated -- period 2j+1, deceptively period-2 for 2j terms."""
    block = [0, 1] * j + [0]
    return [block[i % len(block)] for i in range(n)]


def rand_periodic(period, alphabet, seed, n):
    """Deterministic periodic sequence from ``seed`` (reproducible unplanted rate)."""
    rng = random.Random(seed)
    block = [rng.randrange(alphabet) for _ in range(period)]
    if len(set(block)) == 1:
        block[0] = (block[0] + 1) % alphabet
    return [block[i % period] for i in range(n)]


def phases(res):
    """Extract the canonical phase structure of a revision spectrum."""
    sigs, ns = res.sig, res.n_values
    first_struct = next((n for n, l in zip(ns, res.labels) if l != "literal"), None)
    # a refutation is a step from a structural hypothesis back to literal
    refutations = [
        ns[i + 1] for i in range(len(sigs) - 1)
        if sigs[i] != "literal" and sigs[i + 1] == "literal"
    ]
    final_sig = sigs[-1]
    settle = ns[-1]
    for i in range(len(sigs) - 1, 0, -1):
        if sigs[i - 1] != final_sig:
            settle = ns[i]
            break
    else:
        settle = ns[0]
    return first_struct, refutations, settle


def main():
    print("=" * 78)
    print("PLANTED DECEPTIVE PREFIXES:  D_j = (0 1)^j 0")
    print("=" * 78)
    print(f"  {'j':>2s} {'period':>7s} {'n_terms':>8s} {'1st fit':>8s} "
          f"{'refuted':>9s} {'settle':>7s} {'revs':>5s} {'peak rho':>9s}")
    rows = []
    for j in range(1, 8):
        p = 2 * j + 1
        n_terms = max(3 * p + 12, 30)
        seq = deceptive(j, n_terms)
        res = revision_spectrum(seq, n_min=N_MIN, max_order=p + 3,
                                max_degree=1, slack=SLACK)
        first, refs, settle = phases(res)
        peak = max((abs(r) for r in res.rho), default=0.0)
        rows.append({
            "j": j, "period": p, "n_terms": n_terms,
            "first_fit": first, "n_refutations": len(refs),
            "first_refutation": refs[0] if refs else None,
            "settle": settle, "n_revisions": res.n_revisions(),
            "n_struct_rev": res.n_structural_revisions(),
            "peak_abs_rho": peak,
            "deception_span": (refs[0] - first) if (refs and first) else 0,
            "wilderness": (settle - refs[0]) if refs else 0,
        })
        print(f"  {j:>2d} {p:>7d} {n_terms:>8d} {str(first):>8s} "
              f"{str(refs[0] if refs else '--'):>9s} {settle:>7d} "
              f"{res.n_revisions():>5d} {peak:>9.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "deception.csv"), index=False)

    print("\n" + "=" * 78)
    print("UNPLANTED: random periodic binary sequences, how often is there deception?")
    print("=" * 78)
    rrows = []
    for p in range(2, 13):
        got = 0
        trials = 40
        for seed in range(trials):
            seq = rand_periodic(p, 2, seed * 7919 + 13, n=3 * p + 12)
            res = revision_spectrum(seq, n_min=N_MIN, max_order=p + 3,
                                    max_degree=1, slack=SLACK)
            if res.n_structural_revisions() > 0:
                got += 1
            rrows.append({"period": p, "seed": seed,
                          "struct_rev": res.n_structural_revisions()})
        print(f"  period {p:>2d}: {got:>2d}/{trials} sequences show a revision "
              f"({100*got/trials:5.1f}%)")
    rdf = pd.DataFrame(rrows)
    rdf.to_csv(os.path.join(OUT, "deception_random.csv"), index=False)
    overall = (rdf["struct_rev"] > 0).mean()
    print(f"\n  overall deception rate: {100*overall:.1f}% "
          f"({int((rdf['struct_rev']>0).sum())}/{len(rdf)})")
    print(f"\nwrote {OUT}/deception.csv, deception_random.csv")


if __name__ == "__main__":
    main()
