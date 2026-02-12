"""
components.py — Reusable Streamlit UI widgets for SquadSense.

All components are self-documenting with clear visual cues.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# CSS Theme
# ---------------------------------------------------------------------------

GLOBAL_CSS = """
<style>
    /* ---- Page Background ---- */
    .stApp {
        background: linear-gradient(160deg, #0d0d1a 0%, #111128 40%, #1a1040 100%);
    }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background: rgba(13, 13, 26, 0.97);
        border-right: 1px solid rgba(102, 126, 234, 0.15);
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem;
    }

    /* ---- Chat messages ---- */
    .stChatMessage {
        border-radius: 14px;
        margin-bottom: 10px;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }

    /* ---- Buttons ---- */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);
    }

    /* ---- Expanders ---- */
    .streamlit-expanderHeader {
        border-radius: 10px;
        font-weight: 600;
    }

    /* ---- Step cards ---- */
    .step-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(102,126,234,0.15);
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.3s ease;
    }
    .step-card:hover {
        border-color: rgba(102,126,234,0.4);
    }
    .step-card.active {
        border-color: rgba(102,126,234,0.6);
        background: rgba(102,126,234,0.05);
    }
    .step-card.done {
        border-color: rgba(72,199,142,0.5);
        background: rgba(72,199,142,0.03);
    }

    /* ---- Step number badge ---- */
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-weight: 700;
        font-size: 0.9rem;
        margin-right: 10px;
        flex-shrink: 0;
    }
    .step-number.done {
        background: linear-gradient(135deg, #48c78e, #3ba57a);
    }

    /* ---- Skill badge ---- */
    .skill-badge {
        display: inline-block;
        padding: 6px 18px;
        border-radius: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }

    /* ---- Info hint ---- */
    .hint-box {
        background: rgba(102,126,234,0.08);
        border-left: 3px solid #667eea;
        border-radius: 0 10px 10px 0;
        padding: 12px 16px;
        margin: 10px 0;
        font-size: 0.9rem;
        color: #b0b8e8;
    }

    /* ---- Welcome hero ---- */
    .hero-section {
        text-align: center;
        padding: 3rem 1rem 2rem;
    }
    .hero-title {
        background: linear-gradient(135deg, #667eea 0%, #b06ab3 50%, #e066a0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
        line-height: 1.2;
    }
    .hero-subtitle {
        color: #8890b5;
        font-size: 1.15rem;
        margin-bottom: 2rem;
    }

    /* ---- Feature cards ---- */
    .feature-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(102,126,234,0.12);
        border-radius: 16px;
        padding: 1.8rem 1.5rem;
        text-align: center;
        height: 100%;
        transition: all 0.3s ease;
    }
    .feature-card:hover {
        border-color: rgba(102,126,234,0.35);
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 0.8rem;
    }
    .feature-title {
        color: #e0e4f0;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    .feature-desc {
        color: #8890b5;
        font-size: 0.88rem;
        line-height: 1.5;
    }

    /* ---- How-it-works ---- */
    .flow-arrow {
        text-align: center;
        color: #667eea;
        font-size: 1.5rem;
        padding: 0.3rem 0;
    }

    /* ---- Status pill ---- */
    .status-pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .status-pill.ready { background: rgba(72,199,142,0.15); color: #48c78e; }
    .status-pill.missing { background: rgba(255,100,100,0.15); color: #ff6464; }
    .status-pill.optional { background: rgba(255,200,60,0.15); color: #ffc83c; }
</style>
"""


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def app_header() -> None:
    """Render the SquadSense application header in the sidebar."""
    st.sidebar.markdown(
        """
        <div style="text-align: center; padding: 0.5rem 0 1rem;">
            <div style="font-size: 2rem;">🧠</div>
            <div style="
                background: linear-gradient(135deg, #667eea, #b06ab3);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 1.4rem;
                font-weight: 800;
            ">SquadSense</div>
            <div style="color: #6b7199; font-size: 0.75rem; letter-spacing: 1px;">
                SKILL-AWARE AI ASSISTANT
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Welcome / Onboarding Hero
# ---------------------------------------------------------------------------

def welcome_hero() -> None:
    """Show the welcome screen with getting-started guidance."""
    st.markdown(
        """
        <div class="hero-section">
            <div class="hero-title">🧠 SquadSense</div>
            <div class="hero-subtitle">
                Your codebase, understood. Ask anything.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">📂</div>
                <div class="feature-title">1. Add Your Code</div>
                <div class="feature-desc">
                    Drop Java/TypeScript files into <code>data/code/</code>
                    and docs into <code>data/docs/</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">2. Generate a Skill</div>
                <div class="feature-desc">
                    Use the sidebar to run Discovery.
                    AI agents analyze your code and create a Skill Manifest.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="feature-card">
                <div class="feature-icon">💬</div>
                <div class="feature-title">3. Start Chatting</div>
                <div class="feature-desc">
                    Select a Skill Hat and ask questions.
                    Answers follow YOUR codebase's patterns.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # How it works
    with st.expander("🔍 How does it work?", expanded=False):
        st.markdown(
            """
            **SquadSense** uses an **LLM Council** — three AI agents that each specialize in a different area:

            | Agent | Focus |
            |-------|-------|
            | 🏗️ **Architect** | Structural patterns, entity maps, API surfaces |
            | 🧠 **Domain Expert** | Business logic, formulas, validation rules |
            | 🔬 **Quality** | Industry standards, deviations, best practices |

            Their analyses are merged into a **SKILLS.md** manifest — a structured knowledge document
            that teaches the chat AI exactly how YOUR codebase works.

            When you ask a question, the AI:
            1. Loads the relevant Skill Manifest
            2. Searches your code & docs for context (RAG)
            3. Answers using YOUR patterns, not generic knowledge
            """
        )

    # Getting started checklist
    with st.expander("✅ Setup Checklist", expanded=True):
        st.markdown(
            """
            Before you begin, make sure you have:

            1. **Added your API key** → Edit `.env` and set `GOOGLE_API_KEY`
            2. **Placed your code** → Copy `.java` / `.ts` files into `data/code/`
            3. **Placed your docs** → Copy `.md` files into `data/docs/`

            Then use the **sidebar** to run Discovery → Generate your first Skill! 👉
            """
        )


# ---------------------------------------------------------------------------
# Step Indicator
# ---------------------------------------------------------------------------

def step_indicator(number: int, title: str, description: str, done: bool = False, active: bool = False) -> None:
    """Render a step card with number badge."""
    css_class = "done" if done else ("active" if active else "")
    number_class = "done" if done else ""
    icon = "✓" if done else str(number)

    st.sidebar.markdown(
        f"""
        <div class="step-card {css_class}" style="padding: 0.8rem 1rem; margin-bottom: 0.6rem;">
            <div style="display: flex; align-items: center;">
                <span class="step-number {number_class}">{icon}</span>
                <div>
                    <div style="color: #e0e4f0; font-weight: 600; font-size: 0.9rem;">{title}</div>
                    <div style="color: #6b7199; font-size: 0.78rem;">{description}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Skill Badge
# ---------------------------------------------------------------------------

def skill_badge(skill_name: str) -> None:
    """Display a coloured skill-mode indicator badge."""
    st.markdown(
        f"""
        <div style="margin-bottom: 1rem;">
            <span class="skill-badge">🎯 {skill_name.upper()} MODE</span>
            <span style="color: #6b7199; font-size: 0.85rem; margin-left: 10px;">
                Answers follow this skill's patterns & rules
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Hint Box
# ---------------------------------------------------------------------------

def hint_box(text: str) -> None:
    """Show a subtle hint/tip box."""
    st.sidebar.markdown(
        f'<div class="hint-box">💡 {text}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Discovery Panel
# ---------------------------------------------------------------------------

def discovery_panel(has_data: bool = False) -> dict[str, Any] | None:
    """
    Render the Discovery Mode sidebar section.

    Returns:
        A dict with 'data_path' and 'skill_name' when the user clicks
        the generate button, or None otherwise.
    """
    st.sidebar.markdown(
        """
        <div style="margin: 0.5rem 0 0.3rem;">
            <span style="color: #e0e4f0; font-weight: 700; font-size: 1rem;">
                🔍 Discovery Mode
            </span>
            <span style="color: #6b7199; font-size: 0.78rem; display: block; margin-top: 2px;">
                Analyze your code & docs to generate a Skill Manifest
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    data_path = st.sidebar.text_input(
        "📁 Data folder",
        value="data",
        help="Path to the folder containing `code/` and `docs/` subfolders with your source files.",
    )

    skill_name = st.sidebar.text_input(
        "🏷️ Skill name",
        value="",
        placeholder="e.g. staking, authentication, payments",
        help="Give a name to this skill domain. This becomes the 'Skill Hat' you can chat with.",
    )

    if not skill_name.strip():
        hint_box("Enter a skill name like **staking** or **auth** — this identifies the domain you're analyzing.")

    clicked = st.sidebar.button(
        "⚡ Ingest & Generate Skill",
        type="primary",
        use_container_width=True,
        disabled=not skill_name.strip(),
    )

    if clicked:
        if not skill_name.strip():
            st.sidebar.error("⚠️ Please enter a skill name first.")
            return None
        return {"data_path": data_path.strip(), "skill_name": skill_name.strip()}

    return None


# ---------------------------------------------------------------------------
# Interaction Panel
# ---------------------------------------------------------------------------

def interaction_panel(available_skills: list[str]) -> str | None:
    """
    Render the Interaction Mode sidebar section.

    Returns:
        Selected skill name, or None if no skills are available.
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="margin: 0.3rem 0;">
            <span style="color: #e0e4f0; font-weight: 700; font-size: 1rem;">
                💬 Chat Mode
            </span>
            <span style="color: #6b7199; font-size: 0.78rem; display: block; margin-top: 2px;">
                Ask questions using a generated Skill Hat
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not available_skills:
        st.sidebar.markdown(
            """
            <div style="
                background: rgba(255,200,60,0.08);
                border: 1px solid rgba(255,200,60,0.2);
                border-radius: 10px;
                padding: 12px;
                margin: 8px 0;
                color: #d4b84a;
                font-size: 0.85rem;
            ">
                <strong>No skills yet</strong><br>
                <span style="color: #9a8a3a;">
                    Run Discovery above first to generate a Skill Hat, then come back here to start chatting.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return None

    selected = st.sidebar.selectbox(
        "🎓 Select Skill Hat",
        options=available_skills,
        format_func=lambda x: f"🎯 {x.upper()}",
        help="Each Skill Hat is a specialized AI persona trained on a specific domain of your codebase.",
    )

    st.sidebar.markdown(
        f"""
        <div class="hint-box" style="margin-top: 4px;">
            Selected <strong>{selected.upper()}</strong> — the AI will answer
            using this domain's patterns, rules, and standards.
        </div>
        """,
        unsafe_allow_html=True,
    )

    return selected


# ---------------------------------------------------------------------------
# Status Panel
# ---------------------------------------------------------------------------

def status_panel(api_keys: dict[str, bool], skills_count: int) -> None:
    """Show system status in the sidebar footer."""
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="color: #6b7199; font-weight: 600; font-size: 0.8rem;
                     letter-spacing: 0.5px; margin-bottom: 6px;">
            ⚙️ SYSTEM STATUS
        </div>
        """,
        unsafe_allow_html=True,
    )

    items = []
    for service, configured in api_keys.items():
        if service == "google":
            label = "Google Gemini"
            pill_class = "ready" if configured else "missing"
            pill_text = "Ready" if configured else "Missing — Required"
        elif service == "anthropic":
            label = "Anthropic Claude"
            pill_class = "ready" if configured else "optional"
            pill_text = "Ready" if configured else "Optional"
        elif service == "github":
            label = "GitHub API"
            pill_class = "ready" if configured else "optional"
            pill_text = "Ready" if configured else "Using local files"
        elif service == "confluence":
            label = "Confluence"
            pill_class = "ready" if configured else "optional"
            pill_text = "Ready" if configured else "Using local files"
        else:
            label = service.capitalize()
            pill_class = "ready" if configured else "missing"
            pill_text = "Ready" if configured else "Missing"

        items.append(
            f'<div style="display: flex; justify-content: space-between; align-items: center; '
            f'margin: 4px 0; font-size: 0.8rem;">'
            f'<span style="color: #8890b5;">{label}</span>'
            f'<span class="status-pill {pill_class}">{pill_text}</span>'
            f'</div>'
        )

    items.append(
        f'<div style="display: flex; justify-content: space-between; align-items: center; '
        f'margin: 6px 0 0; padding-top: 6px; border-top: 1px solid rgba(102,126,234,0.1); font-size: 0.8rem;">'
        f'<span style="color: #8890b5;">Skills Generated</span>'
        f'<span style="color: #e0e4f0; font-weight: 600;">{skills_count}</span>'
        f'</div>'
    )

    st.sidebar.markdown(
        f'<div style="background: rgba(255,255,255,0.02); border-radius: 10px; padding: 10px 12px;">'
        f'{"".join(items)}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Chat Welcome (inside chat area)
# ---------------------------------------------------------------------------

def chat_welcome(skill_name: str) -> None:
    """Show welcome message when a skill is selected but no messages yet."""
    st.markdown(
        f"""
        <div style="text-align: center; padding: 2rem 1rem; color: #6b7199;">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">💬</div>
            <div style="color: #e0e4f0; font-size: 1.2rem; font-weight: 600; margin-bottom: 0.3rem;">
                Ready to chat about {skill_name.upper()}
            </div>
            <div style="max-width: 450px; margin: 0 auto; font-size: 0.9rem; line-height: 1.6;">
                Ask anything about this domain — architecture, business logic,
                implementation patterns, or code quality.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Suggestion chips
    st.markdown(
        """
        <div style="text-align: center; color: #6b7199; font-size: 0.8rem; margin: 0.5rem 0;">
            Try asking:
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div style="background: rgba(102,126,234,0.06); border: 1px solid rgba(102,126,234,0.15);
                 border-radius: 10px; padding: 10px 14px; margin: 4px 0; color: #b0b8e8; font-size: 0.85rem; cursor: pointer;">
                🏗️ "What design patterns does {skill_name} use?"
            </div>
            <div style="background: rgba(102,126,234,0.06); border: 1px solid rgba(102,126,234,0.15);
                 border-radius: 10px; padding: 10px 14px; margin: 4px 0; color: #b0b8e8; font-size: 0.85rem; cursor: pointer;">
                📋 "What validation rules apply here?"
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div style="background: rgba(102,126,234,0.06); border: 1px solid rgba(102,126,234,0.15);
                 border-radius: 10px; padding: 10px 14px; margin: 4px 0; color: #b0b8e8; font-size: 0.85rem; cursor: pointer;">
                🧠 "Explain the main entities and relationships"
            </div>
            <div style="background: rgba(102,126,234,0.06); border: 1px solid rgba(102,126,234,0.15);
                 border-radius: 10px; padding: 10px 14px; margin: 4px 0; color: #b0b8e8; font-size: 0.85rem; cursor: pointer;">
                ⚠️ "What quality issues exist in the code?"
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Chat Message
# ---------------------------------------------------------------------------

def chat_message_block(role: str, content: str) -> None:
    """Render a styled chat message."""
    with st.chat_message(role):
        st.markdown(content)


# ---------------------------------------------------------------------------
# Source Citations
# ---------------------------------------------------------------------------

def source_citations(sources: list[dict]) -> None:
    """Render source citations in a clean format."""
    if not sources:
        return

    with st.expander(f"📚 Sources ({len(sources)} chunks referenced)", expanded=False):
        for i, src in enumerate(sources, 1):
            source_id = src.get("id", "unknown")
            score = src.get("score", 0)
            source_type = src.get("metadata", {}).get("type", "unknown")

            # Color code by type
            type_color = "#667eea" if source_type == "code" else "#e066a0"
            type_label = "CODE" if source_type == "code" else "DOC"

            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 10px; padding: 6px 0;
                     border-bottom: 1px solid rgba(102,126,234,0.08);">
                    <span style="color: {type_color}; font-size: 0.7rem; font-weight: 700;
                          background: {type_color}15; padding: 2px 8px; border-radius: 4px;">
                        {type_label}
                    </span>
                    <span style="color: #b0b8e8; font-size: 0.82rem; flex: 1;">
                        <code>{source_id}</code>
                    </span>
                    <span style="color: #6b7199; font-size: 0.75rem;">
                        relevance: {score:.0%}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
