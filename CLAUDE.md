# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoERP is a whitelabeled fork of ERPNext, an open-source ERP system built on the **Frappe Framework** (Python + JavaScript). The upstream package name is `erpnext` and all Python module paths use `erpnext.*`. It uses a DocType-driven architecture where business entities are defined as JSON schemas with Python controllers and optional JavaScript client scripts.

**Version**: ERPNext `version-16` (the fork moved off `develop` on 2026-09-16), **Python**: >=3.14.

⚠️ **The app installs as `erpnext`, not `autoerp`.** Bench puts it in `apps/erpnext`; only `app_title`, logos and desk icons say AutoERP. This is deliberate — it keeps upstream merges and every `frappe.get_app("erpnext")` call working.

### The part that is ours: `erpnext/palm_mill`

Everything sawit-specific lives in one module. It is why this fork exists, and it is what almost every task here touches:

- **11 DocTypes** — `Weighbridge Ticket` (the core, submittable), `Weighbridge Grading`, `Truck`, `Palm Mill Settings` (single), `Palm Mill Grading Rule`, `AutoGrade Operator`, and the estate masters `Kebun` / `Divisi` / `Blok` / `Sertifikasi` / `Sumber TBS`.
- **2 inbound endpoints** for AutoGrade, the only external system that talks to this one: `erpnext.palm_mill.api.upsert_truck` and `upsert_visit`.
- **Ticket finalisation** — `weighbridge_ticket.py` holds `try_finalize`, `create_stock_documents` (Purchase Receipt for bought fruit, Stock Entry for the estate's own), the 15-minute `finalize_due_tickets` scheduler, and the stock-document cancel hook.
- **1 report** (Oil Extraction Rate), **1 workspace** (Pabrik Kelapa Sawit), **11 patches** (`palm_mill_*` in `erpnext/patches.txt`).
- `demo.py` seeds a demo site from code, so the private database dump is not needed.

**Read `docs/README.md` before working on any of it.** The design rationale is in `docs/autograde-integration.md`; where that document and the code disagree, **the code wins**.

### Rules that have already cost time

- **Never run `bench migrate` on a checkout without `erpnext/palm_mill`.** Frappe deletes any standard DocType whose controller it cannot import — and drops the table with it. Silently.
- **Never re-run `create_integration_user` just to read the credentials** — it rotates `api_secret` and every AutoGrade still holding the old one gets 401. Use `make key-show`.
- **Never run tests on a site with real data** — ERPNext's test setup deletes transactions.
- `bench migrate` does **not** compile translations; `bench compile-po-to-mo --app erpnext --force` then `clear-cache`.
- After changing `modules.txt`, `clear-cache` before `migrate` on every site.
- A new site never runs patches (`install_app` marks them done), so site policy set only in a patch will not reach it.

The full list is `docs/gotchas.md`.

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
- **Branch flow**: feature branch → PR to `staging` → release PR `staging` → `main` (a **merge commit**, never a squash). No direct commits to `main`. PR titles and bodies are written in English; commits and docs may be Indonesian.

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

22 business modules (listed in `erpnext/modules.txt`): Accounts, Selling, Buying, Stock, Manufacturing, CRM, Projects, Support, Assets, Setup, **Palm Mill** (ours), and others. Each contains doctypes, reports, pages, and workspaces.

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

PRs trigger: pre-commit linters (Ruff + Prettier + ESLint), Semgrep security rules, and 4 parallel Python test containers on MariaDB. PostgreSQL tests run separately.

Two failures are known and are **not** your change:

- **Patch Test is always red** — `patch.yml` fetches `$GITHUB_BASE_REF` from `frappe/frappe`, and the branches `staging` / `main` do not exist there. Red since PR #5.
- `.github/helper/install.sh` installs `payments --branch develop` while this app is on `version-16`.

Tracked as E6 and E7 in `sawit/docs/TODO-AUTOGRADE-AUTOERP.md`.

## Palm Mill tests

```bash
bench new-site test_site --admin-password admin
bench --site test_site install-app erpnext
bench --site test_site run-tests --module erpnext.palm_mill.test_api
```

48 tests across `test_api.py` (11), `test_qr_card.py` (6), `weighbridge_ticket` (8), `autograde_operator` (18), `truck` (5). `test_fixtures.py` pins the worked example: net 9,160 kg → 11.55 % potongan → 8,102 kg payable.
