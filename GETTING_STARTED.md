# SquadSense — Getting Started Guide

## Table of Contents

1. [How to Prepare Your Data (Manual Download)](#1-how-to-prepare-your-data)
2. [How to Set Up & Run the System](#2-how-to-set-up--run)
3. [Testing: Ingestion → RAG → Skill Generation](#3-testing-the-pipeline)
4. [Understanding the UI (Streamlit)](#4-understanding-the-ui)
5. [How to Interact as a User](#5-interacting-as-a-user)
6. [How to Interact as a Developer](#6-interacting-as-a-developer)
7. [Understanding What Happens Behind the Scenes](#7-behind-the-scenes)

---

## 1. How to Prepare Your Data

Since we're skipping the live GitHub/Confluence APIs for now, you'll manually download files and place them in the `data/` folder.

### Step 1A: Download Your Code

Go to your GitHub repo (e.g., your Java/TypeScript project) and either:

- **Clone it:** `git clone https://github.com/your-org/your-repo.git` somewhere temporary
- **Download ZIP:** Click "Code" → "Download ZIP" on GitHub

Then **copy only the source files** you care about into `data/code/`:

```
squadsense/
└── data/
    └── code/
        ├── StakingService.java          ← copy these in
        ├── StakingValidator.java
        ├── StakingController.java
        ├── models/
        │   ├── StakePosition.java
        │   └── RewardCalculation.java
        └── utils/
            └── CryptoUtils.ts
```

**What to include:**

- ✅ Service classes, Controllers, Models, Utils — the core business logic
- ✅ TypeScript files (`.ts`, `.tsx`)
- ✅ Java files (`.java`)
- ❌ Don't bother with `node_modules/`, `build/`, `.class` files, config XMLs

**Tip:** Focus on ONE domain at a time. If you want to generate a "Staking" skill, only put staking-related code in. You can always run discovery again for different domains.

### Step 1B: Download Your Docs

Go to Confluence and export the relevant pages:

- Click the page → "..." menu → "Export to Word/PDF" or just **copy-paste the content into a `.md` file**
- Or if you have Markdown docs in your repo, just copy those

Place them in `data/docs/`:

```
squadsense/
└── data/
    └── docs/
        ├── staking-overview.md          ← your Confluence/wiki content
        ├── staking-business-rules.md
        ├── api-design-guide.md
        └── architecture-decisions.md
```

**What to include:**

- ✅ Business rules documentation
- ✅ Architecture decision records (ADRs)
- ✅ API specifications
- ✅ Developer guides, onboarding docs
- ❌ Meeting notes, sprint plans, HR docs (irrelevant)

### Your Final Data Folder Should Look Like:

```
squadsense/
└── data/
    ├── code/                    ← Your Java/TS source files
    │   ├── StakingService.java
    │   ├── StakingValidator.java
    │   └── ...
    └── docs/                    ← Your Markdown/HTML docs
        ├── staking-overview.md
        ├── business-rules.md
        └── ...
```

---

## 2. How to Set Up & Run

### Step 1: Create Virtual Environment & Install

```bash
cd /Users/aeres/Desktop/projects/squad-sense/squadsense

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Add Your API Keys

Edit the `.env` file:

```bash
# REQUIRED — at minimum you need the Google key for Gemini
GOOGLE_API_KEY=your_google_api_key_here

# OPTIONAL — needed only if you want Claude for Domain/Quality agents
ANTHROPIC_API_KEY=your_anthropic_key_here

# LEAVE BLANK — we're using local data, not live APIs
GITHUB_TOKEN=
CONFLUENCE_URL=
CONFLUENCE_TOKEN=
```

**Where to get keys:**

- **Google API Key:** https://aistudio.google.com/apikey → Create API Key
- **Anthropic API Key:** https://console.anthropic.com/settings/keys → Create Key

**For MVP testing with just Google/Gemini:** You only need `GOOGLE_API_KEY`. The system defaults to Gemini models.

### Step 3: Place Your Data

Follow Section 1 above — put files in `data/code/` and `data/docs/`.

### Step 4: Choose How to Run

You have **two options** (they do the same thing, just different interfaces):

| Option | Command                                 | Interface             | Best For                      |
| ------ | --------------------------------------- | --------------------- | ----------------------------- |
| **A**  | `streamlit run src/ui/app.py`           | Web UI with buttons   | Visual testing, demos         |
| **B**  | `uvicorn main:app --reload --port 8000` | REST API with Swagger | Developer testing, automation |

---

## 3. Testing the Pipeline

### Option A: Test via Streamlit UI (Recommended for First Time)

```bash
cd /Users/aeres/Desktop/projects/squad-sense/squadsense
source .venv/bin/activate
streamlit run src/ui/app.py
```

This opens a browser at `http://localhost:8501`. Then:

1. **Look at the left sidebar** → You'll see "Discovery Mode"
2. **Data folder path:** Leave as `data` (it reads from `data/code/` and `data/docs/`)
3. **Skill name:** Type `staking` (or whatever your domain is)
4. **Click "⚡ Ingest & Generate Skill"**
5. **Watch the progress bar** — it goes through 5 stages:
   - 📂 Ingesting files...
   - 🌳 Parsing code with Tree-sitter...
   - 📦 Creating semantic chunks...
   - 💾 Storing in vector database...
   - 🤖 Running LLM Council...
6. **When done:** You'll see "🎉 Generated STAKING_SKILLS.md successfully!"
7. **Click** the "📋 View Generated SKILLS.md" expander to see the output
8. **Now in the sidebar**, the dropdown under "Interaction Mode" will show "🎯 STAKING"
9. **Select it** and start chatting!

### Option B: Test via API (Developer Style)

```bash
cd /Users/aeres/Desktop/projects/squad-sense/squadsense
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000/docs** (Swagger UI) or use curl:

```bash
# 1. Check everything is working
curl http://localhost:8000/api/health

# Expected response:
# {"status":"ok","api_keys":{"google":true,"anthropic":false,...},"skills_count":0}

# 2. Run Discovery (this takes 30-60 seconds depending on data size)
curl -X POST http://localhost:8000/api/discover \
  -H "Content-Type: application/json" \
  -d '{
    "data_path": "data",
    "skill_name": "staking"
  }'

# Expected response: JSON with skills_md_content, agent_responses, chunks_ingested

# 3. Check the skill was created
curl http://localhost:8000/api/skills

# Expected response:
# {"skills":["staking"],"count":1}

# 4. Chat with the skill
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main staking entities and how do they relate?",
    "skill_hat": "staking"
  }'

# Expected response: JSON with a detailed answer about your staking code
```

### What to Verify After Running Discovery

1. **Check the generated file exists:**

   ```bash
   cat src/skills/manifests/STAKING_SKILLS.md
   ```

   This should contain a structured Markdown document with Architecture Patterns, Business Logic, Quality Deviations, etc.

2. **Check ChromaDB has data:**

   ```bash
   ls chromadb_store/
   ```

   You should see database files here.

3. **Test a chat query** (via either UI or API) and verify:
   - The response references actual classes/methods from YOUR code
   - The response mentions patterns from the SKILLS.md
   - Sources are cited (you can see them in the UI's "📚 Sources" expander)

---

## 4. Understanding the UI

The Streamlit UI has **two main areas**:

```
┌──────────────────────┬─────────────────────────────────────────────┐
│                      │                                             │
│   SIDEBAR (Left)     │          MAIN AREA (Center)                 │
│                      │                                             │
│  ┌────────────────┐  │  ┌─────────────────────────────────────┐   │
│  │ 🔍 Discovery   │  │  │                                     │   │
│  │    Mode         │  │  │  Welcome screen (before skill       │   │
│  │                 │  │  │  selection)                          │   │
│  │  [Data path]    │  │  │         — OR —                      │   │
│  │  [Skill name]   │  │  │  Chat interface (after skill        │   │
│  │  [Generate ⚡]   │  │  │  selection)                         │   │
│  │                 │  │  │                                     │   │
│  ├────────────────┤  │  │  ┌────────────────────────────────┐ │   │
│  │ 💬 Interaction  │  │  │  │ 🎯 STAKING Mode Active         │ │   │
│  │    Mode         │  │  │  │                                │ │   │
│  │                 │  │  │  │ User: How does staking work?   │ │   │
│  │  [Skill ▼]      │  │  │  │                                │ │   │
│  │  🎯 STAKING     │  │  │  │ Assistant: Based on the       │ │   │
│  │                 │  │  │  │ StakingService class...        │ │   │
│  ├────────────────┤  │  │  │                                │ │   │
│  │ ⚙️ Status       │  │  │  │ 📚 Sources ▶                  │ │   │
│  │ ✅ Google API   │  │  │  └────────────────────────────────┘ │   │
│  │ ❌ Anthropic    │  │  │                                     │   │
│  │ ❌ GitHub       │  │  │  [Type your message here...]        │   │
│  └────────────────┘  │  └─────────────────────────────────────┘   │
│                      │                                             │
└──────────────────────┴─────────────────────────────────────────────┘
```

### Sidebar Sections:

| Section                 | Purpose                                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **🔍 Discovery Mode**   | This is where you trigger ingestion + skill generation. You enter the data folder path and a skill name, then click the button. |
| **💬 Interaction Mode** | After at least one skill is generated, a dropdown appears here. Select which "Skill Hat" you want to chat with.                 |
| **⚙️ Status**           | Shows green/red indicators for which API keys you've configured. Quick way to verify your `.env` is set up.                     |

### Main Area:

| State                 | What You See                                                              |
| --------------------- | ------------------------------------------------------------------------- |
| **No skill selected** | A welcome screen saying "Start by running Discovery Mode"                 |
| **Skill selected**    | A gradient badge showing "🎯 STAKING Mode Active" + a full chat interface |
| **During discovery**  | A progress bar + info messages showing each pipeline stage                |

---

## 5. Interacting as a User

As a **user** (developer who wants to learn about a codebase), your workflow is:

### First Time (Discovery):

```
1. Open Streamlit UI
2. In sidebar → Discovery Mode:
   - Data path: "data"     (where you put your files)
   - Skill name: "staking" (the domain you're exploring)
3. Click "⚡ Ingest & Generate Skill"
4. Wait ~60 seconds for the LLM Council to analyze everything
5. Done! You now have a "Staking" skill hat.
```

### Every Time After (Chat):

```
1. Open Streamlit UI
2. In sidebar → Interaction Mode → Select "🎯 STAKING"
3. The chat area shows "🎯 STAKING Mode Active"
4. Type your question in the chat box at the bottom
5. The AI responds using YOUR codebase's patterns and rules
6. Click "📚 Sources" to see which code/doc chunks were used
```

### Example Questions to Ask:

Once you have a skill loaded, try these kinds of questions:

| Question Type      | Example                                                               |
| ------------------ | --------------------------------------------------------------------- |
| **Architecture**   | "What design patterns does the staking module use?"                   |
| **Implementation** | "How should I implement a new staking reward calculator?"             |
| **Business Logic** | "What validation rules apply when creating a new stake?"              |
| **Code Quality**   | "What are the naming conventions for staking-related classes?"        |
| **Specific Code**  | "Show me how the StakingService calculates rewards"                   |
| **Best Practice**  | "What's the correct way to handle staking errors?"                    |
| **Review**         | "I want to add a method `unstake()` — what patterns should I follow?" |

### Running Multiple Skills:

You can generate skills for different domains:

```
Discovery Run 1: skill_name = "staking"     → STAKING_SKILLS.md
Discovery Run 2: skill_name = "auth"        → AUTH_SKILLS.md
Discovery Run 3: skill_name = "payments"    → PAYMENTS_SKILLS.md
```

Then switch between them in the Interaction Mode dropdown. Each one is a different "persona" with different patterns and rules.

---

## 6. Interacting as a Developer

As a **developer** working on SquadSense itself, here's what you need to know:

### The Two Entry Points:

| Entry Point   | File            | What It Does                                                       |
| ------------- | --------------- | ------------------------------------------------------------------ |
| **Streamlit** | `src/ui/app.py` | Visual interface. Run with `streamlit run src/ui/app.py`           |
| **FastAPI**   | `main.py`       | REST API. Run with `uvicorn main:app --reload`. Swagger at `/docs` |

Both call the same backend code. They're just different frontends.

### Key Files to Modify:

| What you want to change                   | File to edit                                                                |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| Add a new data source (e.g., Jira)        | `src/ingestion/connectors.py` — add a new Connector class                   |
| Support a new language (e.g., Python, Go) | `src/ingestion/cast_parser.py` — add `extract_python_functions()`           |
| Change how chunks are sized/split         | `src/ingestion/chunker.py` — adjust `max_chars`, splitting logic            |
| Change what the council agents focus on   | `src/orchestration/council_agents.py` — edit the `*_INSTRUCTION` strings    |
| Change the chat behavior/persona          | `src/orchestration/chat_agent.py` — edit `SKILL_AWARE_INSTRUCTION_TEMPLATE` |
| Change which LLM models are used          | `.env` — change `ARCHITECT_MODEL`, `CHAT_MODEL`, etc.                       |
| Change vector search behavior             | `src/orchestration/tools.py` — edit the tool functions                      |
| Add new API endpoints                     | `main.py` — add new FastAPI routes                                          |
| Change the UI layout                      | `src/ui/app.py` and `src/ui/components.py`                                  |

### How the Code Flows (Developer View):

```
User clicks "Generate Skill"
        │
        ▼
src/ui/app.py::run_discovery()
        │
        ├── 1. src/ingestion/connectors.py
        │      GitHubConnector._fetch_from_local()  ← reads data/code/
        │      ConfluenceConnector._fetch_from_local()  ← reads data/docs/
        │
        ├── 2. src/ingestion/cast_parser.py
        │      parse_file() → extract_java_methods() or extract_typescript_functions()
        │      Returns: list[CodeChunk] with method bodies + javadoc
        │
        ├── 3. src/ingestion/chunker.py
        │      SemanticChunkerPipeline.chunk_code() + chunk_document()
        │      Returns: list[SemanticChunk] ready for embedding
        │
        ├── 4. src/knowledge/vector_store.py
        │      VectorStore.upsert_chunks("staking", chunks)
        │      → Stored in chromadb_store/ with embeddings
        │
        └── 5. src/orchestration/council_agents.py
               run_council(combined_text, "staking")
               ├── ArchitectAgent analyzes ──┐
               ├── DomainExpertAgent analyzes ├─ parallel
               ├── QualityAgent analyzes ─────┘
               └── SynthesizerAgent merges → STAKING_SKILLS.md
```

```
User asks a question in chat
        │
        ▼
src/ui/app.py::chat_interface()
        │
        ├── 1. src/skills/registry.py
        │      SkillRegistry.load_skill("staking")
        │      → Reads STAKING_SKILLS.md content
        │
        ├── 2. src/knowledge/vector_store.py
        │      VectorStore.query("staking", query, n_results=5)
        │      → Returns top 5 relevant code/doc chunks
        │
        └── 3. src/orchestration/chat_agent.py
               answer(ChatRequest)
               → Builds prompt: SKILLS.md + relevant chunks + query
               → Calls Gemini API
               → Returns ChatResponse with answer + sources
```

### Debugging Tips:

```bash
# See what files the connectors are finding:
python3 -c "
from src.ingestion.connectors import GitHubConnector
c = GitHubConnector(local_dir='data/code')
import asyncio
docs = asyncio.run(c.fetch_files())
for d in docs:
    print(f'{d.file_type}: {d.source}')
"

# See what Tree-sitter extracts from a file:
python3 -c "
from src.ingestion.cast_parser import extract_java_methods
with open('data/code/StakingService.java') as f:
    chunks = extract_java_methods(f.read(), 'StakingService.java')
for c in chunks:
    print(f'{c.name} (lines {c.start_line}-{c.end_line}): {len(c.body)} chars')
"

# See what skills exist:
python3 -c "
from src.skills.registry import SkillRegistry
r = SkillRegistry()
print('Skills:', r.list_skills())
"

# Query the vector store directly:
python3 -c "
from src.knowledge.vector_store import VectorStore
vs = VectorStore()
results = vs.query('staking', 'reward calculation', n_results=3)
for r in results:
    print(f'Score: {r.score:.2f} | {r.id}')
    print(r.content[:200])
    print('---')
"
```

---

## 7. Behind the Scenes

### What Actually Happens When You Click "Generate Skill"

Let's say you put 10 Java files and 3 Markdown docs in `data/`:

| Step              | What Happens                                                                                                                                                                                                                   | Time           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| **1. Ingest**     | Reads all `.java` files from `data/code/` and all `.md` files from `data/docs/` into memory                                                                                                                                    | ~1 second      |
| **2. Parse**      | Tree-sitter parses each Java file's AST, extracts method bodies + Javadoc. Skips getters/setters. Maybe extracts 50 methods from 10 files.                                                                                     | ~2 seconds     |
| **3. Chunk**      | Groups small methods together into larger semantic chunks (~2048 chars each). Splits docs on headers. Maybe produces 30 chunks total.                                                                                          | ~1 second      |
| **4. Embed**      | ChromaDB takes each chunk, runs it through Sentence Transformer (all-MiniLM-L6-v2) to create a vector embedding, stores it locally.                                                                                            | ~5 seconds     |
| **5. Council**    | The top 50 chunks are concatenated into a big text block. Three LLM agents analyze it **in parallel**: Architect looks at structure, Domain Expert looks at business logic, Quality Agent compares against industry standards. | ~30-45 seconds |
| **6. Synthesize** | A fourth agent takes the three analyses and merges them into one clean SKILLS.md with sections for patterns, rules, deviations, and guidelines.                                                                                | ~15-20 seconds |
| **7. Save**       | The final Markdown is written to `src/skills/manifests/STAKING_SKILLS.md`.                                                                                                                                                     | instant        |

**Total: ~1-2 minutes** depending on data size and LLM response time.

### What Actually Happens When You Ask a Question

| Step                | What Happens                                                                                                                    | Time          |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| **1. Load Skill**   | Reads `STAKING_SKILLS.md` from disk. This becomes part of the AI's "personality".                                               | instant       |
| **2. Search**       | Your question is embedded and compared against all chunks in the "staking" collection. Top 5 most relevant chunks are returned. | ~1 second     |
| **3. Build Prompt** | The system builds a prompt: Skill manifest + relevant code chunks + your conversation history + your question.                  | instant       |
| **4. Generate**     | Gemini receives the full prompt and generates a response.                                                                       | ~5-10 seconds |
| **5. Display**      | The answer appears in the chat, with source citations available in the "📚 Sources" expander.                                   | instant       |

### Key Insight: Why This Is Better Than ChatGPT

Regular ChatGPT doesn't know YOUR codebase. SquadSense:

1. **Knows your patterns** — "In this codebase, we use the Repository pattern with..."
2. **Knows your rules** — "Staking amounts must be validated using the `StakingValidator.validate()` method..."
3. **Knows your anti-patterns** — "⚠️ The current error handling in `StakingController` swallows exceptions — use specific catch blocks instead."
4. **Stays within your domain** — When you ask about "staking", it uses YOUR staking code, not generic blockchain knowledge.

---

## Quick Reference Card

```
┌──────────────────────────────────────────────────────────┐
│                    SQUADSENSE QUICK REF                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  SETUP:                                                  │
│    1. Put code in data/code/                             │
│    2. Put docs in data/docs/                             │
│    3. Set GOOGLE_API_KEY in .env                         │
│    4. pip install -r requirements.txt                    │
│                                                          │
│  RUN UI:     streamlit run src/ui/app.py                 │
│  RUN API:    uvicorn main:app --reload --port 8000       │
│                                                          │
│  DISCOVER:   Sidebar → Skill name → Generate ⚡          │
│  CHAT:       Sidebar → Select skill → Type question      │
│                                                          │
│  OUTPUT:     src/skills/manifests/{NAME}_SKILLS.md       │
│  VECTORS:    chromadb_store/                             │
│  API DOCS:   http://localhost:8000/docs                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```
