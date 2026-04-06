# libanaf Architecture

## 1. Overview

libanaf is a modular Python package (≥3.11) that exposes both a **library API** and a **Typer CLI** for interacting with the Romanian ANAF e-Factura system. The library layer (`libanaf/`) has no CLI dependencies; the CLI layer (`libanaf/cli/`) imports from the library and adds Typer commands, Rich output, and user-facing error handling.

---

## 2. Module Map

```
libanaf/
├── __init__.py              # Public API — re-exports from all sub-packages via __all__
├── config.py                # Settings(BaseSettings) — env prefix LIBANAF_, nested delimiter __
├── exceptions.py            # AnafException → AnafRequestError, AuthorizationError → TokenExpiredError
├── types.py                 # Shared types: Filter enum (E/T/P/R)
├── failure_tracker.py       # Persistent JSON failure counter for sync monitoring
├── notifications.py         # Email alerts via smtplib (STARTTLS + auth for Gmail)
│
├── auth/
│   ├── __init__.py          # Re-exports: AnafAuthClient, OAuthCallbackServer
│   ├── client.py            # AnafAuthClient — OAuth2 Authorization Code flow via Authlib
│   └── server.py            # OAuthCallbackServer — Flask + TLS local redirect server
│
├── cli/
│   ├── app.py               # Root Typer app; @app.callback() guards get_settings()
│   ├── auth.py              # `auth` command (retry loop + typer.confirm), `show-token`
│   └── invoices/
│       ├── __init__.py      # Typer sub-app: registers list/show/summary/prod-summary/download/process/render-pdf
│       ├── list.py          # `invoices list` — fetches and displays message list in a Rich table
│       ├── show.py          # `invoices show` — displays matching invoices
│       ├── summary.py       # `invoices summary` — tabular invoice summary
│       ├── product_summary.py  # `invoices prod-summary` — product-level summary
│       ├── download.py      # `invoices download` — download ZIPs from ANAF
│       ├── process.py       # `invoices process` — unzip + ANAF xml2pdf conversion
│       └── pdf_render.py    # `invoices render-pdf` — local PDF rendering via ReportLab
│
├── invoices/
│   ├── __init__.py          # Public API via __all__
│   ├── list.py              # fetch_invoice_list() — async, queries listaMesajeFactura endpoint
│   ├── download.py          # download() — fetches ZIPs, skips already-downloaded IDs
│   ├── process.py           # process_invoices() — unzip, extract XML, call ANAF xml2pdf API
│   ├── query.py             # collect_documents() — parallel XML parsing (ThreadPoolExecutor, 8 threads)
│   ├── summary.py           # SummaryRow, build_summary_rows(), summarize_invoices()
│   ├── product_summary.py   # ProductSummaryRow, build_product_summary_rows(), summarize_products()
│   ├── common.py            # Shared helpers: ensure_date_range(), DateValidationError
│   └── _retry.py            # anaf_retrying() — tenacity retry decorator for ANAF calls
│
└── ubl/
    ├── __init__.py          # Public API via __all__
    ├── ubl_document.py      # UBLDocument (pydantic-xml base), parse_ubl_document() dispatcher
    ├── invoice.py           # Invoice model
    ├── credit_note.py       # CreditNote model
    ├── cac.py               # UBL CAC namespace elements
    └── ubl_types.py         # Namespace map
```

---

## 3. Key Data Flows

### Auth flow
```
libanaf auth
  → AnafAuthClient.get_access_token()
  → OAuthCallbackServer (Flask + TLS on localhost:8000)
  → browser opens ANAF OAuth URL
  → callback receives code → exchanges for tokens
  → save_tokens() writes to secrets/.env via python-dotenv
  → get_settings() cache cleared
```

### Invoice download
```
libanaf invoices download
  → fetch_invoice_list() [async, ANAF listaMesajeFactura]
  → compares message IDs against already-downloaded files in dlds/
  → downloads missing ZIPs from ANAF descarcare endpoint
  → stores as {id}.zip in settings.storage.download_dir (default: dlds/)
```

### Invoice processing
```
libanaf invoices process
  → scans dlds/ for *.zip files not yet unzipped
  → extracts XML from each ZIP
  → calls ANAF xml2pdf endpoint → saves PDF alongside XML
```

### Local querying (show / summary / prod-summary / render-pdf)
```
collect_documents(dlds/)
  → globs *.xml
  → parse_ubl_document() in parallel (8 threads)
  → filters: invoice_number, supplier_name, date range
  → returns list[Invoice | CreditNote]
```

### Sync failure notification
```
invoices download (failure path)
  → TokenExpiredError (OAuth2Error from authlib on failed token refresh)
      → send_token_expired_alert() immediately via smtp.gmail.com:587
  → HTTPStatusError / Exception (network/API outage)
      → record_network_failure(state/sync_state.json)
      → if count >= threshold: send_network_failure_alert()
  → success
      → record_success() — resets counter to 0
```

---

## 4. Configuration

Settings are loaded via `pydantic-settings` with env prefix `LIBANAF_` and nested delimiter `__`:

| Section | Key example | Env var |
|---|---|---|
| `auth` | `client_id` | `LIBANAF_AUTH__CLIENT_ID` |
| `connection` | `access_token` | `LIBANAF_CONNECTION__ACCESS_TOKEN` |
| `efactura` | `message_list_url` | `LIBANAF_EFACTURA__MESSAGE_LIST_URL` |
| `storage` | `download_dir` | `LIBANAF_STORAGE__DOWNLOAD_DIR` |
| `retry` | `count` | `LIBANAF_RETRY__COUNT` |
| `log` | `file` | `LIBANAF_LOG__FILE` |
| `notification` | `email_to` | `LIBANAF_NOTIFICATION__EMAIL_TO` |
| `notification` | `smtp_host` | `LIBANAF_NOTIFICATION__SMTP_HOST` |
| `notification` | `smtp_port` | `LIBANAF_NOTIFICATION__SMTP_PORT` |
| `notification` | `smtp_user` | `LIBANAF_NOTIFICATION__SMTP_USER` |
| `notification` | `smtp_password` | `LIBANAF_NOTIFICATION__SMTP_PASSWORD` |
| `notification` | `network_failure_threshold` | `LIBANAF_NOTIFICATION__NETWORK_FAILURE_THRESHOLD` |
| `state` | `state_file` | `LIBANAF_STATE__STATE_FILE` |

The env file path defaults to `secrets/.env` and is overridden by `LIBANAF_ENV_FILE`.
`get_settings()` is `@lru_cache` — call `get_settings.cache_clear()` after writing new tokens.

Notifications are **disabled by default** (`email_to` is unset). Set `LIBANAF_NOTIFICATION__EMAIL_TO` to activate. See `secrets/.env.example` for a complete reference.

---

## 5. External Dependencies

| Library | Purpose |
|---|---|
| `httpx` | Async HTTP client |
| `authlib` | OAuth2 Authorization Code flow |
| `pydantic-settings` | Typed configuration from env vars |
| `pydantic-xml` | UBL XML deserialization |
| `lxml` | XML schema validation |
| `tenacity` | Retry with exponential backoff |
| `flask` | Local HTTPS callback server for OAuth |
| `cryptography` / `pyOpenSSL` | Self-signed TLS cert for OAuth callback |
| `reportlab` | Local PDF rendering from UBL XML |
| `typer` | CLI framework *(optional — `libanaf[cli]`)* |
| `rich` | Terminal tables and formatting *(optional — `libanaf[cli]`)* |

---

## 6. Error Handling

- `AnafException` — base
  - `AnafRequestError` — HTTP or API-level errors (ANAF returned `"eroare"`)
  - `AuthorizationError` — OAuth flow failures
    - `TokenExpiredError` — refresh token is invalid; hard re-auth via `libanaf auth` is required
- Retry policy: `anaf_retrying()` (tenacity) — exponential backoff on transient errors; configured via `settings.retry.*`
- CLI layer catches library exceptions and prints user-friendly messages via Rich before exiting with non-zero code

### Sync failure notifications (`download()`)

`invoices/download.py::download()` distinguishes two failure modes and acts accordingly:

| Failure type | Detection | Behaviour |
|---|---|---|
| Token expired | `OAuth2Error` from authlib → `TokenExpiredError` | Send email immediately, no counter |
| Network / API error | `HTTPStatusError` or any other exception | Increment `state_file` counter; send email when count ≥ `network_failure_threshold` (default 5) |
| Success | Normal completion | Reset counter to 0 |

Counter is persisted in a JSON file (`settings.state.state_file`, default `state/sync_state.json`) so it survives across systemd restarts.

---

## 7. CLI Commands

```
libanaf
├── auth          — start OAuth2 flow, with retry loop
├── show-token    — decode and display JWT claims from stored access token
└── invoices
    ├── list          — list available messages from ANAF (last N days)
    ├── show          — display matching locally-stored invoices
    ├── summary       — tabular summary (supplier, date, totals)
    ├── prod-summary  — product-level summary with discount allocation
    ├── download      — download new ZIPs from ANAF
    ├── process       — unzip + convert XML→PDF via ANAF api
    └── render-pdf    — generate PDF locally from UBL XML (no ANAF call)
```

---

## 8. Invariants

- `get_settings()` must never be called during `ctx.resilient_parsing` (tab-completion / help generation).
- All invoice library modules call `get_settings()`, never `get_config()`.
- UBL discount math: `LineExtensionAmount` is gross; `AllowanceCharge.Amount` is negative for discounts; taxable = gross − |discount|; VAT is calculated on the taxable amount.
- ANAF message retention window: 60 days.
- `libanaf/invoices/` has no dependency on `typer` or `rich` — display logic lives exclusively in `libanaf/cli/invoices/`.
