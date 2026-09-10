# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WeighbridgeTicket(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.palm_mill.doctype.weighbridge_grading.weighbridge_grading import WeighbridgeGrading

		amended_from: DF.Link | None
		blok: DF.Link | None
		catatan: DF.SmallText | None
		company: DF.Link
		driver_name: DF.Data | None
		grading: DF.Table[WeighbridgeGrading]
		gross_weight_kg: DF.Float
		harga_per_kg: DF.Currency
		net_after_deduction_kg: DF.Float
		net_weight_kg: DF.Float
		nilai: DF.Currency
		potongan_pct: DF.Percent
		purchase_receipt: DF.Link | None
		sampah_kg: DF.Float
		sertifikasi: DF.Literal["ISPO", "RSPO", "Non-sertifikasi"]
		stock_entry: DF.Link | None
		sumber_tbs: DF.Literal["Inti", "Plasma", "Pihak Ketiga"]
		supplier: DF.Link | None
		tare_weight_kg: DF.Float
		ticket_date: DF.Date
		time_in: DF.Time | None
		time_out: DF.Time | None
		truck: DF.Link | None
		vehicle_class: DF.Data | None
		vehicle_no: DF.Data | None
	# end: auto-generated types

	pass
