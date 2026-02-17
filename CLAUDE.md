# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoERP is a whitelabeled fork of ERPNext, an open-source ERP system built on the **Frappe Framework** (Python + JavaScript). The upstream package name is `erpnext` and all Python module paths use `erpnext.*`. It uses a DocType-driven architecture where business entities are defined as JSON schemas with Python controllers and optional JavaScript client scripts.

**Version**: 17.x (develop), **Python**: >=3.14, **Frappe dependency**: >=17.0.0-dev,<18.0.0

## Common Commands

All commands run through **Bench** (Frappe's CLI tool) from the bench directory (typically `~/frappe-bench/`):

```bash
# Run all tests (parallel, 4 containers like CI)
bench --site test_site run-parallel-tests --app erpnext --total-builds 4 --build-number 1

# Run a single test module
bench --site test_site run-tests --module erpnext.accounts.doctype.sales_invoice.test_sales_invoice

# Run a single test method
bench --site test_site run-tests --module erpnext.accounts.doctype.sales_invoice.test_sales_invoice --test test_sales_invoice_with_cost_center

# Linting (pre-commit runs Ruff, Prettier, ESLint)
pre-commit run --all-files

# Run ruff only
ruff check erpnext/
ruff format erpnext/

# Build assets
bench build --app erpnext

# Start development server
bench start

# Migrate database (apply schema changes and patches)
bench --site [site_name] migrate
```

## Code Style

- **Indentation**: Tabs for Python, JavaScript, Vue, CSS/SCSS
- **Line length**: 110 characters
- **Python formatting**: Ruff (double quotes, tab indent)
- **JavaScript formatting**: Prettier v2.7.1
- **Python linting rules**: F, E, W, I, UP, B, RUF (see pyproject.toml for ignored rules)
- **JSON files**: Space indent, size 1, no final newline
- **Commits**: Conventional commit format required (e.g., `fix:`, `feat:`, `refactor:`)
- **No direct commits to `develop` branch** (enforced by pre-commit hook)

## Architecture

### DocType Pattern

Every business entity follows this structure:
```
module_name/doctype/doctype_name/
├── doctype_name.json    # Schema: fields, permissions, naming rules, links
├── doctype_name.py      # Server controller: validation, hooks, business logic
├── doctype_name.js      # Client script: form behavior, UI logic
└── test_doctype_name.py # Tests (inherit from frappe.tests.IntegrationTestCase)
```

The JSON file is the source of truth for the database schema — Frappe auto-generates tables and columns from it via `bench migrate`.

### Controller Inheritance Hierarchy

Business document controllers inherit from base controllers in `erpnext/controllers/`:

- `AccountsController` (`accounts_controller.py`) — base for all accounting documents
  - `SellingController` (`selling_controller.py`) — Sales Invoice, Sales Order, Quotation
  - `BuyingController` (`buying_controller.py`) — Purchase Invoice, Purchase Order
  - `StockController` (`stock_controller.py`) — Stock Entry, Delivery Note
- `TaxesAndTotals` (`taxes_and_totals.py`) — tax calculation logic (mixin)
- `StatusUpdater` (`status_updater.py`) — workflow status management (mixin)
- `SubcontractingController` — subcontracting operations

### Module Organization

21 business modules (listed in `erpnext/modules.txt`): Accounts, Selling, Buying, Stock, Manufacturing, CRM, Projects, Support, Assets, Setup, and others. Each contains doctypes, reports, pages, and workspaces.

### Key Files

- `erpnext/hooks.py` — App-wide configuration: boot session, notifications, scheduled tasks, regional overrides, dashboard setup
- `erpnext/__init__.py` — Version, utility functions, `@allow_regional` decorator for region-specific overrides
- `erpnext/patches.txt` — Ordered list of database migration patches (run during `bench migrate`)
- `erpnext/patches/` — Migration patch implementations

### Regional Overrides

Functions decorated with `@erpnext.allow_regional` can be overridden per country/region via `regional_overrides` in hooks. The last installed app's override takes priority.

### Test Fixtures

Tests use `frappe.tests.IntegrationTestCase`. Test data is loaded from `test_records.json` files alongside test modules. The test site (`test_site`) uses `_Test Company` as the default company.

## CI Pipeline

PRs trigger: pre-commit linters (Ruff + Prettier + ESLint), Semgrep security rules, and 4 parallel Python test containers on MariaDB. PostgreSQL tests run separately. Coverage target: 85% on patches (develop branch).
