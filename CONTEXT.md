# Context & Domain Glossary — libanaf

This document explains the **business and technical context** of `libanaf`.
AI agents and human developers should read this before implementing features.

---

## 1. Domain Overview

- **ANAF e-Factura**: Romania’s national electronic invoicing system, operated by ANAF (National Agency for Fiscal Administration).
- **UBL 2.1**: Universal Business Language XML standard used for invoices.
- **RO-CIUS**: Romanian Core Invoice Usage Specification. A local extension of UBL 2.1 with additional mandatory fields and validation rules.
- **e-Factura API**: REST/JSON endpoints provided by ANAF for authentication, document upload, status checks, and retrieval.

---

## 2. Key Terms

- **Invoice**: UBL 2.1 XML file extended with RO-CIUS requirements.
- **CreditNote**: UBL 2.1 XML for credit adjustments; also RO-CIUS compliant.
- **Message ID**: ANAF-generated identifier returned after uploading an invoice/credit note. Used for status polling and retrieval.
- **Inbox**: ANAF-provided mailbox of incoming invoices from other entities.
- **Authentication**: OAuth2 flow to obtain an access token (and refresh token). Required for all API calls.
- **Token Refresh**: Mechanism to extend access without re-login. Must be handled securely.
- **Validation**: Checking invoice XML against UBL 2.1 schema + RO-CIUS rules before sending to ANAF.
- **Status Polling**: Querying ANAF with a message ID to check if the document was accepted, rejected, or is still processing.

---

## 3. Invariants & Assumptions

- All invoices must be **valid UBL 2.1 + RO-CIUS** before upload; invalid XML will be rejected.
- Access tokens expire; refresh must occur transparently where possible.
- Upload responses include a **message ID**; this must be stored for later retrieval.
- Message statuses may take time to update; polling requires exponential backoff.
- Messages and downloads are available for a **limited retention period** (currently 60 days).
- Communication failures (HTTP 5xx, network issues) must be retried safely (idempotent operations only).
- Sensitive data (invoices, tokens) **must not be logged in plaintext**.

---

## 4. Data Structures

- **Token**

  ```json
  {
    "access_token": "string",
    "refresh_token": "string",
    "expires_in": 3600,
    "token_type": "Bearer"
  }
  ```

## 5. References

- [RO-CIUS Specification (Ministry of Finance PDF)](https://mfinante.gov.ro/static/10/Mfp/anaf/servicii_online/RO_CIUS.pdf)
- [UBL 2.1 Schema Reference (OASIS)](https://docs.oasis-open.org/ubl/os-UBL-2.1/)
- [ANAF e-Factura Service Portal](https://www.anaf.ro/)

## 6. Usage Notes for AI Agents

- Always validate invoices against schema before suggesting upload logic.
- Never include real invoice data or real tokens in examples/tests.
- Use fixtures in tests/fixtures/ for simulation.
- When unsure about RO-CIUS rules, assume stricter validation (mandatory fields must be present).
- For CLI tasks, prefer Typer subcommands over monolithic scripts.
