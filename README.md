# AutoERP

A fork of [ERPNext](https://github.com/frappe/erpnext) (develop line, `v16.0.0-beta.1` + ~1500 commits, Feb 2026)
rebranded as **AutoERP**. It is the ERP app behind the PalmGrade / PKS palm-oil-mill demo and the
LPG valve reconciliation build.

Internally the app is still called `erpnext` (`app_name = "erpnext"` in `erpnext/hooks.py`), so it
installs into `apps/erpnext` and is installed on a site as `erpnext`. Only `app_title`, logos and desk
icons say AutoERP. This is deliberate — it keeps upstream merges and every `frappe.get_app("erpnext")`
call working.

## What differs from upstream

| Area | Change |
|---|---|
| Branding | `app_title`/`app_publisher` = AutoERP, AutoERP logo + favicon (`erpnext/public/images/autoerp-*.svg`), desk icons, footer, help links, "AutoERP Settings" workspace replacing "ERPNext Settings" |
| LPG build | `erpnext/stock/workspace/rekonsiliasi_valve_lpg/` — Rekonsiliasi Valve LPG workspace (ships to every site running this app) |
| Tjokro demo | `erpnext/setup_tjokro_demo.py` — seeding script for the Nexio/Tjokro inventory quotation demo |
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
bench get-app https://github.com/delta-anugrah/autoerp.git

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

The sawit demo (company *PT Sawit Rambang Lestari*, ~7.5k documents) lives in the database, not in
this repo. Two ways to get it:

1. **Restore a backup** handed over out-of-band:
   `bench --site <site> restore /path/to/<timestamp>-pks_localhost-database.sql.gz`
   Backups contain user password hashes and API keys — **do not commit them anywhere**.
2. **Rebuild it** with the seeding pipeline in
   [`delta-anugrah/palmgrade-erp-demo`](https://github.com/delta-anugrah/palmgrade-erp-demo)
   (`pks_00_reset.py` … `pks_08_workspace.py`, run against a fresh site via its REST API).

## Keeping up with upstream ERPNext

```bash
git remote add upstream https://github.com/frappe/erpnext.git   # once
git fetch upstream
git merge upstream/develop
```

Expect conflicts in the branding files listed above; keep ours.

## Working on it

Clone this repo (collaborator access is enough — the org currently doesn't allow forking private
repos), branch off `main`, and open a PR back here. `CLAUDE.md` has notes for AI-assisted work.
