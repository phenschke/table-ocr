"""
Table OCR Manager - Streamlit Multipage App
Main entrypoint using st.Page and st.navigation
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path to find table_ocr package
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Page configuration
st.set_page_config(
    page_title="Table OCR Manager",
    page_icon="📋",
    layout="wide"
)

# Add custom CSS for styling
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
    /* Better back button styling */
    .back-button-container {
        margin-bottom: 1.5rem;
    }
    .back-button-container button {
        background-color: transparent;
        border: 1px solid rgba(250, 250, 250, 0.2);
        color: rgba(250, 250, 250, 0.8);
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        transition: all 0.2s ease;
    }
    .back-button-container button:hover {
        background-color: rgba(250, 250, 250, 0.1);
        border-color: rgba(250, 250, 250, 0.4);
        color: rgba(250, 250, 250, 1);
    }
</style>
""", unsafe_allow_html=True)

st.title("Table OCR Manager")

# Initialize session state for file viewing
if 'viewing_file' not in st.session_state:
    st.session_state.viewing_file = None
if 'viewing_project' not in st.session_state:
    st.session_state.viewing_project = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

# Define pages
# Note: Paths are relative to where streamlit run is executed (ui/ directory)
projects_page = st.Page(
    "pages/projects.py",
    title="Projects",
    icon=":material/folder:",
    default=True
)

prompts_page = st.Page(
    "pages/prompts.py",
    title="Prompts",
    icon=":material/chat:"
)

schemas_page = st.Page(
    "pages/schemas.py",
    title="Schemas",
    icon=":material/table_chart:"
)

file_details_page = st.Page(
    "pages/file_details.py",
    title="File Details",
    icon=":material/description:"
)

# Store page objects in session state so page files can access them
if 'pages' not in st.session_state:
    st.session_state.pages = {
        'projects': projects_page,
        'prompts': prompts_page,
        'schemas': schemas_page,
        'file_details': file_details_page
    }

# Create navigation
# Dynamic navigation: File Details only appears when a file is being viewed
# All pages must be registered in st.navigation() for st.switch_page() to work
if st.session_state.viewing_file is not None:
    # User is viewing a file - show File Details in navigation
    pg = st.navigation({
        "Configuration": [projects_page, prompts_page, schemas_page],
        "Current View": [file_details_page]
    })
else:
    # No file selected - hide File Details from navigation
    # Note: We still register it so st.switch_page() works on first click
    pg = st.navigation({
        "Navigation": [projects_page, prompts_page, schemas_page]
    })

# Run the selected page
pg.run()
