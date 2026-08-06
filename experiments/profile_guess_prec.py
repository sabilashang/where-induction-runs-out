"""Task 1: profile guess_prec on the 200 heaviest sequences from the shuffled sample.

Selection: from results/sample_anums_seed0.txt, load FULL OEIS terms, score each by
(n_terms * max_digit_length), take the top 200. Time guess_prec once per sequence
at full length. Print median / p90 / max and the 10 worst offenders.

No optimisation — diagnosis only.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from revspec.core import guess_prec, literal_cost

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.chdir(ROOT)

MAX_ORDER, MAX_DEGREE, SLACK = 6, 4, 2


def load_full(path, anums):
    want = set(anums)
    out = {}
    with gzip.open(path, "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            anum = parts[0].strip()
            if anum not in want:
                continue
            vals = []
            for tok in parts[1:]:
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    vals.append(int(tok))
                except ValueError:
                    break
            out[anum] = vals
            if len(out) == len(want):
                break
    return out


def max_digit_len(seq):
    if not seq:
        return 0
    return max(len(str(abs(int(x)))) for x in seq)


def main():
    anums = [ln.strip() for ln in open("results/sample_anums_seed0.txt") if ln.strip()]
    print(f"sample size: {len(anums)}")
    assert len(anums) == 20000, len(anums)
    seqs = load_full("stripped.gz", anums)
    print(f"loaded: {len(seqs)}")
    scored = []
    for a in anums:
        if a not in seqs:
            continue
        s = seqs[a]
        mdl = max_digit_len(s)
        scored.append((len(s) * mdl, len(s), mdl, a, s))
    scored.sort(key=lambda t: (-t[0], -t[1], -t[2], t[3]))
    top = scored[:200]
    print(f"profiling top {len(top)} by (n_terms * max_digit_len)")

    rows = []
    for i, (score, n, mdl, anum, seq) in enumerate(top, 1):
        lit = literal_cost(seq)
        t0 = time.perf_counter()
        hyp = guess_prec(
            seq, max_order=MAX_ORDER, max_degree=MAX_DEGREE,
            slack=SLACK, best_bits=lit, strict_leading=False,
        )
        dt = time.perf_counter() - t0
        max_mag = max(abs(int(x)) for x in seq) if seq else 0
        rows.append({
            "anum": anum,
            "n_terms": n,
            "max_digit_len": mdl,
            "score": score,
            "max_abs": max_mag,
            "max_abs_bits": max_mag.bit_length(),
            "seconds": dt,
            "found": hyp is not None and hyp.description_length() < lit,
        })
        if i % 10 == 0 or dt > 5.0:
            print(f"  {i}/{len(top)} {anum} n={n} digits={mdl} t={dt:.3f}s")

    times = sorted(r["seconds"] for r in rows)
    n = len(times)

    def pct(p):
        if n == 0:
            return None
        idx = min(n - 1, max(0, int(round(p / 100.0 * (n - 1)))))
        return times[idx]

    median = pct(50)
    p90 = pct(90)
    mx = times[-1] if times else None
    worst = sorted(rows, key=lambda r: -r["seconds"])[:10]

    summary = {
        "n_profiled": n,
        "median_s": median,
        "p90_s": p90,
        "max_s": mx,
        "sum_s": sum(times),
        "worst10": [
            {
                "anum": w["anum"],
                "n_terms": w["n_terms"],
                "max_digit_len": w["max_digit_len"],
                "max_abs": str(w["max_abs"]),
                "max_abs_bits": w["max_abs_bits"],
                "seconds": w["seconds"],
                "found": w["found"],
            }
            for w in worst
        ],
    }
    os.makedirs("results", exist_ok=True)
    with open("results/profile_guess_prec_200.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print("--- PROFILE SUMMARY ---")
    print(f"n={n}")
    print(f"median_s={median}")
    print(f"p90_s={p90}")
    print(f"max_s={mx}")
    print(f"sum_s={sum(times)}")
    print("worst10:")
    for w in worst:
        print(
            f"  {w['anum']} n_terms={w['n_terms']} max_digit_len={w['max_digit_len']} "
            f"max_abs_bits={w['max_abs_bits']} seconds={w['seconds']:.4f} found={w['found']}"
        )
    print("wrote results/profile_guess_prec_200.json")


if __name__ == "__main__":
    main()
