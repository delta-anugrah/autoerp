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


def after_install():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=frappe.flags.in_patch, update=True)
	setup_roles()
	set_defaults()


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
