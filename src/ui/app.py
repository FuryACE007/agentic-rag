"""
app.py — Main Streamlit entrypoint for SquadSense.

Provides:
  - Discovery Mode: Ingest code/docs and generate a Skill Manifest
  - Interaction Mode: Chat with a Skill-Aware AI assistant
"""

from __future__ import annotations

import asyncio
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
    app_header,
    chat_message_block,
    discovery_panel,
    interaction_panel,
    skill_badge,
    status_indicator,
)

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SquadSense — Skill-Aware AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
    }
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 8px;
    }
    .stSidebar {
        background: rgba(15, 15, 35, 0.95);
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_skill" not in st.session_state:
    st.session_state.current_skill = None
if "discovery_running" not in st.session_state:
    st.session_state.discovery_running = False


# ---------------------------------------------------------------------------
# Helper: async bridge
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
# Discovery Pipeline
# ---------------------------------------------------------------------------

def run_discovery(data_path: str, skill_name: str) -> None:
    """Execute the full discovery pipeline: ingest → parse → embed → council."""
    from src.ingestion.cast_parser import parse_file
    from src.ingestion.chunker import SemanticChunkerPipeline
    from src.ingestion.connectors import GitHubConnector, ConfluenceConnector
    from src.knowledge.vector_store import VectorStore
    from src.orchestration.council_agents import run_council

    progress = st.progress(0, text="Starting discovery pipeline...")

    # --- Step 1: Ingest from connectors ---
    progress.progress(10, text="📂 Ingesting files...")
    code_connector = GitHubConnector(local_dir=f"{data_path}/code")
    doc_connector = ConfluenceConnector(local_dir=f"{data_path}/docs")

    code_docs = _run_async(code_connector.fetch_files())
    doc_docs = _run_async(doc_connector.fetch_pages())

    st.info(f"📄 Found {len(code_docs)} code files and {len(doc_docs)} doc files.")

    # --- Step 2: Parse code with Tree-sitter ---
    progress.progress(30, text="🌳 Parsing code with Tree-sitter...")
    all_code_chunks = []
    for doc in code_docs:
        file_path = doc.metadata.get("local_path", doc.source)
        chunks = parse_file(doc.content, file_path)
        all_code_chunks.extend(chunks)

    st.info(f"🔍 Extracted {len(all_code_chunks)} code units (methods/functions).")

    # --- Step 3: Chunk for embedding ---
    progress.progress(50, text="📦 Creating semantic chunks...")
    chunker = SemanticChunkerPipeline()
    semantic_code = chunker.chunk_code(all_code_chunks)
    semantic_docs = []
    for doc in doc_docs:
        semantic_docs.extend(chunker.chunk_document(doc.content, doc.source, doc.file_type))

    all_semantic = semantic_code + semantic_docs
    st.info(f"📊 Created {len(all_semantic)} semantic chunks ({len(semantic_code)} code, {len(semantic_docs)} docs).")

    # --- Step 4: Store in ChromaDB ---
    progress.progress(65, text="💾 Storing in vector database...")
    store = VectorStore()
    chunks_to_upsert = [
        {"id": c.id, "content": c.content, "metadata": c.metadata}
        for c in all_semantic
    ]
    stored = store.upsert_chunks(skill_name, chunks_to_upsert)
    st.info(f"✅ Stored {stored} chunks in ChromaDB collection '{skill_name}'.")

    # --- Step 5: Run LLM Council ---
    progress.progress(75, text="🤖 Running LLM Council (Architect · Domain · Quality)...")
    combined_text = "\n\n---\n\n".join(c.content for c in all_semantic[:50])  # Cap for context window

    result = _run_async(run_council(combined_text, skill_name))
    result.chunks_ingested = stored

    progress.progress(100, text="✨ Discovery complete!")

    if result.skills_md_content:
        st.success(f"🎉 Generated **{skill_name.upper()}_SKILLS.md** successfully!")
        with st.expander("📋 View Generated SKILLS.md", expanded=False):
            st.markdown(result.skills_md_content)

        # Show agent responses
        for resp in result.agent_responses:
            if resp.success:
                with st.expander(f"🔍 {resp.agent_name} Analysis"):
                    st.markdown(resp.content)
            elif resp.error:
                st.warning(f"⚠️ {resp.agent_name}: {resp.error}")
    else:
        st.error("❌ Failed to generate SKILLS.md. Check API keys and retry.")


# ---------------------------------------------------------------------------
# Chat Interface
# ---------------------------------------------------------------------------

def chat_interface(skill_hat: str) -> None:
    """Render the skill-aware chat interface."""
    from src.orchestration.chat_agent import answer

    # Show active skill badge
    skill_badge(skill_hat)

    # Display chat history
    for msg in st.session_state.messages:
        chat_message_block(msg["role"], msg["content"])

    # Chat input
    if user_input := st.chat_input(f"Ask about {skill_hat}..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        chat_message_block("user", user_input)

        # Generate response
        with st.spinner("🧠 Thinking..."):
            request = ChatRequest(
                query=user_input,
                skill_hat=skill_hat,
                conversation_history=st.session_state.messages[:-1],
            )
            response = _run_async(answer(request))

        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response.answer})
        chat_message_block("assistant", response.answer)

        # Show sources in expander
        if response.sources:
            with st.expander("📚 Sources", expanded=False):
                for src in response.sources:
                    st.markdown(
                        f"- `{src.get('id', 'unknown')}` "
                        f"(score: {src.get('score', 0):.2f})"
                    )


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def main() -> None:
    """SquadSense main application."""
    app_header()

    # --- Sidebar ---
    registry = SkillRegistry()
    api_keys = validate_api_keys()

    # Discovery panel
    discovery_result = discovery_panel()
    if discovery_result:
        run_discovery(
            data_path=discovery_result["data_path"],
            skill_name=discovery_result["skill_name"],
        )

    # Interaction panel
    available_skills = registry.list_skills()
    selected_skill = interaction_panel(available_skills)

    # Status
    status_indicator(api_keys)

    # --- Main Area ---
    if selected_skill:
        st.session_state.current_skill = selected_skill
        chat_interface(selected_skill)
    else:
        st.markdown(
            """
            <div style="text-align: center; padding: 4rem 2rem; color: #888;">
                <h2>👋 Welcome to SquadSense</h2>
                <p style="font-size: 1.1rem; max-width: 600px; margin: 0 auto;">
                    Start by running <strong>Discovery Mode</strong> in the sidebar
                    to ingest code and generate a Skill Manifest.
                    Then select a <strong>Skill Hat</strong> to start chatting.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
