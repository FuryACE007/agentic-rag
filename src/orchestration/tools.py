"""
tools.py — Retrieval tool functions for the Google ADK agents.

These are plain Python functions with typed signatures and docstrings.
Google ADK auto-wraps them as FunctionTool when assigned to an Agent's
``tools`` parameter, providing the LLM with schema for tool invocation.
"""

from __future__ import annotations

from src.knowledge.vector_store import VectorStore


# ---------------------------------------------------------------------------
# Shared vector store instance (lazy-initialized)
# ---------------------------------------------------------------------------

_vector_store: VectorStore | None = None


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# ---------------------------------------------------------------------------
# Retrieval Tools (plain functions —  ADK wraps these as FunctionTool)
# ---------------------------------------------------------------------------

def retrieve_relevant_chunks(
    query: str,
    skill_name: str,
    n_results: int = 5,
) -> list[dict]:
    """
    Search the vector database for chunks relevant to the user's query.

    Use this tool when you need to find code snippets, documentation,
    or architectural patterns from the ingested codebase that are
    relevant to answering the user's question.

    Args:
        query:      The search query describing what information is needed.
        skill_name: The skill domain to search within (e.g. "staking").
        n_results:  Maximum number of results to return.

    Returns:
        A list of dicts, each containing 'id', 'content', 'score', and 'metadata'.
    """
    store = _get_vector_store()
    results = store.query(
        skill_name=skill_name,
        query_text=query,
        n_results=n_results,
    )
    return [r.model_dump() for r in results]


def search_code(
    query: str,
    skill_name: str,
    n_results: int = 5,
) -> list[dict]:
    """
    Search specifically for CODE chunks in the vector database.

    Use this tool when the user asks about implementation details,
    method signatures, code patterns, or wants to see actual source code.

    Args:
        query:      The search query describing the code to find.
        skill_name: The skill domain to search within.
        n_results:  Maximum number of results to return.

    Returns:
        A list of code chunk dicts with 'id', 'content', 'score', 'metadata'.
    """
    store = _get_vector_store()
    results = store.query(
        skill_name=skill_name,
        query_text=query,
        n_results=n_results,
        metadata_filter={"type": "code"},
    )
    return [r.model_dump() for r in results]


def search_docs(
    query: str,
    skill_name: str,
    n_results: int = 5,
) -> list[dict]:
    """
    Search specifically for DOCUMENTATION chunks in the vector database.

    Use this tool when the user asks about business rules, architecture
    decisions, process flows, or high-level explanations.

    Args:
        query:      The search query describing the documentation to find.
        skill_name: The skill domain to search within.
        n_results:  Maximum number of results to return.

    Returns:
        A list of documentation chunk dicts with 'id', 'content', 'score', 'metadata'.
    """
    store = _get_vector_store()
    results = store.query(
        skill_name=skill_name,
        query_text=query,
        n_results=n_results,
        metadata_filter={"type": "doc"},
    )
    return [r.model_dump() for r in results]
