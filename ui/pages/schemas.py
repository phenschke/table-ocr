"""
Schemas page - manage output schema definitions.
"""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

from ui.components import (
    ActionSpec,
    render_action_row,
    render_confirmation_modal,
    render_metadata_chips,
    render_status_badge,
)
from ui.constants import (
    ICON_ADD,
    ICON_ARROW_DOWN,
    ICON_ARROW_UP,
    ICON_DELETE,
    ICON_TABLE_CHART,
)
from ui.feedback import info, success, warning
from ui.models import OutputSchema, SchemaField
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

st.header("Output Schemas")

FLASH_KEY = "schemas__flash_messages"
BUILDER_FIELDS_KEY = "schemas.builder.fields"


def queue_flash(level: str, message: str) -> None:
    st.session_state.setdefault(FLASH_KEY, []).append((level, message))


if flashes := st.session_state.pop(FLASH_KEY, None):
    for level, message in flashes:
        {"success": success, "info": info, "warning": warning}[level](message)


def get_builder_fields() -> List[Dict[str, str]]:
    return st.session_state.setdefault(
        BUILDER_FIELDS_KEY,
        [],
    )


def reset_builder() -> None:
    st.session_state[BUILDER_FIELDS_KEY] = []
    # Clear the schema name widget by deleting its key
    st.session_state.pop("schemas.builder.name", None)


def render_field_editor(field: Dict[str, str], index: int) -> None:
    col_name, col_type, col_required, col_actions = st.columns([4, 2, 1, 1])

    field["name"] = st.text_input(
        "Field name",
        key=f"schemas.field.name::{index}",
        value=field.get("name", ""),
        label_visibility="collapsed",
        placeholder="Field name",
    )

    field["type"] = st.selectbox(
        "Type",
        options=["STRING", "INTEGER", "BOOLEAN", "NUMBER"],
        index=["STRING", "INTEGER", "BOOLEAN", "NUMBER"].index(field.get("type", "STRING")),
        key=f"schemas.field.type::{index}",
        label_visibility="collapsed",
    )

    field["required"] = st.checkbox(
        "Required",
        key=f"schemas.field.required::{index}",
        value=field.get("required", False),
    )

    with col_actions:
        up_disabled = index == 0
        down_disabled = index == len(get_builder_fields()) - 1

        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button(
                ICON_ARROW_UP,
                key=f"schemas.field.up::{index}",
                disabled=up_disabled,
                help="Move up",
            ):
                fields = get_builder_fields()
                fields[index - 1], fields[index] = fields[index], fields[index - 1]
                st.rerun()
        with action_cols[1]:
            if st.button(
                ICON_ARROW_DOWN,
                key=f"schemas.field.down::{index}",
                disabled=down_disabled,
                help="Move down",
            ):
                fields = get_builder_fields()
                fields[index + 1], fields[index] = fields[index], fields[index + 1]
                st.rerun()

        if st.button(
            ICON_DELETE,
            key=f"schemas.field.delete::{index}",
            help="Remove field",
        ):
            st.session_state[f"schemas.builder.confirm_remove::{index}"] = True

    render_field_delete_dialog(index, field.get("name", ""))


def render_field_delete_dialog(index: int, field_name: str) -> None:
    key = f"schemas.builder.confirm_remove::{index}"
    if not st.session_state.get(key):
        return

    def on_confirm() -> None:
        fields = get_builder_fields()
        if 0 <= index < len(fields):
            fields.pop(index)
        st.session_state.pop(key, None)

    def on_cancel() -> None:
        st.session_state.pop(key, None)

    render_confirmation_modal(
        title="Remove Field",
        message=f"Remove field **{field_name or '(unnamed)'}**?",
        on_confirm=on_confirm,
        confirm_label="Remove field",
        cancel_label="Keep field",
        danger=True,
        on_cancel=on_cancel,
        key=key,
    )


def render_schema_builder() -> None:
    with st.container(border=True):
        st.subheader(f"{ICON_ADD} Create Schema")
        new_schema_name = st.text_input("Schema name", key="schemas.builder.name")

        fields = get_builder_fields()
        if not fields:
            info("Add fields to describe the shape of your table output.")

        for i, field in enumerate(list(fields)):
            render_field_editor(field, i)

        add_col, _ = st.columns([1, 3])
        with add_col:
            if st.button(f"{ICON_ADD} Add Field", key="schemas.add_field"):
                fields.append({"name": "", "type": "STRING", "required": False})
                st.rerun()

        if st.button(
            "Create Schema",
            type="primary",
            disabled=not (new_schema_name and any(f.get("name") for f in fields)),
        ):
            create_schema(new_schema_name, fields)


def create_schema(name: str, field_defs: List[Dict[str, str]]) -> None:
    valid_fields = [
        SchemaField(
            name=f["name"],
            field_type=f.get("type", "STRING"),
            required=f.get("required", False),
        )
        for f in field_defs
        if f.get("name")
    ]

    if not valid_fields:
        warning("Please provide at least one field with a name.")
        return

    schema = OutputSchema(name=name, fields=valid_fields)
    store.save_schema(schema)
    queue_flash("success", f"Schema '{name}' created.")
    reset_builder()
    st.rerun()


def render_schema_card(schema: OutputSchema) -> None:
    with st.container(border=True):
        st.subheader(f"{ICON_TABLE_CHART} {schema.name}")

        metadata = [
            ("Created", schema.created_at.strftime("%Y-%m-%d %H:%M")),
            ("Fields", str(len(schema.fields))),
        ]
        render_metadata_chips(metadata)

        projects = store.get_projects()
        in_use_by = [p.name for p in projects if p.schema_name == schema.name]
        if in_use_by:
            render_status_badge(
                f"Used by {len(in_use_by)} project(s)",
                variant="info",
            )

        if schema.fields:
            field_table = [
                {
                    "Field": field.name,
                    "Type": field.field_type,
                    "Required": "Yes" if field.required else "No",
                }
                for field in schema.fields
            ]
            st.table(field_table)
        else:
            info("This schema has no fields.")

        actions = [
            ActionSpec(
                label=f"{ICON_DELETE} Delete",
                key=f"schemas.delete::{schema.name}",
                on_click=lambda name=schema.name: request_schema_delete(name),
            )
        ]
        render_action_row(actions)

    render_schema_delete_dialog(schema, in_use_by)


def request_schema_delete(schema_name: str) -> None:
    st.session_state[f"schemas.confirm_delete::{schema_name}"] = True


def render_schema_delete_dialog(schema: OutputSchema, in_use_by: List[str]) -> None:
    key = f"schemas.confirm_delete::{schema.name}"
    if not st.session_state.get(key):
        return

    warning_text = None
    if in_use_by:
        warning_text = (
            f"This schema is referenced by {len(in_use_by)} project(s): {', '.join(in_use_by)}."
        )

    def on_confirm() -> None:
        store.delete_schema(schema.name)
        st.session_state.pop(key, None)
        queue_flash("success", f"Deleted schema '{schema.name}'.")

    def on_cancel() -> None:
        st.session_state.pop(key, None)

    render_confirmation_modal(
        title="Delete Schema",
        message=f"Delete schema **{schema.name}**?",
        on_confirm=on_confirm,
        confirm_label="Delete schema",
        cancel_label="Cancel",
        warning=warning_text,
        danger=True,
        on_cancel=on_cancel,
        key=key,
    )


# Page layout
render_schema_builder()

schemas = sorted(store.get_schemas(), key=lambda s: s.created_at, reverse=True)
if not schemas:
    info("No schemas yet. Create one above to get started.")
else:
    for schema in schemas:
        render_schema_card(schema)
