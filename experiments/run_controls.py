"""
Experiment 3 -- two controlled studies locating the phase boundary.

Control A (growth invariance)
    Fix the operator, scale the initial conditions over nine orders of
    magnitude.  The literal cost changes enormously; n_id does not.  If
    discovery is identification-limited, n_d must be invariant.

Control B (the phase boundary)
    Periodic sequences over an alphabet of size A and period p.  Increasing p
    raises the operator cost; decreasing A lowers the literal cost per term.
    Somewhere in this plane the compression-limited regime must appear.  We map
    it, and measure whether post-discovery REVISIONS appear there.

Outputs: results/control_growth.csv, results/control_phase.csv
"""

from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import guess_prec, literal_cost, revision_spectrum

SLACK, N_MIN = 2, 6
MAX_ORDER, MAX_DEGREE = 8, 4
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


def fib_scaled(k, n=34):
    s = [0, k]
    while len(s) < n:
        s.append(s[-1] + s[-2])
    return s[:n]


def periodic(period, alphabet, n=40, seed=12345):
    """Deterministic pseudo-random periodic sequence over {0..alphabet-1}."""
    import random as _random
    _r = _random.Random(seed)
    block = [_r.randrange(alphabet) for _ in range(period)]
    if len(set(block)) == 1:            # avoid a degenerate constant block
        block[0] = (block[0] + 1) % alphabet
    return [block[i % period] for i in range(n)]


def analyse(seq, n_min=N_MIN, max_order=MAX_ORDER):
    res = revision_spectrum(seq, n_min=n_min, max_order=max_order,
                            max_degree=MAX_DEGREE, slack=SLACK)
    n_d = res.discovery_point()
    hyp = guess_prec(seq, max_order=max_order, max_degree=MAX_DEGREE,
                     slack=SLACK, best_bits=literal_cost(list(seq)))
    if hyp is None:
        return None
    r, d = hyp.order, hyp.degree
    L_H = hyp.description_length()
    n_id = (r + 1) * (d + 1) + SLACK + r
    n_x = next((n for n in range(1, len(seq) + 1)
                if literal_cost(list(seq[:n])) > L_H), None)
    return {
        "n_d": n_d, "n_id": n_id, "n_x": n_x, "order": r, "degree": d,
        "L_H": L_H, "n_rev": res.n_revisions(),
        "n_struct_rev": res.n_structural_revisions(),
        "regime": ("identification-limited" if n_x is not None and n_id >= n_x
                   else "compression-limited"),
    }


def control_a():
    print("=" * 74)
    print("CONTROL A -- growth invariance (Fibonacci, scaled initial conditions)")
    print("=" * 74)
    rows = []
    for k in [1, 10, 10**2, 10**3, 10**5, 10**7, 10**9, 10**12]:
        seq = fib_scaled(k)
        a = analyse(seq)
        lit = literal_cost(seq)
        rows.append({"scale": k, "L_lit_full": lit, **a})
        print(f"  a(1)=10^{len(str(k))-1:<2d}  L_lit={lit:7d}  "
              f"L(H)={a['L_H']:3d}  n_id={a['n_id']:3d}  n_x={a['n_x']:3d}  "
              f"n_d={a['n_d']:3d}  regime={a['regime']}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "control_growth.csv"), index=False)
    print(f"\n  n_d values: {sorted(set(df['n_d']))}   "
          f"(literal cost varied {df['L_lit_full'].min()} -> {df['L_lit_full'].max()} bits)")
    return df


def control_b():
    print("\n" + "=" * 74)
    print("CONTROL B -- phase boundary (periodic sequences, period p, alphabet A)")
    print("=" * 74)
    rows = []
    print(f"  {'A':>3s} {'p':>3s} {'L(H)':>6s} {'n_id':>5s} {'n_x':>5s} "
          f"{'n_d':>5s} {'revs':>5s}  regime")
    for A in [2, 3, 10, 1000]:
        for p in [2, 3, 4, 5, 6, 7]:
            seq = periodic(p, A, n=40)
            a = analyse(seq)
            if a is None:
                continue
            rows.append({"alphabet": A, "period": p, **a})
            print(f"  {A:>3d} {p:>3d} {a['L_H']:>6d} {a['n_id']:>5d} "
                  f"{a['n_x']:>5d} {a['n_d']:>5d} {a['n_struct_rev']:>5d}  "
                  f"{a['regime']}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "control_phase.csv"), index=False)
    print("\n  regime counts:")
    print("   ", df["regime"].value_counts().to_dict())
    cl = df[df["regime"] == "compression-limited"]
    if len(cl):
        print(f"  compression-limited cases: {len(cl)}, "
              f"mean post-discovery revisions = {cl['n_struct_rev'].mean():.2f}")
        il = df[df["regime"] == "identification-limited"]
        print(f"  identification-limited   : {len(il)}, "
              f"mean post-discovery revisions = {il['n_struct_rev'].mean():.2f}")
    return df


if __name__ == "__main__":
    control_a()
    control_b()
    print(f"\nwrote {OUT}/control_growth.csv, control_phase.csv")
