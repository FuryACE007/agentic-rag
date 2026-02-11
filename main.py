"""
main.py — FastAPI entrypoint for SquadSense.

Exposes REST endpoints for:
  - Discovery pipeline (ingest + council → SKILLS.md)
  - Skill-aware chat
  - Skill listing & health checks
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure src/ is importable
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

load_dotenv()

from src.ingestion.cast_parser import parse_file
from src.ingestion.chunker import SemanticChunkerPipeline
from src.ingestion.connectors import ConfluenceConnector, GitHubConnector
from src.knowledge.vector_store import VectorStore
from src.orchestration.adk_core import (
    ChatRequest,
    ChatResponse,
    DiscoveryResult,
    validate_api_keys,
)
from src.orchestration.chat_agent import answer
from src.orchestration.council_agents import run_council
from src.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SquadSense API",
    description="Skill-Aware AI Developer Assistant — Agentic RAG System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    """Request to trigger the discovery pipeline."""
    data_path: str = "data"
    skill_name: str
    code_extensions: list[str] = Field(
        default_factory=lambda: [".java", ".ts", ".tsx"]
    )


class SkillListResponse(BaseModel):
    """Response listing available skills."""
    skills: list[str]
    count: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    api_keys: dict[str, bool]
    skills_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint showing API key status and skill count."""
    registry = SkillRegistry()
    return HealthResponse(
        api_keys=validate_api_keys(),
        skills_count=len(registry.list_skills()),
    )


@app.get("/api/skills", response_model=SkillListResponse)
async def list_skills() -> SkillListResponse:
    """List all available skill manifests."""
    registry = SkillRegistry()
    skills = registry.list_skills()
    return SkillListResponse(skills=skills, count=len(skills))


@app.post("/api/discover", response_model=DiscoveryResult)
async def discover(request: DiscoverRequest) -> DiscoveryResult:
    """
    Run the full discovery pipeline:
      1. Ingest code & docs from the data folder
      2. Parse with Tree-sitter
      3. Chunk and embed into ChromaDB
      4. Run LLM Council (Architect, Domain, Quality)
      5. Synthesize into SKILLS.md

    This is a long-running operation.
    """
    try:
        # --- Step 1: Ingest ---
        code_connector = GitHubConnector(local_dir=f"{request.data_path}/code")
        doc_connector = ConfluenceConnector(local_dir=f"{request.data_path}/docs")

        extensions = {ext if ext.startswith(".") else f".{ext}" for ext in request.code_extensions}

        code_docs = await code_connector.fetch_files(extensions=extensions)
        doc_docs = await doc_connector.fetch_pages()

        # --- Step 2: Parse ---
        all_code_chunks = []
        for doc in code_docs:
            file_path = doc.metadata.get("local_path", doc.source)
            chunks = parse_file(doc.content, file_path)
            all_code_chunks.extend(chunks)

        # --- Step 3: Chunk ---
        chunker = SemanticChunkerPipeline()
        semantic_code = chunker.chunk_code(all_code_chunks)
        semantic_docs = []
        for doc in doc_docs:
            semantic_docs.extend(
                chunker.chunk_document(doc.content, doc.source, doc.file_type)
            )

        all_semantic = semantic_code + semantic_docs

        # --- Step 4: Embed in ChromaDB ---
        store = VectorStore()
        chunks_to_upsert = [
            {"id": c.id, "content": c.content, "metadata": c.metadata}
            for c in all_semantic
        ]
        stored = store.upsert_chunks(request.skill_name, chunks_to_upsert)

        # --- Step 5: Run Council ---
        combined_text = "\n\n---\n\n".join(
            c.content for c in all_semantic[:50]  # Cap for LLM context window
        )
        result = await run_council(combined_text, request.skill_name)
        result.chunks_ingested = stored

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Skill-aware chat endpoint.

    Accepts a query and skill_hat, returns an answer grounded in
    the skill's manifest and relevant code/doc chunks.
    """
    registry = SkillRegistry()
    if not registry.skill_exists(request.skill_hat):
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{request.skill_hat}' not found. Run discovery first.",
        )

    return await answer(request)


# ---------------------------------------------------------------------------
# Startup Event
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    """Log configuration on startup."""
    api_keys = validate_api_keys()
    registry = SkillRegistry()
    skills = registry.list_skills()

    print("=" * 60)
    print("🧠 SquadSense API Starting")
    print("=" * 60)
    print(f"   Google API Key:    {'✅ Set' if api_keys['google'] else '❌ Missing'}")
    print(f"   Anthropic API Key: {'✅ Set' if api_keys['anthropic'] else '❌ Missing'}")
    print(f"   GitHub Token:      {'✅ Set' if api_keys['github'] else '❌ Missing'}")
    print(f"   Confluence:        {'✅ Set' if api_keys['confluence'] else '❌ Missing'}")
    print(f"   Available Skills:  {skills if skills else 'None (run discovery first)'}")
    print("=" * 60)
