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
