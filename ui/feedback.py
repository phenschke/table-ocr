"""
Shared helpers for consistent success/info/error messaging in the UI.
"""
from typing import Optional

import streamlit as st

from constants import (
    ICON_CHECK_CIRCLE,
    ICON_ERROR,
    ICON_LIGHTBULB,
    ICON_WARNING,
)


def success(message: str, *, icon: Optional[str] = None) -> None:
    """Render a success banner with a consistent icon."""
    prefix = icon or ICON_CHECK_CIRCLE
    st.success(f"{prefix} {message}")


def info(message: str, *, icon: Optional[str] = None) -> None:
    """Render an informational banner."""
    prefix = icon or ICON_LIGHTBULB
    st.info(f"{prefix} {message}")


def warning(message: str, *, icon: Optional[str] = None) -> None:
    """Render a warning banner."""
    prefix = icon or ICON_WARNING
    st.warning(f"{prefix} {message}")


def error(message: str, *, icon: Optional[str] = None) -> None:
    """Render an error banner."""
    prefix = icon or ICON_ERROR
    st.error(f"{prefix} {message}")
