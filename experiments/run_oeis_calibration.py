"""Clean throughput calibration for oeis_60_strict (500-sequence slice).

Same frozen params / sample / settings as the abandoned 20k run, but limit=500.
Records wall time and per-worker CPU time so machine sleep cannot inflate the
compute figure.

Writes:
  results/oeis_60_calibration.json
  results/oeis_60_calibration_per_seq.csv
and updates results/limitations_facts.json to supersede the unreliable timing.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experiments.run_oeis import (  # noqa: E402
    MAX_DEGREE,
    MAX_ORDER,
    N_MIN,
    SLACK,
    _init_worker,
    parse_stripped,
    process,
)

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

# Keep Windows from sleeping during the timed window.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _prevent_sleep():
    if sys.platform != "win32":
        return None
    import ctypes

    ctypes.windll.kernel32.SetThreadExecutionState(
        _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
    )
    return True


def _allow_sleep():
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


def max_digit_len(seq):
    if not seq:
        return 0
    return max(len(str(abs(int(x)))) for x in seq)


def process_timed(job):
    """Worker wrapper: wall + CPU for one sequence."""
    t_wall0 = time.perf_counter()
    t_cpu0 = time.process_time()
    row = process(job)
    wall_s = time.perf_counter() - t_wall0
    cpu_s = time.process_time() - t_cpu0
    anum, seq = job
    row["wall_s"] = wall_s
    row["cpu_s"] = cpu_s
    row["max_digit_len"] = max_digit_len(seq)
    return row


def pctile(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def update_limitations(cal: dict):
    path = "results/limitations_facts.json"
    if not os.path.exists(path):
        print(f"WARN: {path} missing; skip update")
        return
    lim = json.load(open(path, encoding="utf-8"))
    old = lim["1_configurations_attempted_and_abandoned"]["oeis_60_strict"]
    lim["1_configurations_attempted_and_abandoned"]["oeis_60_strict_UNRELIABLE_DISCARDED"] = {
        **old,
        "discarded": True,
        "discard_reason": (
            "Machine sleep during the timed window inflated wall elapsed; "
            "superseded by results/oeis_60_calibration.json"
        ),
        "superseded_by": "results/oeis_60_calibration.json",
    }
    lim["1_configurations_attempted_and_abandoned"]["oeis_60_strict"] = {
        "status": "CALIBRATED_500",
        "calibration": True,
        "rows_completed_calibration": cal["n_sequences"],
        "rows_target_full": 20000,
        "wall_seconds": cal["wall_seconds"],
        "cpu_seconds_sum_workers": cal["cpu_seconds_sum_workers"],
        "rows_per_hour_wall": cal["rows_per_hour_wall"],
        "rows_per_hour_cpu": cal["rows_per_hour_cpu"],
        "projected_total_hours_wall_20000": cal["projected_hours_wall_20000"],
        "projected_total_hours_cpu_20000": cal["projected_hours_cpu_20000"],
        "projected_hours_arithmetic_wall": cal["projected_hours_arithmetic_wall"],
        "projected_hours_arithmetic_cpu": cal["projected_hours_arithmetic_cpu"],
        "n_jobs": cal["n_jobs"],
        "cpu_count": cal["cpu_count"],
        "reason_note": (
            "Throughput from awake 500-seq calibration; earlier 550/53min figure discarded."
        ),
        "sources": [
            "results/oeis_60_calibration.json",
            "experiments/run_oeis_calibration.py",
        ],
    }
    lim["timing_note"] = {
        "text": (
            "The earlier oeis_60_strict timing (550 rows / ~53 min wall) is discarded "
            "as unreliable due to machine sleep. Use oeis_60_calibration.json."
        ),
        "source": "results/oeis_60_calibration.json",
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(lim, fh, indent=2)
    print(f"updated {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stripped", default="stripped.gz")
    ap.add_argument("--anums-file", default="results/sample_anums_seed0.txt")
    ap.add_argument("--terms", type=int, default=60)
    ap.add_argument("--min-terms", type=int, default=30)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--shuffle", type=int, default=0)
    ap.add_argument("--strict-leading", type=int, choices=[0, 1], default=1)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    assert MAX_ORDER == 6 and MAX_DEGREE == 4 and SLACK == 2 and N_MIN == 6
    cpu_count = multiprocessing.cpu_count()
    print(
        f"CALIBRATION oeis_60_strict limit={args.limit} terms={args.terms} "
        f"strict_leading={args.strict_leading} shuffle={args.shuffle} "
        f"jobs={args.jobs} cpu_count={cpu_count}"
    )

    with open(args.anums_file, encoding="utf-8") as fh:
        anums = [ln.strip() for ln in fh if ln.strip().startswith("A")]
    anums = anums[: args.limit]
    assert len(anums) == args.limit, (len(anums), args.limit)

    jobs = parse_stripped(
        args.stripped,
        args.min_terms,
        args.terms,
        args.limit,
        shuffle_seed=args.shuffle,
        anums=anums,
        no_truncate=False,
    )
    assert len(jobs) == args.limit, len(jobs)
    print(f"loaded {len(jobs)} sequences")

    _prevent_sleep()
    rows = []
    wall0 = time.perf_counter()
    # Parent process_time is not used for aggregate CPU (workers are separate).
    try:
        _init_worker(bool(args.strict_leading))
        with ProcessPoolExecutor(
            max_workers=args.jobs,
            initializer=_init_worker,
            initargs=(bool(args.strict_leading),),
        ) as ex:
            futs = {ex.submit(process_timed, job): job[0] for job in jobs}
            done = 0
            for fut in as_completed(futs):
                rows.append(fut.result())
                done += 1
                if done % 50 == 0:
                    print(f"  {done}/{len(jobs)}")
                    sys.stdout.flush()
    finally:
        _allow_sleep()

    wall_s = time.perf_counter() - wall0
    cpu_sum = sum(float(r["cpu_s"]) for r in rows)
    n = len(rows)
    assert n == args.limit

    walls = sorted(float(r["wall_s"]) for r in rows)
    cpus = sorted(float(r["cpu_s"]) for r in rows)

    rows_per_hour_wall = n / (wall_s / 3600.0)
    rows_per_hour_cpu = n / (cpu_sum / 3600.0)
    proj_wall = 20000 / rows_per_hour_wall
    proj_cpu = 20000 / rows_per_hour_cpu

    slowest = sorted(rows, key=lambda r: -float(r["wall_s"]))[:10]
    slowest_out = [
        {
            "anum": r["anum"],
            "n_terms": int(r["n_terms"]),
            "max_digit_len": int(r["max_digit_len"]),
            "wall_s": float(r["wall_s"]),
            "cpu_s": float(r["cpu_s"]),
        }
        for r in slowest
    ]

    cal = {
        "config": {
            "label": "oeis_60_strict_calibration",
            "terms": args.terms,
            "min_terms": args.min_terms,
            "strict_leading": args.strict_leading,
            "shuffle": args.shuffle,
            "limit": args.limit,
            "anums_file": args.anums_file,
            "anums_slice": f"first {args.limit} of sample_anums_seed0.txt",
            "MAX_ORDER": MAX_ORDER,
            "MAX_DEGREE": MAX_DEGREE,
            "SLACK": SLACK,
            "N_MIN": N_MIN,
            "prevent_sleep": sys.platform == "win32",
        },
        "n_sequences": n,
        "n_jobs": args.jobs,
        "cpu_count": cpu_count,
        "wall_seconds": wall_s,
        "cpu_seconds_sum_workers": cpu_sum,
        "per_sequence_wall_s": {
            "median": pctile(walls, 50),
            "p90": pctile(walls, 90),
            "max": walls[-1],
            "min": walls[0],
            "sum": sum(walls),
        },
        "per_sequence_cpu_s": {
            "median": pctile(cpus, 50),
            "p90": pctile(cpus, 90),
            "max": cpus[-1],
            "min": cpus[0],
            "sum": cpu_sum,
        },
        "rows_per_hour_wall": rows_per_hour_wall,
        "rows_per_hour_cpu": rows_per_hour_cpu,
        "projected_hours_wall_20000": proj_wall,
        "projected_hours_cpu_20000": proj_cpu,
        "projected_hours_arithmetic_wall": (
            f"rows_per_hour_wall = {n} / ({wall_s}/3600) = {rows_per_hour_wall}; "
            f"projected_hours_wall_20000 = 20000 / rows_per_hour_wall = {proj_wall}"
        ),
        "projected_hours_arithmetic_cpu": (
            f"rows_per_hour_cpu = {n} / ({cpu_sum}/3600) = {rows_per_hour_cpu}; "
            f"projected_hours_cpu_20000 = 20000 / rows_per_hour_cpu = {proj_cpu}"
        ),
        "interpretation": {
            "wall_projection": (
                "Expected wall-clock hours for a full 20000-seq run at this "
                f"parallelism (n_jobs={args.jobs})."
            ),
            "cpu_projection": (
                "Aggregate worker CPU-hours for 20000 sequences "
                "(single-core-equivalent compute), independent of sleep/throttling "
                "on the parent wall clock."
            ),
            "under_4h_wall": bool(proj_wall < 4.0),
            "still_20h_plus_wall": bool(proj_wall >= 20.0),
        },
        "slowest10": slowest_out,
        "earlier_timing_discarded": {
            "source": "results/oeis_60_timing.json",
            "reason": "Machine sleep inflated wall elapsed; unreliable.",
            "old_rows_completed": 550,
            "old_wall_minutes": 52.762408316666665,
            "old_projected_hours": 31.97721716161616,
        },
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs("results", exist_ok=True)
    with open("results/oeis_60_calibration.json", "w", encoding="utf-8") as fh:
        json.dump(cal, fh, indent=2)

    per_path = "results/oeis_60_calibration_per_seq.csv"
    fields = [
        "anum", "n_terms", "max_digit_len", "wall_s", "cpu_s",
        "full_fit", "prefix_only", "n_struct_rev", "error",
    ]
    with open(per_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["anum"]):
            w.writerow(r)

    update_limitations(cal)

    print("=== CALIBRATION SUMMARY ===")
    print(json.dumps({
        "n": n,
        "n_jobs": args.jobs,
        "cpu_count": cpu_count,
        "wall_seconds": wall_s,
        "cpu_seconds_sum_workers": cpu_sum,
        "per_seq_wall_median_p90_max": [
            cal["per_sequence_wall_s"]["median"],
            cal["per_sequence_wall_s"]["p90"],
            cal["per_sequence_wall_s"]["max"],
        ],
        "rows_per_hour_wall": rows_per_hour_wall,
        "rows_per_hour_cpu": rows_per_hour_cpu,
        "projected_hours_wall_20000": proj_wall,
        "projected_hours_cpu_20000": proj_cpu,
        "under_4h_wall": cal["interpretation"]["under_4h_wall"],
        "still_20h_plus_wall": cal["interpretation"]["still_20h_plus_wall"],
        "slowest10": slowest_out,
    }, indent=2))
    print("wrote results/oeis_60_calibration.json")
    print(f"wrote {per_path}")
    if proj_wall < 4.0:
        print("PROJECTION: under ~4 hours wall for 20000 — full run may be viable.")
    elif proj_wall >= 20.0:
        print("PROJECTION: still 20h+ wall — keep disclosed-future-work plan.")
    else:
        print(f"PROJECTION: {proj_wall:.2f} wall hours for 20000 — between 4h and 20h.")


if __name__ == "__main__":
    main()
