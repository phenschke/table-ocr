"""
Utility functions for the UI.
"""
import streamlit as st
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import json

from ui.models import OutputSchema
from ui.dataframe_utils import load_results_as_dataframe
from ui.state import (
    clear_view_state,
    get_viewing_file,
    set_viewing_context,
)
from ui.constants import (
    RESULTS_DIR,
    STATUS_PROCESSED,
    STATUS_NOT_PROCESSED,
    ICON_CODE,
    ICON_TABLE_CHART,
    ICON_DOWNLOAD,
)


# ===== Session State Management =====

def clear_file_viewing_state():
    """Clear file viewing session state."""
    clear_view_state()


def ensure_cleared_file_state():
    """Clear file state if set, then rerun."""
    if get_viewing_file() is not None:
        clear_viewing_state_and_rerun()


def clear_viewing_state_and_rerun():
    """Clear view state and trigger rerun to reset dependent UI."""
    clear_view_state()
    set_viewing_context(None, None)
    st.rerun()


def set_viewing_state(file_path: str, project_name: str) -> None:
    """Persist the viewing context."""
    set_viewing_context(file_path, project_name)


# ===== Result File Management =====

def get_result_files(project_name: str, pdf_path: str) -> List[Path]:
    """Get all result files for a PDF in a project.
    
    Args:
        project_name: Name of the project
        pdf_path: Path to the PDF file
        
    Returns:
        List of result file paths, sorted by modification time (newest first)
    """
    results_dir = RESULTS_DIR / project_name
    if not results_dir.exists():
        return []
    pdf_stem = Path(pdf_path).stem
    return sorted(
        list(results_dir.glob(f"{pdf_stem}_*.json")),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )


def _extract_numeric_suffix(stem: str, pdf_stem: str, suffix: Optional[str]) -> Optional[int]:
    """Extract the numeric run suffix from a result filename stem."""
    prefix = f"{pdf_stem}_"
    if not stem.startswith(prefix):
        return None

    remainder = stem[len(prefix):]

    if suffix:
        suffix_token = f"_{suffix}"
        if not remainder.endswith(suffix_token):
            return None
        remainder = remainder[: -len(suffix_token)]
    else:
        if "_" in remainder:
            return None

    return int(remainder) if remainder.isdigit() else None


def get_next_result_path(project_name: str, pdf_path: str, suffix: Optional[str] = None) -> Path:
    """Determine the next result file path using an incrementing counter.
    
    Args:
        project_name: Name of the project
        pdf_path: Original PDF path
        suffix: Optional suffix (e.g., 'batch')
    
    Returns:
        Path where the next result run should be stored
    """
    results_dir = RESULTS_DIR / project_name
    results_dir.mkdir(parents=True, exist_ok=True)

    pdf_stem = Path(pdf_path).stem
    existing_numbers = []

    for path in results_dir.glob(f"{pdf_stem}_*.json"):
        number = _extract_numeric_suffix(path.stem, pdf_stem, suffix)
        if number is not None:
            existing_numbers.append(number)

    next_index = (max(existing_numbers) + 1) if existing_numbers else 1

    while True:
        suffix_part = f"_{suffix}" if suffix else ""
        candidate = results_dir / f"{pdf_stem}_{next_index}{suffix_part}.json"
        if not candidate.exists():
            return candidate
        next_index += 1


def get_file_status_badge(result_files: List[Path]) -> tuple[str, str]:
    """Get status badge emoji and color for a file.
    
    Args:
        result_files: List of result files for the PDF
        
    Returns:
        Tuple of (badge_text, variant_name)
    """
    if result_files:
        return f"{STATUS_PROCESSED} · {len(result_files)} run(s)", "success"
    return STATUS_NOT_PROCESSED, "warning"


# ===== Confirmation Dialogs =====

def show_confirmation_dialog(
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    warning_text: Optional[str] = None,
    error_text: Optional[str] = None,
    info_text: Optional[str] = None,
    details: Optional[List[str]] = None
) -> None:
    """Show a reusable confirmation dialog.
    
    Args:
        title: Dialog title
        message: Main confirmation message
        on_confirm: Callback to execute on confirmation
        warning_text: Optional warning message (yellow)
        error_text: Optional error message (red)
        info_text: Optional info message (blue)
        details: Optional list of detail strings to display as captions
    """
    st.write(message)
    
    if error_text:
        st.error(error_text)
    if warning_text:
        st.warning(warning_text)
    if info_text:
        st.info(info_text)
    
    if details:
        for detail in details:
            st.caption(detail)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Delete", use_container_width=True, type="primary"):
            on_confirm()
    with col2:
        if st.button("Cancel", use_container_width=True):
            # Dialog will close automatically
            pass


# ===== Download Utilities =====

def create_json_download_button(
    result_file: Path,
    key: str,
    label: str = f"{ICON_CODE} JSON"
) -> None:
    """Create a JSON download button.
    
    Args:
        result_file: Path to the JSON result file
        key: Unique key for the button
        label: Button label (default has icon)
    """
    with open(result_file, 'r') as f:
        result_content = f.read()
    st.download_button(
        label=label,
        data=result_content,
        file_name=result_file.name,
        mime="application/json",
        key=key,
        use_container_width=True
    )


def create_csv_download_button(
    result_file: Path,
    key: str,
    label: str = f"{ICON_TABLE_CHART} CSV"
) -> None:
    """Create a CSV download button if data can be converted.
    
    Args:
        result_file: Path to the JSON result file
        key: Unique key for the button
        label: Button label (default has icon)
    """
    try:
        df = load_results_as_dataframe(str(result_file))
        if df is not None and len(df) > 0:
            csv_data = df.write_csv()
            csv_filename = f"{Path(result_file).stem}.csv"
            st.download_button(
                label=label,
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
                key=key,
                use_container_width=True
            )
        else:
            st.caption("CSV: No data available")
    except Exception as e:
        st.caption(f"CSV: Error - {str(e)[:30]}")


def create_download_popover(
    result_files: List[Path],
    schema: Optional[OutputSchema],
    key_prefix: str,
    disabled: bool = False
) -> None:
    """Create a download popover with JSON/CSV options.
    
    Args:
        result_files: List of result files (uses most recent)
        schema: Output schema to check if CSV serializable
        key_prefix: Prefix for button keys
        disabled: Whether the button should be disabled
    """
    if not result_files or disabled:
        st.button(ICON_DOWNLOAD, disabled=True, use_container_width=True)
        return
    
    latest_result = result_files[0]
    
    with st.popover(ICON_DOWNLOAD, use_container_width=True):
        st.markdown("**Download as:**")
        
        # JSON download
        create_json_download_button(
            latest_result,
            key=f"{key_prefix}_json"
        )
        
        # CSV download (if available)
        if schema and schema.is_dataframe_serializable():
            create_csv_download_button(
                latest_result,
                key=f"{key_prefix}_csv"
            )
        else:
            st.caption("CSV: Not available for this schema")


def create_combined_download_popover(
    all_result_files: List[Path],
    schema: Optional[OutputSchema],
    project_name: str,
    key_prefix: str
) -> Dict[str, Any]:
    """Create download popover for combined results from multiple files.
    
    Args:
        all_result_files: List of all result files to combine
        schema: Output schema to check if CSV serializable
        project_name: Name of the project (for filename)
        key_prefix: Prefix for button keys
        
    Returns:
        Dictionary with combined results data
    """
    from ui.dataframe_utils import combine_multiple_results
    from datetime import datetime
    import polars as pl
    
    st.markdown("**Download all project results as:**")
    
    # Combine all results
    combined_results = combine_multiple_results([str(f) for f in all_result_files])
    all_data = combined_results["data"]
    
    # Show errors if any
    if combined_results["errors"]:
        with st.expander("⚠️ Processing Warnings", expanded=False):
            for error in combined_results["errors"]:
                st.warning(error)
    
    # Create JSON download
    combined_json = {
        "project": project_name,
        "timestamp": datetime.now().isoformat(),
        "total_files": combined_results["total_files"],
        "total_rows": combined_results["total_rows"],
        "data": all_data
    }
    
    st.download_button(
        label=f"{ICON_CODE} JSON",
        data=json.dumps(combined_json, indent=2),
        file_name=f"{project_name}_all_results.json",
        mime="application/json",
        key=f"{key_prefix}_json",
        use_container_width=True
    )
    
    # CSV download (if schema is DataFrame serializable)
    can_export_csv = schema and schema.is_dataframe_serializable()
    if can_export_csv and all_data:
        df = pl.DataFrame(all_data)
        csv_data = df.write_csv()
        st.download_button(
            label=f"{ICON_TABLE_CHART} CSV",
            data=csv_data,
            file_name=f"{project_name}_all_results.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            use_container_width=True
        )
    elif not can_export_csv:
        st.caption("CSV: Not available for this schema")
    else:
        st.caption("CSV: No data available")
    
    return combined_results
