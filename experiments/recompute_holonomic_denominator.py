"""Task A: recompute OEIS headlines with the TRUE holonomic denominator.

A sequence is holonomic ONLY if a full-sequence operator is present
(order, degree, and n_id all non-null). Prefix-only fits (n_d present but
operator null) are a separate category and never enter the holonomic
denominator.

Reads:
  results/oeis_results.csv
  results/oeis_fixed30.csv
  results/oeis_random30.csv

Writes:
  results/holonomic_denominator_{name}.json
  results/holonomic_denominator_{name}_crosstab.csv
  results/holonomic_denominator_{name}_by_nterms.csv
  results/holonomic_denominator_{name}_by_params.csv
  results/holonomic_denominator_{name}_struct_rev_dist.csv
  results/holonomic_denominator_summary.json
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

RUNS = [
    ("oeis_results", "results/oeis_results.csv"),
    ("oeis_fixed30", "results/oeis_fixed30.csv"),
    ("oeis_random30", "results/oeis_random30.csv"),
]


def pct(num: int, den: int) -> str:
    if den == 0:
        return f"{num}/{den} (n/a)"
    return f"{num}/{den} ({100.0 * num / den:.4f}%)"


def classify(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "error" in out.columns:
        err = out["error"].notna() & (out["error"].astype(str) != "") & (
            out["error"].astype(str) != "None"
        )
    else:
        err = pd.Series(False, index=out.index)
    has_op = out["order"].notna() & out["degree"].notna() & out["n_id"].notna()
    has_nd = out["n_d"].notna()
    # true holonomic = full-sequence operator
    cat = pd.Series("no_fit", index=out.index)
    cat.loc[err] = "errored"
    cat.loc[~err & has_op] = "holonomic"
    cat.loc[~err & ~has_op & has_nd] = "prefix_only"
    # remainder stays no_fit
    out["_cat"] = cat
    out["_err"] = err
    out["_hol"] = (~err) & has_op
    return out


def analyze(name: str, path: str) -> dict:
    df = pd.read_csv(path)
    df = classify(df)
    n = len(df)
    n_hol = int((df["_cat"] == "holonomic").sum())
    n_pref = int((df["_cat"] == "prefix_only").sum())
    n_none = int((df["_cat"] == "no_fit").sum())
    n_err = int((df["_cat"] == "errored").sum())
    cons = n_hol + n_pref + n_none + n_err
    print(f"\n{'=' * 64}")
    print(f"RUN: {name}  ({path})")
    print(f"{'=' * 64}")
    print(f"n processed              : {n}")
    print(f"n holonomic (full op)    : {n_hol}  {pct(n_hol, n)}")
    print(f"n prefix-only-fit        : {n_pref}  {pct(n_pref, n)}")
    print(f"n no-fit                 : {n_none}  {pct(n_none, n)}")
    print(f"n errored                : {n_err}  {pct(n_err, n)}")
    print(f"CONSERVATION sum         : {cons}  (must equal {n})")
    if cons != n:
        print("STOP: conservation failed")
        sys.exit(3)

    hol = df.loc[df["_hol"]].copy()
    revises = hol["n_struct_rev"] > 0
    n_rev = int(revises.sum())
    exact = hol["n_d"] == hol["n_id"]
    w1 = (hol["n_d"] - hol["n_id"]).abs() <= 1
    mae = float((hol["n_d"] - hol["n_id"]).abs().mean()) if n_hol else None
    n_ex = int(exact.sum()) if n_hol else 0
    n_w1 = int(w1.sum()) if n_hol else 0

    print(f"% TRUE holonomic that revise (Result 1): {pct(n_rev, n_hol)}")
    print(f"n_d==n_id exact          : {pct(n_ex, n_hol)}")
    print(f"n_d==n_id within-1       : {pct(n_w1, n_hol)}")
    print(f"MAE (TRUE holonomic)     : {mae}")

    # crosstab revises x exact, row-normalized + raw counts
    hol = hol.assign(
        revises=revises.map({True: "yes", False: "no"}),
        exact_match=exact.map({True: "yes", False: "no"}),
    )
    ct = pd.crosstab(hol["revises"], hol["exact_match"], margins=False)
    ct = ct.reindex(index=["no", "yes"], columns=["no", "yes"], fill_value=0)
    ct_norm = ct.div(ct.sum(axis=1).replace(0, pd.NA), axis=0)
    ct_path = f"results/holonomic_denominator_{name}_crosstab.csv"
    rows_ct = []
    print("crosstab(revises, exact) raw / row-normalized:")
    for rev in ["no", "yes"]:
        for ex in ["no", "yes"]:
            raw = int(ct.loc[rev, ex])
            row_sum = int(ct.loc[rev].sum())
            rn = float(ct_norm.loc[rev, ex]) if row_sum else None
            if rn is not None:
                print(f"  revises={rev} exact={ex}: {raw}/{row_sum} ({100 * rn:.4f}%)")
            else:
                print(f"  revises={rev} exact={ex}: {raw}/{row_sum} (n/a)")
            rows_ct.append({
                "revises": rev, "exact": ex, "count": raw,
                "row_total": row_sum,
                "row_frac": rn,
                "row_pct_str": pct(raw, row_sum),
            })
    pd.DataFrame(rows_ct).to_csv(ct_path, index=False)

    mae_rev = float(
        (hol.loc[revises, "n_d"] - hol.loc[revises, "n_id"]).abs().mean()
    ) if n_rev else None
    mae_nrev = float(
        (hol.loc[~revises, "n_d"] - hol.loc[~revises, "n_id"]).abs().mean()
    ) if (n_hol - n_rev) else None
    print(f"MAE among revisers       : {mae_rev}  (n={n_rev})")
    print(f"MAE among non-revisers   : {mae_nrev}  (n={n_hol - n_rev})")

    # revision rate by n_terms bin
    hol = hol.copy()
    hol["n_terms"] = hol["n_terms"].astype(int)
    bins = sorted(hol["n_terms"].unique())
    by_n = []
    print("revision rate by n_terms:")
    for nt in bins:
        sub = hol.loc[hol["n_terms"] == nt]
        nr = int((sub["n_struct_rev"] > 0).sum())
        den = len(sub)
        print(f"  n_terms={nt}: {pct(nr, den)}")
        by_n.append({"n_terms": int(nt), "n_hol": den, "n_revise": nr, "pct_str": pct(nr, den)})
    by_n_path = f"results/holonomic_denominator_{name}_by_nterms.csv"
    pd.DataFrame(by_n).to_csv(by_n_path, index=False)

    # revision rate by params=(r+1)(d+1)
    hol["n_params"] = (hol["order"].astype(int) + 1) * (hol["degree"].astype(int) + 1)
    by_p = []
    print("revision rate by params=(r+1)(d+1):")
    for p in sorted(hol["n_params"].unique()):
        sub = hol.loc[hol["n_params"] == p]
        nr = int((sub["n_struct_rev"] > 0).sum())
        den = len(sub)
        print(f"  params={p}: {pct(nr, den)}")
        by_p.append({"n_params": int(p), "n_hol": den, "n_revise": nr, "pct_str": pct(nr, den)})
    by_p_path = f"results/holonomic_denominator_{name}_by_params.csv"
    pd.DataFrame(by_p).to_csv(by_p_path, index=False)

    # distribution of n_struct_rev
    vc = hol["n_struct_rev"].astype(int).value_counts().sort_index()
    dist_rows = []
    print("distribution of n_struct_rev (TRUE holonomic):")
    for k, c in vc.items():
        print(f"  n_struct_rev={k}: {pct(int(c), n_hol)}")
        dist_rows.append({
            "n_struct_rev": int(k), "count": int(c),
            "pct_str": pct(int(c), n_hol),
        })
    dist_path = f"results/holonomic_denominator_{name}_struct_rev_dist.csv"
    pd.DataFrame(dist_rows).to_csv(dist_path, index=False)

    summary = {
        "name": name,
        "path": path,
        "n_processed": n,
        "n_holonomic": n_hol,
        "n_prefix_only": n_pref,
        "n_no_fit": n_none,
        "n_errored": n_err,
        "conservation_sum": cons,
        "conservation_ok": cons == n,
        "pct_holonomic_str": pct(n_hol, n),
        "pct_prefix_only_str": pct(n_pref, n),
        "pct_no_fit_str": pct(n_none, n),
        "pct_errored_str": pct(n_err, n),
        "n_revise": n_rev,
        "pct_revise_among_true_holonomic_str": pct(n_rev, n_hol),
        "exact": n_ex,
        "within1": n_w1,
        "exact_str": pct(n_ex, n_hol),
        "within1_str": pct(n_w1, n_hol),
        "mae": mae,
        "mae_revisers": mae_rev,
        "mae_non_revisers": mae_nrev,
        "n_revisers_for_mae": n_rev,
        "n_non_revisers_for_mae": n_hol - n_rev,
        "artifacts": {
            "crosstab": ct_path,
            "by_nterms": by_n_path,
            "by_params": by_p_path,
            "struct_rev_dist": dist_path,
        },
    }
    out_json = f"results/holonomic_denominator_{name}.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"wrote {out_json}")
    return summary


def main():
    all_summ = {}
    for name, path in RUNS:
        if not os.path.exists(path):
            print(f"MISSING {path}")
            sys.exit(2)
        all_summ[name] = analyze(name, path)
    with open("results/holonomic_denominator_summary.json", "w", encoding="utf-8") as fh:
        json.dump(all_summ, fh, indent=2)
    print("\nwrote results/holonomic_denominator_summary.json")
    # highlight fixed30 vs expected ~2780 / ~315 / ~11.3%
    f = all_summ["oeis_fixed30"]
    print("\nFIXED30 CHECK (expected ~2780 holonomic, ~315 revisers, ~11.3%):")
    print(f"  actual holonomic={f['n_holonomic']} revisers={f['n_revise']} "
          f"rate={f['pct_revise_among_true_holonomic_str']}")


if __name__ == "__main__":
    main()
