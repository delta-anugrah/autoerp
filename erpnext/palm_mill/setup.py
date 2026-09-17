# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Install-time setup for the Palm Mill module.

Runs from the `after_install` hook and from the `setup_palm_mill` patch, so it must
stay idempotent. Everything here is site data the module needs but cannot ship as
DocType JSON: fields on native DocTypes, roles, settings defaults.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission

# Namanya membawa "palem" supaya berbeda dari berkas huruf "A" yang pernah ada di
# URL lama: browser menyimpan favicon per URL dan tidak menengok lagi selama URL-nya
# sama, jadi mengganti isi berkas saja meninggalkan lambang lama di tab orang.
FAVICON = "/assets/erpnext/images/autoerp-favicon-palem.svg"
FAVICON_LAMA = ("/assets/erpnext/images/autoerp-favicon.svg",)
OPERATOR_ROLE = "Weighbridge Operator"
INTEGRATION_ROLE = "Palm Mill Integration"
ROLES = (OPERATOR_ROLE, INTEGRATION_ROLE)
# Finalising a ticket creates a Purchase Receipt or Stock Entry, with ERPNext's own
# permission checks on everything underneath (batches, bundles). Same roles a human
# receiving stock would hold.
INTEGRATION_USER_ROLES = (INTEGRATION_ROLE, "Purchase User", "Stock User")

# The estate masters are System Manager only in their DocType JSONs, but the mill sidebar
# links them. A sidebar item whose has_permission fails is dropped silently, and a section
# is only suppressed once every item under it is gone — so without read here an operator
# gets a "Kebun & Blok" heading with nothing beneath it.
READ_ONLY_MASTERS = (
	"Supplier",
	"Blok",
	"Kebun",
	"Divisi",
	"Sumber TBS",
	"Sertifikasi",
)

# Same names and properties the demo generator used, so existing sites see no change.
CUSTOM_FIELDS = {
	"Batch": [
		{
			"fieldname": "custom_source_batches",
			"label": _("Source Batches"),
			"fieldtype": "Small Text",
			"insert_after": "parent_batch",
			"read_only": 1,
		},
		{
			"fieldname": "custom_source_stock_entry",
			"label": _("Produced By"),
			"fieldtype": "Link",
			"options": "Stock Entry",
			"insert_after": "custom_source_batches",
			"read_only": 1,
		},
		{
			"fieldname": "custom_sertifikasi",
			"label": "Certification",
			"fieldtype": "Data",
			"insert_after": "custom_source_stock_entry",
			"description": _("Certification mix of the FFB that produced this batch"),
		},
	],
	"Purchase Receipt Item": [
		{
			"fieldname": "custom_grading_note",
			"label": _("Grading Note"),
			"fieldtype": "Small Text",
			"insert_after": "discount_percentage",
		},
	],
	"Purchase Receipt": [
		{
			"fieldname": "custom_weighbridge_ticket",
			"label": "Weighbridge Ticket",
			"fieldtype": "Link",
			"options": "Weighbridge Ticket",
			"insert_after": "supplier",
		},
	],
}

# (kriteria, deduction % per 1 % of the criterion) — the demo generator's POTONGAN_WEIGHTS.
DEFAULT_GRADING_RULES = (("Mentah", 60), ("Lewat Matang", 15), ("Tangkai Panjang", 100))
DEFAULT_SETTINGS = {
	"max_potongan_pct": 18,
	"default_potongan_pct": 0,
	"grading_timeout_hours": 6,
	"match_window_hours": 2,
}


# Seed masters ERPNext creates for every company but a mill never uses. Defined here
# rather than in the patch so the patch and the install hook cannot drift apart.
SEED_WAREHOUSES = ("Finished Goods", "Goods In Transit", "Stores", "Work In Progress")
SEED_ITEM_GROUPS = ("Services", "Sub Assemblies")


# The two FFB sources the module reasons about (utils.PURCHASED_SOURCES, sumber_for_supplier).
# Ticket.sumber_tbs is mandatory and links here, so a site without these rows cannot take
# a visit; the demo dump carried them, a fresh install must create them.
SOURCES = ("Internal", "External")


def after_install():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=frappe.flags.in_patch, update=True)
	setup_roles()
	setup_sources()
	set_defaults()
	set_favicon()
	apply_site_policy()


def setup_wizard_complete(wizard_args=None):
	"""Runs once the wizard has created the company.

	`hide_seed_masters` cannot live in `after_install`: the warehouses come from
	`Company.create_default_warehouses` and the item groups from the wizard's
	`install_fixtures`, both of which run later. Called from the install hook it would
	match nothing and leave the clutter in place without saying so.

	Frappe passes the wizard's own arguments to every hook positionally, so this has to
	accept them even though the policy does not read them -- a function that refuses them
	fails the final stage of the wizard, after the company already exists. The parameter
	is named rather than called `args` to keep it out of semgrep's `overusing-args`.
	"""
	apply_site_policy()
	hide_seed_masters()


def apply_site_policy():
	"""The settings a mill site has to be born with.

	A fresh site never runs patches -- `install_app` marks them completed without
	executing any -- so everything the patches below do for existing sites has to be
	done here too, or a new site comes up in English, at three decimals, and unable to
	receive FFB at all.
	"""
	set_site_language()
	set_float_precision()
	enable_serial_and_batch()


def set_site_language():
	"""Indonesian by default, still switchable per user from the menu."""
	frappe.db.set_value("Language", "id", "enabled", 1, update_modified=False)
	frappe.db.set_single_value("System Settings", "language", "id")
	# `User.language` outranks the site setting, so users pinned to the old default would
	# stay in English with nothing on screen explaining why.
	frappe.db.sql("update `tabUser` set language = NULL where language = 'en-US'")


def set_float_precision():
	"""A mill reads kilograms and percentages to two places at most, and Frappe uses this
	one setting for every Float and Percent it shows."""
	frappe.db.set_single_value("System Settings", "float_precision", "2")
	frappe.db.set_default("float_precision", "2")  # what bootinfo serves; only a UI save refreshes it


def enable_serial_and_batch():
	"""Without this, finalising a ticket fails 417 and no amount of correct grading data
	gets FFB into the system.

	The upstream v16 patch only turns it on for sites that already have a Batch. A site
	born empty has none, so it stays off exactly where it is needed most.
	"""
	frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)


def hide_seed_masters():
	"""ERPNext's starter warehouses and item groups, out of the way of the mill sidebar.

	Hidden only where they carry nothing: a warehouse with ledger entries is somebody's
	data and disabling it would break their stock transactions.
	"""
	for wh in frappe.get_all("Warehouse", filters={"warehouse_name": ("in", SEED_WAREHOUSES)}, pluck="name"):
		if not frappe.db.exists("Stock Ledger Entry", {"warehouse": wh}):
			frappe.db.set_value("Warehouse", wh, "disabled", 1, update_modified=False)
	for ig in SEED_ITEM_GROUPS:
		if (
			frappe.db.exists("Item Group", ig)
			and not frappe.db.exists("Item", {"item_group": ig})
			and not frappe.db.exists("Item Group", {"parent_item_group": ig})
		):
			frappe.delete_doc("Item Group", ig, ignore_permissions=True, force=True)


def setup_sources():
	for title in SOURCES:
		if not frappe.db.exists("Sumber TBS", title):
			frappe.get_doc({"doctype": "Sumber TBS", "title": title}).insert(ignore_permissions=True)


def set_favicon():
	"""The tab icon is the one piece of branding `app_logo_url` does not reach.

	Frappe renders `<link rel="shortcut icon">` from `Website Settings.favicon` and
	falls back to Frappe's own mark when it is empty, so a site that never set it
	shows an "F" in the tab no matter what the app ships.

	Fills a blank one, and moves a site still pointing at one of our own older files
	onto the current name. A favicon somebody uploaded is left alone — that is their
	choice, not ours to overwrite.
	"""
	sekarang = frappe.db.get_single_value("Website Settings", "favicon")
	if sekarang and sekarang not in FAVICON_LAMA:
		return
	frappe.db.set_single_value("Website Settings", "favicon", FAVICON)


def setup_roles():
	"""Roles are created by DocType sync from the permission rows; here they only get
	read access to the native masters the ticket form links to."""
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
		for doctype in READ_ONLY_MASTERS:
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role)


def set_defaults():
	"""Singles do not pick up DocField defaults on their own (see erpnext.setup.install)."""
	settings = frappe.get_single("Palm Mill Settings")
	changed = False
	if not settings.grading_rules:
		for kriteria, pct in DEFAULT_GRADING_RULES:
			settings.append("grading_rules", {"kriteria": kriteria, "deduction_pct": pct})
		changed = True
	for fieldname, value in DEFAULT_SETTINGS.items():
		if settings.get(fieldname) is None:
			settings.set(fieldname, value)
			changed = True
	for fieldname, doctype, name in (
		("tbs_item", "Item", "TBS"),
		("cpo_item", "Item", "CPO"),
		("kernel_item", "Item", "PK"),
	):
		if not settings.get(fieldname) and frappe.db.exists(doctype, name):
			settings.set(fieldname, name)
			changed = True
	if changed:
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)


def create_integration_user(email: str, full_name: str) -> dict:
	"""A System User with the integration role plus the stock roles finalisation needs,
	and an API key/secret for `Authorization: token key:secret`. Re-running regenerates
	the secret."""
	from frappe.core.doctype.user.user import generate_keys

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		missing = set(INTEGRATION_USER_ROLES) - {r.role for r in user.roles}
		for role in missing:
			user.append("roles", {"role": role})
		if missing:
			user.save(ignore_permissions=True)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in INTEGRATION_USER_ROLES],
			}
		).insert(ignore_permissions=True)

	secret = generate_keys(user.name)["api_secret"]
	return {
		"user": user.name,
		"api_key": frappe.db.get_value("User", user.name, "api_key"),
		"api_secret": secret,
	}
