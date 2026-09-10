# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Truck(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		disabled: DF.Check
		driver_name: DF.Data | None
		plate_number: DF.Data
		supplier: DF.Link | None
		vehicle_class: DF.Literal["Colt Diesel", "Dump Truck", "Tronton"]
	# end: auto-generated types

	pass
