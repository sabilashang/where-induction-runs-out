"""True-holonomic revision rate by n_terms bin on mixed-length oeis_results.csv.

Writes:
  results/oeis_length_bins_holonomic.csv
  results/oeis_length_bins_holonomic_summary.json

Denominator: order/degree/n_id all non-null (full-sequence operator present).
This is a different population from the fixed-30 headline in oeis_fixed30.csv.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
BINS = [(20, 22), (23, 25), (26, 28), (29, 31), (32, 34)]


def main() -> None:
    df = pd.read_csv(RES / "oeis_results.csv")
    h = df[df.order.notna() & df.degree.notna() & df.n_id.notna()].copy()
    h["rev"] = h.n_struct_rev.astype(float) > 0
    rows = []
    for lo, hi in BINS:
        sub = h[(h.n_terms >= lo) & (h.n_terms <= hi)]
        n_h, n_r = len(sub), int(sub.rev.sum())
        rate = (n_r / n_h) if n_h else None
        rows.append(
            {
                "bin_lo": lo,
                "bin_hi": hi,
                "n_revise": n_r,
                "n_holonomic": n_h,
                "rev_rate": rate,
                "pct_str": f"{n_r}/{n_h} ({100 * n_r / n_h:.4f}%)" if n_h else "",
                "pct_1dp": round(100 * n_r / n_h, 1) if n_h else None,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(RES / "oeis_length_bins_holonomic.csv", index=False)
    tot_r, tot_h = int(out.n_revise.sum()), int(out.n_holonomic.sum())
    summary = {
        "source": "results/oeis_results.csv",
        "denominator": "true_holonomic (order/degree/n_id non-null)",
        "n_holonomic_total": tot_h,
        "n_revise_total": tot_r,
        "weighted_mean_pct": round(100 * tot_r / tot_h, 4) if tot_h else None,
        "fixed30_headline_pct": 11.3309,
        "consistent_with_fixed30_11_3": abs(100 * tot_r / tot_h - 11.3309) < 0.5
        if tot_h
        else False,
        "note": (
            "Bins from mixed-length oeis_results.csv (a different population from "
            "the fixed 30-term headline 315/2780 in oeis_fixed30.csv / "
            "holonomic_denominator_oeis_fixed30.json)."
        ),
        "bins": rows,
        "script": "experiments/make_oeis_length_bins_holonomic.py",
    }
    (RES / "oeis_length_bins_holonomic_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(out.to_string(index=False))
    print(
        "weighted",
        summary["weighted_mean_pct"],
        "vs fixed30 11.3 → consistent?",
        summary["consistent_with_fixed30_11_3"],
    )


if __name__ == "__main__":
    main()
