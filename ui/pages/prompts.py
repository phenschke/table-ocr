"""
Prompts page - manage OCR prompt templates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import streamlit as st

from ui.components import ActionSpec, render_action_row, render_metadata_chips, render_status_badge
from ui.constants import (
    ICON_ADD,
    ICON_CANCEL,
    ICON_CHAT,
    ICON_DELETE,
    ICON_EDIT,
    ICON_SAVE,
    TEXTAREA_PROMPT_HEIGHT,
    TEXTAREA_PROMPT_VIEW_HEIGHT,
)
from ui.feedback import info, success, warning
from ui.models import Prompt
from ui.storage import DataStore
from ui.utils import clear_file_viewing_state

# Initialize data store
store = DataStore()

# Clear file viewing state when navigating to this page
clear_file_viewing_state()

# Add max-width styling for better readability on wide screens
st.markdown("""
    <style>
    .main .block-container {
        max-width: 1000px;
    }
    </style>
""", unsafe_allow_html=True)

st.header("Prompts")

FLASH_KEY = "prompts__flash_messages"
EDIT_STATE_KEY = "prompts.editing"


def queue_flash(level: str, message: str) -> None:
    st.session_state.setdefault(FLASH_KEY, []).append((level, message))


if flashes := st.session_state.pop(FLASH_KEY, None):
    for level, message in flashes:
        {"success": success, "info": info, "warning": warning}[level](message)


def get_edit_state() -> Dict[str, Dict[str, str]]:
    return st.session_state.setdefault(EDIT_STATE_KEY, {})


def clear_edit_state(prompt_name: str) -> None:
    get_edit_state().pop(prompt_name, None)


def render_create_prompt() -> None:
    with st.container(border=True):
        st.subheader(f"{ICON_ADD} Create Prompt")
        new_prompt_name = st.text_input("Prompt name", key="prompts.new.name")
        new_prompt_content = st.text_area(
            "Prompt content",
            key="prompts.new.content",
            height=TEXTAREA_PROMPT_HEIGHT,
            help="Enter instructions that guide OCR extraction.",
        )

        can_create = bool(new_prompt_name and new_prompt_content)

        if st.button(
            f"{ICON_SAVE} Save Prompt",
            type="primary",
            disabled=not can_create,
            use_container_width=False,
        ):
            prompt = Prompt(name=new_prompt_name, content=new_prompt_content)
            store.save_prompt(prompt)
            queue_flash("success", f"Prompt '{new_prompt_name}' created.")
            # Clear the form by deleting the widget keys before rerun
            del st.session_state["prompts.new.name"]
            del st.session_state["prompts.new.content"]
            st.rerun()


def render_prompt_card(prompt: Prompt) -> None:
    edit_state = get_edit_state()
    state = edit_state.get(prompt.name, {"editing": False, "content": prompt.content})
    is_editing = state.get("editing", False)

    with st.container(border=True):
        st.subheader(f"{ICON_CHAT} {prompt.name}")

        metadata: List[tuple[str, str]] = [
            ("Created", prompt.created_at.strftime("%Y-%m-%d %H:%M")),
        ]
        if prompt.last_modified:
            metadata.append(("Updated", prompt.last_modified.strftime("%Y-%m-%d %H:%M")))
        render_metadata_chips(metadata)

        projects = store.get_projects()
        in_use_by = [p.name for p in projects if p.prompt_name == prompt.name]
        if in_use_by:
            render_status_badge(
                f"Used by {len(in_use_by)} project(s)",
                variant="info",
            )

        if is_editing:
            state.setdefault("content", prompt.content)
            edited_content = st.text_area(
                "Content",
                key=f"prompts.edit.content::{prompt.name}",
                value=state["content"],
                height=TEXTAREA_PROMPT_VIEW_HEIGHT,
                help="Update the instructions for OCR extraction.",
            )
            state["content"] = edited_content

            if in_use_by:
                warning(
                    f"Changes will affect future runs for: {', '.join(in_use_by)}."
                )

            actions = [
                ActionSpec(
                    label=f"{ICON_SAVE} Save",
                    key=f"prompts.save::{prompt.name}",
                    on_click=lambda p=prompt, content=edited_content: save_prompt_changes(
                        p, content
                    ),
                    disabled=not edited_content.strip(),
                    button_type="primary",
                ),
                ActionSpec(
                    label=f"{ICON_CANCEL} Cancel",
                    key=f"prompts.cancel::{prompt.name}",
                    on_click=lambda name=prompt.name: cancel_edit(name),
                ),
            ]
            render_action_row(actions, columns=[1, 1])
        else:
            st.text_area(
                "Content",
                value=prompt.content,
                height=TEXTAREA_PROMPT_VIEW_HEIGHT,
                key=f"prompts.view.content::{prompt.name}",
                disabled=True,
            )

            actions = [
                ActionSpec(
                    label=f"{ICON_EDIT} Edit",
                    key=f"prompts.edit::{prompt.name}",
                    on_click=lambda name=prompt.name, content=prompt.content: start_edit(
                        name, content
                    ),
                ),
                ActionSpec(
                    label=f"{ICON_DELETE} Delete",
                    key=f"prompts.delete::{prompt.name}",
                    on_click=lambda name=prompt.name: request_delete_prompt(name),
                ),
            ]
            render_action_row(actions, columns=[1, 1])

    render_delete_dialog(prompt, in_use_by)


def start_edit(prompt_name: str, content: str) -> None:
    edit_state = get_edit_state()
    edit_state[prompt_name] = {"editing": True, "content": content}


def cancel_edit(prompt_name: str) -> None:
    clear_edit_state(prompt_name)


def save_prompt_changes(prompt: Prompt, new_content: str) -> None:
    prompt.content = new_content
    prompt.last_modified = datetime.now()
    store.save_prompt(prompt)
    clear_edit_state(prompt.name)
    queue_flash("success", f"Prompt '{prompt.name}' updated.")


def request_delete_prompt(prompt_name: str) -> None:
    st.session_state[f"prompts.confirm_delete::{prompt_name}"] = True


def render_delete_dialog(prompt: Prompt, in_use_by: List[str]) -> None:
    key = f"prompts.confirm_delete::{prompt.name}"
    if not st.session_state.get(key):
        return

    from ui.components import render_confirmation_modal

    warning_text = None
    if in_use_by:
        warning_text = (
            f"This prompt is referenced by {len(in_use_by)} project(s): {', '.join(in_use_by)}."
        )

    def on_confirm() -> None:
        store.delete_prompt(prompt.name)
        clear_edit_state(prompt.name)
        st.session_state.pop(key, None)
        queue_flash("success", f"Deleted prompt '{prompt.name}'.")

    def on_cancel() -> None:
        st.session_state.pop(key, None)

    render_confirmation_modal(
        title="Delete Prompt",
        message=f"Delete prompt **{prompt.name}**?",
        on_confirm=on_confirm,
        confirm_label="Delete",
        cancel_label="Cancel",
        warning=warning_text,
        danger=True,
        on_cancel=on_cancel,
        key=key,
    )


# Page layout
render_create_prompt()

prompts = sorted(store.get_prompts(), key=lambda p: p.created_at, reverse=True)
if not prompts:
    info("No prompts yet. Create one above to get started.")
else:
    for prompt in prompts:
        render_prompt_card(prompt)
