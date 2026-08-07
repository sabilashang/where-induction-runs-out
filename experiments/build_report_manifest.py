"""Build results/manifest.json and print the full Task 0-4 report.

Every figure is read from a committed results file produced by a script.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

MANIFEST = {}


def add(key, value, source_csv, row_filter, script, line_number):
    MANIFEST[key] = {
        "value": value,
        "source_csv": source_csv,
        "row_filter": row_filter,
        "script": script,
        "line_number": line_number,
    }


def load_meta(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cfg_report(name, csv_path, meta_path):
    meta = load_meta(meta_path)
    df = pd.read_csv(csv_path)
    n = len(df)
    err = df["error"].notna() & (df["error"].astype(str) != "") & (df["error"].astype(str) != "None")
    hol = (~err) & (df["full_fit"] == True)  # noqa: E712
    pref = (~err) & (df["prefix_only"] == True)  # noqa: E712
    none = (~err) & (~hol) & (~pref)
    n_hol, n_pref, n_none, n_err = int(hol.sum()), int(pref.sum()), int(none.sum()), int(err.sum())
    assert n_hol + n_pref + n_none + n_err == n == 20000

    ok = df.loc[hol]
    revises = ok["n_struct_rev"] > 0
    exact = ok["n_d"] == ok["n_id"]
    w1 = (ok["n_d"] - ok["n_id"]).abs() <= 1
    mae = float((ok["n_d"] - ok["n_id"]).abs().mean()) if n_hol else None
    n_rev = int(revises.sum()) if n_hol else 0
    n_ex = int(exact.sum()) if n_hol else 0
    n_w1 = int(w1.sum()) if n_hol else 0
    n_sing = int((ok["n_singular"].fillna(0) > 0).sum()) if n_hol else 0
    mean_sing = float(ok["n_singular"].fillna(0).mean()) if n_hol else None

    prefix = f"task3.{name}"
    add(f"{prefix}.n_holonomic", n_hol, csv_path, "full_fit==True", "experiments/run_oeis.py", 0)
    add(f"{prefix}.pct_holonomic", f"{n_hol}/20000 ({100*n_hol/20000:.4f}%)", csv_path, "full_fit==True", "experiments/run_oeis.py", 0)
    add(f"{prefix}.n_revise", n_rev, csv_path, "full_fit & n_struct_rev>0", "experiments/run_oeis.py", 0)
    add(f"{prefix}.pct_revise", f"{n_rev}/{n_hol} ({100*n_rev/n_hol:.4f}%)" if n_hol else "n/a", csv_path, "holonomic", "experiments/run_oeis.py", 0)
    add(f"{prefix}.exact", f"{n_ex}/{n_hol}", csv_path, "holonomic & n_d==n_id", "experiments/run_oeis.py", 0)
    add(f"{prefix}.within1", f"{n_w1}/{n_hol}", csv_path, "holonomic & |n_d-n_id|<=1", "experiments/run_oeis.py", 0)
    add(f"{prefix}.mae", mae, csv_path, "holonomic", "experiments/run_oeis.py", 0)
    add(f"{prefix}.n_singular", n_sing, csv_path, "holonomic & n_singular>0", "experiments/run_oeis.py", 0)
    add(f"{prefix}.mean_singular", mean_sing, csv_path, "holonomic", "experiments/run_oeis.py", 0)
    add(f"{prefix}.prefix_only", n_pref, csv_path, "prefix_only==True", "experiments/run_oeis.py", 0)
    add(f"{prefix}.no_fit", n_none, csv_path, "no fit", "experiments/run_oeis.py", 0)
    add(f"{prefix}.errored", n_err, csv_path, "error notna", "experiments/run_oeis.py", 0)
    add(f"{prefix}.conservation", n_hol + n_pref + n_none + n_err, csv_path, "sum", "experiments/run_oeis.py", 0)

    print(f"\n=== {name} ===")
    print(f"holonomic: {n_hol}/20000 ({100*n_hol/20000:.4f}%)")
    print(f"revise: {n_rev}/{n_hol} ({100*n_rev/max(n_hol,1):.4f}%)")
    print(f"exact: {n_ex}/{n_hol} ({100*n_ex/max(n_hol,1):.4f}%)")
    print(f"within1: {n_w1}/{n_hol} ({100*n_w1/max(n_hol,1):.4f}%)")
    print(f"MAE: {mae}")
    print(f"singular>0: {n_sing}/{n_hol} mean={mean_sing}")
    print(f"prefix_only: {n_pref}  no_fit: {n_none}  errored: {n_err}")
    print(f"conservation: {n_hol}+{n_pref}+{n_none}+{n_err}={n_hol+n_pref+n_none+n_err}")
    return {
        "name": name,
        "meta": meta,
        "n_hol": n_hol, "n_rev": n_rev, "n_ex": n_ex, "n_w1": n_w1,
        "mae": mae, "n_sing": n_sing, "mean_sing": mean_sing,
        "n_pref": n_pref, "n_none": n_none, "n_err": n_err,
    }


def dichotomy(csv_path):
    df = pd.read_csv(csv_path)
    err = df["error"].notna() & (df["error"].astype(str) != "") & (df["error"].astype(str) != "None")
    ok = df.loc[(~err) & (df["full_fit"] == True)].copy()  # noqa: E712
    ok["revises"] = ok["n_struct_rev"] > 0
    ok["exact"] = ok["n_d"] == ok["n_id"]
    ok["within1"] = (ok["n_d"] - ok["n_id"]).abs() <= 1
    ct = pd.crosstab(ok["revises"], ok["exact"], normalize="index")
    print("\n=== TASK4 dichotomy (full_loose, full-fit only) ===")
    print(ct.round(4).to_string())
    rows = []
    for rev, g in ok.groupby("revises"):
        row = {
            "revises": bool(rev),
            "n": int(len(g)),
            "exact_n": int(g["exact"].sum()),
            "exact_rate": float(g["exact"].mean()),
            "within1_n": int(g["within1"].sum()),
            "within1_rate": float(g["within1"].mean()),
            "MAE": float((g["n_d"] - g["n_id"]).abs().mean()),
        }
        rows.append(row)
        print(row)
        tag = "revisers" if rev else "non_revisers"
        add(f"task4.{tag}.n", row["n"], csv_path, f"full_fit & revises={rev}", "experiments/build_report_manifest.py", 0)
        add(f"task4.{tag}.exact", f"{row['exact_n']}/{row['n']} ({100*row['exact_rate']:.4f}%)", csv_path, f"revises={rev}", "experiments/build_report_manifest.py", 0)
        add(f"task4.{tag}.within1", f"{row['within1_n']}/{row['n']} ({100*row['within1_rate']:.4f}%)", csv_path, f"revises={rev}", "experiments/build_report_manifest.py", 0)
        add(f"task4.{tag}.MAE", row["MAE"], csv_path, f"revises={rev}", "experiments/build_report_manifest.py", 0)
    out = {"crosstab": ct.to_dict(), "by_revises": rows}
    with open("results/dichotomy_full_loose.json", "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def main():
    # Task 0
    prov = load_meta("results/provenance.json")
    add("task0.stripped_sha256", prov["stripped_sha256"], "results/provenance.json", "all", "experiments/verify_oeis_data.py", 0)
    add("task0.spot_all_pass", prov["spot_all_pass"], "results/provenance.json", "spot_checks", "experiments/verify_oeis_data.py", 0)
    add("task0.distinct", prov["distinct"], "results/provenance.json", "all", "experiments/verify_oeis_data.py", 0)

    # Task 1
    t1 = load_meta("results/truncation_1887_summary.json")
    add("task1.truncation_artifact", f"{t1['truncation_artifact']}/1887 ({t1['pct_truncation_artifact']:.4f}%)", "results/truncation_1887.csv", "class==truncation_artifact", "experiments/run_truncation_1887.py", 0)
    add("task1.genuine_spurious", f"{t1['genuine_spurious']}/1887 ({t1['pct_genuine_spurious']:.4f}%)", "results/truncation_1887.csv", "class==genuine_spurious", "experiments/run_truncation_1887.py", 0)
    add("task1.undetermined", f"{t1['undetermined']}/1887 ({t1['pct_undetermined']:.4f}%)", "results/truncation_1887.csv", "class==undetermined", "experiments/run_truncation_1887.py", 0)

    # Task 2
    ab = load_meta("results/ablation_encoding_summary.json")
    add("task2.strict.exact", ab["strict"]["exact_frac"], "results/ablation_encoding.csv", "strict_leading==1 & full_fit", "experiments/run_ablation_encoding.py", 0)
    add("task2.loose.exact", ab["loose"]["exact_frac"], "results/ablation_encoding.csv", "strict_leading==0 & full_fit", "experiments/run_ablation_encoding.py", 0)
    add("task2.strict.revisers", ab["strict"]["reviser_anums"], "results/ablation_encoding.csv", "strict & n_struct_rev>0", "experiments/run_ablation_encoding.py", 0)
    add("task2.loose.revisers", ab["loose"]["reviser_anums"], "results/ablation_encoding.csv", "loose & n_struct_rev>0", "experiments/run_ablation_encoding.py", 0)
    add("task2.fibonacci_loose", {"n_d": ab["loose"]["fibonacci_n_d"], "L_H": ab["loose"]["fibonacci_L_H"]}, "results/ablation_encoding.csv", "A000045 & strict=0", "experiments/run_ablation_encoding.py", 0)

    configs = [
        ("fixed30_strict", "results/oeis_fixed30_strict.csv", "results/oeis_fixed30_strict.csv.meta.json"),
        ("fixed30_loose", "results/oeis_fixed30_loose.csv", "results/oeis_fixed30_loose.csv.meta.json"),
        ("full_strict", "results/oeis_full_strict.csv", "results/oeis_full_strict.csv.meta.json"),
        ("full_loose", "results/oeis_full_loose.csv", "results/oeis_full_loose.csv.meta.json"),
    ]
    for name, csv_p, meta_p in configs:
        if not os.path.exists(csv_p):
            print(f"MISSING {csv_p}")
            continue
        cfg_report(name, csv_p, meta_p)

    if os.path.exists("results/oeis_full_loose.csv"):
        dichotomy("results/oeis_full_loose.csv")

    # determinism if both runs present
    if os.path.exists("results/oeis_full_loose_run1.csv.meta.json") and os.path.exists("results/oeis_full_loose_run2.csv.meta.json"):
        m1 = load_meta("results/oeis_full_loose_run1.csv.meta.json")
        m2 = load_meta("results/oeis_full_loose_run2.csv.meta.json")
        keys = ["n_holonomic", "n_revise", "exact", "within1", "mae", "n_prefix_only", "n_errored"]
        same = all(m1.get(k) == m2.get(k) for k in keys)
        add("task3.determinism_identical", same, "results/oeis_full_loose_run{1,2}.csv.meta.json", "summary keys", "experiments/run_oeis.py", 0)
        print(f"determinism identical={same}")
        print("run1", {k: m1.get(k) for k in keys})
        print("run2", {k: m2.get(k) for k in keys})

    with open("results/manifest.json", "w") as fh:
        json.dump(MANIFEST, fh, indent=2)
    print("wrote results/manifest.json")


if __name__ == "__main__":
    main()
