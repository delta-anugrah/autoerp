# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Blok(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		blok_code: DF.Data
		divisi: DF.Literal["I", "II", "III", "IV"]
		jumlah_pokok: DF.Int
		kebun: DF.Literal["Sungai Rambang", "Air Batu"]
		luas_ha: DF.Float
		sertifikasi: DF.Literal["ISPO", "RSPO", "Non-sertifikasi"]
		tahun_tanam: DF.Int
	# end: auto-generated types

	pass
