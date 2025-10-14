"""
Projects page - manage OCR projects, upload PDFs, process files
"""
import streamlit as st
import json
from datetime import datetime
from pathlib import Path

from ui.storage import DataStore
from ui.models import Project
from ui.batch_utils import (
    submit_batch_job_ui, 
    update_batch_job_status_ui,
    download_and_convert_batch_results_ui,
    get_job_status_badge
)
from ui.utils import (
    ensure_cleared_file_state,
    get_result_files,
    get_file_status_badge,
    show_confirmation_dialog,
    create_download_popover,
    create_combined_download_popover
)
from ui.constants import (
    ICON_FOLDER, ICON_DESCRIPTION, ICON_PLAY_CIRCLE, ICON_INBOX,
    ICON_LIST_ALT, ICON_DOWNLOAD, ICON_DELETE, ICON_DELETE_FOREVER,
    ICON_CHECK_CIRCLE, ICON_FOLDER_OPEN, ICON_SCHEDULE, ICON_LIGHTBULB,
    ICON_HOURGLASS, ICON_VISIBILITY, ICON_ERROR, ICON_REFRESH,
    RESULTS_DIR, BATCH_DIR, UPLOADS_DIR
)
from table_ocr.direct import ocr_pdf

# Initialize data store
store = DataStore()

# Clear file viewing state when navigating to this page
ensure_cleared_file_state()

st.header("Projects")

# Create new project section
with st.expander("Create New Project"):
    new_project_name = st.text_input("Project Name", key="new_project_name")
    
    # Get available prompts and schemas
    prompts = store.get_prompts()
    schemas = store.get_schemas()
    
    if not prompts:
        st.warning("No prompts available. Please create a prompt first.")
    if not schemas:
        st.warning("No schemas available. Please create a schema first.")
    
    if prompts and schemas:
        selected_prompt = st.selectbox(
            "Select Prompt",
            [p.name for p in prompts],
            key="new_project_prompt"
        )
        selected_schema = st.selectbox(
            "Select Schema",
            [s.name for s in schemas],
            key="new_project_schema"
        )
        
        if st.button("Create Project"):
            if new_project_name:
                project = Project(
                    name=new_project_name,
                    prompt_name=selected_prompt,
                    schema_name=selected_schema
                )
                store.save_project(project)
                st.success(f"Project '{new_project_name}' created!")
                st.rerun()
            else:
                st.error("Please enter a project name")

# List existing projects
projects = store.get_projects()

if not projects:
    st.info("No projects yet. Create one above!")
else:
    for project in projects:
        with st.expander(f"{ICON_FOLDER} {project.name}"):
            # Constrain width for better readability
            container = st.container()
            with container:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Prompt:** {project.prompt_name}")
                    st.write(f"**Schema:** {project.schema_name}")
                    st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                # Processing Mode Selector (compact)
                processing_mode = st.radio(
                        "**Processing Mode:**",
                        ["Direct", "Batch"],
                        key=f"processing_mode_{project.name}",
                        horizontal=True,
                    )
                
                # Display mode descriptions
                if processing_mode == "Direct":
                    st.caption("⚡ **Direct:** Fast synchronous processing with immediate results (full API cost)")
                else:
                    st.caption("💰 **Batch:** Asynchronous processing with 50% cost savings (~24 hour completion time)")
            
            # PDF upload
            st.subheader("Upload PDF Files")
            uploaded_file = st.file_uploader(
                "Upload PDF Files",
                type="pdf",
                key=f"upload_{project.name}",
                label_visibility="collapsed"
            )
            
            if uploaded_file:
                # Save uploaded file
                upload_dir = UPLOADS_DIR / project.name
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = upload_dir / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Add to project
                if str(file_path) not in project.pdf_files:
                    project.pdf_files.append(str(file_path))
                    store.save_project(project)
                    st.success(f"Added {uploaded_file.name} to project")
            
            # List files (compact)
            if project.pdf_files:
                    st.subheader(f"Files in Project ({len(project.pdf_files)})")
                    
                    # Container for active processing jobs
                    processing_container = st.container()
                    
                    for idx, pdf_path in enumerate(project.pdf_files):
                        file_name = Path(pdf_path).name
                        
                        # Check if results exist for this file
                        result_files = get_result_files(project.name, pdf_path)
                        
                        # Status indicator
                        status_badge, status_color = get_file_status_badge(result_files)
                        
                        col_name, col_buttons = st.columns([3, 3])
                        with col_name:
                            st.markdown(f"{ICON_DESCRIPTION} **{file_name}** :{status_color}[{status_badge}]")
                        with col_buttons:
                            btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 2, 1, 1])
                            with btn_col1:
                                # Change button text based on processing mode
                                if processing_mode == "Direct":
                                    button_label = f"{ICON_PLAY_CIRCLE} Process"
                                else:
                                    button_label = f"{ICON_INBOX} Submit"
                                
                                # Check if currently processing this file
                                is_processing = st.session_state.get(f"processing_{project.name}_{idx}", False)
                                
                                if st.button(button_label, key=f"process_{project.name}_{idx}", 
                                           use_container_width=True, disabled=is_processing):
                                    st.session_state[f"processing_{project.name}_{idx}"] = True
                                    st.rerun()
                        
                            with btn_col2:
                                if st.button(f"{ICON_LIST_ALT} View", key=f"details_{project.name}_{idx}", disabled=not result_files,
                                           use_container_width=True):
                                    st.session_state.viewing_file = pdf_path
                                    st.session_state.viewing_project = project.name
                                    st.switch_page(st.session_state.pages['file_details'])
                            
                            with btn_col3:
                                # Download button - only show if results exist
                                schema = store.get_schema(project.schema_name)
                                create_download_popover(
                                    result_files,
                                    schema,
                                    key_prefix=f"download_{project.name}_{idx}"
                                )
                            
                            with btn_col4:
                                if st.button(f"{ICON_DELETE}", key=f"remove_{project.name}_{idx}", 
                                           use_container_width=True):
                                    # Store file to delete in session state and show confirmation
                                    st.session_state[f"confirm_remove_{project.name}_{idx}"] = True
                                    st.rerun()
                                
                                # Confirmation dialog
                                if st.session_state.get(f"confirm_remove_{project.name}_{idx}", False):
                                    @st.dialog("Confirm Removal")
                                    def confirm_remove_file():
                                        st.write(f"Are you sure you want to remove **{file_name}** from this project?")
                                        st.warning("This will remove the file from the project and delete all related OCR results.")
                                        st.info("The original PDF file will remain in the uploads folder.")
                                        
                                        # Show what will be deleted
                                        if result_files:
                                            st.caption(f"**{len(result_files)} result file(s) will be deleted:**")
                                            for rf in result_files[:5]:  # Show first 5
                                                st.caption(f"- {rf.name}")
                                            if len(result_files) > 5:
                                                st.caption(f"... and {len(result_files) - 5} more")
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("Yes, Remove", use_container_width=True, type="primary"):
                                                # Remove file from project
                                                project.pdf_files.remove(pdf_path)
                                                
                                                # Delete all result files for this PDF
                                                for result_file in result_files:
                                                    try:
                                                        result_file.unlink()
                                                    except Exception as e:
                                                        st.error(f"Failed to delete {result_file.name}: {e}")
                                                
                                                # Also remove any related batch jobs
                                                project.batch_jobs = [
                                                    job for job in project.batch_jobs 
                                                    if job.pdf_file != pdf_path
                                                ]
                                                
                                                store.save_project(project)
                                                st.session_state[f"confirm_remove_{project.name}_{idx}"] = False
                                                st.rerun()
                                        with col2:
                                            if st.button("Cancel", use_container_width=True):
                                                st.session_state[f"confirm_remove_{project.name}_{idx}"] = False
                                                st.rerun()
                                    confirm_remove_file()
                    
                    # ===== ACTIVE PROCESSING SECTION =====
                    # Show processing status for any files currently being processed
                    with processing_container:
                        for idx, pdf_path in enumerate(project.pdf_files):
                            if st.session_state.get(f"processing_{project.name}_{idx}", False):
                                file_name = Path(pdf_path).name
                                
                                with st.container(border=True):
                                    st.markdown(f"### {ICON_HOURGLASS} Processing: {file_name}")
                                    
                                    # Get prompt and schema
                                    prompt_obj = store.get_prompt(project.prompt_name)
                                    schema_obj = store.get_schema(project.schema_name)
                                    
                                    if prompt_obj and schema_obj:
                                        genai_schema = schema_obj.to_genai_schema()
                                        
                                        if processing_mode == "Direct":
                                            # ===== DIRECT PROCESSING =====
                                            # Create results directory
                                            results_dir = RESULTS_DIR / project.name
                                            results_dir.mkdir(parents=True, exist_ok=True)
                                            
                                            # Generate output filename with timestamp
                                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                            pdf_name_stem = Path(pdf_path).stem
                                            output_filename = f"{pdf_name_stem}_{timestamp}.json"
                                            output_path = results_dir / output_filename
                                            
                                            # Create progress bar and status text
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()
                                            
                                            try:
                                                # Define progress callback
                                                def update_progress(current, total):
                                                    progress = current / total
                                                    progress_bar.progress(progress)
                                                    status_text.text(f"Processing page {current} of {total}...")
                                                
                                                # Process PDF with progress tracking
                                                status_text.text("Starting PDF processing...")
                                                results = ocr_pdf(
                                                    pdf_path=pdf_path,
                                                    prompt_template=prompt_obj.content,
                                                    response_schema=genai_schema,
                                                    stream_output=False,
                                                    progress_callback=update_progress
                                                )
                                                
                                                # Save results to file
                                                output_data = {
                                                    "project": project.name,
                                                    "pdf_file": file_name,
                                                    "prompt": prompt_obj.name,
                                                    "schema": schema_obj.name,
                                                    "timestamp": timestamp,
                                                    "processing_mode": "direct",
                                                    "num_pages": len(results),
                                                    "results": results
                                                }
                                                
                                                with open(output_path, 'w') as f:
                                                    json.dump(output_data, f, indent=2)
                                                
                                                # Clear progress indicators
                                                progress_bar.empty()
                                                status_text.empty()
                                                
                                                # Show success message with file path
                                                st.success(f"{ICON_CHECK_CIRCLE} Processed {len(results)} pages!")
                                                st.info(f"{ICON_FOLDER_OPEN} Results saved to: `{output_path}`")
                                                
                                                # Clear processing state
                                                st.session_state[f"processing_{project.name}_{idx}"] = False
                                                    
                                            except Exception as e:
                                                progress_bar.empty()
                                                status_text.empty()
                                                st.error(f"Error processing file: {e}")
                                                
                                                # Clear processing state on error
                                                st.session_state[f"processing_{project.name}_{idx}"] = False
                                        
                                        else:
                                            # ===== BATCH PROCESSING =====
                                            try:
                                                with st.spinner("Submitting batch job..."):
                                                    batch_job = submit_batch_job_ui(
                                                        project=project,
                                                        pdf_path=pdf_path,
                                                        prompt_content=prompt_obj.content,
                                                        genai_schema=genai_schema
                                                    )
                                                
                                                st.success(f"{ICON_CHECK_CIRCLE} Batch job submitted successfully!")
                                                st.info(f"{ICON_INBOX} Job Name: `{batch_job.job_name}`")
                                                st.info(f"{ICON_SCHEDULE} Expected completion: ~24 hours")
                                                st.info(f"{ICON_LIGHTBULB} Check the **Batch Jobs** section below to monitor status")
                                                
                                                # Clear processing state
                                                st.session_state[f"processing_{project.name}_{idx}"] = False
                                                
                                            except Exception as e:
                                                st.error(f"Error submitting batch job: {e}")
                                                import traceback
                                                st.code(traceback.format_exc())
                                                
                                                # Clear processing state on error
                                                st.session_state[f"processing_{project.name}_{idx}"] = False
            
            # ===== BATCH JOBS SECTION =====
            if project.batch_jobs:
                st.markdown("---")
                with st.expander(f"{ICON_INBOX} Batch Jobs ({len(project.batch_jobs)})", expanded=False):
                    # Refresh all jobs button
                    col_refresh, col_spacer = st.columns([1, 3])
                    with col_refresh:
                        if st.button(f"{ICON_REFRESH} Refresh All", key=f"refresh_jobs_{project.name}", use_container_width=True):
                            for idx in range(len(project.batch_jobs)):
                                update_batch_job_status_ui(project, idx)
                            st.rerun()
                    
                    # Display each batch job in compact format
                    for job_idx, job in enumerate(project.batch_jobs):
                        file_name = Path(job.pdf_file).name
                        emoji, color, status_text_display = get_job_status_badge(job.status)
                        
                        # Compact layout
                        cols = st.columns([3, 2])
                        
                        with cols[0]:
                            # File and status in one line
                            st.markdown(f"**{file_name}**  \n:{color}[{emoji} {status_text_display}]")
                            # Batch name below file name
                            st.caption(f"Batch: `{job.job_name}`")
                            # Compact timestamp
                            time_str = job.created_at.strftime('%m/%d %H:%M')
                            if job.completed_at:
                                time_str += f" → {job.completed_at.strftime('%m/%d %H:%M')}"
                            st.caption(time_str)
                        
                        with cols[1]:
                            # Action buttons with text
                            action_cols = st.columns(2)
                            
                            with action_cols[0]:
                                if job.status == "JOB_STATE_SUCCEEDED":
                                    if job.result_file_path:
                                        if st.button(f"{ICON_VISIBILITY} View", key=f"view_{project.name}_{job_idx}", 
                                                   use_container_width=True):
                                            st.session_state.viewing_file = job.pdf_file
                                            st.session_state.viewing_project = project.name
                                            st.switch_page(st.session_state.pages['file_details'])
                                    else:
                                        if st.button(f"{ICON_DOWNLOAD} Download", key=f"dl_{project.name}_{job_idx}", 
                                                   use_container_width=True):
                                            with st.spinner("Downloading..."):
                                                try:
                                                    download_and_convert_batch_results_ui(project, job_idx)
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Failed: {e}")
                                elif job.status == "JOB_STATE_FAILED" and job.error_message:
                                    if st.button(f"{ICON_ERROR} Error", key=f"err_{project.name}_{job_idx}", 
                                               use_container_width=True):
                                        st.error(job.error_message)
                            
                            with action_cols[1]:
                                if st.button(f"{ICON_DELETE} Remove", key=f"rm_{project.name}_{job_idx}", 
                                           use_container_width=True):
                                    st.session_state[f"confirm_rm_{project.name}_{job_idx}"] = True
                                    st.rerun()
                                
                                # Confirmation dialog
                                if st.session_state.get(f"confirm_rm_{project.name}_{job_idx}", False):
                                    @st.dialog("Confirm Removal")
                                    def confirm_remove_batch():
                                        # Collect files to delete
                                        files_to_delete = []
                                        if job.result_file_path and Path(job.result_file_path).exists():
                                            files_to_delete.append(Path(job.result_file_path))
                                        
                                        # Also check for JSONL files in batch directory
                                        batch_dir = BATCH_DIR / project.name
                                        if batch_dir.exists():
                                            jsonl_files = list(batch_dir.glob(f"*{job.job_name}*.jsonl"))
                                            files_to_delete.extend(jsonl_files)
                                        
                                        details = [f"Job: {job.job_name}"]
                                        if files_to_delete:
                                            details.append(f"**{len(files_to_delete)} file(s) will be deleted:**")
                                            for f in files_to_delete[:5]:
                                                details.append(f"- {f.name}")
                                            if len(files_to_delete) > 5:
                                                details.append(f"... and {len(files_to_delete) - 5} more")
                                        
                                        def on_confirm():
                                            # Delete associated files
                                            for file_path in files_to_delete:
                                                try:
                                                    file_path.unlink()
                                                except Exception as e:
                                                    st.error(f"Failed to delete {file_path.name}: {e}")
                                            
                                            # Remove job from project
                                            project.batch_jobs.pop(job_idx)
                                            store.save_project(project)
                                            st.session_state[f"confirm_rm_{project.name}_{job_idx}"] = False
                                            st.rerun()
                                        
                                        show_confirmation_dialog(
                                            title="Confirm Removal",
                                            message="Are you sure you want to remove this batch job?",
                                            on_confirm=on_confirm,
                                            warning_text="This will remove the job from the project list and delete any downloaded result files.",
                                            details=details
                                        )
                                    confirm_remove_batch()
            
            # Download all and Delete project buttons
            btn_col1, btn_col2, btn_spacer = st.columns([1, 1, 2])
            
            with btn_col1:
                # Check if any results exist
                results_dir = RESULTS_DIR / project.name
                all_result_files = []
                if results_dir.exists():
                    all_result_files = list(results_dir.glob("*.json"))
                
                # Download all button with popover
                if all_result_files:
                    schema = store.get_schema(project.schema_name)
                    with st.popover(f"{ICON_DOWNLOAD} Download All Results", use_container_width=True):
                        create_combined_download_popover(
                            all_result_files,
                            schema,
                            project.name,
                            key_prefix=f"download_all_{project.name}"
                        )
                else:
                    st.button(f"{ICON_DOWNLOAD} Download All Results", disabled=True, use_container_width=True)
            
            with btn_col2:
                if st.button(f"{ICON_DELETE_FOREVER} Delete Project", key=f"delete_{project.name}", use_container_width=True):
                    st.session_state[f"confirm_delete_{project.name}"] = True
                    st.rerun()
                
                # Confirmation dialog
                if st.session_state.get(f"confirm_delete_{project.name}", False):
                    @st.dialog("Confirm Project Deletion")
                    def confirm_delete_project():
                        # Count files that will be deleted
                        files_to_delete_count = 0
                        results_dir = RESULTS_DIR / project.name
                        batch_dir = BATCH_DIR / project.name
                        
                        if results_dir.exists():
                            files_to_delete_count += len(list(results_dir.glob("*.json")))
                        if batch_dir.exists():
                            files_to_delete_count += len(list(batch_dir.glob("*.jsonl")))
                        
                        details = []
                        if files_to_delete_count > 0:
                            details.append(f"**{files_to_delete_count} result/batch file(s) will be deleted**")
                        
                        def on_confirm():
                            import shutil
                            # Delete result files
                            if results_dir.exists():
                                try:
                                    shutil.rmtree(results_dir)
                                except Exception as e:
                                    st.error(f"Failed to delete results directory: {e}")
                            
                            # Delete batch files
                            if batch_dir.exists():
                                try:
                                    shutil.rmtree(batch_dir)
                                except Exception as e:
                                    st.error(f"Failed to delete batch directory: {e}")
                            
                            # Delete project configuration
                            store.delete_project(project.name)
                            st.session_state[f"confirm_delete_{project.name}"] = False
                            st.success(f"Deleted project '{project.name}'")
                            st.rerun()
                        
                        show_confirmation_dialog(
                            title="Confirm Project Deletion",
                            message=f"Are you sure you want to delete project **{project.name}**?",
                            on_confirm=on_confirm,
                            error_text="⚠️ This action cannot be undone!",
                            warning_text="This will delete the project configuration, all OCR results, and batch data.",
                            info_text="Original PDF files in the uploads folder will be preserved.",
                            details=details
                        )
                    confirm_delete_project()
