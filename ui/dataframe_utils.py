"""
DataFrame conversion utilities for UI display and export.
"""
from typing import Any, Optional
import polars as pl
import json
from pathlib import Path


def load_page_as_dataframe(page_result: Any, page_idx: int, pdf_file_name: str = "unknown") -> Optional[pl.DataFrame]:
    """Load a single page's OCR result and convert to a Polars DataFrame.
    
    Args:
        page_result: Single page result (list with JSON string or dict)
        page_idx: Page number (1-based)
        pdf_file_name: Name of the PDF file
        
    Returns:
        Polars DataFrame with data from this page, or None if error
    """
    try:
        rows = []
        
        # Each page_result is a list with one element containing a JSON string
        # Example: ["{\"table\": [{...}, {...}]}"]
        if isinstance(page_result, list) and len(page_result) > 0:
            # Get the first element (the JSON string)
            json_string = page_result[0]
            if isinstance(json_string, str):
                try:
                    # Parse the JSON string to get the actual data
                    parsed_data = json.loads(json_string)
                    # Extract the table array
                    if isinstance(parsed_data, dict) and "table" in parsed_data:
                        table_data = parsed_data["table"]
                        # Add each row with file name and page number
                        for row in table_data:
                            if isinstance(row, dict):
                                row_with_metadata = {
                                    "file": pdf_file_name,
                                    "page": page_idx,
                                    **row
                                }
                                rows.append(row_with_metadata)
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON for page {page_idx}: {e}")
                    return None
        
        if not rows:
            return None
        
        # Create DataFrame
        df = pl.DataFrame(rows)
        return df
        
    except Exception as e:
        print(f"Error loading page as DataFrame: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_results_as_dataframe(result_file_path: str) -> Optional[pl.DataFrame]:
    """Load OCR results from a JSON file and convert to a Polars DataFrame.
    
    Handles the structure where results are saved from ocr_pdf():
    - Top level: dict with "results" key
    - results: list of pages
    - Each page: list with one element [0] containing JSON string
    - JSON string: dict with "table" key containing array of row dicts
    
    Args:
        result_file_path: Path to the JSON result file
        
    Returns:
        Polars DataFrame with combined data from all pages, or None if error
    """
    try:
        result_path = Path(result_file_path)
        if not result_path.exists():
            return None
        
        with open(result_path, 'r') as f:
            result_data = json.load(f)
        
        # Extract results array and pdf_file name from the wrapper dict
        pdf_file_name = None
        if isinstance(result_data, dict):
            results = result_data.get("results", [])
            pdf_file_name = result_data.get("pdf_file", result_path.stem)
        elif isinstance(result_data, list):
            results = result_data
            pdf_file_name = result_path.stem
        else:
            return None
        
        if not results:
            return None
        
        # Combine all pages' table arrays
        all_rows = []
        for page_idx, page_result in enumerate(results, start=1):
            page_df = load_page_as_dataframe(page_result, page_idx, pdf_file_name)
            if page_df is not None:
                all_rows.extend(page_df.to_dicts())
        
        if not all_rows:
            return None
        
        # Create DataFrame
        df = pl.DataFrame(all_rows)
        return df
        
    except Exception as e:
        print(f"Error loading results as DataFrame: {e}")
        import traceback
        traceback.print_exc()
        return None
