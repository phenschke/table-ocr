"""
File Details page - view OCR results for individual PDF files
"""
import streamlit as st
import json
from pathlib import Path

from ui.storage import DataStore
from ui.dataframe_utils import load_results_as_dataframe, load_page_as_dataframe
from ui.utils import clear_file_viewing_state
from ui.constants import (
    ICON_ARROW_BACK, ICON_DESCRIPTION, ICON_ANALYTICS,
    ICON_DOWNLOAD, ICON_CODE, ICON_TABLE_CHART,
    DATAFRAME_PREVIEW_HEIGHT, DATAFRAME_PAGE_HEIGHT
)

# Initialize data store
store = DataStore()

# Check if we have a file to view
if 'viewing_file' not in st.session_state or st.session_state.viewing_file is None:
    st.warning("No file selected. Please go to Projects and select a file to view details.")
    if st.button("{ICON_ARROW_BACK} Go to Projects"):
        # Ensure viewing state is cleared
        clear_file_viewing_state()
        st.switch_page(st.session_state.pages['projects'])
    st.stop()

pdf_path = st.session_state.viewing_file
project_name = st.session_state.viewing_project
file_name = Path(pdf_path).name

# Back button with breadcrumb context
col1, col2 = st.columns([1, 4])
with col1:
    if st.button(f"{ICON_ARROW_BACK} Back to Projects", key="back_to_projects", use_container_width=True):
        # Clear viewing state before switching pages
        clear_file_viewing_state()
        st.switch_page(st.session_state.pages['projects'])

# Header with breadcrumb
st.markdown(f"""
    <div style="margin-bottom: 1rem; color: rgba(250, 250, 250, 0.6); font-size: 0.9rem;">
        Projects › {project_name} › <strong>{file_name}</strong>
    </div>
""", unsafe_allow_html=True)

st.header(f"{ICON_DESCRIPTION} {file_name}")

# Check if file exists
if not Path(pdf_path).exists():
    st.error(f"File not found: {pdf_path}")
    st.stop()

# Get result files for this PDF
results_dir = Path("ocr_data") / "results" / project_name
pdf_stem = Path(pdf_path).stem
result_files = []
if results_dir.exists():
    result_files = sorted(list(results_dir.glob(f"{pdf_stem}_*.json")), 
                         key=lambda x: x.stat().st_mtime, reverse=True)

if not result_files:
    st.warning("No results found for this file. Please process it first.")
    st.stop()

# Select result file (default to most recent)
if len(result_files) > 1:
    result_file_names = [f.name for f in result_files]
    selected_result_name = st.selectbox(
        "Select Result File",
        result_file_names,
        help="Multiple results found. Showing most recent first."
    )
    selected_result_file = results_dir / selected_result_name
else:
    selected_result_file = result_files[0]

# Load results
try:
    with open(selected_result_file, 'r') as f:
        result_data = json.load(f)
    
    results = result_data.get("results", [])
    num_pages = len(results)
    
    # Check if schema is DataFrame serializable
    project = store.get_project(project_name)
    schema = None
    is_dataframe_serializable = False
    if project:
        schema = store.get_schema(project.schema_name)
        if schema:
            is_dataframe_serializable = schema.is_dataframe_serializable()
    
    # SECTION 1: File Data Preview (at the top)
    if is_dataframe_serializable:
        st.subheader(f"{ICON_ANALYTICS} File Data Preview")
        
        # Load data as DataFrame
        df = load_results_as_dataframe(str(selected_result_file))
        
        if df is not None and len(df) > 0:
            # Display summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rows", len(df))
            with col2:
                st.metric("Total Columns", len(df.columns))
            with col3:
                st.metric("Pages", num_pages)
            
            # Display interactive DataFrame
            st.write("**Data Table:**")
            st.dataframe(df, use_container_width=True, height=DATAFRAME_PREVIEW_HEIGHT)
            
            # Download button with JSON/CSV options
            with st.popover(f"{ICON_DOWNLOAD} Download All Results"):
                st.markdown("**Download as:**")
                
                # JSON download
                st.download_button(
                    label=f"{ICON_CODE} JSON",
                    data=json.dumps(result_data, indent=2),
                    file_name=selected_result_file.name,
                    mime="application/json",
                    key="download_all_json",
                    use_container_width=True
                )
                
                # CSV download
                csv_data = df.write_csv()
                st.download_button(
                    label=f"{ICON_TABLE_CHART} CSV",
                    data=csv_data,
                    file_name=f"{pdf_stem}.csv",
                    mime="text/csv",
                    key="download_all_csv",
                    use_container_width=True
                )
        else:
            st.info("No data available for preview.")
        
        st.markdown("---")
    
    # SECTION 2: Individual Page View
    st.subheader(f"{ICON_DESCRIPTION} Inspect Pages")
    
    # Initialize page number in session state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1
    
    # Ensure page number is valid
    if st.session_state.current_page > num_pages:
        st.session_state.current_page = 1
    if st.session_state.current_page < 1:
        st.session_state.current_page = 1
    
    # Simple page navigation with number input (has built-in +/- buttons)
    page_input = st.number_input(
        f"Page (of {num_pages})",
        min_value=1,
        max_value=num_pages,
        value=st.session_state.current_page,
        step=1,
        key="page_input"
    )
    
    # Update session state if page changed
    if page_input != st.session_state.current_page:
        st.session_state.current_page = page_input
        st.rerun()
    
    # Display PDF and Results side by side
    pdf_col, results_col = st.columns([1, 1])
    
    with pdf_col:
        st.subheader("PDF Page")
        try:
            from table_ocr.core import pdf_pages_to_images
            images = pdf_pages_to_images(
                pdf_path,
                start_page=st.session_state.current_page,
                max_pages=1
            )
            if images:
                st.image(images[0], use_container_width=True)
            else:
                st.error("Failed to extract page image from PDF")
        except Exception as img_error:
            st.error(f"Error displaying PDF: {img_error}")
    
    with results_col:
        st.subheader("OCR Results")
        if st.session_state.current_page <= len(results):
            page_result = results[st.session_state.current_page - 1]
            
            # Display as DataFrame if serializable, otherwise as JSON
            if is_dataframe_serializable:
                # Load page as DataFrame
                page_df = load_page_as_dataframe(
                    page_result, 
                    st.session_state.current_page,
                    file_name
                )
                if page_df is not None and len(page_df) > 0:
                    st.dataframe(page_df, use_container_width=True, height=DATAFRAME_PAGE_HEIGHT)
                    
                    # Also show row count
                    st.caption(f"Rows: {len(page_df)}")
                else:
                    st.warning("No data extracted for this page")
                    # Fallback to JSON if DataFrame is empty
                    with st.expander("View Raw JSON"):
                        st.json(page_result)
            else:
                # Display as formatted JSON (original behavior)
                st.json(page_result)
            
            # Download button with JSON/CSV options for this page
            with st.popover(f"{ICON_DOWNLOAD} Download Page {st.session_state.current_page} Results"):
                st.markdown("**Download as:**")
                
                # JSON download
                st.download_button(
                    label=f"{ICON_CODE} JSON",
                    data=json.dumps(page_result, indent=2),
                    file_name=f"{pdf_stem}_page_{st.session_state.current_page}.json",
                    mime="application/json",
                    key="download_page_json",
                    use_container_width=True
                )
                
                # CSV download (if DataFrame serializable)
                if is_dataframe_serializable:
                    page_df = load_page_as_dataframe(
                        page_result, 
                        st.session_state.current_page,
                        file_name
                    )
                    if page_df is not None and len(page_df) > 0:
                        csv_data = page_df.write_csv()
                        st.download_button(
                            label=f"{ICON_TABLE_CHART} CSV",
                            data=csv_data,
                            file_name=f"{pdf_stem}_page_{st.session_state.current_page}.csv",
                            mime="text/csv",
                            key="download_page_csv",
                            use_container_width=True
                        )
                    else:
                        st.caption("CSV: No data available")
                else:
                    st.caption("CSV: Not available for this schema")
        else:
            st.warning(f"No results for page {st.session_state.current_page}")
    
except Exception as e:
    st.error(f"Error loading results: {e}")
    import traceback
    st.code(traceback.format_exc())
