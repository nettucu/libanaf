# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
uv run python -m pytest tests/

# Run a single test file or test
uv run python -m pytest tests/test_config.py
uv run python -m pytest tests/test_config.py::test_function_name

# Lint
ruff check .

# Format
ruff format .

# Install dependencies
uv sync
```

## Architecture

**libanaf** is a CLI tool for the Romanian ANAF e-Factura API (OAuth2 auth, invoice download/processing). Entry point: `libanaf/cli/app.py` → `libanaf = "libanaf.cli:app"`.

### Module Map

- `libanaf/config.py` — `Settings(BaseSettings)` with nested sections (`auth`, `connection`, `efactura`, `storage`, `retry`, `log`, `notification`, `state`). Env prefix `LIBANAF_`, nested delimiter `__` (e.g. `LIBANAF_AUTH__CLIENT_ID`). `get_settings()` is `@lru_cache`; env file path from `LIBANAF_ENV_FILE` env var (default: `secrets/.env`). `save_tokens()` writes tokens back via python-dotenv `set_key`.
- `libanaf/exceptions.py` — `AnafException` → `AnafRequestError`, `AuthorizationError` → `TokenExpiredError` (refresh token dead, hard re-auth required).
- `libanaf/failure_tracker.py` — JSON-backed persistent counter (`SyncState`); `record_network_failure()` increments and returns `True` at threshold; `record_success()` resets to 0.
- `libanaf/notifications.py` — `send_email()` via stdlib `smtplib`; calls `starttls()` + `login()` when `smtp_user`/`smtp_password` are set (Gmail SMTP); `send_token_expired_alert()` and `send_network_failure_alert()` are the two alert helpers.
- `libanaf/auth/` — `client.py` (`AnafAuthClient`, OAuth2 flow via Authlib), `server.py` (`OAuthCallbackServer`, Flask-based local redirect server). No typer imports.
- `libanaf/cli/` — `app.py` (root Typer app, `@app.callback()` guards `get_settings()` with `ctx.resilient_parsing`), `auth.py` (auth command with retry loop using `typer.confirm`, `show-token` command), `invoices/` (Typer sub-app; commands: `list`, `show`, `summary`, `prod-summary`, `download`, `process`, `render-pdf`).
- `libanaf/invoices/` — pure library package (no CLI code); `list.py` (`fetch_invoice_list()` async), `download.py`, `process.py`, `query.py` (`collect_documents()` parses XML in parallel via `ThreadPoolExecutor`, 8 threads), `summary.py` (`SummaryRow`, `build_summary_rows`, `summarize_invoices`), `product_summary.py` (`ProductSummaryRow`, `build_product_summary_rows`, `summarize_products`). Public API exposed via `__all__`.
- `libanaf/ubl/` — `ubl_document.py` (`UBLDocument` base pydantic-xml model, `parse_ubl_document()` dispatches to `Invoice` or `CreditNote` based on XML root tag), `invoice.py`, `credit_note.py`, `cac.py` (UBL CAC namespace elements), `ubl_types.py` (namespace map).
- `libanaf/types.py` — shared types including `Filter` enum for ANAF message filtering.

### Key Data Flows

**Invoice download**: `invoices download` → `download()` calls `fetch_invoice_list()` to get message IDs → fetches ZIPs from ANAF API → stores in `settings.storage.download_dir` (default: `dlds/`).

**Invoice processing**: `invoices process` → `process_invoices()` unzips downloads, extracts XML, calls ANAF xml2pdf API to convert to PDF.

**Local querying** (`show`, `summary`, `prod-summary`, `render-pdf`): `collect_documents()` in `invoices/query.py` globs `*.xml` from `dlds/`, parses them in parallel (8 threads), filters by invoice_number/supplier_name/date range, returns `list[Invoice | CreditNote]`.

**Auth flow**: `auth` command → `AnafAuthClient` starts `OAuthCallbackServer` (Flask + TLS), opens browser → user authenticates → callback saves tokens via `save_tokens()`. `get_settings()` cache must be cleared after token save.

**Invoice download (failure path)**: `TokenExpiredError` (OAuth2 refresh failed) → immediate email via `send_token_expired_alert()`; network/HTTP exceptions → `record_network_failure()` increments counter, `send_network_failure_alert()` fires at threshold; success → `record_success()` resets counter.

### Invariants

- `get_settings()` is cached; never call during `ctx.resilient_parsing` (help/tab-completion).
- All invoice modules call `get_settings()`, never `get_config()`.
- UBL discount calculation: `LineExtensionAmount` is gross; discount in `AllowanceCharge` (negative Amount); taxable = gross − |discount|; VAT on taxable amount.
- ANAF messages have a 60-day retention window.
- Notifications are inert until `LIBANAF_NOTIFICATION__EMAIL_TO` is set; all notification/tracker calls are guarded by `if settings.notification.email_to`.
- `failure_tracker` never raises — all I/O errors are logged as warnings so a broken state file cannot mask the original sync failure.

## Code Standards (from AGENTS.md)

- Google or NumPy style docstrings on all functions with Args/Returns/Raises sections.
- Type hints on all function arguments, return types, and variables where clarity is added.
- f-strings for all formatted messages; unicode emojis for CLI output.
- `collections.abc` types where appropriate; use latest Python language features (Python ≥ 3.11).
- Local imports where feasible (avoids circular imports in UBL dispatch).
- Never duplicate logic — check for existing utilities before implementing.
- Line length: 120. Quote style: double. (enforced by `ruff.toml`)

## Branch Policy

AI-generated feature branches: `ai/<short-task-name>`.
