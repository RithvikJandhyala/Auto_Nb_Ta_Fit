# Automated Nb 3d / Ta 4f XPS Fitting App

This Streamlit app provides one common frontend for two independent scientific fitting workflows:

- **Niobium (Nb 3d)** using `Nb_fitting_notebook.ipynb`
- **Tantalum (Ta 4f)** using `Ta_fitting_notebook.ipynb`

The app asks you to choose the element first. After that, the workflow is intentionally the same for both elements: upload one `.xy` spectrum, run the automated fit, review the Shirley background / final fit / residual plots, inspect fitted tables and uncertainties, and download CSV or ZIP results.

## Install

Open Terminal in this folder and run:

```bash
python -m pip install -r requirements.txt
```

## Start the app

```bash
streamlit run app.py
```

Or on macOS, double-click `run_app.command`.

A browser window should open at `http://localhost:8501`.

## Workflow

1. Select **Niobium (Nb)** or **Tantalum (Ta)**.
2. Upload one matching `.xy` file.
3. Click the automated-fit button.
4. Review plots and tables.
5. Download a fitted-results CSV or a ZIP containing every table and PNG figure.

## Scientific models

The interface is shared, but the fitting models remain element-specific.

### Niobium
The Nb workflow executes the scientific core from `Nb_fitting_notebook.ipynb` and fits the Nb 3d region.

### Tantalum
The Ta workflow executes the scientific core from `Ta_fitting_notebook.ipynb` and fits the Ta 4f region, including Ta metal, Ta2O5, TaOx, and O 2s components.

The Ta final-fit plots use the same component color order and visual style as Nb.

## Important

Keep these files together in the same folder:

- `app.py`
- `xps_pipeline.py`
- `Nb_fitting_notebook.ipynb`
- `Ta_fitting_notebook.ipynb`

The pipeline executes selected cells from the notebooks so the web interface remains tied to the scientific fitting logic. If you insert, remove, or reorder fitting cells in either notebook, verify the `execution_cells` values in `ELEMENT_CONFIG` inside `xps_pipeline.py`.

## Files

- `app.py` — Streamlit frontend
- `xps_pipeline.py` — shared element-aware pipeline
- `Nb_fitting_notebook.ipynb` — Nb scientific fitting source
- `Ta_fitting_notebook.ipynb` — Ta scientific fitting source
- `requirements.txt` — Python dependencies
- `run_app.command` — macOS launcher

# XPS Peak Fitting Constraints & Physical Priors

This document summarizes the physical constraints and empirical priors used by the automated **Niobium (Nb 3d)** and **Tantalum (Ta 4f)** XPS fitting workflows.

---

# Niobium (Nb 3d)

## Doublet Constraints

| Parameter | Value |
|-----------|-------|
| Spin-orbit separation | **2.72 eV** |
| Area ratio (3d5/2 : 3d3/2) | **3 : 2** |

## Species Constraints

### Nb Metal
- Position: **202.20 eV**
- Line shape: **LA(1.2,5,12)**

### NbO
- Position: **203.70 eV**
- Line shape: **GL**

### NbO₂
- Position: **206.20 eV**
- Line shape: **GL**

### Nb₂O₅
- Position: **207.40 eV**
- Line shape: **GL**

## Position Priors

| Species | Center | Prior Width |
|----------|-------:|------------:|
| Nb metal | **202.20 eV** | ±0.30 eV |
| NbO | **203.70 eV** | ±1.00 eV |
| NbO₂ | **206.20 eV** | ±1.00 eV |
| Nb₂O₅ | **207.40 eV** | ±0.40 eV |

These Gaussian priors are derived from the literature values used for the fitting routine.

## Average Composition Prior

| Species | Average Fraction |
|----------|----------------:|
| Nb metal | **14.454%** |
| NbO | **2.357%** |
| NbO₂ | **3.829%** |
| Nb₂O₅ | **79.360%** |

These are soft priors used only to guide optimization.

## Metal FWHM Calibration

Calibration factor:

```text
0.471353
```

Applied only when reporting the final metal FWHM:

```text
FWHM_corrected = FWHM_fit × 0.471353
```

The calibration is **not** used during optimization.

---

# Tantalum (Ta 4f)

## Doublet Constraints

| Parameter | Value |
|-----------|-------|
| Spin-orbit separation | **1.91 eV** |
| Area ratio (4f7/2 : 4f5/2) | **4 : 3** |

## Species Constraints

### Ta Metal

| Property | Value |
|----------|-------|
| Position | **21.60 eV** |
| Line shape | **LA(1.1,7,25)** |
| FWHM | **< 0.70 eV** |

### Ta₂O₅

| Property | Value |
|----------|-------|
| Position | **26.70 eV** |
| Position prior | ±0.30 eV |
| Line shape | **GL(30)** |
| FWHM | **< 1.20 eV** |

### TaOx

| Property | Value |
|----------|-------|
| Position | **23.40 eV** |
| Position prior | ±0.30 eV |
| Line shape | **GL(30)** |
| FWHM | **Locked to Ta₂O₅ FWHM** |

### O 2s

| Property | Value |
|----------|-------|
| Position | **24.00 eV** |
| Position prior | ±1.00 eV |
| Line shape | **GL(30)** |
| FWHM | **2.5–5.0 eV** |

## Position Priors

| Species | Center | Prior Width |
|----------|-------:|------------:|
| Ta metal | **21.60 eV** | Reference (post-shift) |
| Ta₂O₅ | **26.70 eV** | ±0.30 eV |
| TaOx | **23.40 eV** | ±0.30 eV |
| O 2s | **24.00 eV** | ±1.00 eV |

## Average Composition Prior

| Species | Average Fraction |
|----------|----------------:|
| Ta metal | **46.48%** |
| Ta₂O₅ | **46.24%** |
| TaOx | **3.09%** |
| O 2s | **4.19%** |

These are soft priors used only to guide optimization.

## Metal FWHM Calibration

Calibration factor:

```text
0.762
```

Applied only when reporting the final metal FWHM:

```text
FWHM_corrected = FWHM_fit × 0.762
```

The calibration is **not** used during optimization.

---

# Common Workflow

1. Adaptive Shirley background (automatic endpoint detection)
2. Simultaneous constrained optimization
3. Automatic post-fit energy calibration
4. Multi-start optimization
5. Soft physical priors (positions, composition, FWHMs, baseline)
6. Output: uncertainties, residual analysis, reduced χ², calibrated peak tables

