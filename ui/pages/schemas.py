"""
Schemas page - manage output schema definitions
"""
import streamlit as st

from ui.storage import DataStore
from ui.models import OutputSchema, SchemaField
from ui.utils import ensure_cleared_file_state, show_confirmation_dialog
from ui.constants import ICON_TABLE_CHART, ICON_DELETE, ICON_ADD

# Initialize data store
store = DataStore()

# Clear file viewing state when navigating to this page
ensure_cleared_file_state()

st.header("Output Schemas")

# Create new schema
with st.expander("Create New Schema"):
    new_schema_name = st.text_input("Schema Name", key="new_schema_name")
    
    st.subheader("Fields")
    
    # Initialize session state for fields
    if 'schema_fields' not in st.session_state:
        st.session_state.schema_fields = []
    
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
            if st.button(f"{ICON_DELETE}", key=f"remove_field_{i}"):
                st.session_state[f"confirm_remove_field_{i}"] = True
                st.rerun()
            
            # Confirmation dialog for field removal
            if st.session_state.get(f"confirm_remove_field_{i}", False):
                @st.dialog("Confirm Field Removal")
                def confirm_remove_field():
                    def on_confirm():
                        st.session_state.schema_fields.pop(i)
                        st.session_state[f"confirm_remove_field_{i}"] = False
                        st.rerun()
                    
                    show_confirmation_dialog(
                        title="Confirm Field Removal",
                        message=f"Remove field **{field_name or '(unnamed)'}**?",
                        on_confirm=on_confirm
                    )
                    
                    # Handle cancel
                    if st.session_state.get('_dialog_cancelled', False):
                        st.session_state[f"confirm_remove_field_{i}"] = False
                        st.rerun()
                confirm_remove_field()
        
        if field_name:
            fields_to_create.append(SchemaField(
                name=field_name,
                field_type=field_type,
                required=field_required
            ))
    
    # Add field button (below the list of fields)
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button(f"{ICON_ADD} Add Field"):
            st.session_state.schema_fields.append({
                "name": "",
                "type": "STRING",
                "required": False
            })
            st.rerun()
    
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
schemas = store.get_schemas()

if not schemas:
    st.info("No schemas yet. Create one above!")
else:
    for schema in schemas:
        with st.expander(f"{ICON_TABLE_CHART} {schema.name}"):
            st.write(f"**Created:** {schema.created_at.strftime('%Y-%m-%d %H:%M')}")
            st.write(f"**Fields:** {len(schema.fields)}")
            
            # Display fields as table
            if schema.fields:
                st.subheader("Fields:")
                for field in schema.fields:
                    required_mark = "✓" if field.required else ""
                    st.write(f"- **{field.name}** ({field.field_type}) {required_mark}")
            
            if st.button(f"{ICON_DELETE} Delete", key=f"delete_schema_{schema.name}"):
                st.session_state[f"confirm_delete_schema_{schema.name}"] = True
                st.rerun()
            
            # Confirmation dialog
            if st.session_state.get(f"confirm_delete_schema_{schema.name}", False):
                @st.dialog("Confirm Schema Deletion")
                def confirm_delete_schema():
                    def on_confirm():
                        store.delete_schema(schema.name)
                        st.session_state[f"confirm_delete_schema_{schema.name}"] = False
                        st.success(f"Deleted schema '{schema.name}'")
                        st.rerun()
                    
                    show_confirmation_dialog(
                        title="Confirm Schema Deletion",
                        message=f"Are you sure you want to delete schema **{schema.name}**?",
                        on_confirm=on_confirm,
                        warning_text="Projects using this schema will need to be updated."
                    )
                    
                    # Handle cancel
                    if st.session_state.get('_dialog_cancelled', False):
                        st.session_state[f"confirm_delete_schema_{schema.name}"] = False
                        st.rerun()
                confirm_delete_schema()
