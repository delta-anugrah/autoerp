# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Demo data for showing AutoERP to a client, on a laptop or on a server.

This replaces the private database dump (`sawit-data-2026-09-09-truck`) for every use
that is not "reproduce Jesse's exact site". The dump carries the site encryption key and
real user hashes, so it can never be handed to a client or installed on their machine;
this module can, because it builds the same *shape* of data from code.

    bench --site <site> execute erpnext.palm_mill.demo.seed
    bench --site <site> execute erpnext.palm_mill.demo.reset   # wipe, then seed again

Idempotent: re-running adds nothing. Every record it creates is tagged (company
`DEMO_COMPANY`, plates from `PLATES`, tickets carrying `autograde_visit_id` prefixed
`DEMO-`), which is what lets `reset` find its own rows and leave everything else alone.

Names and numbers mirror the demo site the module was designed against: estate
Sungai Rambang, KUD plasma suppliers, agen CVs, TBS at Rp 2,850/kg. They are invented,
but invented in the same shape as the real mill, so a client recognises the screens.

**Not for a production site.** `seed` refuses to run unless the site has
`demo_mode: 1` in site_config, or `force=1` is passed.
"""

import datetime
import random

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from erpnext.palm_mill.setup import OPERATOR_ROLE
from erpnext.palm_mill.utils import relax_snapshot_isolation

DEMO_COMPANY = "PT Sawit Rambang Lestari"
ABBR = "SRL"
CURRENCY = "IDR"
COUNTRY = "Indonesia"

TBS_ITEM = "TBS"
TBS_PRICE = 2850.0
PRICE_LIST = "Standard Buying"

KEBUN = ("Sungai Rambang", "Air Batu")
DIVISI = ("I", "II", "III", "IV")
SERTIFIKASI = ("ISPO", "RSPO", "Non-sertifikasi")

# Plasma cooperatives and agent traders: the two kinds of External supplier a mill buys
# from. Internal loads carry no supplier at all — the estate is the company itself.
PLASMA = (
	"KUD Tani Jaya",
	"KUD Sumber Makmur",
	"KUD Rambang Sejahtera",
	"KUD Karya Bersama",
)
AGEN = (
	"CV Sawit Berkah",
	"CV Mitra Sawit Lestari",
	"H. Ahmad Rasyid (Agen)",
)

# (plate, supplier or None for the estate's own truck, vehicle class). BE is Lampung,
# BG South Sumatra — the two areas the mill actually sees.
PLATES = (
	("BE 6311 TSA", "KUD Sumber Makmur", "Dump Truck"),
	("BE 1825 TSC", "KUD Tani Jaya", "Dump Truck"),
	("BE 8605 TSD", "KUD Rambang Sejahtera", "Colt Diesel"),
	("BE 9698 TSD", "KUD Karya Bersama", "Dump Truck"),
	("BE 1473 TSE", "CV Sawit Berkah", "Tronton"),
	("BE 5585 TSE", "CV Mitra Sawit Lestari", "Tronton"),
	("BE 9874 TSE", "H. Ahmad Rasyid (Agen)", "Colt Diesel"),
	("BG 9911 ZA", None, "Dump Truck"),
	("BG 7742 ZB", None, "Dump Truck"),
	("BG 3308 ZC", None, "Colt Diesel"),
)

DRIVERS = (
	"Suparman",
	"Joko Widodo",
	"Ahmad Fauzi",
	"Budi Santoso",
	"Rudi Hartono",
	"Slamet Riyadi",
	"Bambang Sutrisno",
	"Eko Prasetyo",
)

# Desk logins for the showcase, one per role the client will ask about. Password is the
# same for all three so nobody fumbles a demo; this is why the module refuses to run on
# a site that has not declared itself a demo.
DEMO_PASSWORD = "sawit2026"
DESK_USERS = (
	("krani@demo.autoerp.test", "Krani", "Timbang", (OPERATOR_ROLE,)),
	("mandor@demo.autoerp.test", "Mandor", "Kebun", (OPERATOR_ROLE, "Stock User")),
	(
		"manajer@demo.autoerp.test",
		"Manajer",
		"Pabrik",
		(OPERATOR_ROLE, "Stock User", "Stock Manager", "Purchase User", "Purchase Manager", "Accounts User"),
	),
)

# The console accounts AutoGrade pulls down (AutoGrade Operator DocType). Kept in step
# with the seeder on the AutoGrade side so both demos show the same two people.
CONSOLE_USERS = (
	("operator@demo.autoerp.test", "Operator Line", "operator"),
	("support@demo.autoerp.test", "Support AutoGrade", "support"),
)

DAYS = 7  # days of history, ending today
# The TBS price is backdated well past the longest history anyone would seed, so
# `seed(days=60)` still prices every ticket.
PRICE_VALID_FROM_DAYS = 400
VISITS_PER_DAY = (6, 11)  # a mill day is uneven; this is the range
VISIT_PREFIX = "DEMO-"

# Grading shares drawn per visit. Mentah is what the line rejects; Tangkai Panjang rides
# along with accepted fruit. Matang is the remainder, so these two are all that is drawn.
MENTAH_RANGE = (2.0, 14.0)
TANGKAI_RANGE = (1.0, 8.0)

SEED = 20260917  # fixed, so two machines seeded from scratch show identical numbers

# Mentah is 0 on purpose, unlike the module default of 60. Rejected bunches go back on the
# truck, so the weigh-out tare has already excluded them; charging Mentah again as a price
# deduction would penalise the supplier twice (docs/autograde-integration.md §8). The demo
# shows the go-live setting, not the pre-rejection one.
DEMO_GRADING_RULES = (("Mentah", 0), ("Lewat Matang", 15), ("Tangkai Panjang", 100))


# --------------------------------------------------------------------------- guard
def _check_allowed(force=0):
	if frappe.utils.cint(force):
		return
	if not frappe.utils.cint(frappe.conf.get("demo_mode")):
		frappe.throw(
			"This site is not marked as a demo. Either\n"
			"  bench --site {0} set-config demo_mode 1\n"
			"or pass force=1 if you are certain:\n"
			"  bench --site {0} execute erpnext.palm_mill.demo.seed --kwargs \"{{'force': 1}}\"".format(
				frappe.local.site
			)
		)


# ---------------------------------------------------------------------------- seed
def seed(force=0, days=DAYS, quiet=0):
	"""Build the whole demo: company, masters, users, and `days` of truck visits."""
	_check_allowed(force)
	relax_snapshot_isolation()
	frappe.flags.in_demo = True
	drain_queue()

	steps = (
		("erpnext fixtures", make_fixtures),
		("fiscal years", make_fiscal_years),
		("company", make_company),
		("currency", set_defaults_currency),
		("masters", make_masters),
		("suppliers", make_suppliers),
		("item + price", make_item_and_price),
		("settings", configure_settings),
		("trucks", make_trucks),
		("desk users", make_desk_users),
		("console users", make_console_users),
	)
	for label, fn in steps:
		fn()
		# Per step, not one transaction at the end: a seeder that dies half way should
		# leave what it already built, and the next run picks up from there (it is
		# idempotent).
		# nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
		frappe.db.commit()
		_say(quiet, f"  {label}")

	made = make_visits(days=frappe.utils.cint(days) or DAYS)
	# nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
	frappe.db.commit()
	_say(quiet, f"  visits: {made} tickets")
	_say(quiet, "")
	_say(quiet, summary())
	return {"company": DEMO_COMPANY, "tickets": made}


def drain_queue():
	"""Empty this site's background queues before seeding.

	Every submitted document enqueues follow-up work. Seeding a week of visits queues
	hundreds of jobs, and if no worker is running — `bench execute` does not start one,
	and neither does a laptop where nobody ran `bench start` — the queue fills up and
	Frappe refuses further saves with `QueueOverloaded` partway through the run, leaving
	a half-seeded site.

	Dropping them is safe here: they are follow-ups for demo documents this same run
	created, and nothing is waiting on their results.
	"""
	from frappe.utils.background_jobs import get_queues

	site = frappe.local.site
	for queue in get_queues():
		for job in queue.jobs:
			if job.kwargs.get("site") == site:
				job.delete()


def _say(quiet, msg):
	if not frappe.utils.cint(quiet):
		print(msg)


def make_fixtures():
	"""ERPNext's preset records — UOMs, party types, warehouse types, item groups.

	Normally the setup wizard installs these, and a site created with
	`bench new-site --install-app erpnext` never runs the wizard. Without them company
	creation dies on `Could not find Warehouse Type: Transit`, because the default
	warehouse set includes Goods In Transit. Safe on a site that has run the wizard:
	`install` skips records that already exist.
	"""
	from erpnext.setup.setup_wizard.operations.install_fixtures import install

	if frappe.db.exists("Warehouse Type", "Transit"):
		return
	install(COUNTRY)


def make_fiscal_years(days=DAYS):
	"""A Fiscal Year covering the demo history, or the receipts cannot post to the GL.

	The wizard creates these from the country's calendar; `--install-app` does not. Every
	year the history touches gets one, so seeding across a new-year boundary still works.
	"""
	years = {getdate(add_days(nowdate(), -back)).year for back in (0, frappe.utils.cint(days))}
	for year in sorted(years):
		name = str(year)
		if frappe.db.exists("Fiscal Year", name) or frappe.db.exists(
			"Fiscal Year", {"year_start_date": f"{year}-01-01"}
		):
			continue
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": name,
				"year_start_date": f"{year}-01-01",
				"year_end_date": f"{year}-12-31",
			}
		).insert(ignore_permissions=True)


def make_company():
	if frappe.db.exists("Company", DEMO_COMPANY):
		return
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": DEMO_COMPANY,
			"abbr": ABBR,
			"default_currency": CURRENCY,
			"country": COUNTRY,
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": "Standard",
		}
	).insert(ignore_permissions=True)
	frappe.defaults.set_global_default("company", DEMO_COMPANY)


def set_defaults_currency():
	"""The global default currency, and the country the wizard would have set.

	A fresh site's global default is INR. The company and the price list are both IDR, but
	the supplier's billing currency comes from this global, so every Purchase Receipt was
	raised in INR and multiplied by the INR->IDR rate: correct `amount`, `base_amount`
	184x too big, and Stock In Hand in the hundreds of billions. Nothing warns about it.
	"""
	frappe.db.set_default("currency", CURRENCY)
	frappe.db.set_default("country", COUNTRY)
	if not frappe.db.get_single_value("Global Defaults", "default_currency"):
		frappe.db.set_single_value("Global Defaults", "default_currency", CURRENCY)
	currency = frappe.get_doc("Currency", CURRENCY)
	if not currency.enabled:
		currency.enabled = 1
		currency.save(ignore_permissions=True)
	frappe.clear_cache()


def make_masters():
	"""Estate geography: kebun, divisi, sertifikasi, and the blocks fruit comes from."""
	for doctype, titles in (
		("Sumber TBS", ("Internal", "External")),
		("Kebun", KEBUN),
		("Divisi", DIVISI),
		("Sertifikasi", SERTIFIKASI),
	):
		for title in titles:
			if not frappe.db.exists(doctype, title):
				frappe.get_doc({"doctype": doctype, "title": title}).insert(ignore_permissions=True)

	rng = random.Random(SEED)
	# Twelve blocks per estate, spread over the divisions. Enough to make the block filter
	# on the ticket list worth clicking, few enough to read on one screen.
	for kebun in KEBUN:
		prefix = "A" if kebun == KEBUN[0] else "B"
		for n in range(1, 13):
			code = f"{prefix}{n:02d}"
			if frappe.db.exists("Blok", code):
				continue
			frappe.get_doc(
				{
					"doctype": "Blok",
					"blok_code": code,
					"kebun": kebun,
					"divisi": DIVISI[(n - 1) % len(DIVISI)],
					"luas_ha": 28.0,
					"tahun_tanam": rng.choice(range(2009, 2019)),
					"jumlah_pokok": 3808,
					"sertifikasi": "RSPO" if n <= 6 else "ISPO",
				}
			).insert(ignore_permissions=True)


def make_suppliers():
	for group in ("Plasma", "Agen TBS"):
		if not frappe.db.exists("Supplier Group", group):
			frappe.get_doc(
				{
					"doctype": "Supplier Group",
					"supplier_group_name": group,
					"parent_supplier_group": "All Supplier Groups",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)

	for names, group in ((PLASMA, "Plasma"), (AGEN, "Agen TBS")):
		for name in names:
			if not frappe.db.exists("Supplier", name):
				frappe.get_doc(
					{
						"doctype": "Supplier",
						"supplier_name": name,
						"supplier_group": group,
						"supplier_type": "Company",
						"country": COUNTRY,
					}
				).insert(ignore_permissions=True)


def make_item_and_price():
	# `Standard Buying` is an `install_defaults` record, not an `install_fixtures` one, and
	# that function wants the wizard's whole args object. One price list is cheaper to
	# create here than to fake the wizard for.
	if not frappe.db.exists("Price List", PRICE_LIST):
		frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": PRICE_LIST,
				"currency": CURRENCY,
				"buying": 1,
				"selling": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Item", TBS_ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": TBS_ITEM,
				"item_name": "Tandan Buah Segar",
				"item_group": _item_group(),
				"stock_uom": "Kg",
				"is_stock_item": 1,
				"is_purchase_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 0,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Item Price", {"item_code": TBS_ITEM, "price_list": PRICE_LIST}):
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": TBS_ITEM,
				"price_list": PRICE_LIST,
				"price_list_rate": TBS_PRICE,
				# `valid_from` defaults to today, and the ticket prices itself on its own
				# date (`get_price` passes `transaction_date`). Without backdating this,
				# every historical ticket finds no price and never finalises — it just
				# leaves "no buying Item Price" in the Error Log.
				"valid_from": add_days(nowdate(), -(PRICE_VALID_FROM_DAYS)),
			}
		).insert(ignore_permissions=True)


def _item_group():
	for group in ("Raw Material", "All Item Groups"):
		if frappe.db.exists("Item Group", group):
			return group
	return frappe.db.get_value("Item Group", {"is_group": 0}, "name")


def configure_settings():
	"""Point Palm Mill Settings at the demo company's own records.

	Without a warehouse and cost centre the ticket finalises but cannot create its
	Purchase Receipt, which is exactly the screen the demo is for.
	"""
	# TBS is batch-tracked (one daily batch per mill day), and the ticket's receipt builds a
	# Serial and Batch Bundle for it. ERPNext refuses to make one unless this is on, and the
	# wizard does not set it either.
	frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)

	settings = frappe.get_single("Palm Mill Settings")
	warehouse = _warehouse()
	settings.update(
		{
			"tbs_item": TBS_ITEM,
			"buying_price_list": PRICE_LIST,
			"tbs_warehouse": warehouse,
			"purchase_cost_center": frappe.db.get_value("Company", DEMO_COMPANY, "cost_center"),
			"inti_expense_account": frappe.db.get_value("Company", DEMO_COMPANY, "stock_adjustment_account"),
			# Rejected bunches leave with the truck, so the weighing has already excluded
			# them; charging Mentah again would penalise the supplier twice
			# (docs/autograde-integration.md §8). Demo shows the go-live setting.
			"create_stock_documents_on_submit": 1,
		}
	)
	# Rewritten, not just filled in when empty: `after_install` has already seeded the
	# module defaults, which carry Mentah 60 from before the line returned rejects.
	settings.grading_rules = []
	for kriteria, pct in DEMO_GRADING_RULES:
		settings.append("grading_rules", {"kriteria": kriteria, "deduction_pct": pct})
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


def _warehouse():
	for name in (f"Stores - {ABBR}", f"All Warehouses - {ABBR}"):
		if frappe.db.exists("Warehouse", name):
			return name
	return frappe.db.get_value("Warehouse", {"company": DEMO_COMPANY, "is_group": 0}, "name")


def make_trucks():
	for plate, supplier, vehicle_class in PLATES:
		if frappe.db.exists("Truck", plate):
			continue
		frappe.get_doc(
			{
				"doctype": "Truck",
				"plate_number": plate,
				"supplier": supplier,
				"vehicle_class": vehicle_class,
				"source": "Manual",
			}
		).insert(ignore_permissions=True)


def make_desk_users():
	for email, first, last, roles in DESK_USERS:
		if frappe.db.exists("User", email):
			continue
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first,
				"last_name": last,
				"user_type": "System User",
				"send_welcome_email": 0,
				"language": "id",
				"roles": [{"role": r} for r in roles if frappe.db.exists("Role", r)],
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.new_password = DEMO_PASSWORD
		user.save(ignore_permissions=True)


def make_console_users():
	"""The AutoGrade console accounts, so the mill PC pulls operators down from here."""
	if not frappe.db.exists("DocType", "AutoGrade Operator"):
		return
	for email, full_name, role in CONSOLE_USERS:
		if frappe.db.exists("AutoGrade Operator", email):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "AutoGrade Operator",
				"email": email,
				"full_name": full_name,
				"role": role,
				"active": 1,
			}
		)
		doc.new_password = DEMO_PASSWORD
		doc.insert(ignore_permissions=True)


# -------------------------------------------------------------------------- visits
def make_visits(days=DAYS):
	"""One Weighbridge Ticket per truck visit, through the real controller.

	Nothing is written straight to the table: each ticket is saved and finalised the same
	way `upsert_visit` does it, so potongan, price, Purchase Receipt and Stock Entry are
	all produced by the code the client is being shown — not faked alongside it.
	"""
	trucks = [p for p, _s, _v in PLATES]
	blocks = frappe.get_all("Blok", pluck="name", order_by="name")
	made = 0

	for back in range(days - 1, -1, -1):
		date = getdate(add_days(nowdate(), -back))
		# Once per day of history, not just at the start: a week of visits enqueues more
		# than the 500-job ceiling on its own, so a single drain up front is not enough.
		drain_queue()
		count = random.Random(f"{SEED}:{date:%Y%m%d}").randint(*VISITS_PER_DAY)
		for i in range(count):
			visit_id = f"{VISIT_PREFIX}{date:%Y%m%d}-{i:03d}"
			if frappe.db.exists("Weighbridge Ticket", {"autograde_visit_id": visit_id}):
				continue
			# Seeded per visit, not once for the run: a visit that already exists is
			# skipped, and a shared generator would then hand every later visit different
			# numbers than the first run did. This way re-running is a true no-op, and
			# `days=30` reproduces the same week `days=7` made.
			rng = random.Random(f"{SEED}:{visit_id}")
			# Today's last two visits stay mid-flow on purpose: one still on the
			# weighbridge, one already graded. A demo where every row is Finalised never
			# shows what the status column is for.
			stage = _stage(back, i, count)
			if _make_visit(rng, date, i, trucks[rng.randrange(len(trucks))], visit_id, blocks, stage):
				made += 1
			# Per visit: a week of tickets is thousands of documents, and holding them all
			# in one transaction is what makes a seeder look hung.
			# nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
			frappe.db.commit()
	return made


def _stage(back, i, count):
	"""Where this visit stopped. Today's last two are left mid-flow on purpose — one just
	through the gate, one already graded — so the demo has open tickets and is not a wall
	of Finalised rows. Every other visit is complete.

	Both read `Waiting Weight`, which is right: `set_status` reports the missing weight
	first, and neither has weighed out yet. The difference is in the grading columns —
	the graded one carries its bunch counts and sortasi rows, the gate one is empty.
	"""
	if back != 0:
		return "done"
	if i == count - 1:
		return "gate"
	if i == count - 2:
		return "graded"
	return "done"


def _make_visit(rng, date, i, plate, visit_id, blocks, stage):
	supplier = frappe.db.get_value("Truck", plate, "supplier")
	internal = not supplier

	hour = 7 + (i * 11) % 11  # spread over a working day, deterministic
	minute = rng.randint(0, 59)
	time_in = datetime.time(hour, minute)
	time_out = datetime.time(hour + 1, minute)

	gross = float(rng.randrange(9000, 24000, 10))
	tare = float(rng.randrange(4000, min(int(gross) - 2500, 8000), 10))

	ticket = frappe.get_doc(
		{
			"doctype": "Weighbridge Ticket",
			"company": DEMO_COMPANY,
			"ticket_date": date,
			"truck": plate,
			"supplier": supplier,
			"sumber_tbs": "Internal" if internal else "External",
			"blok": rng.choice(blocks) if internal and blocks else None,
			"driver_name": rng.choice(DRIVERS),
			"time_in": time_in,
			"gross_weight_kg": gross,
			"autograde_visit_id": visit_id,
			"scale_ticket_no": f"TKT-{date:%y%m%d}-{i:03d}",
		}
	)

	if stage == "gate":
		# Through the gate, fruit still on the truck: no tare, no grading yet.
		ticket.insert(ignore_permissions=True)
		return True

	if stage == "graded":
		# Graded on the line but not yet weighed out — the state that shows why the ticket
		# waits for two independent inputs instead of being written once.
		_apply_grading(rng, ticket)
		ticket.insert(ignore_permissions=True)
		return True

	ticket.update(
		{
			"time_out": time_out,
			"tare_weight_kg": tare,
			"net_weight_kg": gross - tare,
			"weight_received_at": frappe.utils.now_datetime(),
		}
	)
	_apply_grading(rng, ticket)
	ticket.flags.recompute = True
	ticket.insert(ignore_permissions=True)
	ticket.try_finalize()
	return True


def _apply_grading(rng, ticket):
	"""AI shares, plus the bunch counts the ticket shows next to them."""
	mentah = round(rng.uniform(*MENTAH_RANGE), 2)
	tangkai = round(rng.uniform(*TANGKAI_RANGE), 2)
	for kriteria, persen in (
		("Mentah", mentah),
		("Tangkai Panjang", tangkai),
		("Matang", round(100 - mentah - tangkai, 2)),
	):
		ticket.append("grading", {"kriteria": kriteria, "persen": persen})

	# Bunches, not kilograms: roughly 20 kg a bunch, and Mentah % of them rejected. A
	# ticket graded before it weighs out has no net yet, so estimate from the gross the
	# gate recorded — which is what the line actually knows at that moment.
	weight = flt(ticket.net_weight_kg) or flt(ticket.gross_weight_kg) * 0.6
	total = max(1, int(weight / 20))
	rej = int(total * mentah / 100)
	ticket.update(
		{
			"grading_total": total,
			"grading_acc": total - rej,
			"grading_rej": rej,
			"autograde_assignment_id": ticket.autograde_visit_id.replace(VISIT_PREFIX, "ASG-"),
			"grading_received_at": frappe.utils.now_datetime(),
		}
	)


# --------------------------------------------------------------------------- reset
def reset(force=0, days=DAYS, quiet=0):
	"""Delete every ticket this module made (and what they created), then seed again.

	Masters, suppliers, trucks and users are left in place: they are what a client's own
	data would replace, and rebuilding them each time would churn the account tree.
	"""
	_check_allowed(force)
	relax_snapshot_isolation()
	drain_queue()
	removed = wipe_visits(quiet=quiet)
	_say(quiet, f"  removed {removed} tickets")
	return seed(force=1, days=days, quiet=quiet)


def wipe_visits(quiet=0):
	"""Cancel and delete the demo tickets, receipts and stock entries — in dependency order."""
	tickets = frappe.get_all(
		"Weighbridge Ticket",
		filters={"autograde_visit_id": ["like", f"{VISIT_PREFIX}%"]},
		fields=["name", "docstatus", "purchase_receipt", "stock_entry"],
	)
	for i, t in enumerate(tickets):
		if i % 20 == 0:
			drain_queue()  # cancelling enqueues too; same ceiling applies
		for doctype, name in (
			("Purchase Receipt", t.purchase_receipt),
			("Stock Entry", t.stock_entry),
		):
			if name and frappe.db.exists(doctype, name):
				_force_delete(doctype, name)
		_force_delete("Weighbridge Ticket", t.name)
		# Per ticket: cancelling and deleting submitted documents is slow, and a partial
		# wipe must stay wiped.
		# nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
		frappe.db.commit()
	return len(tickets)


def _force_delete(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		doc.flags.ignore_permissions = True
		doc.cancel()
	frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)


# ------------------------------------------------------------------------- summary
def summary():
	"""What was built and how to sign in — printed after seeding, and callable on its own."""
	counts = {
		"Weighbridge Ticket": {"autograde_visit_id": ["like", f"{VISIT_PREFIX}%"]},
		"Purchase Receipt": {"company": DEMO_COMPANY, "docstatus": 1},
		"Stock Entry": {"company": DEMO_COMPANY, "docstatus": 1},
		"Truck": {},
		"Supplier": {"supplier_group": ["in", ("Plasma", "Agen TBS")]},
		"Blok": {},
	}
	lines = [f"AutoERP demo — {DEMO_COMPANY}", ""]
	for doctype, filters in counts.items():
		lines.append(f"  {frappe.db.count(doctype, filters):>5}  {doctype}")
	lines += ["", "  Desk logins (password: %s)" % DEMO_PASSWORD]
	for email, first, last, _roles in DESK_USERS:
		lines.append(f"    {email:<32} {first} {last}")
	lines += ["", "  Administrator still signs in with its own password."]
	return "\n".join(lines)
