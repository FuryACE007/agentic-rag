# SquadSense — System Context & Architecture Guide

**For AI Assistants:** This document provides complete context about the SquadSense codebase, its architecture, design decisions, and implementation details.

---

## 🎯 Project Vision

**SquadSense** is a Skill-Aware AI Developer Assistant built as an enterprise Agentic RAG (Retrieval-Augmented Generation) system. It operates in two distinct phases:

### Phase 1: Discovery (The LLM Council)

- **Input:** Raw codebase (Java/TypeScript) + documentation (Markdown/HTML)
- **Process:** Three specialized AI agents (Architect, Domain Expert, Quality) analyze the code in parallel
- **Output:** A structured `SKILLS.md` manifest — the "Skill Hat" — containing patterns, rules, entities, and standards

### Phase 2: Interaction (Skill-Aware Chat)

- **Input:** Developer selects a Skill Hat (e.g., "Staking") and asks questions
- **Process:** AI loads the SKILLS.md into its system prompt, retrieves relevant code/docs from ChromaDB
- **Output:** Answers that follow the _specific_ patterns and rules defined in that skill domain

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                          │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │  Streamlit UI    │              │   FastAPI REST   │         │
│  │  (src/ui/app.py) │              │   (main.py)      │         │
│  └────────┬─────────┘              └────────┬─────────┘         │
└───────────┼──────────────────────────────────┼──────────────────┘
            │                                  │
            ▼                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Google ADK Agents (google.adk.agents.Agent)             │   │
│  │  ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐ │   │
│  │  │ Architect  │ │  Domain  │ │ Quality │ │Synthesizer │ │   │
│  │  │   Agent    │ │  Expert  │ │  Agent  │ │   Agent    │ │   │
│  │  └────────────┘ └──────────┘ └─────────┘ └────────────┘ │   │
│  │                                                          │   │
│  │  ┌────────────────────────────────────────────────────┐ │   │
│  │  │  Skill-Aware Chat Agent                            │ │   │
│  │  │  (Loads SKILLS.md + uses retrieval tools)          │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Tools: retrieve_relevant_chunks, search_code, search_docs      │
└─────────────┬────────────────────────────────┬───────────────────┘
              │                                │
              ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│   KNOWLEDGE LAYER         │    │   INGESTION PIPELINE         │
│                           │    │                              │
│  ┌────────────────────┐  │    │  ┌────────────────────────┐ │
│  │   ChromaDB         │  │    │  │  Tree-sitter cAST      │ │
│  │   Vector Store     │  │    │  │  Parser (Java/TS)      │ │
│  │                    │  │    │  └────────────────────────┘ │
│  │  Per-skill         │  │    │                              │
│  │  collections       │  │    │  ┌────────────────────────┐ │
│  │  with metadata     │  │    │  │  GitHub/Confluence     │ │
│  │  filters           │  │    │  │  Connectors            │ │
│  └────────────────────┘  │    │  └────────────────────────┘ │
│                           │    │                              │
│  Default embedding:       │    │  ┌────────────────────────┐ │
│  all-MiniLM-L6-v2        │    │  │  Semantic Chunker      │ │
│                           │    │  │  (Code + Docs)         │ │
└───────────────────────────┘    │  └────────────────────────┘ │
                                 └──────────────────────────────┘
```

---

## 📂 Project Structure

```
squadsense/
├── .env                        # API keys (GOOGLE_API_KEY, ANTHROPIC_API_KEY, etc.)
├── .gitignore                  # Excludes venv, chromadb_store, __pycache__
├── requirements.txt            # All dependencies with version pins
├── README.md                   # User-facing setup guide
├── CONTEXT.md                  # ← THIS FILE (for AI assistants)
├── main.py                     # FastAPI entrypoint
│
├── data/                       # Local data for MVP (gitignored)
│   ├── code/                   # Java/TypeScript source files
│   └── docs/                   # Markdown/HTML documentation
│
├── chromadb_store/             # Persistent vector DB (gitignored)
│
└── src/
    ├── ingestion/              # Data ingestion & parsing
    │   ├── cast_parser.py      # Tree-sitter extraction (Java/TS → CodeChunk)
    │   ├── connectors.py       # GitHub/Confluence fetchers (with local fallback)
    │   └── chunker.py          # Semantic chunking (merges small chunks)
    │
    ├── knowledge/              # Vector database layer
    │   └── vector_store.py     # ChromaDB wrapper (per-skill collections)
    │
    ├── orchestration/          # Agent orchestration (Google ADK)
    │   ├── adk_core.py         # Config, Pydantic models, enums
    │   ├── tools.py            # Retrieval tool functions (auto-wrapped by ADK)
    │   ├── council_agents.py   # LLM Council (3 analysts + synthesizer)
    │   └── chat_agent.py       # Skill-aware QA agent
    │
    ├── skills/                 # Skill manifest management
    │   ├── registry.py         # CRUD for *_SKILLS.md files
    │   └── manifests/          # Generated skill manifests (e.g., STAKING_SKILLS.md)
    │
    └── ui/                     # Streamlit frontend
        ├── app.py              # Main UI entrypoint
        └── components.py       # Reusable widgets (badges, panels, etc.)
```

---

## 🔑 Key Design Decisions

### 1. **Google ADK Direct Import (Stability)**

- **What:** Uses `google.adk.agents.Agent` from the official `google-adk` package
- **Why:** User requested direct import for stability instead of a custom ADK-style pattern
- **How:** Tools are plain Python functions with docstrings; ADK auto-wraps them as `FunctionTool`

### 2. **Tree-sitter Language Pack (No Compilation)**

- **What:** Uses `tree-sitter-language-pack` instead of deprecated `tree-sitter-languages`
- **Why:** Pre-built binary wheels for 165+ languages; no manual compilation needed
- **How:** `get_parser("java")` and `get_language("java")` from the language pack

### 3. **ChromaDB with Default Embeddings (MVP)**

- **What:** ChromaDB persistent client with default Sentence Transformer (`all-MiniLM-L6-v2`)
- **Why:** Fast setup for MVP; embeddings can be swapped later (OpenAI, Cohere, etc.)
- **How:** One collection per skill, metadata filters for code vs. docs

### 4. **Parallel Council Execution**

- **What:** Three analysis agents (Architect, Domain, Quality) run in parallel via `asyncio.gather`
- **Why:** Reduces total discovery time by ~3x
- **How:** Each agent analyzes the same code chunks independently, then Synthesizer merges

### 5. **Local Fallback for Connectors**

- **What:** GitHub/Confluence connectors read from `data/` if API tokens aren't set
- **Why:** Enables MVP testing without live API access
- **How:** `GitHubConnector.is_live` checks for `GITHUB_TOKEN`; falls back to `data/code/`

### 6. **Quality Agent Industry Standards Comparison** 🆕

- **What:** Quality Agent compares codebase against industry best practices (OWASP, SOLID, language style guides) and flags deviations with severity levels
- **Why:** Prevents the system from learning bad patterns even if they exist in the current codebase/documentation
- **How:**
  - Analyzes code against established standards (JUnit/Jest patterns, Google Java Style, OWASP Top 10, etc.)
  - Flags deviations as 🔴 CRITICAL, 🟠 HIGH, 🟡 MEDIUM, or 🟢 LOW
  - Provides "Acceptable Deviation?" analysis (some deviations may be justified for performance/domain reasons)
  - Synthesizer creates separate sections in SKILLS.md:
    - "Code Standards & Quality Baseline" (industry standards)
    - "⚠️ Quality Deviations & Corrections" (what's wrong + how to fix)
    - "DO/DON'T" with migration paths from bad to good patterns
- **Result:** SKILLS.md teaches CORRECT patterns, not just documents existing patterns

---

## 🧩 Core Components Explained

### Ingestion Pipeline (`src/ingestion/`)

#### `cast_parser.py` — Context-Aware Splitting

- **Purpose:** Extract structured code units (methods, functions) with their Javadoc/JSDoc
- **Key Functions:**
  - `extract_java_methods(file_content, file_path)` → `list[CodeChunk]`
  - `extract_typescript_functions(file_content, file_path)` → `list[CodeChunk]`
  - `parse_file(file_content, file_path)` — auto-detects language from extension
- **Heuristics:**
  - Skips trivial getters/setters (name starts with `get`/`set`/`is` AND ≤2 statements)
  - Captures preceding block comments as docstrings
- **Data Model:** `CodeChunk(name, language, body, docstring, start_line, end_line, file_path, chunk_type)`

#### `connectors.py` — Data Source Adapters

- **GitHubConnector:**
  - Live mode: Fetches via GitHub Contents API (`/repos/{owner}/{repo}/contents/{path}`)
  - Fallback: Reads from `data/code/` directory
  - Returns: `list[RawDocument]`
- **ConfluenceConnector:**
  - Live mode: Fetches via Confluence REST API v2 (`/wiki/api/v2/spaces/{id}/pages`)
  - Fallback: Reads from `data/docs/` directory
  - Returns: `list[RawDocument]`
- **Data Model:** `RawDocument(content, source, file_type, metadata)`

#### `chunker.py` — Semantic Chunking

- **CodeChunker:**
  - Merges adjacent small `CodeChunk`s from the same file into larger units
  - Configurable `max_chars=2048` (roughly 512 tokens)
  - Preserves docstrings + method bodies together
- **DocumentChunker:**
  - Splits on Markdown headers (`#`, `##`, etc.) and horizontal rules (`---`)
  - Falls back to character-based splitting with overlap if sections are too large
  - Configurable `max_chars=1500`, `overlap_chars=150`
- **Output:** `SemanticChunk(id, content, chunk_type, metadata)`

### Knowledge Layer (`src/knowledge/`)

#### `vector_store.py` — ChromaDB Wrapper

- **Purpose:** Persistent vector storage with per-skill collections
- **Key Methods:**
  - `get_or_create_collection(skill_name)` — normalizes name to valid ChromaDB format
  - `upsert_chunks(skill_name, chunks)` — batch insert/update
  - `query(skill_name, query_text, n_results, metadata_filter)` — semantic search
  - `list_collections()` — returns all skill names
- **Metadata Filters:** `{"type": "code"}` or `{"type": "doc"}` for targeted retrieval
- **Persistence:** Stored in `chromadb_store/` directory (gitignored)

### Orchestration Layer (`src/orchestration/`)

#### `adk_core.py` — Configuration & Models

- **Enums:** `ModelProvider`, `AgentRole`
- **Config Models:**
  - `LLMConfig` — model_id, provider, temperature, max_tokens
  - `AgentConfig` — name, role, model_id, system_instruction
  - `PipelineConfig` — loads from `.env` (ARCHITECT_MODEL, DOMAIN_MODEL, etc.)
- **Response Models:**
  - `AgentResponse` — agent_name, role, content, success, error
  - `DiscoveryResult` — skill_name, skills_md_content, agent_responses, chunks_ingested
  - `ChatRequest` / `ChatResponse` — for the QA pipeline
- **Helpers:** `validate_api_keys()` — checks which API keys are configured

#### `tools.py` — Retrieval Functions

- **Plain Python functions** with type hints and docstrings
- **ADK auto-wraps** these as `FunctionTool` when assigned to `Agent.tools`
- **Functions:**
  - `retrieve_relevant_chunks(query, skill_name, n_results)` — general search
  - `search_code(query, skill_name, n_results)` — filters `type=code`
  - `search_docs(query, skill_name, n_results)` — filters `type=doc`
- **Shared State:** Lazy-initialized `_vector_store` singleton

#### `council_agents.py` — The LLM Council

- **Agents:**
  1. **ArchitectAgent** — Analyzes structural patterns, entity relationships, layer boundaries
  2. **DomainExpertAgent** — Analyzes business logic, formulas, validation rules
  3. **QualityAgent** — **Compares against industry standards** (OWASP, SOLID, style guides), flags deviations with severity levels (🔴 CRITICAL → 🟢 LOW), provides "Acceptable Deviation?" analysis, and recommends fixes
  4. **SynthesizerAgent** — Merges all three analyses into structured `SKILLS.md` with separate sections for industry standards vs. current codebase deviations
- **System Prompts:** Each agent has a detailed instruction focusing on its specialty
  - **Quality Agent Prompt:** Includes framework for deviation detection, severity classification, and migration path recommendations
  - **Synthesizer Prompt:** Includes instructions to preserve quality deviations and teach correct patterns (not just document existing ones)
- **Execution:** `run_council(code_chunks_text, skill_name)` orchestrates:
  1. Create 4 agents (Architect, Domain, Quality, Synthesizer)
  2. Run first 3 in parallel via `asyncio.gather`
  3. Pass all 3 outputs to Synthesizer
  4. Save final `SKILLS.md` via `SkillRegistry`
- **LLM Invocation:** Uses `google.generativeai` directly for MVP (not ADK's Runner/Session)
- **Quality Output Structure:**
  - Executive Summary with deviation counts by severity
  - Industry Standards Comparison (Testing, Naming, Error Handling, Security, Architecture, Documentation, Code Style)
  - Positive Patterns (what's done right)
  - Tech Debt Inventory
  - Prioritized Action Items

#### `chat_agent.py` — Skill-Aware QA

- **Purpose:** Answer developer questions using skill-specific context
- **Workflow:**
  1. Load `{skill_hat}_SKILLS.md` from registry
  2. Inject manifest into system prompt template
  3. Retrieve relevant chunks from ChromaDB (top 5)
  4. Build full prompt: system instruction + context + conversation history + query
  5. Generate response via `google.generativeai`
  6. Return `ChatResponse` with answer + source citations
- **System Prompt Template:** `SKILL_AWARE_INSTRUCTION_TEMPLATE` — emphasizes following patterns, using domain vocabulary, citing sources

### Skills Layer (`src/skills/`)

#### `registry.py` — Manifest Manager

- **Purpose:** CRUD operations for `*_SKILLS.md` files
- **Methods:**
  - `list_skills()` — scans `manifests/` for `*_SKILLS.md`, returns skill names
  - `load_skill(skill_name)` — reads Markdown content
  - `save_skill(skill_name, content)` — writes to `{SKILL_NAME}_SKILLS.md`
  - `delete_skill(skill_name)` — removes manifest
  - `skill_exists(skill_name)` — boolean check
- **Normalization:** Skill names are uppercased and sanitized for filenames

### UI Layer (`src/ui/`)

#### `app.py` — Streamlit Entrypoint

- **Layout:**
  - **Sidebar:** Discovery panel + Interaction panel + Status indicators
  - **Main Area:** Chat interface with skill badge or welcome screen
- **Discovery Mode:**
  - User inputs data path + skill name
  - Triggers full pipeline: ingest → parse → chunk → embed → council
  - Shows progress bar with 5 stages
  - Displays generated `SKILLS.md` in expander
- **Interaction Mode:**
  - Dropdown to select skill hat
  - Chat interface with message history (`st.session_state.messages`)
  - Shows source citations in expander
- **Styling:** Dark gradient theme with custom CSS

#### `components.py` — Reusable Widgets

- `skill_badge(skill_name)` — Gradient badge showing active skill
- `discovery_panel()` — Sidebar panel for ingestion
- `interaction_panel(available_skills)` — Skill dropdown
- `chat_message_block(role, content)` — Styled message
- `app_header()` — Gradient title
- `status_indicator(api_keys)` — Shows which APIs are configured

### API Layer (`main.py`)

#### FastAPI Endpoints

- **`GET /api/health`** — Returns API key status + skill count
- **`GET /api/skills`** — Lists all available skill manifests
- **`POST /api/discover`** — Triggers full discovery pipeline (long-running)
  - Request: `{data_path, skill_name, code_extensions}`
  - Response: `DiscoveryResult`
- **`POST /api/chat`** — Skill-aware QA
  - Request: `ChatRequest(query, skill_hat, conversation_history)`
  - Response: `ChatResponse(answer, sources, metadata)`
- **Startup Event:** Logs API key status and available skills

---

## 🔄 Data Flow Examples

### Discovery Pipeline Flow

```
1. User clicks "Ingest & Generate Skill" in Streamlit
   ↓
2. GitHubConnector.fetch_files() → list[RawDocument]
   ConfluenceConnector.fetch_pages() → list[RawDocument]
   ↓
3. For each code file:
   parse_file(content, path) → list[CodeChunk]
   ↓
4. SemanticChunkerPipeline:
   chunk_code(code_chunks) → list[SemanticChunk]
   chunk_document(doc_content) → list[SemanticChunk]
   ↓
5. VectorStore.upsert_chunks(skill_name, chunks)
   → Stored in ChromaDB collection
   ↓
6. run_council(combined_text, skill_name):
   - ArchitectAgent.run() ─┐
   - DomainExpertAgent.run() ├─ asyncio.gather
   - QualityAgent.run() ─────┘
   ↓
7. SynthesizerAgent.run([arch, domain, quality])
   → Merged SKILLS.md
   ↓
8. SkillRegistry.save_skill(skill_name, content)
   → Written to src/skills/manifests/{SKILL_NAME}_SKILLS.md
```

### Chat Interaction Flow

```
1. User selects "Staking" skill hat + types query
   ↓
2. SkillRegistry.load_skill("staking")
   → Loads STAKING_SKILLS.md content
   ↓
3. VectorStore.query("staking", query, n_results=5)
   → Returns top 5 relevant chunks
   ↓
4. Build prompt:
   - System instruction with SKILLS.md injected
   - Relevant chunks as context
   - Conversation history
   - Current query
   ↓
5. google.generativeai.generate_content_async(prompt)
   → LLM generates answer
   ↓
6. Return ChatResponse(answer, sources, metadata)
   ↓
7. Streamlit displays answer + source citations
```

---

## 🛠️ Dependencies & Tech Stack

| Category          | Technology                         | Purpose                                  |
| ----------------- | ---------------------------------- | ---------------------------------------- |
| **Orchestration** | `google-adk>=1.0.0`                | Agent framework (LlmAgent, FunctionTool) |
| **LLMs**          | `google-generativeai>=0.8.0`       | Gemini models (Architect, Chat)          |
|                   | `anthropic>=0.39.0`                | Claude models (Domain, Quality)          |
| **Vector DB**     | `chromadb>=0.5.0`                  | Persistent vector storage                |
| **Parsing**       | `tree-sitter>=0.23.0`              | AST parsing library                      |
|                   | `tree-sitter-language-pack>=0.6.0` | Pre-built grammars (Java, TS)            |
| **Backend**       | `fastapi>=0.115.0`                 | REST API framework                       |
|                   | `uvicorn[standard]>=0.32.0`        | ASGI server                              |
| **Frontend**      | `streamlit>=1.40.0`                | Interactive UI                           |
| **Data**          | `pydantic>=2.0.0`                  | Data validation                          |
|                   | `python-dotenv>=1.0.0`             | Environment config                       |
| **HTTP**          | `httpx>=0.27.0`                    | Async HTTP client                        |

---

## 🚀 How to Run

```bash
# 1. Setup
cd squad-sense/squadsense
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure API keys
# Edit .env and add:
#   GOOGLE_API_KEY=your_key_here
#   ANTHROPIC_API_KEY=your_key_here

# 3. Add data (optional for MVP)
# Place Java/TS files in data/code/
# Place Markdown/HTML docs in data/docs/

# 4. Run Streamlit UI
streamlit run src/ui/app.py

# OR run FastAPI backend
uvicorn main:app --reload --port 8000
# Then visit http://localhost:8000/docs for API docs
```

---

## 🧪 Testing the System

### Test Discovery Pipeline

1. Place sample Java files in `data/code/`
2. Open Streamlit UI
3. Enter skill name: "test"
4. Click "Ingest & Generate Skill"
5. Wait for progress bar to complete
6. Check `src/skills/manifests/TEST_SKILLS.md` was created

### Test Chat Interaction

1. After discovery completes, select "test" from skill dropdown
2. Ask: "What are the main entities in this codebase?"
3. Verify response references specific classes from your code
4. Check "Sources" expander shows relevant chunks

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# List skills
curl http://localhost:8000/api/skills

# Discover (long-running)
curl -X POST http://localhost:8000/api/discover \
  -H "Content-Type: application/json" \
  -d '{"data_path": "data", "skill_name": "api_test"}'

# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the architecture", "skill_hat": "api_test"}'
```

---

## 🔍 Troubleshooting

### Common Issues

**"No module named 'google.adk'"**

- Solution: `pip install google-adk`

**"Tree-sitter parser not found"**

- Solution: `pip install tree-sitter-language-pack` (not `tree-sitter-languages`)

**"ChromaDB collection error"**

- Solution: Delete `chromadb_store/` and restart

**"API key not found"**

- Solution: Check `.env` file has `GOOGLE_API_KEY` and `ANTHROPIC_API_KEY`

**"Discovery fails with context window error"**

- Solution: Reduce the number of chunks passed to council (edit line in `main.py`: `all_semantic[:50]` → `all_semantic[:20]`)

---

## 📝 Future Enhancements (Not in MVP)

- **Drift Detection:** Monitor codebase changes and auto-update SKILLS.md
- **CI/CD Integration:** GitHub Actions to run discovery on every PR
- **Multi-Skill Chat:** Allow mixing multiple skill hats in one conversation
- **Custom Embeddings:** Swap ChromaDB default for OpenAI/Cohere embeddings
- **Agent Evaluation:** Use ADK's eval framework to test council quality
- **Streaming Responses:** Stream chat answers token-by-token
- **Voice Interface:** Integrate Gemini Live API for voice chat

---

## 📚 Additional Resources

- **Google ADK Docs:** https://google.github.io/adk-docs/
- **ChromaDB Docs:** https://docs.trychroma.com/
- **Tree-sitter:** https://tree-sitter.github.io/tree-sitter/
- **Streamlit:** https://docs.streamlit.io/
- **FastAPI:** https://fastapi.tiangolo.com/

---

**Last Updated:** 2026-02-12  
**Version:** 0.1.0 (MVP Scaffold)
