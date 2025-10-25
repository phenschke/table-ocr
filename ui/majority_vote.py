"""
Majority voting utilities for combining multiple OCR results.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import polars as pl

from ui.constants import RESULTS_DIR
from ui.utils import get_result_files
from table_ocr.parser import sample_majority_vote, strip_json_codeblock


def get_majority_vote_path(project_name: str, pdf_path: str) -> Path:
    """
    Get the path where the majority-voted result file should be stored.

    Args:
        project_name: Name of the project
        pdf_path: Path to the PDF file

    Returns:
        Path where the majority-voted result file is/should be located
    """
    results_dir = RESULTS_DIR / project_name
    pdf_stem = Path(pdf_path).stem
    return results_dir / f"{pdf_stem}_majority_voted.json"


def majority_vote_exists(project_name: str, pdf_path: str) -> bool:
    """
    Check if a majority-voted result already exists for this PDF.

    Args:
        project_name: Name of the project
        pdf_path: Path to the PDF file

    Returns:
        True if a majority-voted result exists, False otherwise
    """
    return get_majority_vote_path(project_name, pdf_path).exists()


def is_majority_vote_file(file_path: Path) -> bool:
    """
    Check if a result file is a majority-voted result.

    Args:
        file_path: Path to the result file

    Returns:
        True if the file is a majority-voted result, False otherwise
    """
    stem = file_path.stem
    return stem.endswith("_majority_voted") or stem.endswith("_majority")


def create_majority_voted_result(project_name: str, pdf_path: str) -> Optional[Path]:
    """
    Create a majority-voted result file by combining multiple OCR runs.

    Requires at least 3 result files for the given PDF. Uses position-based
    row alignment and majority voting from table_ocr.parser.sample_majority_vote.

    Note: Only one majority-voted result is kept per PDF. If one already exists,
    it will be replaced.

    Args:
        project_name: Name of the project
        pdf_path: Path to the PDF file

    Returns:
        Path to the created majority-voted result file, or None if insufficient files

    Raises:
        ValueError: If fewer than 3 result files exist
        Exception: If any processing error occurs
    """
    # Get all result files for this PDF (excluding any existing majority vote)
    all_files = get_result_files(project_name, pdf_path)
    majority_vote_path = get_majority_vote_path(project_name, pdf_path)

    # Filter out the existing majority vote file from the source files
    result_files = [f for f in all_files if f != majority_vote_path]

    if len(result_files) < 3:
        raise ValueError(f"Majority voting requires at least 3 result files, but only {len(result_files)} found.")

    # Load all result files
    result_data_list = []
    for result_file in result_files:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
            result_data_list.append(result_data)

    # Get metadata from the most recent (first) result file
    latest_result = result_data_list[0]
    pdf_file = latest_result.get("pdf_file", Path(pdf_path).name)
    prompt_name = latest_result.get("prompt", "unknown")
    schema_name = latest_result.get("schema", "unknown")

    # Get the maximum number of pages across all results
    max_pages = max(len(rd.get("results", [])) for rd in result_data_list)

    # Process each page
    majority_voted_results = []

    for page_idx in range(max_pages):
        # Collect page data from all result files
        page_dataframes = []

        for sample_idx, result_data in enumerate(result_data_list):
            results = result_data.get("results", [])

            # Skip if this result doesn't have this page
            if page_idx >= len(results):
                continue

            page_result = results[page_idx]

            # Parse the page result (it's a list with JSON string)
            if isinstance(page_result, list) and len(page_result) > 0:
                json_string = page_result[0]
                if isinstance(json_string, str):
                    try:
                        clean_json = strip_json_codeblock(json_string)
                        parsed_data = json.loads(clean_json)

                        # Extract table data
                        if isinstance(parsed_data, dict) and "table" in parsed_data:
                            table_data = parsed_data["table"]

                            # Add metadata columns
                            for row_idx, row in enumerate(table_data):
                                if isinstance(row, dict):
                                    row["_sample"] = sample_idx
                                    row["_page"] = page_idx + 1
                                    row["_row_index"] = row_idx

                            # Create DataFrame for this sample's page
                            if table_data:
                                df = pl.DataFrame(table_data)
                                page_dataframes.append(df)
                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue

        # If we have data for this page, perform majority voting
        if page_dataframes:
            # Combine all samples for this page
            combined_df = pl.concat(page_dataframes, how="diagonal_relaxed")

            # Get the list of actual data columns (excluding metadata)
            data_columns = [col for col in combined_df.columns if not col.startswith("_")]

            # Apply majority voting
            # Group by page and row index, get mode for each data column
            voted_df = sample_majority_vote(
                df=combined_df,
                group_by_cols=["_page", "_row_index"],
                n_samples=len(result_files),
                resolve_group=None
            )

            # Remove metadata columns and agreement columns
            voted_df = voted_df.select([col for col in voted_df.columns if not col.startswith("_") and not col.endswith("_agreement") and col != "n_samples" and col != "ambiguous"])

            # Convert to table format
            table_rows = voted_df.to_dicts()

            # Create the page result in the standard format
            page_json = json.dumps({"table": table_rows})
            majority_voted_results.append([page_json])
        else:
            # No data for this page - use empty table
            majority_voted_results.append([json.dumps({"table": []})])

    # Create the final result payload
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    payload = {
        "project": project_name,
        "pdf_file": pdf_file,
        "prompt": prompt_name,
        "schema": schema_name,
        "timestamp": timestamp,
        "processing_mode": "majority_vote",
        "num_pages": len(majority_voted_results),
        "num_source_files": len(result_files),
        "results": majority_voted_results,
    }

    # Save to file (this will overwrite any existing majority vote)
    results_dir = RESULTS_DIR / project_name
    results_dir.mkdir(parents=True, exist_ok=True)

    with open(majority_vote_path, "w") as f:
        json.dump(payload, f, indent=2)

    return majority_vote_path


def can_create_majority_vote(project_name: str, pdf_path: str) -> bool:
    """
    Check if majority voting is possible for the given PDF.

    Args:
        project_name: Name of the project
        pdf_path: Path to the PDF file

    Returns:
        True if at least 3 result files exist (excluding any existing majority vote), False otherwise
    """
    all_files = get_result_files(project_name, pdf_path)
    majority_vote_path = get_majority_vote_path(project_name, pdf_path)

    # Filter out the existing majority vote file from the count
    result_files = [f for f in all_files if f != majority_vote_path]
    return len(result_files) >= 3
