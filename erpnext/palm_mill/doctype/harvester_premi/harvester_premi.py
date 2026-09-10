# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class HarvesterPremi(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		basis_kg: DF.Float
		company: DF.Link | None
		diatas_basis_kg: DF.Float
		divisi: DF.Literal["I", "II", "III", "IV"]
		journal_entry: DF.Link | None
		jumlah_pemanen: DF.Int
		kebun: DF.Literal["Sungai Rambang", "Air Batu"]
		premi_rp: DF.Currency
		tanggal: DF.Date
		tonnase_kg: DF.Float
	# end: auto-generated types

	pass
