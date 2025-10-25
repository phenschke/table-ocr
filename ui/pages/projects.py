"""
Projects page - manage OCR projects, upload PDFs, process files.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st

from ui.batch_utils import (
    download_and_convert_batch_results_ui,
    get_batch_jobs_for_file,
    get_job_status_badge,
    get_latest_batch_job_for_file,
    submit_batch_job_ui,
    update_batch_job_status_ui,
)
from ui.components import ActionSpec, render_action_row, render_metadata_chips, render_status_badge
from ui.constants import (
    BATCH_DIR,
    ICON_ADD,
    ICON_CHECK_CIRCLE,
    ICON_CODE,
    ICON_DELETE,
    ICON_DELETE_FOREVER,
    ICON_DESCRIPTION,
    ICON_DOWNLOAD,
    ICON_EXPAND_LESS,
    ICON_EXPAND_MORE,
    ICON_EXPORT,
    ICON_FOLDER,
    ICON_FOLDER_OPEN,
    ICON_HOURGLASS,
    ICON_HOW_TO_VOTE,
    ICON_INBOX,
    ICON_LIGHTBULB,
    ICON_PLAY_CIRCLE,
    ICON_REFRESH,
    ICON_SCHEDULE,
    ICON_TABLE_CHART,
    ICON_VISIBILITY,
    RESULTS_DIR,
    UPLOADS_DIR,
)
from ui.feedback import error, info, success, warning
from ui.majority_vote import (
    can_create_majority_vote,
    create_majority_voted_result,
    is_majority_vote_file,
    majority_vote_exists,
)
from ui.models import Project
from ui.state import (
    clear_active_task,
    get_active_task,
    get_processing_state,
    get_project_mode,
    is_project_expanded,
    set_active_task,
    set_processing_state,
    set_project_mode,
    toggle_project_expansion,
)
from ui.storage import DataStore
from ui.utils import (
    clear_file_viewing_state,
    get_file_status_badge,
    get_next_result_path,
    get_result_files,
    set_viewing_state,
)
from table_ocr.direct import ocr_pdf_parallel

# Initialize data store
store = DataStore()

# Clear file viewing state when navigating to this page
clear_file_viewing_state()

# Add max-width styling for better readability on wide screens
st.markdown("""
    <style>
    .main .block-container {
        max-width: 700px;
    }
    </style>
""", unsafe_allow_html=True)

st.header("Projects")

# Flash any queued notifications
if flashes := st.session_state.pop("projects__flash_messages", None):
    for level, message in flashes:
        {
            "success": success,
            "info": info,
            "warning": warning,
            "error": error,
        }[level](message)


def queue_flash(level: str, message: str) -> None:
    """Queue a message to display after rerun."""
    st.session_state.setdefault("projects__flash_messages", []).append((level, message))


def sorted_projects(projects: List[Project]) -> List[Project]:
    return sorted(projects, key=lambda p: p.created_at, reverse=True)


def render_create_project_card() -> None:
    prompts = store.get_prompts()
    schemas = store.get_schemas()

    needs_prompt = len(prompts) == 0
    needs_schema = len(schemas) == 0

    with st.container(border=True):
        st.subheader(f"{ICON_ADD} Create Project")

        if needs_prompt:
            warning("You need at least one prompt before creating a project.")
        if needs_schema:
            warning("You need at least one schema before creating a project.")

        new_project_name = st.text_input("Project Name", key="projects.new_project_name")

        prompt_name = st.selectbox(
            "Prompt",
            options=[p.name for p in prompts] if prompts else [],
            key="projects.new_project_prompt",
            disabled=needs_prompt,
        )
        schema_name = st.selectbox(
            "Schema",
            options=[s.name for s in schemas] if schemas else [],
            key="projects.new_project_schema",
            disabled=needs_schema,
        )

        can_create = (
            new_project_name
            and not needs_prompt
            and not needs_schema
            and prompt_name
            and schema_name
        )

        if st.button(
            f"{ICON_CHECK_CIRCLE} Create Project",
            type="primary",
            use_container_width=False,
            disabled=not can_create,
        ):
            project = Project(
                name=new_project_name,
                prompt_name=prompt_name,
                schema_name=schema_name,
            )
            store.save_project(project)
            queue_flash("success", f"Project '{new_project_name}' created.")
            st.rerun()


def trigger_processing(project: Project, pdf_path: str, mode: str) -> None:
    set_processing_state(project.name, pdf_path, True)
    set_active_task(project.name, pdf_path, {"mode": mode})


def handle_direct_processing(project: Project, pdf_path: str, file_name: str) -> None:
    prompt = store.get_prompt(project.prompt_name)
    schema = store.get_schema(project.schema_name)

    if not prompt or not schema:
        error("Missing prompt or schema; cannot process this file.")
        set_processing_state(project.name, pdf_path, False)
        clear_active_task(project.name, pdf_path)
        return

    # Use Pydantic schema (google-genai SDK supports Pydantic directly)
    pydantic_schema = schema.to_pydantic_schema()
    output_path = get_next_result_path(project.name, pdf_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    progress_bar = st.progress(0)
    status_placeholder = st.empty()

    try:
        def update_progress(current: int, total: int) -> None:
            """Update progress bar with number of completed pages."""
            progress_bar.progress(current / total)
            status_placeholder.text(f"Completed {current} of {total} pages…")

        status_placeholder.text("Starting PDF processing with parallel API calls…")
        results = ocr_pdf_parallel(
            pdf_path=pdf_path,
            prompt_template=prompt.content,
            response_schema=pydantic_schema,
            progress_callback=update_progress,
            max_concurrent_requests=20,
        )

        status_placeholder.text(f"Processing complete. Saving results to {output_path}…")

        payload = {
            "project": project.name,
            "pdf_file": file_name,
            "prompt": prompt.name,
            "schema": schema.name,
            "timestamp": timestamp,
            "processing_mode": "direct",
            "num_pages": len(results),
            "results": results,
        }

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(payload, f, indent=2)

        status_placeholder.text(f"Results saved to {output_path}")
        queue_flash("success", f"Processed {len(results)} page(s) for {file_name}.")
        queue_flash("info", f"{ICON_FOLDER_OPEN} Results saved to `{output_path}`.")
    except Exception as exc:
        import traceback
        error(f"Error processing {file_name}: {exc}")
        error(f"Traceback: {traceback.format_exc()}")
    finally:
        progress_bar.empty()
        status_placeholder.empty()
        set_processing_state(project.name, pdf_path, False)
        clear_active_task(project.name, pdf_path)
        st.rerun()


def handle_batch_submission(project: Project, pdf_path: str, _file_name: str) -> None:
    prompt = store.get_prompt(project.prompt_name)
    schema = store.get_schema(project.schema_name)

    if not prompt or not schema:
        error("Missing prompt or schema; cannot submit batch job.")
        set_processing_state(project.name, pdf_path, False)
        clear_active_task(project.name, pdf_path)
        return

    # Use Pydantic schema (google-genai SDK supports Pydantic directly)
    pydantic_schema = schema.to_pydantic_schema()

    try:
        batch_job = submit_batch_job_ui(
            project=project,
            pdf_path=pdf_path,
            prompt_content=prompt.content,
            genai_schema=pydantic_schema,
        )

        queue_flash("success", f"Batch job '{batch_job.job_name}' submitted.")
        queue_flash("info", f"{ICON_SCHEDULE} Expect completion in ~24 hours.")
    except Exception as exc:
        import traceback
        error(f"Failed to submit batch job: {exc}")
        error(f"Traceback: {traceback.format_exc()}")
    finally:
        set_processing_state(project.name, pdf_path, False)
        clear_active_task(project.name, pdf_path)
        st.rerun()


def render_file_row(project: Project, pdf_path: str, processing_mode: str) -> None:
    file_name = Path(pdf_path).name
    result_files = get_result_files(project.name, pdf_path)
    badge_label, badge_variant = get_file_status_badge(result_files)
    is_processing = get_processing_state(project.name, pdf_path)

    # Get latest batch job for this file
    latest_batch = get_latest_batch_job_for_file(project, pdf_path)

    row = st.container()
    with row:
        file_cols = st.columns([4, 1, 1, 0.5, 0.5])

        # Column 0: File name and status
        with file_cols[0]:
            st.markdown(f"{ICON_DESCRIPTION} **{file_name}**")
            render_status_badge(badge_label, badge_variant)

            # Show batch status inline if there's an active batch job
            if latest_batch:
                job_idx, batch_job = latest_batch
                emoji, _color, status_text = get_job_status_badge(batch_job.status)

                # Only show batch status if job is not completed or if it's succeeded but not downloaded
                show_batch_status = (
                    batch_job.status not in ["JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"]
                    or (batch_job.status == "JOB_STATE_SUCCEEDED" and not batch_job.result_file_path)
                )

                if show_batch_status:
                    # Show different UI based on status
                    if batch_job.status == "JOB_STATE_SUCCEEDED" and not batch_job.result_file_path:
                        # Job succeeded but results not downloaded yet - show download button
                        batch_cols = st.columns([3.5, 1])
                        with batch_cols[0]:
                            st.caption(f"{emoji} Batch {status_text} - Ready to download")
                        with batch_cols[1]:
                            if st.button(
                                f"{ICON_DOWNLOAD} Download",
                                key=f"projects.download_batch_inline::{project.name}::{file_name}",
                                help="Download batch results",
                                use_container_width=True,
                            ):
                                try:
                                    download_and_convert_batch_results_ui(project, job_idx)
                                    queue_flash("success", f"Batch results downloaded for {file_name}")
                                    st.rerun()
                                except Exception as exc:
                                    error(f"Failed to download batch results: {exc}")
                    else:
                        # Job is pending/running - show refresh button
                        batch_cols = st.columns([4, 0.5])
                        with batch_cols[0]:
                            st.caption(f"{emoji} Batch {status_text}")
                        with batch_cols[1]:
                            if st.button(
                                ICON_REFRESH,
                                key=f"projects.refresh_batch::{project.name}::{file_name}",
                                help="Refresh batch job status",
                                use_container_width=True,
                            ):
                                update_batch_job_status_ui(project, job_idx)
                                st.rerun()

        # Column 1: View button
        with file_cols[1]:
            if st.button(
                f"{ICON_VISIBILITY} View",
                key=f"projects.view::{project.name}::{file_name}",
                use_container_width=True,
                disabled=not result_files,
            ):
                open_file_details(pdf_path, project.name)

        # Column 2: Process button
        with file_cols[2]:
            mode_label = ICON_PLAY_CIRCLE if processing_mode == "Direct" else ICON_INBOX
            process_label = f"{mode_label} {'Process' if processing_mode == 'Direct' else 'Submit'}"
            if st.button(
                process_label,
                key=f"projects.process::{project.name}::{file_name}",
                use_container_width=True,
                disabled=is_processing,
            ):
                trigger_processing(project, pdf_path, processing_mode)

        # Column 3: Download button with popover
        with file_cols[3]:
            if result_files:
                schema = store.get_schema(project.schema_name)
                latest_result = result_files[0]

                with st.popover(ICON_DOWNLOAD, use_container_width=True, help="Download results"):
                    # JSON download
                    with open(latest_result, 'r') as f:
                        result_content = f.read()
                    st.download_button(
                        label=f"{ICON_CODE} JSON",
                        data=result_content,
                        file_name=latest_result.name,
                        mime="application/json",
                        key=f"download_json::{project.name}::{file_name}",
                        use_container_width=True,
                    )

                    # CSV download
                    if schema and schema.is_dataframe_serializable():
                        from ui.dataframe_utils import load_results_as_dataframe
                        try:
                            df = load_results_as_dataframe(str(latest_result))
                            if df is not None and len(df) > 0:
                                csv_data = df.write_csv()
                                csv_filename = f"{latest_result.stem}.csv"
                                st.download_button(
                                    label=f"{ICON_TABLE_CHART} CSV",
                                    data=csv_data,
                                    file_name=csv_filename,
                                    mime="text/csv",
                                    key=f"download_csv::{project.name}::{file_name}",
                                    use_container_width=True,
                                )
                            else:
                                st.caption("CSV: No data available")
                        except Exception as e:
                            st.caption(f"CSV: Error - {str(e)[:30]}")
                    else:
                        st.caption("CSV: Not available for this schema")
            else:
                st.button(
                    ICON_DOWNLOAD,
                    disabled=True,
                    key=f"projects.download_disabled::{project.name}::{file_name}",
                    help="No results to download",
                    use_container_width=True,
                )

        # Column 4: Delete button
        with file_cols[4]:
            if st.button(
                ICON_DELETE,
                key=f"projects.remove_file::{project.name}::{file_name}",
                help="Remove file from project",
                use_container_width=True,
            ):
                st.session_state[
                    f"projects.confirm_remove_file::{project.name}::{file_name}"
                ] = True

    confirm_key = f"projects.confirm_remove_file::{project.name}::{file_name}"
    if st.session_state.get(confirm_key):
        @st.dialog("Confirm Removal")
        def show_removal_confirmation():
            details = []
            if result_files:
                details = [
                    f"File: **{file_name}**",
                    f"{len(result_files)} result file(s) will be deleted.",
                ]
            render_confirmation_modal_for_file(project, pdf_path, result_files, confirm_key, details)

        show_removal_confirmation()


def render_confirmation_modal_for_file(
    project: Project,
    pdf_path: str,
    result_files: List[Path],
    confirm_key: str,
    details: List[str],
) -> None:
    from ui.components import render_confirmation_modal

    def on_confirm() -> None:
        # Remove from project
        project.pdf_files = [f for f in project.pdf_files if f != pdf_path]
        store.save_project(project)

        # Delete result files
        for result in result_files:
            try:
                result.unlink(missing_ok=True)
            except Exception as exc:  # pragma: no cover - filesystem edge case
                error(f"Failed to delete {result.name}: {exc}")

        queue_flash("success", f"Removed {Path(pdf_path).name} from {project.name}.")
        st.session_state.pop(confirm_key, None)

    def on_cancel() -> None:
        st.session_state.pop(confirm_key, None)

    render_confirmation_modal(
        title="Confirm File Removal",
        message=f"Remove **{Path(pdf_path).name}** from project?",
        on_confirm=on_confirm,
        confirm_label="Yes, remove",
        cancel_label="Keep file",
        details=details,
        warning="Deletes processed results for this file. Source PDF remains in uploads.",
        danger=True,
        on_cancel=on_cancel,
        key=confirm_key,
    )


def open_file_details(pdf_path: str, project_name: str) -> None:
    set_viewing_state(pdf_path, project_name)
    st.switch_page(st.session_state.pages["file_details"])


def render_batch_jobs(project: Project) -> None:
    if not project.batch_jobs:
        return

    # Count active (non-completed) batch jobs
    active_jobs = sum(
        1 for job in project.batch_jobs
        if job.status not in ["JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"]
    )

    # Show expander with active job count, expand by default if there are active jobs
    total_count = len(project.batch_jobs)
    expander_label = f"{ICON_INBOX} Batch Jobs: {active_jobs} active, {total_count} total"

    st.markdown("---")
    with st.expander(expander_label, expanded=active_jobs > 0):
        header_cols = st.columns([1, 3])
        with header_cols[0]:
            if st.button(
                f"{ICON_REFRESH} Refresh All",
                key=f"projects.refresh_jobs::{project.name}",
                use_container_width=True,
            ):
                for idx in range(len(project.batch_jobs)):
                    update_batch_job_status_ui(project, idx)
                store.save_project(project)
                queue_flash("info", "Batch job statuses refreshed.")
                st.rerun()

        for job_idx, job in enumerate(project.batch_jobs):
            file_name = Path(job.pdf_file).name
            emoji, _color, status_text_display = get_job_status_badge(job.status)

            job_container = st.container(border=True)
            with job_container:
                cols = st.columns([3, 2])
                with cols[0]:
                    st.markdown(f"**{file_name}**")
                    render_status_badge(
                        f"{emoji} {status_text_display}",
                        "info",
                        icon="",
                    )
                    timeline = job.created_at.strftime("%m/%d %H:%M")
                    if job.completed_at:
                        timeline += f" → {job.completed_at.strftime('%m/%d %H:%M')}"
                    st.caption(f"Batch: `{job.job_name}` · {timeline}")

                with cols[1]:
                    actions: List[ActionSpec] = []
                    if job.status == "JOB_STATE_SUCCEEDED":
                        if job.result_file_path:
                            actions.append(
                                ActionSpec(
                                    label=f"{ICON_VISIBILITY} View",
                                    key=f"projects.batch_view::{project.name}::{job_idx}",
                                    on_click=lambda path=job.pdf_file, proj=project.name: open_file_details(
                                        path, proj
                                    ),
                                )
                            )
                        else:
                            actions.append(
                                ActionSpec(
                                    label=f"{ICON_DOWNLOAD} Download",
                                    key=f"projects.batch_download::{project.name}::{job_idx}",
                                    on_click=lambda p=project, j_idx=job_idx: download_batch_results(
                                        p, j_idx
                                    ),
                                )
                            )
                    elif job.status == "JOB_STATE_FAILED" and job.error_message:
                        actions.append(
                            ActionSpec(
                                label=f"{ICON_LIGHTBULB} Show Error",
                                key=f"projects.batch_error::{project.name}::{job_idx}",
                                on_click=lambda message=job.error_message: error(message),
                            )
                        )

                    actions.append(
                        ActionSpec(
                            label=f"{ICON_DELETE} Remove",
                            key=f"projects.batch_remove::{project.name}::{job_idx}",
                            on_click=lambda p=project, idx=job_idx: confirm_remove_batch_job(
                                p, idx
                            ),
                            button_type="secondary",
                        )
                    )
                    render_action_row(actions, columns=[2] * len(actions))


def download_batch_results(project: Project, job_idx: int) -> None:
    with st.spinner("Downloading results…"):
        try:
            download_and_convert_batch_results_ui(project, job_idx)
            store.save_project(project)
            queue_flash("success", "Batch results downloaded.")
        except Exception as exc:
            error(f"Failed to download batch results: {exc}")


def confirm_remove_batch_job(project: Project, job_idx: int) -> None:
    st.session_state[
        f"projects.confirm_remove_batch::{project.name}::{job_idx}"
    ] = True


def render_batch_removal_dialog(project: Project, job_idx: int) -> None:
    from ui.components import render_confirmation_modal

    key = f"projects.confirm_remove_batch::{project.name}::{job_idx}"
    if not st.session_state.get(key):
        return

    job = project.batch_jobs[job_idx]

    details = [f"Job: `{job.job_name}`"]
    files_to_delete: List[Path] = []
    if job.result_file_path and Path(job.result_file_path).exists():
        files_to_delete.append(Path(job.result_file_path))

    batch_dir = BATCH_DIR / project.name
    if batch_dir.exists():
        files_to_delete.extend(batch_dir.glob(f"*{job.job_name}*.jsonl"))

    if files_to_delete:
        details.append(f"{len(files_to_delete)} related file(s) will be deleted.")
        details.extend(f"- {f.name}" for f in files_to_delete[:5])

    def on_confirm() -> None:
        for file_path in files_to_delete:
            try:
                file_path.unlink(missing_ok=True)
            except Exception as exc:  # pragma: no cover
                error(f"Failed to delete {file_path.name}: {exc}")

        project.batch_jobs.pop(job_idx)
        store.save_project(project)

        queue_flash("success", f"Removed batch job `{job.job_name}`.")
        st.session_state.pop(key, None)

    def on_cancel() -> None:
        st.session_state.pop(key, None)

    @st.dialog("Remove Batch Job")
    def show_batch_removal_confirmation():
        render_confirmation_modal(
            title="Remove Batch Job",
            message=f"Remove batch job `{job.job_name}`?",
            on_confirm=on_confirm,
            confirm_label="Remove job",
            cancel_label="Keep job",
            details=details,
            warning="This deletes downloaded result files linked to the job.",
            danger=True,
            on_cancel=on_cancel,
            key=key,
        )

    show_batch_removal_confirmation()


def handle_majority_vote_all(project: Project) -> None:
    """Handle majority voting for all files in the project."""
    created_count = 0
    updated_count = 0
    skip_count = 0
    error_count = 0

    for pdf_path in project.pdf_files:
        file_name = Path(pdf_path).name
        if not can_create_majority_vote(project.name, pdf_path):
            skip_count += 1
            continue

        try:
            vote_existed = majority_vote_exists(project.name, pdf_path)
            create_majority_voted_result(project.name, pdf_path)
            if vote_existed:
                updated_count += 1
            else:
                created_count += 1
        except Exception as exc:
            error_count += 1
            queue_flash("error", f"Failed to create majority vote for {file_name}: {exc}")

    # Show summary
    if created_count > 0:
        queue_flash("success", f"Created {created_count} majority-voted result(s).")
    if updated_count > 0:
        queue_flash("success", f"Updated {updated_count} existing majority-voted result(s).")
    if skip_count > 0:
        queue_flash("info", f"Skipped {skip_count} file(s) with fewer than 3 result files.")
    if error_count > 0:
        queue_flash("error", f"Failed to process {error_count} file(s).")

    st.rerun()


def show_export_dialog(project: Project) -> None:
    """Show dialog for selecting which results to export."""
    from ui.dataframe_utils import combine_multiple_results
    import polars as pl

    # Clear the dialog trigger flag immediately
    dialog_key = f"projects.show_export_dialog::{project.name}"
    if dialog_key in st.session_state:
        del st.session_state[dialog_key]

    st.markdown(f"### {ICON_EXPORT} Export Results for {project.name}")
    st.caption("Select which result file to include for each PDF in the export.")

    # Initialize selection state if not present
    selection_key_prefix = f"export_selection::{project.name}"

    # Build selection UI for each PDF file
    if not project.pdf_files:
        warning("No files in this project to export.")
        return

    st.markdown("---")

    for pdf_path in project.pdf_files:
        file_name = Path(pdf_path).name
        result_files = get_result_files(project.name, pdf_path)

        if not result_files:
            continue

        # Determine default selection
        majority_path = None
        for rf in result_files:
            if is_majority_vote_file(rf):
                majority_path = rf
                break

        default_file = majority_path if majority_path else result_files[0]

        # Create selection key
        selection_key = f"{selection_key_prefix}::{file_name}"
        if selection_key not in st.session_state:
            st.session_state[selection_key] = str(default_file)

        # Build options with visual indicators
        options = []
        option_labels = []
        for rf in result_files:
            options.append(str(rf))
            label = rf.name
            if is_majority_vote_file(rf):
                label = f"★ {label} (Majority Vote)"
            option_labels.append(label)

        # File selection row
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"**{file_name}**")
        with col2:
            # Find current selection index
            current_selection = st.session_state[selection_key]
            try:
                current_index = options.index(current_selection)
            except ValueError:
                current_index = 0

            selected = st.selectbox(
                f"Result for {file_name}",
                options=options,
                index=current_index,
                format_func=lambda x: option_labels[options.index(x)],
                key=f"{selection_key}_widget",
                label_visibility="collapsed",
            )
            st.session_state[selection_key] = selected

    st.markdown("---")

    # Gather selected files
    selected_files = []
    for pdf_path in project.pdf_files:
        file_name = Path(pdf_path).name
        selection_key = f"{selection_key_prefix}::{file_name}"
        if selection_key in st.session_state:
            selected_files.append(st.session_state[selection_key])

    if not selected_files:
        warning("No result files selected for export.")
        return

    # Export buttons
    schema = store.get_schema(project.schema_name)
    export_cols = st.columns(3)

    with export_cols[0]:
        # JSON export
        if st.button(f"{ICON_CODE} Export as JSON", use_container_width=True, type="primary"):
            try:
                combined_results = combine_multiple_results(selected_files)
                from datetime import datetime
                combined_json = {
                    "project": project.name,
                    "timestamp": datetime.now().isoformat(),
                    "total_files": combined_results["total_files"],
                    "total_rows": combined_results["total_rows"],
                    "data": combined_results["data"]
                }

                st.download_button(
                    label=f"{ICON_DOWNLOAD} Download JSON",
                    data=json.dumps(combined_json, indent=2),
                    file_name=f"{project.name}_export.json",
                    mime="application/json",
                    key=f"export_json_download::{project.name}",
                    use_container_width=True,
                )
            except Exception as exc:
                error(f"Failed to generate JSON export: {exc}")

    with export_cols[1]:
        # CSV export
        can_export_csv = schema and schema.is_dataframe_serializable()
        if st.button(
            f"{ICON_TABLE_CHART} Export as CSV",
            use_container_width=True,
            disabled=not can_export_csv,
            help="Export as CSV" if can_export_csv else "CSV not available for this schema",
        ):
            try:
                combined_results = combine_multiple_results(selected_files)
                if combined_results["data"]:
                    df = pl.DataFrame(combined_results["data"])
                    csv_data = df.write_csv()

                    st.download_button(
                        label=f"{ICON_DOWNLOAD} Download CSV",
                        data=csv_data,
                        file_name=f"{project.name}_export.csv",
                        mime="text/csv",
                        key=f"export_csv_download::{project.name}",
                        use_container_width=True,
                    )
                else:
                    warning("No data to export.")
            except Exception as exc:
                error(f"Failed to generate CSV export: {exc}")

    with export_cols[2]:
        # Cancel button
        if st.button("Cancel", use_container_width=True):
            # Clear selection state
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and key.startswith(selection_key_prefix):
                    del st.session_state[key]
            st.rerun()


def render_project_footer(project: Project) -> None:
    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        # Check if any files have results
        has_results = any(get_result_files(project.name, pdf_path) for pdf_path in project.pdf_files)

        if st.button(
            f"{ICON_EXPORT} Export Results",
            key=f"projects.export::{project.name}",
            use_container_width=True,
            disabled=not has_results,
            help="Export selected results from all files",
        ):
            st.session_state[f"projects.show_export_dialog::{project.name}"] = True

    with cols[1]:
        # Check if any files can be majority voted
        can_vote_any = any(can_create_majority_vote(project.name, pdf_path) for pdf_path in project.pdf_files)

        if st.button(
            f"{ICON_HOW_TO_VOTE} Majority Vote All",
            key=f"projects.majority_vote_all::{project.name}",
            use_container_width=True,
            disabled=not can_vote_any,
            help="Create majority-voted results for all files with 3+ runs",
        ):
            handle_majority_vote_all(project)

    with cols[2]:
        if st.button(
            f"{ICON_DELETE_FOREVER} Delete Project",
            key=f"projects.delete::{project.name}",
            use_container_width=True,
        ):
            st.session_state[f"projects.confirm_delete::{project.name}"] = True

    confirm_key = f"projects.confirm_delete::{project.name}"
    if st.session_state.get(confirm_key):
        @st.dialog("Confirm Project Deletion")
        def show_delete_confirmation():
            from ui.components import render_confirmation_modal

            results_dir = RESULTS_DIR / project.name
            batch_dir = BATCH_DIR / project.name
            files_count = 0
            if results_dir.exists():
                files_count += len(list(results_dir.glob("*.json")))
            if batch_dir.exists():
                files_count += len(list(batch_dir.glob("*.jsonl")))

            details = []
            if files_count:
                details.append(f"{files_count} result/batch file(s) will be deleted.")

            def on_confirm() -> None:
                import shutil

                if results_dir.exists():
                    shutil.rmtree(results_dir, ignore_errors=True)
                if batch_dir.exists():
                    shutil.rmtree(batch_dir, ignore_errors=True)
                store.delete_project(project.name)

                queue_flash("success", f"Deleted project '{project.name}'.")
                st.session_state.pop(confirm_key, None)

            def on_cancel() -> None:
                st.session_state.pop(confirm_key, None)

            render_confirmation_modal(
                title="Delete Project",
                message=f"Delete project **{project.name}**?",
                on_confirm=on_confirm,
                confirm_label="Delete project",
                cancel_label="Cancel",
                details=details,
                warning="Removes project config, OCR results, and batch data. Uploads remain untouched.",
                danger=True,
                on_cancel=on_cancel,
                key=confirm_key,
            )

        show_delete_confirmation()

    # Show export dialog if requested
    export_dialog_key = f"projects.show_export_dialog::{project.name}"
    if st.session_state.get(export_dialog_key):
        @st.dialog("Export Results")
        def show_export_modal():
            show_export_dialog(project)

        show_export_modal()


def process_active_tasks(project: Project) -> None:
    for pdf_path in list(project.pdf_files):
        if not get_processing_state(project.name, pdf_path):
            continue

        file_name = Path(pdf_path).name
        task = get_active_task(project.name, pdf_path) or {}
        mode = task.get("mode", "Direct")

        with st.container(border=True):
            st.markdown(f"### {ICON_HOURGLASS} Processing: {file_name}")

            if mode == "Direct":
                handle_direct_processing(project, pdf_path, file_name)
            else:
                handle_batch_submission(project, pdf_path, file_name)


def render_project_card(project: Project) -> None:
    default_mode = get_project_mode(project.name)
    is_expanded = is_project_expanded(project.name)

    # Determine expansion icons
    folder_icon = ICON_FOLDER_OPEN if is_expanded else ICON_FOLDER
    chevron_icon = ICON_EXPAND_LESS if is_expanded else ICON_EXPAND_MORE

    with st.container(border=True):
        # Project header
        st.subheader(f"{folder_icon} {project.name}")
        render_metadata_chips(
            [
                ("Prompt", project.prompt_name),
                ("Schema", project.schema_name),
                ("Created", project.created_at.strftime("%Y-%m-%d %H:%M")),
                ("Files", str(len(project.pdf_files))),
            ]
        )

        # Expansion toggle row
        toggle_cols = st.columns([1])
        with toggle_cols[0]:
            if st.button(
                f"{chevron_icon} {'Collapse' if is_expanded else 'Expand'}",
                key=f"projects.toggle_expand::{project.name}",
                use_container_width=True,
                help="Expand/collapse project",
            ):
                toggle_project_expansion(project.name)
                st.rerun()

        # Only show full content when expanded
        if not is_expanded:
            return

        st.markdown("---")

        # Processing mode with inline description
        processing_mode = st.radio(
            "Mode",
            options=["Direct", "Batch"],
            index=["Direct", "Batch"].index(default_mode if default_mode in ["Direct", "Batch"] else "Direct"),
            key=f"projects.mode::{project.name}",
            horizontal=True,
        )

        # Update mode and rerun if changed
        if processing_mode != default_mode:
            set_project_mode(project.name, processing_mode)
            st.rerun()

        # Inline description
        mode_desc = "⚡ Fast, immediate results" if processing_mode == "Direct" else "💰 Async, ~24h, lower cost"
        st.caption(f"({mode_desc})")

        st.subheader(f"Files ({len(project.pdf_files)})")

        # Compact upload section
        uploaded_files = st.file_uploader(
            "Upload PDF",
            type="pdf",
            key=f"projects.upload::{project.name}",
            accept_multiple_files=True,
        )

        if uploaded_files:
            upload_dir = UPLOADS_DIR / project.name
            upload_dir.mkdir(parents=True, exist_ok=True)

            added_count = 0
            existing_count = 0

            for uploaded_file in uploaded_files:
                file_path = upload_dir / uploaded_file.name
                file_path.write_bytes(uploaded_file.getvalue())

                if str(file_path) not in project.pdf_files:
                    project.pdf_files.append(str(file_path))
                    added_count += 1
                else:
                    existing_count += 1

            if added_count > 0:
                store.save_project(project)
                queue_flash("success", f"Added {added_count} file(s) to {project.name}.")
            if existing_count > 0:
                queue_flash("info", f"{existing_count} file(s) already existed in this project.")
            st.rerun()

        if not project.pdf_files:
            info("No files yet. Upload a PDF above to start processing.")
        else:
            for pdf_path in project.pdf_files:
                render_file_row(project, pdf_path, processing_mode)

        process_active_tasks(project)
        render_batch_jobs(project)
        render_batch_removal_dialogs(project)
        render_project_footer(project)


def render_batch_removal_dialogs(project: Project) -> None:
    for job_idx in range(len(project.batch_jobs)):
        render_batch_removal_dialog(project, job_idx)


# Page layout
render_create_project_card()

projects = store.get_projects()
if not projects:
    info("No projects yet. Create one above to get started.")
else:
    for project in sorted_projects(projects):
        render_project_card(project)
