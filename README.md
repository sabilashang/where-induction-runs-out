# Where Induction Runs Out

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21830331-blue.svg)](https://doi.org/10.5281/zenodo.21830331)
[![Software DOI](https://img.shields.io/badge/Software_DOI-10.5281%2Fzenodo.21830532-blue.svg)](https://doi.org/10.5281/zenodo.21830532)
[![arXiv](https://img.shields.io/badge/arXiv-2608.29411-b31b1b.svg)](https://arxiv.org/abs/2608.29411)

Code, classical/OEIS results, and paper source for *Where Induction Runs Out:
Description-Length Difficulty and the Memorisation Gap in Integer-Sequence
Benchmarks.*

Author: Sabilashan Ganeshan (Independent Researcher),
<sabilashanganeshan@gmail.com>

We compute MDL revision spectra over P-recursive (holonomic) operators on a
labelled classical corpus and on OEIS draws, then stratify three language
models by those MDL regimes. Discovery is identification-limited on the
classical corpus; at OEIS scale a wilderness regime (prefix fit, no
full-length operator) dominates; models hedge in the wilderness and
confabulate on easy sequences mainly via recognition.

Paper versions: v1.0 (`10.5281/zenodo.21830332`) initial release; v1.1
(`10.5281/zenodo.22084529`) readability pass, notation table, worked example,
CITATION.cff DOI fix (see the Zenodo record for full notes). The concept DOI
`10.5281/zenodo.21830331` always resolves to the latest version.

## Headline numbers

Values below are read from the shipped `results/` files (not restated from
memory).

| Quantity | Value | Source |
|---|---|---|
| Classical structural revisers | 2 / 61 (A000578 cubes, A000330 square pyramidal) | `results/analysis.json` |
| Holonomic operator found (classical) | 46 / 61 | `results/analysis.json` |
| \(n_d = n_{\mathrm{id}}\) exact / within ±1 | 41/46 / 46/46 | `results/analysis.json` |
| MAE of \(n_{\mathrm{id}}\) / \(n_{\times}\) | 0.11 / 3.20 | `results/analysis.json` |
| corr(\(n_d\), \(L(H^*)\)) / growth | +0.85 / −0.007 | `results/analysis.json` |
| Unplanted deception (default encoding) | 21.8% (96/440) | `results/deception_random.csv` |
| Unplanted deception (`strict_leading=True`) | 14.3% (63/440) | `results/deception_random_strict.csv` |
| OEIS true-holonomic revisers (fixed 30-term) | 315 / 2780 (11.3%) | `results/holonomic_denominator_oeis_fixed30.json` ← `oeis_fixed30.csv` |
| OEIS length bins (mixed-length; different population) | 4.2 / 6.1 / 9.3 / 5.7 / 12.0% | `results/oeis_length_bins_holonomic.csv` ← `oeis_results.csv` |
| Wilderness split of 1887 | 1698 genuine / 29 truncation / 160 undetermined | `results/truncation_1887_summary.json` |
| Calibration (60-term attempt) | 1612 rows/h → 12.4 h / 20k | `results/oeis_60_calibration.json` |
| LLM calls / failures / temperature | 180 / 12 / 0 | `results/llm_summary.json` |
| LLM wilderness abstention | 64.7%–95.0% | `results/llm_summary.json` |

See `results/README.md` for the full artefact catalogue.

## Quick start

```bash
pip install -r requirements.txt
make clean && make all
python experiments/repro_gate.py
python experiments/audit_paper_numbers.py
```

Classical spectra, controls, deception, figures, and the PDF rebuild in a few
minutes on a laptop (no GPU). OEIS and LLM stages are separate (below).

## Scripts

| Path | Purpose |
|---|---|
| `revspec/core.py` | MDL codes, P-recursive guessing, revision spectrum |
| `revspec/corpus.py` | 61-sequence labelled classical corpus |
| `experiments/run_spectra.py` | Classical spectra → `results/spectra.json`, `features.csv`, `lcp.json` |
| `experiments/run_analysis.py` | \(n_d=\max(n_{\mathrm{id}},n_{\times})\) decomposition |
| `experiments/run_controls.py` | Growth and phase-boundary controls |
| `experiments/run_deception.py` | Planted / unplanted deceptive prefixes |
| `experiments/make_figures.py` | Classical figures and LaTeX tables |
| `experiments/make_clean.py` | `make clean` helper (classical artefacts only) |
| `experiments/run_oeis.py` | OEIS scale-up (`--resume`, `--shuffle`) |
| `experiments/run_oeis_calibration.py` | 500-seq timing calibration for 60-term budget |
| `experiments/run_truncation_1887.py` | Wilderness truncation audit |
| `experiments/run_ablation_encoding.py` | Loose vs strict encoding ablation |
| `experiments/run_llm_eval.py` | OpenRouter LLM eval (3 models × 60 sequences) |
| `experiments/make_llm_figure.py` | Figure 5 from `results/llm_summary.json` |
| `experiments/repro_gate.py` | Reproducibility gate against classical + cited artefacts |
| `experiments/audit_paper_numbers.py` | Trace every paper number to `results/` |
| `paper/` | LaTeX source, bibliography, figures, tables, PDF |

## Reproduce the OEIS runs

Download the OEIS dumps (`stripped.gz`, `names.gz`) from
https://oeis.org/ and place them next to the working directory (or pass paths):

```bash
python experiments/run_oeis.py --stripped stripped.gz --names names.gz \
    --limit 20000 --terms 30 --jobs 8 --resume --shuffle \
    --out results/oeis_fixed30.csv
```

The mixed-length extract shipped as `results/oeis_results.csv` used the same
pipeline with the database’s native term counts (not a fixed budget). Headline
315/2780 is from the fixed-30 population; length bins 4.2–12.0% are from the
mixed-length population — see `results/oeis_length_bins_holonomic.csv`.

A controlled sweep at a fixed **60-term** budget and a full-length config were
**not** completed: calibration on 500 sequences projects **12.4 hours per
configuration** for 20 000 sequences (`results/oeis_60_calibration.json`).
Partial outputs `results/oeis_60_strict.csv` and `results/oeis_full_strict.csv`
are retained and marked partial in `results/README.md`.

Wilderness truncation audit (after the mixed-length / fixed-30 CSVs exist):

```bash
python experiments/run_truncation_1887.py
```

True-holonomic denominators in this release are already computed under
`results/holonomic_denominator_*.json`.

## Reproduce the LLM evaluation

Requires an OpenRouter API key (~US$1 for the 180-call run):

```bash
# create a local .env (gitignored); never commit it
# OPENROUTER_API_KEY=...
python experiments/run_llm_eval.py
python experiments/make_llm_figure.py
```

Models: Claude Sonnet 4.5, GPT-4o, Llama 3.3 70B; temperature 0; one call per
(sequence, model). Precomputed responses are in `results/llm_eval.csv`.

## Classical corpus

61 sequences generated from definitions (never transcribed), truncated to 34
terms, labelled by ground-truth position in the holonomic hierarchy:

| Label | Meaning | n |
|---|---|---|
| `POLY` | polynomial closed form | 15 |
| `CFIN` | C-finite but not polynomial | 16 |
| `PREC` | holonomic but not C-finite | 15 |
| `NONH` | provably not holonomic | 15 |

## Known limitations

See paper §9 (`paper/main.tex`, label `sec:limitations`): term-budget /
abandoned 60-term runs, hand-labelled classical corpus, hypothesis-class
bounds (\(r\le 6\), \(d\le 4\)), encoding sensitivity
(`strict_leading`), and the small LLM sample (12/180 failed calls).

## Citation

Ganeshan, S. (2026). Where Induction Runs Out: Description-Length
Difficulty and the Memorisation Gap in Integer-Sequence Benchmarks.
Zenodo.

- Paper: https://doi.org/10.5281/zenodo.21830331
- Software: https://doi.org/10.5281/zenodo.21830532

```bibtex
@software{where_induction_runs_out,
  title = {Where Induction Runs Out: Description-Length Difficulty
           and the Memorisation Gap in Integer-Sequence Benchmarks},
  author = {Ganeshan, Sabilashan},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.21830331},
  url = {https://doi.org/10.5281/zenodo.21830331},
}
```

Also see `CITATION.cff` (CFF 1.2.0).

## Licenses

- Code (`revspec/`, `experiments/`, build files): MIT — `LICENSE`
- Paper (`paper/`): CC BY 4.0 — `LICENSE-PAPER`
- OEIS sequence data: CC BY-SA 4.0 (upstream)

## AI assistance

AI assistance (Claude, Cursor) was used for implementation, experiment
execution, and drafting. All experimental design decisions, verification of
results, and final claims are the author's.
