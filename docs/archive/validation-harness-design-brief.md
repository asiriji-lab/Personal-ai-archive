ZeroCostBrain is a local-first personal knowledge system with a two-tier brain:
Active Brain (Obsidian vault) and Archive Brain (LightRAG). AutoResearchClaw
generates research papers that land in autoresearchclaw/artifacts/rc-<run_id>/,
but currently nothing moves them into Archives/ with validation. I need a
best-effort validation harness and structured review queue that sits between
paper generation and LightRAG indexing.

Produce `docs/validation-harness.txt`, a tight, decision-complete specification
following the project's style.

## Integration handoff point
The harness must define and own the handoff step from AutoResearchClaw output
into the Archive. It must:
- Locate paper_draft.md and pipeline_summary.json in the artifact directory.
- Run claims extraction and validation (detailed below).
- On completion, copy paper_draft.md into Archives/ (enriched with validation
  metadata in frontmatter and a warning block if needed).
- Trigger LightRAG indexing on the archived file.
- Be invocable explicitly after an AutoResearchClaw run or watch for completion.

## Claims extraction
Use the most structured source available:
- Primary: If pipeline_summary.json contains a key like "knowledge_cards",
  "claims", or a structured summary array, extract claims directly from there.
- Fallback: If no structured claims exist, call Gemini Flash (existing stack
  model) to extract factual claims from the abstract and conclusion sections
  of paper_draft.md, limiting scope to those sections for cost/accuracy.

## Validation
For each claim, call a local LLM (default: Ollama with model qwen3.5:4b) with
the source text chunk and the claim text. The validator must return JSON:
{"verdict": "pass|fail", "explanation": "..."}.
- If Ollama is unavailable, mark the claim as "validation skipped" and proceed.
- Validation is best-effort: never block ingestion.

## Review queue
Store review entries in both formats:
- Authoritative: vault/system/review-queue.jsonl (append-only, machine-readable).
- Human-readable: vault/system/review-queue.md, regenerated from JSONL on each
  update for browsing in Obsidian.

JSONL schema per line:
{
  "timestamp": "ISO8601",
  "source_file": "path/to/paper_draft.md",
  "claim_text": "...",
  "confidence": 0.85,
  "validator_verdict": "pass|fail|skipped",
  "validator_explanation": "...",
  "status": "pending_review|accepted|rejected"
}

## Handling failed claims before indexing
Before copying paper_draft.md to Archives/ and indexing:
- Add a validation_summary block to the YAML frontmatter:
  validation_summary:
    total_claims: 12
    passed: 9
    failed: 2
    skipped: 1
    failed_claims: ["text1", "text2"]
- Prepend a blockquote warning to the top of the body:
  > ⚠️ Validation Warning: This paper contains claims that did not pass
  > automated validation. See vault/system/review-queue.md for details.
- The entire enriched file is then what LightRAG indexes, making the caveat
  searchable and visible.

## MCP bridge extension
Extend the existing FastMCP bridge with a `review_queue` tool that returns
current review queue contents from the JSONL file (formatted for display).

## Assumptions and constraints
- No new databases, no new servers. Reuse existing stack.
- Ollama URL and model are configurable via environment variables.
- Gemini Flash API key via existing GEMINI_API_KEY env var.
- The harness script is placed in scripts/validate_and_archive.py.
- Existing AutoResearchClaw artifact structure is standard (paper_draft.md and
  pipeline_summary.json present).

Output the complete specification document as `docs/validation-harness.txt`.
No implementation code—just the spec.