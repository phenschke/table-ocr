"""
Batch processing utility functions for UI
"""
import streamlit as st
import json
from datetime import datetime
from pathlib import Path

from table_ocr.batch import (
    create_batch_ocr_job,
    get_job_state,
    download_batch_results_file,
    parse_pdf_batch_results_file
)
from table_ocr.core import GeminiClient
from ui.storage import DataStore
from ui.models import Project, BatchJob
from ui.utils import get_next_result_path


def _update_ui_progress(progress_bar, status_text, message: str, percentage: float) -> None:
    """Update Streamlit progress indicators."""
    progress_bar.progress(percentage)
    status_text.text(message)


def submit_batch_job_ui(project: Project, pdf_path: str, prompt_content: str, genai_schema) -> BatchJob:
    """Submit a batch OCR job and add it to the project."""
    # Create batch directory for this project
    batch_dir = Path("ocr_data") / "batch" / project.name
    batch_dir.mkdir(parents=True, exist_ok=True)

    # Create progress indicators
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Submit batch job with progress callback
        status_text.text("Converting PDF pages to images...")
        job_name = create_batch_ocr_job(
            pdf_path=pdf_path,
            prompt=prompt_content,
            response_schema=genai_schema,
            jsonl_dir=str(batch_dir),
            n_samples=1,  # Fixed to 1 for now
            progress_callback=lambda msg, pct: _update_ui_progress(progress_bar, status_text, msg, pct)
        )
        status_text.text("Batch job created successfully!")
    finally:
        # Clean up progress indicators
        progress_bar.empty()
        status_text.empty()
    
    # Create BatchJob record
    batch_job = BatchJob(
        job_name=job_name,
        pdf_file=pdf_path,
        status="JOB_STATE_PENDING",
        created_at=datetime.now()
    )
    
    # Add to project and save
    project.batch_jobs.append(batch_job)
    store = DataStore()
    store.save_project(project)
    
    return batch_job


def update_batch_job_status_ui(project: Project, job_index: int, auto_download: bool = True) -> BatchJob:
    """
    Check and update status for a specific batch job.

    Args:
        project: The project containing the batch job
        job_index: Index of the job in project.batch_jobs
        auto_download: If True, automatically download results when job succeeds

    Returns:
        The updated BatchJob
    """
    job = project.batch_jobs[job_index]
    previous_status = job.status

    try:
        current_state = get_job_state(job.job_name)

        if current_state and current_state != job.status:
            job.status = current_state

            if current_state in ['JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED']:
                job.completed_at = datetime.now()

            if current_state == 'JOB_STATE_FAILED':
                try:
                    client = GeminiClient()
                    batch_job_obj = client.client.batches.get(name=job.job_name)
                    job.error_message = str(getattr(batch_job_obj, 'error', 'Unknown error'))
                except Exception as e:
                    job.error_message = f"Failed to fetch error details: {e}"

            # Auto-download results if job just succeeded
            if auto_download and current_state == 'JOB_STATE_SUCCEEDED' and previous_status != 'JOB_STATE_SUCCEEDED':
                try:
                    download_and_convert_batch_results_ui(project, job_index)
                    st.success(f"Batch job completed! Results automatically downloaded.")
                except Exception as e:
                    st.warning(f"Batch job succeeded but auto-download failed: {e}")

            store = DataStore()
            store.save_project(project)
    except Exception as e:
        st.error(f"Error checking job status: {e}")

    return job


def download_and_convert_batch_results_ui(project: Project, job_index: int) -> str:
    """Download batch results and convert to standard results format."""
    job = project.batch_jobs[job_index]
    
    try:
        # Download JSONL file to batch directory
        batch_dir = Path("ocr_data") / "batch" / project.name
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        jsonl_path = download_batch_results_file(
            batch_job_name=job.job_name,
            output_dir=str(batch_dir)
        )
        
        # Parse JSONL to extract results
        batch_result = parse_pdf_batch_results_file(jsonl_path)
        
        # Convert to same format as direct processing
        # Each page should be a list with one JSON string
        results = []
        for page_num in sorted(batch_result.results_by_page.keys()):
            page_samples = batch_result.results_by_page[page_num]
            # Take first sample (sample_num = 1)
            sample_data = page_samples.get(1)
            if sample_data:
                # Convert dict to JSON string and wrap in list
                results.append([json.dumps(sample_data)])
        
        # Save in standard results format
        output_path = get_next_result_path(project.name, job.pdf_file, suffix="batch")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        output_data = {
            "project": project.name,
            "pdf_file": Path(job.pdf_file).name,
            "prompt": project.prompt_name,
            "schema": project.schema_name,
            "timestamp": timestamp,
            "processing_mode": "batch",
            "batch_job_name": job.job_name,
            "num_pages": len(results),
            "results": results
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # Update job record
        job.result_file_path = str(output_path)
        store = DataStore()
        store.save_project(project)
        
        return str(output_path)
        
    except Exception as e:
        st.error(f"Error downloading/converting batch results: {e}")
        import traceback
        st.code(traceback.format_exc())
        raise


def get_job_status_badge(status: str) -> tuple:
    """Return emoji and color for job status."""
    status_map = {
        "JOB_STATE_PENDING": ("🕐", "orange", "Pending"),
        "JOB_STATE_RUNNING": ("⏳", "blue", "Running"),
        "JOB_STATE_SUCCEEDED": ("✅", "green", "Succeeded"),
        "JOB_STATE_FAILED": ("❌", "red", "Failed"),
        "JOB_STATE_CANCELLED": ("🚫", "gray", "Cancelled"),
        "JOB_STATE_EXPIRED": ("⏰", "gray", "Expired"),
    }
    return status_map.get(status, ("❓", "gray", status))


def get_batch_jobs_for_file(project: Project, pdf_path: str):
    """
    Get all batch jobs associated with a specific PDF file.

    Args:
        project: The project containing batch jobs
        pdf_path: Path to the PDF file

    Returns:
        List of (job_index, BatchJob) tuples for the specified file
    """
    jobs_for_file = []
    for idx, job in enumerate(project.batch_jobs):
        if job.pdf_file == pdf_path:
            jobs_for_file.append((idx, job))
    return jobs_for_file


def get_latest_batch_job_for_file(project: Project, pdf_path: str):
    """
    Get the most recent batch job for a specific PDF file.

    Args:
        project: The project containing batch jobs
        pdf_path: Path to the PDF file

    Returns:
        Tuple of (job_index, BatchJob) or None if no batch jobs exist for this file
    """
    jobs = get_batch_jobs_for_file(project, pdf_path)
    if not jobs:
        return None
    # Return the most recent job (last in list, since jobs are appended)
    return jobs[-1]
