# cti_biases — Reviewer README

## Purpose of this repository

This repository is the reproducibility package for the CTI valuation / cognitive-bias study.
It contains the raw LimeSurvey exports, the Prolific demographic exports, the cleaned analytic dataset,
and the Python scripts that recreate the analysis tables, figures, and text report used for the paper.

At a high level, the repository answers four reviewer questions:

1. What are the raw input files?
2. How are the raw files merged and cleaned?
3. How are the paper statistics and plots produced?
4. Which repository outputs correspond directly to statements in the paper?

---

## Repository contents

### Raw survey exports

- `results-survey329854.csv`  
  Raw LimeSurvey export for the **buyer** study.

- `results-survey562856.csv`  
  Raw LimeSurvey export for the **seller** study.

These files contain the original response rows, including:
- screening-question answers,
- condition/group assignment,
- MPL choices across token prices,
- free-text reservation prices,
- confidence responses,
- timing metadata,
- Prolific participant IDs.

### Raw Prolific exports

- `prolific_export_6942b370903f99bfdc35f0cc.csv`
- `prolific_export_6985e4cb6d6373b8a28ac3ce.csv`
- `prolific_export_698c772a8678f5a688e79ca3.csv`
- `prolific_export_698c7acd313fdcb85539ffde.csv`
- `prolific_export_69bbc4e1dd803bdd5d678245.csv`
- `prolific_export_69bbc57cf460a21a043af931.csv`

These are the Prolific batch exports used to append participant metadata and demographics to the survey data.
Relevant fields include age, sex, language, employment status, and current job role.

### Survey-structure / archival JSON files

- `329854.json`
- `562856.json`

These JSON files contain exported response payloads for the two LimeSurvey studies.
They are useful for audit and archival inspection because they preserve the raw question text,
response schema, and the original row structure outside the CSV format.

### Derived analytic dataset

- `cti_valuation_clean.csv`

This is the main cleaned dataset produced by `merge_and_clean.py`.
Each row is one completed LimeSurvey submission that was mapped to a study role and condition and enriched with derived analysis variables.

Important derived columns include:
- `role` — buyer / seller
- `condition` — baseline / anchor
- `cell` — buyer_baseline / buyer_anchor / seller_baseline / seller_anchor
- `valuation` — extracted WTP/WTA reservation price in tokens
- `free_text_price` — entered corner/cap value, if any
- `used_free_text_price` — whether the free-text value became the analytic valuation
- `switches` — number of directional switches in the MPL
- `screening_score` — number of correct screening answers
- `screening_pass` — screening score >= 3
- `is_monotone` — MPL monotonicity flag (`switches <= 1`)
- `per_protocol` — final analysis inclusion flag (`screening_pass & is_monotone`)
- demographic columns merged from Prolific
- `profession` — coarse profession class derived from the job-role field
- `is_corner_low`, `is_corner_high` — low/high corner indicators

### Analysis outputs

- `table_cellmeans.csv`  
  Sensitivity-sample descriptive cell statistics used for the paper tables/text.

- `table_regression.csv`  
  Sensitivity-sample OLS coefficients with HC1 robust standard errors.

- `table_anchor_decomp.csv`  
  Role-specific anchor-shift decomposition (buyers vs. sellers).

- `fig_boxplot_main.png`  
  Four-cell boxplot for buyer/seller x no-anchor/anchor.

- `fig_boxplot_anchor_shift.png`  
  Two-panel buyer vs. seller anchor-shift figure.

- `fig_gap_decomposition.png`  
  Gap-decomposition bar chart (baseline gap, buyer shift, seller shift, residual gap).

- `REPORT.txt`  
  Auto-generated narrative analysis log with the main test results, Cook's-distance diagnostic,
  sensitivity analysis, and summary statements.

### Existing repository README

- `README.md`

This file is currently minimal and only states the repository name and a one-line description.
It does not document the workflow or file roles in a reviewer-friendly way.

---

## End-to-end workflow

The repository follows this pipeline:

1. **Start from raw survey exports** (`results-survey*.csv`) and raw Prolific exports (`prolific_export_*.csv`).
2. **Run `merge_and_clean.py`** to:
   - identify buyer vs. seller rows,
   - map survey groups to baseline vs. anchor,
   - score the 4-item CTI screening,
   - extract MPL reservation prices,
   - retain corner solutions,
   - compute monotonicity,
   - set the per-protocol flag,
   - merge Prolific demographics,
   - write `cti_valuation_clean.csv`.
3. **Run `analyze_results.py`** on `cti_valuation_clean.csv` to:
   - reproduce the main confirmatory H1/H2 results,
   - identify the influential 999,999-token protest response,
   - run the sensitivity analysis without that one response,
   - export tables, figures, and `REPORT.txt`.

In short:

`raw survey + raw Prolific -> merge_and_clean.py -> cti_valuation_clean.csv -> analyze_results.py -> tables/figures/REPORT.txt`

---

## What the two Python scripts do

## `merge_and_clean.py`

This script is the data-preparation step.

### Inputs
- `results-survey329854.csv`
- `results-survey562856.csv`
- all files matching `prolific_export_*.csv`

### Core logic

It does the following:

1. Loads buyer and seller survey CSVs.
2. Loads and concatenates all Prolific export CSVs.
3. Computes the 4-item CTI screening score.
4. Maps survey groups to experimental conditions:
   - buyer group 3 -> baseline
   - buyer group 4 -> anchor
   - seller group 1 -> baseline
   - seller group 2 -> anchor
5. Extracts the MPL reservation price:
   - buyers: last "I will buy" point,
   - sellers: first "I will sell" point.
6. Handles corner solutions:
   - buyer monotone "never buy" with no free-text follow-up -> valuation `0`
   - seller with no switch and no qualifying free-text above the MPL ceiling -> valuation `22,000`
   - free-text values at or above the MPL upper bound are retained as entered
7. Computes data-quality indicators:
   - `screening_pass`
   - `is_monotone`
   - `per_protocol`
8. Merges Prolific demographics.
9. Writes `cti_valuation_clean.csv`.

### Output
- `cti_valuation_clean.csv`

### Why this matters for reviewers

This is the script to inspect if you want to verify:
- which participants are excluded,
- how WTP/WTA values are extracted,
- how corner cases are handled,
- how raw survey records become the analytic dataset.

---

## `analyze_results.py`

This script is the analysis and output-generation step.

### Input
- `cti_valuation_clean.csv`

### Core logic

It does the following:

1. Restricts the primary analysis to `per_protocol == True`.
2. Runs the pre-registered H1 test:
   - Mann-Whitney U (one-sided) for seller baseline WTA > buyer baseline WTP.
3. Runs the H2 regression:
   - OLS with HC1 robust standard errors for role, anchor, and interaction.
4. Computes Cook's distance for the full per-protocol sample.
5. Flags the single 999,999-token seller-anchor response as influential.
6. Runs a sensitivity analysis excluding that single protest response.
7. Exports:
   - descriptive cell table,
   - regression table,
   - anchor decomposition table,
   - three figures,
   - narrative `REPORT.txt`.

### Outputs and their meaning

#### `REPORT.txt`
Human-readable audit log of the analysis. Contains:
- total completed and per-protocol counts,
- H1 and H2 outputs,
- Cook's-distance ranking,
- sensitivity-analysis results,
- anchor decomposition,
- seller-variance compression,
- concise interpretive summary.

#### `table_cellmeans.csv`
Sensitivity-sample descriptive statistics by experimental cell.
Useful for checking the numbers shown in the paper's descriptive table.

#### `table_regression.csv`
Sensitivity-sample regression table with coefficient estimates and HC1 SEs.
Useful for checking the interaction result and the paper's Table 2.

#### `table_anchor_decomp.csv`
Role-specific anchor shifts.
Useful for checking the exploratory asymmetry claim that buyers move strongly and sellers barely move.

#### `fig_boxplot_main.png`
All four cells in one figure.
Useful for seeing the full buyer/seller x anchor/no-anchor distribution at once.

#### `fig_boxplot_anchor_shift.png`
The clearest figure for the paper's asymmetric-susceptibility claim.
Shows the anchor shift separately for buyers and sellers.

#### `fig_gap_decomposition.png`
A compact visualization of how the baseline gap is reduced by buyer and seller shifts.
Useful for checking the "67% reduction" decomposition.

---

## Reproducing the outputs

Run from the repository root:

```bash
python merge_and_clean.py
python analyze_results.py
```

Expected headline outputs after successful execution:
- `cti_valuation_clean.csv`
- `table_cellmeans.csv`
- `table_regression.csv`
- `table_anchor_decomp.csv`
- `fig_boxplot_main.png`
- `fig_boxplot_anchor_shift.png`
- `fig_gap_decomposition.png`
- `REPORT.txt`

The scripts ran successfully in local re-execution with no code changes.

---

## Key reproduced results

From a clean local run of the repository scripts:

- total completed in the merged analytic dataset: **289**
- per-protocol sample: **233**
- baseline buyer mean WTP: **8,774**
- baseline seller mean WTA: **12,633**
- baseline gap: **3,859**
- WTA/WTP ratio: **1.44**
- Mann-Whitney U for H1: **U = 2401, p = 0.0028**
- sensitivity interaction term: **beta = -2,577, p = 0.1619**
- gap reduction under anchor: **67%**
- buyer shift: **+2,833**
- seller shift: **+256**
- seller-anchor protest response excluded only in sensitivity analysis: **999,999 tokens**

These values reproduce the repository tables and report exactly.

---

## What corresponds to the paper

### Directly aligned with the paper PDF

- `table_cellmeans.csv` -> paper Table 1 values
- `table_regression.csv` -> paper Table 2 values
- `fig_boxplot_anchor_shift.png` -> same underlying statistics as paper Figure 1
- `REPORT.txt` -> contains the same core numerical results cited in the Results/Discussion sections

### Present in the repository but not directly shown as standalone items in the PDF

- `table_anchor_decomp.csv`
- `fig_boxplot_main.png`
- `fig_gap_decomposition.png`

These are helpful reproducibility outputs, but they are not all included as standalone tables/figures in the submitted PDF.

---

## Practical reviewer guidance

If you want the fastest verification path:

1. Open `cti_valuation_clean.csv` and confirm the `per_protocol` counts by cell.
2. Run `python analyze_results.py`.
3. Compare the resulting:
   - `table_cellmeans.csv`
   - `table_regression.csv`
   - `REPORT.txt`
   against the paper's Results section.
4. Open `fig_boxplot_anchor_shift.png` to verify the anchor-shift asymmetry visually.

If you want the data provenance path:

1. Inspect `results-survey329854.csv` and `results-survey562856.csv`.
2. Inspect `merge_and_clean.py`.
3. Confirm how exclusion, corner handling, and valuation extraction work.

---

## Known caveats worth noticing

- The repository `README.md` is currently too sparse for external review and should be replaced by a fuller document such as this one.
- `analyze_results.py` uses a **10 x (4/n)** Cook's-distance rule for the sensitivity exclusion, while part of the script docstring mentions `Cook's D > 4/n`. The implemented code is the authoritative behavior.
- The methodology text in the paper mentions `eta^2_p` for H2, but the analysis script does not compute or export that effect size.
- The paper PDF and repository are numerically aligned on the main sensitivity results, but not every repository figure is embedded in the PDF.

