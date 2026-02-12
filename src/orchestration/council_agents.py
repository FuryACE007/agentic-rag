"""
council_agents.py — The LLM Council for the Discovery Phase.

Uses Google ADK's ``Agent`` (LlmAgent) to create four specialized agents:
  1. ArchitectAgent   — structural patterns, entity maps, layer boundaries
  2. DomainExpertAgent — business logic, formulas, validation rules
  3. QualityAgent      — testing standards, naming conventions, tech debt
  4. SynthesizerAgent  — merges all three into a structured SKILLS.md

The ``run_council`` function orchestrates the full pipeline.
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.adk.agents import Agent
from google.genai import types as genai_types

from src.orchestration.adk_core import (
    AgentResponse,
    AgentRole,
    DiscoveryResult,
    PipelineConfig,
    get_pipeline_config,
)
from src.orchestration.tools import retrieve_relevant_chunks
from src.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

ARCHITECT_INSTRUCTION = """You are the **Architect Agent** in an LLM Council analyzing a software codebase.

Your focus areas:
- **Structural Patterns**: Identify design patterns (MVC, Repository, Service, Factory, etc.)
- **Entity Relationships**: Map out key entities and how they relate (dependencies, inheritance, composition)
- **Layer Boundaries**: Identify architectural layers (Controller → Service → Repository → Model)
- **Module Organization**: How the codebase is structured into packages/modules
- **API Surface**: Public interfaces, endpoints, contracts

Analyze the provided code chunks and produce a structured Markdown report covering these areas.
Be specific — cite class names, method names, and package paths where relevant.
Format your output as clean Markdown with headers, bullet points, and code references."""

DOMAIN_EXPERT_INSTRUCTION = """You are the **Domain Expert Agent** in an LLM Council analyzing a software codebase.

Your focus areas:
- **Business Logic**: Core algorithms, calculations, and decision flows
- **Formulas & Computations**: Mathematical formulas, financial calculations, scoring algorithms
- **Validation Rules**: Input validation, business constraints, invariants
- **Domain Entities**: Key business objects and their lifecycle (states, transitions)
- **Business Terminology**: Domain-specific vocabulary and its mapping to code constructs

Analyze the provided code chunks and produce a structured Markdown report covering these areas.
Be specific — cite method names, variable names, and exact logic flows.
Format your output as clean Markdown with headers, bullet points, and code references."""

QUALITY_INSTRUCTION = """You are the **Quality Agent** in an LLM Council analyzing a software codebase.

Your PRIMARY RESPONSIBILITY is to compare the codebase against **industry best practices and standards**,
then flag deviations with severity levels and recommendations. This prevents the system from learning
bad patterns even if they exist in the current codebase.

## Your Analysis Framework:

### 1. Industry Standards Baseline
For each area, compare against established industry standards:
- **Testing**: JUnit/Jest best practices, AAA pattern, test pyramid, coverage thresholds (>80%)
- **Naming**: Language-specific conventions (Java: camelCase methods, PascalCase classes; TypeScript: same)
- **Error Handling**: Fail-fast, specific exceptions, proper logging, no swallowed exceptions
- **Security**: OWASP Top 10, input validation, SQL injection prevention, XSS protection
- **Architecture**: SOLID principles, DRY, separation of concerns, dependency injection
- **Documentation**: Javadoc/JSDoc completeness, README presence, API documentation
- **Code Style**: Language style guides (Google Java Style, Airbnb TypeScript)

### 2. Deviation Detection & Flagging
For EACH deviation from industry standards, report:

```markdown
### ⚠️ [SEVERITY] Deviation: [Brief Title]

**Industry Standard:**
[What the gold standard practice is]

**Current Implementation:**
[What the codebase actually does, with code references]

**Impact:**
- Risk Level: [CRITICAL | HIGH | MEDIUM | LOW]
- Consequences: [What could go wrong]

**Recommendation:**
[Specific fix or improvement]

**Acceptable Deviation?**
[YES/NO + Justification]
- If YES: Explain valid reasons (performance, domain constraints, legacy compatibility)
- If NO: Mark as MUST FIX
```

### 3. Severity Levels
- 🔴 **CRITICAL**: Security vulnerabilities, data loss risks, production-breaking issues
- 🟠 **HIGH**: Major tech debt, maintainability issues, performance problems
- 🟡 **MEDIUM**: Code smells, minor anti-patterns, documentation gaps
- 🟢 **LOW**: Style inconsistencies, minor improvements

### 4. Positive Patterns
Also highlight where the codebase EXCEEDS or MATCHES industry standards:
```markdown
### ✅ Excellent: [Pattern Name]
[What they're doing right and why it's good]
```

## Your Output Structure:

```markdown
# Quality Analysis Report

## Executive Summary
- Total Deviations Found: [count by severity]
- Critical Issues Requiring Immediate Attention: [count]
- Patterns Exceeding Standards: [count]

## Industry Standards Comparison

### Testing Standards
[Analysis with deviations flagged]

### Naming Conventions
[Analysis with deviations flagged]

### Error Handling & Resilience
[Analysis with deviations flagged]

### Security Practices
[Analysis with deviations flagged]

### Architecture & Design
[Analysis with deviations flagged]

### Documentation Quality
[Analysis with deviations flagged]

### Code Style & Maintainability
[Analysis with deviations flagged]

## Positive Patterns (What They're Doing Right)
[List of practices that meet or exceed standards]

## Tech Debt Inventory
- TODO/FIXME markers: [count + examples]
- Deprecated usage: [list]
- Code smells: [list with locations]

## Prioritized Action Items
1. [CRITICAL] [Issue] → [Fix]
2. [HIGH] [Issue] → [Fix]
...
```

## Critical Rules:
1. **Be Objective**: Base all judgments on established industry standards (OWASP, SOLID, language style guides)
2. **Be Specific**: Always cite code examples and line references
3. **Be Constructive**: Provide actionable fixes, not just criticism
4. **Be Balanced**: Acknowledge good patterns alongside issues
5. **Be Contextual**: Consider if deviations might be justified (explain why/why not)

Your goal is to ensure the SKILLS.md teaches CORRECT patterns, not just the patterns present in this codebase."""

SYNTHESIZER_INSTRUCTION = """You are the **Synthesizer Agent**. Your job is to merge the analyses from three
specialist agents (Architect, Domain Expert, Quality) into a single, cohesive **SKILLS.md** manifest.

The SKILLS.md must follow this exact structure:

```markdown
# {SKILL_NAME} — Skill Manifest

## Overview
Brief description of this skill domain.

## Architecture Patterns
(From Architect analysis)
- Pattern descriptions with code references

## Entity Map
(From Architect analysis)
- Entity relationships and class hierarchy

## Business Logic & Rules
(From Domain Expert analysis)
- Core algorithms and formulas
- Validation rules and constraints

## Domain Vocabulary
(From Domain Expert analysis)
- Term → Code mapping table

## Code Standards & Quality Baseline
(From Quality analysis - INDUSTRY STANDARDS)
- Naming conventions (industry standard)
- Testing patterns (industry standard)
- Error handling patterns (industry standard)
- Security practices (industry standard)

## ⚠️ Quality Deviations & Corrections
(From Quality analysis - CRITICAL SECTION)

This section lists where the CURRENT codebase deviates from industry standards.
**IMPORTANT**: When writing new code, follow the INDUSTRY STANDARD, not the current implementation.

### Critical Deviations (MUST FIX)
- [List 🔴 CRITICAL and 🟠 HIGH severity issues]
- For each: Current pattern → Industry standard → Why it matters

### Acceptable Deviations (Context-Specific)
- [List deviations that are justified for this domain]
- For each: Why the deviation is acceptable in this context

### Positive Patterns
- [List ✅ patterns where codebase meets/exceeds standards]

## Implementation Guidelines
Synthesized guidelines combining all three analyses:

### DO (Follow These Patterns):
- [Industry-standard patterns, even if not currently in codebase]
- [Good patterns found in current codebase]
- [Specific code examples of CORRECT implementations]

### DON'T (Anti-Patterns to Avoid):
- [Patterns from Quality deviations marked as MUST FIX]
- [Security vulnerabilities found]
- [Performance anti-patterns]
- [Specific code examples of INCORRECT implementations with corrections]

### MIGRATION PATH (For Existing Code):
- [How to refactor current deviations to industry standards]
- [Prioritized list: Critical → High → Medium → Low]

## Code Examples

### ✅ Recommended Pattern
```[language]
// Industry-standard implementation
[example following best practices]
```

### ❌ Anti-Pattern (Found in Codebase - Do Not Replicate)
```[language]
// Current implementation with issues
[example of deviation]
```

### ✅ Corrected Version
```[language]
// How it should be written
[corrected example]
```
```

CRITICAL INSTRUCTIONS:
1. **Preserve Quality Deviations**: Do NOT hide or normalize bad patterns. Explicitly flag them.
2. **Teach Industry Standards**: The SKILLS.md should teach CORRECT patterns, not just document current patterns.
3. **Provide Migration Paths**: Show how to fix deviations, not just identify them.
4. **Balance Context**: Acknowledge when deviations are justified (performance, domain constraints).
5. **Be Specific**: Include actual code examples of both wrong and right patterns.
6. **Prioritize Safety**: Security and data integrity issues must be flagged as CRITICAL.

Your goal: Create a SKILLS.md that prevents future developers from replicating bad patterns,
even if those patterns exist in the current codebase."""


# ---------------------------------------------------------------------------
# Agent Factory
# ---------------------------------------------------------------------------

def _create_council_agent(
    name: str,
    instruction: str,
    model: str,
    description: str,
) -> Agent:
    """Create a Google ADK Agent for the council."""
    return Agent(
        name=name,
        model=model,
        instruction=instruction,
        description=description,
        tools=[retrieve_relevant_chunks],
    )


def create_architect_agent(config: PipelineConfig) -> Agent:
    """Create the Architect analysis agent."""
    return _create_council_agent(
        name="architect_agent",
        instruction=ARCHITECT_INSTRUCTION,
        model=config.architect_model,
        description="Analyzes structural patterns, entity relationships, and layer boundaries.",
    )


def create_domain_expert_agent(config: PipelineConfig) -> Agent:
    """Create the Domain Expert analysis agent."""
    return _create_council_agent(
        name="domain_expert_agent",
        instruction=DOMAIN_EXPERT_INSTRUCTION,
        model=config.domain_model,
        description="Analyzes business logic, formulas, and validation rules.",
    )


def create_quality_agent(config: PipelineConfig) -> Agent:
    """Create the Quality analysis agent."""
    return _create_council_agent(
        name="quality_agent",
        instruction=QUALITY_INSTRUCTION,
        model=config.quality_model,
        description="Analyzes testing standards, naming conventions, and tech debt.",
    )


def create_synthesizer_agent(config: PipelineConfig) -> Agent:
    """Create the Synthesizer agent that merges all analyses."""
    return Agent(
        name="synthesizer_agent",
        model=config.architect_model,  # Use Gemini for large context merge
        instruction=SYNTHESIZER_INSTRUCTION,
        description="Merges Architect, Domain, and Quality analyses into SKILLS.md.",
    )


# ---------------------------------------------------------------------------
# Council Pipeline
# ---------------------------------------------------------------------------

async def _run_single_agent(
    agent: Agent,
    role: AgentRole,
    input_text: str,
) -> AgentResponse:
    """
    Run a single council agent and return its response.

    Note: In a production setting, this would use ADK's Runner/Session.
    For the MVP, we invoke the agent via google.genai for direct generation.
    """
    try:
        import google.generativeai as genai

        model = genai.GenerativeModel(agent.model)
        full_prompt = f"{agent.instruction}\n\n---\n\nCodebase chunks to analyze:\n\n{input_text}"

        response = await model.generate_content_async(
            full_prompt,
            generation_config=genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=4096,
            ),
        )
        content = response.text or ""

        return AgentResponse(
            agent_name=agent.name,
            role=role,
            content=content,
            success=True,
        )
    except Exception as e:
        return AgentResponse(
            agent_name=agent.name,
            role=role,
            content="",
            success=False,
            error=str(e),
        )


async def run_council(
    code_chunks_text: str,
    skill_name: str,
    config: PipelineConfig | None = None,
) -> DiscoveryResult:
    """
    Run the full LLM Council pipeline:
      1. Run Architect, Domain, Quality agents in parallel
      2. Merge their outputs via the Synthesizer agent
      3. Save the resulting SKILLS.md

    Args:
        code_chunks_text: Concatenated text of all code/doc chunks.
        skill_name:       Name for the generated skill (e.g. "staking").
        config:           Optional pipeline configuration.

    Returns:
        DiscoveryResult with the generated SKILLS.md content.
    """
    if config is None:
        config = get_pipeline_config()

    # --- Step 1: Create council agents ---
    architect = create_architect_agent(config)
    domain_expert = create_domain_expert_agent(config)
    quality = create_quality_agent(config)
    synthesizer = create_synthesizer_agent(config)

    # --- Step 2: Run analysis agents in parallel ---
    architect_task = _run_single_agent(architect, AgentRole.ARCHITECT, code_chunks_text)
    domain_task = _run_single_agent(domain_expert, AgentRole.DOMAIN_EXPERT, code_chunks_text)
    quality_task = _run_single_agent(quality, AgentRole.QUALITY, code_chunks_text)

    responses = await asyncio.gather(architect_task, domain_task, quality_task)

    # --- Step 3: Synthesize into SKILLS.md ---
    synthesis_input = f"""# Analysis Results for {skill_name.upper()}

## Architect Agent Analysis:
{responses[0].content}

---

## Domain Expert Agent Analysis:
{responses[1].content}

---

## Quality Agent Analysis:
{responses[2].content}

---

Please synthesize these three analyses into a single SKILLS.md manifest for the "{skill_name}" domain.
"""

    synth_response = await _run_single_agent(
        synthesizer, AgentRole.SYNTHESIZER, synthesis_input
    )
    all_responses = list(responses) + [synth_response]

    # --- Step 4: Save manifest ---
    skills_content = synth_response.content or f"# {skill_name.upper()} — Skill Manifest\n\n*Generation failed. Please retry.*"

    registry = SkillRegistry(manifests_dir=config.skills_manifest_dir)
    registry.save_skill(skill_name, skills_content)

    return DiscoveryResult(
        skill_name=skill_name,
        skills_md_content=skills_content,
        agent_responses=all_responses,
        chunks_ingested=0,  # Will be set by caller
    )
