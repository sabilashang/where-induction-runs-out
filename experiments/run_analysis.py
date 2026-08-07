"""
Experiment 2 -- the two-regime decomposition of the MDL discovery point.

Hypothesis
----------
The discovery point n_d (first prefix length at which a symbolic hypothesis
beats verbatim storage) is the maximum of two independent quantities:

    n_id  : IDENTIFIABILITY threshold -- the fewest terms that determine the
            operator, (r+1)(d+1) + slack + r for the selected (r, d)

    n_x   : CROSSING threshold -- the fewest terms for which the operator is
            cheaper than the literal encoding, min{ n : L_lit(n) > L(H*) }

    prediction:  n_d = max(n_id, n_x)

A sequence is IDENTIFICATION-LIMITED if n_id > n_x (the formula would pay for
itself immediately, but there is not yet enough data to pin it down) and
COMPRESSION-LIMITED if n_x > n_id (the formula is already determined, but does
not yet pay for itself).

Outputs: results/regimes.csv, results/analysis.json
"""

from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from math import log2

import numpy as np
import pandas as pd
from scipy.stats import f_oneway

from revspec.core import guess_prec, literal_cost, revision_spectrum
from revspec.corpus import build_corpus

N_TERMS, N_MIN, SLACK = 34, 6, 2
MAX_ORDER, MAX_DEGREE = 6, 4
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)


def crossing_point(seq, target_bits, n_min=1):
    """Smallest n with L_lit(s_1..s_n) > target_bits."""
    for n in range(n_min, len(seq) + 1):
        if literal_cost(list(seq[:n])) > target_bits:
            return n
    return None


def main():
    corpus = build_corpus(N_TERMS)
    rows = []

    for item in corpus:
        seq = item["seq"]
        res = revision_spectrum(seq, item["name"], item["anum"],
                                item["true_class"], n_min=N_MIN,
                                max_order=MAX_ORDER, max_degree=MAX_DEGREE,
                                slack=SLACK)
        n_d = res.discovery_point()
        lit_full = literal_cost(seq)
        hyp = guess_prec(seq, max_order=MAX_ORDER, max_degree=MAX_DEGREE,
                         slack=SLACK, best_bits=lit_full)

        if hyp is None:
            rows.append({
                "anum": item["anum"], "name": item["name"],
                "true_class": item["true_class"], "n_d": np.nan,
                "n_id": np.nan, "n_x": np.nan, "pred": np.nan,
                "order": np.nan, "degree": np.nan, "L_H": np.nan,
                "growth": log2(abs(seq[-1]) + 2) / len(seq),
                "regime": "unfittable", "n_revisions": res.n_revisions(),
                "n_struct_rev": res.n_structural_revisions(),
                "final_lambda": res.L[-1] / res.L_lit[-1],
            })
            continue

        r, d = hyp.order, hyp.degree
        L_H = hyp.description_length()
        n_id = (r + 1) * (d + 1) + SLACK + r
        n_x = crossing_point(seq, L_H) or np.nan
        pred = max(n_id, n_x) if not np.isnan(n_x) else np.nan
        regime = "identification-limited" if n_id >= n_x else "compression-limited"

        rows.append({
            "anum": item["anum"], "name": item["name"],
            "true_class": item["true_class"], "n_d": n_d,
            "n_id": n_id, "n_x": n_x, "pred": pred,
            "order": r, "degree": d, "L_H": L_H,
            "growth": log2(abs(seq[-1]) + 2) / len(seq),
            "regime": regime, "n_revisions": res.n_revisions(),
            "n_struct_rev": res.n_structural_revisions(),
            "final_lambda": res.L[-1] / res.L_lit[-1],
        })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "regimes.csv"), index=False)

    fit = df.dropna(subset=["n_d", "pred"])
    exact = int((fit["n_d"] == fit["pred"]).sum())
    within1 = int((abs(fit["n_d"] - fit["pred"]) <= 1).sum())
    mae = float(abs(fit["n_d"] - fit["pred"]).mean())

    # naive baselines
    mae_id = float(abs(fit["n_d"] - fit["n_id"]).mean())
    mae_x = float(abs(fit["n_d"] - fit["n_x"]).mean())

    print("=" * 74)
    print("TWO-REGIME DECOMPOSITION OF THE DISCOVERY POINT")
    print("=" * 74)
    print(f"fittable sequences            : {len(fit)} / {len(df)}")
    print(f"exact hits  n_d == max(n_id,n_x): {exact}/{len(fit)} "
          f"({100*exact/len(fit):.1f}%)")
    print(f"within +/-1                    : {within1}/{len(fit)} "
          f"({100*within1/len(fit):.1f}%)")
    print(f"MAE  max(n_id, n_x)            : {mae:.3f}")
    print(f"MAE  n_id alone                : {mae_id:.3f}")
    print(f"MAE  n_x  alone                : {mae_x:.3f}")

    print("\nregime split:")
    print(df["regime"].value_counts().to_string())
    print("\nregime x class:")
    print(pd.crosstab(df["true_class"], df["regime"]).to_string())

    print("\nrevision behaviour:")
    print(f"  sequences with >=1 post-discovery revision: "
          f"{int((df['n_struct_rev'] > 0).sum())}/{len(df)}")
    print(f"  mean structural revisions                 : "
          f"{df['n_struct_rev'].mean():.3f}")

    print("\nmean n_d by class:")
    print(df.groupby("true_class")["n_d"].agg(["count", "mean", "std"]).to_string())

    # correlation of n_d with structure vs growth
    sub = fit.copy()
    c_struct = float(np.corrcoef(sub["L_H"], sub["n_d"])[0, 1])
    c_growth = float(np.corrcoef(sub["growth"], sub["n_d"])[0, 1])
    print(f"\ncorr(n_d, L(H*))  = {c_struct:+.3f}")
    print(f"corr(n_d, growth) = {c_growth:+.3f}")

    class_means = {}
    class_stds = {}
    anova_groups = []
    for cls in ("POLY", "CFIN", "PREC"):
        vals = fit.loc[fit["true_class"] == cls, "n_d"].astype(float)
        class_means[cls] = float(vals.mean())
        class_stds[cls] = float(vals.std(ddof=1))
        anova_groups.append(vals.values)
    anova_F, anova_p = f_oneway(*anova_groups)
    revisers = fit.loc[fit["n_struct_rev"] > 0, ["anum", "name"]]
    print(f"ANOVA F={anova_F:.2f} p={anova_p:.4g}")
    print("revisers:", revisers.to_dict("records"))

    summary = {
        "n_total": len(df), "n_fittable": len(fit),
        "exact": exact, "within1": within1,
        "mae_max": mae, "mae_id": mae_id, "mae_x": mae_x,
        "regime_counts": df["regime"].value_counts().to_dict(),
        "corr_struct": c_struct, "corr_growth": c_growth,
        "struct_rev_total": int(df["n_struct_rev"].sum()),
        "n_with_revision": int((df["n_struct_rev"] > 0).sum()),
        "reviser_anums": revisers["anum"].tolist(),
        "reviser_names": revisers["name"].tolist(),
        "mean_nd_by_class": class_means,
        "std_nd_by_class": class_stds,
        "anova_F": float(anova_F),
        "anova_p": float(anova_p),
    }
    with open(os.path.join(OUT, "analysis.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"\nwrote {OUT}/regimes.csv and analysis.json")


if __name__ == "__main__":
    main()
