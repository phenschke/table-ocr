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


def submit_batch_job_ui(project: Project, pdf_path: str, prompt_content: str, genai_schema) -> BatchJob:
    """Submit a batch OCR job and add it to the project."""
    # Create batch directory for this project
    batch_dir = Path("ocr_data") / "batch" / project.name
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    # Submit batch job
    job_name = create_batch_ocr_job(
        pdf_path=pdf_path,
        prompt=prompt_content,
        response_schema=genai_schema,
        jsonl_dir=str(batch_dir),
        n_samples=1  # Fixed to 1 for now
    )
    
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


def update_batch_job_status_ui(project: Project, job_index: int) -> BatchJob:
    """Check and update status for a specific batch job."""
    job = project.batch_jobs[job_index]
    
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
        results_dir = Path("ocr_data") / "results" / project.name
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_name_stem = Path(job.pdf_file).stem
        output_filename = f"{pdf_name_stem}_{timestamp}_batch.json"
        output_path = results_dir / output_filename
        
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
