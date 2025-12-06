# Error Handling Improvements in Invoices List

## Overview
This document outlines the improvements made to error handling within the `libanaf` library, specifically targeting the `invoices list` functionality. The goal is to provide more robust and granular handling of network and API-related errors, ensuring the application fails gracefully with informative messages rather than crashing with unhandled exceptions.

## Rationale
The previous implementation directly awaited `httpx.get` calls without specific exception handling. This meant that network issues, timeouts, or non-200 OK responses (that weren't manually checked) could propagate as raw stack traces to the user.

## Changes

### New Exception Hierarchy
A new module `libanaf.exceptions` has been introduced to define custom application exceptions.
- `AnafException`: Base class for all library-specific exceptions.
- `AnafRequestError`: Raised when an API request fails due to network issues, timeouts, or bad status codes.

### Granular Handling in `list.py`
The `fetch_invoice_list` function now wraps `httpx` calls in a `try-except` block that distinguishes between:
- `httpx.TimeoutException`: Connection timed out.
- `httpx.NetworkError`: General network failure (DNS, connection refused, etc.).
- `httpx.HTTPStatusError`: The server returned a 4xx or 5xx status code.
- `json.JSONDecodeError`: The server returned a success status but invalid JSON.
- `httpx.RequestError`: Catch-all for other `httpx` errors.

Each of these is wrapped into an `AnafRequestError` with a context-specific message and re-raised.

### Retries with Tenacity
The application now uses the `tenacity` library to handle retries for network operations.
- **Configurable**: Retry parameters (count, delay, backoff) are configurable via `config.toml` under `[retry]`.
- **Implementation**: Uses `AsyncRetrying` context manager to wrap HTTP requests.
- **Scope**: Applied to `list` (fetching messages), `download` (downloading ZIPs), and `process` (PDF conversion).

### Graceful Exit in CLI
The `invoices list` command in `libanaf.invoices.app` catches `AnafRequestError`. Instead of printing a traceback, it:
1. Logs the error detailed message.
2. Prints a user-friendly error message to the console using `typer.secho`.
3. Exits with a non-zero status code (`typer.Exit(code=1)`), allowing scripts (like systemd units) to detect failure.
