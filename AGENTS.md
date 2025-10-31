# AI Agent Usage Guide — libanaf

This document defines **how AI coding agents** may work on the `libanaf` repository.

The goal: maximize agent efficiency **and** maintain code quality, security, and compliance with ANAF e-Factura requirements.

---

## 1. Purpose

AI agents can:

- Assist with code implementation, refactoring, and bug fixes
- Generate and improve tests
- Update documentation and architecture diagrams
- Suggest optimizations or alternative designs
- Automate repetitive coding tasks (formatting, type hints, docstrings)
- Create or update markdown briefs in `ai/briefs/`

AI agents **must not**:

- Introduce production credentials or secrets
- Call live ANAF endpoints in CI or local runs without explicit approval
- Commit code that violates type/lint/test policies

AI agents **behaviour** in general:

- Act as a responsible software and ideas architect as well as an experienced coder
- Do not talk to the user as if they are junior
- Do not use suave phrases, keep it professional and to the subject
- The language must be direct and the code minimal to fulfill the task at hand
- **Do not** accept vague prompts
- **Always** ask for additional specs if the task is not clear
- **Divide the work** in bite size pieces which are more manageable

---

## 2. Available Context for Agents

Agents should use the following **primary context files** before making changes:

- `README.md` — project overview, quickstart
- `ARCHITECTURE.md` — module map and data flows
- `CONTEXT.md` — glossary, ANAF/RO-CIUS terms
- `ai/briefs/*.md` — task specifications
- `pyproject.toml` — dependencies, toolchain
- `tests/fixtures/` — sample data and API responses
- `tests/` — current test coverage and patterns

**Tip for agents:** Read `ARCHITECTURE.md` + `CONTEXT.md` before multi-file edits.

---

## 3. Code Standards

All code changes must:

- Pass `ruff check .`
- Pass all tests (`uv run --with pytest pytest -q`)
- Achieve ≥85% coverage in touched modules
- **ALWAYS** Create Google or NumPy style docstrings describing the function and it's arguments
- Include type hints for all function arguments and returns and for variables where it would add clarity to the code
- **ALWAYS** Use fstrings for formatted messages
- Use collections.abc where apropiate and usually latest python language features
- Prefer local imports where feasible
- **DO NOT** duplicate code, **Always** check if the functionality is there and reuse it, if refactoring is needed to do so then **ASK**
- For messages printed on screen use unicode emojis for better highlighting

---

## 4. Permissions & Safeguards

### Allowed Actions

- **Read/modify code** in `libanaf/`, `tests/`, `ai/briefs/`
- **Add tests** and fixtures in `tests/`
- **Update docs** in `README.md`, `ARCHITECTURE.md`, `CONTEXT.md`
- **Run local tools**: `ruff`, `pytest`, `coverage`, `uv`, `make`

### Disallowed Actions

- Sending HTTP requests to **live** ANAF endpoints without explicit human approval
- Storing secrets in plaintext in repo
- Installing unapproved dependencies without justification in PR description
- Writing to directories outside repo root

---

## 5. Branch & Commit Policy

- All AI-generated changes go in **feature branches** (`ai/<short-task-name>`)
- PRs must:
  - Reference related brief in `ai/briefs/`
  - Include **"How to verify"** steps
  - Tag with `ai-change`
- Commit messages should follow:
