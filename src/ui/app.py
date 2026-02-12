"""
app.py — Main Streamlit entrypoint for Nexus.

A self-guiding UI with two modes:
  - Discovery: Ingest code/docs → Generate a Skill Manifest via LLM Council
  - Chat: Ask questions using a Skill Hat for domain-specific answers
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st

# Ensure the project root is importable
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.orchestration.adk_core import ChatRequest, validate_api_keys
from src.skills.registry import SkillRegistry
from src.ui.components import (
    GLOBAL_CSS,
    app_header,
    chat_message_block,
    chat_welcome,
    discovery_panel,
    hint_box,
    interaction_panel,
    skill_badge,
    source_citations,
    status_panel,
    step_indicator,
    welcome_hero,
)


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Nexus — Skill-Aware AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject global CSS
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_skill" not in st.session_state:
    st.session_state.current_skill = None
if "discovery_complete" not in st.session_state:
    st.session_state.discovery_complete = False
if "last_discovery_skill" not in st.session_state:
    st.session_state.last_discovery_skill = None


# ---------------------------------------------------------------------------
# Async Helper
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from synchronous Streamlit context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Data Validation
# ---------------------------------------------------------------------------

def _check_data_folder(data_path: str) -> dict:
    """Check what files exist in the data folder."""
    code_dir = Path(data_path) / "code"
    docs_dir = Path(data_path) / "docs"

    code_files = []
    doc_files = []

    if code_dir.exists():
        code_files = list(code_dir.rglob("*.java")) + list(code_dir.rglob("*.ts")) + list(code_dir.rglob("*.tsx"))

    if docs_dir.exists():
        doc_files = list(docs_dir.rglob("*.md")) + list(docs_dir.rglob("*.html")) + list(docs_dir.rglob("*.txt"))

    return {
        "code_dir_exists": code_dir.exists(),
        "docs_dir_exists": docs_dir.exists(),
        "code_files": code_files,
        "doc_files": doc_files,
        "code_count": len(code_files),
        "doc_count": len(doc_files),
        "has_any": len(code_files) + len(doc_files) > 0,
    }


# ---------------------------------------------------------------------------
# Discovery Pipeline
# ---------------------------------------------------------------------------

def run_discovery(data_path: str, skill_name: str) -> None:
    """Execute the full discovery pipeline with detailed progress."""
    from src.ingestion.cast_parser import parse_file
    from src.ingestion.chunker import SemanticChunkerPipeline
    from src.ingestion.connectors import ConfluenceConnector, GitHubConnector
    from src.knowledge.vector_store import VectorStore
    from src.orchestration.council_agents import run_council

    # Pre-flight check
    data_info = _check_data_folder(data_path)
    if not data_info["has_any"]:
        st.error(
            f"❌ **No files found** in `{data_path}/code/` or `{data_path}/docs/`.\n\n"
            "Please add your source files first:\n"
            f"- Java/TypeScript code → `{data_path}/code/`\n"
            f"- Markdown/HTML docs → `{data_path}/docs/`"
        )
        return

    # Show what we found
    st.markdown(
        f"""
        <div style="background: rgba(72,199,142,0.08); border: 1px solid rgba(72,199,142,0.2);
             border-radius: 12px; padding: 14px 18px; margin-bottom: 1rem;">
            <div style="color: #48c78e; font-weight: 600; margin-bottom: 6px;">
                📂 Files Found
            </div>
            <div style="color: #9cbfac; font-size: 0.88rem;">
                <strong>{data_info['code_count']}</strong> code files
                ({', '.join(f.suffix for f in data_info['code_files'][:5])})
                &nbsp;·&nbsp;
                <strong>{data_info['doc_count']}</strong> doc files
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Progress container
    progress = st.progress(0)
    status_text = st.empty()

    # --- Step 1: Ingest ---
    status_text.markdown("**Step 1/5** — 📂 Ingesting files from data folder...")
    progress.progress(10)

    code_connector = GitHubConnector(local_dir=f"{data_path}/code")
    doc_connector = ConfluenceConnector(local_dir=f"{data_path}/docs")

    code_docs = _run_async(code_connector.fetch_files())
    doc_docs = _run_async(doc_connector.fetch_pages())

    st.info(f"📄 Ingested **{len(code_docs)}** code files and **{len(doc_docs)}** documentation files.")
    progress.progress(20)

    # --- Step 2: Parse ---
    status_text.markdown("**Step 2/5** — 🌳 Parsing code with Tree-sitter (extracting methods & functions)...")
    progress.progress(30)

    all_code_chunks = []
    for doc in code_docs:
        file_path = doc.metadata.get("local_path", doc.source)
        chunks = parse_file(doc.content, file_path)
        all_code_chunks.extend(chunks)

    st.info(f"🔍 Extracted **{len(all_code_chunks)}** code units (methods, functions, classes).")
    progress.progress(45)

    # --- Step 3: Chunk ---
    status_text.markdown("**Step 3/5** — 📦 Creating semantic chunks for embedding...")
    progress.progress(50)

    chunker = SemanticChunkerPipeline()
    semantic_code = chunker.chunk_code(all_code_chunks)
    semantic_docs = []
    for doc in doc_docs:
        semantic_docs.extend(chunker.chunk_document(doc.content, doc.source, doc.file_type))

    all_semantic = semantic_code + semantic_docs
    st.info(
        f"📊 Created **{len(all_semantic)}** semantic chunks "
        f"({len(semantic_code)} from code, {len(semantic_docs)} from docs)."
    )
    progress.progress(60)

    # --- Step 4: Embed ---
    status_text.markdown("**Step 4/5** — 💾 Embedding and storing in vector database...")
    progress.progress(65)

    store = VectorStore()
    chunks_to_upsert = [
        {"id": c.id, "content": c.content, "metadata": c.metadata}
        for c in all_semantic
    ]
    stored = store.upsert_chunks(skill_name, chunks_to_upsert)
    st.info(f"✅ Stored **{stored}** chunks in ChromaDB collection `{skill_name}`.")
    progress.progress(75)

    # --- Step 5: LLM Council ---
    status_text.markdown(
        "**Step 5/5** — 🤖 Running LLM Council "
        "(Architect · Domain Expert · Quality Agent)... _This takes ~60 seconds._"
    )
    progress.progress(80)

    combined_text = "\n\n---\n\n".join(c.content for c in all_semantic[:50])
    result = _run_async(run_council(combined_text, skill_name))
    result.chunks_ingested = stored

    progress.progress(100)
    status_text.markdown("**✨ Discovery complete!**")

    # --- Results ---
    if result.skills_md_content:
        st.session_state.discovery_complete = True
        st.session_state.last_discovery_skill = skill_name

        st.markdown(
            f"""
            <div style="background: rgba(72,199,142,0.1); border: 1px solid rgba(72,199,142,0.3);
                 border-radius: 14px; padding: 18px 22px; margin: 1rem 0;">
                <div style="color: #48c78e; font-weight: 700; font-size: 1.1rem; margin-bottom: 6px;">
                    🎉 Skill "{skill_name.upper()}" Generated Successfully!
                </div>
                <div style="color: #9cbfac; font-size: 0.9rem;">
                    Manifest saved to <code>src/skills/manifests/{skill_name.upper()}_SKILLS.md</code><br>
                    Now select <strong>{skill_name.upper()}</strong> in the Chat Mode sidebar to start asking questions.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("📋 View Generated SKILLS.md", expanded=False):
            st.markdown(result.skills_md_content)

        with st.expander("🔍 Agent Analysis Details", expanded=False):
            for resp in result.agent_responses:
                if resp.success:
                    st.markdown(f"### {resp.agent_name.replace('_', ' ').title()}")
                    st.markdown(resp.content)
                    st.markdown("---")
                elif resp.error:
                    st.warning(f"⚠️ **{resp.agent_name}** encountered an error: {resp.error}")
    else:
        st.error(
            "❌ Failed to generate SKILLS.md.\n\n"
            "**Common causes:**\n"
            "- `GOOGLE_API_KEY` not set in `.env`\n"
            "- API quota exceeded\n"
            "- Network issue\n\n"
            "Check the agent details below for specific errors."
        )
        for resp in (result.agent_responses or []):
            if resp.error:
                st.error(f"**{resp.agent_name}:** {resp.error}")


# ---------------------------------------------------------------------------
# Chat Interface
# ---------------------------------------------------------------------------

def chat_interface(skill_hat: str) -> None:
    """Render the skill-aware chat interface."""
    from src.orchestration.chat_agent import answer

    skill_badge(skill_hat)

    # Show welcome suggestions if no messages yet
    if not st.session_state.messages:
        chat_welcome(skill_hat)

    # Display chat history
    for msg in st.session_state.messages:
        chat_message_block(msg["role"], msg["content"])
        # Show sources for assistant messages
        if msg["role"] == "assistant" and msg.get("sources"):
            source_citations(msg["sources"])

    # Chat input
    if user_input := st.chat_input(f"Ask about {skill_hat}..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        chat_message_block("user", user_input)

        # Generate response
        with st.spinner("🧠 Searching your codebase and generating answer..."):
            request = ChatRequest(
                query=user_input,
                skill_hat=skill_hat,
                conversation_history=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ],
            )
            response = _run_async(answer(request))

        # Add assistant message
        msg_data = {
            "role": "assistant",
            "content": response.answer,
            "sources": response.sources or [],
        }
        st.session_state.messages.append(msg_data)
        chat_message_block("assistant", response.answer)

        if response.sources:
            source_citations(response.sources)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def main() -> None:
    """Nexus main application."""

    # --- Sidebar ---
    app_header()

    registry = SkillRegistry()
    api_keys = validate_api_keys()
    available_skills = registry.list_skills()
    has_google_key = api_keys.get("google", False)

    # Step indicators in sidebar
    st.sidebar.markdown("---")

    data_info = _check_data_folder("data")
    has_data = data_info["has_any"]
    has_skills = len(available_skills) > 0

    step_indicator(1, "Add Your Data", f"{data_info['code_count']} code, {data_info['doc_count']} docs found", done=has_data)
    step_indicator(2, "Generate a Skill", f"{len(available_skills)} skill(s) ready" if has_skills else "Run Discovery below", done=has_skills, active=has_data and not has_skills)
    step_indicator(3, "Start Chatting", "Select a Skill Hat below" if has_skills else "Waiting for Step 2", done=False, active=has_skills)

    st.sidebar.markdown("---")

    # Warn if no API key
    if not has_google_key:
        st.sidebar.markdown(
            """
            <div style="background: rgba(255,100,100,0.08); border: 1px solid rgba(255,100,100,0.2);
                 border-radius: 10px; padding: 12px; margin: 0 0 10px; font-size: 0.85rem;">
                <strong style="color: #ff6464;">⚠️ API Key Missing</strong><br>
                <span style="color: #c96464;">
                    Set <code>GOOGLE_API_KEY</code> in <code>.env</code> to enable Discovery & Chat.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Discovery panel
    discovery_result = discovery_panel(has_data=has_data)

    # Interaction panel
    selected_skill = interaction_panel(available_skills)

    # If skill changed, clear chat
    if selected_skill and selected_skill != st.session_state.current_skill:
        st.session_state.current_skill = selected_skill
        st.session_state.messages = []

    # Status footer
    status_panel(api_keys, len(available_skills))

    # --- Main Area ---

    # Handle discovery trigger
    if discovery_result:
        run_discovery(
            data_path=discovery_result["data_path"],
            skill_name=discovery_result["skill_name"],
        )

    # Handle chat or welcome
    elif selected_skill:
        chat_interface(selected_skill)

    else:
        welcome_hero()


if __name__ == "__main__":
    main()
