"""Generate all figures (PDF) and LaTeX tables from the results directory."""

from __future__ import annotations

import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from revspec.core import revision_spectrum
from experiments.run_deception import deceptive

HERE = os.path.dirname(__file__)
RES = os.path.join(HERE, "..", "results")
FIG = os.path.join(HERE, "..", "paper", "figures")
TAB = os.path.join(HERE, "..", "paper", "tables")
os.makedirs(FIG, exist_ok=True)
os.makedirs(TAB, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.linewidth": 0.6, "grid.linewidth": 0.4, "lines.linewidth": 1.1,
    "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 200,
    "axes.spines.top": False, "axes.spines.right": False,
})

CLS_COLOR = {"POLY": "#2c6fbb", "CFIN": "#1a9850", "PREC": "#d95f02", "NONH": "#888888"}


# --------------------------------------------------------------------------- #
def fig_anatomy():
    """Anatomy of a revision spectrum: the planted deceptive sequence D_3."""
    J = 3                                    # D_J = (0 1)^J 0, true period 2J+1
    seq = deceptive(J, 33)
    r = revision_spectrum(seq, n_min=6, max_order=10, max_degree=1, slack=2)
    n, L, Ll = np.array(r.n_values), np.array(r.L), np.array(r.L_lit)
    rn, rho = np.array(r.n_values[:-1]), np.array(r.rho)

    # Every landmark and operator order below is derived from the spectrum just
    # computed, never transcribed: a hardcoded landmark would silently go stale
    # if the encoding or the hypothesis class changed.
    struct = [lab != "literal" for lab in r.labels]
    i_spur = struct.index(True)                                   # spurious fit
    i_ref = next(i for i in range(i_spur, len(struct)) if not struct[i])
    i_set = next(i for i in range(i_ref, len(struct)) if struct[i])
    n_spur, n_ref, n_set = (r.n_values[i] for i in (i_spur, i_ref, i_set))
    order = lambda i: int(re.search(r"r=(\d+)", r.labels[i]).group(1))
    p_spur, p_true = order(i_spur), order(i_set)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.5, 3.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1.35, 1]})
    ax1.plot(n, Ll, color="#999999", ls="--", label=r"$L_{\rm lit}(n)$ (verbatim)")
    ax1.plot(n, L, color="#1f1f1f", marker="o", ms=2.4, label=r"$L(n)$ (MDL)")
    ax1.set_ylabel("description length (bits)")
    ax1.legend(loc="upper left", frameon=False)

    # Phase bands.  ax1 plots the states L(n), so its bands are state-indexed:
    # literal at 6, spurious fit at 7, wilderness 8..16, stable from 17.
    for lo, hi, col, al in ((n[0], n_spur, "#cccccc", .30),
                            (n_spur, n_ref, "#2c6fbb", .16),
                            (n_ref, n_set, "#d95f02", .13),
                            (n_set, n[-1], "#1a9850", .13)):
        ax1.axvspan(lo, hi, color=col, alpha=al)
    # ax2 plots rho(n) = [L(n+1)-L(n)]/l(s_{n+1}), indexed by the SOURCE n, so
    # the revision at n is what installs the state at n+1.  Its bands are
    # therefore shifted one step left -- each stem is shaded by the phase it
    # leads INTO -- and broken at half-integers so no stem lands on an edge.
    # Unshifted, the -0.75 discovery at n=6 would sit in the literal band and
    # the -3.50 discovery at n=16 in the wilderness band.
    for lo, hi, col, al in ((n_spur - 1.5, n_spur - .5, "#2c6fbb", .16),
                            (n_spur - .5, n_set - 1.5, "#d95f02", .13),
                            (n_set - 1.5, n[-1], "#1a9850", .13)):
        ax2.axvspan(lo, hi, color=col, alpha=al)

    ax2.axhline(0, color="k", lw=.6)
    ax2.axhline(1, color="#999999", lw=.6, ls=":")
    ax2.stem(rn, rho, linefmt="C0-", markerfmt="C0o", basefmt=" ")
    ax2.set_ylabel(r"revision  $\rho(n)$")
    ax2.set_xlabel(r"prefix length $n$")
    ax2.set_ylim(-4.6, 5.4)

    # Data anchors (xy) are derived; the xytext values are layout offsets only.
    ax1.annotate(f"spurious\nperiod-{p_spur} fit", xy=(n_spur, L[i_spur]),
                 xytext=(n_spur + 1.4, .45 * Ll[-1]),
                 arrowprops=dict(arrowstyle="->", lw=.6), ha="left", fontsize=6.5)
    ax1.annotate("refuted", xy=(n_ref, L[i_ref]),
                 xytext=(n_ref + 2.4, .21 * Ll[-1]),
                 arrowprops=dict(arrowstyle="->", lw=.6), ha="left", fontsize=6.5)
    ax1.annotate(f"true period-{p_true}\noperator found", xy=(n_set, L[i_set]),
                 xytext=(n_set + 2, .29 * Ll[-1]),
                 arrowprops=dict(arrowstyle="->", lw=.6), ha="left", fontsize=6.5)
    ax2.text((n_spur + n_set) / 2, 3.4, "wilderness\n(no theory)",
             ha="center", fontsize=6.5)
    ax2.text((n_set + n[-1]) / 2, 3.4, r"stable: $\rho=0$",
             ha="center", fontsize=6.5)

    fig.suptitle(rf"Anatomy of a revision spectrum: "
                 rf"$D_{J}=(0\,1)^{J} 0$, true period {p_true}",
                 y=.99, fontsize=8.5)
    fig.tight_layout(rect=[0, 0, 1, .96])
    fig.savefig(os.path.join(FIG, "fig_anatomy.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_anatomy.pdf")


def fig_identification():
    """n_d is predicted by identifiability, and is invariant to growth."""
    df = pd.read_csv(os.path.join(RES, "regimes.csv"))
    fit = df.dropna(subset=["n_d"])
    g = pd.read_csv(os.path.join(RES, "control_growth.csv"))
    # Titles quote measured quantities; read them from results/analysis.json
    # rather than transcribing, so the figure cannot drift from the results.
    an = json.load(open(os.path.join(RES, "analysis.json")))
    exact_pct = 100.0 * an["exact"] / an["n_fittable"]
    corr_growth = an["corr_growth"]

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.25))

    ax = axes[0]
    for cls in ["POLY", "CFIN", "PREC"]:
        s = fit[fit.true_class == cls]
        ax.scatter(s["n_id"] + np.random.RandomState(0).uniform(-.12, .12, len(s)),
                   s["n_d"], s=16, alpha=.85, label=cls,
                   color=CLS_COLOR[cls], edgecolor="none")
    lo, hi = 5.4, 14
    ax.plot([lo, hi], [lo, hi], color="k", lw=.7, ls="--", zorder=0)
    ax.set_xlabel(r"identifiability bound $n_{\rm id}$")
    ax.set_ylabel(r"discovery point $n_d$")
    ax.set_title(rf"(a) $n_d=n_{{\rm id}}$: {exact_pct:.0f}% exact")
    ax.legend(frameon=False, loc="upper left")

    ax = axes[1]
    ax.scatter(fit["growth"], fit["n_d"], s=16, alpha=.8,
               c=[CLS_COLOR[c] for c in fit["true_class"]], edgecolor="none")
    ax.set_xlabel("growth rate (bits/term)")
    ax.set_ylabel(r"$n_d$")
    ax.set_title(rf"(b) growth is irrelevant ($r={corr_growth:.3f}$)")

    ax = axes[2]
    ax.semilogx(g["scale"], g["n_d"], marker="o", ms=3.5, color="#1f1f1f",
                label=r"$n_d$")
    ax.semilogx(g["scale"], g["L_H"] / g["L_lit_full"] * 100, marker="s", ms=3.5,
                color="#d95f02", label=r"$100\times\lambda$")
    ax.set_xlabel(r"initial condition $a(1)$")
    ax.set_ylim(0, 10)
    ax.set_title("(c) growth invariance (Fibonacci)")
    ax.legend(frameon=False, loc="center right")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_identification.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_identification.pdf")


def fig_atlas():
    """Small multiples: MDL curves for representative sequences of each class."""
    spec = json.load(open(os.path.join(RES, "spectra.json")))
    picks = [("A000027", "POLY"), ("A000290", "POLY"), ("A000583", "POLY"),
             ("A000045", "CFIN"), ("A000079", "CFIN"), ("A001608", "CFIN"),
             ("A000142", "PREC"), ("A000108", "PREC"), ("A001006", "PREC"),
             ("A000040", "NONH"), ("A000110", "NONH"), ("A000002", "NONH")]
    # 6.5in == \textwidth at 1in margins on letter, so the figure is included
    # at scale 1.0 and the nominal font sizes below are the rendered sizes.
    fig, axes = plt.subplots(3, 4, figsize=(6.5, 3.95), sharex=True)
    for ax, (a, cls) in zip(axes.T.ravel(), picks):
        s = spec[a]
        n = np.array(s["n"])
        ax.plot(n, s["L_lit"], color="#bbbbbb", ls="--", lw=.9)
        ax.plot(n, s["L"], color=CLS_COLOR[cls], lw=1.2)
        d = s.get("discovery")
        if d:
            ax.axvline(d, color="k", lw=.5, ls=":")
        ax.set_title(f"{s['name'][:17]}\n{a} ({cls})", fontsize=6.8, pad=2.5)
        ax.tick_params(labelsize=6.5)
        ax.set_yscale("log")
    for ax in axes[-1]:
        ax.set_xlabel(r"$n$", fontsize=7)
    for ax in axes[:, 0]:
        ax.set_ylabel("bits", fontsize=7)
    fig.suptitle(r"MDL curve $L(n)$ (solid) vs verbatim $L_{\rm lit}(n)$ (dashed); "
                 r"dotted line = discovery point", fontsize=8, y=1.0)
    fig.tight_layout(rect=[0, 0, 1, .96])
    fig.savefig(os.path.join(FIG, "fig_atlas.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_atlas.pdf")


def fig_deception():
    d = pd.read_csv(os.path.join(RES, "deception.csv"))
    r = pd.read_csv(os.path.join(RES, "deception_random.csv"))
    rate = r.groupby("period")["struct_rev"].apply(lambda x: (x > 0).mean())

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.15))

    ax = axes[0]
    dd = d[d.n_refutations > 0]
    ax.plot(dd["period"], dd["first_fit"], marker="o", ms=3.4,
            label="spurious fit", color="#2c6fbb")
    ax.plot(dd["period"], dd["first_refutation"], marker="s", ms=3.4,
            label="refutation", color="#d95f02")
    ax.plot(dd["period"], dd["settle"], marker="^", ms=3.4,
            label="true operator", color="#1a9850")
    ax.set_xlabel("true period $p$")
    ax.set_ylabel("prefix length $n$")
    ax.set_title("(a) planted deception $D_j$")
    ax.set_xticks(sorted(dd["period"].unique()))     # period is an integer
    ax.legend(frameon=False, loc="upper left")

    ax = axes[1]
    ax.plot(dd["period"], dd["peak_abs_rho"], marker="o", ms=3.4, color="#1f1f1f")
    z = np.polyfit(dd["period"], dd["peak_abs_rho"], 1)
    xs = np.linspace(dd["period"].min(), dd["period"].max(), 10)
    ax.plot(xs, np.polyval(z, xs), ls="--", lw=.7, color="#d95f02",
            label=f"slope {z[0]:.2f}")
    ax.set_xlabel("true period $p$")
    ax.set_ylabel(r"peak $|\rho|$")
    ax.set_title("(b) revision magnitude scales")
    ax.set_xticks(sorted(dd["period"].unique()))     # period is an integer
    ax.legend(frameon=False)

    ax = axes[2]
    ax.bar(rate.index, rate.values * 100, color="#2c6fbb", width=.66)
    ax.set_xlabel("period of random binary sequence")
    ax.set_ylabel(r"% with a revision")
    ax.set_title("(c) unplanted deception rate")
    ax.set_xticks(sorted(rate.index))                # period is an integer

    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_deception.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_deception.pdf")


# --------------------------------------------------------------------------- #
def tables():
    df = pd.read_csv(os.path.join(RES, "regimes.csv"))
    an = json.load(open(os.path.join(RES, "analysis.json")))

    # ---- Table 1: corpus summary by class ---------------------------------
    g = df.groupby("true_class")
    rows = []
    for cls in ["POLY", "CFIN", "PREC", "NONH"]:
        s = g.get_group(cls)
        fit = s.dropna(subset=["n_d"])
        rows.append((
            cls, len(s), len(fit),
            f"{fit['n_d'].mean():.1f}" if len(fit) else "--",
            f"{fit['n_d'].min():.0f}--{fit['n_d'].max():.0f}" if len(fit) else "--",
            f"{fit['L_H'].mean():.0f}" if len(fit) else "--",
            f"{s['final_lambda'].mean():.3f}",
            f"{int(s['n_struct_rev'].sum())}",
        ))
    t1 = ["\\begin{tabular}{lrrrrrrr}", "\\toprule",
          "class & $|C|$ & fitted & mean $n_d$ & range & mean $L(H^*)$ "
          "& mean $\\lambda_N$ & revisions \\\\", "\\midrule"]
    for r in rows:
        t1.append(" & ".join(str(x) for x in r) + " \\\\")
    t1 += ["\\midrule",
           f"all & {len(df)} & {int(df['n_d'].notna().sum())} & "
           f"{df['n_d'].mean():.1f} & {df['n_d'].min():.0f}--{df['n_d'].max():.0f} & "
           f"{df['L_H'].mean():.0f} & {df['final_lambda'].mean():.3f} & "
           f"{int(df['n_struct_rev'].sum())} \\\\",
           "\\bottomrule", "\\end{tabular}"]
    open(os.path.join(TAB, "table1_corpus.tex"), "w").write("\n".join(t1))

    # ---- Table 2: prediction accuracy -------------------------------------
    t2 = ["\\begin{tabular}{lrrr}", "\\toprule",
          "predictor & exact & within $\\pm1$ & MAE \\\\", "\\midrule"]
    fit = df.dropna(subset=["n_d", "pred"])
    for nm, col in [("$\\max(n_{\\rm id}, n_\\times)$", "pred"),
                    ("$n_{\\rm id}$ alone", "n_id"),
                    ("$n_\\times$ alone", "n_x")]:
        ex = int((fit["n_d"] == fit[col]).sum())
        w1 = int((abs(fit["n_d"] - fit[col]) <= 1).sum())
        mae = abs(fit["n_d"] - fit[col]).mean()
        t2.append(f"{nm} & {ex}/{len(fit)} & {w1}/{len(fit)} & {mae:.2f} \\\\")
    mean_pred = fit["n_d"].mean()
    t2.append(f"corpus mean & 0/{len(fit)} & "
              f"{int((abs(fit['n_d']-mean_pred)<=1).sum())}/{len(fit)} & "
              f"{abs(fit['n_d']-mean_pred).mean():.2f} \\\\")
    t2 += ["\\bottomrule", "\\end{tabular}"]
    open(os.path.join(TAB, "table2_prediction.tex"), "w").write("\n".join(t2))

    print("table1_corpus.tex, table2_prediction.tex")
    return an


def fig_strata():
    """Schematic of the three MDL strata used to stratify the LLM evaluation.

    This figure carries no measured values: it is a stylised drawing of the
    three characteristic L(n) shapes, so the axes are deliberately unticked.
    Colours reuse the fig1 phase palette (green = stable, blue = revised,
    orange = wilderness) and the same verbatim/MDL line styles.
    """
    n = np.arange(0, 31)
    llit = 3.0 * n + 6.0

    def piece(segments):
        """segments: list of (start, stop, value-or-None); None = follow L_lit."""
        out = llit.astype(float).copy()
        for lo, hi, val in segments:
            m = (n >= lo) & (n < hi)
            if val is not None:
                out[m] = val
        return out

    clean = piece([(8, 31, llit[8] * 0.62)])
    revising = piece([(7, 14, llit[7] * 0.60), (18, 31, llit[18] * 0.72)])
    wilderness = piece([(7, 13, llit[7] * 0.60)])

    panels = [
        ("(a) clean", clean, "#1a9850", 8,
         "holonomic operator found at full\nlength, and never revised"),
        ("(b) revising", revising, "#2c6fbb", 7,
         "operator found, then refuted and\nreplaced by a costlier one"),
        ("(c) wilderness", wilderness, "#d95f02", 7,
         "prefix fit only: no operator at full\nlength, at least 40 terms available"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.35), sharey=True)
    for ax, (title, curve, colour, nd, cond) in zip(axes, panels):
        # L(n) first, L_lit on top, so the dashed verbatim line stays visible
        # through the stretches where the two coincide (the wilderness).
        ax.plot(n, curve, color=colour, lw=1.6, zorder=2, label=r"$L(n)$ (MDL)")
        ax.plot(n, llit, color="#999999", ls="--", lw=1.0, zorder=3,
                label=r"$L_{\rm lit}(n)$ (verbatim)")
        ax.axvline(nd, color="k", lw=.7, ls=":", zorder=1)
        ax.text(nd + .7, llit[-1] * .04, r"$n_d$", fontsize=7, va="bottom")
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel(r"prefix length $n$")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_ylim(0, llit[-1] * 1.06)
        ax.text(.5, -.40, cond, transform=ax.transAxes, ha="center",
                va="top", fontsize=6.6, linespacing=1.35)

    axes[0].set_ylabel("description length (bits)")
    axes[0].legend(loc="upper left", fontsize=6.6, frameon=True, framealpha=1.0,
                   edgecolor="none", facecolor="white", borderpad=.2).set_zorder(5)
    axes[1].annotate("refuted", xy=(14, llit[14]), xytext=(15.5, llit[14] * .45),
                     arrowprops=dict(arrowstyle="->", lw=.6), fontsize=6.4)
    axes[2].annotate("never recovers", xy=(24, llit[24]),
                     xytext=(14.5, llit[-1] * .18),
                     arrowprops=dict(arrowstyle="->", lw=.6), fontsize=6.4)

    fig.subplots_adjust(bottom=.34)
    fig.savefig(os.path.join(FIG, "fig_strata.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_strata.pdf")


if __name__ == "__main__":
    fig_strata()
    fig_anatomy()
    fig_identification()
    fig_atlas()
    fig_deception()
    tables()
    print("\nall figures + tables written")
