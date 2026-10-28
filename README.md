# libanaf

**libanaf** is a Python library and CLI tool for interacting with **ANAF's e-Factura API** in Romania.

It handles:

- OAuth2 authentication and token management (browser-based, cross-platform)
- Invoices (UBL 2.1 + RO-CIUS) download, in the future it could also validate and upload invoices
- Invoices processing, which takes the downloaded XML and using ANAF services converts it to PDF
- Message status polling
- SPV (Spațiul Privat Virtual) inbox: list and archive message PDFs past the 60-day retention, request documents
  (fișa pe plătitor, obligații, duplicate de declarații/recipise, vector fiscal, adeverințe de venit)
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
- **SPV client** (`libanaf spv ...`): inbox listing with authorized-CUI summary, incremental PDF download, document
  requests; certificate session imported from a browser (works with cloud certificates such as certSIGN vToken)
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
pbpaste | ssh linux-host 'cd ~/work/libanaf && uv run libanaf spv import-cookies'          # from macOS
Get-Clipboard | ssh linux-host "cd ~/work/libanaf && uv run libanaf spv import-cookies"    # from Windows PowerShell
libanaf spv import-cookies cookies.txt                                                     # or from a file
```

`libanaf spv import-cookies --help` repeats these steps.

**Commands**

```bash
libanaf spv list --days 60 [--cif 123]     # messages + table of authorized CUI/CNPs with message counts
libanaf spv download [--dir PATH]          # only messages not stored yet
libanaf spv request "Fisa Rol" --cui 123   # answer arrives later as an inbox message (RASPUNS SOLICITARE)
libanaf spv request D300 --cui 123 --an 2026 --luna 9
```

- `list` prints the inbox and a summary of the CUI/CNPs the certificate is authorized for (from the `cui` field of
  the response) with the message count per CIF; authorized CUIs with no messages show `0`.
- `download` saves PDFs as `<dir>/<cif>/<YYYY-MM>/<YYYY-MM-DD>_<tip>_<id>.pdf`, default dir `dlds/spv/`
  (override with `--dir` or `LIBANAF_SPV__DOWNLOAD_DIR`). A message is skipped when a PDF with its `id` already
  exists anywhere under the dir, so running it at least every 60 days keeps a full archive.
- `request` files a `cerere`; every call creates a new request at ANAF (repeats produce duplicate answers). The
  `TIP` is case-sensitive and passed verbatim (`"Fisa Rol"`, not `"Fisa rol"`). `libanaf spv request --help` lists
  the known types:

| Parameters | Types |
|---|---|
| `--cui` | `Fisa Rol` (optional `--cui-pui`), `Obligatii de plata`, `Nota obligatiilor de plata`, `Situatie Sintetica`, `VECTOR FISCAL`, `DATE IDENTIFICARE`, `Istoric Spatiu Virtual`, `Registru intrari-iesiri`, `InterogariBanci`, `Istoric bilant`, `D112Contrib`, `NeconcordanteD112CNP` |
| `--cui --an` | `Istoric declaratii`, `Bilant anual`, `Bilant semestrial`, `D101`, `D106`, `D120`, `D130`, `D205`, `D212`, `D392`, `D393` |
| `--cui --an --luna` | `D100`, `D112`, `D180`, `D300`, `D301`, `D311`, `D390`, `D394`, `D208` (`--luna 6`/`12` = S1/S2) |
| `--cui --numar-inregistrare` | `Duplicat Recipisa` |
| `--cui --an --motiv` | `Adeverinte Venit` (e.g. `Pensie`, `Altele`) |
| `--cui --an --lunai --lunas` | `NeconcordanteD394` |

`CAF` is not available through the API. The list comes from ANAF's 2018–2019 reference client
([MfpAnaf/ClientSPV](https://github.com/MfpAnaf/ClientSPV)); ANAF's validation error is authoritative.

When the session expires the commands exit with 🔐 and ask for a fresh import. The session provider is pluggable
(`libanaf.spv.session.SpvSession`); a PKCS#11 provider for a physical token can replace the cookie jar.
