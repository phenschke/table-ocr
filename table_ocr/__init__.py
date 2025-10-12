"""
Table OCR - Digitize table scans using the Gemini API

Core library for OCR functionality. For the UI application, see the ui/ directory.
"""
__version__ = "0.1.0"

# Export core API functions for programmatic use
from table_ocr.direct import ocr_pdf
from table_ocr.batch import create_batch_ocr_job, get_job_state, download_batch_results_file

__all__ = [
    "ocr_pdf",
    "create_batch_ocr_job",
    "get_job_state",
    "download_batch_results_file",
]
