# Developer setup — reproduce the mill demo end to end

> ⚠️ **Written 2026-09-11, partly overtaken since.** It still describes the fork on Frappe
> `develop` and the branch `feat/palm-mill-module` (merged), the repo under `samueljw/`
> (moved to `delta-anugrah/`), and seven patches (there are now eleven).
>
> **For a normal install use [`instalasi.md`](instalasi.md)** — it targets `version-16`
> and does not need the private database dump. Keep reading here only if you specifically
> need that dump, which is what this page is really about.

This is the exact path from an empty machine to the same site Jesse works on: the sawit demo
data, the Palm Mill module, Indonesian/English switching, the OER report, and the environment
fixes. Follow it top to bottom; every step has a check.

## 0. Versions (what this was built and tested against)

| Tool | Version |
|---|---|
| macOS + Homebrew (Linux works the same; notes inline) | |
| Python | 3.14.3 |
| Node / yarn | 26.0 / 1.22 |
| MariaDB | 12.2.2 |
| Redis | 8.6 |
| bench | 5.29.1 |
| frappe | `develop` @ `2231252fe8` (17 Feb 2026) |
| this app | `feat/palm-mill-module` |

```bash
brew install python@3.14 mariadb redis node yarn
pipx install frappe-bench            # or: pip install frappe-bench
```

## 1. MariaDB: one line before anything else

MariaDB 11.6+ ships `innodb_snapshot_isolation = ON`. Frappe reads a document and updates it
later in the same transaction all over the place; under snapshot isolation a concurrent update
raises error 1020, which the desk shows as **"Deadlock Occurred"**. The app relaxes this per
connection (`before_request` / `before_job` hooks), but set the server default too.

Put this under `[mysqld]` — not `[client]`, which the CLI would reject as an unknown option:

```ini
# /opt/homebrew/etc/my.cnf   (Linux: /etc/mysql/mariadb.conf.d/50-server.cnf)
[mysqld]
innodb_snapshot_isolation = OFF
```

Then `brew services restart mariadb` (Linux: `systemctl restart mariadb`), and check:

```bash
mariadb -u root -p -e "SELECT @@innodb_snapshot_isolation;"     # OFF
```

Frappe also wants `character-set-server = utf8mb4` and `collation-server = utf8mb4_unicode_ci`;
`bench new-site` will complain if they're missing.

## 2. Bench, pinned to the tested Frappe commit

```bash
bench init --frappe-branch develop --python python3.14 frappe-bench
cd frappe-bench
git -C apps/frappe checkout 2231252fe8
bench setup requirements
```

## 3. This app — it installs as `erpnext`

The package is still named `erpnext` (see README, "What differs from upstream"). Check out the
branch **before** creating or migrating any site: Frappe drops DocTypes it cannot import,
tables included, and `main` does not contain `erpnext/palm_mill`.

```bash
bench get-app https://github.com/delta-anugrah/autoerp.git
git -C apps/erpnext checkout feat/palm-mill-module
bench setup requirements
bench build --app erpnext        # also compiles erpnext/locale/*.po → .mo (migrate does NOT)
```

Check: `ls apps/erpnext/erpnext/palm_mill/doctype` lists ten DocTypes and no `harvester_premi`.

## 4. The demo data

The data is a database dump on a private release; you need collaborator access to the repo (ask
Jesse). It also contains the site encryption key and user hashes — never commit or reshare it.

```bash
gh release download sawit-data-2026-09-09-truck --repo delta-anugrah/autoerp -D /tmp/sawit

bench new-site pks.localhost --db-root-password <mariadb root pw> --admin-password admin
bench --site pks.localhost restore /tmp/sawit/*-pks_localhost-database.sql.gz --db-root-password <mariadb root pw>
bench --site pks.localhost set-config developer_mode 1
bench --site pks.localhost migrate
bench --site pks.localhost set-admin-password admin
bench --site pks.localhost clear-cache
bench use pks.localhost
```

`migrate` is where the dump becomes the current state. It syncs the shipped DocType JSON over the
dump's `custom: 1` records and runs the seven `palm_mill_*` patches in `erpnext/patches.txt`:

| Patch | What it does to the restored data |
|---|---|
| `setup_palm_mill` | custom fields, roles, settings defaults, plate / status / back-link backfills |
| `palm_mill_navigation` | Home hidden, every user's default workspace = Pabrik Kelapa Sawit, operator read on masters |
| `palm_mill_desktop_layout` | deletes saved Desktop Layout snapshots (they freeze the launcher) |
| `palm_mill_language` | site language `id`, un-pins users from `en-US`, disables ERPNext's unused seed warehouses / item groups |
| `palm_mill_audit` | removes Harvester Premi (record and table) |
| `palm_mill_oer` | seeds CPO / kernel items in Palm Mill Settings, drops Batch `custom_oer` |
| `palm_mill_ffb_source` | renames Inti → Internal and merges Plasma + Pihak Ketiga → External across every table |

On Linux add `127.0.0.1 pks.localhost` to `/etc/hosts`; macOS resolves `*.localhost` itself.

### 4b. One thing the patches don't do: the demo lab records

The dump has 146 Quality Inspections (all wrongly marked Rejected) and two templates. Lab was
removed from the mill layer; this is demo data, so it's deleted by hand, not by a patch:

```bash
bench --site pks.localhost console
```

```python
for n in frappe.get_all("Quality Inspection", pluck="name"):
    doc = frappe.get_doc("Quality Inspection", n)
    if doc.docstatus == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()                       # on_cancel clears the link on the stock-entry rows
    frappe.delete_doc("Quality Inspection", n, force=True, ignore_permissions=True)
for t in frappe.get_all("Quality Inspection Template", pluck="name"):
    frappe.delete_doc("Quality Inspection Template", t, force=True, ignore_permissions=True)
frappe.db.commit()
```

## 5. Run it and check

```bash
bench start          # http://pks.localhost:8000 — Administrator / admin
```

`bench start` also launches the worker; without one, accounting dimensions never reach GL Entry.

The repo root has a `Makefile` wrapping this and the other day-to-day commands
(`make up`, `make stop`, `make status`, `make key-show`); `make help` lists them. It drives
the bench at `~/frappe-bench` — override with `make up BENCH=... SITE=...`. `make up` refuses
to start a second bench: the redis ports are already bound, one child dies, and honcho then
stops the whole group, which on screen looks like the first bench crashed when it is in fact
still serving.

Landing page (in Indonesian — switch to English from the user menu, bottom-left): the
**Pabrik Kelapa Sawit** dashboard with seven cards (FFB received ≈ 46.5 M kg, tickets 3,848,
Avg Daily OER ≈ 21.4) and five charts, then a sidebar of five collapsed groups.

Without a browser:

```bash
bench --site pks.localhost console
```

```python
frappe.db.count("Weighbridge Ticket")                              # 3848
frappe.get_all("Sumber TBS", pluck="name")                         # ['External', 'Internal']
frappe.db.exists("DocType", "Harvester Premi")                     # None
frappe.db.count("Quality Inspection")                              # 0
frappe.db.get_single_value("System Settings", "language")          # 'id'
frappe.db.get_single_value("Palm Mill Settings", "cpo_item")       # 'CPO'
from frappe.desk.query_report import run
r = run("Oil Extraction Rate", filters={"company": "PT Sawit Rambang Lestari",
        "from_date": "2026-05-01", "to_date": "2026-07-27"}, ignore_prepared_report=True)
len(r["result"]), r["report_summary"][0]["value"]                   # (73, 21.43)
frappe._("Home", lang="id"), frappe._("Pihak Ketiga", lang="en")   # ('Beranda', 'Pihak Ketiga')
```

(That last `Pihak Ketiga` is correct: the value no longer exists, so nothing translates it.)

## 6. Exercising the AutoGrade side

Nothing outside this repo calls the API yet. To play AutoGrade:

```bash
bench --site pks.localhost execute erpnext.palm_mill.setup.create_integration_user \
  --kwargs '{"email": "autograde@pks.local", "full_name": "AutoGrade"}'
# prints api_key / api_secret
```

Then the three `upsert_visit` sends (gate, grading, departed) documented in
`docs/autograde-integration.md` §6, with `Authorization: token <key>:<secret>`. A visit for an
unknown plate creates a Truck with no owner; finalisation runs as soon as weight and grading are
both in, or from the **Receive Stock** button on a hand-typed ticket.

## 7. Rules that will bite you (each one did)

- **Never `migrate` a site on a checkout without `erpnext/palm_mill`.** Frappe deletes the
  DocTypes it can't import — and their tables.
- **Editing a shipped JSON record does nothing until you bump its `modified`.** Migrate skips
  files older than the database row. `Workspace.is_hidden` never syncs from file at all
  (set it in a patch).
- **`bench migrate` does not compile translations.** After touching `erpnext/locale/*.po`:
  `bench compile-po-to-mo --app erpnext --force` then `bench --site pks.localhost clear-cache`
  (per-user boot caches the whole translation dict). Author strings in English in source;
  never hand-add msgids to a `.po` — `bench generate-pot-file` then `update-po-files`.
  Frappe-owned strings can't be overridden from ERPNext's catalog; they go in
  `erpnext/fixtures/translation.json` (README → Translations).
- **Workspace content blocks match widgets by label.** Give a card, chart or shortcut a
  `label` and the block's `*_name` must equal it, or the widget silently vanishes.
- **A saved Desktop Layout freezes the launcher.** Right-click → Reset Layout, or delete the row.
- **Script report packages are named by `frappe.scrub(report name)`**, parentheses included —
  keep report names to plain words.
- **Browser caches SVG icons for 12 hours** (`/assets/` is `max-age=43200`). Open the icon URL
  and hard-reload it after changing one.
- The site has `developer_mode 1`: **Edit Sidebar** in the UI writes straight back to
  `erpnext/workspace_sidebar/*.json`. Useful, and easy to commit by accident.

## 8. Day to day

```bash
bench start                                            # web, worker, scheduler, redis
bench --site pks.localhost migrate                     # after pulling schema / patch changes
bench --site pks.localhost clear-cache                 # after any JSON / translation change
bench build --app erpnext                              # after JS or .po changes
ruff check erpnext/palm_mill && ruff format erpnext/palm_mill
apps/frappe/node_modules/.bin/prettier --check 'erpnext/public/js/palm_mill/**/*.js'
```

A note the rest of this page predates: **`erpnext/palm_mill/demo.py` builds the same shape of
data from code** (`bench --site <site> execute erpnext.palm_mill.demo.seed`), so the private dump
is no longer the only way to get a populated site — and unlike the dump it can be handed to a
client, because it carries no encryption key and no real password hashes. See
[`instalasi.md`](instalasi.md) §4a.

Tests are written (`erpnext/palm_mill/test_*.py`, `doctype/*/test_*.py`) but need a test site:
`bench new-site test_site --admin-password admin && bench --site test_site install-app erpnext`,
then `bench --site test_site run-tests --module erpnext.palm_mill.test_api`.
