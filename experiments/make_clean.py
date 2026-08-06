"""Remove classical pipeline artefacts only (OEIS/LLM results kept)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    "results/spectra.json",
    "results/features.csv",
    "results/lcp.json",
    "results/regimes.csv",
    "results/analysis.json",
    "results/control_growth.csv",
    "results/control_phase.csv",
    "results/deception.csv",
    "results/deception_random.csv",
    "paper/figures/fig_strata.pdf",
    "paper/figures/fig_anatomy.pdf",
    "paper/figures/fig_identification.pdf",
    "paper/figures/fig_atlas.pdf",
    "paper/figures/fig_deception.pdf",
    "paper/tables/table1_corpus.tex",
    "paper/tables/table2_prediction.tex",
    "paper/main.aux",
    "paper/main.log",
    "paper/main.out",
    "paper/main.bbl",
    "paper/main.blg",
    "paper/main.fls",
    "paper/main.fdb_latexmk",
    "paper/main.synctex.gz",
]


def main() -> None:
    removed = 0
    for rel in TARGETS:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            removed += 1
    print(f"clean: removed {removed} classical artefacts")


if __name__ == "__main__":
    main()
