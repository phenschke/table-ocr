"""
Session state helpers centralizing key usage patterns.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

# Namespaced session state keys
VIEWING_FILE_KEY = "view.current_file"
VIEWING_PROJECT_KEY = "view.current_project"
CURRENT_PAGE_KEY = "view.current_page"
PROCESSING_STATE_KEY = "projects.processing"
PROJECT_MODES_KEY = "projects.modes"
ACTIVE_TASKS_KEY = "projects.active_tasks"


def _ensure_dict(key: str) -> Dict[str, Any]:
    """Return a mutable dict stored at key, creating it if absent."""
    if key not in st.session_state or not isinstance(st.session_state[key], dict):
        st.session_state[key] = {}
    return st.session_state[key]


# ===== View State ============================================================

def set_viewing_context(file_path: Optional[str], project_name: Optional[str]) -> None:
    """Persist the currently viewed project/file context."""
    st.session_state[VIEWING_FILE_KEY] = file_path
    st.session_state[VIEWING_PROJECT_KEY] = project_name
    # Backwards compatibility with previous key usage
    st.session_state["viewing_file"] = file_path
    st.session_state["viewing_project"] = project_name


def get_viewing_file() -> Optional[str]:
    """Return the active file path, if any."""
    return (
        st.session_state.get(VIEWING_FILE_KEY)
        or st.session_state.get("viewing_file")
    )


def get_viewing_project() -> Optional[str]:
    """Return the active project name, if any."""
    return (
        st.session_state.get(VIEWING_PROJECT_KEY)
        or st.session_state.get("viewing_project")
    )


def clear_view_state() -> None:
    """Clear the current viewing context and reset page number."""
    for key in (VIEWING_FILE_KEY, "viewing_file"):
        st.session_state.pop(key, None)
    for key in (VIEWING_PROJECT_KEY, "viewing_project"):
        st.session_state.pop(key, None)
    st.session_state.pop(CURRENT_PAGE_KEY, None)


def get_current_page(default: Optional[int] = 1) -> Optional[int]:
    """Return the current page number for file inspection."""
    return st.session_state.get(CURRENT_PAGE_KEY, default)


def set_current_page(page_number: int) -> None:
    """Update the active page number for file inspection."""
    st.session_state[CURRENT_PAGE_KEY] = page_number
    st.session_state["current_page"] = page_number  # backwards compat


# ===== Project Processing State =============================================

def get_processing_state(project_name: str, file_path: str) -> bool:
    """Check if a given file within a project is marked as processing."""
    processing = _ensure_dict(PROCESSING_STATE_KEY)
    project_state = processing.get(project_name, {})
    return bool(project_state.get(file_path))


def set_processing_state(project_name: str, file_path: str, value: bool) -> None:
    """Set or clear the processing flag for a project/file combination."""
    processing = _ensure_dict(PROCESSING_STATE_KEY)
    project_state = processing.setdefault(project_name, {})
    if value:
        project_state[file_path] = True
    else:
        project_state.pop(file_path, None)
    # Clean up empty project entries
    if not project_state:
        processing.pop(project_name, None)


def clear_project_processing(project_name: str) -> None:
    """Clear all processing flags for a specific project."""
    processing = _ensure_dict(PROCESSING_STATE_KEY)
    processing.pop(project_name, None)


# ===== Active Task Metadata ==================================================

def set_active_task(project_name: str, file_path: str, payload: Dict[str, Any]) -> None:
    """Store metadata for an in-flight task."""
    tasks = _ensure_dict(ACTIVE_TASKS_KEY)
    project_tasks = tasks.setdefault(project_name, {})
    project_tasks[file_path] = payload


def get_active_task(project_name: str, file_path: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata about an in-flight task if present."""
    tasks = _ensure_dict(ACTIVE_TASKS_KEY)
    project_tasks = tasks.get(project_name, {})
    return project_tasks.get(file_path)


def clear_active_task(project_name: str, file_path: Optional[str] = None) -> None:
    """Remove active task metadata."""
    tasks = _ensure_dict(ACTIVE_TASKS_KEY)
    project_tasks = tasks.get(project_name, {})
    if file_path is None:
        project_tasks.clear()
    else:
        project_tasks.pop(file_path, None)
    if not project_tasks and project_name in tasks:
        tasks.pop(project_name, None)


# ===== Project Mode Preferences =============================================

def get_project_mode(project_name: str, fallback: str = "Direct") -> str:
    """Return the last selected processing mode for a project."""
    modes = _ensure_dict(PROJECT_MODES_KEY)
    return modes.get(project_name, fallback)


def set_project_mode(project_name: str, mode: str) -> None:
    """Persist the last selected processing mode for a project."""
    modes = _ensure_dict(PROJECT_MODES_KEY)
    modes[project_name] = mode


# ===== Project Expansion State ==============================================

PROJECT_EXPANSION_KEY = "projects.expansion_state"


def is_project_expanded(project_name: str) -> bool:
    """Check if a project is currently expanded."""
    expansion = _ensure_dict(PROJECT_EXPANSION_KEY)
    return expansion.get(project_name, False)


def toggle_project_expansion(project_name: str) -> None:
    """Toggle the expansion state of a project."""
    expansion = _ensure_dict(PROJECT_EXPANSION_KEY)
    current = expansion.get(project_name, False)
    expansion[project_name] = not current
