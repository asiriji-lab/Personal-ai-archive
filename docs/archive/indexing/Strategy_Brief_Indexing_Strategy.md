===== Page 1 =====

 Rethinking the Indexing Strategy

How the Zero- Cost Virtual Brain should acquire, structure, and evolve its knowledge over time

A cross- functional council of five specialists convenes to challenge the current flat- indexing approach, debate tiered memory strategies, and propose a narrative- aligned framework where indexing decisions are driven by content purpose, freshness needs, and retrieval patterns rather than simple file- system traversal.

===== Page 2 =====

1. Executive Summary 3

2. Council Composition 3

3. Opening Statements 4

3.1 Dr. Priya Chandra (Knowledge Architect) 4

3.2 Sam Torres (Content Lifecycle Strategist) 4

3.3 Dr. Lena Kowalski (Semantic Coherence Expert) 4

3.4 Morgan (Brain Architect) 4

3.5 Raj Mehta (Information Retrieval Researcher) 5

4. Strategic Problem Analysis 5

4.1 Gap 1: Uniform Treatment of Heterogeneous Content 5

4.2 Gap 2: No Freshness or Decay Model 5

4.3 Gap 3: Single-Granularity Chunking 6

4.4 Gap 4: Decoupled Indexing from Query Patterns 6

5. Proposed Framework: Purpose-Driven Multi-Pipeline Indexing 7

5.1 Pillar 1: Content Classification at Ingestion 7

5.2 Pillar 2: Adaptive Chunking Strategy 7

5.3 Pillar 3: Freshness-Aware Storage 8

5.4 Pillar 4: Query-Driven Rebalancing 8

6. Content Type Indexing Matrix 8

7. Multi-Pipeline Architecture 9

===== Page 3 =====

7.1 Pipeline A: Deep Index (Research Papers and Validated Artifacts) 9 7.2 Pipeline B: Fast Index (News Articles and Meeting Notes) 9 7.3 Pipeline C: Summary Index (Personal Notes and References) 10

## 8. Content Promotion and Demotion 10

8.1 Promotion Rules 10 8.2 Demotion Rules 11

## 9. Implementation Roadmap 11

9.1 Phase 1: Metadata Foundation (Week 1- 2) 11 9.2 Phase 2: Multi-Chunking Strategy (Week 3- 4) 12 9.3 Phase 3: Pipeline Router (Week 5- 6) 12 9.4 Phase 4: Freshness and Lifecycle (Week 7- 8) 12

10. Risk Assessment 13

11. Role Assignment 13

12. Success Metrics 14

13. Council Consensus 14

===== Page 4 =====

1. Executive Summary

The Zero- Cost Virtual Brain currently indexes all markdown files in the Archives folder using a single, uniform strategy: hash each file, skip unchanged ones, chunk the text at 1,500 characters, embed every chunk, and extract entities via LightRAG. This approach treats every document identically regardless of its content type, purpose, freshness requirements, or retrieval pattern. While functional, this flat strategy misses opportunities to align the indexing process with the project's own narrative: a two- tier memory system where active knowledge lives in fast vector search (Tier 1) and deep historical knowledge lives in a knowledge graph (Tier 2), with a validation gate between generation and long- term storage.

This council was convened to rethink the indexing strategy from the ground up. Five specialists, each bringing a distinct perspective on knowledge management, debated how the Brain should decide what to index, when to index it, which pipeline to use, and how to maintain knowledge freshness over time. The resulting framework proposes a purpose- driven, multi- pipeline indexing architecture that replaces the current single- path approach with a system that adapts its indexing behavior based on content metadata, source provenance, and usage patterns.

## 2. Council Composition

The Chairman assembled five specialists, each chosen to represent a critical dimension of the indexing strategy problem. Unlike the previous performance- focused council, this group was selected for their expertise in knowledge architecture, content lifecycle management, semantic coherence, retrieval science, and systems integration.

| Member | Perspective |
|--------|--------------|
| Dr. Priya Chandra (Chief Knowledge Architect) | Designs how knowledge systems should be organized. Believes indexing should reflect the cognitive structure it serves, not the filesystem it reads from. Frustrated by systems that treat a grocery list the same as a research paper. |
| Sam Torres (Content Lifecycle Strategist) | Specializes in how information ages, decays, and gets refreshed. Advocates for freshness-aware indexing where staleness is a first-class concern. Frustrated by systems that index once and forget. |
| Dr. Lena Kowalski (Semantic Coherence Expert) | Studies how meaning is preserved (or lost) when text is chunked and embedded. Argues that chunk boundaries should respect semantic structure, not character counts. Frustrated by chunks that cut mid-argument. |
| Morgan (Zero-Cost Virtual Brain Architect) | Deep knowledge of the Personal-ai-archive codebase, LightRAG internals, MCP integration, and the existing toolchain. Represents the implementer's perspective. Bridges vision and code. |
| Raj Mehta (Information Retrieval Researcher) | Brings academic perspective on retrieval-augmented generation, hybrid search, and query routing. Believes indexing strategy must be backward-looking from the query, not forward-looking from the document. |

Table 1. Council members and their strategic perspectives.

===== Page 5 =====

3. Opening Statements

## 3.1 Dr. Priya Chandra (Knowledge Architect)

Priya opened by challenging the fundamental assumption that all archive content deserves the same indexing treatment. The Brain's own architecture already defines two memory tiers: Tier 1 (active memory in 3. Resources with split- vec) and Tier 2 (long- term memory in 4. Archives with LightRAG). Yet the current indexing strategy in index_archive.py treats Tier 2 as a monolith. It scans every .md file recursively, chunks them all at the same size, and feeds them all through the same entity- extraction pipeline. Priya argued that the Brain's narrative already implies a richer structure: research papers carry different knowledge than daily notes, and the validation gate (validate_and_archive.py) already distinguishes between generated artifacts and organic content. The indexing strategy should mirror these distinctions.

## 3.2 Sam Torres (Content Lifecycle Strategist)

Sam focused on the concept of knowledge decay. In the current system, once a file is indexed, it stays indexed forever unless manually deleted. The manifest in index_manifest.json tracks file hashes, so a file is only re- indexed if its content changes. But Sam pointed out that knowledge can become stale without any file modification: a 2023 technology note about Python 3.11 is less relevant after Python 3.13 ships, even if the file was never edited. The Brain has no concept of freshness scoring, decay curves, or time- weighted relevance. Sam proposed that every indexed chunk should carry metadata about when it was created, when it was last referenced by a query, and what its estimated half- life is based on its content type.

## 3.3 Dr. Lena Kowalski (Semantic Coherence Expert)

Lena zeroed in on the chunking strategy. The chunk_text() function in utils.py splits on paragraph boundaries first, then sentence boundaries, then falls back to hard character cuts at CHUNK_MAX_CHARS (default 1,500). Lena acknowledged that paragraph- first splitting is a good starting point, but argued that it does not account for deeper semantic structures like argument threads, narrative arcs, or conceptual boundaries. A research paper's methodology section and its conclusion may be in adjacent paragraphs, but they serve entirely different retrieval purposes. A chunk that straddles both will confuse entity extraction and produce muddled embeddings. Lena proposed a multi- granularity approach where the Brain stores both fine- grained chunks (for precise retrieval) and coarse- grained document summaries (for context and overview).

## 3.4 Morgan (Brain Architect)

Morgan anchored the discussion in the codebase reality. The current pipeline in index_archive.py works as follows: glob all \*.md files in 4. Archives, compare file hashes against the manifest, chunk each new/changed file, embed all chunks via Ollama (nomic- embed- text), and then call LightRAG to extract entities and relationships. Morgan highlighted several strategic levers already

===== Page 6 =====

3.5 Raj Mehta (Information Retrieval Researcher)

Raj framed the problem from the query side. The Brain currently offers two search tools via MCP: vault_search (hybrid vector \(^+\) BM25 over Tier 1) and archive_search (semantic \(^+\) graph over Tier 2 via LightRAG). Raj argued that the indexing strategy should be backward- looking from these query patterns. If most user queries are about recent meetings or active projects, then Tier 1 should be indexed with high freshness and low latency. If queries are about deep historical patterns or cross- document connections, then Tier 2 should be optimized for graph richness and entity density. The current strategy indexes both tiers with the same approach, which means neither is optimized for its actual retrieval workload. Raj proposed query- driven indexing: analyze query logs to identify which content types are most frequently retrieved, and allocate indexing resources proportionally.

## 4. Strategic Problem Analysis

The Chairman guided the council through a structured analysis of the four strategic gaps in the current indexing approach. Each gap represents a dimension where the current strategy conflicts with the Brain's own narrative about how knowledge should be organized.

### 4.1 Gap 1: Uniform Treatment of Heterogeneous Content

The Archives folder contains research papers generated by AutoResearchClaw, news articles ingested via news_ingest.py, personal notes, validated artifacts from validate_and_archive.py, and fetched papers from fetch_papers.py. Each content type has different structural characteristics: research papers have abstracts, methodologies, and references; news articles have datelines, sources, and temporal context; personal notes are informal and often fragmentary. The current indexer applies identical chunk sizes and entity extraction to all of them, which means it cannot exploit type- specific structures. Priya called this "structural blindness," and estimated that it causes \(20 - 30\%\) information loss during indexing because type- specific features (like a paper's abstract or a news article's date) are not treated as first- class metadata.

### 4.2 Gap 2: No Freshness or Decay Model

Once content is indexed, the Brain has no mechanism to assess whether that content is still current or relevant. The index_manifest.json tracks whether a file has been modified, but not whether the knowledge it represents has aged. Sam described this as a "write- only knowledge model": the Brain accumulates knowledge indefinitely but never re- evaluates it. In practice, this means that outdated

===== Page 7 =====

information can persist in the knowledge graph indefinitely, potentially degrading retrieval quality over time. For example, a 2022 note about "current best practices in LLM fine- tuning" would carry equal weight in graph traversal as a 2025 validated research paper on the same topic. Without a freshness signal, the Brain cannot prioritize recent, validated knowledge over stale, unvalidated claims.

### 4.3 Gap 3: Single-Granularity Chunking

The current chunking approach produces chunks of approximately 1,500 characters, all at the same granularity level. This is adequate for simple keyword retrieval but insufficient for the kind of multi- level reasoning that the Brain's knowledge graph is designed to support. Lena explained that retrieval tasks operate at different zoom levels: sometimes a user needs a specific fact ("what was the accuracy of model X on benchmark Y?"), and sometimes they need thematic context ("what are the main themes across all papers about prompt engineering?"). A single granularity cannot serve both well. Fine- grained chunks are good for factoid queries but lose thematic coherence; coarse- grained chunks preserve context but are too noisy for precise retrieval. The Brain needs both levels, and it needs to route queries to the appropriate level automatically.

### 4.4 Gap 4: Decoupled Indexing from Query Patterns

Raj emphasized that the current indexing strategy is entirely document- driven: it processes whatever files exist in the archive, regardless of whether that content is ever queried. The Brain's MCP tools expose archive_search and vault_search, but there is no feedback loop from query patterns to indexing decisions. Raj described this as "indexing in the dark." A content- driven strategy means that high- value content (frequently queried, highly connected in the graph) receives the same indexing investment as low- value content (never queried, orphaned in the graph). Raj proposed that the Brain should maintain query access logs and use them to compute a "knowledge value score" for each indexed chunk, which then informs re- indexing priority and decay rate.

| Rank | Strategic Gap | Description | Impact |
|------|---------------|-------------|--------|
| #1 | Uniform Treatment | All content types indexed identically; type-specific structure ignored | 20-30% information loss |
| #2 | No Freshness Model | Indexed knowledge never decays or gets re-evaluated | Stale knowledge degrades retrieval |
| #3 | Single-Granularity | One chunk size serves all retrieval zoom levels | Poor multi-level reasoning |
| #4 | Query Decoupled | Indexing ignores what users actually search for | Equal investment in all content |

Table 2. Four strategic gaps in the current indexing approach.

===== Page 8 =====

5. Proposed Framework: Purpose-Driven Multi-Pipeline Indexing

After extensive debate, the council converged on a unified framework called Purpose- Driven Multi- Pipeline Indexing (PDMPI). The core idea is that the Brain should route each piece of content through an indexing pipeline that matches its purpose, not through a single universal pipeline. The framework has four pillars: Content Classification, Adaptive Chunking, Freshness- Aware Storage, and Query- Driven Rebalancing.

### 5.1 Pillar 1: Content Classification at Ingestion

Priya (Architect): Every file entering the Brain should be classified into a content type at the moment of ingestion. The existing validate_and_archive.py pipeline already adds metadata to artifacts before they reach the archive. We should extend this pattern to all content sources. A simple classifier, even rule- based, that tags each file with its type (research paper, news article, personal note, validated artifact, meeting note) gives the downstream indexer the information it needs to choose the right pipeline. This tag lives in a YAML frontmatter block at the top of each file, so it is human- readable and Git- friendly.

Priya proposed a frontmatter schema that every indexed file should carry. The schema includes fields for content type, source, creation date, validation status, and freshness priority. Morgan confirmed that this is feasible because validate_and_archive.py already writes enriched metadata to archived files. Extending this to all ingestion paths (news_ingest.py, fetch_papers.py, manual drops) is a matter of adding a classification step at the entry point. The classifier can start as a simple rule- based system (match filename patterns, detect abstract sections, check for news datelines) and evolve into a lightweight LLM classifier over time.

### 5.2 Pillar 2: Adaptive Chunking Strategy

Lena (Semantic Expert): Instead of one chunk size for all content, the Brain should apply different chunking strategies based on content type and purpose. Research papers should be chunked by section (abstract, introduction, methodology, results, conclusion), preserving the internal structure. News articles should be chunked by paragraph with dateline metadata attached to each chunk. Personal notes should use smaller, overlapping chunks to capture the informal, non- sequential nature of the content.

Lena and Morgan co- designed a chunking strategy matrix. The key insight is that chunk_text() in utils.py should accept a strategy parameter that selects the appropriate splitting behavior. For structured documents (research papers, validated artifacts), the splitter should detect Markdown headings (H2, H3) and use them as natural chunk boundaries, producing variable- length chunks that respect semantic structure. For unstructured content (personal notes, meeting notes), the existing paragraph- first approach is appropriate but should use smaller chunks (800- 1,000 characters) with a 200- character overlap to preserve context across boundaries. For all content types, the Brain should

===== Page 9 =====

1

### 5.3 Pillar 3: Freshness-Aware Storage

Sam (Lifecycle Strategist): Every chunk should carry three temporal metadata fields: indexed_at (when it was first indexed), last_accessed (when it was last returned in a query result), and half_life_days (an estimated freshness window based on content type). News articles might have a half- life of 30 days; research papers, 365 days; personal notes, 180 days. At query time, the retrieval scorer can down- weight chunks whose age exceeds their half- life, ensuring that fresh knowledge ranks higher without deleting old knowledge entirely.

Sam proposed that the freshness metadata be stored alongside each chunk in the LightRAG storage layer, accessible via a lightweight metadata query. The watch_archive.py service would be extended to periodically scan for "decay candidates," which are chunks whose age has exceeded twice their half- life without being accessed. These candidates are flagged for review rather than automatically deleted, preserving the user's ability to decide whether stale knowledge should be retained. Morgan confirmed that LightRAG's storage layer supports custom metadata on chunks, making this implementable without modifying the core LightRAG library. The existing scripts/prune_graph.py utility would be extended to support freshness- aware pruning in addition to its current structural pruning (orphans, dates, symbols).

### 5.4 Pillar 4: Query-Driven Rebalancing

Raj (IR Researcher): The Brain should maintain a query access log that records every search query, the chunks returned, and whether the user followed up. Over time, this log reveals which content areas are "hot" (frequently queried) and which are "cold" (never queried). Hot content should be re- indexed more frequently and given higher embedding precision. Cold content can be indexed less frequently and stored in compressed formats that save space.

Raj proposed a "knowledge heat map" that the Brain maintains continuously. Each indexed chunk gets an access frequency score, computed as a decaying sum of query hits over time. Chunks with high access scores are candidates for enhanced indexing: re- embedding with higher precision, extracting additional entities, and ensuring their graph connections are up- to- date. Chunks with low access scores are candidates for reduced indexing: coarser chunks, fewer entity extractions, and eventual archival to a cold storage layer. Morgan noted that the MCP server (brain_server.py) already exposes archive_search and vault_search tools, so adding query logging is a small instrumentation change. The heat map data would be stored in a lightweight SQLite table alongside the existing .lightrag working directory.

## 6. Content Type Indexing Matrix

The council produced a detailed matrix that maps each content type in the Brain to its recommended indexing strategy. This matrix is the practical output of the PDMPI framework and serves as the

===== Page 10 =====

implementation specification for Morgan.

| Content Type | Chunking | Chunk Size | Half-Life | Entity Extraction |
|--------------|----------|------------|-----------|-------------------|
| Research Paper (AutoResearchClaw) | Section-based (H2/H3) | 1500-2500 per section | 365 days | Full entity + relationship mapping |
| Fetched Paper (fetch_papers.py) | Section-based (H2/H3) | 1500-2500 per section | 365 days | Full entity + citation linking |
| News Article (news_ingest.py) | Paragraph with dateline prefix | 800-1200 per paragraph | 30 days | Named entities + event detection |
| Validated Artifact (validate_and_archive.py) | Section with claim tags | 1500-2000 per section | 180 days | Claim entities + verdict tracking |
| Personal Note (3. Resources) | Small overlapping chunks | 600-1000, 200 overlap | 90 days | Light entity extraction (no relations) |
| Meeting Note | Topic-segmented chunks | 800-1200 per topic | 60 days | Action items + participant linking |

Table 3. Content type indexing matrix.

## 7. Multi-Pipeline Architecture

The PDMPI framework replaces the current single pipeline with three specialized pipelines, each optimized for a different indexing purpose. A lightweight router inspects the content type metadata and directs the file to the appropriate pipeline.

## 7.1 Pipeline A: Deep Index (Research Papers and Validated Artifacts)

Pipeline A is the current LightRAG entity- extraction pipeline, enhanced with section- aware chunking. It processes research papers and validated artifacts, which require the richest graph representation. The pipeline operates as follows: detect Markdown heading structure, split on section boundaries, generate a document- level summary chunk, embed all chunks (fine and coarse), extract entities and relationships via the LLM, and write to the LightRAG knowledge graph. This pipeline uses the Gemini provider for parallel LLM calls (as recommended by the previous performance council) and produces the highest- quality graph nodes. Pipeline A is the most expensive in terms of LLM calls and should be reserved for content that justifies the investment.

## 7.2 Pipeline B: Fast Index (News Articles and Meeting Notes)

===== Page 11 =====

1

Pipeline B is a lightweight pipeline optimized for high- volume, short- half- life content. It skips the full entity- relationship extraction and instead performs only named entity extraction (people, organizations, locations, dates). Chunks are embedded for vector search but are not added to the knowledge graph. This means Pipeline B content is retrievable via vault_search (hybrid vector + BM25) but not via archive_search (graph traversal). When news articles or meeting notes age past their half- life, they can be either promoted to Pipeline A (if they proved valuable based on query frequency) or archived to cold storage (if they were never queried). Morgan confirmed that this can be implemented by adding a conditional branch in index_archive.py that checks the content type frontmatter and skips LightRAG insertion for Pipeline B content.

### 7.3 Pipeline C: Summary Index (Personal Notes and References)

Pipeline C is the lightest pipeline, designed for personal notes and reference material that benefit from searchability but do not require graph integration. It generates small overlapping chunks, embeds them for vector search, and extracts only the most salient entities (skipping relationship mining entirely). The chunks are stored in Tier 1 (sqlite- vec) rather than Tier 2 (LightRAG). This pipeline is extremely fast because it avoids LLM- based entity extraction entirely, relying on embedding similarity and BM25 for retrieval. Morgan noted that 3. Resources already uses sqlite- vec for vault_search, so Pipeline C content would be stored in the same tier and retrievable through the existing MCP tool interface.

| Pipeline | Content Types | Chunking | Entity Level | Storage | Cost |
|----------|---------------|----------|--------------|---------|------|
| A: Deep Index | Research papers, validated artifacts | Section-based | Full entity + relationship | LightRAG graph (Tier 2) | High (LLM per chunk) |
| B: Fast Index | News articles, meeting notes | Paragraph-based | Named entities only | sqlite-vec (Tier 1) | Medium (embedding) |
| C: Summary Index | Personal notes, references | Small overlapping | Salient entities only | sqlite-vec (Tier 1) | Low (embedding) |

Table 4. Three-pipeline architecture comparison.

## 8. Content Promotion and Demotion

A key innovation of the PDMPI framework is that content is not permanently assigned to a single pipeline. Instead, content can be promoted (moved to a richer pipeline) or demoted (moved to a lighter pipeline) based on its observed usage and age. This creates a dynamic, self- optimizing knowledge system that invests indexing resources where they generate the most retrieval value.

### 8.1 Promotion Rules

===== Page 12 =====

1

Content is promoted when it demonstrates high retrieval value. Specifically, a chunk initially indexed via Pipeline B (Fast Index) will be promoted to Pipeline A (Deep Index) if it meets two criteria: its access frequency score exceeds a threshold (for example, returned in query results more than 5 times in 30 days), and its age has not exceeded its half- life (it is still considered fresh). This ensures that content which proves valuable through actual usage receives the richer graph representation it deserves. Promotion involves re- chunking the original file with section- aware boundaries, running full entity extraction, and writing the results to the LightRAG graph. The original Pipeline B chunks are retained in sqlite- vec for fast vector retrieval, creating a dual- representation where the same content is accessible through both graph traversal and vector search.

## 8.2Demotion Rules

8.2 Demotion Rules
Content is demoted when it loses retrieval value over time. A chunk indexed via Pipeline A (Deep Index) is demoted to Pipeline B (Fast Index) when its age exceeds twice its half- life and its access frequency drops below a minimum threshold. Demotion removes the chunk from the LightRAG graph (freeing graph traversal resources) but retains it in sqlite- vec for vector search. If a demoted chunk is later queried and found relevant, it can be re- promoted. Content in Pipeline B that exceeds three times its half- life without any queries is demoted further to cold storage, meaning its embeddings are compressed and it is excluded from standard search results but remains accessible via an explicit archive search. This three- tier lifecycle (Deep, Fast, Cold) ensures that the Brain's active knowledge base stays lean and relevant while preserving the full archive for deep historical queries.

| State | Trigger | Storage | Typical Content |
|-------|---------|---------|------------------|
| Deep Index (Pipeline A) | High access + fresh | Full graph + vector | Research papers, hot content |
| Fast Index (Pipeline B) | Moderate access + aging | Vector only | News, notes, warm content |
| Cold Storage | No access + expired | Compressed, search-only | Archived historical content |

Table 5. Content lifecycle states and transitions.

## 9. Implementation Roadmap

9. Implementation Roadmap
The council defined a phased implementation plan that builds incrementally, with each phase delivering standalone value before the next phase begins. Morgan will lead all implementation, with the other members providing domain-specific guidance and validation.

### 9.1 Phase 1: Metadata Foundation (Week 1-2)

===== Page 13 =====

1 establishes the metadata infrastructure that all subsequent phases depend on. This includes adding YAML frontmatter to all ingestion scripts (validate_and_archive.py, news_ingest.py, fetch_papers.py), implementing a content type classifier (initially rule- based), and extending the manifest in index_manifest.json to store content type, half- life, and last- accessed metadata alongside the existing file hash. This phase requires no changes to the LightRAG pipeline itself; it only adds metadata at the ingestion layer. The classifier can start with simple heuristics: files from autoresearchlaw/artifacts/ are "research paper," files with datelines in the first three lines are "news article," files under 500 characters are "personal note," and everything else defaults to "general."

### 9.2 Phase 2: Multi-Chunking Strategy (Week 3-4)

Phase 2 implements the adaptive chunking logic in utils.py. The chunk_text() function gains a strategy parameter that accepts values like "section", "paragraph", "overlap", and "summary". Each strategy implements the chunking behavior described in the Content Type Matrix (Table 3). The document- level summary chunk is a new addition: for every file processed, the pipeline generates a single chunk that is a compressed summary of the entire document (generated by the LLM or by extracting the first paragraph and all headings). This summary chunk is always stored, regardless of pipeline, providing a consistent coarse- grained retrieval entry point for every document.

### 9.3 Phase 3: Pipeline Router (Week 5-6)

Phase 3 implements the pipeline routing logic in index_archive.py. Before processing each file, the indexer reads the YAML frontmatter, determines the content type, and selects the appropriate pipeline (A, B, or C). Pipeline A follows the existing LightRAG path. Pipeline B embeds chunks into sqlite- vec without LightRAG entity extraction. Pipeline C creates overlapping small chunks and stores them in sqlite- vec only. The router is implemented as a simple switch statement that maps content types to pipeline functions. Morgan estimates this requires approximately 150- 200 lines of new code and modifications to approximately 50 lines of existing code.

### 9.4 Phase 4: Freshness and Lifecycle (Week 7-8)

Phase 4 implements the freshness tracking and promotion/demotion system. This includes adding query logging to brain_server.py (a few lines in the archive_search and vault_search tool handlers), computing access frequency scores on a daily basis, and running a "lifecycle review" script that identifies chunks eligible for promotion or demotion. The lifecycle review is a new script (scripts/lifecycle_review.py) that reads the query access log, computes each chunk's freshness score, and generates a list of recommended promotions and demotions for human review. The user can accept or reject each recommendation via the existing review_queue MCP tool.

| Phase | Name | Time | Deliverables | Files Affected |
|-------|------|------|--------------|----------------|
| Phase 1 | Metadata Foundation | Week 1-2 | Content type classifier, YAML frontmatter, extended manifest | Ingestion layer only |

===== Page 14 =====

| Phase 2 | Multi-Chunking | Week 3-4 | Adaptive chunk_text() with strategy parameter, summary chunks | utils.py |
| Phase 3 | Pipeline Router | Week 5-6 | Three-pipeline routing based on content type | index_archive.py |
| Phase 4 | Freshness and Lifecycle | Week 7-8 | Query logging, access scores, lifecycle_review.py | brain_server.py + new script |

Table 6. Implementation roadmap summary.

## 10. Risk Assessment

The council identified four primary risks associated with the PDMPI framework and proposed mitigations for each.

| Risk | Description | Severity | Mitigation |
|------|-------------|----------|-------------|
| Classification Accuracy | Rule-based classifier may misclassify content types | Medium | Start conservative; add LLM fallback in Phase 2; allow manual override via frontmatter |
| Backward Compatibility | Existing indexed content has no frontmatter; changes could break retrieval | High | Migration script retroactively classifies existing files; "general" default routes to Pipeline A |
| Complexity Overhead | Three pipelines are more complex to maintain than one | Medium | Comprehensive logging at each routing decision; integration tests; "dry-run" mode |
| Freshness Gaming | Frequently queried but low-quality content could get promoted | Low | Combine frequency with validation status; manual review queue for all promotions |

Table 7. Risk assessment and mitigations.

## 11. Role Assignment

| Member | Role | Responsibilities |
|--------|------|------------------|
| Morgan | Lead Implementer | All phases: code changes to index_archive.py, utils.py, brain_server.py; new scripts lifecycle_review.py, content_classifier.py |
| Dr. Priya Chandra | Architecture Advisor | Define content type taxonomy; design frontmatter schema; validate classification rules; review pipeline routing logic |
| Sam Torres | Freshness Design Lead | Design decay curves and half-life defaults; validate lifecycle_review.py; define promotion/demotion thresholds |

===== Page 15 =====

Table 8. Implementation role assignments.

## 12. Success Metrics

The council defined five measurable success criteria for the PDMPI framework. These metrics will be evaluated after each implementation phase to ensure that the strategy changes are delivering their intended benefits without degrading existing retrieval quality.

| Metric | Measurement | Target | Rationale |
|--------|-------------|--------|-----------|
| Classification Accuracy | Percentage of files correctly classified | > 90% on test set | Validates content type detection |
| Retrieval Quality | Score on eval/run_eval.py vs. baseline | No regression (> 95%) | Multi-pipeline must not degrade quality |
| Indexing Cost Reduction | Total LLM calls per full index | 40-60% reduction | Pipelines B/C skip expensive LLM extraction |
| Freshness Coverage | Chunks with half-life metadata | > 95% after Phase 4 | All content carries freshness metadata |
| Promotion Accuracy | Promoted chunks that improve relevance | > 70% positive impact | Query-driven promotion adds value |

Table 9. Success metrics with targets and rationale.

## 13. Council Consensus

The council reached unanimous agreement on the following conclusions. The current single- pipeline, uniform- chunk, no- freshness indexing strategy is a functional starting point but fundamentally misaligned with the Brain's two- tier memory narrative. The Brain already distinguishes between active resources and deep archives, between validated artifacts and raw content, between fast vector search and rich graph traversal. The indexing strategy should reflect these distinctions.

The Purpose- Driven Multi- Pipeline Indexing (PDMPI) framework provides a principled approach to making indexing decisions based on content purpose, structural characteristics, freshness requirements, and observed retrieval value. By routing content through pipelines that match their nature, the Brain can invest its limited compute budget where it generates the most value: deep entity extraction for research papers, fast embedding for news, and lightweight search for notes. The promotion and demotion lifecycle ensures that the knowledge base is self- optimizing, automatically elevating content that proves valuable through actual usage and gracefully degrading content that loses relevance over time.

===== Page 16 =====

1

The eight- week implementation roadmap delivers standalone value at each phase: metadata in weeks one and two, better chunking in weeks three and four, multi- pipeline routing in weeks five and six, and full lifecycle management in weeks seven and eight. Morgan will lead implementation, with each council member providing domain expertise and validation in their area of specialization. The framework preserves full backward compatibility through a migration path for existing content and a default "general" type that maintains the current indexing behavior for unclassified files. The council recommends immediate execution of Phase 1, with a two- week checkpoint to validate classification accuracy before proceeding to Phase 2.