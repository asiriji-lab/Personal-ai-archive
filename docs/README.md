# ZeroCostBrain — Docs

Start here. Three documents. Read in order if you're new.

---

## 1. [idea.md](idea.md)
**What this is and why it exists.**
The founding vision — two-tier brain, zero API cost, full local privacy.
Read this to understand the goals before touching any code.

## 2. [setup_brain.md](setup_brain.md)
**How to run it.**
Prerequisites, first-time setup, all commands, all environment variables.
The correct current values are here (not in the code comments, not in your memory).

## 3. [dev_log.md](dev_log.md)
**What was built, what broke, and why.**
Every non-obvious bug with its root cause. Every design decision with its reasoning.
Performance numbers measured on real hardware. What works, what doesn't, what's next.

If something breaks, check dev_log.md before debugging blind.
If you're continuing development, read the "For the Next Developer" section at the bottom.

---

## Quick orientation

```
Two tiers:
  Tier 1  embed.py + query.py    Obsidian vault -> SQLite (fast keyword/vector search)
  Tier 2  index_archive.py       Archives -> LightRAG knowledge graph (entity + graph search)

Research loop:
  AutoResearchClaw runs a sprint -> paper lands in 4. Archives/research/
  -> python index_archive.py --reset -> LightRAG learns it
  -> brain_server.py serves it via MCP to Claude/Cursor

Hardware assumed: RTX 4050 (6GB VRAM), Windows 11, Ollama local
Models: qwen3.5:4b (Q4_K_M) for LLM, nomic-embed-text for 768-dim embeddings
```
