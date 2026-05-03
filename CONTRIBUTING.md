# Contributing to Zero-Cost Virtual Brain

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

1. **Fork & clone** the repository.
2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio ruff
   ```
4. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```
5. **Pull Ollama models** (if testing locally):
   ```bash
   ollama pull qwen3.5:4b
   ollama pull nomic-embed-text
   ```

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests are designed to run **without** Ollama or GPU — they only test pure logic (chunking, hashing, RRF scoring, query sanitization).

## Linting

```bash
ruff check .
```

Fix auto-fixable issues:
```bash
ruff check . --fix
```

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `refactor:` | Code restructuring (no behavior change) |
| `docs:` | Documentation only |
| `ci:` | CI/CD workflow changes |
| `chore:` | Maintenance (deps, .gitignore, etc.) |
| `test:` | Adding or updating tests |

Example: `feat: add graph pruning with configurable threshold`

## Pull Request Process

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make your changes with tests.
3. Ensure `pytest` and `ruff check` pass.
4. Open a PR against `main` with a clear description.
5. Wait for CI to pass and a maintainer review.

## Reporting Bugs

Use the [Bug Report](https://github.com/asiriji-lab/Personal-ai-archive/issues/new?template=bug_report.md) template.

## Hardware Notes

This project is optimized for **6GB VRAM** GPUs. If you're adding features that use the GPU, please test on constrained hardware or document VRAM requirements.

---

Thank you for contributing! 🧠
