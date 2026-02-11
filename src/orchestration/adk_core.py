"""
adk_core.py — Google ADK utilities, configuration, and shared scaffolding.

Provides configuration loading, model constants, and helper functions
that work alongside the official google-adk Agent/LlmAgent classes.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# ---------------------------------------------------------------------------
# Constants & Enums
# ---------------------------------------------------------------------------

class ModelProvider(str, Enum):
    """Supported LLM provider identifiers."""
    GEMINI = "gemini"
    CLAUDE = "claude"


class AgentRole(str, Enum):
    """Roles within the SquadSense pipeline."""
    ARCHITECT = "architect"
    DOMAIN_EXPERT = "domain_expert"
    QUALITY = "quality"
    SYNTHESIZER = "synthesizer"
    CHAT = "chat"


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    """Configuration for a single LLM model."""
    model_id: str
    provider: ModelProvider
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_model_id(cls, model_id: str, **kwargs: Any) -> "LLMConfig":
        """Auto-detect provider from model ID string."""
        if model_id.startswith("gemini"):
            provider = ModelProvider.GEMINI
        elif model_id.startswith("claude"):
            provider = ModelProvider.CLAUDE
        else:
            provider = ModelProvider.GEMINI  # default
        return cls(model_id=model_id, provider=provider, **kwargs)


class AgentConfig(BaseModel):
    """Configuration for a SquadSense agent."""
    name: str
    role: AgentRole
    model_id: str
    system_instruction: str = ""
    description: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class PipelineConfig(BaseModel):
    """Configuration for the full discovery/chat pipeline."""
    architect_model: str = Field(
        default_factory=lambda: os.getenv("ARCHITECT_MODEL", "gemini-1.5-pro")
    )
    domain_model: str = Field(
        default_factory=lambda: os.getenv("DOMAIN_MODEL", "claude-3-5-sonnet-20241022")
    )
    quality_model: str = Field(
        default_factory=lambda: os.getenv("QUALITY_MODEL", "claude-3-5-sonnet-20241022")
    )
    chat_model: str = Field(
        default_factory=lambda: os.getenv("CHAT_MODEL", "gemini-1.5-pro")
    )
    chromadb_persist_dir: str = Field(
        default_factory=lambda: os.getenv("CHROMADB_PERSIST_DIR", "./chromadb_store")
    )
    skills_manifest_dir: str = Field(
        default_factory=lambda: os.getenv("SKILLS_MANIFEST_DIR", "./src/skills/manifests")
    )
    data_dir: str = Field(
        default_factory=lambda: os.getenv("DATA_DIR", "./data")
    )


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Standardised response from any agent in the pipeline."""
    agent_name: str
    role: AgentRole
    content: str
    metadata: dict = Field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class DiscoveryResult(BaseModel):
    """Result from the full discovery pipeline."""
    skill_name: str
    skills_md_content: str
    agent_responses: list[AgentResponse] = Field(default_factory=list)
    chunks_ingested: int = 0


class ChatRequest(BaseModel):
    """Incoming chat request."""
    query: str
    skill_hat: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response from the skill-aware chat agent."""
    answer: str
    skill_hat: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_pipeline_config() -> PipelineConfig:
    """Load pipeline configuration from environment."""
    return PipelineConfig()


def validate_api_keys() -> dict[str, bool]:
    """Check which API keys are configured."""
    return {
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "github": bool(os.getenv("GITHUB_TOKEN")),
        "confluence": bool(os.getenv("CONFLUENCE_URL") and os.getenv("CONFLUENCE_TOKEN")),
    }
