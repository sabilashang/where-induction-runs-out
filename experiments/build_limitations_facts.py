"""Build results/limitations_facts.json from measured result artifacts.

Every numeric field cites a source file. Projected hours show arithmetic.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from datetime import datetime

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)


def file_row_count(path: str) -> int:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return max(0, sum(1 for _ in fh) - 1)


def projected_block(rows_done: int, elapsed_s: float, rows_target: int = 20000) -> dict:
    rows_per_hour = rows_done / (elapsed_s / 3600.0) if elapsed_s > 0 else None
    projected_total_hours = (
        rows_target / rows_per_hour if rows_per_hour and rows_per_hour > 0 else None
    )
    return {
        "rows_done": rows_done,
        "elapsed_seconds": elapsed_s,
        "elapsed_hours": elapsed_s / 3600.0,
        "rows_per_hour": rows_per_hour,
        "rows_target": rows_target,
        "projected_total_hours": projected_total_hours,
        "arithmetic": (
            f"rows_per_hour = {rows_done} / ({elapsed_s}/3600) = {rows_per_hour}; "
            f"projected_total_hours = {rows_target} / rows_per_hour = {projected_total_hours}"
        ),
    }


def main():
    t60 = json.load(open("results/oeis_60_timing.json", encoding="utf-8"))
    sp = json.load(open("results/profile_speedup_task2a.json", encoding="utf-8"))
    t2 = json.load(open("results/task2_optimization_report.json", encoding="utf-8"))
    t1887 = json.load(open("results/truncation_1887_summary.json", encoding="utf-8"))
    hol = json.load(open("results/holonomic_denominator_summary.json", encoding="utf-8"))
    length_bins = pd.read_csv("results/oeis_length_bins.csv")
    regimes_pre = pd.read_csv("results/regimes_pre_task2.csv")

    # --- oeis_60_strict (from timing json; CSV retained) ---
    s60 = t60["oeis_60_strict"]
    assert file_row_count("results/oeis_60_strict.csv") == s60["rows_completed"]
    proj60 = projected_block(
        s60["rows_completed"], s60["wall_seconds_observed"], s60["rows_target"]
    )

    # --- oeis_full_strict: measure from partial CSV timestamps ---
    full_path = "results/oeis_full_strict.csv"
    full_rows = file_row_count(full_path)
    st = os.stat(full_path)
    full_elapsed = st.st_mtime - st.st_ctime
    proj_full = projected_block(full_rows, full_elapsed, 20000)

    # RAM
    ram_gb = None
    ram_source = "not measured"
    try:
        import psutil

        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        ram_source = "psutil.virtual_memory().total at build time"
    except Exception:
        pass

    cpu = multiprocessing.cpu_count()

    affected = []
    for name in ("triangular", "oblong"):
        row = regimes_pre.loc[regimes_pre["name"] == name].iloc[0]
        affected.append({
            "name": name,
            "anum": str(row["anum"]),
            "n_struct_rev_baseline": int(row["n_struct_rev"]),
            "n_struct_rev_with_task2b_skip": 0,
            "baseline_source": "results/regimes_pre_task2.csv",
            "change_source": "results/task2_optimization_report.json",
        })

    genuine_dist = t1887["terms_dist_by_class"]["genuine_spurious"]

    out = {
        "title": "Limitations / disclosed future work — measured facts",
        "generated_by": "experiments/build_limitations_facts.py",
        "paper_note": "Do not edit paper/main.tex in this step; material only.",
        "1_configurations_attempted_and_abandoned": {
            "oeis_60_strict": {
                "status": s60["status"],
                "rows_completed": s60["rows_completed"],
                "rows_target": s60["rows_target"],
                "frac": f"{s60['rows_completed']}/{s60['rows_target']}",
                "wall_seconds": s60["wall_seconds_observed"],
                "wall_minutes": s60["wall_minutes_observed"],
                "created": s60["created"],
                "last_write": s60["last_write"],
                "rows_per_hour": proj60["rows_per_hour"],
                "projected_total_hours": proj60["projected_total_hours"],
                "projected_hours_arithmetic": proj60["arithmetic"],
                "reason_stopped": s60["reason"],
                "partial_csv_retained": "results/oeis_60_strict.csv",
                "sources": [
                    "results/oeis_60_timing.json",
                    "results/oeis_60_strict.csv",
                    "results/oeis_60_strict.log",
                ],
            },
            "oeis_60_loose": {
                "status": t60["oeis_60_loose"]["status"],
                "rows_completed": 0,
                "rows_target": 20000,
                "wall_seconds": "not measured",
                "rows_per_hour": "not measured",
                "projected_total_hours": "not measured",
                "reason_stopped": t60["oeis_60_loose"]["reason"],
                "cost_class_justification": (
                    "Same frozen params and 20000-sequence workload as oeis_60_strict; "
                    "strict alone projected ~32 hours, so loose was not started."
                ),
                "sources": ["results/oeis_60_timing.json"],
            },
            "oeis_full_strict": {
                "status": "KILLED_INCOMPLETE",
                "rows_completed": full_rows,
                "rows_target": 20000,
                "frac": f"{full_rows}/20000",
                "wall_seconds": full_elapsed,
                "wall_hours": full_elapsed / 3600.0,
                "timestamp_created": datetime.fromtimestamp(st.st_ctime).isoformat(
                    timespec="seconds"
                ),
                "timestamp_last_write": datetime.fromtimestamp(st.st_mtime).isoformat(
                    timespec="seconds"
                ),
                "rows_per_hour": proj_full["rows_per_hour"],
                "projected_total_hours": proj_full["projected_total_hours"],
                "projected_hours_arithmetic": proj_full["arithmetic"],
                "reason_stopped": (
                    "Abandoned: full-length (--no-truncate) 20000-sequence run incomplete; "
                    "wall time from partial CSV timestamps already projects far beyond "
                    "the 2-hour kill budget used for later scoped runs."
                ),
                "partial_csv_retained": "results/oeis_full_strict.csv",
                "meta_json": "not present",
                "sources": [
                    "results/oeis_full_strict.csv",
                    "file st_ctime/st_mtime of results/oeis_full_strict.csv",
                ],
            },
            "oeis_full_loose": {
                "status": "not started",
                "rows_completed": 0,
                "rows_target": 20000,
                "wall_seconds": "not measured",
                "rows_per_hour": "not measured",
                "projected_total_hours": "not measured",
                "reason_stopped": (
                    "Not started: same cost class as oeis_full_strict (full OEIS term "
                    "lists + revision_spectrum over all prefixes), which was already "
                    "incomplete and projected intractable."
                ),
                "csv_present": False,
                "sources": [
                    "absence of results/oeis_full_loose.csv",
                    "results/oeis_full_strict.csv (sibling incomplete run)",
                ],
            },
        },
        "2_why_intractable": {
            "statement": (
                "guess_prec cost grows with term count and integer magnitude; "
                "revision_spectrum re-solves from scratch at every prefix; "
                "the Task 2(a) speedup (3.06x sum / 2.57x median / 3.58x p90 on the "
                "Task-1 profile set) was insufficient to make 20000-sequence "
                "full-length (or even terms=60) runs tractable within the compute budget."
            ),
            "task2a_speedup": {
                "speedup_sum": sp["speedup_sum"],
                "speedup_median": sp["speedup_median"],
                "speedup_p90": sp["speedup_p90"],
                "baseline_sum_s": sp["baseline_sum_s"],
                "after_sum_s": sp["after_sum_s"],
                "source": "results/profile_speedup_task2a.json",
            },
            "spectrum_behavior_source": "revspec/core.py:revision_spectrum",
            "sources": [
                "results/profile_speedup_task2a.json",
                "results/task2_optimization_report.json",
                "results/oeis_60_timing.json",
                "revspec/core.py",
            ],
        },
        "3_what_we_report_instead": {
            "mixed_length_complete": {
                "path": "results/oeis_results.csv",
                "n_processed": hol["oeis_results"]["n_processed"],
                "n_holonomic_true_full_operator": hol["oeis_results"]["n_holonomic"],
                "pct_revise_true_holonomic": hol["oeis_results"][
                    "pct_revise_among_true_holonomic_str"
                ],
                "conservation_sum": hol["oeis_results"]["conservation_sum"],
                "source": "results/holonomic_denominator_summary.json",
            },
            "fixed_30_complete": {
                "path": "results/oeis_fixed30.csv",
                "n_processed": hol["oeis_fixed30"]["n_processed"],
                "n_holonomic_true_full_operator": hol["oeis_fixed30"]["n_holonomic"],
                "pct_revise_true_holonomic": hol["oeis_fixed30"][
                    "pct_revise_among_true_holonomic_str"
                ],
                "conservation_sum": hol["oeis_fixed30"]["conservation_sum"],
                "source": "results/holonomic_denominator_summary.json",
            },
            "length_dependence_table": {
                "path": "results/oeis_length_bins.csv",
                "note": (
                    "Revision rate rises with n_terms bin; confound disclosed and "
                    "quantified. Rates in this table were computed under the earlier "
                    "n_d-present denominator (see results/oeis_summary.json era); "
                    "true-holonomic recomputation is in "
                    "results/holonomic_denominator_oeis_results_by_nterms.csv."
                ),
                "bins": length_bins.to_dict(orient="records"),
                "sources": [
                    "results/oeis_length_bins.csv",
                    "results/holonomic_denominator_oeis_results_by_nterms.csv",
                ],
            },
        },
        "4_task2b_negative_result": {
            "status": t2["task2b_spectrum_skip_when_standing_annihilates"]["status"],
            "finding": (
                "Skipping the full re-solve when the standing hypothesis still "
                "annihilates the new term CHANGES which hypothesis is selected. "
                "This is a real finding about MDL selection under growing prefixes "
                "(a cheaper newly eligible (r,d) can appear when neqs crosses "
                "ncols+slack), not an implementation bug."
            ),
            "affected_sequences": affected,
            "observation_quoted_from_report": t2[
                "task2b_spectrum_skip_when_standing_annihilates"
            ]["reason"],
            "action_taken": t2["task2b_spectrum_skip_when_standing_annihilates"][
                "action"
            ],
            "sources": [
                "results/task2_optimization_report.json",
                "results/regimes_pre_task2.csv",
            ],
        },
        "5_the_1887_split": {
            "n": t1887["n"],
            "i_truncation_artifact": {
                "count": t1887["truncation_artifact"],
                "frac": f"{t1887['truncation_artifact']}/1887",
                "pct": t1887["pct_truncation_artifact"],
                "pct_rounded_display": "1.54%",
            },
            "ii_genuine_ge40": {
                "count": t1887["genuine_spurious"],
                "frac": f"{t1887['genuine_spurious']}/1887",
                "pct": t1887["pct_genuine_spurious"],
                "pct_rounded_display": "89.98%",
            },
            "iii_undetermined_lt40": {
                "count": t1887["undetermined"],
                "frac": f"{t1887['undetermined']}/1887",
                "pct": t1887["pct_undetermined"],
                "pct_rounded_display": "8.48%",
            },
            "conservation": (
                t1887["truncation_artifact"]
                + t1887["genuine_spurious"]
                + t1887["undetermined"]
                + t1887["error"]
            ),
            "terms_distribution_for_1698_genuine": {
                "n": genuine_dist["n"],
                "min": genuine_dist["min"],
                "median": genuine_dist["median"],
                "mean": genuine_dist["mean"],
                "max": genuine_dist["max"],
            },
            "sources": [
                "results/truncation_1887_summary.json",
                "results/truncation_1887.csv",
                "experiments/run_truncation_1887.py",
            ],
        },
        "6_compute_environment": {
            "cpu_count": cpu,
            "cpu_count_source": "multiprocessing.cpu_count() at build time",
            "ram_gb": ram_gb,
            "ram_source": ram_source,
            "parallel": True,
            "parallel_mechanism": "concurrent.futures.ProcessPoolExecutor",
            "parallel_source": "experiments/run_oeis.py",
            "oeis_60_strict_jobs_flag": (
                "not recorded in results/oeis_60_strict.log; "
                "experiments/run_oeis.py defaults --jobs to os.cpu_count()"
            ),
            "oeis_runner_default_jobs": "os.cpu_count() or 1",
            "oeis_runner_default_jobs_source": "experiments/run_oeis.py",
        },
    }

    # sanity on 1887 conservation
    assert out["5_the_1887_split"]["conservation"] == 1887
    assert out["5_the_1887_split"]["terms_distribution_for_1698_genuine"]["n"] == 1698

    path = "results/limitations_facts.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {path}")
    print(
        "oeis_60_strict:",
        out["1_configurations_attempted_and_abandoned"]["oeis_60_strict"]["frac"],
        "projected_h=",
        out["1_configurations_attempted_and_abandoned"]["oeis_60_strict"][
            "projected_total_hours"
        ],
    )
    print(
        "oeis_full_strict:",
        out["1_configurations_attempted_and_abandoned"]["oeis_full_strict"]["frac"],
        "projected_h=",
        out["1_configurations_attempted_and_abandoned"]["oeis_full_strict"][
            "projected_total_hours"
        ],
    )


if __name__ == "__main__":
    main()
