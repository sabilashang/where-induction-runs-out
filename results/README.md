# Results catalogue

For each artefact: one-line contents, generating script, paper section.
`present` refers to whether that script is in this release’s `experiments/`.

**Provenance note.** Headline OEIS rate 315/2780 (11.3%) is from the fixed
30-term population (`oeis_fixed30.csv`). Length bins 4.2–12.0% are from the
mixed-length population (`oeis_results.csv`) — a different run.

| Filename | Contents | Generating script | In release? | Cited in |
|---|---|---|---|---|
| `analysis.json` | Classical summary (exact, MAE, corrs, revisers, ANOVA) | `experiments/run_analysis.py` | yes | Abstract, §§4–5 |
| `features.csv` | Per-sequence classical features | `experiments/run_spectra.py` | yes | Tables / LCP |
| `spectra.json` | Full classical revision spectra | `experiments/run_spectra.py` | yes | Figs 2–3 |
| `lcp.json` | Literal-complexity profiles | `experiments/run_spectra.py` | yes | §LCP |
| `regimes.csv` | Classical regimes / \(n_d\) | `experiments/run_analysis.py` | yes | §5 |
| `control_growth.csv` | Fibonacci magnitude control | `experiments/run_controls.py` | yes | §6 |
| `control_phase.csv` | Alphabet × period control | `experiments/run_controls.py` | yes | §6 |
| `deception.csv` | Planted deceptive-prefix sweep | `experiments/run_deception.py` | yes | §7 / Fig. 4 |
| `deception_random.csv` | Unplanted deception, default encoding | `experiments/run_deception.py` | yes | §7, §9 |
| `deception_random_strict.csv` | Unplanted deception, `strict_leading=True` | `experiments/make_deception_random_strict.py` | yes | §9 |
| `deception_random_strict_summary.json` | Strict unplanted summary | `experiments/make_deception_random_strict.py` | yes | §9 (via CSV) |
| `ablation_encoding.csv` | Per-sequence loose vs strict | `experiments/run_ablation_encoding.py` | yes | §9 |
| `ablation_encoding_summary.json` | Ablation headlines | `experiments/run_ablation_encoding.py` | yes | §9 |
| `oeis_results.csv` | Mixed-length OEIS run (20k) | `experiments/run_oeis.py` | yes | §4 bins source |
| `oeis_fixed30.csv` | Fixed 30-term OEIS run (20k); headline population | `experiments/run_oeis.py --terms 30 --out results/oeis_fixed30.csv` | yes | Abstract, §§4–5, §9 |
| `oeis_random30.csv` | Random-30 OEIS draw | `experiments/run_oeis.py` | yes | denom contrast |
| `oeis_fixed30_strict.csv` | Fixed-30, `strict_leading=True` | `experiments/run_oeis.py` | yes | ablation |
| `oeis_fixed30_strict.csv.meta.json` | Run metadata sidecar | `experiments/run_oeis.py` | yes | supporting |
| `oeis_fixed30_strict.csv.header.txt` | Header dump | `experiments/run_oeis.py` | yes | supporting |
| `oeis_fixed30_loose.csv` | Fixed-30, `strict_leading=False` | `experiments/run_oeis.py` | yes | ablation |
| `oeis_fixed30_loose.csv.meta.json` | Run metadata sidecar | `experiments/run_oeis.py` | yes | supporting |
| `oeis_fixed30_loose.csv.header.txt` | Header dump | `experiments/run_oeis.py` | yes | supporting |
| `oeis_60_strict.csv` | **Partial** 60-term strict run (abandoned) | `experiments/run_oeis.py` (killed incomplete) | yes | §9 |
| `oeis_60_strict.log` | Log of partial 60-term run | `experiments/run_oeis.py` (stdout) | yes | §9 |
| `oeis_full_strict.csv` | **Partial** full-length strict run | `experiments/run_oeis.py` (killed incomplete) | yes | §9 |
| `holonomic_denominator_oeis_fixed30.json` | True-holonomic denom: **315/2780** | `experiments/recompute_holonomic_denominator.py` | yes | Abstract, §§4–5 |
| `holonomic_denominator_oeis_fixed30_*.csv` | Crosstabs / dists for fixed-30 | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_oeis_results.json` | True-holonomic denom on mixed-length | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_oeis_results_*.csv` | Crosstabs for mixed-length | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_oeis_random30.json` | True-holonomic denom on random-30 | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_oeis_random30_*.csv` | Crosstabs for random-30 | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_summary.json` | Combined denom summary | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `holonomic_denominator_run.log` | Denom recompute stdout log | `experiments/recompute_holonomic_denominator.py` | yes | supporting |
| `oeis_length_bins_holonomic.csv` | True-holonomic bins on **mixed-length** `oeis_results.csv` (different population from fixed-30 315/2780): 4.2 / 6.1 / 9.3 / 5.7 / 12.0% | `experiments/make_oeis_length_bins_holonomic.py` | yes | Abstract, §4 |
| `oeis_length_bins_holonomic_summary.json` | Provenance + weighted-mean sanity | `experiments/make_oeis_length_bins_holonomic.py` | yes | supporting |
| `truncation_1887.csv` | Per-sequence wilderness truncation classes | `experiments/run_truncation_1887.py` | yes | §wilderness |
| `truncation_1887_summary.json` | 29 / 1698 / 160 of 1887 | `experiments/run_truncation_1887.py` | yes | Abstract, §wilderness |
| `task4_1887_report.json` | Wrapper report for truncation task | `experiments/run_truncation_1887.py` (sidecar / companion write) | yes* | supporting |
| `task4_1887_run.log` | Truncation stdout log | `experiments/run_truncation_1887.py` | yes | supporting |
| `oeis_60_calibration.json` | 500-seq calib → 1612 rows/h, 12.4 h/20k | `experiments/run_oeis_calibration.py` | yes | §9 |
| `oeis_60_calibration_per_seq.csv` | Per-sequence calib timings | `experiments/run_oeis_calibration.py` | yes | §9 |
| `oeis_60_calibration.log` | Calibration stdout log | `experiments/run_oeis_calibration.py` | yes | §9 |
| `provenance.json` | OEIS dump SHA / spot checks | `experiments/verify_oeis_data.py` | yes | provenance |
| `limitations_facts.json` | Structured §9 facts | `experiments/build_limitations_facts.py` | yes | §9 |
| `manifest.json` | Claim / report manifest | `experiments/build_report_manifest.py` (+ `build_manifest_ab.py`) | yes | supporting |
| `llm_eval.csv` | Raw LLM responses (180 calls) | `experiments/run_llm_eval.py` | yes | §LLM / Fig. 5 |
| `llm_summary.json` | Aggregated LLM rates | `experiments/run_llm_eval.py` | yes | Abstract, §LLM |
| `llm_eval_run.log` | LLM eval stdout log (**not cited** in `main.tex`). Absolute local paths in two “WROTE” lines were normalised to relative `results/…` paths; no metrics were altered. | `experiments/run_llm_eval.py` | yes | supporting only |
| `llm_sample.json` | Stratified 60-sequence sample | `experiments/build_llm_sample.py` | yes | §LLM |
| `llm_sample.txt` | Sample A-number list | `experiments/build_llm_sample.py` | yes | §LLM |
| `profile_guess_prec_200.json` | guess_prec profile (after Task 2a) | `experiments/profile_guess_prec.py` | yes | §9 timing |

## Files without generators

These artefacts have no committed regenerator. They are retained on purpose; none were deleted.

**INPUTS, not outputs.** Fixed records of what was sampled or sent; regenerating them would change the experiment.

- `llm_prompt.txt`
- `list_1887.txt`
- `sample_anums_seed0.txt`

**DERIVED VIEWS.** Recomputable in seconds from the committed CSVs; kept for convenience.

- `oeis_summary.json`
- `oeis_fixed30_summary.json`
- `oeis_random30_summary.json`
- `oeis_fixed30_struct_rev_counts.csv`
- `oeis_fixed30_rev_by_params.csv`
- `oeis_fixed30_result2_by_revises.csv`
- `oeis_fixed30_result2_crosstab.csv`
- `task4_1887_report.json` (companion wrap of `truncation_1887_*.csv/json`)

**HARDWARE MEASUREMENTS.** Timing figures specific to the machine used; not reproducible by design and cited as such in §9.

- `oeis_60_timing.json`
- `task1_profile_report.json`
- `task2_optimization_report.json`
- `profile_guess_prec_200_baseline.json`
- `profile_speedup_task2a.json`

**SUPERSEDED, retained for the audit trail.** Replaced by corrected versions; kept so the correction is visible rather than hidden.

- `oeis_length_bins.csv` (replaced by `oeis_length_bins_holonomic.csv`)
- `regimes_pre_task2.csv` (replaced by current `regimes.csv` after Task-2 core changes)

No file in this release exceeds 50 MB.
