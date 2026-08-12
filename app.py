from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from xps_pipeline import analyze_xy_file, figure_to_png_bytes, get_element_config


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Automated Nb / Ta XPS Peak Fitting",
    page_icon="image.png",
    layout="wide",
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("---")
st.sidebar.header("About")

st.sidebar.write(
    """
    **Automated Nb 3d / Ta 4f XPS Peak Fitting**

    Developed by **Rithvik Jandhyala**.

    This application performs adaptive Shirley background subtraction,
    simultaneous constrained fitting, automatic energy calibration,
    uncertainty estimation, area verification, and visualization of
    Niobium or Tantalum XPS spectra.
    """
)

st.sidebar.markdown(
    """
    <link rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">

    <p>
        <a href="https://www.linkedin.com/in/rithvik-jandhyala/" target="_blank" style="text-decoration:none;">
            <i class="fab fa-linkedin" style="color:#0A66C2;"></i>
            LinkedIn
        </a>
    </p>

    <p>
        <a href="mailto:ricky.jandhyala@gmail.com" style="text-decoration:none;">
            <i class="fas fa-envelope" style="color:#EA4335;"></i>
            Email
        </a>
    </p>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CUSTOM PROGRESS SPINNER
# ============================================================

st.markdown(
    """
    <style>
    .progress-line {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.875rem;
        color: #6b7280;
        margin-top: 4px;
    }

    .progress-spinner {
        width: 14px;
        height: 14px;
        border: 2px solid rgba(100, 116, 139, 0.25);
        border-top-color: #2563eb;
        border-radius: 50%;
        animation: progress-spin 0.8s linear infinite;
        flex-shrink: 0;
    }

    .progress-complete {
        color: #16a34a;
        font-weight: 500;
    }

    @keyframes progress-spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# MAIN PAGE — ELEMENT SELECTION FIRST
# ============================================================

st.title("Automated Nb / Ta XPS Fitting")
st.caption(
    "Choose the element first, then upload one .xy spectrum. "
    "Both workflows use the same interface, plots, tables, and downloads."
)

element_label = st.radio(
    "Select element",
    options=["Niobium (Nb)", "Tantalum (Ta)"],
    horizontal=True,
    key="element_selector",
)

element = "Nb" if element_label.startswith("Niobium") else "Ta"
cfg = get_element_config(element)

# Do not accidentally show an old Nb result after switching to Ta, or vice versa.
stored_results = st.session_state.get("xps_results")
if stored_results is not None and stored_results.get("element") != element:
    st.session_state.pop("xps_results", None)

st.subheader(f"{cfg['name']} — {cfg['orbital']}")

uploaded_file = st.file_uploader(
    f"Upload one {cfg['orbital']} .xy file",
    type=["xy"],
    accept_multiple_files=False,
    key=f"uploader_{element}",
)

if uploaded_file is None:
    st.info(f"Choose one {cfg['orbital']} .xy file to begin.")
    st.stop()

run_fit = st.button(
    f"Run automated {element} fit",
    type="primary",
    use_container_width=True,
)


# ============================================================
# RUN ANALYSIS WITH LIVE PROGRESS
# ============================================================

if run_fit:
    st.session_state.pop("xps_results", None)

    progress_bar = st.progress(0)
    progress_message = st.empty()
    progress_detail = st.empty()

    def update_progress(fraction: float, message: str) -> None:
        fraction = max(0.0, min(float(fraction), 1.0))
        percent = int(round(100 * fraction))

        progress_bar.progress(fraction)
        progress_message.markdown(f"**{message}**")
        progress_detail.markdown(
            f"""
            <div class="progress-line">
                <div class="progress-spinner"></div>
                <span>Overall progress: {percent}%</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    try:
        update_progress(0.0, f"Starting {cfg['orbital']} analysis...")

        results = analyze_xy_file(
            uploaded_file.getvalue(),
            uploaded_file.name,
            element=element,
            progress_callback=update_progress,
        )

        st.session_state["xps_results"] = results

        progress_bar.progress(1.0)
        progress_message.success(f"{cfg['name']} analysis complete")
        progress_detail.markdown(
            """
            <div class="progress-line progress-complete">
                <span>✓</span>
                <span>Overall progress: 100%</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as exc:
        progress_bar.empty()
        progress_message.error("Analysis failed")
        progress_detail.markdown(
            """
            <div class="progress-line" style="color:#dc2626;">
                <span>✕</span>
                <span>Analysis stopped before completion</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.error("The fit did not complete.")
        st.exception(exc)


# ============================================================
# RESULTS
# ============================================================

if "xps_results" not in st.session_state:
    st.stop()

results = st.session_state["xps_results"]

# Extra safeguard against stale state.
if results.get("element") != element:
    st.stop()

st.header(f'{results["base_name"]} — {results["element_name"]} {results["orbital"]}')

m1, m2, m3, m4 = st.columns(4)
m1.metric("Energy shift", f'{results["energy_shift"]:+.3f} eV')
m2.metric("Gaussian contribution", f'{results["gaussian_percent"]:.1f}%')
m3.metric("Lorentzian contribution", f'{results["lorentzian_percent"]:.1f}%')
m4.metric("Residual σ", f'{results["residual_std"]:.3f}')

plot_tab, table_tab, download_tab, log_tab = st.tabs(
    ["Plots", "Tables", "Downloads", "Run details"]
)


# ============================================================
# PLOTS
# ============================================================

with plot_tab:
    st.subheader("Adaptive Shirley background")
    st.pyplot(results["shirley_figure"], use_container_width=True)

    st.subheader("Raw and Shirley-corrected simultaneous fit")
    st.pyplot(results["fit_figure"], use_container_width=True)

    st.subheader("Residuals")
    st.pyplot(results["residual_figure"], use_container_width=True)


# ============================================================
# TABLES
# ============================================================

with table_tab:
    st.subheader("Binding energies and FWHM")
    st.dataframe(
        results["shift_table"],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Areas and Simpson verification")
    st.dataframe(
        results["area_table"],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Approximate 1σ uncertainties")
    st.dataframe(
        results["uncertainty_table"],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Total-area verification")
    st.dataframe(
        results["total_area_table"],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Fit diagnostics")
    st.dataframe(
        results["diagnostics_table"],
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# DOWNLOADS
# ============================================================

with download_tab:
    base = results["base_name"]
    prefix = f"{base}_{results['element']}"

    st.download_button(
        "Download fitted-parameter CSV",
        results["uncertainty_table"].to_csv(index=False),
        file_name=f"{prefix}_fit_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    bundle = BytesIO()

    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        for name in [
            "shift_table",
            "area_table",
            "uncertainty_table",
            "total_area_table",
            "diagnostics_table",
        ]:
            archive.writestr(
                f"{prefix}_{name}.csv",
                results[name].to_csv(index=False),
            )

        archive.writestr(
            f"{prefix}_shirley_background.png",
            figure_to_png_bytes(results["shirley_figure"]),
        )
        archive.writestr(
            f"{prefix}_final_fit.png",
            figure_to_png_bytes(results["fit_figure"]),
        )
        archive.writestr(
            f"{prefix}_residuals.png",
            figure_to_png_bytes(results["residual_figure"]),
        )

    st.download_button(
        "Download all tables and figures (.zip)",
        bundle.getvalue(),
        file_name=f"{prefix}_xps_results.zip",
        mime="application/zip",
        use_container_width=True,
    )


# ============================================================
# EXECUTION LOG
# ============================================================

with log_tab:
    st.caption(
        f"Messages generated by the {results['element_name']} scientific notebook core."
    )
    st.code(results["execution_log"] or "No text output was generated.")
