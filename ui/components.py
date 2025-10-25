"""
Reusable UI building blocks to keep page layouts consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import streamlit as st

from ui.constants import STATUS_BADGE_STYLES


# ===== Status Badges =========================================================

def render_status_badge(label: str, variant: str = "info", *, icon: Optional[str] = None) -> None:
    """Render a text badge with variant styling."""
    config = STATUS_BADGE_STYLES.get(variant, STATUS_BADGE_STYLES["info"])
    prefix = icon or config.icon
    style = f"color: {config.text_color}; background: {config.background};"
    st.markdown(
        f"<span class='status-badge status-badge--{variant}' style=\"{style}\">{prefix} {label}</span>",
        unsafe_allow_html=True,
    )


# ===== Chips & Metadata ======================================================

def render_metadata_chips(pairs: Iterable[tuple[str, str]]) -> None:
    """Render a horizontal set of chips describing metadata fields."""
    chips = " ".join(
        f"<span class='meta-chip'><strong>{label}</strong>: {value}</span>"
        for label, value in pairs
    )
    st.markdown(f"<div class='meta-chip-row'>{chips}</div>", unsafe_allow_html=True)


# ===== Action Buttons ========================================================

@dataclass
class ActionSpec:
    label: str
    key: str
    on_click: Callable[[], None]
    disabled: bool = False
    button_type: str = "secondary"


def render_action_row(actions: Iterable[ActionSpec], *, columns: Optional[list[int]] = None) -> None:
    """Render a set of buttons horizontally."""
    actions = list(actions)
    if not actions:
        return
    stretch = columns or [1] * len(actions)
    cols = st.columns(stretch)
    for action, col in zip(actions, cols):
        with col:
            if st.button(
                action.label,
                key=action.key,
                use_container_width=True,
                disabled=action.disabled,
                type=action.button_type,
            ):
                action.on_click()


# ===== Confirmation Modal ====================================================

def render_confirmation_modal(
    *,
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    details: Optional[list[str]] = None,
    warning: Optional[str] = None,
    danger: bool = False,
    on_cancel: Optional[Callable[[], None]] = None,
    key: str,
) -> None:
    """Display a modal dialog asking the user to confirm an action."""

    confirm_type = "primary" if not danger else "primary"

    st.write(message)

    if warning:
        st.warning(warning)

    if details:
        for detail in details:
            st.caption(detail)

    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button(confirm_label, use_container_width=True, type=confirm_type, key=f"{key}::confirm"):
            on_confirm()
            st.rerun()
    with col_cancel:
        if st.button(cancel_label, use_container_width=True, key=f"{key}::cancel"):
            if on_cancel:
                on_cancel()
            st.rerun()
