# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WeighbridgeGrading(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		berat_kg: DF.Float
		keterangan: DF.Data | None
		kriteria: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		persen: DF.Percent
	# end: auto-generated types

	pass
