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
