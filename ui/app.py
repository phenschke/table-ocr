"""
Streamlit UI for Table OCR project management.
Fully vibe-coded -- don't judge.
"""
import streamlit as st
from streamlit_option_menu import option_menu
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path to find table_ocr package
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import from table_ocr core package
from table_ocr.direct import ocr_pdf
from table_ocr.batch import create_batch_ocr_job, get_job_state, download_batch_results_file, parse_pdf_batch_results_file

# Import from ui package
from ui.storage import DataStore
from ui.models import Project, Prompt, OutputSchema, SchemaField, BatchJob
from ui.dataframe_utils import load_results_as_dataframe, load_page_as_dataframe

# Initialize data store
store = DataStore()

# Page configuration
st.set_page_config(
    page_title="Table OCR Manager",
    page_icon="�️",
    layout="wide"
)

# Add custom CSS for max-width on project content and Bootstrap icons
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
<style>
    /* Limit width of project expanders for better readability */
    .stExpander {
        max-width: 1200px;
    }
    /* Ensure buttons don't get too stretched */
    .stButton > button {
        white-space: nowrap;
    }
    /* Bootstrap icon styling */
    .bi {
        margin-right: 0.3em;
    }
</style>
""", unsafe_allow_html=True)

st.title("Table OCR Manager")

# Initialize session state for page navigation and file details
if 'page' not in st.session_state:
    st.session_state.page = "Projects"
if 'viewing_file' not in st.session_state:
    st.session_state.viewing_file = None
if 'viewing_project' not in st.session_state:
    st.session_state.viewing_project = None


# ===== BATCH PROCESSING HELPER FUNCTIONS =====

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
                from table_ocr.core import GeminiClient
                try:
                    client = GeminiClient()
                    batch_job_obj = client.client.batches.get(name=job.job_name)
                    job.error_message = str(getattr(batch_job_obj, 'error', 'Unknown error'))
                except Exception as e:
                    job.error_message = f"Failed to fetch error details: {e}"
            
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

# Sidebar navigation with option menu
# Only show main pages in navigation - File Details is accessed via Details button
with st.sidebar:
    if st.session_state.page == "File Details":
        # If we're on File Details page, show navigation but don't let it change the page
        option_menu(
            menu_title=None,
            options=["Projects", "Prompts", "Schemas"],
            icons=["folder", "chat-text", "table"],
            menu_icon="grid-3x3-gap-fill",
            default_index=0,
            key="nav_menu_disabled",
            styles={
                "container": {"padding": "5px", "background-color": "#0e1117"},
                "icon": {"color": "#808495", "font-size": "18px"}, 
                "nav-link": {
                    "font-size": "15px", 
                    "text-align": "left", 
                    "margin": "2px 0px",
                    "padding": "10px 15px",
                    "border-radius": "5px",
                    "color": "#808495"
                },
                "nav-link-selected": {
                    "background-color": "#1f2937",
                    "color": "#fafafa",
                    "font-weight": "500"
                },
                "menu-title": {
                    "font-size": "18px",
                    "font-weight": "600",
                    "color": "#fafafa",
                    "padding": "10px 15px 15px 15px"
                }
            }
        )
        st.info(":material/info: Use the Back button to return to Projects")
        page = "File Details"  # Keep showing File Details page
    else:
        # Normal navigation for main pages
        default_index = 0
        if st.session_state.page in ["Projects", "Prompts", "Schemas"]:
            default_index = ["Projects", "Prompts", "Schemas"].index(st.session_state.page)
        
        page = option_menu(
            menu_title=None,
            options=["Projects", "Prompts", "Schemas"],
            icons=["folder", "chat-text", "table"],
            menu_icon="grid-3x3-gap-fill",
            default_index=default_index,
            key="nav_menu",
            styles={
                "container": {"padding": "5px", "background-color": "#0e1117"},
                "icon": {"color": "#83c5be", "font-size": "18px"}, 
                "nav-link": {
                    "font-size": "15px", 
                    "text-align": "left", 
                    "margin": "2px 0px",
                    "padding": "10px 15px",
                    "border-radius": "5px",
                    "transition": "all 0.2s ease"
                },
                "nav-link-selected": {
                    "background-color": "#1f2937",
                    "color": "#fafafa",
                    "font-weight": "500",
                    "box-shadow": "0 1px 3px rgba(0,0,0,0.3)"
                },
                "nav-link:hover": {
                    "background-color": "#262730"
                },
                "menu-title": {
                    "font-size": "18px",
                    "font-weight": "600",
                    "color": "#fafafa",
                    "padding": "10px 15px 15px 15px"
                }
            }
        )
        st.session_state.page = page

# Projects Page
if page == "Projects":
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
    st.subheader("Existing Projects")
    projects = store.get_projects()
    
    if not projects:
        st.info("No projects yet. Create one above!")
    else:
        for project in projects:
            with st.expander(f":material/folder: {project.name}"):
                # Constrain width for better readability
                container = st.container()
                with container:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Prompt:** {project.prompt_name}")
                        st.write(f"**Schema:** {project.schema_name}")
                        st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Processing Mode Selector (compact)
                    st.markdown("**Processing Mode**")
                    processing_mode = st.radio(
                        "mode",
                        ["Direct Processing", "Batch Processing"],
                        key=f"processing_mode_{project.name}",
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    
                    # Display mode descriptions
                    if processing_mode == "Direct Processing":
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
                    upload_dir = Path("ocr_data") / "uploads" / project.name
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
                        for idx, pdf_path in enumerate(project.pdf_files):
                            file_name = Path(pdf_path).name
                            
                            # Check if results exist for this file
                            results_dir = Path("ocr_data") / "results" / project.name
                            pdf_stem = Path(pdf_path).stem
                            has_results = False
                            result_files = []
                            if results_dir.exists():
                                result_files = list(results_dir.glob(f"{pdf_stem}_*.json"))
                                has_results = len(result_files) > 0
                            
                            # Status indicator
                            if has_results:
                                status_badge = f"✅ ({len(result_files)})"
                                status_color = "green"
                            else:
                                status_badge = "⏸️"
                                status_color = "orange"
                            
                            col_name, col_buttons = st.columns([3, 2])
                            with col_name:
                                st.markdown(f":material/description: **{file_name}** :{status_color}[{status_badge}]")
                            with col_buttons:
                                btn_col1, btn_col2, btn_col3 = st.columns(3)
                                with btn_col1:
                                    # Change button text based on processing mode
                                    if processing_mode == "Direct Processing":
                                        button_label = ":material/play_circle: Process"
                                    else:
                                        button_label = ":material/inbox: Submit"
                                    
                                    if st.button(button_label, key=f"process_{project.name}_{idx}", 
                                               use_container_width=True):
                                        # Get prompt and schema
                                        prompt_obj = store.get_prompt(project.prompt_name)
                                        schema_obj = store.get_schema(project.schema_name)
                                        
                                        if prompt_obj and schema_obj:
                                            genai_schema = schema_obj.to_genai_schema()
                                            
                                            if processing_mode == "Direct Processing":
                                                # ===== DIRECT PROCESSING =====
                                                # Create results directory
                                                results_dir = Path("ocr_data") / "results" / project.name
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
                                                    st.success(f":material/check_circle: Processed {len(results)} pages!")
                                                    st.info(f":material/folder_open: Results saved to: `{output_path}`")
                                                    
                                                    # Display results
                                                    with st.expander("View Results"):
                                                        st.json(results)
                                                    
                                                    # Offer download button
                                                    with open(output_path, 'r') as f:
                                                        st.download_button(
                                                            label=":material/download: Download Results",
                                                            data=f.read(),
                                                            file_name=output_filename,
                                                            mime="application/json",
                                                            key=f"download_{project.name}_{file_name}"
                                                        )
                                                        
                                                except Exception as e:
                                                    progress_bar.empty()
                                                    status_text.empty()
                                                    st.error(f"Error processing file: {e}")
                                            
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
                                                    
                                                    st.success(":material/check_circle: Batch job submitted successfully!")
                                                    st.info(f":material/inbox: Job Name: `{batch_job.job_name}`")
                                                    st.info(":material/schedule: Expected completion: ~24 hours")
                                                    st.info(":material/lightbulb: Check the **Batch Jobs** section below to monitor status")
                                                    
                                                except Exception as e:
                                                    st.error(f"Error submitting batch job: {e}")
                                                    import traceback
                                                    st.code(traceback.format_exc())
                            
                                with btn_col2:
                                    if st.button(":material/list_alt: Details", key=f"details_{project.name}_{idx}", disabled=not has_results,
                                               use_container_width=True):
                                        st.session_state.viewing_file = pdf_path
                                        st.session_state.viewing_project = project.name
                                        st.session_state.page = "File Details"
                                        st.rerun()
                                
                                with btn_col3:
                                    if st.button(":material/delete: Remove", key=f"remove_{project.name}_{idx}", 
                                               use_container_width=True):
                                        # Remove file from project
                                        project.pdf_files.remove(pdf_path)
                                        store.save_project(project)
                                        st.rerun()
                
                # ===== BATCH JOBS SECTION =====
                if project.batch_jobs:
                    st.markdown("---")
                    with st.expander(f":material/inbox: Batch Jobs ({len(project.batch_jobs)})", expanded=False):
                        # Refresh all jobs button
                        col_refresh, col_spacer = st.columns([1, 3])
                        with col_refresh:
                            if st.button(":material/refresh: Refresh All", key=f"refresh_jobs_{project.name}", use_container_width=True):
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
                                            if st.button(":material/visibility: View", key=f"view_{project.name}_{job_idx}", 
                                                       use_container_width=True):
                                                st.session_state.viewing_file = job.pdf_file
                                                st.session_state.viewing_project = project.name
                                                st.session_state.page = "File Details"
                                                st.rerun()
                                        else:
                                            if st.button(":material/download: Download", key=f"dl_{project.name}_{job_idx}", 
                                                       use_container_width=True):
                                                with st.spinner("Downloading..."):
                                                    try:
                                                        download_and_convert_batch_results_ui(project, job_idx)
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(f"Failed: {e}")
                                    elif job.status == "JOB_STATE_FAILED" and job.error_message:
                                        if st.button(":material/error: Error", key=f"err_{project.name}_{job_idx}", 
                                                   use_container_width=True):
                                            st.error(job.error_message)
                                
                                with action_cols[1]:
                                    if st.button(":material/delete: Remove", key=f"rm_{project.name}_{job_idx}", 
                                               use_container_width=True):
                                        project.batch_jobs.pop(job_idx)
                                        store.save_project(project)
                                        st.rerun()
                
                # Delete project
                if st.button(":material/delete_forever: Delete Project", key=f"delete_{project.name}"):
                        store.delete_project(project.name)
                        st.success(f"Deleted project '{project.name}'")
                        st.rerun()

# Prompts Page
elif page == "Prompts":
    st.header("Prompts")
    
    # Create new prompt
    with st.expander("Create New Prompt"):
        new_prompt_name = st.text_input("Prompt Name", key="new_prompt_name")
        new_prompt_content = st.text_area(
            "Prompt Content",
            height=200,
            key="new_prompt_content",
            help="Enter the instruction text for the OCR task"
        )
        
        if st.button("Create Prompt"):
            if new_prompt_name and new_prompt_content:
                prompt = Prompt(name=new_prompt_name, content=new_prompt_content)
                store.save_prompt(prompt)
                st.success(f"Prompt '{new_prompt_name}' created!")
                st.rerun()
            else:
                st.error("Please fill in all fields")
    
    # List existing prompts
    st.subheader("Existing Prompts")
    prompts = store.get_prompts()
    
    if not prompts:
        st.info("No prompts yet. Create one above!")
    else:
        for prompt in prompts:
            with st.expander(f":material/chat: {prompt.name}"):
                st.text_area(
                    "Content",
                    value=prompt.content,
                    height=150,
                    key=f"view_prompt_{prompt.name}",
                    disabled=True
                )
                st.write(f"**Created:** {prompt.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                if st.button(":material/delete: Delete", key=f"delete_prompt_{prompt.name}"):
                    store.delete_prompt(prompt.name)
                    st.success(f"Deleted prompt '{prompt.name}'")
                    st.rerun()

# Schemas Page
elif page == "Schemas":
    st.header("Output Schemas")
    
    # Create new schema
    with st.expander("Create New Schema"):
        new_schema_name = st.text_input("Schema Name", key="new_schema_name")
        
        st.subheader("Fields")
        
        # Initialize session state for fields
        if 'schema_fields' not in st.session_state:
            st.session_state.schema_fields = []
        
        # Add field button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(":material/add: Add Field"):
                st.session_state.schema_fields.append({
                    "name": "",
                    "type": "STRING",
                    "required": False
                })
        
        # Display fields
        fields_to_create = []
        for i, field_data in enumerate(st.session_state.schema_fields):
            col_a, col_b, col_c, col_d = st.columns([3, 2, 1, 1])
            
            with col_a:
                field_name = st.text_input(
                    "Field Name",
                    value=field_data.get("name", ""),
                    key=f"field_name_{i}",
                    label_visibility="collapsed",
                    placeholder="Field name"
                )
            
            with col_b:
                field_type = st.selectbox(
                    "Type",
                    ["STRING", "INTEGER", "BOOLEAN", "NUMBER"],
                    index=["STRING", "INTEGER", "BOOLEAN", "NUMBER"].index(
                        field_data.get("type", "STRING")
                    ),
                    key=f"field_type_{i}",
                    label_visibility="collapsed"
                )
            
            with col_c:
                field_required = st.checkbox(
                    "Required",
                    value=field_data.get("required", False),
                    key=f"field_required_{i}"
                )
            
            with col_d:
                if st.button(":material/delete:", key=f"remove_field_{i}"):
                    st.session_state.schema_fields.pop(i)
                    st.rerun()
            
            if field_name:
                fields_to_create.append(SchemaField(
                    name=field_name,
                    field_type=field_type,
                    required=field_required
                ))
        
        if st.button("Create Schema"):
            if new_schema_name and fields_to_create:
                schema = OutputSchema(name=new_schema_name, fields=fields_to_create)
                store.save_schema(schema)
                st.success(f"Schema '{new_schema_name}' created!")
                st.session_state.schema_fields = []
                st.rerun()
            else:
                st.error("Please enter a schema name and add at least one field")
    
    # List existing schemas
    st.subheader("Existing Schemas")
    schemas = store.get_schemas()
    
    if not schemas:
        st.info("No schemas yet. Create one above!")
    else:
        for schema in schemas:
            with st.expander(f":material/table_chart: {schema.name}"):
                st.write(f"**Created:** {schema.created_at.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Fields:** {len(schema.fields)}")
                
                # Display fields as table
                if schema.fields:
                    st.subheader("Fields:")
                    for field in schema.fields:
                        required_mark = "✓" if field.required else ""
                        st.write(f"- **{field.name}** ({field.field_type}) {required_mark}")
                
                if st.button(":material/delete: Delete", key=f"delete_schema_{schema.name}"):
                    store.delete_schema(schema.name)
                    st.success(f"Deleted schema '{schema.name}'")
                    st.rerun()

# File Details Page
elif page == "File Details":
    if st.session_state.viewing_file is None or st.session_state.viewing_project is None:
        st.warning("No file selected. Please go to Projects and select a file to view details.")
        if st.button("← Go to Projects"):
            st.session_state.page = "Projects"
            st.rerun()
    else:
        pdf_path = st.session_state.viewing_file
        project_name = st.session_state.viewing_project
        file_name = Path(pdf_path).name
        
        # Header with back button
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button(":material/arrow_back: Back"):
                st.session_state.page = "Projects"
                st.rerun()
        with col2:
            st.header(f":material/description: File Details: {file_name}")
        
        # Check if file exists
        if not Path(pdf_path).exists():
            st.error(f"File not found: {pdf_path}")
        else:
            # Get result files for this PDF
            results_dir = Path("ocr_data") / "results" / project_name
            pdf_stem = Path(pdf_path).stem
            result_files = []
            if results_dir.exists():
                result_files = sorted(list(results_dir.glob(f"{pdf_stem}_*.json")), 
                                     key=lambda x: x.stat().st_mtime, reverse=True)
            
            if not result_files:
                st.warning("No results found for this file. Please process it first.")
            else:
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
                    
                    # SECTION 1: Full File Data Preview (at the top)
                    if is_dataframe_serializable:
                        st.subheader(":material/analytics: Full File Data Preview")
                        
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
                            
                            # Show column info
                            with st.expander(":material/info: Column Information"):
                                col_info = []
                                for col_name in df.columns:
                                    dtype = str(df[col_name].dtype)
                                    col_info.append({"Column": col_name, "Type": dtype})
                                st.table(col_info)
                            
                            # Display interactive DataFrame
                            st.write("**Data Table:**")
                            st.dataframe(df, use_container_width=True, height=400)
                            
                            # CSV download button
                            csv_data = df.write_csv()
                            st.download_button(
                                label=":material/download: Download as CSV",
                                data=csv_data,
                                file_name=f"{pdf_stem}.csv",
                                mime="text/csv",
                                key="download_csv"
                            )
                        else:
                            st.info("No data available for preview.")
                        
                        st.markdown("---")
                    
                    # SECTION 2: Individual Page View
                    st.subheader(":material/description: Individual Page View")
                    
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
                                    st.dataframe(page_df, use_container_width=True, height=600)
                                    
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
                            
                            # Download button for this page's results
                            st.download_button(
                                label=f":material/download: Download Page {st.session_state.current_page} Results",
                                data=json.dumps(page_result, indent=2),
                                file_name=f"{pdf_stem}_page_{st.session_state.current_page}.json",
                                mime="application/json",
                                key="download_page_result"
                            )
                        else:
                            st.warning(f"No results for page {st.session_state.current_page}")
                    
                    # Download all results button
                    st.markdown("---")
                    st.download_button(
                        label=":material/download: Download All Results (JSON)",
                        data=json.dumps(result_data, indent=2),
                        file_name=selected_result_file.name,
                        mime="application/json",
                        key="download_all_results"
                    )
                    
                except Exception as e:
                    st.error(f"Error loading results: {e}")
                    import traceback
                    st.code(traceback.format_exc())


# Footer
st.sidebar.markdown("---")
st.sidebar.info("""
**Table OCR Manager**

Manage OCR projects with custom prompts and output schemas.
""")
