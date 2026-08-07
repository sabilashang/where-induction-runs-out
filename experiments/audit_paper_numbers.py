"""Audit: every numeric claim in paper/main.tex must trace to results/.

For each claim prints: number | sentence | source::field | PASS/FAIL/UNTRACEABLE
Exit 1 if any FAIL or UNTRACEABLE.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import f_oneway, linregress

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TEX = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
TAB1 = (ROOT / "paper" / "tables" / "table1_corpus.tex").read_text(encoding="utf-8")
TAB2 = (ROOT / "paper" / "tables" / "table2_prediction.tex").read_text(encoding="utf-8")

# Figure scripts are audited too: a number typed into a plot title or label is
# as much of a claim as one typed into main.tex, and fails the same way when
# the results move.  fig2 panel (b) shipped "r=-0.09" against a true
# corr_growth of -0.007 for exactly this reason.
FIGSRC = {
    "fig:figures": (ROOT / "experiments" / "make_figures.py").read_text(encoding="utf-8"),
    "fig:llm": (ROOT / "experiments" / "make_llm_figure.py").read_text(encoding="utf-8"),
}


def J(name: str) -> dict:
    return json.loads((RES / name).read_text(encoding="utf-8"))


def snip(needle: str, src: str = TEX, pad: int = 100) -> str:
    i = src.find(needle)
    if i < 0:
        return f"(needle missing: {needle!r})"
    s = src[max(0, i - pad) : i + len(needle) + pad].replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def frac_str(s: str) -> str:
    return s.split()[0]


rows: list[tuple] = []


def add(number, where, needle, source, field, expected, actual, *, tol=None, note=""):
    if actual is None:
        status = "UNTRACEABLE"
    elif tol is not None:
        try:
            status = "PASS" if abs(float(actual) - float(expected)) <= tol else "FAIL"
        except (TypeError, ValueError):
            status = "FAIL"
    elif isinstance(expected, (set, list, tuple)):
        status = "PASS" if set(actual) == set(expected) else "FAIL"
    else:
        status = "PASS" if actual == expected else "FAIL"
    src_text = (
        TAB1 if where == "table1"
        else TAB2 if where == "table2"
        else FIGSRC.get(where, TEX)
    )
    rows.append(
        (
            status,
            str(number),
            where,
            snip(needle, src_text),
            f"{source}::{field}",
            expected,
            actual,
            note,
        )
    )


# --------------------------------------------------------------------------- #
# Figure-script scan
#
# Rule: any string literal in a figure script that carries a digit must either
# be built at run time (f-string / .format, i.e. derived from results/) or be
# listed in FIG_ALLOW with its provenance.  Structural strings -- colours,
# filenames, regex sources, matplotlib format specs, OEIS A-numbers, model ids
# -- are excluded first.  Constants inside an f-string are skipped because the
# surrounding string is derived.
#
# This deliberately over-approximates "printed on the figure": a stale number
# in a non-displayed literal is worth flagging too, and under-approximating
# would miss strings that reach a label through a variable (as fig0's stratum
# conditions do).
# --------------------------------------------------------------------------- #

_FIG_SKIP = (
    re.compile(r"^#[0-9a-fA-F]{3,8}$"),                 # colour
    re.compile(r"\.(pdf|png|csv|json|tex|txt|log)$"),   # filename
    re.compile(r"\\[dswbAZ]|\(\?|\[\^"),                # regex source
    re.compile(r"^C\d[a-z\-.:^]*$"),                    # matplotlib fmt spec
    re.compile(r"^A\d{6}$"),                            # OEIS A-number
    re.compile(r"^[a-z0-9.\-]+/[a-z0-9.\-]+$"),         # model id
)

# displayed literal -> (provenance, optional (json file, field, value) recheck)
FIG_ALLOW = {
    "GPT-4o": ("model display name; results/llm_summary.json models_used", None),
    "stable: $\\rho=0$": ("rho=0 exactly, by the Exactness observation", None),
    "$100\\times\\lambda$": ("100 = percent scale applied to lambda in code", None),
    "initial condition $a(1)$": ("a(1) is a sequence index, not a measurement", None),
    "prefix fit only: no operator at full\nlength, at least 40 terms available": (
        "wilderness stratum criterion",
        ("llm_sample.json", "sources.wilderness", "n_terms>=40"),
    ),
    "predictor & exact & within $\\pm1$ & MAE \\\\": (
        "table 2 column header; +-1 is the stated tolerance, not a measurement",
        None,
    ),
}


def _fig_literals(src: str):
    """(lineno, value) for each str constant, minus docstrings and f-string parts."""
    tree = ast.parse(src)
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                skip.add(id(b[0].value))
        if isinstance(node, ast.JoinedStr):
            for part in ast.walk(node):
                if isinstance(part, ast.Constant):
                    skip.add(id(part))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _fig_derived_sites(src: str) -> int:
    """Count display calls whose text is built at run time from results/."""
    display = {"set_title", "set_xlabel", "set_ylabel", "suptitle", "annotate",
               "text", "set_xticklabels"}
    n = 0
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
        args = list(node.args) + [k.value for k in node.keywords if k.arg == "label"]
        if name not in display and not any(k.arg == "label" for k in node.keywords):
            continue
        for arg in args:
            if isinstance(arg, ast.JoinedStr):
                n += 1
            elif (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
                  and arg.func.attr == "format"):
                n += 1
    return n


def audit_figure_scripts() -> None:
    for where, fname in (("fig:figures", "make_figures.py"),
                         ("fig:llm", "make_llm_figure.py")):
        src = FIGSRC[where]
        for lineno, val in _fig_literals(src):
            if not re.search(r"\d", val) or any(p.search(val) for p in _FIG_SKIP):
                continue
            needle = val.split("\n")[0][:28]
            entry = FIG_ALLOW.get(val)
            if entry is None:
                add(f"L{lineno} literal", where, needle, fname,
                    "unsourced numeric literal", "derived or allowlisted", None,
                    note="number typed into a figure string; read it from results/")
                continue
            prov, recheck = entry
            if recheck is None:
                add(f"L{lineno} structural", where, needle, fname, prov, True, True,
                    note="structural constant, not a measurement")
            else:
                jf, field, token = recheck
                add(f"L{lineno} const", where, needle, jf, field, True,
                    token in json.dumps(J(jf)), note=prov)

        add(f"{fname} derived sites", where, "set_title", fname,
            "display strings built from results at run time", True,
            _fig_derived_sites(src) > 0,
            note=f"{_fig_derived_sites(src)} derived display call(s)")

    # explicit regression guards for the two defects this check exists to catch
    ff, fl = FIGSRC["fig:figures"], FIGSRC["fig:llm"]
    add("fig2 corr_growth derived", "fig:figures", "corr_growth", "make_figures.py",
        "title reads analysis.json::corr_growth", True, 'an["corr_growth"]' in ff)
    add("fig2 exact% derived", "fig:figures", "exact_pct", "make_figures.py",
        "title reads analysis.json::exact / n_fittable", True, 'an["exact"]' in ff)
    add("fig2 stale -0.09 gone", "fig:figures", "growth is irrelevant",
        "analysis.json", "hardcoded corr_growth absent", True, "-0.09" not in ff)
    add("fig2 stale 89% gone", "fig:figures", "exact", "analysis.json",
        "hardcoded exact-rate absent", True, "89% exact" not in ff)
    add("fig1 landmarks derived", "fig:figures", "i_spur", "make_figures.py",
        "D_3 landmarks derived from the spectrum", True,
        "struct.index(True)" in ff)
    add("fig5 series derived", "fig:llm", "_series(", "make_llm_figure.py",
        "all six series read from llm_summary.json", True,
        "_series(" in fl and "3 / 17" not in fl)
    ylim = re.search(r"set_ylim\(0,\s*(\d+)\)", fl)
    add("fig5 ylim not clipped", "fig:llm", "set_ylim", "make_llm_figure.py",
        "percent axes explicitly bounded at >= 100", True,
        bool(ylim) and int(ylim.group(1)) >= 100,
        note=f"top={ylim.group(1) if ylim else 'unset'}")


def main() -> int:
    a = J("analysis.json")
    hol = J("holonomic_denominator_oeis_fixed30.json")
    trunc = J("truncation_1887_summary.json")
    cal = J("oeis_60_calibration.json")
    llm = J("llm_summary.json")
    ab = J("ablation_encoding_summary.json")
    deco = pd.read_csv(RES / "deception.csv")
    deco_r = pd.read_csv(RES / "deception_random.csv")
    growth = pd.read_csv(RES / "control_growth.csv")
    phase = pd.read_csv(RES / "control_phase.csv")
    bins = pd.read_csv(RES / "oeis_length_bins_holonomic.csv")
    deco_strict = pd.read_csv(RES / "deception_random_strict.csv")
    feat = pd.read_csv(RES / "features.csv")
    regimes = pd.read_csv(RES / "regimes.csv")
    spectra = J("spectra.json")
    lcp = J("lcp.json")

    by = llm["aggregates"]["by_model"]
    M = {
        "claude": "anthropic/claude-sonnet-4.5",
        "gpt": "openai/gpt-4o",
        "llama": "meta-llama/llama-3.3-70b-instruct",
    }

    def L(model, stratum, key):
        return by[M[model]]["by_stratum"][stratum][key]

    # ----- abstract -----
    add("41/46", "abstract", "41/46", "analysis.json", "exact/n_fittable",
        "41/46", f"{a['exact']}/{a['n_fittable']}")
    add("MAE 0.11", "abstract", "MAE $0.11$", "analysis.json", "mae_id",
        0.11, round(a["mae_id"], 2))
    add("MAE 3.20", "abstract", "MAE $3.20$", "analysis.json", "mae_x",
        3.20, round(a["mae_x"], 2))
    add("n_d=7", "abstract", "nd = 7", "control_growth.csv", "unique n_d",
        {7}, set(int(x) for x in growth["n_d"].unique()))
    add("20000 OEIS", "abstract", "20{,}000", "oeis_fixed30.csv", "nrows",
        20000, len(pd.read_csv(RES / "oeis_fixed30.csv", usecols=["anum"])))
    add("1698/1887", "abstract", "1698/1887", "truncation_1887_summary.json",
        "genuine_spurious", 1698, trunc["genuine_spurious"])
    add("89.98%", "abstract", "89.98\\%", "truncation_1887_summary.json",
        "pct_genuine_spurious", 89.98, round(trunc["pct_genuine_spurious"], 2))
    add("29/1887", "abstract", "29/1887", "truncation_1887_summary.json",
        "truncation_artifact", 29, trunc["truncation_artifact"])
    add("1.54%", "abstract", "1.54\\%", "truncation_1887_summary.json",
        "pct_truncation_artifact", 1.54, round(trunc["pct_truncation_artifact"], 2))
    add("315/2780", "abstract", "oeisRev", "holonomic_denominator_oeis_fixed30.json",
        "n_revise/n_holonomic", f"{hol['n_revise']}/{hol['n_holonomic']}",
        f"{hol['n_revise']}/{hol['n_holonomic']}")
    add("11.3%", "abstract", "11.3\\%", "holonomic_denominator_oeis_fixed30.json",
        "315/2780", 11.3, round(100 * hol["n_revise"] / hol["n_holonomic"], 1))
    add("fixed-30 provenance abs", "abstract", "fixed $30$-term budget",
        "oeis_fixed30.csv", "provenance clause", True,
        "fixed $30$-term budget" in TEX)
    add("mixed-length provenance abs", "abstract", "different population",
        "oeis_results.csv / oeis_length_bins_holonomic.csv",
        "provenance clause", True,
        "different population" in TEX and "mixed-length" in TEX)
    claimed_bins = [4.2, 6.1, 9.3, 5.7, 12.0]
    actual_bins = [float(x) for x in bins["pct_1dp"].tolist()]
    add("length bins", "abstract", "4.2\\%", "oeis_length_bins_holonomic.csv",
        "pct_1dp", claimed_bins, actual_bins)
    add("91.9% nonrev exact", "abstract", "91.9\\%", "holonomic_denominator_oeis_fixed30.json",
        "nonreviser exact", 91.9, _exact_pct(revisers=False))
    add("0% reviser exact", "abstract", "0\\% exact", "holonomic_denominator_oeis_fixed30.json",
        "reviser exact", 0.0, _exact_pct(revisers=True))
    add("180 calls", "abstract", "180$ calls", "llm_summary.json", "n_rows",
        180, llm["n_rows"])
    add("temp 0", "abstract", "temperature $0$", "llm_summary.json", "temperature",
        0, llm["temperature"])
    add("64.7% abstain", "abstract", "64.7", "llm_summary.json", "claude wild abstain",
        64.7, round(100 * int(frac_str(L("claude", "wilderness", "abstention_rate")).split("/")[0])
                    / int(frac_str(L("claude", "wilderness", "abstention_rate")).split("/")[1]), 1))
    add("95.0% abstain", "abstract", "95.0", "llm_summary.json", "gpt wild abstain",
        95.0, round(100 * int(frac_str(L("gpt", "wilderness", "abstention_rate")).split("/")[0])
                    / int(frac_str(L("gpt", "wilderness", "abstention_rate")).split("/")[1]), 1))
    add("65% llama confab clean", "abstract", "65\\% for Llama", "llm_summary.json",
        "llama confab clean", 65.0,
        round(100 * int(frac_str(L("llama", "clean", "confabulation_rate")).split("/")[0])
              / int(frac_str(L("llama", "clean", "confabulation_rate")).split("/")[1]), 1))
    add("45% gpt confab clean", "abstract", "45\\% for GPT", "llm_summary.json",
        "gpt confab clean", 45.0,
        round(100 * int(frac_str(L("gpt", "clean", "confabulation_rate")).split("/")[0])
              / int(frac_str(L("gpt", "clean", "confabulation_rate")).split("/")[1]), 1))
    add("21.1% llama confab wild", "abstract", "21.1\\%", "llm_summary.json",
        "llama confab wild", 21.1,
        round(100 * int(frac_str(L("llama", "wilderness", "confabulation_rate")).split("/")[0])
              / int(frac_str(L("llama", "wilderness", "confabulation_rate")).split("/")[1]), 1))
    add("5% gpt confab wild", "abstract", "$5\\%", "llm_summary.json",
        "gpt confab wild", 5.0,
        round(100 * int(frac_str(L("gpt", "wilderness", "confabulation_rate")).split("/")[0])
              / int(frac_str(L("gpt", "wilderness", "confabulation_rate")).split("/")[1]), 1))
    add("5/6", "abstract", "5/6", "llm_summary.json", "llama recog",
        "5/6", frac_str(L("llama", "clean", "exact_accuracy_recognized")))
    add("0/14", "abstract", "0/14", "llm_summary.json", "llama not recog",
        "0/14", frac_str(L("llama", "clean", "exact_accuracy_not_recognized")))

    # ----- §4 -----
    add("2 of 61", "§4", "2$ of $61", "analysis.json", "n_with_revision",
        2, a["n_with_revision"])
    add("A000578", "§4", "A000578", "analysis.json", "reviser_anums",
        True, "A000578" in a["reviser_anums"])
    add("A000330", "§4", "A000330", "analysis.json", "reviser_anums",
        True, "A000330" in a["reviser_anums"])
    add("0.033", "§4", "0.033", "analysis.json", "mean struct rev",
        0.033, round(a["struct_rev_total"] / a["n_total"], 3))
    add("3.3% classical", "§4", "3.3\\%", "analysis.json", "revise pct",
        3.3, round(100 * a["n_with_revision"] / a["n_total"], 1))
    add("2780 hol", "§4", "oeisHol", "holonomic_denominator_oeis_fixed30.json",
        "n_holonomic", 2780, hol["n_holonomic"])
    add("315 rev", "§4", "oeisRev", "holonomic_denominator_oeis_fixed30.json",
        "n_revise", 315, hol["n_revise"])
    add("§4 cites oeis_fixed30", "§4", "oeis\\_fixed30.csv",
        "oeis_fixed30.csv", "inline cite", True, "oeis\\_fixed30.csv" in TEX)
    add("§4 cites oeis_results", "§4", "oeis\\_results.csv",
        "oeis_results.csv", "inline cite", True, "oeis\\_results.csv" in TEX)
    add("§4 different population", "§4", "different population",
        "oeis_length_bins_holonomic.csv", "provenance", True,
        "different population" in TEX)
    for i, (lo, hi, pct) in enumerate(
        [(20, 22, 4.2), (23, 25, 6.1), (26, 28, 9.3), (29, 31, 5.7), (32, 34, 12.0)]
    ):
        add(f"{pct}% bin", "§4", f"{pct}\\%", "oeis_length_bins_holonomic.csv",
            f"row{i} pct_1dp", pct, float(bins.iloc[i]["pct_1dp"]))

    # ----- §5 -----
    add("41/46 body", "§5", "exact for $41/46$", "analysis.json", "exact",
        41, a["exact"])
    add("46/46 body", "§5", "46/46", "analysis.json", "within1", 46, a["within1"])
    add("+0.85", "§5", "+0.85", "analysis.json", "corr_struct",
        0.85, round(a["corr_struct"], 2))
    add("-0.007", "§5", "-0.007", "analysis.json", "corr_growth",
        -0.007, round(a["corr_growth"], 3))
    add("7.19±0.98", "§5", "7.19", "analysis.json", "CFIN",
        (7.19, 0.98),
        (round(a["mean_nd_by_class"]["CFIN"], 2), round(a["std_nd_by_class"]["CFIN"], 2)))
    add("8.73±1.87", "§5", "8.73", "analysis.json", "PREC",
        (8.73, 1.87),
        (round(a["mean_nd_by_class"]["PREC"], 2), round(a["std_nd_by_class"]["PREC"], 2)))
    add("8.53±1.64", "§5", "8.53", "analysis.json", "POLY",
        (8.53, 1.64),
        (round(a["mean_nd_by_class"]["POLY"], 2), round(a["std_nd_by_class"]["POLY"], 2)))
    add("F=4.70", "§5", "4.70", "analysis.json", "anova_F", 4.70, round(a["anova_F"], 2))
    add("p=0.014", "§5", "0.014", "analysis.json", "anova_p", 0.014, round(a["anova_p"], 3))
    add("2465", "§5", "2465", "holonomic_denominator_oeis_fixed30.json",
        "n_non_revisers_for_mae", 2465, hol["n_non_revisers_for_mae"])
    add("315 dichotomy", "§5", "revises       & $315$", "holonomic_denominator_oeis_fixed30.json",
        "n_revisers_for_mae", 315, hol["n_revisers_for_mae"])
    add("91.9% table", "§5", "91.9\\%", "oeis_fixed30.csv", "nonrev exact",
        91.9, _exact_pct(False))
    add("99.0%", "§5", "99.0\\%", "oeis_fixed30.csv", "nonrev w1", 99.0, _w1_pct(False))
    add("0.11 MAE nonrev", "§5", "0.11$ \\\\", "holonomic_denominator_oeis_fixed30.json",
        "mae_non_revisers", 0.11, round(hol["mae_non_revisers"], 2))
    add("0.0% rev exact", "§5", "0.0\\%", "oeis_fixed30.csv", "rev exact",
        0.0, _exact_pct(True))
    add("48.6%", "§5", "48.6\\%", "oeis_fixed30.csv", "rev w1", 48.6, _w1_pct(True))
    add("4.37", "§5", "4.37", "holonomic_denominator_oeis_fixed30.json",
        "mae_revisers", 4.37, round(hol["mae_revisers"], 2))

    # ----- §6 growth -----
    add("3519 factorials", "§6", "3519", "spectra.json", "factorial L_lit[-1]",
        3519, _spec_llit(spectra, "factorial"))
    add("315 naturals", "§6", "315", "spectra.json", "naturals L_lit[-1]",
        315, _spec_llit(spectra, "naturals"))
    add("759 L_lit", "§6", "759", "control_growth.csv", "L_lit min",
        759, int(growth["L_lit_full"].min()))
    add("3377 L_lit", "§6", "3377", "control_growth.csv", "L_lit max",
        3377, int(growth["L_lit_full"].max()))
    add("22 L_H", "§6", "22", "control_growth.csv", "L_H min",
        22, int(growth["L_H"].min()))
    add("98 L_H", "§6", "98", "control_growth.csv", "L_H max",
        98, int(growth["L_H"].max()))
    # lambda: L(N)/Llit — from growth row scale=1
    row1 = growth[growth["scale"] == 1].iloc[0]
    # need final lambda — may not be in CSV; compute from spectra fib
    add("lambda 0.029", "§6", "0.029", "spectra.json", "fibonacci final_lambda",
        0.029, _fib_lambda(spectra, feat))
    add("24 cells", "§6", "24$ cells", "control_phase.csv", "nrows",
        24, len(phase))
    add("nd=2p*+3 true period", "§6", "2p^{*}+3", "control_phase.csv",
        "n_d==n_id==2*order+3 (C-finite)", True, _phase_ok_true_period(phase))

    # ----- §7 deception -----
    sub = deco[deco.period.isin([7, 9, 11, 13, 15])]
    add("settle=2p+3", "§7", "2p+3", "deception.csv", "settle",
        True, bool((sub.settle == 2 * sub.period + 3).all()))
    add("4.50 p=7", "§7", "4.50", "deception.csv", "peak p=7",
        4.5, float(deco.loc[deco.period == 7, "peak_abs_rho"].iloc[0]))
    add("7.50 p=9", "§7", "7.50", "deception.csv", "peak p=9",
        7.5, float(deco.loc[deco.period == 9, "peak_abs_rho"].iloc[0]))
    add("10.50 p=11", "§7", "10.50", "deception.csv", "peak p=11",
        10.5, float(deco.loc[deco.period == 11, "peak_abs_rho"].iloc[0]))
    add("11.0 p=13", "§7", "11.0", "deception.csv", "peak p=13",
        11.0, float(deco.loc[deco.period == 13, "peak_abs_rho"].iloc[0]))
    add("11.0 p=15", "§7", "p \\ge 13", "deception.csv", "peak p=15",
        11.0, float(deco.loc[deco.period == 15, "peak_abs_rho"].iloc[0]))
    add("21.8%", "§7", "21.8\\%", "deception_random.csv", "rate",
        21.8, round(100 * (deco_r.struct_rev > 0).mean(), 1))
    add("440", "§7", "440$", "deception_random.csv", "n", 440, len(deco_r))
    add("0% p<=4", "§7", "p \\le 4", "deception_random.csv", "p<=4 rate",
        0.0, round(100 * (deco_r[deco_r.period <= 4].struct_rev > 0).mean(), 1))
    add("7.5% p=5", "§7", "7.5\\%", "deception_random.csv", "p=5",
        7.5, _ppct(deco_r, 5))
    add("27.5% p=6", "§7", "27.5\\% at $p=6$", "deception_random.csv", "p=6",
        27.5, _ppct(deco_r, 6))
    add("35% p=10", "§7", "35\\% at $p=10$", "deception_random.csv", "p=10",
        35.0, _ppct(deco_r, 10))
    add("45% p=12", "§7", "45\\% at $p=12$", "deception_random.csv", "p=12",
        45.0, _ppct(deco_r, 12))
    add("27.5% p=11", "§7", "p=11", "deception_random.csv", "p=11",
        27.5, _ppct(deco_r, 11))
    # Paper says "at n=7/8/17"; rho[i] is R(n_i)=L(n_i+1)-L(n_i).
    # Spurious discovery: step 6->7 (rho at n=6); refutation 7->8; true 16->17.
    add("rho=-0.75", "§7", "-0.75", "recompute D_3 spectrum", "rho at n=6 (into discovery@7)",
        -0.75, _d3_rho_at(6))
    add("rho=+4.50", "§7", "+4.50", "recompute D_3 spectrum", "rho at n=7 (into refutation@8)",
        4.5, _d3_rho_at(7))
    add("rho=-3.50", "§7", "-3.50", "recompute D_3 spectrum", "rho at n=16 (into settle@17)",
        -3.5, _d3_rho_at(16),
        note="Paper labels these events at n=7/8/17 (prefix after the step)")

    # ----- wilderness -----
    add("1887", "§wilderness", "1887", "truncation_1887_summary.json", "n",
        1887, trunc["n"])
    add("160", "§wilderness", "$160$", "truncation_1887_summary.json", "undetermined",
        160, trunc["undetermined"])
    add("8.48%", "§wilderness", "8.48\\%", "truncation_1887_summary.json",
        "pct_undetermined", 8.48, round(trunc["pct_undetermined"], 2))

    # ----- LCP -----
    lcp_stats = _lcp_stats(lcp, feat)
    add("LCP NONH 11.20", "§LCP", "11.20", "lcp.json+features", "NONH mean final",
        11.20, lcp_stats.get("NONH"))
    add("LCP means poly/cfin/prec", "§LCP", "1.80", "lcp.json+features", "POLY mean",
        1.80, lcp_stats.get("POLY"))
    add("LCP CFIN 1.94", "§LCP", "1.94", "lcp.json+features", "CFIN mean",
        1.94, lcp_stats.get("CFIN"))
    add("LCP PREC 5.93", "§LCP", "5.93", "lcp.json+features", "PREC mean",
        5.93, lcp_stats.get("PREC"))
    add("LCP F=9.81", "§LCP", "9.81", "lcp.json+features", "ANOVA F",
        9.81, lcp_stats.get("F"))

    # ----- LLM body -----
    add("60 seq", "§LLM", "60$ sequences", "llm_summary.json", "n_sequences",
        60, llm["n_sequences"])
    add("12 failed", "§LLM", "12$ failed", "llm_summary.json", "n_failed_calls",
        12, llm["n_failed_calls"])
    add("3.18 conf", "§LLM", "3.18", "llm_summary.json", "claude mean conf wild",
        3.18, round(L("claude", "wilderness", "mean_confidence"), 2))
    add("2.45 conf", "§LLM", "2.45", "llm_summary.json", "gpt mean conf wild",
        2.45, round(L("gpt", "wilderness", "mean_confidence"), 2))
    add("2.68 conf", "§LLM", "2.68", "llm_summary.json", "llama mean conf wild",
        2.68, round(L("llama", "wilderness", "mean_confidence"), 2))
    for label, model, stratum, key, want in [
        ("claude confab clean", "claude", "clean", "confabulation_rate", "3/17"),
        ("gpt confab clean", "gpt", "clean", "confabulation_rate", "9/20"),
        ("llama confab clean", "llama", "clean", "confabulation_rate", "13/20"),
        ("claude confab wild", "claude", "wilderness", "confabulation_rate", "2/17"),
        ("gpt confab wild", "gpt", "wilderness", "confabulation_rate", "1/20"),
        ("llama confab wild", "llama", "wilderness", "confabulation_rate", "4/19"),
        ("claude exact clean", "claude", "clean", "exact_accuracy", "12/17"),
        ("gpt exact clean", "gpt", "clean", "exact_accuracy", "8/20"),
        ("llama exact clean", "llama", "clean", "exact_accuracy", "5/20"),
        ("claude recog", "claude", "clean", "exact_accuracy_recognized", "8/10"),
        ("gpt recog", "gpt", "clean", "exact_accuracy_recognized", "4/11"),
        ("llama recog", "llama", "clean", "exact_accuracy_recognized", "5/6"),
        ("claude notrecog", "claude", "clean", "exact_accuracy_not_recognized", "4/7"),
        ("gpt notrecog", "gpt", "clean", "exact_accuracy_not_recognized", "4/9"),
        ("llama notrecog", "llama", "clean", "exact_accuracy_not_recognized", "0/14"),
        ("claude exact wild", "claude", "wilderness", "exact_accuracy", "7/17"),
        ("gpt exact wild", "gpt", "wilderness", "exact_accuracy", "7/20"),
        ("llama exact wild", "llama", "wilderness", "exact_accuracy", "3/19"),
        ("claude abstain", "claude", "wilderness", "abstention_rate", "11/17"),
        ("gpt abstain", "gpt", "wilderness", "abstention_rate", "19/20"),
        ("llama abstain", "llama", "wilderness", "abstention_rate", "17/19"),
    ]:
        add(label, "§LLM", want.replace("/", "/"), "llm_summary.json",
            f"{model}.{stratum}.{key}", want, frac_str(L(model, stratum, key)))

    # ----- limitations / encoding -----
    add("1612 rows/h", "§9", "1612", "oeis_60_calibration.json", "rows_per_hour_wall",
        1612, round(cal["rows_per_hour_wall"]))
    add("12.4 h", "§9", "12.4", "oeis_60_calibration.json", "projected_hours_wall_20000",
        12.4, round(cal["projected_hours_wall_20000"], 1))
    add("500 calib", "§9", "500", "oeis_60_calibration.json", "n_sequences",
        500, cal["n_sequences"])
    add("21.8% vs", "§9", "21.8\\% vs", "deception_random.csv", "default rate",
        21.8, round(100 * (deco_r.struct_rev > 0).mean(), 1))
    add("14.3% strict contrast", "§9", "14.3\\%", "deception_random_strict.csv",
        "rate", 14.3, round(100 * (deco_strict.struct_rev > 0).mean(), 1))
    add("strict file cited", "§9", "deception\\_random\\_strict.csv",
        "deception_random_strict.csv", "exists", True,
        (RES / "deception_random_strict.csv").exists())
    add("ablation exact invariant", "§9", "41/46 exact", "ablation_encoding_summary.json",
        "loose.exact==strict.exact", True,
        ab["loose"]["exact"] == ab["strict"]["exact"] == 41)
    add("strict revisers", "§9", "triangular/oblong", "ablation_encoding_summary.json",
        "strict.reviser_anums", {"A000217", "A002378"}, set(ab["strict"]["reviser_anums"]))
    add("loose revisers §9", "§9", "A000578", "ablation_encoding_summary.json",
        "loose.reviser_anums", {"A000578", "A000330"}, set(ab["loose"]["reviser_anums"]))

    # ----- tables -----
    add("table2 41/46", "table2", "41/46", "analysis.json", "exact", True, "41/46" in TAB2)
    add("table2 0.11", "table2", "0.11", "analysis.json", "mae", True, "0.11" in TAB2)
    add("table2 3.20", "table2", "3.20", "analysis.json", "mae_x", True, "3.20" in TAB2)
    add("table1 POLY 8.5", "table1", "8.5", "analysis.json", "POLY mean rounded",
        8.5, round(a["mean_nd_by_class"]["POLY"], 1))
    add("table1 rev 2", "table1", "POLY & 15 & 15 & 8.5", "analysis.json",
        "n_with_revision", 2, a["n_with_revision"])

    # ----- recommendations -----
    add("21.8% reco", "§reco", "21.8\\% even", "deception_random.csv", "rate",
        21.8, round(100 * (deco_r.struct_rev > 0).mean(), 1))

    # ----- figure scripts -----
    audit_figure_scripts()

    # print
    print(f"{'STATUS':<12} {'NUMBER':<28} {'WHERE':<12} SOURCE")
    print("=" * 120)
    for status, number, where, sentence, source, exp, act, note in rows:
        print(f"{status:<12} {number:<28} {where:<12} {source}")
        print(f"             expected={exp!r} actual={act!r} {note}")
        print(f"             {sentence[:160]}")
        print()

    n_pass = sum(1 for r in rows if r[0] == "PASS")
    n_fail = sum(1 for r in rows if r[0] == "FAIL")
    n_untr = sum(1 for r in rows if r[0] == "UNTRACEABLE")
    print("=" * 60)
    print(f"SUMMARY: total={len(rows)} PASS={n_pass} FAIL={n_fail} UNTRACEABLE={n_untr}")
    if n_untr:
        print("\n*** UNTRACEABLE DEFECTS ***")
        for r in rows:
            if r[0] == "UNTRACEABLE":
                print(f"  - {r[1]} @ {r[2]}: {r[4]} | {r[7]}")
    if n_fail:
        print("\n*** FAIL ***")
        for r in rows:
            if r[0] == "FAIL":
                print(f"  - {r[1]} @ {r[2]}: expected {r[5]!r} got {r[6]!r} | {r[7]}")
    return 0 if n_fail == 0 and n_untr == 0 else 1


def _exact_pct(revisers: bool) -> float:
    df = pd.read_csv(RES / "oeis_fixed30.csv")
    H = df[df.order.notna() & df.degree.notna() & df.n_id.notna()].copy()
    H["rev"] = H.n_struct_rev.astype(float) > 0
    H["err"] = (H.n_d.astype(float) - H.n_id.astype(float)).abs()
    sub = H[H.rev == revisers]
    return round(100 * (sub.err == 0).mean(), 1)


def _w1_pct(revisers: bool) -> float:
    df = pd.read_csv(RES / "oeis_fixed30.csv")
    H = df[df.order.notna() & df.degree.notna() & df.n_id.notna()].copy()
    H["rev"] = H.n_struct_rev.astype(float) > 0
    H["err"] = (H.n_d.astype(float) - H.n_id.astype(float)).abs()
    sub = H[H.rev == revisers]
    return round(100 * (sub.err <= 1).mean(), 1)


def _spec_llit(spectra, name_sub: str):
    if isinstance(spectra, dict):
        for v in spectra.values():
            if isinstance(v, dict) and name_sub.lower() in str(v.get("name", "")).lower():
                return int(v["L_lit"][-1])
    return None


def _fib_lambda(spectra, feat):
    row = feat[feat["anum"] == "A000045"]
    if len(row):
        return round(float(row.iloc[0]["final_lambda"]), 3)
    return None


def _phase_ok(phase) -> bool:
    if "period" in phase.columns and "n_d" in phase.columns:
        return bool(
            (phase["n_d"] == phase["n_id"]).all()
            and (phase["n_d"] == 2 * phase["period"] + 3).all()
        )
    return None


def _phase_ok_true_period(phase) -> bool:
    """Law uses true period = operator order for these C-finite sequences."""
    if not {"n_d", "n_id", "order", "degree"}.issubset(phase.columns):
        return None
    pred = 2 * phase["order"] + 3  # degree 0 => n_id = (r+1)+s+r = 2r+3 with s=2
    return bool(
        (phase["degree"] == 0).all()
        and (phase["n_d"] == phase["n_id"]).all()
        and (phase["n_id"] == pred).all()
    )


def _ppct(df, p):
    sub = df[df.period == p]
    return round(100 * (sub.struct_rev > 0).mean(), 1)


def _d3_rho_at(n):
    """Recompute D_3 spectrum (read-only) for caption landmarks."""
    from experiments.run_deception import deceptive
    from revspec.core import revision_spectrum

    res = revision_spectrum(deceptive(3, 33), n_min=6, max_order=10, max_degree=1, slack=2)
    if n not in res.n_values:
        return None
    # rho[i] is revision from n_values[i] to n_values[i]+1? check core
    # R(n)=L(n+1)-L(n) stored aligned with n_values[:-1] or with n?
    # In SpectrumResult, rho has len N-1 typically paired with n_values[:-1]
    idx = res.n_values.index(n)
    if idx >= len(res.rho):
        # try n-1 as the step ending at n
        if idx - 1 >= 0 and idx - 1 < len(res.rho):
            return round(res.rho[idx - 1], 2)
        return None
    return round(res.rho[idx], 2)


def _lcp_stats(lcp, feat):
    finals = {}
    for _, row in feat.iterrows():
        anum = row["anum"]
        if anum not in lcp:
            continue
        finals.setdefault(row["true_class"], []).append(float(lcp[anum][-1]))
    out = {cls: round(sum(v) / len(v), 2) for cls, v in finals.items() if v}
    if len(finals) >= 2:
        F, p = f_oneway(*finals.values())
        out["F"] = round(F, 2)
        out["p"] = p
    return out


if __name__ == "__main__":
    # ensure package import for D3
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
