"""
vector_store.py — ChromaDB wrapper for SquadSense knowledge persistence.

Manages collections per skill domain, handles upserting semantic chunks
and querying with metadata filters.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class QueryResult(BaseModel):
    """A single query result from the vector store."""
    id: str
    content: str
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Vector Store
# ---------------------------------------------------------------------------

class VectorStore:
    """
    ChromaDB wrapper providing collection-per-skill management,
    chunk upserting, and filtered search.

    Uses ChromaDB's default embedding function (all-MiniLM-L6-v2)
    for the MVP. Can be swapped for OpenAI/Cohere embeddings later.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
    ) -> None:
        self.persist_dir = persist_dir or os.getenv(
            "CHROMADB_PERSIST_DIR", "./chromadb_store"
        )
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def get_or_create_collection(self, skill_name: str) -> chromadb.Collection:
        """
        Get or create a ChromaDB collection for the given skill.
        Collection names are normalized to lowercase with underscores.
        """
        collection_name = self._normalize_name(skill_name)
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"skill": skill_name},
        )

    def delete_collection(self, skill_name: str) -> None:
        """Delete a collection by skill name."""
        collection_name = self._normalize_name(skill_name)
        try:
            self._client.delete_collection(collection_name)
        except ValueError:
            pass  # Collection doesn't exist

    def list_collections(self) -> list[str]:
        """List all collection names in the vector store."""
        collections = self._client.list_collections()
        return [c.name for c in collections]

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        skill_name: str,
        chunks: list[dict[str, Any]],
    ) -> int:
        """
        Upsert semantic chunks into the skill's collection.

        Each chunk dict must have: 'id', 'content', and optionally 'metadata'.

        Args:
            skill_name: The skill collection to write to.
            chunks:     List of chunk dicts.

        Returns:
            Number of chunks upserted.
        """
        if not chunks:
            return 0

        collection = self.get_or_create_collection(skill_name)

        ids = [c["id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        # ChromaDB handles batch sizes internally
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return len(chunks)

    def query(
        self,
        skill_name: str,
        query_text: str,
        n_results: int = 5,
        metadata_filter: Optional[dict] = None,
    ) -> list[QueryResult]:
        """
        Query the vector store for relevant chunks.

        Args:
            skill_name:      Collection to search in.
            query_text:      The query string.
            n_results:       Number of results to return.
            metadata_filter: Optional ChromaDB where-filter dict.

        Returns:
            List of QueryResult objects ranked by relevance.
        """
        collection = self.get_or_create_collection(skill_name)

        query_params: dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": min(n_results, collection.count() or 1),
        }
        if metadata_filter:
            query_params["where"] = metadata_filter

        results = collection.query(**query_params)

        query_results: list[QueryResult] = []
        if results["ids"] and results["ids"][0]:
            for idx, doc_id in enumerate(results["ids"][0]):
                query_results.append(QueryResult(
                    id=doc_id,
                    content=results["documents"][0][idx] if results["documents"] else "",
                    score=1.0 - (results["distances"][0][idx] if results["distances"] else 0.0),
                    metadata=results["metadatas"][0][idx] if results["metadatas"] else {},
                ))

        return query_results

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a skill name to a valid ChromaDB collection name."""
        normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
        # ChromaDB collection names must be 3–63 chars, start/end with alphanumeric
        if len(normalized) < 3:
            normalized = normalized + "_col"
        return normalized[:63]
