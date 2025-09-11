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

---

## Quickstart

### Install

```bash
uv pip install libanaf
# or
pip install libanaf
