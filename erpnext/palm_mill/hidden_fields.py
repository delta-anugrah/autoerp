# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Fields a palm mill never fills in, hidden from the UI instead of removed.

These are native ERPNext fields on Stock Entry and Purchase Receipt. Deleting them
would mean editing core DocType JSON, which conflicts on every upstream pull and
breaks the documents' own logic — `is_return` and `per_transferred` are written by
ERPNext itself. Hiding is reversible and touches nothing but the form layout.

Property Setters are applied idempotently from `after_install` and from the
`palm_mill_hidden_fields` patch, so they survive a fresh install and a migrate.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# (doctype, fieldname, why it is never used here)
HIDDEN_FIELDS = (
	# A palm mill receives FFB; it never moves it between warehouses from this form.
	# make_stock_entry() maps to_warehouse onto the item row's `t_warehouse`, so the
	# parent-level defaults are dead weight on a Material Receipt.
	("Stock Entry", "from_warehouse", "no source warehouse on a Material Receipt"),
	("Stock Entry", "to_warehouse", "the receiving warehouse comes from Palm Mill Settings"),
	# Progress counters, only meaningful for Material Transfer and for returns.
	("Stock Entry", "per_transferred", "Material Transfer only"),
	("Stock Entry", "is_return", "FFB receipts are never returns"),
	("Purchase Receipt", "is_return", "FFB receipts are never returns"),
	("Purchase Receipt", "per_returned", "FFB receipts are never returns"),
)


# `hidden` only governs the form. The list view builds its columns from
# `in_list_view` and its filter row from `in_standard_filter`, so a field hidden on
# the form still shows up as an empty column and a filter until those are cleared.
PROPERTIES = (("hidden", 1), ("in_list_view", 0), ("in_standard_filter", 0))


def hide_unused_fields():
	"""Idempotent: a Property Setter is named `<doctype>-<field>-<property>`, and its
	validate() drops the existing row of that name before inserting, so re-running
	replaces rather than duplicates."""
	for doctype, fieldname, _reason in HIDDEN_FIELDS:
		if not frappe.get_meta(doctype).get_field(fieldname):
			continue  # upstream dropped or renamed it; nothing to hide
		for prop, value in PROPERTIES:
			make_property_setter(
				doctype,
				fieldname,
				prop,
				value,
				"Check",
				validate_fields_for_doctype=False,
			)
	frappe.clear_cache()
