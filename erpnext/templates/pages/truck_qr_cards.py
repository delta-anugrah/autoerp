# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Printable sheet of truck QR cards, opened from the Truck list in ERP Desk.

A page rather than a Print Format: the cards are a grid of images cut apart with
scissors, not a document, and the browser's own print dialog already does the job.
"""

import frappe
from frappe import _

from erpnext.palm_mill.qr_card import cards

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		raise frappe.PermissionError

	names = frappe.parse_json(frappe.form_dict.get("trucks") or "[]")
	if not names:
		frappe.throw(_("Select at least one truck to print"), frappe.ValidationError)

	context.no_cache = 1
	context.title = _("Truck QR Cards")
	context.cards = cards(names)
	# Named separately so the template does not have to count a filtered list twice.
	context.unscannable = [card for card in context.cards if not card["qr"]]
