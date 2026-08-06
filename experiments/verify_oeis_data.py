"""Prove that stripped.gz / names.gz are authentic OEIS dumps.

Writes results/provenance.json and prints a human-readable report.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import statistics
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

GROUND_TRUTH = {
    "A000045": [0, 1, 1, 2, 3, 5, 8, 13, 21, 34],
    "A000108": [1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862],
    "A000040": [2, 3, 5, 7, 11, 13, 17, 19, 23, 29],
    "A000142": [1, 1, 2, 6, 24, 120, 720, 5040],
    "A000203": [1, 3, 4, 7, 6, 12, 8, 15, 13, 18],
}


def sha256_file(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def parse_line(line: str):
    parts = line.split(",")
    anum = parts[0].strip()
    if not anum.startswith("A"):
        return None, []
    vals = []
    for tok in parts[1:]:
        tok = tok.strip()
        if not tok:
            continue
        try:
            vals.append(int(tok))
        except ValueError:
            break
    return anum, vals


def main() -> int:
    stripped = "stripped.gz"
    names = "names.gz"
    if not os.path.exists(stripped) or not os.path.exists(names):
        print("FAIL: stripped.gz or names.gz missing")
        return 1

    strip_sha, strip_bytes = sha256_file(stripped)
    names_sha, names_bytes = sha256_file(names)
    print(f"stripped.gz sha256={strip_sha} bytes={strip_bytes}")
    print(f"names.gz    sha256={names_sha} bytes={names_bytes}")

    total_lines = 0
    comment_lines = 0
    parseable = 0
    anums = []
    term_counts = []
    spot = {a: None for a in GROUND_TRUTH}

    with gzip.open(stripped, "rt", errors="replace") as fh:
        for line in fh:
            total_lines += 1
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                comment_lines += 1
                continue
            anum, vals = parse_line(s)
            if anum is None:
                continue
            parseable += 1
            anums.append(anum)
            term_counts.append(len(vals))
            if anum in spot and spot[anum] is None:
                need = len(GROUND_TRUTH[anum])
                spot[anum] = vals[:need]

    distinct = sorted(set(anums))
    print(f"total_lines={total_lines} comment_lines={comment_lines} "
          f"parseable_A={parseable}")
    print(f"lowest={distinct[0]} highest={distinct[-1]} "
          f"distinct={len(distinct)}")

    spot_results = {}
    any_fail = False
    for anum, expect in GROUND_TRUTH.items():
        got = spot.get(anum)
        ok = got == expect
        status = "PASS" if ok else "FAIL"
        print(f"SPOT {anum}: {status} got={got}")
        spot_results[anum] = {"expected": expect, "got": got, "status": status}
        if not ok:
            any_fail = True

    if any_fail:
        print("STOP: ground-truth spot check failed")
        out = {
            "stripped_sha256": strip_sha,
            "stripped_bytes": strip_bytes,
            "names_sha256": names_sha,
            "names_bytes": names_bytes,
            "total_lines": total_lines,
            "comment_lines": comment_lines,
            "parseable_A": parseable,
            "lowest": distinct[0] if distinct else None,
            "highest": distinct[-1] if distinct else None,
            "distinct": len(distinct),
            "spot_checks": spot_results,
            "spot_all_pass": False,
        }
        os.makedirs("results", exist_ok=True)
        with open("results/provenance.json", "w") as fh:
            json.dump(out, fh, indent=2)
        return 2

    term_counts_sorted = sorted(term_counts)
    mid = len(term_counts_sorted) // 2
    if len(term_counts_sorted) % 2:
        median = term_counts_sorted[mid]
    else:
        median = (term_counts_sorted[mid - 1] + term_counts_sorted[mid]) / 2
    dist = {
        "min": min(term_counts),
        "median": median,
        "mean": statistics.mean(term_counts),
        "max": max(term_counts),
        "n_ge_20": sum(1 for t in term_counts if t >= 20),
        "n_ge_30": sum(1 for t in term_counts if t >= 30),
        "n_ge_40": sum(1 for t in term_counts if t >= 40),
        "n_sequences": len(term_counts),
    }
    print("terms_per_sequence:", json.dumps(dist, indent=2))

    out = {
        "stripped_sha256": strip_sha,
        "stripped_bytes": strip_bytes,
        "names_sha256": names_sha,
        "names_bytes": names_bytes,
        "total_lines": total_lines,
        "comment_lines": comment_lines,
        "parseable_A": parseable,
        "lowest": distinct[0],
        "highest": distinct[-1],
        "distinct": len(distinct),
        "spot_checks": spot_results,
        "spot_all_pass": True,
        "terms_per_sequence": dist,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/provenance.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote results/provenance.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
