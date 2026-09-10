# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PalmMillSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.palm_mill.doctype.palm_mill_grading_rule.palm_mill_grading_rule import (
			PalmMillGradingRule,
		)

		buying_price_list: DF.Link | None
		create_stock_documents_on_submit: DF.Check
		default_potongan_pct: DF.Percent
		grading_rules: DF.Table[PalmMillGradingRule]
		grading_timeout_hours: DF.Int
		inti_expense_account: DF.Link | None
		match_window_hours: DF.Int
		max_potongan_pct: DF.Percent
		plasma_supplier_group: DF.Link | None
		purchase_cost_center: DF.Link | None
		tbs_item: DF.Link | None
		tbs_warehouse: DF.Link | None
	# end: auto-generated types

	pass
