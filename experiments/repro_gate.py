"""Reproducibility gate: paper numbers vs freshly generated classical results.

Exit 0 iff every checked figure matches. Does not touch OEIS/LLM artefacts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import f_oneway

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TEX = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")


def fail(msg: str) -> None:
    print("FAIL:", msg)
    sys.exit(1)


def main() -> None:
    a = json.loads((RES / "analysis.json").read_text(encoding="utf-8"))
    regimes = pd.read_csv(RES / "regimes.csv")
    fit = regimes.dropna(subset=["n_d"])
    deco_r = pd.read_csv(RES / "deception_random.csv")
    deco = pd.read_csv(RES / "deception.csv")
    table1 = (ROOT / "paper" / "tables" / "table1_corpus.tex").read_text(
        encoding="utf-8"
    )
    ab = json.loads((RES / "ablation_encoding_summary.json").read_text(encoding="utf-8"))

    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond, detail))
        print(("OK  " if cond else "BAD "), name, detail)

    check("exact 41/46", a["exact"] == 41 and a["n_fittable"] == 46)
    check("within1 46/46", a["within1"] == 46)
    check("mae_id ~0.11", abs(a["mae_id"] - 0.10869565217391304) < 1e-9)
    check("mae_x ~3.20", abs(a["mae_x"] - 3.1956521739130435) < 1e-9)
    check("corr_struct", abs(a["corr_struct"] - 0.8546821770230112) < 1e-9)
    check("corr_growth", abs(a["corr_growth"] + 0.007034755775103548) < 1e-9)
    check("n_revisers", a["n_with_revision"] == 2)
    check(
        "reviser anums",
        set(a.get("reviser_anums", [])) == {"A000578", "A000330"},
        str(a.get("reviser_anums")),
    )

    for cls, mean, sd in (
        ("CFIN", 7.1875, 0.9810708435174292),
        ("PREC", 8.733333333333333, 1.8695555876298773),
        ("POLY", 8.533333333333333, 1.6417180315870612),
    ):
        check(
            f"mean_nd {cls}",
            abs(a["mean_nd_by_class"][cls] - mean) < 1e-9,
        )
        check(
            f"std_nd {cls}",
            abs(a["std_nd_by_class"][cls] - sd) < 1e-9,
        )

    groups = [fit.loc[fit.true_class == c, "n_d"].values for c in ("POLY", "CFIN", "PREC")]
    F, p = f_oneway(*groups)
    check("anova_F", abs(F - a["anova_F"]) < 1e-9 and abs(F - 4.699) < 0.01, f"F={F}")
    check("anova_p", abs(p - a["anova_p"]) < 1e-9, f"p={p}")

    rate = float((deco_r.struct_rev > 0).mean())
    n_pos = int((deco_r.struct_rev > 0).sum())
    check("deception rate 96/440", n_pos == 96 and len(deco_r) == 440 and abs(rate - 0.21818) < 1e-3)

    sub = deco[deco.period.isin([7, 9, 11, 13, 15])]
    check("settle == 2p+3", bool((sub.settle == 2 * sub.period + 3).all()))
    peaks = {int(r.period): float(r.peak_abs_rho) for r in deco.itertuples()}
    check("peak p=7/9/11", peaks[7] == 4.5 and peaks[9] == 7.5 and peaks[11] == 10.5)
    check("peak plateau p>=13", peaks[13] == 11.0 and peaks[15] == 11.0)

    phase = pd.read_csv(RES / "control_phase.csv")
    check(
        "control B true-period law",
        bool((phase["n_d"] == phase["n_id"]).all()
             and (phase["n_id"] == 2 * phase["order"] + 3).all()),
    )
    bins = pd.read_csv(RES / "oeis_length_bins_holonomic.csv")
    check("holonomic bins", bins["pct_1dp"].tolist() == [4.2, 6.1, 9.3, 5.7, 12.0])
    strict = pd.read_csv(RES / "deception_random_strict.csv")
    check(
        "strict deception 63/440",
        int((strict.struct_rev > 0).sum()) == 63 and len(strict) == 440,
    )

    # paper text
    check("tex cubes/square pyramidal", "A000578" in TEX and "A000330" in TEX)
    check("tex not old revisers as current", "A000217 and the oblong" not in TEX)
    check("tex corr +0.85", r"+0.85" in TEX)
    check("tex corr -0.007", r"-0.007" in TEX)
    check("tex POLY 8.53", r"8.53" in TEX)
    check("tex ANOVA 4.70", r"4.70" in TEX and r"0.014" in TEX)
    check("tex deception 21.8%", r"21.8\%" in TEX)
    check("tex 14.3% cites strict file", "deception\\_random\\_strict.csv" in TEX)
    check("tex naturals 315", r"naturals" in TEX and r"315" in TEX)
    check("tex no old 545 naturals", "costs $545$" not in TEX)
    check("tex holonomic bins 4.2/12.0", r"4.2\%" in TEX and r"12.0\%" in TEX)
    check("tex no old 55.9 bin", r"55.9\%" not in TEX)
    check(
        "tex fixed-30 provenance",
        "fixed $30$-term budget" in TEX or r"fixed $30$-term" in TEX,
    )
    check(
        "tex mixed-length different population",
        "different population" in TEX and "mixed-length" in TEX,
    )
    check("tex cites oeis_fixed30", "oeis\\_fixed30.csv" in TEX)
    check("tex cites oeis_results", "oeis\\_results.csv" in TEX)
    check("tex default encoding named", "strict\\_leading=False" in TEX)
    check("tex true period p^*", r"p^{*}" in TEX or "p^*" in TEX)
    check("table1 POLY 8.5", "POLY & 15 & 15 & 8.5" in table1)
    check("table1 POLY revisions 2", bool(re.search(r"POLY & 15 & 15 & 8\.5 & 7--13 & 33 & 0\.059 & 2", table1)))

    # ablation consistency
    check("ablation has both encodings", ab["strict"]["n_fitted"] == 46 and ab["loose"]["n_fitted"] == 46)
    check(
        "ablation loose revisers",
        set(ab["loose"]["reviser_anums"]) == {"A000578", "A000330"},
    )
    check(
        "ablation strict revisers",
        set(ab["strict"]["reviser_anums"]) == {"A000217", "A002378"},
    )
    check("main matches loose corr_struct", abs(a["corr_struct"] - ab["loose"]["corr_struct"]) < 1e-9)

    bad = [n for n, ok, _ in checks if not ok]
    if bad:
        fail(f"{len(bad)} mismatches: {bad}")
    print(f"\nGATE PASSED ({len(checks)} checks)")


if __name__ == "__main__":
    main()
