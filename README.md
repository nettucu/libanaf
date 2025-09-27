# libanaf

**libanaf** is a Python library and CLI tool for interacting with **ANAF's e-Factura API** in Romania.

It handles:

- OAuth2 authentication and token management, this requires Windows because ANAF tokens are handled by applications on windows
- Invoices (UBL 2.1 + RO-CIUS) download, in the future it could also validate and upload invoices
- Invoices processing, which takes the downloaded XML and using ANAF services converts it to PDF
- Message status polling
- Secure local configuration management

---

## Features

- **Python API** and **CLI** (via Typer)
- **Asynchronous HTTP** calls (httpx)
- **Retry and error handling** for ANAF endpoints
- **Configurable token storage** (filesystem or OS keyring)
- **Schema validation** for UBL 2.1 invoices
- **Invoice product summary** command with Rich output and precise discount allocation

---

## Quickstart

### Install

```bash
uv pip install libanaf
# or
pip install libanaf
```

### Invoice product summary

Produce a per-product table (all filters optional; supply both dates when filtering by period):

```bash
libanaf invoices prod-summary --invoice-number FIMCGB --start-date 2025-02-01 --end-date 2025-02-06
```

Wildcards are supported in `--invoice-number` and `--supplier-name`. Omitting all filters processes every stored document. The generated table includes quantities, unit prices, discounts split per line, VAT, and totals that reconcile with the payable amount.
