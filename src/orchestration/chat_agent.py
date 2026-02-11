"""
chat_agent.py — Skill-Aware QA Agent for the Interaction Phase.

Uses Google ADK's ``Agent`` class to create a chat agent that:
  1. Loads the selected skill's SKILLS.md into its system prompt
  2. Uses retrieval tools to fetch relevant code/docs from ChromaDB
  3. Answers user questions with skill-specific context
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import Agent

from src.orchestration.adk_core import (
    ChatRequest,
    ChatResponse,
    PipelineConfig,
    get_pipeline_config,
)
from src.orchestration.tools import retrieve_relevant_chunks, search_code, search_docs
from src.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# System Prompt Template
# ---------------------------------------------------------------------------

SKILL_AWARE_INSTRUCTION_TEMPLATE = """You are **SquadSense**, a Skill-Aware AI Developer Assistant.

You are currently operating in **{skill_hat} Mode**. You must answer all questions
using the specific patterns, business rules, entities, and coding standards defined
in the Skill Manifest below.

## Active Skill Manifest:
{skills_md_content}

## Your Responsibilities:
1. **Follow the patterns** defined in the skill manifest exactly
2. **Use domain vocabulary** as mapped in the manifest
3. **Apply the coding standards** (naming, testing, error handling) from the manifest
4. **Reference specific entities** and their relationships when explaining architecture
5. **Use the retrieval tools** to find relevant code and documentation when needed

## How to Answer:
- When asked to WRITE CODE: Follow the implementation guidelines strictly
- When asked to EXPLAIN: Reference the specific business logic and patterns
- When asked about TESTING: Apply the testing standards from the manifest
- When UNSURE: Use the search tools to find relevant context from the codebase

## Tool Usage:
- Use `retrieve_relevant_chunks` for general queries about the codebase
- Use `search_code` when looking for specific code implementations
- Use `search_docs` when looking for documentation or business rules

Always cite your sources when referencing specific code or documentation."""


# ---------------------------------------------------------------------------
# Agent Factory
# ---------------------------------------------------------------------------

def create_skill_aware_agent(
    skill_hat: str,
    config: PipelineConfig | None = None,
) -> Agent:
    """
    Create a Skill-Aware chat agent configured for the given skill domain.

    Args:
        skill_hat: The skill domain to activate (e.g. "staking").
        config:    Optional pipeline configuration.

    Returns:
        A configured Google ADK Agent instance.
    """
    if config is None:
        config = get_pipeline_config()

    registry = SkillRegistry(manifests_dir=config.skills_manifest_dir)
    skills_md_content = registry.load_skill(skill_hat)

    if not skills_md_content:
        skills_md_content = (
            f"*No SKILLS.md manifest found for '{skill_hat}'. "
            "Operating in general-purpose mode. "
            "Run Discovery first to generate a skill manifest.*"
        )

    instruction = SKILL_AWARE_INSTRUCTION_TEMPLATE.format(
        skill_hat=skill_hat.upper(),
        skills_md_content=skills_md_content,
    )

    return Agent(
        name=f"squadsense_{skill_hat.lower()}_agent",
        model=config.chat_model,
        instruction=instruction,
        description=f"Skill-Aware Developer Assistant for the {skill_hat} domain.",
        tools=[retrieve_relevant_chunks, search_code, search_docs],
    )


# ---------------------------------------------------------------------------
# Chat Entrypoint
# ---------------------------------------------------------------------------

async def answer(
    request: ChatRequest,
    config: PipelineConfig | None = None,
) -> ChatResponse:
    """
    Handle a skill-aware chat request.

    Workflow:
      1. Load the SKILLS.md for the selected skill hat
      2. Create/configure the ADK agent with skill context
      3. Retrieve relevant chunks from ChromaDB
      4. Generate and return the response

    Args:
        request: The incoming chat request with query and skill_hat.
        config:  Optional pipeline configuration.

    Returns:
        ChatResponse with the answer and source references.
    """
    if config is None:
        config = get_pipeline_config()

    try:
        # --- Step 1: Retrieve relevant context ---
        from src.knowledge.vector_store import VectorStore

        store = VectorStore(persist_dir=config.chromadb_persist_dir)
        relevant_chunks = store.query(
            skill_name=request.skill_hat,
            query_text=request.query,
            n_results=5,
        )

        context_text = "\n\n---\n\n".join(
            f"**Source:** {chunk.metadata.get('file_path', chunk.metadata.get('source', 'unknown'))}\n\n{chunk.content}"
            for chunk in relevant_chunks
        )

        # --- Step 2: Load skill manifest ---
        registry = SkillRegistry(manifests_dir=config.skills_manifest_dir)
        skills_content = registry.load_skill(request.skill_hat)

        # --- Step 3: Build prompt and invoke model ---
        import google.generativeai as genai

        model = genai.GenerativeModel(config.chat_model)

        system_instruction = SKILL_AWARE_INSTRUCTION_TEMPLATE.format(
            skill_hat=request.skill_hat.upper(),
            skills_md_content=skills_content or "*No manifest loaded*",
        )

        # Build conversation with context
        full_prompt = f"""{system_instruction}

## Relevant Codebase Context:
{context_text if context_text else "*No relevant chunks found in vector store.*"}

## Conversation History:
{_format_history(request.conversation_history)}

## Current Question:
{request.query}

Please provide a detailed, skill-aware answer:"""

        response = await model.generate_content_async(full_prompt)
        answer_text = response.text or "I was unable to generate a response. Please try again."

        sources = [
            {
                "id": chunk.id,
                "score": chunk.score,
                "metadata": chunk.metadata,
            }
            for chunk in relevant_chunks
        ]

        return ChatResponse(
            answer=answer_text,
            skill_hat=request.skill_hat,
            sources=sources,
            metadata={
                "model": config.chat_model,
                "chunks_used": len(relevant_chunks),
            },
        )

    except Exception as e:
        return ChatResponse(
            answer=f"❌ Error generating response: {str(e)}",
            skill_hat=request.skill_hat,
            sources=[],
            metadata={"error": str(e)},
        )


def _format_history(history: list[dict[str, str]]) -> str:
    """Format conversation history for the prompt."""
    if not history:
        return "*No prior conversation.*"

    parts: list[str] = []
    for msg in history[-5:]:  # Keep last 5 messages for context
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        parts.append(f"**{role}:** {content}")

    return "\n\n".join(parts)
