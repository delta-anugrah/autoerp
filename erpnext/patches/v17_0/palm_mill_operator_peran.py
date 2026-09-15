"""Isi `peran` untuk akun yang dibuat sebelum field ini ada.

Semuanya jadi `operator`. Menaikkan seseorang jadi `support` adalah keputusan
sadar per orang, bukan efek samping sebuah migrasi.
"""

import frappe


def execute():
	frappe.reload_doc("palm_mill", "doctype", "autograde_operator")
	frappe.db.sql(
		"""UPDATE `tabAutoGrade Operator`
		   SET peran = 'operator'
		   WHERE peran IS NULL OR peran = ''"""
	)
