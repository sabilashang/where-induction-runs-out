"""
Figure 5 -- the LLM benchmark-validity result.

Every value plotted here is read from results/llm_summary.json, produced by the
OpenRouter evaluation (180 calls, 3 models, 60 sequences, temperature 0).
Nothing is transcribed, so the figure cannot drift from the results; the file
is checked in, so the figure still regenerates without an API key.
"""

from __future__ import annotations

import json
import os
import re
import warnings

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(__file__)
RES = os.path.join(HERE, "..", "results")
FIG = os.path.join(HERE, "..", "paper", "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.linewidth": 0.6, "grid.linewidth": 0.4, "lines.linewidth": 1.1,
    "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 200,
    "axes.spines.top": False, "axes.spines.right": False,
})

MODELS = ["anthropic/claude-sonnet-4.5", "openai/gpt-4o",
          "meta-llama/llama-3.3-70b-instruct"]
SHORT = ["Claude", "GPT-4o", "Llama"]
COL = ["#2c6fbb", "#1a9850", "#d95f02"]

# --- read every plotted value from results/llm_summary.json ----------------
_BY_MODEL = json.load(
    open(os.path.join(RES, "llm_summary.json")))["aggregates"]["by_model"]


def _ratio(model, stratum, field):
    """Parse an 'a/b (p%)' cell from llm_summary.json into (a, b, a/b)."""
    cell = _BY_MODEL[model]["by_stratum"][stratum][field]
    a, b = (int(v) for v in re.match(r"\s*(\d+)\s*/\s*(\d+)", cell).groups())
    return a, b, (a / b if b else 0.0)


def _series(stratum, field):
    return [_ratio(m, stratum, field)[2] for m in MODELS]


confab_clean = _series("clean", "confabulation_rate")
confab_wild = _series("wilderness", "confabulation_rate")

clean_recog = _series("clean", "exact_accuracy_recognized")
clean_unrec = _series("clean", "exact_accuracy_not_recognized")

wild_abstain = _series("wilderness", "abstention_rate")
wild_exact = _series("wilderness", "exact_accuracy")


def main():
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.3))
    x = np.arange(3)
    w = 0.36

    # (a) inverted confabulation
    ax = axes[0]
    ax.bar(x - w / 2, [100 * v for v in confab_clean], w,
           label="clean (has formula)", color="#d95f02")
    ax.bar(x + w / 2, [100 * v for v in confab_wild], w,
           label="wilderness (none)", color="#9ecae1")
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT)
    ax.set_ylabel(r"confabulation rate (%)")
    ax.set_title("(a) confident errors are inverted")
    ax.legend(frameon=False, loc="upper left")

    # (b) contamination
    ax = axes[1]
    ax.bar(x - w / 2, [100 * v for v in clean_recog], w,
           label="recognised", color="#2c6fbb")
    ax.bar(x + w / 2, [100 * v for v in clean_unrec], w,
           label="not recognised", color="#bbbbbb")
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT)
    ax.set_ylabel(r"exact accuracy (%)")
    ax.set_title("(b) clean accuracy is recall")
    ax.legend(frameon=False, loc="upper right")
    lu_a, lu_b, _ = _ratio(MODELS[2], "clean", "exact_accuracy_not_recognized")
    ax.annotate(f"{lu_a}/{lu_b}", xy=(2 + w / 2, 2), xytext=(2 + w / 2, 22),
                ha="center", fontsize=6.5,
                arrowprops=dict(arrowstyle="->", lw=.6))

    # (c) hedging
    ax = axes[2]
    ax.bar(x - w / 2, [100 * v for v in wild_abstain], w,
           label="abstention", color="#1a9850")
    ax.bar(x + w / 2, [100 * v for v in wild_exact], w,
           label="exact accuracy", color="#cccccc")
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT)
    ax.set_ylabel(r"%")
    ax.set_title("(c) models hedge in the wilderness")
    ax.legend(frameon=False, loc="upper left")

    # All three panels are percentages. Ticks run 0-100 so the panels are
    # directly comparable; the axis extends past 100 purely to leave headroom
    # for the legends, so no bar is clipped and no legend overlaps a bar.
    for ax in axes:
        ax.set_ylim(0, 118)
        ax.set_yticks([0, 20, 40, 60, 80, 100])

    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_llm.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("fig_llm.pdf")


if __name__ == "__main__":
    main()
