---

## `ARCHITECTURE.md` skeleton

```markdown
# libanaf Architecture

## 1. Overview
libanaf is structured as a modular Python package with a Typer-based CLI.
It provides a consistent interface for ANAF e-Factura operations:
- Authentication
- Communication (HTTP requests)
- Invoice (UBL) handling
- CLI commands

---

## 2. Module Map

libanaf/
│
├── auth.py # OAuth2 flow, token management, refresh
├── comms.py # HTTP client (httpx), retries, error handling
├── config.py # Config loading, token store abstraction
├── cli.py # Typer CLI entrypoints
├── types.py # TypedDict / Pydantic models
├── utils.py # Helpers (logging, env, parsing)
│
├── invoices/ # Invoice-specific logic
├── ubl/ # UBL XML serialization/validation
│
└── tests/ # Unit/integration tests + fixtures

---

## 3. Data Flow

### **Example: Invoice Upload**

1. CLI calls `invoice upload` command in `cli.py`
2. Loads config + token from `config.py` / `auth.py`
3. Serializes and validates invoice via `ubl/`
4. Sends request to ANAF API using `comms.py`
5. Parses response into typed model in `types.py`
6. CLI prints message ID / status

---

## 4. Authentication

- **OAuth2 Authorization Code Flow** (local redirect)
- Refresh token logic (TODO: implement & test)
- Token storage backends:
  - Filesystem (encrypted)
  - OS keyring

---

## 5. External Dependencies

- `httpx` — async HTTP client
- `authlib` — OAuth2 flows
- `pydantic` / `pydantic-xml` — typed models and XML parsing
- `lxml` — UBL schema validation
- `typer` - CLI manager

---

## 6. Configuration

- `.env` or `conf/config.toml` for endpoints and client credentials
- `.env.example` with placeholders
- AI agents: refer to `CONTEXT.md` for domain glossary

---

## 7. Error Handling

- Custom exceptions (`AnafAuthError`, `AnafRequestError`, `AnafRateLimitError`)
- Retry policy (exponential backoff) for 5xx and certain 4xx responses
- Validation errors surfaced with schema details

---

## 8. CLI Commands

- `auth` → login, refresh, status
- `invoice` → validate, upload, status, download
- `inbox` → list, pull

---

## 9. Future Enhancements

- Complete token refresh + expiry handling
- Async batch upload
- Full RO-CIUS schema compliance checks
