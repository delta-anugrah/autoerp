# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.palm_mill.utils import canonical_plate, normalize_plate


class Truck(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		autograde_id: DF.Data | None
		disabled: DF.Check
		driver_name: DF.Data | None
		pending: DF.Check
		plate_normalized: DF.Data | None
		plate_number: DF.Data
		source: DF.Literal["Manual", "AutoGrade", "Scale"]
		supplier: DF.Link | None
		vehicle_class: DF.Literal["", "Colt Diesel", "Dump Truck", "Tronton"]
	# end: auto-generated types

	def validate(self):
		self.plate_normalized = normalize_plate(self.plate_number)
		if not self.plate_normalized:
			frappe.throw(_("Plate number must contain letters or digits"))

		other = frappe.db.get_value(
			"Truck", {"plate_normalized": self.plate_normalized, "name": ["!=", self.name]}, "name"
		)
		if other:
			frappe.throw(
				_("Plate {0} is already registered as Truck {1}").format(self.plate_number, other),
				frappe.DuplicateEntryError,
			)

		# "Perlu Dilengkapi" clears itself once the backoffice has filled the owner and class.
		if self.pending and self.supplier and self.vehicle_class:
			self.pending = 0


def get_truck_by_plate(plate: str) -> str | None:
	return frappe.db.get_value("Truck", {"plate_normalized": normalize_plate(plate)}, "name")


def get_or_create_truck(
	plate: str,
	source: str = "Manual",
	supplier: str | None = None,
	vehicle_class: str | None = None,
	autograde_id: str | None = None,
) -> Truck:
	"""Resolve a plate to a Truck, creating a pending one when the mill sees it first.

	An existing truck is never overwritten by an integration: only an empty
	`autograde_id` is filled in. Master data is owned in AutoERP.
	"""
	name = get_truck_by_plate(plate)
	if name:
		truck = frappe.get_doc("Truck", name)
		if autograde_id and not truck.autograde_id:
			truck.autograde_id = autograde_id
			truck.save()
		return truck

	truck = frappe.get_doc(
		{
			"doctype": "Truck",
			"plate_number": canonical_plate(plate),
			"supplier": supplier,
			"vehicle_class": vehicle_class,
			"autograde_id": autograde_id,
			"source": source,
			"pending": 1,
		}
	)
	truck.insert()
	return truck
