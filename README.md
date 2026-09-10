# AutoERP

A fork of [ERPNext](https://github.com/frappe/erpnext) (develop line, `v16.0.0-beta.1` + ~1500 commits, Feb 2026)
rebranded as **AutoERP**. It is the ERP app behind the PalmGrade / PKS palm-oil-mill demo.

Internally the app is still called `erpnext` (`app_name = "erpnext"` in `erpnext/hooks.py`), so it
installs into `apps/erpnext` and is installed on a site as `erpnext`. Only `app_title`, logos and desk
icons say AutoERP. This is deliberate — it keeps upstream merges and every `frappe.get_app("erpnext")`
call working.

## What differs from upstream

| Area | Change |
|---|---|
| Branding | `app_title`/`app_publisher` = AutoERP, AutoERP logo + favicon (`erpnext/public/images/autoerp-*.svg`), desk icons, footer, help links, "AutoERP Settings" workspace replacing "ERPNext Settings" |
| Tweaks | small edits to Accounts/Buying/Stock settings doctypes, `stock_ledger.py`, `reorder_item.py`, Production Plan, Company, and the CRM/Support workspaces |

Everything else is upstream ERPNext. See `git log` — each of the above is its own commit.

## Tested environment

| Tool | Version used |
|---|---|
| Python | 3.14 (`pyproject.toml` requires `>=3.14`) |
| Node / yarn | 26.x / 1.22 |
| MariaDB | 12.2 (10.6+ should work) |
| Redis | 8.x |
| bench | 5.29 |
| frappe | `develop` @ commit `2231252` |

## Run it from scratch

```bash
# 1. bench with frappe develop, pinned to the commit this fork is tested against
bench init --frappe-branch develop --python python3.14 frappe-bench
cd frappe-bench
git -C apps/frappe checkout 2231252
bench setup requirements

# 2. this app — note it lands in apps/erpnext, not apps/autoerp
bench get-app https://github.com/samueljw/autoerp.git

# 3. a site
bench new-site autoerp.localhost --db-root-password <mariadb root pw> --admin-password admin
bench --site autoerp.localhost install-app erpnext
bench use autoerp.localhost
bench start          # http://localhost:8000
```

Frappe's bench needs redis running on the ports in `config/redis_*.conf` (13000/11000/12000) —
`bench start` launches them; if you run `bench serve` by hand, start them yourself:
`redis-server config/redis_cache.conf --daemonize yes` (and the same for `redis_queue.conf`), plus
`bench --site <site> worker` so background jobs (reposting, accounting-dimension propagation) run.

## Getting the palm-oil-mill demo data

The sawit demo (company *PT Sawit Rambang Lestari*, 3,848 weighbridge tickets, ~7.4k transactions
May–Jul 2026, 58 trucks linked to their TBS supplier) is **data, not code**. It lives in a site's MariaDB database, so a fresh install of
this app is empty. To get it, restore the database dump attached to the
[`sawit-data-2026-09-09-truck`](https://github.com/samueljw/autoerp/releases/tag/sawit-data-2026-09-09-truck)
release. The dump is tied to this app at commit `915bcc2` and frappe at `2231252` — use the bench
from the section above.

Follow these steps top to bottom from the bench directory (`frappe-bench/`):

```bash
# 1. download the dump (needs collaborator access to this repo; or grab it from the Releases page)
gh release download sawit-data-2026-09-09-truck --repo samueljw/autoerp -D /tmp/sawit

# 2. a fresh site to restore into (install-app is NOT needed — the dump already contains the app)
bench new-site pks.localhost --db-root-password <mariadb root pw> --admin-password admin

# 3. restore the dump over it, then align the schema with the installed code
bench --site pks.localhost restore /tmp/sawit/*-pks_localhost-database.sql.gz --db-root-password <mariadb root pw>
bench --site pks.localhost migrate

# 4. the dump carries the old Administrator hash — set your own
bench --site pks.localhost set-admin-password admin

# 5. run it
bench use pks.localhost
bench start                       # http://pks.localhost:8000  (login: Administrator / admin)
```

On Linux add `127.0.0.1 pks.localhost` to `/etc/hosts`; macOS resolves `*.localhost` on its own.
A worker must be running (`bench start` launches one) or accounting dimensions never reach GL Entry.

**What you should see.** One company, PT Sawit Rambang Lestari (abbr `S`). A **Pabrik Kelapa Sawit** workspace on the
desk, Weighbridge Ticket list with ~3.8k rows, Purchase Receipts (~1.8k), and a Stock Ledger for
TBS / CPO / PK.
Sanity check without the browser:

```bash
bench --site pks.localhost execute frappe.get_all --kwargs '{"doctype":"Company","fields":["name","abbr"]}'
# [{"name": "PT Sawit Rambang Lestari", "abbr": "S"}]
```

Things to know:

- **Fictional data.** A 45 t/h mill with a 5,000 ha nucleus estate, generated deterministically.
  Nothing here is any real mill's operating result; do not present it otherwise.
- **The dump contains credentials** (user password hashes, the site encryption key). It is on a
  private release for that reason — do not commit it or reshare it outside this repo's collaborators.
- **Custom DocTypes travel inside the dump.** Weighbridge Ticket, Blok, Kebun, Divisi, Sumber TBS, Sertifikasi,
  Harvester Premi, the batch-genealogy field and the Accounting Dimensions are `custom: 1` records in the database, not files in this repo.
- **Don't restore onto a much newer app.** Restore first, then `migrate`. If you merge a lot of
  upstream ERPNext, take a fresh backup of your working site before migrating it.
- The dataset was generated by the private `delta-anugrah/palmgrade-erp-demo` pipeline. If it ever
  needs to be rebuilt from scratch rather than restored, ask Jesse.

## Keeping up with upstream ERPNext

```bash
git remote add upstream https://github.com/frappe/erpnext.git   # once
git fetch upstream
git merge upstream/develop
```

Expect conflicts in the branding files listed above; keep ours.

## Working on it

Clone this repo (collaborator access is enough), branch off `main`, and open a PR back here. `CLAUDE.md` has notes for AI-assisted work.

## Palm Mill module

`erpnext/palm_mill` is the palm-oil-mill module of this fork: the sawit DocTypes (Weighbridge
Ticket, Weighbridge Grading, Truck, Blok, Kebun, Divisi, Sumber TBS, Sertifikasi, Harvester Premi),
Palm Mill Settings, the "Pabrik Kelapa Sawit" workspace with its cards and charts, the ticket
finalisation logic, and the inbound endpoints for AutoGrade, the one system that talks to the ERP
(`erpnext.palm_mill.api.upsert_truck` and `upsert_visit`; the scale program feeds AutoGrade). The design is
in `docs/autograde-integration.md`.

Rules that keep a site healthy:

- **Never run `bench migrate` on a checkout without `erpnext/palm_mill`.** Frappe deletes any
  standard DocType whose controller it cannot import, and that drops the table with it.
- After changing `modules.txt`, run `bench --site <site> clear-cache` before `migrate` on every site;
  the module map is cached per site.
- Integration users are created with `bench --site <site> execute
  erpnext.palm_mill.setup.create_integration_user --kwargs '{"email": "...", "full_name": "..."}'`.
  They hold Palm Mill Integration, Purchase User and Stock User; the key and secret are printed once.
- Tests (`bench --site test_site run-tests --module erpnext.palm_mill.test_api` and the DocType
  tests) need a dedicated `test_site` with `allow_tests`. Never run them on a site with real data:
  ERPNext's test setup deletes transactions.
- Editing these DocTypes through the UI requires `developer_mode` on the site (it is on for
  `pks.localhost`); Frappe then re-exports the JSON into the module.

