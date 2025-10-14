"""
Prompts page - manage OCR prompt templates
"""
import streamlit as st
from datetime import datetime

from ui.storage import DataStore
from ui.models import Prompt
from ui.utils import ensure_cleared_file_state, show_confirmation_dialog
from ui.constants import (
    ICON_CHAT, ICON_DELETE, ICON_EDIT, ICON_SAVE, ICON_CANCEL, ICON_WARNING,
    TEXTAREA_PROMPT_HEIGHT, TEXTAREA_PROMPT_VIEW_HEIGHT
)

# Initialize data store
store = DataStore()

# Clear file viewing state when navigating to this page
ensure_cleared_file_state()

st.header("Prompts")

# Create new prompt
with st.expander("Create New Prompt"):
    new_prompt_name = st.text_input("Prompt Name", key="new_prompt_name")
    new_prompt_content = st.text_area(
        "Prompt Content",
        height=TEXTAREA_PROMPT_HEIGHT,
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
prompts = store.get_prompts()

if not prompts:
    st.info("No prompts yet. Create one above!")
else:
    for prompt in prompts:
        with st.expander(f"{ICON_CHAT} {prompt.name}"):
            # Check if this prompt is being edited
            is_editing = st.session_state.get(f"editing_prompt_{prompt.name}", False)
            
            if is_editing:
                # Editable mode
                edited_content = st.text_area(
                    "Content",
                    value=st.session_state.get(f"edit_content_{prompt.name}", prompt.content),
                    height=TEXTAREA_PROMPT_VIEW_HEIGHT,
                    key=f"edit_prompt_{prompt.name}",
                    help="Edit the prompt content"
                )
                
                # Check if prompt is in use by any projects
                projects = store.get_projects()
                projects_using_prompt = [p.name for p in projects if p.prompt_name == prompt.name]
                
                if projects_using_prompt:
                    st.warning(
                        f"{ICON_WARNING} This prompt is used by {len(projects_using_prompt)} project(s): "
                        f"{', '.join(projects_using_prompt)}. Changes will affect future OCR operations."
                    )
                
                col1, col2, col3 = st.columns([1, 1, 4])
                with col1:
                    if st.button(f"{ICON_SAVE} Save Changes", key=f"save_prompt_{prompt.name}", use_container_width=True):
                        if edited_content:
                            # Update prompt with new content and last_modified timestamp
                            prompt.content = edited_content
                            prompt.last_modified = datetime.now()
                            store.save_prompt(prompt)
                            st.session_state[f"editing_prompt_{prompt.name}"] = False
                            if f"edit_content_{prompt.name}" in st.session_state:
                                del st.session_state[f"edit_content_{prompt.name}"]
                            st.success(f"Prompt '{prompt.name}' updated!")
                            st.rerun()
                        else:
                            st.error("Prompt content cannot be empty")
                
                with col2:
                    if st.button(f"{ICON_CANCEL} Cancel", key=f"cancel_edit_prompt_{prompt.name}", use_container_width=True):
                        st.session_state[f"editing_prompt_{prompt.name}"] = False
                        if f"edit_content_{prompt.name}" in st.session_state:
                            del st.session_state[f"edit_content_{prompt.name}"]
                        st.rerun()
            else:
                # View-only mode
                st.text_area(
                    "Content",
                    value=prompt.content,
                    height=TEXTAREA_PROMPT_VIEW_HEIGHT,
                    key=f"view_prompt_{prompt.name}",
                    disabled=True
                )
                
                # Show timestamps
                st.write(f"**Created:** {prompt.created_at.strftime('%Y-%m-%d %H:%M')}")
                if prompt.last_modified:
                    st.write(f"**Last Modified:** {prompt.last_modified.strftime('%Y-%m-%d %H:%M')}")
                
                # Action buttons
                col1, col2, col3 = st.columns([1, 1, 4])
                with col1:
                    if st.button(f"{ICON_EDIT} Edit", key=f"edit_btn_prompt_{prompt.name}", use_container_width=True):
                        st.session_state[f"editing_prompt_{prompt.name}"] = True
                        st.session_state[f"edit_content_{prompt.name}"] = prompt.content
                        st.rerun()
                
                with col2:
                    if st.button(f"{ICON_DELETE} Delete", key=f"delete_prompt_{prompt.name}", use_container_width=True):
                        st.session_state[f"confirm_delete_prompt_{prompt.name}"] = True
                        st.rerun()
            
            # Confirmation dialog for deletion
            if st.session_state.get(f"confirm_delete_prompt_{prompt.name}", False):
                @st.dialog("Confirm Prompt Deletion")
                def confirm_delete_prompt():
                    def on_confirm():
                        store.delete_prompt(prompt.name)
                        st.session_state[f"confirm_delete_prompt_{prompt.name}"] = False
                        st.success(f"Deleted prompt '{prompt.name}'")
                        st.rerun()
                    
                    show_confirmation_dialog(
                        title="Confirm Prompt Deletion",
                        message=f"Are you sure you want to delete prompt **{prompt.name}**?",
                        on_confirm=on_confirm,
                        warning_text="Projects using this prompt will need to be updated."
                    )
                    
                    # Handle cancel
                    if st.session_state.get('_dialog_cancelled', False):
                        st.session_state[f"confirm_delete_prompt_{prompt.name}"] = False
                        st.rerun()
                confirm_delete_prompt()
