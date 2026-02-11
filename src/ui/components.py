"""
components.py — Reusable Streamlit UI widgets for SquadSense.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# Skill Badge
# ---------------------------------------------------------------------------

def skill_badge(skill_name: str) -> None:
    """Display a coloured skill-mode indicator badge."""
    st.markdown(
        f"""
        <div style="
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 12px;
        ">
            🎯 {skill_name.upper()} Mode Active
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Discovery Panel
# ---------------------------------------------------------------------------

def discovery_panel() -> dict[str, Any] | None:
    """
    Render the Discovery Mode sidebar panel.

    Returns:
        A dict with 'data_path' and 'skill_name' when the user clicks
        "Generate Skill", or None otherwise.
    """
    st.sidebar.markdown("### 🔍 Discovery Mode")
    st.sidebar.markdown("Ingest code & docs, then generate a Skill Manifest.")

    data_path = st.sidebar.text_input(
        "📁 Data folder path",
        value="data",
        help="Path to folder containing code and docs for ingestion.",
    )

    skill_name = st.sidebar.text_input(
        "🏷️ Skill name",
        value="",
        placeholder="e.g. staking, authentication",
        help="Name for the generated skill manifest.",
    )

    if st.sidebar.button("⚡ Ingest & Generate Skill", type="primary", use_container_width=True):
        if not skill_name.strip():
            st.sidebar.error("Please enter a skill name.")
            return None
        return {"data_path": data_path, "skill_name": skill_name.strip()}

    return None


# ---------------------------------------------------------------------------
# Interaction Panel
# ---------------------------------------------------------------------------

def interaction_panel(available_skills: list[str]) -> str | None:
    """
    Render the Interaction Mode sidebar panel with skill dropdown.

    Args:
        available_skills: List of available skill names.

    Returns:
        Selected skill name, or None if no skills are available.
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💬 Interaction Mode")

    if not available_skills:
        st.sidebar.info("No skills generated yet. Run Discovery first.")
        return None

    selected = st.sidebar.selectbox(
        "🎓 Select Skill Hat",
        options=available_skills,
        format_func=lambda x: f"🎯 {x.upper()}",
    )
    return selected


# ---------------------------------------------------------------------------
# Chat Message
# ---------------------------------------------------------------------------

def chat_message_block(role: str, content: str) -> None:
    """
    Render a styled chat message.

    Args:
        role:    "user" or "assistant".
        content: The message content (supports Markdown).
    """
    with st.chat_message(role):
        st.markdown(content)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def app_header() -> None:
    """Render the SquadSense application header."""
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem 0;">
            <h1 style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.5rem;
                margin-bottom: 0;
            ">🧠 SquadSense</h1>
            <p style="color: #888; font-size: 1.1rem;">
                Skill-Aware AI Developer Assistant
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_indicator(api_keys: dict[str, bool]) -> None:
    """Show which API keys are configured."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Status")

    for service, configured in api_keys.items():
        icon = "✅" if configured else "❌"
        st.sidebar.markdown(f"{icon} **{service.capitalize()}** API Key")
