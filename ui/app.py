"""
Table OCR Manager - Streamlit Multipage App
Main entrypoint using st.Page and st.navigation
"""
import streamlit as st
import sys
from pathlib import Path

from constants import (
    ICON_FOLDER,
    ICON_CHAT,
    ICON_TABLE_CHART,
    ICON_DESCRIPTION,
)
from state import (
    get_viewing_file,
    set_viewing_context,
    get_current_page,
    set_current_page,
)

# Add parent directory to path to find table_ocr package
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Page configuration
st.set_page_config(
    page_title="Table OCR Manager",
    page_icon="📋",
    layout="wide",
)

# Add custom CSS for styling
st.markdown(
    """
<style>
    .stButton > button {
        white-space: nowrap;
        border-radius: 6px;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.1rem 0.5rem;
        font-size: 0.85rem;
        border-radius: 12px;
        font-weight: 500;
        line-height: 1.4;
    }
    .status-badge--success {
        color: #136534;
        background: rgba(19, 101, 52, 0.12);
    }
    .status-badge--warning {
        color: #8A6D1D;
        background: rgba(215, 183, 0, 0.18);
    }
    .status-badge--danger {
        color: #8A1D1D;
        background: rgba(215, 0, 0, 0.12);
    }
    .status-badge--processing {
        color: #125F82;
        background: rgba(30, 144, 255, 0.12);
    }
    .status-badge--info {
        color: #1E3A5F;
        background: rgba(30, 90, 255, 0.12);
    }
    .meta-chip-row {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin: 0.5rem 0 1rem 0;
    }
    .meta-chip {
        background: rgba(250, 250, 250, 0.06);
        border: 1px solid rgba(250, 250, 250, 0.08);
        border-radius: 999px;
        padding: 0.2rem 0.75rem;
        font-size: 0.85rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Table OCR Manager")

# Initialize session state for file viewing
if get_viewing_file() is None and "viewing_file" not in st.session_state:
    set_viewing_context(None, None)
if get_current_page(default=None) is None:
    set_current_page(1)

# Define pages
projects_page = st.Page(
    "pages/projects.py",
    title="Projects",
    icon=ICON_FOLDER,
    default=True,
)

prompts_page = st.Page(
    "pages/prompts.py",
    title="Prompts",
    icon=ICON_CHAT,
)

schemas_page = st.Page(
    "pages/schemas.py",
    title="Schemas",
    icon=ICON_TABLE_CHART,
)

file_details_page = st.Page(
    "pages/file_details.py",
    title="File Details",
    icon=ICON_DESCRIPTION,
)

# Store page objects in session state so page files can access them
if "pages" not in st.session_state:
    st.session_state.pages = {
        "projects": projects_page,
        "prompts": prompts_page,
        "schemas": schemas_page,
        "file_details": file_details_page,
    }

# Create navigation
if get_viewing_file():
    nav = st.navigation(
        {
            "Configuration": [projects_page, prompts_page, schemas_page],
            "Current View": [file_details_page],
        }
    )
else:
    nav = st.navigation(
        {
            "Configuration": [projects_page, prompts_page, schemas_page],
        }
    )

# Run the selected page
nav.run()
