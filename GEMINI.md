# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this project. Adhering to these guidelines will ensure consistency and maintain code quality.

## 1. Project Overview & Purpose

* **Primary Goal:** This project, `libanaf`, is a Python library and Command Line Interface (CLI) designed to interact with the Romanian National Agency for Fiscal Administration (ANAF) e-Factura API. Its core functions include handling OAuth2 authentication, downloading and processing electronic invoices (in UBL XML format), and monitoring message statuses.
* **Business Domain:** The project operates in the Fintech sector, specifically focusing on electronic invoicing and fiscal compliance within Romania.

## 2. Core Technologies & Stack

* **Languages:** Python (>=3.11)
* **Frameworks & Runtimes:** Typer for the CLI application, with Flask used for the local server during the OAuth2 authentication flow.
* **Databases:** The application does not use a traditional database. It interacts directly with the ANAF API and stores configuration and downloaded invoices on the local filesystem.
* **Key Libraries/Dependencies:**
    *   `httpx`: Asynchronous HTTP client for API communication.
    *   `authlib`: Handles the OAuth2 authentication flow.
    *   `pydantic-xml`: For parsing and validating UBL XML invoices.
    *   `lxml`: Used for XML schema validation.
    *   `typer`: Powers the command-line interface.
    *   `rich`: For creating formatted and visually rich CLI output.
* **Package Manager(s):** `pip` is the standard package manager. The `README.md` also mentions `uv` as a faster alternative for installation and environment management.

## 3. Architectural Patterns

* **Overall Architecture:** The project is a modular Python application with a clear separation of concerns. It exposes its functionality as both a library and a CLI. The architecture is designed around distinct modules for authentication (`auth.py`), API communication (`comms.py`), configuration (`config.py`), and domain-specific logic for invoices (`invoices/`) and UBL standards (`ubl/`).
* **Directory Structure Philosophy:**
    *   `/libanaf`: Contains all primary source code for the library and CLI.
    *   `/libanaf/invoices`: Holds the logic specific to invoice management (downloading, processing, summarizing).
    *   `/libanaf/ubl`: Contains code for UBL XML serialization, deserialization, and validation.
    *   `/tests`: Contains all unit and integration tests, with fixtures located in `/tests/fixtures`.
    *   `/conf`: Intended for application configuration files (e.g., `config.toml`).
    *   `/ai/briefs`: Stores detailed specifications for tasks to be handled by AI agents.
    *   `/docs`: Contains project documentation, specifications, and sample files.

## 4. Coding Conventions & Style Guide

* **Formatting:** Code is formatted using `ruff` with a line length of 120 characters, double quotes (`"`) for strings, and space-based indentation. All code must pass `ruff check .`.
* **Naming Conventions:**
    *   `variables`, `functions`: `snake_case` (e.g., `get_config`)
    *   `classes`: `PascalCase` (e.g., `LibANAF_AuthClient`)
    *   `files`: `snake_case` (e.g., `product_summary.py`)
* **API Design:** The internal API is modular. The external interaction is with the ANAF REST/JSON API. The CLI follows a command/subcommand structure (e.g., `libanaf invoices prod-summary`).
* **Error Handling:** The application uses custom exceptions (e.g., `AnafAuthError`, `AnafRequestError`) and implements a retry policy with exponential backoff for handling transient API errors.

## 5. Key Files & Entrypoints

* **Main Entrypoint(s):** The primary entrypoint for the CLI application is the `app` object in `libanaf/cli.py`, which is exposed as a script via `pyproject.toml` (`libanaf.cli:app`).
* **Configuration:** Configuration is loaded from `conf/config.toml` or `.env` files. The `libanaf/config.py` module manages access to configuration.
* **CI/CD Pipeline:** No CI/CD pipeline configuration file (e.g., `.github/workflows/`) was detected in the project structure.

## 6. Development & Testing Workflow

* **Local Development Environment:** To set up a local development environment, install the project in editable mode with development dependencies using `uv pip install -e .[dev]`.
* **Testing:** Tests are written using `pytest` and executed by running `uv run pytest -q`. Test files are located in the `/tests` directory. New code should have corresponding test coverage, aiming for ≥85%.
* **CI/CD Process:** There is no automated CI/CD process defined in the repository. All checks (linting, testing) are expected to be run manually before committing.

## 7. Specific Instructions for AI Collaboration

* **Contribution Guidelines:** The `AGENTS.md` file is the definitive guide. Key rules include:
    *   All code must pass `ruff check .` and all tests (`uv run pytest -q`).
    *   New code in a module should achieve at least 85% test coverage.
    *   Functions must have Google or NumPy style docstrings and full type hints.
    *   Use f-strings for string formatting.
    *   Do not duplicate code; refactor for reuse if necessary.
    *   All work should be done in feature branches named `ai/<short-task-name>`.
* **Infrastructure (IaC):** No Infrastructure as Code (IaC) was detected.
* **Security:** Be extremely mindful of security. Do not hardcode secrets or keys. Do not log sensitive data like tokens or invoice contents in plaintext. Live ANAF endpoints must not be called without explicit human approval.
* **Dependencies:** New dependencies should be added to the `[project.dependencies]` or `[project.optional-dependencies]` section in `pyproject.toml`.
* **Commit Messages:** While not explicitly defined, follow the Conventional Commits specification (e.g., `feat:`, `fix:`, `docs:`, `refactor:`) for clear and consistent commit history.
