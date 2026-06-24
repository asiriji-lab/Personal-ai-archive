# AI COUNCIL REPORT

**Structured Debate on Improving the**  
**Personal AI Archive (Zero-Cost Virtual Brain)**

Repository: [github.com/asiriji-lab/Personal-ai-archive](https://github.com/asiriji-lab/Personal-ai-archive)  
Council Members: Innovator | Devil's Advocate | Outsider  
Date: May 4, 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Briefing: Repository Context](#2-briefing-repository-context)
   - 2.1 Core Value Proposition
   - 2.2 Key Technical Constraints
3. [Opening Statements](#3-opening-statements)
   - 3.1 The Innovator
   - 3.2 The Devil's Advocate
   - 3.3 The Outsider
4. [Cross-Examination](#4-cross-examination)
   - 4.1 Round 1: Feasibility Under Constraint
   - 4.2 Round 2: The Federation Question
   - 4.3 Round 3: Multi-Modal Reality Check
5. [Evaluated Proposals Table](#5-evaluated-proposals-table)
6. [Consensus Roadmap](#6-consensus-roadmap)
   - 6.1 Short-Term Wins (Low Effort, High Impact)
   - 6.2 Mid-Term Goals (Requires Planning)
   - 6.3 Long-Term Moonshots (High Risk, High Reward)
7. [Dissenting Opinions](#7-dissenting-opinions)
   - 7.1 Devil's Advocate: Federation Should Be Removed from the Roadmap Entirely
   - 7.2 Outsider: Onboarding Should Be the Single Highest Priority
   - 7.3 Innovator: Graph Reasoning Is Underestimated

---

## 1. Executive Summary

The AI Council convened to evaluate improvement proposals for the Personal AI Archive (Zero-Cost Virtual Brain), a locally-run, privacy-first knowledge management system built on LightRAG and MCP. The repository's defining constraints—running entirely on 6GB VRAM consumer hardware with zero cloud dependency for core functionality—framed every discussion. The Council debated ten major proposals across three rounds of cross-examination, weighing technical ambition against the project's core philosophy of accessibility and privacy.

The Innovator pushed for agentic multi-step workflows, graph-augmented retrieval with cross-document reasoning, multi-modal ingestion pipelines, and federated knowledge sharing. The Devil's Advocate systematically challenged each proposal on the grounds of VRAM feasibility, security surface expansion, maintenance burden for a small-team project, and the risk of scope creep that could undermine the "zero-cost" and "100% local" value propositions. The Outsider consistently redirected the debate toward real-world usability: onboarding friction, documentation gaps, and the needs of developers who lack ML expertise but want a personal knowledge brain.

The Council reached consensus on a tiered roadmap. Short-term wins focus on low-effort, high-impact improvements: enhanced documentation with a Quick Start guide, Docker-based setup for zero-friction installation, and incremental test coverage. Mid-term goals include a lightweight agentic planning layer that respects the 6GB VRAM ceiling, a plugin architecture for the MCP bridge, and a web-based configuration dashboard. Long-term moonshots—multi-modal ingestion and federated knowledge exchange—were acknowledged as visionary but deferred pending community validation and hardware evolution. The Devil's Advocate's dissent on federated sharing was formally recorded, as was the Outsider's strong minority position that onboarding simplification should be the single highest priority.

---

## 2. Briefing: Repository Context

Before the debate commenced, the Chairman delivered a briefing to ensure all Council members shared a common understanding of the repository's purpose, architecture, and technical constraints.

### 2.1 Core Value Proposition

The Personal AI Archive (branded as "Zero-Cost Virtual Brain") is a local-first, privacy-preserving AI memory system that bridges daily active thinking (via an Obsidian vault) with deep historical knowledge (archived documents). It automatically constructs and queries a dense Knowledge Graph using LightRAG, enabling thematic, semantic, and relational searches across years of personal archives. The system's killer feature is that it runs entirely on constrained consumer hardware—specifically a 6GB VRAM NVIDIA RTX 4050—without requiring any cloud APIs for core functionality. It also features native Model Context Protocol (MCP) integration, allowing AI agents like Claude or Cursor to read, write, and search the personal knowledge base autonomously.

### 2.2 Key Technical Constraints

| Constraint       | Details                                                                                     |
|------------------|---------------------------------------------------------------------------------------------|
| VRAM Budget      | 6GB (RTX 4050). Must run qwen3.5:4b + nomic-embed-text simultaneously.                     |
| Local-First      | 100% local and private. No cloud APIs for core functionality. Ollama-only inference.        |
| LLM Engine       | LightRAG for Knowledge Graph construction and hybrid (semantic + graph) retrieval.          |
| Agent Interface  | MCP bridge via FastMCP with annotated tools (readOnlyHint, destructiveHint, idempotentHint). |
| Two-Tier Memory  | Tier 1: Active Memory (sqlite-vec for vault search). Tier 2: Long-Term Memory (LightRAG KG for archives). |
| Validation Gate  | Best-effort claim extraction and validation pipeline between generation and indexing.       |
| Language         | Python 3.10+. Minimal web components (brain_explorer.py uses a web-based graph viewer).     |
| Scalability      | Designed for 8GB+ VRAM upgrade path (qwen2.5:7b, larger context window).                   |

---

## 3. Opening Statements

Each Council member presented their initial analysis and top proposals. The statements reflect their distinct perspectives: the Innovator seeks to push the system's capabilities forward, the Devil's Advocate identifies structural weaknesses and risks, and the Outsider evaluates from the standpoint of a prospective user encountering the project for the first time.

### 3.1 The Innovator

The Personal AI Archive is sitting on a goldmine of structured personal knowledge, but it's currently a passive system—it waits for queries instead of proactively surfacing insights. My first proposal is to implement **Agentic Multi-Step Workflows**. Instead of single-shot MCP tool calls, we should give the Brain the ability to plan, execute, and reflect across multiple retrieval steps. Imagine an agent that can: (1) search the archive for a topic, (2) identify gaps in the knowledge graph, (3) cross-reference with the active vault, and (4) synthesize a summary with explicit citations. This transforms the Brain from a retrieval engine into a research assistant. The key is that this can be done within the 6GB VRAM constraint by using the existing qwen3.5:4b model with structured prompts and a lightweight planner module—no additional model loading required.

My second proposal is **Graph-Augmented Retrieval with Cross-Document Reasoning**. LightRAG already extracts entities and relationships, but the current query interface is essentially "search and return." We should add a reasoning layer that traverses the knowledge graph to find non-obvious connections between documents. For example, if the user asks about "trends in AI safety," the system shouldn't just return documents mentioning "AI safety"—it should trace citation chains, identify evolving themes across time-stamped documents, and surface contradictory viewpoints. This is essentially a GraphRAG-style approach, but leveraging the existing LightRAG infrastructure rather than replacing it.

My third proposal is **Multi-Modal Ingestion**. The current system is text-only, but personal archives are increasingly multi-modal: screenshots, diagrams, voice memos, and PDFs with embedded images. We should add a pre-processing pipeline that uses lightweight vision models (like moondream2 at 1.7GB) to generate text descriptions of images, and Whisper-tiny for audio transcription. Both models can fit within the VRAM budget when swapped in temporarily during ingestion (not during real-time serving). This dramatically expands the Brain's knowledge capture surface without violating the local-first principle.

My fourth and most ambitious proposal is **Federated Knowledge Exchange**. Right now, each Brain is an isolated island. But imagine if trusted users could selectively share subgraphs of their knowledge base—for example, sharing your "AI research" subgraph with a colleague while keeping your "personal journal" subgraph private. This would use differential privacy and zero-knowledge proofs to ensure that shared subgraphs reveal only intentional information. It's technically complex but would transform the project from a personal tool into a networked knowledge ecosystem.

### 3.2 The Devil's Advocate

Let me be direct: every one of the Innovator's proposals carries significant risk that could undermine the project's core value proposition. Starting with **Agentic Workflows**—the moment you introduce multi-step autonomous planning, you introduce unpredictability. An agent running in a loop on a 6GB VRAM machine will compete with the embedding model for memory, and the qwen3.5:4b model is already a budget model for reasoning. Structured prompts are not a substitute for actual planning capability. I've seen too many "lightweight planner modules" that are just brittle prompt chains which break silently on edge cases. The real cost is not VRAM—it's the user's trust. If the agent hallucinates a citation or misattributes a source in a multi-step workflow, the validation harness (which is already "best-effort") won't catch it because it was designed for single-document claims, not synthesized multi-hop reasoning.

On **Graph-Augmented Retrieval**, I'll note that LightRAG's knowledge graph is already noisy—the repository itself includes a `prune_graph.py` utility, which tells you everything you need to know about entity extraction quality. Adding a reasoning layer on top of a noisy graph doesn't produce insight; it produces confident-sounding nonsense. The "citation chain traversal" the Innovator describes requires a level of entity disambiguation and relation typing that LightRAG simply does not provide out of the box. You'd need to build an entire NLP pipeline for coreference resolution and temporal ordering before any of this works reliably.

**Multi-Modal Ingestion** sounds reasonable until you do the math. Swapping models in and out of VRAM means cold starts on every model load. Whisper-tiny is fast but inaccurate; Whisper-base is better but takes 1GB of VRAM. Moondream2 at 1.7GB plus the base model plus the embedding model exceeds 6GB during the overlap. The practical effect is that ingestion becomes a stop-start process where the user has to wait for model swapping, defeating the "incremental indexing" feature that's currently a strength. Also, the generated text descriptions of images are inherently lossy—you're indexing a summary of an image, not the image itself, which limits retrieval quality.

**Federated Knowledge Exchange** is, frankly, a security nightmare. The project's entire identity is "100% local and private." The moment you open a network port for federation, you've created an attack surface. Differential privacy and zero-knowledge proofs are academically elegant but notoriously difficult to implement correctly in practice. A single implementation flaw could leak personal data. More pragmatically, this feature requires a critical mass of users to be useful—network effects don't work with a dozen early adopters. It's a moonshot that would consume development resources better spent on core reliability.

### 3.3 The Outsider

I'm going to approach this from a completely different angle. I tried to set up this project this morning, and it took me 45 minutes and three failed attempts before I had it running. The README is technically complete but assumes a lot—it assumes you know what Ollama is, it assumes you know what MCP is, it assumes you're comfortable editing `.env` files, and it assumes your Python environment won't conflict with the dependencies. My first and strongest proposal is **Onboarding Simplification**. This project needs: (1) a Docker Compose setup that bundles Ollama, the Python environment, and a pre-configured vault, (2) a "Quick Start" guide that gets a new user from zero to their first query in under 10 minutes, and (3) a health-check script that validates the environment before the user encounters cryptic errors. None of this is glamorous, but it's the difference between a project that gets 50 stars and a project that gets 5,000.

My second proposal is **Documentation Expansion with User-Focused Guides**. The current docs are architecture-focused: they explain what the system is, not how to use it effectively. There's no guide on "How to Organize Your Vault for Best Results," no examples of good vs. bad queries, no troubleshooting section for common issues (Ollama not running, model not pulled, VRAM exceeded). The Sprint Log and Dev Log are great for contributors, but there's nothing for the end user who just wants to search their notes. I'd propose a separate "User Guide" section with real-world walkthroughs.

My third proposal is **MCP Tool Usability**. The current MCP tools are functional but bare-bones. The `archive_search` tool returns raw results; there's no ranking explanation, no highlighting of matched passages, and no way to refine or follow up on a query. For the `save_active_note` tool, there's no way to specify tags, categories, or relationships to existing notes. These tools need to be designed from the agent's perspective: what does Claude or Cursor actually need to be useful? I'd propose adding structured metadata to tool responses and implementing a conversation-context-aware query refinement mechanism.

My fourth proposal is **Community Infrastructure**. This project has zero community tooling: no Discord, no GitHub Discussions, no CONTRIBUTING.md with clear guidelines, no issue templates, no roadmap. For a project that wants to be "your personal AI brain," it needs to build trust and a user base. A clear contribution guide, labeled issues for newcomers, and a communication channel would cost almost nothing to set up and would dramatically increase the project's reach and sustainability.

---

## 4. Cross-Examination

The cross-examination phase ran for three rounds, with each round deepening the analysis of key proposals. The Chairman moderated, asking clarifying questions to drive the debate toward actionable conclusions.

### 4.1 Round 1: Feasibility Under Constraint

**Devil's Advocate (challenging Innovator):** You claim agentic workflows can run within the 6GB VRAM budget, but qwen3.5:4b with an 8192-token context window is already resource-constrained for single-step reasoning. When you add multi-step planning with intermediate state, you're effectively asking a budget model to maintain a working memory across steps. What evidence do you have that this won't degrade output quality to the point of unusability?

**Innovator (response):** The key insight is that we don't need the planner to be a general-purpose reasoner. We can implement a constrained planning framework where the agent selects from a fixed library of "search strategies"—sequential search, contrastive search, temporal search, etc.—rather than free-form planning. This reduces the reasoning burden to a classification task, which qwen3.5:4b can handle reliably. The intermediate state can be stored in the existing sqlite-vec database rather than in the LLM's context window, keeping the VRAM footprint stable.

**Chairman (clarifying question):** Are you proposing a new abstraction layer—a 'strategy selector' that sits between the agent and the MCP tools? If so, how does this differ from simply exposing more specific MCP tools (e.g., `archive_temporal_search`, `archive_contrastive_search`)?

**Innovator:** Good question. The difference is composability. Individual tools are atomic; a strategy selector can chain them. For example, a 'compare and contrast' strategy might first call `archive_temporal_search` for two time periods, then call a synthesis step. The user doesn't need to know the chain—they just ask the question, and the planner decomposes it. This is closer to how LangChain works but without the overhead, since the strategies are pre-defined Python functions, not dynamically generated prompts.

**Outsider (weighing in):** I hear the technical argument, but I'm concerned about the user experience. If the agent silently chains five search calls, the user has no visibility into what's happening or why. I'd argue that any agentic workflow needs a 'transparent reasoning' feature—show the user each step the agent takes, with intermediate results they can inspect and override. This is both a UX feature and a safety feature.

### 4.2 Round 2: The Federation Question

**Innovator (defending federation):** I want to push back on the security framing. Federation doesn't require opening arbitrary network ports. We can use a pub/sub model where users export signed subgraph snapshots to a shared repository (like a Git remote). There's no live connection—it's asynchronous and user-initiated. Think of it as 'knowledge Git' rather than 'knowledge API.' The differential privacy layer sanitizes the exported subgraph before it leaves the machine.

**Devil's Advocate:** 'Knowledge Git' is an appealing metaphor, but the analogy breaks down quickly. Code is deterministic—you can diff it, test it, and verify it. Knowledge graphs are probabilistic and contextual. A subgraph that makes sense in your personal context may be deeply misleading in someone else's. How do you prevent 'knowledge contamination' where a noisy or biased subgraph from user A degrades the quality of user B's knowledge base? And the signing infrastructure you describe requires a PKI layer that this project has zero experience maintaining.

**Outsider:** Let me add a user perspective. I can barely get this project running on my machine, and you're talking about federated knowledge exchange with differential privacy and zero-knowledge proofs? This is a classic case of building the spaceship before paving the runway. Who is federation for? Power users who already have working Brains? How many of those exist today? I'd estimate fewer than 50 based on the repository's activity. The effort-to-impact ratio for federation is terrible at the project's current stage.

**Chairman (clarifying question):** Could there be a lighter version of federation—perhaps just the ability to export and import curated subgraph snapshots as files, with no network component? This would allow manual sharing without the security surface.

**Innovator:** That's actually reasonable as a stepping stone. An 'export subgraph' and 'import subgraph' MCP tool pair would let users share knowledge manually while we figure out the trust and privacy model. It's also useful for backup and migration scenarios even without federation.

**Devil's Advocate:** I can accept that as a minimal-viable-sharing feature, provided the import tool runs the imported data through the existing validation harness before indexing. Unvalidated imports would be a direct path to knowledge graph pollution.

### 4.3 Round 3: Multi-Modal Reality Check

**Innovator (refining multi-modal proposal):** Let me address the VRAM math more carefully. During ingestion, we don't need the reasoning model loaded—only the embedding model and the ingestion-specific model. The pipeline would be: (1) unload qwen3.5:4b, (2) load vision or audio model, (3) process files, (4) unload, (5) reload qwen3.5:4b. This is a batch operation, not a real-time one. Users can run it overnight or during scheduled maintenance. The nomic-embed-text model is only 274MB, leaving over 5GB for the vision/audio model during ingestion.

**Devil's Advocate:** The model-swapping approach works in theory but creates a fragile operational dependency. What if Ollama's model unloading doesn't fully release VRAM (a known issue with certain Ollama versions)? What about the cold-start latency for reloading qwen3.5:4b (roughly 15-30 seconds)? If a user has the MCP server running and triggers ingestion, the server becomes unresponsive during the swap. You'd need to implement a queuing system that pauses MCP requests during ingestion and resumes after—that's a significant engineering effort for a feature that processes images into lossy text descriptions.

**Outsider:** I think the real question is: what percentage of a typical user's archive is non-text? For developers using Obsidian, the answer is probably 5-10% at most—mostly code screenshots and the occasional diagram. Is the engineering investment justified for that use case? I'd argue that a simpler approach is to let users manually describe their images in markdown alt text, which Obsidian already supports, and have the Brain index that. It's lower-tech but respects the project's resource constraints and the user's time.

**Innovator:** The manual approach works for power users but defeats the 'automatic' promise of the Brain. What if we start with PDF extraction only? Many users archive PDFs with embedded images and tables. A lightweight PDF parser (like PyMuPDF) can extract text, tables, and image metadata without any AI model at all. This addresses the most common multi-modal use case with zero VRAM impact.

**Devil's Advocate:** That's the first proposal from you that I can't poke holes in. PyMuPDF is mature, well-tested, and doesn't need a GPU. PDF extraction is a genuine user need, the implementation is straightforward, and the risk is minimal. I'd support this as a mid-term goal.

---

## 5. Evaluated Proposals Table

The following table summarizes all proposals evaluated by the Council, along with their assessed feasibility, impact, and key risks. The assessments reflect the Council's consensus after three rounds of cross-examination.

| Proposal                               | Source                       | Feasibility | Impact | Key Risks                                                                 |
|----------------------------------------|------------------------------|-------------|--------|---------------------------------------------------------------------------|
| Agentic Multi-Step Workflows           | Innovator                    | Medium      | High   | Model reasoning limitations on 4B; brittle prompt chains; trust erosion from hallucinated multi-hop citations |
| Graph-Augmented Cross-Document Reasoning | Innovator                  | Low         | High   | Noisy KG entities; requires NLP pipeline for coreference/temporal ordering not present in LightRAG |
| Multi-Modal Ingestion (Vision/Audio)   | Innovator                    | Medium      | Medium | VRAM swapping fragility; cold-start latency; lossy image-to-text descriptions; Ollama VRAM release issues |
| Federated Knowledge Exchange           | Innovator                    | Low         | Medium | Security surface expansion; PKI complexity; knowledge contamination risk; insufficient user base for network effects |
| Subgraph Export/Import (lightweight federation) | Innovator + Devil's Advocate | High        | Medium | Imported data must pass validation harness; minimal security surface |
| PDF Table & Image Extraction (PyMuPDF) | Innovator + Devil's Advocate | High        | Medium | No GPU needed; mature library; addresses most common multi-modal use case |
| Onboarding Simplification (Docker + Quick Start) | Outsider                  | High        | High   | Ongoing maintenance of Docker images; potential dependency version conflicts |
| Documentation Expansion (User Guides)  | Outsider                     | High        | High   | Documentation rot if not kept in sync with code changes |
| MCP Tool Usability Enhancements        | Outsider                     | High        | Medium | Backward compatibility with existing MCP integrations must be maintained |
| Community Infrastructure (Discord, CONTRIBUTING.md) | Outsider             | High        | Medium | Requires ongoing moderation effort; low initial engagement risk |

---

## 6. Consensus Roadmap

The following roadmap represents the Council's consensus on prioritization, organized by time horizon. Each tier was debated and adjusted based on cross-examination outcomes, with particular attention to the VRAM constraint, the project's privacy-first identity, and the Outsider's emphasis on user accessibility.

### 6.1 Short-Term Wins (Low Effort, High Impact)

- **Docker Compose Setup:** Create a `docker-compose.yml` that bundles Ollama, the Python environment, and a pre-configured test vault. This eliminates the single biggest barrier to adoption—environment setup. Estimated effort: 2-3 days. The Docker image should include a health-check endpoint that verifies all components are running and models are loaded.
- **Quick Start Guide:** Write a step-by-step "5-Minute Quick Start" guide in the README that walks a new user from clone to first query. This should be above the fold, before the architecture details. Include copy-paste commands, expected output examples, and a "troubleshooting" sidebar for common issues (Ollama not running, model not pulled, Python version mismatch).
- **Environment Validation Script:** Create a `setup_brain.py` script that checks Python version, Ollama availability, model presence, VRAM capacity, and `.env` configuration before the user attempts to run the system. This should output a clear pass/fail report with actionable fix instructions for each failure. This alone would eliminate the majority of "doesn't work" issues.
- **CONTRIBUTING.md and Issue Templates:** Add a CONTRIBUTING.md with clear guidelines for code contributions, documentation updates, and bug reports. Create GitHub issue templates for bug reports, feature requests, and questions. This costs almost nothing and signals project maturity.
- **Incremental Test Coverage:** Add integration tests for the core pipeline (indexing, querying, MCP tools) to the existing CI workflow. The repository already has `.github/workflows/ci.yml`; expand it with realistic end-to-end tests that run against a test vault. This prevents regressions as features are added.

### 6.2 Mid-Term Goals (Requires Planning)

- **Constrained Agentic Planning Layer:** Implement a "strategy selector" that allows the MCP bridge to decompose complex queries into chains of existing tool calls. This is not a free-form planner but a library of pre-defined search strategies (sequential, contrastive, temporal, exploratory) that the LLM selects between. The intermediate state is stored in sqlite-vec, not in the LLM context, keeping VRAM stable. A "transparent reasoning" feature shows the user each step the agent takes. Estimated effort: 4-6 weeks for a prototype.
- **MCP Tool Enhancements:** Enrich MCP tool responses with structured metadata: relevance scores, matched passage highlighting, source attribution, and query refinement suggestions. Add an optional 'explain' parameter to `archive_search` that returns the reasoning behind the ranking. Add metadata parameters (tags, categories, relationships) to `save_active_note`. Maintain backward compatibility with existing MCP integrations.
- **PDF Table and Image Extraction:** Integrate PyMuPDF (`fitz`) into the ingestion pipeline to extract text, tables, and image metadata from PDF files without any AI model. This addresses the most common multi-modal use case (archived PDFs) with zero VRAM impact and minimal engineering risk. Extracted tables should be converted to markdown for consistent indexing. Estimated effort: 1-2 weeks.
- **Subgraph Export/Import Tools:** Add `export_subgraph` and `import_subgraph` MCP tools that allow users to export curated portions of their knowledge graph as portable JSON files and import subgraphs from other sources. Imported data must pass through the existing validation harness before indexing. This enables manual knowledge sharing, backup, and migration without network security concerns. Estimated effort: 2-3 weeks.
- **Web-Based Configuration Dashboard:** Replace the current `.env`-based configuration with a lightweight web dashboard (built with Gradio or Streamlit for minimal dependency overhead) that allows users to configure models, paths, and settings through a browser interface. This dramatically reduces the technical barrier for non-developer users while maintaining the local-first principle. Estimated effort: 3-4 weeks.

### 6.3 Long-Term Moonshots (High Risk, High Reward)

- **Graph-Augmented Cross-Document Reasoning:** Build a reasoning layer on top of LightRAG that traverses the knowledge graph to find non-obvious connections between documents, traces citation chains, and identifies evolving themes across time. This requires solving the entity disambiguation and temporal ordering problems first, which are significant research challenges. Prerequisite: a comprehensive evaluation of LightRAG's entity extraction quality and a plan for noise reduction. Target: 6-12 months, contingent on community interest and contributor availability.
- **Multi-Modal Ingestion with Vision and Audio Models:** Extend the ingestion pipeline to process images (using lightweight vision models like moondream2) and audio (using Whisper) in addition to text and PDFs. This requires a robust model-swapping infrastructure that pauses MCP serving during ingestion, manages VRAM carefully, and handles Ollama's known VRAM release issues. Target: 9-15 months, contingent on Ollama improvements and user demand validation.
- **Federated Knowledge Exchange:** Enable trusted users to selectively share subgraph snapshots of their knowledge base using a "knowledge Git" model with differential privacy sanitization. This requires solving the knowledge contamination, trust, and PKI challenges identified during cross-examination. The Council recommends deferring this until the project has an active community of at least 500 users and a dedicated security reviewer. Target: 12-24 months, contingent on community scale and security audit capacity.

---

## 7. Dissenting Opinions

The following dissenting opinions were formally recorded during the Council session. These represent strong minority viewpoints that were not adopted by the consensus but which the Council deemed important enough to preserve for future reconsideration.

### 7.1 Devil's Advocate: Federation Should Be Removed from the Roadmap Entirely

The Devil's Advocate formally dissented from the inclusion of Federated Knowledge Exchange in the long-term roadmap, even as a moonshot. The argument is that the mere presence of federation on the roadmap creates expectations that will influence architectural decisions in the mid-term (e.g., adding subgraph versioning, export signing, or trust metrics) that add complexity without delivering value until the moonshot is realized—if it ever is. The Devil's Advocate's position is that the subgraph export/import feature in the mid-term roadmap is sufficient for the project's sharing needs, and that federation should only be reconsidered if and when the project reaches a scale (1,000+ active users) where network effects genuinely matter. Until then, it's a distraction that could compromise the "100% local and private" brand identity.

### 7.2 Outsider: Onboarding Should Be the Single Highest Priority

The Outsider formally dissented from the roadmap's allocation of onboarding improvements to the "short-term wins" tier, arguing that they should be elevated to the single highest priority for the project, superseding even core feature development. The argument is based on a simple observation: the project's current adoption rate suggests that the majority of interested users fail at the setup stage. Every hour spent on Docker setup, Quick Start guides, and validation scripts generates more value than ten hours spent on agentic workflows or graph reasoning, because those features only matter for users who can actually run the system. The Outsider proposes a "90-Day Onboarding Sprint" where all other feature work is paused until the new-user success rate (measured by the number of users who complete the Quick Start guide and make their first query) reaches 90%.

### 7.3 Innovator: Graph Reasoning Is Underestimated

The Innovator formally dissented from the low feasibility rating assigned to Graph-Augmented Cross-Document Reasoning, arguing that the Council underestimated the potential of LightRAG's existing entity extraction when combined with a targeted noise-reduction pass. The Innovator's position is that the existing `prune_graph.py` utility demonstrates the project already has the infrastructure for graph curation, and that a relatively small investment in entity confidence scoring and relation type filtering could elevate LightRAG's graph quality to the point where cross-document reasoning becomes viable. The Innovator proposes that a 2-week "graph quality sprint"—focused on improving entity extraction accuracy and adding relation typing—should precede any decision on the feasibility of graph reasoning, and that the current "Low" feasibility rating is premature without this empirical evaluation.