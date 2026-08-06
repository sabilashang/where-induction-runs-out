"""Task 2: encoding ablation on the classical 61-sequence corpus.

Runs revision spectra under strict_leading=True and False.
Writes results/ablation_encoding.csv and results/ablation_encoding_summary.json.
Does NOT overwrite existing classical results/*.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import guess_prec, literal_cost, revision_spectrum
from revspec.corpus import build_corpus

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

SLACK, N_MIN, MAX_ORDER, MAX_DEGREE = 2, 6, 6, 4


def run_one(entry: dict, strict_leading: bool) -> dict:
    seq = entry["seq"]
    res = revision_spectrum(
        seq, name=entry["name"], anum=entry["anum"],
        true_class=entry["true_class"],
        n_min=N_MIN, max_order=MAX_ORDER, max_degree=MAX_DEGREE, slack=SLACK,
        strict_leading=strict_leading,
    )
    lit = literal_cost(list(seq))
    hyp = guess_prec(
        seq, max_order=MAX_ORDER, max_degree=MAX_DEGREE, slack=SLACK,
        best_bits=lit, strict_leading=strict_leading,
    )
    full_fit = hyp is not None and hyp.description_length() < lit
    n_d = res.discovery_point()
    if full_fit:
        r, d = hyp.order, hyp.degree
        n_id = (r + 1) * (d + 1) + SLACK + r
        L_H = hyp.description_length()
        n_sing = len(hyp.singular_terms)
    else:
        r = d = n_id = L_H = n_sing = None
    import math
    growth = sum(math.log1p(abs(int(x))) for x in seq) / len(seq)
    return {
        "anum": entry["anum"],
        "name": entry["name"],
        "true_class": entry["true_class"],
        "strict_leading": int(strict_leading),
        "n_d": n_d,
        "n_id": n_id,
        "order": r,
        "degree": d,
        "L_H": L_H,
        "n_singular": n_sing,
        "full_fit": bool(full_fit),
        "n_revisions": res.n_revisions(),
        "n_struct_rev": res.n_structural_revisions(),
        "final_lambda": res.L[-1] / res.L_lit[-1],
        "growth": growth,
    }


def summarize(df: pd.DataFrame, label: str) -> dict:
    fit = df[df["full_fit"]].copy()
    n_fit = len(fit)
    if n_fit:
        exact = (fit["n_d"] == fit["n_id"])
        w1 = (fit["n_d"] - fit["n_id"]).abs() <= 1
        mae = (fit["n_d"] - fit["n_id"]).abs().mean()
        # corr with L_H and growth among fittable with n_d
        sub = fit.dropna(subset=["n_d", "L_H", "growth"])
        corr_struct = float(sub["n_d"].corr(sub["L_H"])) if len(sub) > 2 else None
        corr_growth = float(sub["n_d"].corr(sub["growth"])) if len(sub) > 2 else None
        mean_LH = fit.groupby("true_class")["L_H"].mean().to_dict()
        revisers = fit[fit["n_struct_rev"] > 0]
        rev_names = revisers["name"].tolist()
        rev_anums = revisers["anum"].tolist()
    else:
        exact = w1 = mae = corr_struct = corr_growth = None
        mean_LH = {}
        rev_names = rev_anums = []
        revisers = fit
    out = {
        "setting": label,
        "n_total": int(len(df)),
        "n_fitted": int(n_fit),
        "exact": int(exact.sum()) if n_fit else 0,
        "exact_frac": f"{int(exact.sum())}/{n_fit}" if n_fit else "0/0",
        "within1": int(w1.sum()) if n_fit else 0,
        "within1_frac": f"{int(w1.sum())}/{n_fit}" if n_fit else "0/0",
        "mae": float(mae) if n_fit else None,
        "corr_struct": corr_struct,
        "corr_growth": corr_growth,
        "mean_L_H_by_class": {k: float(v) for k, v in mean_LH.items()},
        "n_structural_revisers": int(len(revisers)),
        "reviser_names": rev_names,
        "reviser_anums": rev_anums,
    }
    # Fibonacci check
    fib = df[df["anum"] == "A000045"].iloc[0]
    out["fibonacci_n_d"] = fib["n_d"]
    out["fibonacci_L_H"] = fib["L_H"]
    return out


def main():
    corpus = build_corpus()
    print(f"corpus: {len(corpus)}")
    rows = []
    for strict in (True, False):
        print(f"=== strict_leading={strict} ===")
        for i, e in enumerate(corpus, 1):
            row = run_one(e, strict)
            rows.append(row)
            print(f"  [{i:02d}/61] {e['anum']} strict={int(strict)} "
                  f"n_d={row['n_d']} L_H={row['L_H']} "
                  f"struct_rev={row['n_struct_rev']}")
    df = pd.DataFrame(rows)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/ablation_encoding.csv", index=False)

    s_true = summarize(df[df.strict_leading == 1], "strict_leading=True")
    s_false = summarize(df[df.strict_leading == 0], "strict_leading=False")

    # invariant / not
    keys = [
        "n_fitted", "exact", "within1", "mae", "corr_struct", "corr_growth",
        "n_structural_revisers", "reviser_anums", "fibonacci_n_d", "fibonacci_L_H",
        "mean_L_H_by_class",
    ]
    invariant = []
    not_invariant = []
    for k in keys:
        if s_true[k] == s_false[k]:
            invariant.append(k)
        else:
            not_invariant.append({"key": k, "strict": s_true[k], "loose": s_false[k]})

    summary = {
        "strict": s_true,
        "loose": s_false,
        "invariant": invariant,
        "not_invariant": not_invariant,
    }
    with open("results/ablation_encoding_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    if s_false["fibonacci_n_d"] != 7 or s_false["fibonacci_L_H"] != 22:
        print("STOP: Fibonacci changed under strict_leading=False")
        sys.exit(4)
    print("wrote results/ablation_encoding.csv")
    print("wrote results/ablation_encoding_summary.json")


if __name__ == "__main__":
    main()
