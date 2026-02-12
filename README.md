# 🧠 SquadSense — Skill-Aware AI Developer Assistant

An enterprise **Agentic RAG** system that ingests codebases and documentation, uses an **LLM Council** (Architect · Domain · Quality agents) to auto-generate a **SKILLS.md** manifest, and then provides **Skill-Aware Chat** so developers can query the AI using the _specific_ patterns, rules, and entities of a chosen skill domain.

---

## Architecture Overview

<img width="8192" height="7799" alt="sqdsense-2026-02-11-121333" src="https://github.com/user-attachments/assets/cd8c9188-1159-45b1-b1f8-f04d22d80d21" />


## Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **pip** (or **uv** for faster installs)

### 2. Clone & Install

```bash
cd squad-sense/squadsense

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies (includes pre-built tree-sitter binaries)
pip install -r requirements.txt
```

> **Note:** `tree-sitter-language-pack` ships pre-built wheels — no manual binary compilation needed.

### 3. Configure Environment

```bash
cp .env .env.local
# Edit .env and add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_API_KEY=AI...
```

### 4. Prepare Data for Ingestion

Place your raw source files in the `data/` directory:

```bash
data/
├── code/          # Java/TypeScript source files
│   ├── StakingService.java
│   └── validator.ts
└── docs/          # Markdown or HTML documentation
    └── staking-guide.md
```

### 5. Run the Application

**Option A — FastAPI Backend (API mode):**

```bash
uvicorn main:app --reload --port 8000
```

**Option B — Streamlit UI (Interactive mode):**

```bash
streamlit run src/ui/app.py
```

**Option C — ADK Dev UI:**

```bash
adk web
```

---

## API Endpoints

| Method | Endpoint        | Description                               |
| ------ | --------------- | ----------------------------------------- |
| POST   | `/api/discover` | Ingest data + run LLM Council → SKILLS.md |
| POST   | `/api/chat`     | Skill-aware Q&A                           |
| GET    | `/api/skills`   | List available skill manifests            |
| GET    | `/api/health`   | Health check                              |

---

## Project Structure

```
squadsense/
├── .env                        # API Keys
├── requirements.txt            # Dependencies
├── main.py                     # FastAPI entrypoint
├── data/                       # Raw docs & code for ingestion
├── chromadb_store/             # Persisted vector DB
└── src/
    ├── ingestion/
    │   ├── cast_parser.py      # Tree-sitter Java/TS extraction
    │   ├── connectors.py       # GitHub & Confluence fetchers
    │   └── chunker.py          # Semantic chunk merging
    ├── knowledge/
    │   └── vector_store.py     # ChromaDB wrapper
    ├── orchestration/
    │   ├── adk_core.py         # ADK base utilities & config
    │   ├── council_agents.py   # LLM Council (Architect/Domain/Quality)
    │   ├── chat_agent.py       # Skill-Aware QA Agent
    │   └── tools.py            # Retrieval tool functions
    ├── skills/
    │   ├── registry.py         # Skill manifest manager
    │   └── manifests/          # Generated *_SKILLS.md files
    └── ui/
        ├── app.py              # Streamlit entrypoint
        └── components.py       # Reusable UI widgets
```

---

## How It Works

### Phase 1: Discovery (LLM Council)

1. **Ingest** — Tree-sitter parses Java/TS into semantic code chunks; docs are split on headers.
2. **Embed** — Chunks are stored in ChromaDB with metadata (language, type, source).
3. **Council** — Three specialized agents analyze the codebase in parallel:
   - 🏗️ **Architect** → structural patterns, entity maps, layer boundaries
   - 📊 **Domain Expert** → business logic, formulas, validation rules
   - ✅ **Quality** → testing standards, naming conventions, tech debt
4. **Synthesize** — A synthesizer agent merges all analyses into a structured `SKILLS.md` manifest.

### Phase 2: Interaction (Skill-Aware Chat)

1. Select a **Skill Hat** (e.g., "Staking") from the UI dropdown.
2. The agent loads the corresponding `STAKING_SKILLS.md` into its system prompt.
3. User queries are augmented with relevant code/doc chunks from ChromaDB.
4. Responses follow the _specific_ patterns and rules defined in the skill manifest.

---

## License

MIT
