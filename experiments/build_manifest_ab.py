"""Append Task A/B figures into results/manifest.json."""
from __future__ import annotations

import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)


def add(m, key, value, source, script):
    m[key] = {"value": value, "source": source, "script": script}


def main():
    path = "results/manifest.json"
    m = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

    summ = json.load(open("results/holonomic_denominator_summary.json", encoding="utf-8"))
    for name, s in summ.items():
        p = f"taskA.{name}"
        add(m, f"{p}.n_processed", s["n_processed"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.n_holonomic", s["n_holonomic"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.n_prefix_only", s["n_prefix_only"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.n_no_fit", s["n_no_fit"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.n_errored", s["n_errored"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.conservation_sum", s["conservation_sum"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.pct_revise_true_holonomic", s["pct_revise_among_true_holonomic_str"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.exact", s["exact_str"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.within1", s["within1_str"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.mae", s["mae"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.mae_revisers", s["mae_revisers"], s["path"], "experiments/recompute_holonomic_denominator.py")
        add(m, f"{p}.mae_non_revisers", s["mae_non_revisers"], s["path"], "experiments/recompute_holonomic_denominator.py")

    sample = json.load(open("results/llm_sample.json", encoding="utf-8"))
    add(m, "taskB.sample_n", sample["n_total"], "results/llm_sample.json", "experiments/build_llm_sample.py")
    add(m, "taskB.sample_n_per_stratum", sample["n_per_stratum"], "results/llm_sample.json", "experiments/build_llm_sample.py")
    add(m, "taskB.sample_seed", sample["seed"], "results/llm_sample.json", "experiments/build_llm_sample.py")
    add(m, "taskB.pool_clean", sample["pool_sizes"]["clean"], "results/llm_sample.json", "experiments/build_llm_sample.py")
    add(m, "taskB.pool_revising", sample["pool_sizes"]["revising"], "results/llm_sample.json", "experiments/build_llm_sample.py")
    add(m, "taskB.pool_wilderness", sample["pool_sizes"]["wilderness"], "results/llm_sample.json", "experiments/build_llm_sample.py")

    llm = json.load(open("results/llm_summary.json", encoding="utf-8"))
    add(m, "taskB.llm_status", llm["status"], "results/llm_summary.json", "experiments/run_llm_eval.py")
    add(m, "taskB.llm_reason", llm.get("reason"), "results/llm_summary.json", "experiments/run_llm_eval.py")

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2)
    print(f"wrote {path} ({len(m)} keys)")
    print("Task A fixed30 Result 1:", summ["oeis_fixed30"]["pct_revise_among_true_holonomic_str"])
    print("Task B status:", llm["status"])


if __name__ == "__main__":
    main()
