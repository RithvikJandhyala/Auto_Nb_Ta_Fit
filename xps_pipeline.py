from __future__ import annotations

from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Callable
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import numpy as np
import pandas as pd
from scipy.integrate import simpson
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.special import voigt_profile


ELEMENT_CONFIG = {
    "Nb": {
        "name": "Niobium",
        "orbital": "Nb 3d",
        "notebook": "Nb_fitting_notebook.ipynb",
        "execution_cells": (4, 5, 6, 9, 10, 11, 12, 13, 15, 16, 18),
        "xlim": (214, 200),
        "plot_labels": ["Nb metal", "NbO", r"NbO$_2$", r"Nb$_2$O$_5$"],
    },
    "Ta": {
        "name": "Tantalum",
        "orbital": "Ta 4f",
        "notebook": "Ta_fitting_notebook.ipynb",
        "execution_cells": (3, 4, 5, 9, 10, 11, 12, 13, 15, 16, 18),
        "xlim": (31, 20),
        "plot_labels": ["Ta metal", r"Ta$_2$O$_5$", r"TaO$_x$", "O 2s"],
    },
}

ProgressCallback = Callable[[float, str], None]


def get_element_config(element: str) -> dict[str, Any]:
    try:
        return ELEMENT_CONFIG[element]
    except KeyError as exc:
        raise ValueError("Element must be 'Nb' or 'Ta'.") from exc


class ProgressCapture:
    """Capture notebook stdout and forward optimizer milestones to the UI."""

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        element: str = "Nb",
    ):
        self._buffer = StringIO()
        self._line_buffer = ""
        self._progress_callback = progress_callback
        self._refinement_total = 5
        self._element = element

    def _emit(self, fraction: float, message: str) -> None:
        if self._progress_callback is not None:
            self._progress_callback(float(np.clip(fraction, 0.0, 1.0)), message)

    def _parse_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        match = re.search(
            r"Beginning\s+coarse\s+fitting\s+of\s+(\d+)\s+starts",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            total = int(match.group(1))
            self._emit(0.15, f"Multistart optimization: 0/{total} starts completed")
            return

        match = re.search(
            r"Completed\s+(\d+)\s+of\s+(\d+)\s+starts",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            completed = int(match.group(1))
            total = max(int(match.group(2)), 1)
            fraction = 0.15 + 0.65 * (completed / total)
            self._emit(
                fraction,
                f"Multistart optimization: {completed}/{total} starts completed",
            )
            return

        match = re.search(
            r"Refining\s+the\s+best\s+(\d+)\s+solutions",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            self._refinement_total = max(int(match.group(1)), 1)
            self._emit(
                0.80,
                f"Refining best solutions: 0/{self._refinement_total} completed",
            )
            return

        match = re.search(r"Refinement\s+(\d+)\s*:", line, flags=re.IGNORECASE)
        if match:
            completed = int(match.group(1))
            total = max(self._refinement_total, 1)
            fraction = 0.80 + 0.15 * min(completed / total, 1.0)
            self._emit(
                fraction,
                f"Refining best solutions: {completed}/{total} completed",
            )
            return

        if "FINAL MULTI-START RESULTS" in line.upper():
            self._emit(0.95, "Optimization complete. Building plots and tables...")

    def write(self, text: str) -> int:
        self._buffer.write(text)
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            self._parse_line(line)
        return len(text)

    def flush(self) -> None:
        if self._line_buffer.strip():
            self._parse_line(self._line_buffer)
            self._line_buffer = ""

    def getvalue(self) -> str:
        return self._buffer.getvalue()


def read_xy_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read a SPECS-style .xy export entirely in memory."""
    if Path(filename).suffix.lower() != ".xy":
        raise ValueError("Please upload exactly one .xy file.")

    text = file_bytes.decode("utf-8", errors="ignore")
    rows: list[tuple[float, float]] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        columns = stripped.replace(",", " ").split()
        if len(columns) < 2:
            continue

        try:
            energy = float(columns[0])
            intensity = float(columns[1])
        except ValueError:
            continue

        if np.isfinite(energy) and np.isfinite(intensity):
            rows.append((energy, intensity))

    if not rows:
        raise ValueError(
            "No valid spectrum rows were found. Expected at least two numeric "
            "columns after the # metadata section."
        )

    df = pd.DataFrame(rows, columns=["Binding Energy (eV)", "Intensity"])
    if df["Binding Energy (eV)"].duplicated().any():
        df = df.groupby("Binding Energy (eV)", as_index=False)["Intensity"].mean()
    return df


def _execute_notebook_core(
    df: pd.DataFrame,
    filename: str,
    element: str,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], str]:
    """Execute the scientific core from the selected element notebook."""
    cfg = get_element_config(element)
    notebook_path = Path(__file__).with_name(cfg["notebook"])
    notebook = nbformat.read(notebook_path, as_version=4)

    x_original = df["Binding Energy (eV)"].to_numpy(dtype=float)
    y_original = df["Intensity"].to_numpy(dtype=float)

    namespace: dict[str, Any] = {
        "np": np,
        "pd": pd,
        "plt": plt,
        "Path": Path,
        "least_squares": least_squares,
        "gaussian_filter1d": gaussian_filter1d,
        "simpson": simpson,
        "PchipInterpolator": PchipInterpolator,
        "voigt_profile": voigt_profile,
        "display": lambda *args, **kwargs: None,
        "x_original": x_original,
        "y_original": y_original,
        "base_name": Path(filename).stem,
    }

    if progress_callback is not None:
        progress_callback(0.05, f"Reading spectrum and preparing {cfg['orbital']} analysis...")

    captured = ProgressCapture(progress_callback=progress_callback, element=element)

    with redirect_stdout(captured):
        for cell_number, cell_index in enumerate(cfg["execution_cells"], start=1):
            if progress_callback is not None:
                if cell_number == 2:
                    progress_callback(0.08, "Calculating adaptive Shirley background...")
                elif cell_number == 5:
                    progress_callback(0.11, f"Preparing {cfg['orbital']} peak model and constraints...")
                elif cell_number == 8:
                    progress_callback(0.14, "Preparing multistart optimization...")

            source = notebook.cells[cell_index].source
            exec(
                compile(
                    source,
                    f"{cfg['notebook']}:cell_{cell_index}",
                    "exec",
                ),
                namespace,
            )

    captured.flush()
    return namespace, captured.getvalue()


def _create_shirley_figure(ns: dict[str, Any], element: str):
    cfg = get_element_config(element)
    x_original = np.asarray(ns["x_original"], dtype=float)
    y_original = np.asarray(ns["y_original"], dtype=float)
    shirley = np.asarray(ns["shirley"], dtype=float)

    background_subtracted = y_original - shirley
    shirley_min = ns["SHIRLEY_MIN_BE"]
    shirley_max = ns["SHIRLEY_MAX_BE"]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(x_original, y_original, color="tab:blue", lw=1.8, label="Raw data", zorder=3)
    ax.plot(
        x_original, shirley, "--", color="tab:orange", lw=2.2,
        label="Adaptive Shirley background (pre-shift)", zorder=2,
    )
    ax.plot(
        x_original, background_subtracted, color="tab:green", lw=1.8,
        label="Shirley-subtracted spectrum", zorder=1,
    )

    ax.axvline(
        shirley_min, color="gray", linestyle="--", linewidth=1.5,
        label="Adaptive Shirley window",
    )
    ax.axvline(shirley_max, color="gray", linestyle="--", linewidth=1.5)
    ax.axvspan(shirley_min, shirley_max, color="gray", alpha=0.08, zorder=0)

    y_top = np.nanmax(y_original)
    ax.text(
        shirley_min, 0.97 * y_top, f"{shirley_min:.2f} eV",
        rotation=90, va="top", ha="right", fontsize=9, color="gray",
    )
    ax.text(
        shirley_max, 0.97 * y_top, f"{shirley_max:.2f} eV",
        rotation=90, va="top", ha="left", fontsize=9, color="gray",
    )

    ax.set_title(f"{ns['base_name']}: Adaptive Shirley Background Pre-Shift")
    ax.set_xlabel("Binding Energy (eV)")
    ax.set_ylabel("Intensity (counts/sec)")
    ax.set_xlim(*cfg["xlim"])
    ax.grid(alpha=0.15)
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    return fig


def _create_fit_figure(ns: dict[str, Any], element: str):
    cfg = get_element_config(element)
    x = ns["x"]
    popt = ns["popt"]
    x_shifted = ns["x_shifted"]
    energy_shift = ns["energy_shift"]

    model_at_x = ns["total_model"](x, popt)
    component_curves = list(ns["component_curves"](x, popt))

    valid_bg = np.isfinite(ns["shirley"])
    bg_order = np.argsort(ns["x_original"][valid_bg])
    shirley_at_x = np.interp(
        x,
        ns["x_original"][valid_bg][bg_order],
        ns["shirley"][valid_bg][bg_order],
    )
    raw_x_shifted = ns["x_original"] + energy_shift

    component_bg = [curve + shirley_at_x for curve in component_curves]
    total_fit_bg = model_at_x + shirley_at_x

    # Identical palette/order for Nb and Ta.
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]
    labels = cfg["plot_labels"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 12), sharex=True)

    ax1.plot(
        raw_x_shifted, ns["y_original"], color="black", lw=1.5,
        label="Raw data", zorder=10,
    )
    ax1.plot(
        raw_x_shifted, ns["shirley"], "--", color="gray", lw=2,
        label="Shirley background",
    )
    for curve_bg, color, label in zip(component_bg, colors, labels):
        ax1.fill_between(
            x_shifted, shirley_at_x, curve_bg,
            color=color, alpha=0.35, label=label,
        )
        ax1.plot(x_shifted, curve_bg, color=color, lw=1)

    ax1.plot(x_shifted, total_fit_bg, color="red", lw=2.5, label="Total fit")
    ax1.set_title(f'{ns["base_name"]}: Raw Spectrum with Shirley Background Post-Shift')
    ax1.set_ylabel("Intensity (counts/sec)")
    ax1.set_xlabel("Binding Energy (eV)")
    ax1.tick_params(axis="x", labelbottom=True)
    ax1.legend(frameon=False, ncol=2)

    ax2.plot(
        x_shifted, ns["y"], "ko", markersize=3,
        label="Shirley-corrected data",
    )
    for curve, color, label in zip(component_curves, colors, labels):
        ax2.fill_between(
            x_shifted, 0, curve, color=color, alpha=0.35, label=label,
        )
        ax2.plot(x_shifted, curve, color=color, lw=1)

    ax2.plot(x_shifted, model_at_x, color="red", lw=2.5, label="Total fit")
    ax2.set_title(f'{ns["base_name"]}: Shirley-Corrected Simultaneous Fit Post-Shift')
    ax2.set_xlabel("Binding Energy (eV)")
    ax2.set_ylabel("Intensity (counts/sec)")
    ax2.legend(frameon=False, ncol=2)

    ax1.set_xlim(*cfg["xlim"])
    fig.tight_layout()
    return fig


def _create_residual_figure(ns: dict[str, Any], element: str):
    cfg = get_element_config(element)
    residuals = ns["y"] - ns["total_model"](ns["x"], ns["popt"])
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axhline(0.0, color="black", linestyle="--", linewidth=1)
    ax.plot(ns["x_shifted"], residuals, linewidth=1.3)
    ax.set_xlabel("Binding Energy (eV)")
    ax.set_ylabel("Residual")
    ax.set_title(f'{ns["base_name"]}: Fit Residuals')
    ax.set_xlim(*cfg["xlim"])
    fig.tight_layout()
    return fig, residuals


def _parameter_uncertainties(ns: dict[str, Any]) -> np.ndarray:
    best_result = ns["best_result"]
    jacobian = best_result.jac
    degrees_of_freedom = max(len(ns["y"]) - len(ns["popt"]), 1)
    try:
        covariance = np.linalg.pinv(jacobian.T @ jacobian)
        covariance *= 2.0 * best_result.cost / degrees_of_freedom
        return np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    except np.linalg.LinAlgError:
        return np.full_like(ns["popt"], np.nan, dtype=float)


def _build_tables(
    ns: dict[str, Any],
    residuals: np.ndarray,
    element: str,
) -> dict[str, pd.DataFrame]:
    component_names = list(ns["component_names"])
    fitted_areas = np.asarray(ns["fitted_areas"], dtype=float)
    shifted_centers = np.asarray(ns["shifted_centers"], dtype=float)
    unshifted_centers = np.asarray(ns["unshifted_centers"], dtype=float)
    reported_fwhms = np.asarray(ns["reported_fwhms"], dtype=float)

    shift_table = pd.DataFrame({
        "Species": component_names,
        "Unshifted position (eV)": unshifted_centers,
        "Shifted position (eV)": shifted_centers,
        "FWHM (eV)": reported_fwhms,
    })

    dense_components = ns["component_curves"](ns["AREA_GRID"], ns["popt"])
    simpson_areas = np.array([
        abs(simpson(curve, x=ns["AREA_GRID"]))
        for curve in dense_components
    ])

    area_table = pd.DataFrame({
        "Component": component_names,
        "Fitted area": fitted_areas,
        "Simpson verification area": simpson_areas,
        "Difference": simpson_areas - fitted_areas,
        "% of fitted total": 100.0 * fitted_areas / fitted_areas.sum(),
    })

    parameter_std = _parameter_uncertainties(ns)
    area_indices = np.asarray(ns["area_indices"], dtype=int)
    center_indices = np.asarray(ns["center_indices"], dtype=int)

    if element == "Nb":
        metal_fwhm_std = parameter_std[2] * ns["METAL_FWHM_CALIBRATION"]
        oxide_fwhm_std = parameter_std[3]
        fwhm_std = [
            metal_fwhm_std,
            oxide_fwhm_std,
            oxide_fwhm_std,
            oxide_fwhm_std,
        ]
    else:
        metal_fwhm_std = parameter_std[2] * ns["TA_METAL_FWHM_CALIBRATION"]
        oxide_fwhm_std = parameter_std[3]
        o2s_fwhm_std = parameter_std[10]
        fwhm_std = [
            metal_fwhm_std,
            oxide_fwhm_std,
            oxide_fwhm_std,
            o2s_fwhm_std,
        ]

    uncertainty_table = pd.DataFrame({
        "Component": component_names,
        "Area": fitted_areas,
        "Area 1-sigma": parameter_std[area_indices],
        "Shifted position (eV)": shifted_centers,
        "Position 1-sigma (eV)": parameter_std[center_indices],
        "FWHM (eV)": reported_fwhms,
        "FWHM 1-sigma (eV)": fwhm_std,
    })

    parameter_total = float(fitted_areas.sum())
    simpson_total = float(simpson_areas.sum())
    total_area_table = pd.DataFrame({
        "Measurement": ["Total fitted area", "Total Simpson area", "Difference"],
        "Value": [parameter_total, simpson_total, simpson_total - parameter_total],
    })

    gaussian_percent, lorentzian_percent = _line_shape_percentages(ns, element)

    diagnostics_rows = [
        ("Selected element", get_element_config(element)["name"]),
        ("Core level", get_element_config(element)["orbital"]),
        ("Applied energy shift (eV)", ns["energy_shift"]),
        ("Residual standard deviation", np.std(residuals, ddof=1)),
        ("Gaussian contribution (%)", gaussian_percent),
        ("Lorentzian contribution (%)", lorentzian_percent),
        ("Successful coarse starts", len(ns["coarse_candidates"])),
    ]

    if element == "Ta":
        diagnostics_rows.extend([
            ("Residual baseline offset", ns.get("baseline_offset", np.nan)),
            ("Residual baseline slope", ns.get("baseline_slope", np.nan)),
        ])

    diagnostics_table = pd.DataFrame(diagnostics_rows, columns=["Metric", "Value"])

    return {
        "shift_table": shift_table,
        "area_table": area_table,
        "uncertainty_table": uncertainty_table,
        "total_area_table": total_area_table,
        "diagnostics_table": diagnostics_table,
    }


def _line_shape_percentages(ns: dict[str, Any], element: str) -> tuple[float, float]:
    if element == "Nb":
        eta = float(ns["shared_oxide_eta"])
        return (1.0 - eta) * 100.0, eta * 100.0

    # Ta notebook uses a fixed GL(30)-style 70% Gaussian / 30% Lorentzian mix
    # for Ta2O5, TaOx and O 2s.
    return 70.0, 30.0


def figure_to_png_bytes(fig) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=220, bbox_inches="tight")
    buffer.seek(0)
    return buffer.getvalue()


def analyze_xy_file(
    file_bytes: bytes,
    filename: str,
    element: str = "Nb",
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run the complete selected-element workflow and return UI-ready results."""
    cfg = get_element_config(element)

    if progress_callback is not None:
        progress_callback(0.02, "Reading uploaded .xy file...")

    df = read_xy_bytes(file_bytes, filename)
    ns, log = _execute_notebook_core(
        df,
        filename,
        element,
        progress_callback=progress_callback,
    )

    if progress_callback is not None:
        progress_callback(0.96, "Creating Shirley-background figure...")
    shirley_figure = _create_shirley_figure(ns, element)

    if progress_callback is not None:
        progress_callback(0.97, "Creating final fit figure...")
    fit_figure = _create_fit_figure(ns, element)

    if progress_callback is not None:
        progress_callback(0.98, "Calculating residuals and uncertainty tables...")
    residual_figure, residuals = _create_residual_figure(ns, element)
    tables = _build_tables(ns, residuals, element)

    gaussian_percent, lorentzian_percent = _line_shape_percentages(ns, element)

    if progress_callback is not None:
        progress_callback(1.0, "Analysis complete")

    return {
        "element": element,
        "element_name": cfg["name"],
        "orbital": cfg["orbital"],
        "base_name": ns["base_name"],
        "input_table": df,
        "energy_shift": float(ns["energy_shift"]),
        "gaussian_percent": float(gaussian_percent),
        "lorentzian_percent": float(lorentzian_percent),
        "residual_std": float(np.std(residuals, ddof=1)),
        "shirley_figure": shirley_figure,
        "fit_figure": fit_figure,
        "residual_figure": residual_figure,
        "execution_log": log,
        **tables,
    }
