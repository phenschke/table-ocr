"""
File Details page - view OCR results for individual PDF files.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ui.components import render_metadata_chips, render_status_badge
from ui.constants import (
    DATAFRAME_PAGE_HEIGHT,
    DATAFRAME_PREVIEW_HEIGHT,
    ICON_ANALYTICS,
    ICON_ARROW_BACK,
    ICON_CODE,
    ICON_DESCRIPTION,
    ICON_DOWNLOAD,
    ICON_FOLDER_OPEN,
    ICON_HOW_TO_VOTE,
    ICON_TABLE_CHART,
    RESULTS_DIR,
)
from ui.dataframe_utils import load_page_as_dataframe, load_results_as_dataframe
from ui.feedback import error, info, success, warning
from ui.majority_vote import (
    can_create_majority_vote,
    create_majority_voted_result,
    is_majority_vote_file,
    majority_vote_exists,
)
from ui.state import (
    clear_view_state,
    get_current_page,
    get_viewing_file,
    get_viewing_project,
    set_current_page,
)
from ui.storage import DataStore

# Initialize data store
store = DataStore()


def go_back_to_projects() -> None:
    clear_view_state()
    st.switch_page(st.session_state.pages["projects"])


pdf_path = get_viewing_file()
project_name = get_viewing_project()

if not pdf_path or not project_name:
    warning("No file selected. Choose a file from the Projects page to view results.")
    if st.button(f"{ICON_ARROW_BACK} Go to Projects", use_container_width=False):
        go_back_to_projects()
    st.stop()

pdf_path_obj = Path(pdf_path)
file_name = pdf_path_obj.name

if not pdf_path_obj.exists():
    error(f"Source PDF not found: {pdf_path}")
    st.button(f"{ICON_ARROW_BACK} Back to Projects", on_click=go_back_to_projects)
    st.stop()

# Navigation header
nav_cols = st.columns([1, 4])
with nav_cols[0]:
    st.button(
        f"{ICON_ARROW_BACK} Back",
        key="file_details.back",
        use_container_width=True,
        on_click=go_back_to_projects,
    )

breadcrumb = f"Projects › {project_name} › {file_name}"
st.markdown(
    f"<div style='margin: 0.5rem 0 1.5rem 0; opacity: 0.7;'>{breadcrumb}</div>",
    unsafe_allow_html=True,
)
st.header(f"{ICON_DESCRIPTION} {file_name}")

# Pull associated project information
project = store.get_project(project_name)
prompt_name = project.prompt_name if project else "Unknown"
schema_name = project.schema_name if project else "Unknown"

render_metadata_chips(
    [
        ("Project", project_name),
        ("Prompt", prompt_name),
        ("Schema", schema_name),
    ]
)

# Locate result files
results_dir = RESULTS_DIR / project_name
pdf_stem = pdf_path_obj.stem
result_files = (
    sorted(results_dir.glob(f"{pdf_stem}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if results_dir.exists()
    else []
)

if not result_files:
    warning("No OCR results found for this file yet.")
    st.stop()

if len(result_files) > 1:
    result_col, vote_col = st.columns([3, 1])
    with result_col:
        select_options = [f.name for f in result_files]
        option_labels = {
            name: (f"★ {name}" if is_majority_vote_file(results_dir / name) else name)
            for name in select_options
        }
        selected_name = st.selectbox(
            "Result run:",
            options=select_options,
            index=0,
            help="Pick from previous processing runs. Latest appears first.",
            format_func=lambda value: option_labels.get(value, value),
        )
        selected_result = results_dir / selected_name
    with vote_col:
        can_vote = can_create_majority_vote(project_name, pdf_path)
        vote_exists = majority_vote_exists(project_name, pdf_path)
        button_label = f"{ICON_HOW_TO_VOTE} {'Update' if vote_exists else 'Create'} Vote"
        button_help = f"{'Update' if vote_exists else 'Create'} majority-voted result (requires 3+ runs)"

        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)  # Align with selectbox
        if st.button(
            button_label,
            key="file_details.majority_vote",
            use_container_width=True,
            disabled=not can_vote,
            help=button_help,
        ):
            try:
                output_path = create_majority_voted_result(project_name, pdf_path)
                action = "updated" if vote_exists else "created"
                success(f"Majority-voted result {action}!")
                info(f"{ICON_FOLDER_OPEN} Result saved to `{output_path.name}`")
                st.rerun()
            except ValueError as exc:
                error(str(exc))
            except Exception as exc:
                error(f"Failed to create majority-voted result: {exc}")
else:
    selected_result = result_files[0]
    can_vote = can_create_majority_vote(project_name, pdf_path)
    vote_exists = majority_vote_exists(project_name, pdf_path)
    if can_vote:
        button_label = f"{ICON_HOW_TO_VOTE} {'Update' if vote_exists else 'Create'} Vote"
        button_help = f"{'Update' if vote_exists else 'Create'} majority-voted result (requires 3+ runs)"

        if st.button(
            button_label,
            key="file_details.majority_vote_single",
            help=button_help,
        ):
            try:
                output_path = create_majority_voted_result(project_name, pdf_path)
                action = "updated" if vote_exists else "created"
                success(f"Majority-voted result {action}!")
                info(f"{ICON_FOLDER_OPEN} Result saved to `{output_path.name}`")
                st.rerun()
            except ValueError as exc:
                error(str(exc))
            except Exception as exc:
                error(f"Failed to create majority-voted result: {exc}")

# Load chosen result file
try:
    result_data = json.loads(selected_result.read_text())
except Exception as exc:
    error(f"Failed to load result file: {exc}")
    st.stop()

results = result_data.get("results", [])
num_pages = len(results)

schema = store.get_schema(schema_name) if project else None
is_dataframe_serializable = bool(schema and schema.is_dataframe_serializable())

# Snapshot summary
st.subheader(f"{ICON_ANALYTICS} Extraction Preview")

if is_dataframe_serializable:
    df = load_results_as_dataframe(str(selected_result))
    if df is not None and len(df) > 0:
        table_cols = st.columns(3)
        with table_cols[0]:
            st.metric("Total rows", len(df))
        with table_cols[1]:
            st.metric("Pages processed", num_pages)
        st.dataframe(df, use_container_width=True, height=DATAFRAME_PREVIEW_HEIGHT)
    else:
        info("No tabular data available in this snapshot.")
else:
    info("Current schema does not support table preview. Raw JSON is available in downloads.")

download_cols = st.columns(2 if is_dataframe_serializable else 1)
with download_cols[0]:
    st.download_button(
        label=f"{ICON_CODE} Download JSON",
        data=json.dumps(result_data, indent=2),
        file_name=selected_result.name,
        mime="application/json",
        key="file_details.download_json_all",
        use_container_width=True,
    )
if is_dataframe_serializable:
    with download_cols[1]:
        if df is not None and len(df) > 0:
            st.download_button(
                label=f"{ICON_TABLE_CHART} Download CSV",
                data=df.write_csv(),
                file_name=f"{pdf_stem}.csv",
                mime="text/csv",
                key="file_details.download_csv_all",
                use_container_width=True,
            )
        else:
            st.button(
                f"{ICON_TABLE_CHART} Download CSV",
                disabled=True,
                use_container_width=True,
                key="file_details.download_csv_all_disabled",
            )

st.divider()

# Page-level inspection
st.subheader(f"{ICON_DESCRIPTION} Inspect Pages")


pdf_col, data_col = st.columns([1, 1])

with pdf_col:
    st.subheader("PDF page")
    current_page = get_current_page(default=1) or 1
    current_page = min(max(current_page, 1), max(num_pages, 1))

    page_input = st.number_input(
                "Page number",
                min_value=1,
                max_value=max(num_pages, 1),
                value=current_page,
                step=1,
                key="file_details.page_input",
                width=125
            )

    if page_input != current_page:
        set_current_page(page_input)
        st.rerun()
    else:
        set_current_page(current_page)

    page_idx = current_page - 1
    try:
        from table_ocr.core import pdf_pages_to_images

        images = pdf_pages_to_images(pdf_path, start_page=current_page, max_pages=1)
        if images:
            # Display image with responsive sizing
            st.image(images[0], use_container_width=True)
        else:
            warning("Unable to render this PDF page.")
    except Exception as exc:
        error(f"Error rendering PDF page: {exc}")

with data_col:
    st.subheader("OCR result")
    if 0 <= page_idx < len(results):
        page_result = results[page_idx]
        if is_dataframe_serializable:
            page_df = load_page_as_dataframe(page_result, current_page, file_name)
            if page_df is not None and len(page_df) > 0:
                render_status_badge(f"{len(page_df)} row(s)", variant="info")
                st.dataframe(page_df, use_container_width=True, height=DATAFRAME_PAGE_HEIGHT)
            else:
                warning("No structured data extracted on this page.")
                with st.expander("View raw JSON", expanded=False):
                    st.json(page_result)
        else:
            st.json(page_result)

        download_page_cols = st.columns(2 if is_dataframe_serializable else 1)
        with download_page_cols[0]:
            st.download_button(
                label=f"{ICON_CODE} Download page JSON",
                data=json.dumps(page_result, indent=2),
                file_name=f"{pdf_stem}_page_{current_page}.json",
                mime="application/json",
                key=f"file_details.download_json_page_{current_page}",
                use_container_width=True,
            )
        if is_dataframe_serializable:
            with download_page_cols[1]:
                page_df = load_page_as_dataframe(page_result, current_page, file_name)
                if page_df is not None and len(page_df) > 0:
                    st.download_button(
                        label=f"{ICON_TABLE_CHART} Download page CSV",
                        data=page_df.write_csv(),
                        file_name=f"{pdf_stem}_page_{current_page}.csv",
                        mime="text/csv",
                        key=f"file_details.download_csv_page_{current_page}",
                        use_container_width=True,
                    )
                else:
                    st.button(
                        f"{ICON_TABLE_CHART} Download page CSV",
                        disabled=True,
                        use_container_width=True,
                        key=f"file_details.download_csv_page_disabled_{current_page}",
                    )
    else:
        warning(f"No result data for page {current_page}.")
