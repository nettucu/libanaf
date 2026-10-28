# libanaf

**libanaf** is a Python library and CLI tool for interacting with **ANAF's e-Factura API** in Romania.

It handles:

- OAuth2 authentication and token management (browser-based, cross-platform)
- Invoices (UBL 2.1 + RO-CIUS) download, in the future it could also validate and upload invoices
- Invoices processing, which takes the downloaded XML and using ANAF services converts it to PDF
- Message status polling
- Secure local configuration management

See also: [Architecture](ARCHITECTURE.md) · [Domain Glossary](CONTEXT.md) · [AI Agent Guide](AGENTS.md)

---

## Features

- **Python library API** (`import libanaf`) and **CLI** (`libanaf invoices ...`) via Typer
- **Asynchronous HTTP** calls (httpx) with automatic retry and exponential backoff
- **Token storage** via pydantic-settings and `.env` files (`secrets/.env`)
- **UBL 2.1 + RO-CIUS** invoice and credit note parsing (pydantic-xml)
- **Invoice summary** and **product-level summary** with precise discount allocation
- **Local PDF rendering** from UBL XML without an ANAF API call
- **Email alerts** on sync failure: immediate notification when the ANAF refresh token is expired (hard re-auth required); threshold-based notification (default: 5 consecutive runs) for network/API outages

---

## Quickstart

### Install

```bash
# Library only (no CLI entry point)
pip install libanaf

# Library + CLI (installs `libanaf` command)
pip install libanaf[cli]

# Development
uv sync
```

### Invoice product summary

Produce a per-product table (all filters optional; supply both dates when filtering by period):

```bash
libanaf invoices prod-summary --invoice-number FIMCGB --start-date 2025-02-01 --end-date 2025-02-06
```

Wildcards are supported in `--invoice-number` and `--supplier-name`. Omitting all filters processes every stored document. The generated table includes quantities, unit prices, discounts split per line, VAT, and totals that reconcile with the payable amount.

### SPV inbox and document requests (SPVWS2)

SPV (`https://webserviced.anaf.ro/SPVWS2/rest/`) does not accept the e-Factura OAuth token: it needs a session
bootstrapped with the qualified certificate. With a cloud certificate (certSIGN vToken, Windows/macOS only) the
session is created in a browser and its cookies are imported:

1. On the Mac/Windows machine with vToken, open `https://webserviced.anaf.ro/SPVWS2/rest/listaMesaje?zile=60`,
   pick the certificate and approve with the authenticator code until the JSON list shows.
2. In DevTools → Network, reload, copy the `Cookie` request header (or export `cookies.txt` with an extension).
3. Import it on the Linux machine (stored in `state/spv_cookies.json`, mode 0600 — treat it like a password):

```bash
pbpaste | ssh linux-host 'cd ~/work/libanaf && uv run libanaf spv import-cookies'
libanaf spv list --days 60
libanaf spv download                       # new PDFs -> dlds/spv/<cif>/<YYYY-MM>/
libanaf spv request "Fisa Rol" --cui 123   # answer arrives later as an inbox message
libanaf spv request D300 --cui 123 --an 2026 --luna 9
```

When the session expires the commands exit with 🔐 and ask for a fresh import. The session provider is pluggable
(`libanaf.spv.session.SpvSession`); a PKCS#11 provider for a physical token can replace the cookie jar.
